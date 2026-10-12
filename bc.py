"""Short wrapper around laya_player.claude_cli so each move is a few words.

Usage (from laya-player/):
    python bc.py show
    python bc.py play 1 2 3
    python bc.py discard 0 4
    python bc.py do 0 "play this blind"     # text is forwarded as-is
    python bc.py new [SEED]

Every argument after the script name is passed straight to claude_cli, so the
guard that checks option text still applies. Use plain strings for `do` text;
no shell `$` expansion happens here, which avoids the "$10" -> "0" problem.
"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENV_PY = HERE / ".venv" / "Scripts" / "python.exe"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    py = str(VENV_PY) if VENV_PY.exists() else sys.executable
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    cmd = [py, "-m", "laya_player.claude_cli", *sys.argv[1:]]
    return subprocess.call(cmd, cwd=HERE, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
