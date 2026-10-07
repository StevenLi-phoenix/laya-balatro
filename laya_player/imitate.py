"""Large-scale imitation of the HF teacher (V68 heuristic: 74.6% win rate, 22.4 rounds/game).

Trains the current champion on teacher decisions in chunks; after each chunk the weights are
scored on the simulator validation seeds, and any checkpoint beating the champion becomes the
new champion in runs_sim/state.json (so realloop and simloop pick it up).

  python -m laya_player.imitate --data data/hf_big.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

from .simloop import CK, OUT, log, play, score


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/hf_big.jsonl")
    ap.add_argument("--chunk", type=int, default=20000)
    ap.add_argument("--heldout", type=int, default=2000)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--init", help="resume from this checkpoint instead of the champion")
    ap.add_argument("--start-chunk", type=int, default=1, help="resume numbering; earlier chunks are skipped")
    args = ap.parse_args()
    from .policy import Policy

    data = [json.loads(l) for l in open(args.data, encoding="utf8")]
    random.Random(0).shuffle(data)
    held, train = data[: args.heldout], data[args.heldout:]
    state_f = OUT / "state.json"
    st = json.loads(state_f.read_text())
    val_seeds = [f"VAL{i:05d}" for i in range(st["val_games"])]
    pol = Policy(args.init or st["champion"])
    log(f"imit: start from {Path(args.init or st['champion']).name} (best {st['best']:.2f}); teacher agreement "
        f"{pol.evaluate(held)['all']}; {len(train)} train examples")
    order = [i for _ in range(max(1, round(args.epochs))) for i in random.sample(range(len(train)), len(train))]
    for k, lo in enumerate(range(0, len(order), args.chunk), 1):
        if k < args.start_chunk:
            continue
        t0 = time.time()
        pol.train([train[i] for i in order[lo: lo + args.chunk]], epochs=1.0, lr=args.lr, log=lambda m: None)
        t1 = time.time()
        agree = pol.evaluate(held)
        v = score(play(pol, val_seeds, 0.3, True, False)[0])
        path = CK / f"imit{k:02d}.pt"
        pol.save(str(path))
        st = json.loads(state_f.read_text())
        improved = v > st["best"]
        if improved:
            st.update(best=v, champion=str(path), work=str(path))
            state_f.write_text(json.dumps(st))
        log(f"imit {k}: {lo + args.chunk} examples, agreement {agree['all']} (hand {agree.get('hand')} shop "
            f"{agree.get('shop')}) val {v:.2f} (best {st['best']:.2f}{' NEW' if improved else ''}) | "
            f"train {t1 - t0:.0f}s val {time.time() - t1:.0f}s")


if __name__ == "__main__":
    main()
