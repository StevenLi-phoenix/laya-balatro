"""Screen fresh random seeds in the simulator for runs a checkpoint wins (greedy, real boss order),
so real Balatro can be played on the seeds it is most likely to win.

  python -m laya_player.screen ckpt_sim/raw0056.pt --seeds 8192 --batch 256
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .simloop import ROOT, play, rand_seeds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ckpt")
    ap.add_argument("--seeds", type=int, default=8192)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    from .policy import Policy
    pol = Policy(args.ckpt)
    out = Path(args.out or ROOT / "runs" / f"screen_{Path(args.ckpt).stem}.jsonl")
    done, wins, t0 = 0, 0, time.time()
    while done < args.seeds:
        seeds = rand_seeds(args.batch)
        summ = play(pol, seeds, 0.3, True, False)[0]
        with open(out, "a", encoding="utf8") as f:
            for s, x in zip(seeds, summ):
                f.write(json.dumps({"seed": s, "rounds": x["rounds_won"], "ante": x["max_ante"], "won": x["won"]}) + "\n")
                if x["won"]:
                    wins += 1
                    print(f"WIN {s}: {x['rounds_won']} rounds", flush=True)
        done += len(seeds)
        print(f"{done} seeds, {wins} wins, {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
