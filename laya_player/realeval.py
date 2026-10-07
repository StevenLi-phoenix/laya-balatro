"""Real-Balatro test set: play a checkpoint on fixed seeds in the real game and in the simulator.

The same seed string drives both (jackdaw ports Balatro's PRNG), so each row is both a test
score and a fidelity check: a large per-seed sim/real gap points at a simulator or adapter bug.

  python -m laya_player.realeval --ckpt ckpt_sim/sim0042.pt --seeds LAYA0001,LAYA0002,LAYA0003,LAYA0004
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from . import evolve, simloop
from .bridge import Bridge

ROOT = Path(__file__).resolve().parent.parent
TEST_SEEDS = ["LAYA0001", "LAYA0002", "LAYA0003", "LAYA0004", "LAYA0005", "LAYA0006"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--seeds", default=",".join(TEST_SEEDS))
    ap.add_argument("--temperature", type=float, default=0.3)
    ap.add_argument("--deck", default="b_red")
    ap.add_argument("--stake", type=int, default=1)
    ap.add_argument("--device", default="cpu", help="cpu leaves the GPU to simulator training")
    args = ap.parse_args()
    from .policy import Policy

    (evolve.RUNS / "decisions").mkdir(parents=True, exist_ok=True)
    seeds = args.seeds.split(",")
    pol = Policy(args.ckpt, device=args.device)
    sim, _ = simloop.play(pol, seeds, args.temperature, True, False)
    b = Bridge()
    out = ROOT / "runs" / "real_test.jsonl"
    rows = []
    for seed, sm in zip(seeds, sim):
        run_args = argparse.Namespace(fresh=True, deck=args.deck, stake=args.stake, seed=seed,
                                      max_decisions=2500, temperature=args.temperature)
        run_id = f"test_{Path(args.ckpt).stem}_{seed}_{time.strftime('%H%M%S')}"
        summary, _ = evolve.play_run(b, pol, -1, run_id, run_args)
        row = {"ckpt": Path(args.ckpt).name, "seed": seed, "real_rounds": summary["rounds_won"],
               "real_ante": summary["max_ante"], "real_outcome": summary["outcome"],
               "sim_rounds": sm["rounds_won"], "sim_ante": sm["max_ante"], "minutes": summary["minutes"],
               "time": time.strftime("%Y-%m-%d %H:%M")}
        rows.append(row)
        with open(out, "a", encoding="utf8") as f:
            f.write(json.dumps(row) + "\n")
        evolve.log(f"TEST {row}")
    real = statistics.mean(r["real_rounds"] for r in rows)
    simm = statistics.mean(r["sim_rounds"] for r in rows)
    evolve.log(f"TEST {Path(args.ckpt).name}: real {real:.2f} rounds vs sim {simm:.2f} on {len(rows)} seeds")


if __name__ == "__main__":
    main()
