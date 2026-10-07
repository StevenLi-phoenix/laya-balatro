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

from . import evolve, simloop
from .bridge import Bridge
from .realeval import TEST_SEEDS

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "runs_sim" / "state.json"
OUT = ROOT / "runs" / "real_test.jsonl"


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--default", default=str(ROOT / "ckpt" / "raw_init.pt"))
    ap.add_argument("--temperature", type=float, default=0.3)
    ap.add_argument("--device", default="cuda" if __import__("torch").cuda.is_available() else "cpu")
    ap.add_argument("--fixed-seeds", action="store_true", help="cycle TEST_SEEDS instead of random runs")
    args = ap.parse_args()
    from .policy import Policy

    (evolve.RUNS / "decisions").mkdir(parents=True, exist_ok=True)
    done = [json.loads(l) for l in open(OUT, encoding="utf8")] if OUT.exists() else []
    i = len(done)
    ck = champion(args.default)
    while not Path(ck).exists():  # training runs remotely: wait for remote_sync to bring the first champion
        time.sleep(60)
        ck = champion(args.default)
    pol = Policy(ck, device=args.device)
    evolve.log(f"realloop: playing with {Path(ck).name} on {args.device}")
    b = Bridge()
    while True:
        latest = champion(args.default)
        if latest != ck:
            ck = latest
            pol.load(ck)
            evolve.log(f"realloop: switched to new champion {Path(ck).name}")
        seed = TEST_SEEDS[i % len(TEST_SEEDS)] if args.fixed_seeds else None
        i += 1
        run_args = argparse.Namespace(fresh=True, deck="b_red", stake=1, seed=seed, max_decisions=10000, greedy=True,
                                      temperature=args.temperature)
        run_id = f"real_{Path(ck).stem}_{seed}_{time.strftime('%m%d_%H%M%S')}"
        try:
            summary, _ = evolve.play_run(b, pol, -1, run_id, run_args)
        except (ConnectionError, OSError, TimeoutError) as e:
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
        row = {"ckpt": Path(ck).name, "seed": seed, "real_rounds": summary["rounds_won"],
               "real_ante": summary["max_ante"], "real_outcome": summary["outcome"],
               "sim_rounds": sim[0]["rounds_won"], "sim_ante": sim[0]["max_ante"],
               "minutes": summary["minutes"], "bosses": summary.get("bosses"),
               "time": time.strftime("%Y-%m-%d %H:%M")}
        with open(OUT, "a", encoding="utf8") as f:
            f.write(json.dumps(row) + "\n")
        evolve.log(f"REAL {row['ckpt']} {seed}: real {row['real_rounds']} rounds (ante {row['real_ante']}, "
                   f"{row['real_outcome']}) | sim {row['sim_rounds']} | {row['minutes']} min")
        report()


if __name__ == "__main__":
    main()
