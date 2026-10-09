"""Stage 5: Claude plays real Balatro itself, one command per decision, through the same mod bridge
and the same state text Laya reads (no simulator lookahead, no score calculator).

  python -m laya_player.claude_cli show            # state text + hand indices + numbered options
  python -m laya_player.claude_cli play 0 2 3      # play hand cards by index (discard likewise)
  python -m laya_player.claude_cli do 3            # a listed option (blind, shop, pack, use, sell ...)
  python -m laya_player.claude_cli use 0 1 4       # consumable slot 0 on hand cards 1 and 4
  python -m laya_player.claude_cli pick 2 0 1      # pack item 2, targets hand cards 0 and 1
  python -m laya_player.claude_cli jokers 2 0 1    # reorder jokers: new left-to-right order of slots
  python -m laya_player.claude_cli new [SEED]      # fresh Red Deck / White Stake run

Every command and its result go to runs_claude/moves.jsonl; finished runs to runs_claude/runs.jsonl.
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


def log(rec: dict, name: str = "moves.jsonl") -> None:
    OUT.mkdir(exist_ok=True)
    with open(OUT / name, "a", encoding="utf8") as f:
        f.write(json.dumps({"time": time.strftime("%Y-%m-%d %H:%M:%S"), **rec}, ensure_ascii=False) + "\n")


def settle(b: Bridge) -> dict:
    """Wait for a decision; cash out round rewards on the way, report a win or game over."""
    for _ in range(20):
        p = wait_stable(b)
        ph = p.get("phase")
        if p.get("won") and p.get("overlay_open"):
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
    return [a for a in cands if not (s["phase"] == "hand" and a["t"] in HAND_MOVES)]


def show(b: Bridge) -> None:
    p = settle(b)
    ph = p.get("phase")
    if ph == "GAME_OVER":
        print(f"GAME OVER: ante {p.get('ante')}, seed {p.get('seed')}, won={bool(p.get('won'))}")
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
        print(f"  {i}: {game.action_text(s, a)}")


def main():
    cmd, args = sys.argv[1], [int(x) if x.lstrip("-").isdigit() else x for x in sys.argv[2:]]
    b = Bridge(timeout=15)
    if cmd == "show":
        return show(b)
    if cmd == "new":
        from .evolve import start_run
        start_run(b, "b_red", 1, args[0] if args else None)
        log({"cmd": "new", "seed": args[0] if args else None})
        return show(b)
    p = settle(b)
    if cmd == "endless" or (cmd == "do" and args == ["endless"]):
        print(b.call("endless_mode"))
        return show(b)
    s = canonical(p)
    if cmd in ("play", "discard"):
        a = {"t": cmd, "cards": args}
        desc = f"{cmd} " + " ".join(game.card_labels(s["hand"])[i] for i in args)
    elif cmd == "do":
        a = options(s)[args[0]]
        desc = game.action_text(s, a)
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
        a, desc = None, "jokers order " + " ".join(s["jokers"][i]["key"] for i in args)
    else:
        raise SystemExit(f"unknown command {cmd}")
    try:
        res = b.call("reorder_jokers", {"card_ids": ids}) if a is None else execute(b, s, a)
        ok = True
    except BridgeError as e:
        res, ok = str(e), False
    log({"cmd": cmd, "args": args, "desc": desc, "ok": ok, "ante": s["ante"], "phase": s["phase"],
         "seed": p.get("seed"), "result": res if not ok else None})
    print(("OK " if ok else "REJECTED ") + desc + ("" if ok else f": {res}"))
    p2 = settle(b)
    if p2.get("phase") == "GAME_OVER":
        log({"seed": p2.get("seed"), "ante": p2.get("ante"), "won": bool(p2.get("won"))}, "runs.jsonl")
    show(b)


if __name__ == "__main__":
    main()
