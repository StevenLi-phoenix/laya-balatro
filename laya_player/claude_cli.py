"""Stage 5: Claude plays real Balatro itself, one command per decision, through the same mod bridge
and the same state text Laya reads (no simulator lookahead, no score calculator).

  python -m laya_player.claude_cli show            # state text + hand indices + numbered options
  python -m laya_player.claude_cli play 0 2 3      # play hand cards by index (discard likewise)
  python -m laya_player.claude_cli play 0 1 2 6 7 expect=KKK33   # refuse unless the chosen ranks match (T = 10)
  python -m laya_player.claude_cli do 3            # a listed option (blind, shop, pack, use, sell ...)
  python -m laya_player.claude_cli use 0 1 4       # consumable slot 0 on hand cards 1 and 4
  python -m laya_player.claude_cli pick 2 0 1      # pack item 2, targets hand cards 0 and 1
  python -m laya_player.claude_cli jokers 2 0 1    # reorder jokers: new left-to-right order of slots
  python -m laya_player.claude_cli new [SEED]      # fresh Red Deck / White Stake run
  python -m laya_player.claude_cli new deck=b_blue stake=3 [seed=X]   # any deck/stake
  python -m laya_player.claude_cli new challenge=c_omelette_1         # a challenge run
  python -m laya_player.claude_cli new deck=b_blue stake=1 model=haiku effort=high [variant=bare]   # label the player (variant = which brief it got)
  python -m laya_player.claude_cli report [model]  # per-mode table (default) or per-model/effort table from runs.jsonl
  python -m laya_player.claude_cli recover        # game crashed/closed: kill + relaunch it and continue the saved run
  python -m laya_player.claude_cli annotate [RUN_ID] tokens=187417 tool_uses=131   # add facts to a finished run

Prefer the wrapper `./bal <command>` (cd + utf-8 handled). The run (deck, stake, seed, model, effort, start time) is
kept in runs_claude/current.json. Every command goes to runs_claude/moves.jsonl tagged with run_id/model/effort;
a finished run (loss or win) adds one row to runs_claude/runs.jsonl: run_id, model, effort, mode, seed, ante, won,
commands, duration_s, jokers. `annotate` adds what the CLI cannot see (tokens, tool_uses).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("LAYA_ACTIONS", "raw")

from . import game  # noqa: E402
from .bridge import Bridge, BridgeError  # noqa: E402
from .live import canonical, execute, live_candidates, wait_stable  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "runs_claude"
HAND_MOVES = ("select", "deselect", "play", "discard")


def current() -> dict:
    try:
        return json.loads((OUT / "current.json").read_text(encoding="utf8"))
    except (OSError, ValueError):
        return {}


def log(rec: dict, name: str = "moves.jsonl") -> None:
    OUT.mkdir(exist_ok=True)
    tag = {k: v for k, v in current().items() if k in ("run_id", "model", "effort", "variant") and v} if name == "moves.jsonl" else {}
    rec = {**tag, **rec}
    with open(OUT / name, "a", encoding="utf8") as f:
        f.write(json.dumps({"time": time.strftime("%Y-%m-%d %H:%M:%S"), **rec}, ensure_ascii=False) + "\n")


def settle(b: Bridge) -> dict:
    """Wait for a decision; cash out round rewards on the way, report a win or game over."""
    for _ in range(20):
        p = wait_stable(b)
        ph = p.get("phase")
        if p.get("won") and p.get("overlay_open") and ph != "GAME_OVER":  # GAME_OVER + won seen once on a loss (Plasma, Ante 8)
            print(f"*** WON (ante {p.get('ante')}) -- the win overlay is up; `do endless` keeps playing")
            return p
        if ph == "ROUND_EVAL":
            try:
                b.call("cash_out")
            except BridgeError as e:
                print("cash_out:", e)
                time.sleep(1)
            continue
        return p
    return p


def options(s: dict) -> list[dict]:
    cands = live_candidates(s)
    out = [a for a in cands if not (s["phase"] == "hand" and a["t"] in HAND_MOVES)]
    # The game allows selling outside the shop too (Verdant Leaf mid-blind, or freeing a slot inside a Buffoon pack).
    if s["phase"] in ("hand", "blind", "pack"):
        out += [{"t": "sell_joker", "slot": i, "key": j.get("key"), "sell": j.get("sell")}
                for i, j in enumerate(s.get("jokers", [])) if not j.get("eternal")]
    return out


def opt_text(s: dict, a: dict) -> str:
    t = game.action_text(s, a)
    if a["t"] == "skip_blind" and (s.get("blinds") or [{}])[0].get("slot") == "Big":
        t += " (next stop is the BOSS: no shop before it)"
    return t


def show(b: Bridge) -> None:
    p = settle(b)
    ph = p.get("phase")
    if ph == "GAME_OVER":
        print(f"GAME OVER: ante {p.get('ante')}, seed {p.get('seed')}, won=False")
        return
    if ph == "MENU":
        print("MENU (start with `new`)")
        return
    s = canonical(p)
    if s is None:
        print("phase", ph, "(not a decision)")
        return
    print(f"[seed {p.get('seed')}] round {(p.get('round') or {}).get('round_num', '?')}")
    print(game.state_text(s))
    if s["phase"] in ("hand", "pack") and s["hand"]:
        print("\nHAND (index: card): " + "  ".join(f"{i}:{l}" for i, l in enumerate(game.card_labels(s["hand"]))))
    if s["jokers"]:
        print("JOKERS (slot: key): " + "  ".join(f"{i}:{j['key']}" for i, j in enumerate(s["jokers"])))
    if s["phase"] == "pack":
        print("PACK (index: item): " + "  ".join(f"{i}:{game.item_str(x)}" for i, x in enumerate(s["pack"])))
    print("\nOPTIONS:")
    for i, a in enumerate(options(s)):
        print(f"  {i}: {opt_text(s, a)}")


def read_runs() -> list[dict]:
    return [json.loads(l) for l in (OUT / "runs.jsonl").read_text(encoding="utf8").splitlines() if l.strip()]


def report(by: str = "mode") -> None:
    """Table of finished runs from runs.jsonl: per mode (deck/stake/challenge) or per model/effort."""
    rows: dict[tuple, list] = {}
    for r in read_runs():
        if "deck" not in r:
            continue
        key = (r.get("challenge") or r["deck"], r.get("stake")) if by == "mode" else (r.get("model") or "?", (r.get("effort") or "-") + ("/" + r["variant"] if r.get("variant") else ""))
        rows.setdefault(key, []).append(r)
    head = ("mode", "stake") if by == "mode" else ("model", "effort")
    print(f"| {head[0]} | {head[1]} | runs | wins | avg ante | best ante | avg commands | avg tokens |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")

    def avg(rs, k):
        v = [r[k] for r in rs if isinstance(r.get(k), (int, float))]
        return f"{sum(v) / len(v):.1f}" if v else "-"
    for (a, b), rs in rows.items():
        print(f"| {a} | {b} | {len(rs)} | {sum(bool(r['won']) for r in rs)} | {avg(rs, 'ante')} | "
              f"{max((r['ante'] or 0) for r in rs)} | {avg(rs, 'commands')} | {avg(rs, 'tokens')} |")


def annotate(args: list) -> None:
    """annotate [RUN_ID] key=value ...: add facts the CLI cannot see (tokens, tool_uses, notes) to a finished run."""
    ids = [str(x) for x in args if "=" not in str(x)]
    kv = {}
    for x in args:
        if "=" in str(x):
            k, v = str(x).split("=", 1)
            kv[k] = int(v) if v.lstrip("-").isdigit() else v
    rows = read_runs()
    row = next((r for r in reversed(rows) if ids and r.get("run_id") == ids[0]), rows[-1] if rows and not ids else None)
    if row is None:
        raise SystemExit("no such run")
    row.update(kv)
    (OUT / "runs.jsonl").write_text(chr(10).join(json.dumps(r, ensure_ascii=False) for r in rows) + chr(10), encoding="utf8")
    print("annotated", row.get("run_id") or row.get("seed"), kv)


def main():
    cmd, args = sys.argv[1], [int(x) if x.lstrip("-").isdigit() else x for x in sys.argv[2:]]
    if cmd == "recover":  # the game died (pipe missing / crash screen): relaunch it and continue the saved run
        from .evolve import restart_game
        b = restart_game()
        for _ in range(5):
            try:
                print(b.call("continue_game", timeout=60))
                break
            except BridgeError as e:
                print("continue_game:", e)
                time.sleep(5)
        return show(b)
    if cmd == "report":
        return report(str(args[0]) if args else "mode")
    if cmd == "annotate":
        return annotate(args)
    b = Bridge(timeout=15)
    if cmd == "show":
        return show(b)
    if cmd == "new":
        from .evolve import start_run
        kw = dict(str(x).split("=", 1) for x in args if "=" in str(x))
        seed = kw.get("seed") or next((str(x) for x in args if "=" not in str(x)), None)
        if "challenge" in kw:
            if (b.state()["payload"] or {}).get("phase") != "MENU":
                b.call("go_to_menu", timeout=30)
                wait_stable(b, timeout=30)
            b.call("new_game", {"challenge": kw["challenge"]})
        else:
            start_run(b, kw.get("deck", "b_red"), int(kw.get("stake", 1)), seed)
        deck, stake = kw.get("deck", "b_red"), int(kw.get("stake", 1))
        cur = {"run_id": time.strftime("%Y%m%d-%H%M%S") + "-" + (kw.get("challenge") or deck), "started": time.time(),
               "deck": deck, "stake": stake, "challenge": kw.get("challenge"),
               "variant": kw.get("variant"), "model": kw.get("model") or os.environ.get("BAL_MODEL"), "effort": kw.get("effort") or os.environ.get("BAL_EFFORT"),
               "seed": wait_stable(b).get("seed")}
        (OUT / "current.json").write_text(json.dumps(cur), encoding="utf8")
        log({"cmd": "new", "seed": cur["seed"], "deck": deck, "stake": stake, "challenge": cur["challenge"]})
        return show(b)
    p = settle(b)
    if cmd == "endless" or (cmd == "do" and args == ["endless"]):
        print(b.call("endless_mode"))
        return show(b)
    s = canonical(p)
    try:
        if cmd in ("play", "discard"):
            want = next((str(x)[7:] for x in args if str(x).startswith("expect=")), None)
            args = [x for x in args if not str(x).startswith("expect=")]
            labels = game.card_labels(s["hand"])
            if not 1 <= len(args) <= 5:  # the game silently rejects 6+ cards
                raise SystemExit(f"{cmd} takes 1..5 cards, got {len(args)}; nothing done")
            if want:  # e.g. expect=KKK33: ranks of the chosen cards, order-free; guards against index slips
                rk = lambda l: "?" if l.startswith("face-down") else "T" if l.startswith("10") else l[0]  # face-down = ?
                got = sorted(rk(labels[i]) for i in args)
                if got != sorted(want.upper().replace("10", "T")):
                    raise SystemExit(f"{cmd} {args} would be {''.join(got)} ({' '.join(labels[i] for i in args)}), not {want}; nothing done")
            a = {"t": cmd, "cards": args}
            desc = f"{cmd} " + " ".join(labels[i] for i in args)
        elif cmd == "do":
            opts = options(s)
            if not 0 <= args[0] < len(opts):
                raise SystemExit(f"option {args[0]} does not exist (0..{len(opts) - 1}); run show; nothing done")
            a = opts[args[0]]
            desc = opt_text(s, a)
            want = " ".join(str(x) for x in args[1:])
            if want and want.lower() not in desc.lower():  # options re-index after every action
                raise SystemExit(f"option {args[0]} is now '{desc}', not '{want}'; nothing done")
        elif cmd == "use":
            a = {"t": "use", "slot": args[0], "targets": args[1:]}
            desc = f"use {s['consumables'][args[0]]['key']} on " + " ".join(game.card_labels(s["hand"])[i] for i in args[1:])
        elif cmd == "pick":
            a = {"t": "pick", "item": s["pack"][args[0]], "targets": args[1:]}
            desc = f"pick {game.item_str(s['pack'][args[0]])}" + (" on " + " ".join(game.card_labels(s["hand"])[i] for i in args[1:]) if args[1:] else "")
        elif cmd == "jokers":
            ids = [s["jokers"][i]["id"] for i in args]
            a, desc = None, "jokers order " + " ".join(str(s["jokers"][i].get("key")) for i in args)
        else:
            raise SystemExit(f"unknown command {cmd}")
    except (IndexError, KeyError, TypeError) as e:  # a bad index/slot: say so instead of a traceback
        raise SystemExit(f"{cmd} {args}: no such hand card / option / slot / pack item ({type(e).__name__}); nothing done")
    try:
        res = b.call("reorder_jokers", {"card_ids": ids}) if a is None else execute(b, s, a)
        ok = True
    except (BridgeError, ValueError) as e:  # ValueError: a targeted pack pick via `do` (use `pick N targets`)
        res, ok = str(e), False
    log({"cmd": cmd, "args": args, "desc": desc, "ok": ok, "ante": s["ante"], "phase": s["phase"],
         "seed": p.get("seed"), "result": res if not ok else None})
    print(("OK " if ok else "REJECTED ") + desc + ("" if ok else f": {res}"))
    p2 = settle(b)
    if p2.get("phase") == "GAME_OVER" or (p2.get("won") and p2.get("overlay_open")):  # a loss, or the win overlay
        cur = current()
        if not cur.get("finished"):  # one row per run, even if more commands follow a game over
            started = cur.get("started")
            mine = [json.loads(l) for l in (OUT / "moves.jsonl").read_text(encoding="utf8").splitlines()
                    if cur.get("run_id") and cur["run_id"] in l]
            log({"run_id": cur.get("run_id"), "model": cur.get("model"), "effort": cur.get("effort"), "variant": cur.get("variant"),
                 "seed": p2.get("seed"), "ante": p2.get("ante"), "round": (p2.get("round") or {}).get("round_num"),
                 "won": bool(p2.get("won")) and p2.get("phase") != "GAME_OVER", "deck": cur.get("deck"), "stake": cur.get("stake"), "challenge": cur.get("challenge"),
                 "commands": sum(1 for m in mine if m.get("cmd") != "new"),
                 "duration_s": round(time.time() - started) if started else None,
                 "jokers": [j["key"] for j in s["jokers"]]}, "runs.jsonl")
            cur["finished"] = True
            (OUT / "current.json").write_text(json.dumps(cur), encoding="utf8")
    show(b)


if __name__ == "__main__":
    main()
