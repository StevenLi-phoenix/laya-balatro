"""Same-seed comparison of checkpoints in the simulator: every checkpoint plays the same fresh random
seeds greedily, so deal luck cancels and the per-seed differences are paired.

  python -m laya_player.ladder ckpt/raw_init.pt ckpt_sim/raw0046.pt ckpt_sim/raw0056.pt --seeds 128
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from .simloop import ROOT, play, rand_seeds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ckpts", nargs="+")
    ap.add_argument("--seeds", type=int, default=128)
    ap.add_argument("--out", default=str(ROOT / "runs" / "ladder.json"))
    ap.add_argument("--seeds-from", help="replay the seeds of an earlier ladder json (results compare per seed)")
    ap.add_argument("--tag", default="", help="suffix for result names (e.g. +calc when LAYA_CALC=1)")
    args = ap.parse_args()
    from .policy import Policy
    seeds = json.loads(Path(args.seeds_from).read_text())["seeds"] if args.seeds_from else rand_seeds(args.seeds)
    pol = Policy(args.ckpts[0])
    res = {}
    for ck in args.ckpts:
        pol.load(ck)
        summ = play(pol, seeds, 0.3, True, False)[0]
        name = Path(ck).stem + args.tag
        res[name] = {"rounds": [x["rounds_won"] for x in summ], "won": [x["won"] for x in summ]}
        r = res[name]["rounds"]
        print(f"{name:10s} mean {statistics.mean(r):.2f} median {statistics.median(r)} >=9 {sum(x >= 9 for x in r)}"
              f"/{len(r)} wins {sum(res[name]['won'])}", flush=True)
    Path(args.out).write_text(json.dumps({"seeds": seeds, "results": res}, indent=1))


if __name__ == "__main__":
    main()
