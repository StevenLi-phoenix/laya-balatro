"""Train Laya by self-play in the jackdaw simulator; the real game is only the test set.

Each iteration plays `--games` simulated runs in lockstep (one batched Laya forward per step
across all games), fine-tunes on the decisions with outcome-based advantages plus HF teacher
replay, then scores the new weights greedily on a fixed simulator validation seed set. The
best-by-validation checkpoint is the champion; `realeval.py` checks champions in real Balatro.

  python -m laya_player.simloop --init ckpt/gen14.pt --iters 1000
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import time
from pathlib import Path

import torch

from . import game
from .sim import SimGame

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "runs_sim"
CK = ROOT / "ckpt_sim"


def log(msg: str) -> None:
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    with open(OUT / "simloop.log", "a", encoding="utf8") as f:
        f.write(line + "\n")


@torch.no_grad()
def choose_batch(pol, items: list[tuple[str, str, list[str]]], temperature: float, greedy: bool,
                 chunk: int = 16) -> list[int]:  # 48 x 1024-token prompts overflows an 8 GB card into shared memory
    out = []
    pol.model.eval()
    for i in range(0, len(items), chunk):
        part = items[i:i + chunk]
        exs = [{"phase": ph, "state": st, "options": op} for ph, st, op in part]
        lg = pol.logits(exs)
        for row, (_, _, op) in zip(lg, part):
            z = row[: len(op)] / max(temperature, 1e-3)
            out.append(int(z.argmax()) if greedy else int(torch.multinomial(torch.softmax(z, -1), 1)))
    return out


def play(pol, seeds: list[str], temperature: float, greedy: bool, record: bool,
         bosses: list[list[str]] | None = None) -> tuple[list[dict], list[dict]]:
    games = [SimGame(s, bosses=(bosses[i] if bosses else None)) for i, s in enumerate(seeds)]
    traj: list[list[dict]] = [[] for _ in games]
    round_of = [0] * len(games)
    while True:
        live, items, meta = [], [], []
        for gi, g in enumerate(games):
            s = g.pending()
            if s is None:
                continue
            if g.rounds_won != round_of[gi]:
                for d in traj[gi]:
                    if d["round"] == round_of[gi] and d["phase"] == "hand":
                        d["round_won"] = True
                round_of[gi] = g.rounds_won
            cands = game.candidates(s)
            txt = game.state_text(s)
            opts, acts = [], []
            for a in cands:
                o = game.action_text(s, a)
                if o not in opts and o not in g.__dict__.setdefault("banned", {}).get(txt, ()):
                    opts.append(o)
                    acts.append(a)
            if not acts:
                fb = {"shop": {"t": "leave"}, "pack": {"t": "skip_pack"}, "blind": {"t": "select_blind"}}.get(s["phase"])
                if fb is None:
                    g.steps = 10 ** 6  # no legal play: end the run
                    continue
                acts, opts = [fb], [game.action_text(s, fb)]
            live.append(gi)
            items.append((s["phase"], txt, opts))
            meta.append((s, txt, opts, acts))
        if not live:
            break
        picks = choose_batch(pol, items, temperature, greedy)
        for gi, k, (s, txt, opts, acts) in zip(live, picks, meta):
            g = games[gi]
            if not g.apply(s, acts[k]):
                g.banned.setdefault(txt, set()).add(opts[k])
                continue
            if record and len(opts) > 1:
                traj[gi].append({"phase": s["phase"], "state": txt, "options": opts, "label": k,
                                 "round": round_of[gi], "round_won": False})
    torch.cuda.empty_cache()  # long prompts fragment VRAM; an 8 GB card spills to shared memory otherwise
    summaries = [{"seed": g.seed, "rounds_won": g.rounds_won, "max_ante": g.max_ante, "won": bool(g.gs.get("won")),
                  "illegal": g.illegal, "steps": g.steps} for g in games]
    decisions = []
    if record:
        # Reward-to-go: a decision made in round r is credited with the rounds cleared after it,
        # baselined against other decisions made in the same round this batch. A round-3 shop
        # purchase is then judged by rounds 3+, not by how the run's opening went.
        rows = [(d, x["rounds_won"] - d["round"]) for x, tr in zip(summaries, traj) for d in tr]
        by_round: dict[int, list[float]] = {}
        for d, ret in rows:
            by_round.setdefault(d["round"], []).append(ret)
        stats = {r: (statistics.mean(v), statistics.pstdev(v) or 1.0) for r, v in by_round.items()}
        for d, ret in rows:
            mu, sd = stats[d["round"]]
            adv = max(-1.5, min(1.5, (ret - mu) / sd)) if len(by_round[d["round"]]) > 1 else 0.0
            w = (0.5 * (1.0 if d["round_won"] else -0.5) + 0.5 * adv) if d["phase"] == "hand" else adv
            if abs(w) >= 0.1:
                decisions.append({k: d[k] for k in ("phase", "state", "options", "label")} | {"w": round(w, 3)})
    return summaries, decisions


def score(summ: list[dict]) -> float:
    return statistics.mean(x["rounds_won"] for x in summ)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", default=str(ROOT / "ckpt" / "gen14.pt"))
    ap.add_argument("--iters", type=int, default=1000)
    ap.add_argument("--games", type=int, default=128)
    ap.add_argument("--val-games", type=int, default=128)
    ap.add_argument("--confirm-games", type=int, default=64, help="fresh seeds a challenger must also win on")
    ap.add_argument("--rollback", type=float, default=1.0, help="reset to the champion if val drops this far below best")
    ap.add_argument("--temperature", type=float, default=0.6)
    ap.add_argument("--lr", type=float, default=3e-6)
    # Off by default: hf_train.jsonl is the old names-only format, and teacher imitation lowered
    # simulator scores (imit 1-8: 9.01 -> 7-8.3 while teacher agreement rose).
    ap.add_argument("--replay", type=float, default=0.0, help="HF replay examples per self-play example")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    CK.mkdir(exist_ok=True)
    from .policy import Policy

    hf = [json.loads(l) for l in open(ROOT / "data" / "hf_rich.jsonl", encoding="utf8")] if args.replay else []
    val_seeds = [f"VAL{i:05d}" for i in range(args.val_games)]  # fixed: comparable across iterations
    state_f = OUT / "state.json"
    work = CK / "work.pt"  # training weights carry over between iterations; the champion is tracked apart
    st = json.loads(state_f.read_text()) if state_f.exists() else {"iter": 0, "champion": args.init, "best": None}
    pol = Policy(st["champion"])
    if st.get("val_games") != len(val_seeds):
        st["best"] = None  # validation set changed: re-baseline the champion
    if st["best"] is None:
        t = time.time()
        summ, _ = play(pol, val_seeds, 0.3, True, False)
        st.update(best=score(summ), val_games=len(val_seeds))
        log(f"init {st['champion']}: val {st['best']:.2f} rounds over {len(val_seeds)} seeds ({time.time() - t:.0f}s)")
        state_f.write_text(json.dumps(st))
    elif st.get("work") and Path(st["work"]).exists():
        pol.load(st["work"])
    for it in range(st["iter"] + 1, st["iter"] + 1 + args.iters):
        t0 = time.time()
        seeds = [f"T{it:05d}{j:03d}" for j in range(args.games)]
        summ, dec = play(pol, seeds, args.temperature, False, True)
        t1 = time.time()
        replay = random.sample(hf, min(len(hf), int(len(dec) * args.replay)))
        pol.train(dec + replay, epochs=1.0, lr=args.lr, log=lambda m: None)
        t2 = time.time()
        val, _ = play(pol, val_seeds, 0.3, True, False)
        v = score(val)
        rec = {"iter": it, "train_rounds": score(summ), "val_rounds": v,
               "val_max_ante": statistics.mean(x["max_ante"] for x in val), "val_wins": sum(x["won"] for x in val),
               "decisions": len(dec), "play_s": round(t1 - t0), "train_s": round(t2 - t1), "val_s": round(time.time() - t2)}
        improved = v > st["best"]
        if improved:
            # The best val score is a max over many noisy tries, so a challenger must also beat the
            # champion head-to-head on seeds neither has been selected on.
            conf = [f"C{it:05d}{j:03d}" for j in range(args.confirm_games)]
            mine = score(play(pol, conf, 0.3, True, False)[0])
            pol.save(str(work))
            pol.load(st["champion"])
            theirs = score(play(pol, conf, 0.3, True, False)[0])
            pol.load(str(work))
            rec.update(confirm=mine, confirm_champion=theirs)
            improved = mine > theirs
            log(f"iter {it}: challenger {mine:.2f} vs champion {theirs:.2f} on {len(conf)} fresh seeds")
        if improved:
            path = CK / f"sim{it:04d}.pt"
            pol.save(str(path))
            st.update(best=v, champion=str(path))
        elif v < st["best"] - args.rollback:
            pol.load(st["champion"])  # drifted too far: restart from the champion
            rec["rollback"] = True
        pol.save(str(work))
        st["work"] = str(work)
        rec["champion"] = Path(st["champion"]).name
        st["iter"] = it
        state_f.write_text(json.dumps(st))
        with open(OUT / "iters.jsonl", "a", encoding="utf8") as f:
            f.write(json.dumps(rec) + "\n")
        log(f"iter {it}: train {rec['train_rounds']:.2f} val {v:.2f} (best {st['best']:.2f}"
            f"{' NEW' if improved else ' rollback' if rec.get('rollback') else ''}) "
            f"wins {rec['val_wins']} | {len(dec)} dec, play {rec['play_s']}s train {rec['train_s']}s val {rec['val_s']}s")


if __name__ == "__main__":
    main()
