"""Mirror simulator training on the GPU box to this PC: the champion checkpoint and the logs.

Training runs remotely (`run_stage2_n8.sh`); the real game runs here. `realloop` reads the local
runs_sim/state.json, so it always validates the newest champion.

  python -m laya_player.remote_sync --host n8
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / "runs_sim"
CK = ROOT / "ckpt_sim"


def ssh(host: str, cmd: str) -> str:
    return subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", host, cmd],
                          capture_output=True, text=True, timeout=120).stdout


def scp(host: str, remote: str, local: Path) -> bool:
    tmp = local.with_suffix(local.suffix + ".part")
    ok = subprocess.run(["scp", "-q", "-o", "BatchMode=yes", f"{host}:{remote}", str(tmp)],
                        timeout=1800).returncode == 0
    if ok:
        try:
            tmp.replace(local)
        except PermissionError:  # a reader (e.g. `tail -F`) holds the file open on Windows: overwrite in place
            local.write_bytes(tmp.read_bytes())
            tmp.unlink()
    return ok


def sync(host: str, root: str) -> str | None:
    raw = ssh(host, f"cat {root}/runs_sim/state.json 2>/dev/null || (test -f {root}/ckpt/raw_init.pt && "
                    f"echo '{{\"iter\": 0, \"champion\": \"ckpt/raw_init.pt\"}}')").strip()
    if not raw:
        return None
    st = json.loads(raw)
    remote = st["champion"] if st["champion"].startswith("/") else f"{root}/{st['champion']}"
    local = CK / Path(remote).name
    if not local.exists() and not scp(host, remote, local):
        return None
    for f in ("simloop.log", "iters.jsonl"):
        scp(host, f"{root}/runs_sim/{f}", LOCAL / f)
    for remote_f, local_f in (("raw_init_eval.json", "raw_init_eval.json"), ("stage2.log", "stage2_n8.log"),
                              ("stage3.log", "stage3_n8.log"), ("ladder_calc.json", "ladder_calc.json")):
        scp(host, f"{root}/runs/{remote_f}", ROOT / "runs" / local_f)
    st["champion"] = str(local)
    (LOCAL / "state.json").write_text(json.dumps(st), encoding="utf8")
    return local.name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="n8")
    ap.add_argument("--root", default="laya-player", help="project dir on the host (relative to home)")
    ap.add_argument("--every", type=int, default=120)
    args = ap.parse_args()
    LOCAL.mkdir(exist_ok=True)
    CK.mkdir(exist_ok=True)
    last = None
    while True:
        try:
            ck = sync(args.host, args.root)
            if ck and ck != last:
                print(time.strftime("%H:%M:%S"), "champion", ck, flush=True)
                last = ck
        except (subprocess.SubprocessError, OSError, ValueError) as e:
            print(time.strftime("%H:%M:%S"), "sync failed:", e, flush=True)
        time.sleep(args.every)


if __name__ == "__main__":
    main()
