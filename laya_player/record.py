"""Record one real Balatro run played by Laya, with its decisions burned in as subtitles.

ffmpeg captures the game window (gdigrab) while `evolve.play_run` plays; the evolve.log lines
written during the run become an .srt, and the final cut is sped up with subtitles retimed.

  python -m laya_player.record --seed 71SHDI9E --speed 4
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import time
from pathlib import Path

from . import evolve, realloop
from .bridge import Bridge

ROOT = Path(__file__).resolve().parent.parent
LINE = re.compile(r"^(\d\d:\d\d:\d\d) \[g-1 (a\d+ \S+)\] (?:(\S+) )?-> (.*?)(?: \(p=([\d.]+)\))?$")


def srt_time(s: float) -> str:
    ms = int(round(s * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def build_srt(log_lines: list[str], t0: dt.datetime, speed: float, out: Path) -> int:
    events = []
    for l in log_lines:
        m = LINE.match(l.strip())
        if not m:
            continue
        hh, mm, ss = map(int, m[1].split(":"))
        t = t0.replace(hour=hh, minute=mm, second=ss)
        if t < t0:
            t += dt.timedelta(days=1)
        where, score, act, p = m[2], m[3], m[4], m[5]
        text = f"{where.replace('a', 'Ante ', 1)}{'  ' + score if score else ''}\nLaya: {act}" + (f"  (p={p})" if p else "")
        events.append(((t - t0).total_seconds() / speed, text))
    with open(out, "w", encoding="utf8") as f:
        for i, (s, text) in enumerate(events):
            e = events[i + 1][0] if i + 1 < len(events) else s + 3
            f.write(f"{i + 1}\n{srt_time(s)} --> {srt_time(max(s + 0.5, e))}\n{text}\n\n")
    return len(events)


class GameWindow:
    """Put the Balatro window on the primary monitor, on top, for desktop-duplication capture
    (gdigrab mis-crops under mixed DPI, and ddagrab only sees outputs of the primary adapter)."""

    def __init__(self):
        import ctypes
        import win32con
        import win32gui
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        self.g, self.c = win32gui, win32con
        self.h = win32gui.FindWindow(None, "Balatro")
        if not self.h:
            raise RuntimeError("Balatro window not found")
        self.orig = win32gui.GetWindowRect(self.h)

    def __enter__(self):
        l, t, r, b = self.orig
        self.g.SetWindowPos(self.h, self.c.HWND_TOPMOST, 40, 40, r - l, b - t, self.c.SWP_SHOWWINDOW)
        time.sleep(1.5)
        x, y = self.g.ClientToScreen(self.h, (0, 0))
        _, _, w, h = self.g.GetClientRect(self.h)
        self.region = (x, y, w - w % 2, h - h % 2)
        return self

    def __exit__(self, *exc):
        l, t, r, b = self.orig
        self.g.SetWindowPos(self.h, self.c.HWND_NOTOPMOST, l, t, r - l, b - t, self.c.SWP_SHOWWINDOW)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", default=None)
    ap.add_argument("--speed", type=float, default=4.0)
    ap.add_argument("--out", default=str(ROOT / "runs" / "video" / "laya_balatro.mp4"))
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--ckpt", default=None)
    args = ap.parse_args()
    from .policy import Policy

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    raw, srt = out.with_suffix(".raw.mp4"), out.with_suffix(".srt")
    ck = args.ckpt or realloop.champion(str(ROOT / "ckpt" / "rich_init.pt"))
    pol = Policy(ck, device=args.device)
    try:
        b = Bridge(timeout=10)
    except OSError:
        b = evolve.restart_game()
    (evolve.RUNS / "decisions").mkdir(parents=True, exist_ok=True)
    log_f = evolve.RUNS / "evolve.log"
    n0 = sum(1 for _ in open(log_f, encoding="utf8")) if log_f.exists() else 0
    run_args = argparse.Namespace(fresh=True, deck="b_red", stake=1, seed=args.seed, max_decisions=10000,
                                  greedy=True, temperature=0.3)
    run_id = f"video_{Path(ck).stem}_{args.seed}_{time.strftime('%m%d_%H%M%S')}"
    with GameWindow() as win:
        x, y, w, h = win.region
        ff = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                               f"ddagrab=output_idx=0:framerate=30:offset_x={x}:offset_y={y}:video_size={w}x{h}",
                               "-vf", "hwdownload,format=bgra,format=yuv420p", "-c:v", "libx264", "-preset",
                               "ultrafast", str(raw)], stdin=subprocess.PIPE)
        t0 = dt.datetime.now().replace(microsecond=0)
        time.sleep(1)
        try:
            summary, _ = evolve.play_run(b, pol, -1, run_id, run_args)
            time.sleep(4)  # keep the game-over screen
        finally:
            ff.communicate(b"q", timeout=60)
    lines = open(log_f, encoding="utf8").read().splitlines()[n0:]
    n = build_srt(lines, t0, args.speed, srt)
    title = (f"Laya (421M ModernBERT decision model) plays Balatro - {Path(ck).stem}, seed {summary.get('seed')}, "
             f"{args.speed:g}x speed").replace(":", r"\:").replace("'", "")
    srt_arg = str(srt).replace("\\", "/").replace(":", r"\:")
    vf = (f"setpts=PTS/{args.speed},scale=1280:-2,"
          f"drawtext=text='{title}':x=12:y=10:fontsize=20:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=6,"
          f"subtitles='{srt_arg}':force_style='FontName=Segoe UI Symbol,FontSize=15,Alignment=2,"
          f"BorderStyle=3,Outline=1,BackColour=&H90000000,MarginV=24'")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(raw), "-vf", vf, "-r", "30", "-an",
                    "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p", str(out)], check=True)
    print(f"{out}: {summary['rounds_won']} rounds, ante {summary['max_ante']}, {summary['outcome']}; {n} subtitles")


if __name__ == "__main__":
    main()
