"""Direct JSON-RPC client for the balatro-agent Lua mod (bypasses the TS MCP server).

The mod serves exactly one client on a named pipe (Windows) or AF_UNIX socket, speaking
newline-delimited JSON-RPC 2.0. Close any MCP server that holds the pipe before connecting.
"""
from __future__ import annotations

import itertools
import json
import os
import socket
import sys
import select
import time
from typing import Any

DEFAULT_SOCKET = r"\\.\pipe\balatro-mcp" if sys.platform == "win32" else "/tmp/balatro-mcp.sock"


class BridgeError(RuntimeError):
    def __init__(self, code: str, message: str, data: Any = None):
        super().__init__(f"{code}: {message}")
        self.code, self.message, self.data = code, message, data


class Bridge:
    def __init__(self, path: str | None = None, timeout: float = 30.0):
        self.path = path or os.environ.get("BALATRO_BRIDGE_SOCKET", DEFAULT_SOCKET)
        self.timeout = timeout
        self._ids = itertools.count(1)
        self._open()

    def _open(self) -> None:
        deadline = time.time() + self.timeout
        while True:
            try:
                if sys.platform == "win32":
                    self._f = open(self.path, "r+b", buffering=0)
                else:
                    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    s.connect(self.path)
                    self._f = s.makefile("rwb", buffering=0)
                break
            except OSError:
                if time.time() > deadline:
                    raise
                time.sleep(0.5)
        self._buf = b""
        self.info = self.call("connect")

    def close(self) -> None:
        self._f.close()

    def _poll(self) -> bytes:
        """Non-blocking read. A synchronous Windows pipe handle serialises I/O, so a blocking
        reader thread would deadlock writes; peek first instead. A crashed game then surfaces
        as TimeoutError in `call` rather than a hang."""
        if sys.platform == "win32":
            import msvcrt
            import win32pipe
            _, avail, _ = win32pipe.PeekNamedPipe(msvcrt.get_osfhandle(self._f.fileno()), 0)
            if not avail:
                return b""
            chunk = self._f.read(avail)
        else:
            if not select.select([self._f], [], [], 0)[0]:
                return b""
            chunk = self._f.read(65536)
        if not chunk:
            raise ConnectionError("bridge closed")
        return chunk

    def call(self, method: str, params: dict | None = None, timeout: float = 60.0) -> Any:
        rid = next(self._ids)
        msg = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            msg["params"] = params
        self._f.write((json.dumps(msg) + "\n").encode())
        deadline = time.time() + timeout
        while True:
            while b"\n" not in self._buf:
                if time.time() > deadline:
                    raise TimeoutError(f"no response to {method} within {timeout:.0f}s")
                chunk = self._poll()
                if chunk:
                    self._buf += chunk
                else:
                    time.sleep(0.005)
            line, self._buf = self._buf.split(b"\n", 1)
            resp = json.loads(line)
            if resp.get("id") == rid:
                break
        if "error" in resp:
            e = resp["error"]
            data = e.get("data") or {}
            raise BridgeError(data.get("error_code", str(e.get("code"))), e.get("message", ""), data)
        res = resp.get("result")
        # action handlers wrap results as {ok, data | error_code, error_message}
        if isinstance(res, dict) and res.get("ok") is False:
            raise BridgeError(res.get("error_code", "ERROR"), res.get("error_message", ""), res)
        if isinstance(res, dict) and "ok" in res:
            return res.get("data", res)
        return res

    def state(self) -> dict:
        return self.call("get_state")
