"""Stage 4: imitate the teacher at scale, measured on the fixed ladder seeds after every chunk.

Pure RL from the click kickoff stalled (Stage 2: 5.63 rounds on the 128 ladder seeds; Stage 3 with
computed notes did not improve on it). The last shot: train Stage 2's champion on far more teacher
clicks (makemake/5k-balatro-games, V68 heuristic) than the one-time kickoff did, and after every
chunk measure held-out click agreement and the same 128 ladder seeds raw0056 played. The best chunk
by ladder is checked again on fresh seeds (it was selected on the ladder seeds).

  python -m laya_player.teach --data data/hf_s4.jsonl --init ckpt_sim/raw0056.pt
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import time
from pathlib import Path

from .simloop import ROOT, play, rand_seeds

OUT = ROOT / "runs_teach"
CK = ROOT / "ckpt_teach"


def log(msg: str) -> None:
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    with open(OUT / "teach.log", "a", encoding="utf8") as f:
        f.write(line + "\n")


def paired(mine: list[int], base: list[int]) -> tuple[float, float]:
    d = [a - b for a, b in zip(mine, base)]
    se = (statistics.pstdev(d) or 1.0) / len(d) ** 0.5
    return statistics.mean(d), statistics.mean(d) / se


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "data" / "hf_s4.jsonl"))
    ap.add_argument("--init", default=str(ROOT / "ckpt_sim" / "raw0056.pt"))
    ap.add_argument("--chunk", type=int, default=100_000, help="teacher clicks per chunk")
    ap.add_argument("--chunks", type=int, default=13)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--holdout-games", type=int, default=100)
    ap.add_argument("--ladder", default=str(ROOT / "runs" / "ladder.json"))
    ap.add_argument("--base", default="raw0056", help="ladder entry the chunks are compared with")
    ap.add_argument("--confirm", type=int, default=256, help="fresh seeds for the best chunk at the end")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    CK.mkdir(exist_ok=True)
    from .policy import Policy

    data = [json.loads(l) for l in open(args.data, encoding="utf8")]
    games = sorted({e["seed"] for e in data})
    random.Random(0).shuffle(games)
    held_games = set(games[: args.holdout_games])
    held = [e for e in data if e["seed"] in held_games]
    train = [e for e in data if e["seed"] not in held_games]
    random.Random(1).shuffle(train)
    random.Random(2).shuffle(held)
    held = held[:3000]
    lad = json.loads(Path(args.ladder).read_text())
    seeds, base = lad["seeds"], lad["results"][args.base]["rounds"]

    pol = Policy(args.init)
    agree = pol.evaluate(held)
    log(f"start {Path(args.init).name}: {len(train)} train clicks ({len(games) - len(held_games)} games), "
        f"held-out agreement {agree}; ladder {args.base} {statistics.mean(base):.2f}")
    best = (statistics.mean(base), args.init, 0)
    rec_f = OUT / "teach.jsonl"
    for k in range(1, args.chunks + 1):
        part = train[(k - 1) * args.chunk: k * args.chunk]
        if not part:
            break
        t0 = time.time()
        pol.train(part, epochs=1.0, batch_size=args.batch, lr=args.lr, log=lambda m: None)
        t1 = time.time()
        agree = pol.evaluate(held)
        summ = play(pol, seeds, 0.3, True, False)[0]
        rounds = [x["rounds_won"] for x in summ]
        diff, t = paired(rounds, base)
        path = CK / f"teach{k:03d}.pt"
        pol.save(str(path))
        rec = {"chunk": k, "clicks": k * args.chunk, "agree": agree, "ladder": statistics.mean(rounds),
               "ladder_median": statistics.median(rounds), "ladder_games": rounds, "wins": sum(x["won"] for x in summ),
               "vs_base": round(diff, 3), "t": round(t, 2), "train_s": round(t1 - t0), "eval_s": round(time.time() - t1)}
        with open(rec_f, "a", encoding="utf8") as f:
            f.write(json.dumps(rec) + "\n")
        if rec["ladder"] > best[0]:
            best = (rec["ladder"], str(path), k)
        log(f"chunk {k}: {k * args.chunk} clicks | agreement {agree['all']} (hand {agree.get('hand')}, shop {agree.get('shop')}) "
            f"| ladder {rec['ladder']:.2f} (median {rec['ladder_median']}) vs {args.base} {diff:+.2f}, t {t:+.1f} "
            f"| wins {rec['wins']} | train {rec['train_s']}s eval {rec['eval_s']}s")
    if best[2]:
        fresh = rand_seeds(args.confirm)
        pol.load(best[1])
        mine = [x["rounds_won"] for x in play(pol, fresh, 0.3, True, False)[0]]
        pol.load(args.init)
        theirs = [x["rounds_won"] for x in play(pol, fresh, 0.3, True, False)[0]]
        diff, t = paired(mine, theirs)
        log(f"confirm best chunk {best[2]} on {args.confirm} fresh seeds: {statistics.mean(mine):.2f} vs "
            f"{Path(args.init).stem} {statistics.mean(theirs):.2f} ({diff:+.2f}, t {t:+.1f})")
        (OUT / "best.json").write_text(json.dumps({"chunk": best[2], "ckpt": best[1], "ladder": best[0],
                                                    "fresh": statistics.mean(mine), "fresh_base": statistics.mean(theirs),
                                                    "fresh_t": round(t, 2), "fresh_seeds": fresh}))
    else:
        log("no chunk beat the start on the ladder seeds")


if __name__ == "__main__":
    main()
