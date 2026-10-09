"""Keep real Balatro playing with the latest Laya: the simulator champion, hot-reloaded.

Runs cycle through fixed test seeds so real scores stay comparable across checkpoints, and
each seed is also played in the simulator by the same weights (sim/real fidelity check).
Inference uses the local GPU when there is one (training runs on a separate box); pass --device cpu
when simulator training shares this GPU.

  python -m laya_player.realloop
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from . import calc, evolve, record, simloop
from .bridge import Bridge
from .realeval import TEST_SEEDS

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "runs_sim" / "state.json"
OUT = ROOT / "runs" / "real_test.jsonl"
VIDEO = ROOT / "runs" / "video"


def champion(default: str) -> str:
    try:
        return json.loads(STATE.read_text())["champion"]
    except (OSError, ValueError, KeyError):
        return default


def report() -> str:
    rows = [json.loads(l) for l in open(OUT, encoding="utf8")] if OUT.exists() else []
    lines = ["| checkpoint | real runs | real rounds (mean) | best | real ante (mean) | wins | sim rounds same seeds |",
             "|---|---|---|---|---|---|---|"]
    for ck in dict.fromkeys(r["ckpt"] for r in rows):
        rs = [r for r in rows if r["ckpt"] == ck and r["real_outcome"] in ("won", "lost")]
        if rs:
            lines.append(f"| {ck} | {len(rs)} | {statistics.mean(r['real_rounds'] for r in rs):.2f} | "
                         f"{max(r['real_rounds'] for r in rs)} | {statistics.mean(r['real_ante'] for r in rs):.1f} | "
                         f"{sum(r['real_outcome'] == 'won' for r in rs)} | "
                         f"{statistics.mean([r['sim_rounds'] for r in rs if r['sim_rounds'] is not None] or [0]):.2f} |")
    md = ("# Real Balatro test (latest Laya)\n\nRed Deck / White Stake. Random seeds since 2026-10-06 (fixed "
          f"{', '.join(TEST_SEEDS)} before); the simulator replays each run's own seed. "
          "Checkpoints come from simulator training.\n\n" + "\n".join(lines) + "\n")
    (ROOT / "runs" / "real_test.md").write_text(md, encoding="utf8")
    return md


def recorded_run(b, pol, run_id: str, run_args, raw: Path) -> tuple[dict, float]:
    VIDEO.mkdir(parents=True, exist_ok=True)
    with record.GameWindow() as win:
        ff, t0 = record.start_capture(win.region, raw)
        time.sleep(1)
        try:
            summary, _ = evolve.play_run(b, pol, -1, run_id, run_args)
            time.sleep(4)  # keep the game-over screen
        finally:
            record.stop_capture(ff)
    return summary, t0


def keep_recording(summary: dict, run_id: str, raw: Path, t0: float, args) -> None:
    """A won run becomes win_<seed>.mp4 (cut a few seconds after the win screen) plus a cover still;
    the longest unfinished run so far stays as best.raw.mp4 (best.json says how to render it);
    every other capture is deleted."""
    best_f = VIDEO / "best.json"
    best = json.loads(best_f.read_text()) if best_f.exists() else {"rounds": -1}
    seed = summary.get("seed")
    if summary["outcome"] == "won" and summary.get("won_at"):
        decisions = [json.loads(l) for l in open(evolve.RUNS / "decisions" / f"{run_id}.jsonl", encoding="utf8")]
        at = summary["won_at"] - t0
        out = VIDEO / f"win_{seed}.mp4"
        title = (f"Laya (421M ModernBERT decision model) beats Balatro - {summary['ckpt'] and Path(summary['ckpt']).stem}, "
                 f"seed {seed}, Red Deck / White Stake, {args.speed:g}x speed")
        record.render(raw, decisions, t0, args.speed, out, "Laya", title, end=at + args.hold_win,
                      slow_from=at - 2)
        record.still(raw, at + min(2.0, args.hold_win), VIDEO / f"win_{seed}.png")
        evolve.log(f"realloop: recorded the win -> {out.name} (+ cover {out.stem}.png, raw kept)")
    elif summary["rounds_won"] > best["rounds"]:
        old = VIDEO / "best.raw.mp4"
        old.unlink(missing_ok=True)
        raw.rename(old)
        best_f.write_text(json.dumps({"run": run_id, "t0": t0, "rounds": summary["rounds_won"], "seed": seed,
                                      "ckpt": summary["ckpt"]}))
        evolve.log(f"realloop: best recorded run so far: {summary['rounds_won']} rounds ({seed})")
    else:
        raw.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--default", default=str(ROOT / "ckpt" / "raw_init.pt"))
    ap.add_argument("--temperature", type=float, default=0.3)
    ap.add_argument("--device", default="cuda" if __import__("torch").cuda.is_available() else "cpu")
    ap.add_argument("--fixed-seeds", action="store_true", help="cycle TEST_SEEDS instead of random runs")
    ap.add_argument("--seeds-file", help="play these seeds first (one per line, re-read each run), then random ones")
    ap.add_argument("--ckpt", default=None, help="play this checkpoint only (no champion hot-reload)")
    ap.add_argument("--record", action="store_true", help="screen-record every run; keep wins (and the best run so far)")
    ap.add_argument("--stop-on-win", action="store_true")
    ap.add_argument("--speed", type=float, default=4.0, help="speed-up of recorded videos")
    ap.add_argument("--hold-win", type=float, default=6.0, help="seconds the win screen stays up when recording")
    args = ap.parse_args()
    from .policy import Policy

    (evolve.RUNS / "decisions").mkdir(parents=True, exist_ok=True)
    done = [json.loads(l) for l in open(OUT, encoding="utf8")] if OUT.exists() else []
    i = len(done)
    ck = args.ckpt or champion(args.default)
    while not Path(ck).exists():  # training runs remotely: wait for remote_sync to bring the first champion
        time.sleep(60)
        ck = champion(args.default)
    pol = Policy(ck, device=args.device)
    evolve.log(f"realloop: playing with {Path(ck).name} on {args.device}")
    b = Bridge()
    while True:
        latest = args.ckpt or champion(args.default)
        if latest != ck:
            ck = latest
            pol.load(ck)
            evolve.log(f"realloop: switched to new champion {Path(ck).name}")
        seed = TEST_SEEDS[i % len(TEST_SEEDS)] if args.fixed_seeds else None
        if args.seeds_file:  # screened seeds (screen.py), each played once
            played = {json.loads(l)["seed"] for l in open(OUT, encoding="utf8")}
            todo = [x for x in Path(args.seeds_file).read_text().split() if x not in played]
            seed = todo[0] if todo else seed
        i += 1
        run_args = argparse.Namespace(fresh=True, deck="b_red", stake=1, seed=seed, max_decisions=10000, greedy=True,
                                      temperature=args.temperature, hold_win=args.hold_win if args.record else 0)
        run_id = f"real_{Path(ck).stem}_{seed}_{time.strftime('%m%d_%H%M%S')}"
        raw = VIDEO / f"{run_id}.raw.mp4"
        try:
            if args.record:
                summary, t0 = recorded_run(b, pol, run_id, run_args, raw)
            else:
                summary, _ = evolve.play_run(b, pol, -1, run_id, run_args)
        except (ConnectionError, OSError, TimeoutError) as e:
            raw.unlink(missing_ok=True)
            crashed = evolve.game_crashed()
            evolve.log(f"realloop: bridge lost {e!r}; crashed={crashed}")
            try:
                b.close()
            except OSError:
                pass
            try:
                b = evolve.restart_game() if crashed else Bridge(timeout=120)
            except OSError as e2:  # the mod stopped accepting clients (wedged, not crashed): restart the game
                evolve.log(f"realloop: reconnect failed {e2!r}; restarting Balatro")
                b = evolve.restart_game()
            continue
        seed = seed or summary.get("seed")  # random runs: replay the game's own seed in the simulator
        sim = (simloop.play(pol, [seed], args.temperature, True, False, bosses=[summary.get("bosses")])[0] if seed
               else [{"rounds_won": None, "max_ante": None}])
        row = {"ckpt": Path(ck).name + ("+calc" if calc.ON else ""), "seed": seed, "real_rounds": summary["rounds_won"],
               "real_ante": summary["max_ante"], "real_outcome": summary["outcome"],
               "sim_rounds": sim[0]["rounds_won"], "sim_ante": sim[0]["max_ante"],
               "minutes": summary["minutes"], "bosses": summary.get("bosses"),
               "time": time.strftime("%Y-%m-%d %H:%M"), "notes": summary.get("notes"), "twin_lost": summary.get("twin_lost")}
        with open(OUT, "a", encoding="utf8") as f:
            f.write(json.dumps(row) + "\n")
        evolve.log(f"REAL {row['ckpt']} {seed}: real {row['real_rounds']} rounds (ante {row['real_ante']}, "
                   f"{row['real_outcome']}) | sim {row['sim_rounds']} | {row['minutes']} min"
                   + (f" | notes {row['notes']}" if row["notes"] else ""))
        report()
        if args.record:
            keep_recording(summary, run_id, raw, t0, args)
        if args.stop_on_win and summary["outcome"] == "won":
            evolve.log("realloop: run won, stopping (--stop-on-win)")
            break


if __name__ == "__main__":
    main()
