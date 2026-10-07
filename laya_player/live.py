"""Live game adapter: bridge payload -> canonical state, canonical action -> bridge calls."""
from __future__ import annotations

import time

from . import game
from .bridge import Bridge, BridgeError

RANK_MAP = {"Jack": "J", "Queen": "Q", "King": "K", "Ace": "A"}
SUIT_MAP = {"Spades": "S", "Hearts": "H", "Diamonds": "D", "Clubs": "C"}
PACK_PHASES = {"TAROT_PACK", "PLANET_PACK", "SPECTRAL_PACK", "STANDARD_PACK", "BUFFOON_PACK",
               "SMODS_BOOSTER_OPENED"}
TRANSIENT = {"HAND_PLAYED", "DRAW_TO_HAND", "NEW_ROUND", "PLAY_TAROT", "SMODS_REDEEM_VOUCHER", "SPLASH"}


def _blind_key(name: str | None) -> str | None:
    """Display name ("The Goad") -> key ("bl_goad"), matching simulator/HF prompts."""
    if not name:
        return name
    try:
        from jackdaw.engine.blind import BLINDS
    except ImportError:
        return name
    for k, v in BLINDS.items():
        if getattr(v, "name", None) == name:
            return k
    return name


def _live_desc(j: dict) -> str:
    """English effect text with the joker's live values, rendered from its ability table by
    the same code the simulator uses (the game's own text follows the player's language)."""
    from .desc import describe
    ab = j.get("ability")
    return describe(j.get("entity_id"), ab if isinstance(ab, dict) else None)


def _deck_counts(p: dict) -> dict | None:
    t = (((p.get("deck_summary") or {}).get("remaining") or {}).get("tallies")) or {}
    if not t:
        return None
    suits = {SUIT_MAP.get(k, k): (v or {}).get("base", 0) for k, v in (t.get("by_suit") or {}).items()}
    ranks = {RANK_MAP.get(str(k), str(k)): (v or {}).get("base", 0) for k, v in (t.get("by_rank") or {}).items()}
    return {"suits": suits, "ranks": ranks}


def _card(c: dict) -> dict:
    if c.get("faced_down"):
        return {"id": c.get("card_id"), "hidden": True, "rank": "?", "suit": "?"}
    r = str(c.get("rank") or "?")
    d = {"id": c.get("card_id"), "rank": RANK_MAP.get(r, r), "suit": SUIT_MAP.get(c.get("suit"), "?"),
         "enh": c.get("enhancement"), "ed": c.get("edition"), "seal": (c.get("seal") or None),
         "debuff": bool(c.get("debuffed"))}
    if c.get("forced_selection"):  # Cerulean Bell (mod state.lua serialize_playing_card)
        d["forced"] = True
    return d


def _item(x: dict) -> dict:
    kind = x.get("kind")
    if kind == "playing_card":
        return {"id": x.get("card_id"), "kind": "card", "card": _card(x), "cost": x.get("cost", 0)}
    it = {"id": x.get("card_id"), "kind": kind if kind != "consumable" else "tarot", "key": x.get("entity_id"),
          "cost": x.get("cost", 0), "ed": x.get("edition"), "usable": x.get("usable", True)}
    if x.get("usable") is False and it["key"] not in game.TARGETS:  # untargeted pack card the game greys out
        it["blocked"] = True
    return it


def canonical(p: dict) -> dict | None:
    ph = p.get("phase")
    phase = {"BLIND_SELECT": "blind", "SELECTING_HAND": "hand", "SHOP": "shop"}.get(ph)
    if ph in PACK_PHASES:
        phase = "pack"
    if phase is None:
        return None
    r = p.get("round") or {}
    s = {"phase": phase, "ante": p.get("ante"), "money": p.get("money", 0),
         "hands_left": r.get("hands_left", 0), "discards_left": r.get("discards_left", 0),
         "joker_slots": p.get("joker_slots", 5), "consumable_slots": p.get("consumable_slots", 2),
         "deck_left": ((p.get("deck_summary") or {}).get("remaining") or {}).get("draw_pile_count")}
    s["hand"] = [_card(c) for c in p.get("hand") or []] if phase in ("hand", "pack") else []
    s["jokers"] = [{"id": j.get("card_id"), "key": j.get("entity_id"), "sell": j.get("sell_value"),
                    "ed": j.get("edition"), "eternal": "eternal" in (j.get("stickers") or []),
                    "desc": _live_desc(j)} for j in p.get("jokers") or []]
    s["vouchers"] = list(p.get("used_vouchers") or [])
    s["deck_counts"] = _deck_counts(p)
    s["consumables"] = [{"id": c.get("card_id"), "key": c.get("entity_id"), "usable": c.get("usable", True)}
                        for c in p.get("consumables") or []]
    s["levels"] = {h["name"]: [h.get("level", 1), h.get("chips", 0), h.get("mult", 0)]
                   for h in p.get("hand_levels") or []}
    if phase == "hand" and r.get("blind"):
        s["blind"] = {"name": _blind_key(r["blind"].get("name")), "target": r["blind"].get("chips"),
                      "scored": r.get("chips_scored") or 0}
    if phase == "blind":
        bs = (p.get("blind_select") or {})
        cur = bs.get("current")
        bl = bs.get("blinds") or []
        order = ["Small", "Big", "Boss"]
        start = order.index(cur) if cur in order else 0
        s["blinds"] = [{"slot": b.get("slot"), "name": b.get("blind_id") or b.get("name"), "target": b.get("chips"),
                        "tag": (b.get("skip_reward") or {}).get("entity_id")}
                       for b in bl if b.get("slot") in order[start:]]
        s["can_skip"] = "skip_blind" in (p.get("legal_actions") or [])
    if phase == "shop":
        sh = p.get("shop") or {}
        s["shop"] = [_item(x) for x in (sh.get("cards") or []) + (sh.get("vouchers") or []) + (sh.get("boosters") or [])]
        s["reroll_cost"] = 0 if sh.get("free_rerolls") else sh.get("reroll_cost", 5)
    if phase == "pack":
        pk = p.get("pack") or {}
        s["pack"] = [_item(x) if x.get("kind") != "joker" else
                     {"id": x.get("card_id"), "kind": "joker", "key": x.get("entity_id"), "ed": x.get("edition")}
                     for x in pk.get("options") or []]
        s["pack_picks"] = pk.get("picks_remaining", 1)
    return s


def live_candidates(s: dict) -> list[dict]:
    """Generator candidates, minus ones the live game would reject."""
    out = []
    for a in game.candidates(s):
        if a["t"] == "use" and not s["consumables"][a["slot"]].get("usable", True):
            continue
        if a["t"] == "sell_joker" and s["jokers"][a["slot"]].get("eternal"):
            continue
        if a["t"] == "buy" and a["item"]["kind"] == "unknown":
            continue
        out.append(a)
    return out


def execute(b: Bridge, s: dict, a: dict) -> dict:
    t = a["t"]
    hand_ids = lambda idxs: [s["hand"][i]["id"] for i in idxs]
    if t == "select_blind":
        return b.call("select_blind")
    if t == "skip_blind":
        return b.call("skip_blind")
    if t in ("play", "discard"):
        b.call("select_hand_cards", {"card_ids": hand_ids(a["cards"])})
        return b.call("play_hand" if t == "play" else "discard_hand")
    if t == "use":
        params = {"card_id": s["consumables"][a["slot"]]["id"]}
        if a.get("targets"):
            params["targets"] = hand_ids(a["targets"])
        return b.call("use_consumable", params)
    if t == "buy":
        it = a["item"]
        method = {"joker": "buy_card", "card": "buy_card", "voucher": "buy_voucher", "booster": "buy_booster"}.get(
            it["kind"], "buy_consumable")
        return b.call(method, {"card_id": it["id"]})
    if t == "reroll":
        return b.call("reroll_shop")
    if t == "sell_joker":
        return b.call("sell_card", {"card_id": s["jokers"][a["slot"]]["id"]})
    if t == "leave":
        return b.call("leave_shop")
    if t == "pick":
        params = {"card_id": a["item"]["id"]}
        if a.get("targets"):
            params["targets"] = hand_ids(a["targets"])
        return b.call("select_booster_card", params)
    if t == "skip_pack":
        return b.call("skip_booster")
    raise ValueError(t)


def wait_stable(b: Bridge, timeout: float = 20.0) -> dict:
    """Poll until the game sits in a decision phase (or game over / menu)."""
    deadline = time.time() + timeout
    hidden_grace = time.time() + 3.0  # freshly drawn cards are face-down during the draw animation
    p = b.state()["payload"]
    while time.time() < deadline:
        ph = p.get("phase")
        hidden = ph == "SELECTING_HAND" and any(c.get("faced_down") for c in p.get("hand") or [])
        if hidden and time.time() < hidden_grace:
            time.sleep(0.25)
            p = b.state()["payload"]
            continue
        if ph not in TRANSIENT and not (ph == "SELECTING_HAND" and not p.get("hand")):
            if ph != "BLIND_SELECT" or "select_blind" in (p.get("legal_actions") or []):
                return p
        time.sleep(0.25)
        p = b.state()["payload"]
    return p


__all__ = ["canonical", "live_candidates", "execute", "wait_stable", "BridgeError"]
