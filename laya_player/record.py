"""Record one real Balatro run played by Laya, with its decisions burned in as subtitles.

ffmpeg captures the game window while `evolve.play_run` plays; the run's decision records carry
millisecond send times, which become the .srt; the final cut is sped up with subtitles retimed.

  python -m laya_player.record --seed 71SHDI9E --speed 4
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path

from . import evolve, realloop
from .bridge import Bridge

ROOT = Path(__file__).resolve().parent.parent


def srt_time(s: float) -> str:
    ms = int(round(s * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def build_srt(decisions: list[dict], t0: float, speed: float, out: Path, who: str = "Laya") -> int:
    """Captions from the decision records' millisecond timestamps (`ts`, when each move was sent).
    Within one decision the caption grows click by click and resets after the committing move,
    so captions never overlap."""
    events, chain = [], []
    for d in decisions:
        if "ts" not in d:
            continue
        act, p = d["options"][d["label"]], d["probs"][d["label"]]
        m = re.search(r"Score (\d+)/(\d+)", d["state"])
        head = f"Ante {d['ante']} {d['phase']}" + (f"  {m[1]}/{m[2]}" if m and d["phase"] == "hand" else "")
        click = act.startswith(("select ", "deselect ", "cancel ")) or "(then choose" in act
        chain.append(f"{act} ({p:.2f})")
        events.append(((d["ts"] - t0) / speed, f"{head}\n{who}: " + " · ".join(chain[-6:])))
        if not click:
            chain = []
    with open(out, "w", encoding="utf8") as f:
        for i, (st, text) in enumerate(events):
            en = events[i + 1][0] if i + 1 < len(events) else st + 3
            f.write(f"{i + 1}\n{srt_time(max(0.0, st))} --> {srt_time(max(st + 0.25, en))}\n{text}\n\n")
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
            raise OSError("Balatro window not found")  # realloop treats it as a lost game
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
        try:
            self.g.SetWindowPos(self.h, self.c.HWND_NOTOPMOST, l, t, r - l, b - t, self.c.SWP_SHOWWINDOW)
        except self.g.error:  # the game crashed and its window is gone
            pass


def start_capture(region: tuple, raw: Path, lag: float = 0.5) -> tuple[subprocess.Popen, float]:
    """ffmpeg desktop-duplication capture of `region` into `raw`; returns the process and the time
    of its first frame (~`lag` after launch). Stop it with `stop_capture`."""
    x, y, w, h = region
    ff = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                           f"ddagrab=output_idx=0:framerate=30:offset_x={x}:offset_y={y}:video_size={w}x{h}",
                           "-vf", "hwdownload,format=bgra,format=yuv420p", "-c:v", "libx264", "-preset",
                           "ultrafast", str(raw)], stdin=subprocess.PIPE)
    return ff, time.time() + lag


def stop_capture(ff: subprocess.Popen) -> None:
    try:
        ff.communicate(b"q", timeout=60)
    except (subprocess.TimeoutExpired, ValueError):
        ff.kill()


def render(raw: Path, decisions: list[dict], t0: float, speed: float, out: Path, who: str, title: str,
           end: float | None = None, slow_from: float | None = None, hold: float = 3.0) -> int:
    """Speed up `raw`, burn in `title` and the decision captions; `end` cuts the raw capture at
    that many seconds. From `slow_from` (raw seconds) on, play at normal speed without captions and
    hold the last frame `hold` seconds (a win screen). Returns the caption count."""
    srt = out.with_suffix(".srt")
    n = build_srt(decisions, t0, speed, srt, who)
    title = title.replace(":", r"\:").replace("'", "")
    # Windows ffmpeg builds have no fontconfig default: name the font file / folder explicitly
    # (without them drawtext crashes with an access violation).
    fonts = r"C\:/Windows/Fonts"
    head = (f"scale=1280:-2,drawtext=fontfile='{fonts}/arial.ttf':text='{title}':x=12:y=10:fontsize=20:"
            f"fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=6")
    subs = (f"subtitles={srt.name}:fontsdir='{fonts}':force_style='FontName=Segoe UI Symbol,FontSize=15,Alignment=2,"
            f"BorderStyle=3,Outline=1,BackColour=&H90000000,MarginV=24'")
    cut = ["-t", f"{end:.2f}"] if end else []
    if slow_from is None:
        filt = ["-vf", f"setpts=PTS/{speed},{head},{subs}"]
    else:
        filt = ["-filter_complex",
                f"[0:v]split[x][y];[x]trim=0:{slow_from:.2f},setpts=(PTS-STARTPTS)/{speed},{head},{subs}[a];"
                f"[y]trim=start={slow_from:.2f},setpts=PTS-STARTPTS,{head},tpad=stop_mode=clone:stop_duration={hold}[b];"
                f"[a][b]concat=n=2:v=1:a=0[v]", "-map", "[v]"]
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *cut, "-i", str(raw.resolve()), *filt, "-r", "30",
                    "-an", "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p", out.name], check=True, cwd=out.parent)
    return n


def still(raw: Path, at: float, out: Path) -> None:
    """One full-resolution frame of `raw` at `at` seconds (a cover image)."""
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{at:.2f}", "-i", str(raw), "-frames:v", "1",
                    str(out)], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", default=None)
    ap.add_argument("--speed", type=float, default=4.0)
    ap.add_argument("--out", default=str(ROOT / "runs" / "video" / "laya_balatro.mp4"))
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--ckpt", default=None)
    ap.add_argument("--api", default=None, help="a decisions-API model id (OpenRouter) playing instead of Laya")
    ap.add_argument("--name", default=None, help="player name in captions and title")
    ap.add_argument("--capture-lag", type=float, default=0.5, help="seconds ffmpeg takes to deliver its first frame")
    args = ap.parse_args()
    from .policy import Policy

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = out.with_suffix(".raw.mp4")
    if args.api:
        from .apiplay import ApiPolicy
        ck, pol = args.api, ApiPolicy(args.api)
    else:
        ck = args.ckpt or realloop.champion(str(ROOT / "ckpt" / "rich_init.pt"))
        pol = Policy(ck, device=args.device)
    who = args.name or ("Laya" if not args.api else args.api)
    try:
        b = Bridge(timeout=10)
    except OSError:
        b = evolve.restart_game()
    (evolve.RUNS / "decisions").mkdir(parents=True, exist_ok=True)
    run_args = argparse.Namespace(fresh=True, deck="b_red", stake=1, seed=args.seed, max_decisions=10000,
                                  greedy=True, temperature=0.3)
    run_id = f"video_{Path(ck).stem.replace('/', '_')}_{args.seed}_{time.strftime('%m%d_%H%M%S')}"
    with GameWindow() as win:
        ff, t0 = start_capture(win.region, raw, args.capture_lag)
        time.sleep(1)
        try:
            summary, _ = evolve.play_run(b, pol, -1, run_id, run_args)
            time.sleep(4)  # keep the game-over screen
        finally:
            stop_capture(ff)
    decisions = [json.loads(l) for l in open(evolve.RUNS / "decisions" / f"{run_id}.jsonl", encoding="utf8")]
    title = ((f"Laya (421M ModernBERT decision model) plays Balatro - {Path(ck).stem}" if not args.api else
              f"{who} plays Balatro") + f", seed {summary.get('seed')}, {args.speed:g}x speed")
    n = render(raw, decisions, t0, args.speed, out, who, title)
    print(f"{out}: {summary['rounds_won']} rounds, ante {summary['max_ante']}, {summary['outcome']}; {n} subtitles"
          + (f"; API cost ${pol.cost:.4f}" if args.api else ""))


if __name__ == "__main__":
    main()
