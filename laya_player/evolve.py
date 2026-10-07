"""Play Balatro with Laya in the live game and evolve it between runs.

Generation 0 is stock Laya (zero-shot). While `pretrain.py` holds ckpt/pretrain.lock, gen0
plays on CPU so the GPU is free for imitation pretraining; once ckpt/gen1.pt lands, the loop
switches to it on the GPU. After every `--runs-per-gen` runs it fine-tunes on its own
decisions (round/run outcome as advantage) mixed with HF teacher replay and saves gen N+1.

  python -m laya_player.evolve --runs-per-gen 2
  python -m laya_player.evolve --report          # per-generation comparison table only
"""
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import statistics
import time
import traceback
from pathlib import Path

from . import game
from .bridge import Bridge, BridgeError
from .live import canonical, execute, live_candidates, wait_stable

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
CKPT = ROOT / "ckpt"


def torch_empty() -> None:
    import gc

    import torch
    gc.collect()
    torch.cuda.empty_cache()


def log(msg: str) -> None:
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    with open(RUNS / "evolve.log", "a", encoding="utf8") as f:
        f.write(line + "\n")


def latest_gen() -> tuple[int, str | None]:
    gens = sorted((int(p.stem[3:]), str(p)) for p in CKPT.glob("gen*.pt"))
    return gens[-1] if gens else (0, None)


def load_runs() -> list[dict]:
    f = RUNS / "runs.jsonl"
    return [json.loads(l) for l in open(f, encoding="utf8")] if f.exists() else []


# ---------------------------------------------------------------------------- one run

LOVELY_LOG = Path(os.environ.get("APPDATA", "")) / "Balatro" / "Mods" / "lovely" / "log"


def game_crashed() -> bool:
    logs = sorted(LOVELY_LOG.glob("lovely-*.log"), key=lambda p: p.stat().st_mtime)
    return bool(logs) and "Oops! The game crashed" in logs[-1].read_text(encoding="utf8", errors="ignore")


def restart_game() -> Bridge:
    """Kill the crashed Balatro (its crash screen holds nothing) and relaunch it via Steam."""
    subprocess.run(["taskkill", "/IM", "Balatro.exe", "/F"], capture_output=True)
    time.sleep(5)
    os.startfile("steam://rungameid/2379780")
    time.sleep(20)
    return Bridge(timeout=240)


def start_run(b: Bridge, deck: str, stake: int, seed: str | None = None) -> None:
    if (b.state()["payload"] or {}).get("phase") != "MENU":
        b.call("go_to_menu", timeout=30)
        wait_stable(b, timeout=30)
    for attempt in range(3):
        try:
            b.call("new_game", {"deck": deck, "stake": stake} | ({"seed": seed} if seed else {}))
            return
        except BridgeError as e:
            log(f"new_game failed ({e}); retrying")
            time.sleep(3)
    raise RuntimeError("cannot start a new run (popup blocking?)")


def play_run(b: Bridge, pol, gen: int, run_id: str, args) -> dict:
    p = wait_stable(b)
    if p.get("phase") in ("MENU", "GAME_OVER") or args.fresh:
        start_run(b, args.deck, args.stake, getattr(args, "seed", None))
        args.fresh = False
    decisions, round_idx, rounds_won, max_ante, invalid = [], 0, 0, 1, 0
    last_txt, repeat, banned = None, 0, set()
    best_hand, outcome, t0 = 0, "abort", time.time()
    counted_round = -1
    run_seed = None
    bosses: dict[int, str] = {}
    won = False
    busy = streak = 0
    tries: dict = {}
    dec_f = open(RUNS / "decisions" / f"{run_id}.jsonl", "w", encoding="utf8")
    for _ in range(args.max_decisions):
        p = wait_stable(b)
        ph = p.get("phase")
        max_ante = max(max_ante, p.get("ante") or 1)
        run_seed = p.get("seed") or run_seed
        if ph == "BLIND_SELECT":
            for bl in (p.get("blind_select") or {}).get("blinds") or []:
                if bl.get("slot") == "Boss" and bl.get("blind_id"):
                    bosses[p.get("ante") or 1] = bl["blind_id"]
        if p.get("won") and not won:
            won = True
            log(f"*** RUN WON at ante {max_ante} ({rounds_won} rounds) -- continuing into endless")
        if p.get("won") and p.get("overlay_open"):
            try:
                b.call("endless_mode")  # dismiss the win overlay: keep playing past ante 8
            except BridgeError as e:
                log(f"endless_mode: {e}")
                time.sleep(1)
            continue
        if ph == "GAME_OVER":
            outcome = "won" if won else "lost"
            break
        if ph == "ROUND_EVAL":
            if counted_round != round_idx:
                counted_round = round_idx
                rounds_won += 1
                for d in decisions:
                    if d["round"] == round_idx and d["phase"] == "hand":
                        d["round_won"] = True
            try:
                b.call("cash_out")
            except BridgeError as e:
                log(f"cash_out: {e}")
                time.sleep(1)
            continue
        if counted_round == round_idx and ph != "ROUND_EVAL":
            round_idx += 1
        if ph == "MENU":
            outcome = "menu"
            break
        s = canonical(p)
        if s is None:
            time.sleep(0.3)
            continue
        cands = live_candidates(s)
        txt = game.state_text(s)
        repeat = repeat + 1 if txt == last_txt else 0
        last_txt = txt
        opts, acts = [], []
        for a in cands:
            o = game.action_text(s, a)
            if o not in opts and (txt, o) not in banned:
                opts.append(o)
                acts.append(a)
        if not acts:
            fallback = {"hand": None, "shop": {"t": "leave"}, "pack": {"t": "skip_pack"},
                        "blind": {"t": "select_blind"}}[s["phase"]]
            if fallback is None:
                log(f"no legal candidates in {txt[:120]}")
                break
            acts, opts = [fallback], [game.action_text(s, fallback)]
        idx, probs = pol.choose(s["phase"], txt, opts, temperature=args.temperature,
                                greedy=getattr(args, "greedy", False))
        a = acts[idx]
        try:
            res = execute(b, s, a)
            if a["t"] == "play" and isinstance(res, dict):
                best_hand = max(best_hand, int(res.get("points_gained") or 0))
        except BridgeError as e:
            if e.code == "CANNOT_USE_NOW":
                # usually an animation still running (retry), but also a card the game refuses
                # outright (e.g. a tarot with no room for what it creates): give up on it after 3 tries
                busy += 1
                tries[(txt, opts[idx])] = tries.get((txt, opts[idx]), 0) + 1
                if tries[(txt, opts[idx])] >= 3:
                    banned.add((txt, opts[idx]))
                    log(f"  refused {opts[idx]!r}: {e.message[:80]}")
                if busy > 40:
                    outcome = "stuck"
                    break
                time.sleep(1.0)
                continue
            invalid += 1
            streak += 1
            if streak > 40:
                outcome = "stuck"
                break
            banned.add((txt, opts[idx]))
            log(f"  invalid {opts[idx]!r}: {e.code} {e.message[:100]}")
            continue
        busy = streak = 0
        if repeat >= 4:
            banned.add((txt, opts[idx]))
        d = {"gen": gen, "run": run_id, "step": len(decisions), "round": round_idx, "phase": s["phase"],
             "ante": s.get("ante"), "state": txt, "options": opts, "label": idx, "probs": probs,
             "round_won": False}
        decisions.append(d)
        dec_f.write(json.dumps(d, ensure_ascii=False) + "\n")
        dec_f.flush()
        if s["phase"] == "hand":
            log(f"[g{gen} a{s['ante']} r{round_idx}] {s['blind'].get('scored')}/{s['blind'].get('target')}"
                f" -> {opts[idx]} (p={probs[idx]:.2f})")
        else:
            log(f"[g{gen} a{s['ante']} {s['phase']}] -> {opts[idx]} (p={probs[idx]:.2f})")
    dec_f.close()
    return {"gen": gen, "run": run_id, "ckpt": pol.ckpt, "outcome": outcome, "won": won, "seed": run_seed, "bosses": [bosses[a] for a in sorted(bosses)], "rounds_won": rounds_won,
            "max_ante": max_ante, "decisions": len(decisions), "invalid": invalid, "best_hand": best_hand,
            "minutes": round((time.time() - t0) / 60, 1), "deck": args.deck, "stake": args.stake,
            "temperature": args.temperature, "time": time.strftime("%Y-%m-%d %H:%M")}, decisions


# ---------------------------------------------------------------------------- learning

def selfplay_examples(runs: list[dict], baseline: float) -> list[dict]:
    exs = []
    for r in runs:
        path = RUNS / "decisions" / f"{r['run']}.jsonl"
        if not path.exists():
            continue
        run_adv = max(-1.0, min(1.0, (r["rounds_won"] - baseline) / 4.0))
        for l in open(path, encoding="utf8"):
            d = json.loads(l)
            if len(d["options"]) < 2:
                continue
            if d["phase"] == "hand":
                w = 1.0 if d["round_won"] else -0.5
            else:
                w = run_adv
            if abs(w) < 0.1:
                continue
            exs.append({"phase": d["phase"], "state": d["state"], "options": d["options"], "label": d["label"],
                        "w": w})
    return exs


def champion(runs: list[dict], min_runs: int = 2) -> int | None:
    """Generation with the best mean rounds won (ties -> newer); gen0 never trains further."""
    best = None
    for g in sorted({r["gen"] for r in runs if r["gen"] >= 1}):
        rs = [r["rounds_won"] for r in runs if r["gen"] == g and r["outcome"] in ("won", "lost")]
        if len(rs) >= min_runs and (best is None or statistics.mean(rs) >= best[1]):
            best = (g, statistics.mean(rs))
    return best[0] if best else None


def evolve_step(pol, gen: int, args) -> int:
    runs = load_runs()
    done = [r for r in runs if r["outcome"] in ("won", "lost") and r["gen"] >= 1]
    # Train from the best generation so far: a regressed generation's games still feed the
    # data (as negatives), but its weights do not become the next starting point.
    champ = champion(runs)
    n_champ = sum(1 for r in runs if r["gen"] == champ and r["outcome"] in ("won", "lost"))
    if champ is not None and champ != gen and n_champ < args.champion_runs:
        # Two lucky runs should not crown a champion forever: replay it before trusting it.
        pol.load(str(CKPT / f"gen{champ}.pt"))
        log(f"gen{gen} underperformed; re-evaluating champion gen{champ} ({n_champ} runs so far)")
        return champ
    if champ is not None and champ != gen:
        pol.load(str(CKPT / f"gen{champ}.pt"))
        log(f"gen{gen} underperformed; training next generation from champion gen{champ}")
    recent = done[-6:]
    hist = [r["rounds_won"] for r in done]
    baseline = statistics.mean(hist[-12:]) if hist else 3.0
    sp = selfplay_examples(recent, baseline)
    hf_path = ROOT / "data" / "hf_train.jsonl"
    replay = []
    if hf_path.exists():
        hf = [json.loads(l) for l in open(hf_path, encoding="utf8")]
        replay = random.sample(hf, min(len(hf), max(800, len(sp))))
    exs = sp + replay
    new = latest_gen()[0] + 1  # after a champion replay `gen` is old; never reuse a number
    base = champ if champ is not None else gen
    log(f"evolve gen{base}->gen{new}: {len(sp)} self-play (baseline {baseline:.1f} rounds) + {len(replay)} replay")
    pol.train(exs, epochs=1.0, lr=args.lr, log=log, max_steps=args.max_train_steps)
    out = CKPT / f"gen{new}.pt"
    pol.save(str(out))
    log(f"saved {out}")
    return new


# ---------------------------------------------------------------------------- report

def report() -> str:
    # aborted/stuck runs (interface gaps) still show how far the policy got; crashes do not
    runs = [r for r in load_runs() if r["outcome"] != "crash"]
    rows = ["| gen | runs (incomplete) | rounds won (mean) | best | max ante (mean) | wins | invalid/run | min/run |",
            "|---|---|---|---|---|---|---|---|"]
    for g in sorted({r["gen"] for r in runs}):
        rs = [r for r in runs if r["gen"] == g]
        inc = sum(r["outcome"] not in ("won", "lost") for r in rs)
        rows.append(f"| {g} | {len(rs)} ({inc}) | {statistics.mean(r['rounds_won'] for r in rs):.1f} | "
                    f"{max(r['rounds_won'] for r in rs)} | {statistics.mean(r['max_ante'] for r in rs):.1f} | "
                    f"{sum(r['outcome'] == 'won' for r in rs)} | "
                    f"{statistics.mean(r['invalid'] for r in rs):.1f} | {statistics.mean(r['minutes'] for r in rs):.0f} |")
    ev = RUNS / "pretrain_eval.json"
    extra = ""
    if ev.exists():
        e = json.loads(ev.read_text())
        extra = ("\n\nHeld-out agreement with the HF V68 teacher (1,500 decisions from unseen games):\n\n"
                 "| gen | all | hand | shop | pack | blind |\n|---|---|---|---|---|---|\n"
                 + "\n".join(f"| {g} | {v['all']:.1%} | {v['hand']:.1%} | {v['shop']:.1%} | {v['pack']:.1%} | "
                             f"{v['blind']:.1%} |" for g, v in e.items()))
    md = ("# Laya Balatro — generations\n\nRed Deck / White Stake, sampling T as logged. "
          "gen0 = stock Laya zero-shot; gen1 = imitation of HF V68 teacher; gen2+ = self-play evolution.\n\n"
          + "\n".join(rows) + extra + "\n")
    (RUNS / "generations.md").write_text(md, encoding="utf8")
    return md


# ---------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-per-gen", type=int, default=2)
    ap.add_argument("--gen0-runs", type=int, default=2)
    ap.add_argument("--champion-runs", type=int, default=4, help="runs before a champion is trusted")
    ap.add_argument("--total-runs", type=int, default=1000)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--deck", default="b_red")
    ap.add_argument("--stake", type=int, default=1)
    ap.add_argument("--lr", type=float, default=1e-5)
    ap.add_argument("--max-train-steps", type=int, default=400)
    ap.add_argument("--max-decisions", type=int, default=2500)
    ap.add_argument("--fresh", action="store_true", help="start a new run even if one is in progress")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    (RUNS / "decisions").mkdir(parents=True, exist_ok=True)
    CKPT.mkdir(exist_ok=True)
    if args.report:
        print(report())
        return
    from .policy import Policy

    lock = CKPT / "pretrain.lock"
    done = lambda g: sum(1 for r in load_runs() if r["gen"] == g and r["outcome"] in ("won", "lost"))
    gen, ck = latest_gen()
    if done(0) < args.gen0_runs:
        gen, ck = 0, None  # finish the stock-Laya baseline first so generations are comparable
    device = "cpu" if lock.exists() else "cuda"
    pol = Policy(ck, device=device)
    log(f"policy gen{gen} ({ck or 'stock laya'}) on {device}")
    b = Bridge()
    played_this_gen = done(gen)

    def switch_to_latest():
        nonlocal pol, gen, played_this_gen, device
        g2, ck2 = latest_gen()
        device = "cuda"
        del pol
        torch_empty()
        pol = Policy(ck2, device=device)
        gen, played_this_gen = g2, done(g2)
        log(f"switched to gen{gen} ({ck2}) on cuda")

    if gen >= 1 and device == "cuda" and played_this_gen >= args.runs_per_gen:
        gen = evolve_step(pol, gen, args)  # resumed after a generation already finished its runs
        played_this_gen = 0
    for n in range(args.total_runs):
        if device == "cpu" and not lock.exists() and done(0) >= args.gen0_runs:
            switch_to_latest()
        run_id = f"g{gen}_{time.strftime('%Y%m%d_%H%M%S')}"
        try:
            summary, _ = play_run(b, pol, gen, run_id, args)
        except (ConnectionError, OSError, TimeoutError) as e:
            crashed = game_crashed()
            log(f"bridge lost: {e!r}; game crashed={crashed}")
            with open(RUNS / "runs.jsonl", "a", encoding="utf8") as f:
                f.write(json.dumps({"gen": gen, "run": run_id, "ckpt": pol.ckpt, "outcome": "crash",
                                    "rounds_won": 0, "max_ante": 0, "decisions": 0, "invalid": 0,
                                    "best_hand": 0, "minutes": 0, "error": repr(e)[:200],
                                    "time": time.strftime("%Y-%m-%d %H:%M")}) + "\n")
            try:
                b.close()
            except OSError:
                pass
            b = restart_game() if crashed else Bridge(timeout=120)
            args.fresh = True
            continue
        except Exception:
            log(traceback.format_exc())
            raise
        with open(RUNS / "runs.jsonl", "a", encoding="utf8") as f:
            f.write(json.dumps(summary) + "\n")
        log(f"RUN {run_id}: {summary['outcome']} rounds {summary['rounds_won']} ante {summary['max_ante']} "
            f"({summary['minutes']} min)")
        report()
        if summary["outcome"] not in ("won", "lost"):
            args.fresh = True  # never resume a state the interface could not handle
            continue
        played_this_gen += 1
        if gen == 0:
            # gen1 comes from HF imitation pretraining, not from gen0 self-play
            if played_this_gen >= args.gen0_runs and latest_gen()[0] > 0 and not lock.exists():
                switch_to_latest()
        elif device == "cuda" and played_this_gen >= args.runs_per_gen:
            gen = evolve_step(pol, gen, args)
            played_this_gen = 0
            report()


if __name__ == "__main__":
    main()
