"""Imitation pretraining of Laya on the converted HF teacher data -> ckpt/gen1.pt.

  python -m laya_player.pretrain --data data/hf_train.jsonl --epochs 1
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_split(path: str, holdout_games: int = 150, seed: int = 0):
    exs = [json.loads(l) for l in open(path, encoding="utf8")]
    seeds = sorted({e["seed"] for e in exs})
    random.Random(seed).shuffle(seeds)
    held = set(seeds[:holdout_games])
    return [e for e in exs if e["seed"] not in held], [e for e in exs if e["seed"] in held]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "data" / "hf_train.jsonl"))
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--out", default=str(ROOT / "ckpt" / "gen1.pt"))
    ap.add_argument("--init", default=None, help="start from this checkpoint instead of stock Laya")
    ap.add_argument("--eval-out", default=str(ROOT / "runs" / "pretrain_eval.json"))
    args = ap.parse_args()
    lock = ROOT / "ckpt" / "pretrain.lock"
    lock.parent.mkdir(exist_ok=True)
    lock.write_text(str(time.time()))
    log_f = open(ROOT / "runs" / "pretrain.log", "a", encoding="utf8")

    def log(m):
        print(m, flush=True)
        log_f.write(m + "\n")
        log_f.flush()

    try:
        from .policy import Policy
        train, held = load_split(args.data)
        log(f"train {len(train)} heldout {len(held)}")
        pol = Policy(args.init)
        before = pol.evaluate(held[:1500])
        log(f"{Path(args.init).name if args.init else 'gen0'} heldout teacher-agreement: {before}")
        pol.train(train, epochs=args.epochs, log=log)
        pol.save(args.out)
        after = pol.evaluate(held[:1500])
        log(f"{Path(args.out).name} heldout teacher-agreement: {after}")
        Path(args.eval_out).write_text(json.dumps({"before": before, "after": after}, indent=1))
    finally:
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
