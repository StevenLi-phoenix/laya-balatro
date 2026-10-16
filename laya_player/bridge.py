r"""Direct JSON-RPC client for the balatro-agent Lua mod (bypasses the TS MCP server).

Each game launch serves newline-delimited JSON-RPC 2.0 on its own endpoint
(`\\.\pipe\balatro-mcp-<instance>` on Windows, `/tmp/balatro-mcp-<instance>.sock` elsewhere) and
publishes a discovery record next to it (mod `src/instance.lua`). The pipe accepts several
clients, so an MCP server may stay connected.
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


def _registry_prefixes() -> list[str]:
    override = os.environ.get("BALATRO_BRIDGE_REGISTRY")
    if override:
        return [override]
    if sys.platform != "win32":
        return ["/tmp/balatro-mcp"]
    # The game writes to its own %TEMP%; a sandboxed shell may point TEMP elsewhere.
    temps = [os.environ.get("TEMP"), os.environ.get("TMP"),
             os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp")]
    return list(dict.fromkeys(os.path.join(t, "balatro-mcp") for t in temps if t))


def discover() -> list[str]:
    """Endpoints of published game instances, newest first. A record is
    `<prefix>-<instance>` holding `id<TAB>endpoint<TAB>published_ms`, refreshed every second
    while the game runs; a crashed game leaves its stale record behind."""
    recs = set()
    for prefix in _registry_prefixes():
        folder, base = os.path.split(prefix)
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for name in names:
            if not name.startswith(base + "-") or name.endswith((".tmp", ".sock")):
                continue
            try:
                with open(os.path.join(folder, name), encoding="utf8") as f:
                    fields = f.read().strip().split("\t")
            except OSError:
                continue
            if len(fields) >= 3 and fields[2].isdigit():
                recs.add((int(fields[2]), fields[1]))
    return [endpoint for _, endpoint in sorted(recs, reverse=True)]


class BridgeError(RuntimeError):
    def __init__(self, code: str, message: str, data: Any = None):
        super().__init__(f"{code}: {message}")
        self.code, self.message, self.data = code, message, data


class Bridge:
    def __init__(self, path: str | None = None, timeout: float = 30.0):
        self.path = path
        self.timeout = timeout
        self._ids = itertools.count(1)
        self._open()

    def _connect(self, endpoint: str) -> None:
        if sys.platform == "win32":
            self._f = open(endpoint, "r+b", buffering=0)
        else:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(endpoint)
            self._f = s.makefile("rwb", buffering=0)
        self.path = endpoint

    def _open(self) -> None:
        """Connect to the given endpoint, else to the newest live instance; wait for one to appear."""
        deadline = time.time() + self.timeout
        explicit = self.path
        while True:
            last: OSError = FileNotFoundError("no Balatro instance published a bridge endpoint")
            for endpoint in [explicit] if explicit else discover():
                try:
                    self._connect(endpoint)
                    break
                except OSError as e:
                    last = e
            else:
                if time.time() > deadline:
                    raise last
                time.sleep(0.5)
                continue
            break
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
