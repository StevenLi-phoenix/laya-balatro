"""Train Laya by self-play in the jackdaw simulator; the real game is only the test set.

Each iteration plays `--games` simulated runs on random seeds in lockstep (one batched Laya
forward per step across all games) and fine-tunes on the decisions with outcome-based advantages
(pure RL: the HF teacher only seeds the initial weights). The new weights then play the champion
head-to-head on fresh random seeds; a significant win takes the title. `realloop.py` validates
the champion in real Balatro.

  python -m laya_player.simloop --init ckpt/raw_init.pt
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import string
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


def _infer_chunk() -> int:
    """Prompts per forward pass. 48 x 1024 tokens overflows an 8 GB card into shared memory (a
    ~5x slowdown), so small cards get 16; a 16 GB card takes 64."""
    if not torch.cuda.is_available():
        return 16
    mem = torch.cuda.get_device_properties(0).total_memory
    return 128 if mem >= 15 * 2 ** 30 else 64 if mem >= 12 * 2 ** 30 else 16


INFER_CHUNK = _infer_chunk()


@torch.no_grad()
def choose_batch(pol, items: list[tuple[str, str, list[str]]], temperature: float, greedy: bool,
                 chunk: int = INFER_CHUNK, logps: list[float] | None = None) -> list[int]:
    """Pick an option per item. `logps`, if given, receives log p(pick) under the raw policy
    (temperature 1): the behaviour probability PPO's ratio is measured against."""
    out = []
    pol.model.eval()
    for i in range(0, len(items), chunk):
        part = items[i:i + chunk]
        exs = [{"phase": ph, "state": st, "options": op} for ph, st, op in part]
        lg = pol.logits(exs)
        for row, (_, _, op) in zip(lg, part):
            z = row[: len(op)] / max(temperature, 1e-3)
            k = int(z.argmax()) if greedy else int(torch.multinomial(torch.softmax(z, -1), 1))
            out.append(k)
            if logps is not None:
                logps.append(float(torch.log_softmax(row[: len(op)], -1)[k]))
    return out


def play(pol, seeds: list[str], temperature: float, greedy: bool, record: bool,
         bosses: list[list[str]] | None = None, credit: str = "round") -> tuple[list[dict], list[dict]]:
    """credit: "round" = reward-to-go baselined by round index across all games; "seed" = baselined by
    the other games on the same seed that reached the same round (needs repeated seeds; deal luck
    cancels); "best" = keep only each seed's best game, as positive examples."""
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
        lps: list[float] = []
        picks = choose_batch(pol, items, temperature, greedy, logps=lps)
        for gi, k, lp, (s, txt, opts, acts) in zip(live, picks, lps, meta):
            g = games[gi]
            if not g.apply(s, acts[k]):
                g.banned.setdefault(txt, set()).add(opts[k])
                continue
            if record and len(opts) > 1:
                traj[gi].append({"phase": s["phase"], "state": txt, "options": opts, "label": k,
                                 "round": round_of[gi], "round_won": False, "old_lp": lp})
    torch.cuda.empty_cache()  # long prompts fragment VRAM; an 8 GB card spills to shared memory otherwise
    summaries = [{"seed": g.seed, "rounds_won": g.rounds_won, "max_ante": g.max_ante, "won": bool(g.gs.get("won")),
                  "illegal": g.illegal, "steps": g.steps} for g in games]
    decisions = []
    if record and credit in ("seed", "best"):
        return summaries, _seed_credit(summaries, traj, credit)
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
                decisions.append({k: d[k] for k in ("phase", "state", "options", "label", "old_lp")} | {"w": round(w, 3)})
    return summaries, decisions


def _seed_credit(summaries: list[dict], traj: list[list[dict]], credit: str) -> list[dict]:
    """Same-seed credit: games on one seed share deck order, shops and bosses, so comparing them
    isolates what Laya's choices did. A decision in round r is judged against the mean final round
    of the siblings that also reached round r."""
    by_seed: dict[str, list[int]] = {}
    for gi, x in enumerate(summaries):
        by_seed.setdefault(x["seed"], []).append(gi)
    keep = lambda d: {k: d[k] for k in ("phase", "state", "options", "label", "old_lp")}
    out = []
    if credit == "best":
        for gs in by_seed.values():
            rs = [summaries[g]["rounds_won"] for g in gs]
            if len(set(rs)) > 1:  # all equal: nothing to learn from this seed
                out += [keep(d) | {"w": 1.0} for d in traj[gs[rs.index(max(rs))]]]
        return out
    rows = []
    for gs in by_seed.values():
        for g in gs:
            mine = summaries[g]["rounds_won"]
            for d in traj[g]:
                sib = [summaries[h]["rounds_won"] for h in gs if summaries[h]["rounds_won"] >= d["round"]]
                if len(sib) > 1:
                    rows.append((d, mine - statistics.mean(sib)))
    sd = statistics.pstdev([a for _, a in rows]) or 1.0 if rows else 1.0
    for d, a in rows:
        w = max(-2.0, min(2.0, a / sd))
        if abs(w) >= 0.1:
            out.append(keep(d) | {"w": round(w, 3)})
    return out


def score(summ: list[dict]) -> float:
    return statistics.mean(x["rounds_won"] for x in summ)


def rand_seeds(n: int) -> list[str]:
    """Fresh Balatro-style seeds: nothing is ever selected or tuned on a fixed seed set."""
    abc = string.ascii_uppercase + string.digits
    return ["".join(random.choices(abc, k=8)) for _ in range(n)]


def head_to_head(pol, champion: str, work: Path, n: int) -> tuple[list[int], list[int], float]:
    """Working weights vs the champion on the same n fresh seeds -> (mine, theirs per seed, paired t)."""
    seeds = rand_seeds(n)
    mine = play(pol, seeds, 0.3, True, False)[0]
    pol.save(str(work))
    pol.load(champion)
    theirs = play(pol, seeds, 0.3, True, False)[0]
    pol.load(str(work))
    d = [a["rounds_won"] - b["rounds_won"] for a, b in zip(mine, theirs)]
    se = (statistics.pstdev(d) or 1.0) / len(d) ** 0.5
    return [x["rounds_won"] for x in mine], [x["rounds_won"] for x in theirs], statistics.mean(d) / se


def main():
    """Pure RL: train on random seeds, test head-to-head on fresh random seeds, Balatro validates."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", default=str(ROOT / "ckpt" / "raw_init.pt"))
    ap.add_argument("--iters", type=int, default=1000)
    ap.add_argument("--games", type=int, default=64, help="self-play games per iteration (random seeds)")
    ap.add_argument("--test-games", type=int, default=64, help="fresh seeds per head-to-head test")
    ap.add_argument("--promote-t", type=float, default=1.0, help="paired t-statistic needed to take the title")
    ap.add_argument("--rollback", type=float, default=1.0, help="reset to the champion if this many rounds behind")
    ap.add_argument("--temperature", type=float, default=0.6)
    ap.add_argument("--lr", type=float, default=3e-6)
    ap.add_argument("--batch", type=int, default=8, help="training batch (32 fits a 16 GB card)")
    ap.add_argument("--epochs", type=float, default=2.0, help="passes over each iteration's games (PPO-clipped)")
    ap.add_argument("--group", type=int, default=1, help="games per seed (>1: same-seed credit, deal luck cancels)")
    ap.add_argument("--credit", choices=("seed", "best"), default="seed",
                    help="with --group: seed = advantage vs same-seed siblings (all games); best = only each seed's best game")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    CK.mkdir(exist_ok=True)
    from .policy import Policy

    state_f = OUT / "state.json"
    work = CK / "work.pt"  # training weights carry over between iterations; the champion is tracked apart
    st = json.loads(state_f.read_text()) if state_f.exists() else {"iter": 0, "champion": args.init}
    pol = Policy(st["champion"])
    if st.get("work") and Path(st["work"]).exists():
        pol.load(st["work"])
    log(f"start: champion {Path(st['champion']).name}, actions {'raw' if game.RAW else 'combo'}")
    for it in range(st["iter"] + 1, st["iter"] + 1 + args.iters):
        t0 = time.time()
        seeds = [s for s in rand_seeds(args.games // args.group) for _ in range(args.group)]
        summ, dec = play(pol, seeds, args.temperature, False, True, credit=args.credit if args.group > 1 else "round")
        t1 = time.time()
        pol.train(dec, epochs=args.epochs, batch_size=args.batch, lr=args.lr, log=lambda m: None)
        t2 = time.time()
        mine_g, theirs_g, t = head_to_head(pol, st["champion"], work, args.test_games)
        mine, theirs = statistics.mean(mine_g), statistics.mean(theirs_g)
        rec = {"iter": it, "train_rounds": score(summ), "test_rounds": mine, "champion_rounds": theirs, "t": round(t, 2),
               "train_games": [x["rounds_won"] for x in summ], "test_games": mine_g, "champion_games": theirs_g,
               "decisions": len(dec), "play_s": round(t1 - t0), "train_s": round(t2 - t1),
               "test_s": round(time.time() - t2)}
        improved = mine > theirs and t >= args.promote_t
        if improved:
            path = CK / f"raw{it:04d}.pt"
            pol.save(str(path))
            st["champion"] = str(path)
        elif mine < theirs - args.rollback:
            pol.load(st["champion"])  # drifted too far: restart from the champion
            rec["rollback"] = True
        pol.save(str(work))
        st.update(work=str(work), iter=it)
        rec["champion"] = Path(st["champion"]).name
        state_f.write_text(json.dumps(st))
        with open(OUT / "iters.jsonl", "a", encoding="utf8") as f:
            f.write(json.dumps(rec) + "\n")
        log(f"iter {it}: train {rec['train_rounds']:.2f} | test {mine:.2f} vs champion {theirs:.2f} (t {t:+.1f})"
            f"{' NEW' if improved else ' rollback' if rec.get('rollback') else ''} | {len(dec)} dec, "
            f"play {rec['play_s']}s train {rec['train_s']}s test {rec['test_s']}s")


if __name__ == "__main__":
    main()
