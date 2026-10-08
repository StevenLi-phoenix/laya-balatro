"""Side-by-side(ish) video: several players' real runs on one seed in a 2x2 grid, plus a scoreboard.

Each input is a finished record.py video (title + captions burned in, same speed). Shorter runs hold
their last frame until the longest ends.

  python -m laya_player.compare_video --seed BXEMK4GS \
      --clip "OpenAI GPT-6 Luna Decisions=runs/video/cmp_openai.mp4=13" \
      --clip "Laya raw0056=runs/video/cmp_laya.mp4=5" --clip "TypeSafe Jev 1.13=runs/video/cmp_jev.mp4=1" \
      --out runs/video/compare_BXEMK4GS.mp4
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

FONT = r"C\:/Windows/Fonts/arial.ttf"


def duration(path: str) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace(":", r"\:").replace("'", "").replace(",", r"\,")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", required=True)
    ap.add_argument("--clip", action="append", required=True, help="NAME=PATH=ROUNDS (up to 3)")
    ap.add_argument("--note", default="same seed, same raw-click interface, no computed notes, 4x speed")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    clips = [c.split("=") for c in args.clip][:3]
    durs = [duration(p) for _, p, _ in clips]
    total = max(durs) + 2
    w, h = 960, 540
    inputs, parts = [], []
    for i, ((name, path, rounds), d) in enumerate(zip(clips, durs)):
        inputs += ["-i", path]
        parts.append(f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,"
                     f"tpad=stop_mode=clone:stop_duration={total - d:.2f},trim=duration={total:.2f},setpts=PTS-STARTPTS,"
                     f"drawtext=fontfile='{FONT}':text='{esc(name)}':x=w-tw-12:y=h-th-12:fontsize=22:fontcolor=white:"
                     f"box=1:boxcolor=black@0.6:boxborderw=6[v{i}]")
    lines = [f"Seed {args.seed}", args.note, ""] + [f"{n}: {r} rounds" for n, _, r in clips]
    board = f"color=c=0x1a1a19:s={w}x{h}:d={total:.2f}"
    for k, line in enumerate(lines):
        size = 34 if k == 0 else 20 if k == 1 else 28
        board += (f",drawtext=fontfile='{FONT}':text='{esc(line)}':x=40:y={60 + 52 * k}:fontsize={size}:"
                  f"fontcolor={'white' if k != 1 else '0xc3c2b7'}")
    parts.append(f"{board}[v3]")
    grid = "".join(f"[v{i}]" for i in range(4)) + "xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0[out]"
    fc = ";".join(parts + [grid])
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", fc, "-map", "[out]",
                    "-r", "30", "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p", args.out], check=True)
    print(f"{args.out}: {total:.0f}s, clips {[round(d) for d in durs]}s")


if __name__ == "__main__":
    main()
