"""Canonical Balatro decision state, text rendering and candidate-action generation.

Both the live bridge (`live.py`) and the HF dataset converter (`hf_convert.py`) produce the same
canonical state dict, so the Laya prompts the model trains on and plays with are identical.

Canonical state:
  phase: "blind" | "hand" | "shop" | "pack"
  ante, money, hands_left, discards_left, hand_size, joker_slots, consumable_slots, deck_left
  blind: {name, target, scored}                       (hand phase)
  blinds: [{slot, name, target}]                      (blind phase, upcoming first)
  jokers: [{key, sell}]   consumables: [{key}]        keys like "j_jolly", "c_pluto"
  hand: [{rank, suit, enh, ed, seal}]                 rank "2".."10","J","Q","K","A"; suit "S","H","D","C"
  levels: {hand_name: [level, chips, mult]}
  shop: [{kind, key, cost}]  kind: joker|tarot|planet|spectral|voucher|booster|card
  pack: [{kind, key} | {kind:"card", card:{...}}], pack_picks
  selected: [hand idx], sel_budget                    (raw mode: cards picked so far this decision)
Actions: {"t": select_blind|skip_blind|play|discard|use|buy|reroll|sell_joker|leave|pick|skip_pack, ...}

Two action interfaces (LAYA_ACTIONS env var):
  raw (default)  Laya clicks like a player: "select K♥" ... "play selected". One choice question per
                 click, several calls per decision; no combinations, hand labels or score estimates.
                 With LAYA_CALC=1 (Stage 3) each hand click also states its computed consequence (calc.py).
  combo          the original generator: pre-built plays/discards with hand type and ~score.
"""
from __future__ import annotations

import itertools
import os
from collections import Counter

RAW = os.environ.get("LAYA_ACTIONS", "raw") == "raw"
SELECT_BUDGET = 10  # deselects allowed per decision; afterwards a click can only add a card or commit

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
RANK_VAL = {r: i + 2 for i, r in enumerate(RANKS)}
CHIPS = {r: (11 if r == "A" else 10 if r in ("J", "Q", "K") else int(r)) for r in RANKS}
SUIT_SYM = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}

HAND_BASE = {  # level-1 chips, mult; per-level increments
    "Flush Five": (160, 16, 50, 3), "Flush House": (140, 14, 40, 4), "Five of a Kind": (120, 12, 35, 3),
    "Straight Flush": (100, 8, 40, 4), "Four of a Kind": (60, 7, 30, 3), "Full House": (40, 4, 25, 2),
    "Flush": (35, 4, 15, 2), "Straight": (30, 4, 30, 3), "Three of a Kind": (30, 3, 20, 2),
    "Two Pair": (20, 2, 20, 1), "Pair": (10, 2, 15, 1), "High Card": (5, 1, 10, 1),
}

# Consumables that need hand targets: key -> max cards.
TARGETS = {
    "c_magician": 2, "c_empress": 2, "c_hierophant": 2, "c_heirophant": 2,  # the game spells it heirophant
    "c_lovers": 1, "c_chariot": 1, "c_justice": 1,
    "c_strength": 2, "c_hanged_man": 2, "c_death": 2, "c_devil": 1, "c_tower": 1, "c_star": 3,
    "c_moon": 3, "c_sun": 3, "c_world": 3, "c_aura": 1, "c_talisman": 1, "c_deja_vu": 1,
    "c_trance": 1, "c_medium": 1, "c_cryptid": 1,
}
PLANETS = {
    "c_pluto": "High Card", "c_mercury": "Pair", "c_uranus": "Two Pair", "c_venus": "Three of a Kind",
    "c_saturn": "Straight", "c_jupiter": "Flush", "c_earth": "Full House", "c_mars": "Four of a Kind",
    "c_neptune": "Straight Flush", "c_planet_x": "Five of a Kind", "c_ceres": "Flush House",
    "c_eris": "Flush Five",
}

ANTE_BASE = [100, 300, 800, 2000, 5000, 11000, 20000, 35000, 50000, 110000, 560000]


def pretty_key(key: str | None) -> str:
    if not key:
        return "?"
    k = key
    for p in ("j_", "c_", "v_", "p_", "bl_", "tag_", "m_", "e_"):
        if k.startswith(p):
            k = k[len(p):]
            break
    if key.startswith("p_"):
        parts = [x for x in k.split("_") if not x.isdigit()]
        return " ".join(parts) + " pack"
    return k.replace("_", " ")


def card_str(c: dict) -> str:
    if c.get("hidden"):
        return "??"
    s = f"{c['rank']}{SUIT_SYM.get(c['suit'], c['suit'])}"
    extras = [x for x in (c.get("enh"), c.get("ed"), c.get("seal") and f"{c['seal']} seal") if x]
    if c.get("debuff"):
        extras.append("debuffed")
    if c.get("forced"):  # Cerulean Bell: always selected
        extras.append("forced")
    return s + (f"({','.join(extras)})" if extras else "")


# ---------------------------------------------------------------- poker hand evaluation

def _straight_ranks(vals: list[int], four_fingers: bool = False) -> bool:
    need = 4 if four_fingers else 5
    s = sorted(set(vals))
    if 14 in s:
        s = [1] + s
    run = 1
    for a, b in zip(s, s[1:]):
        run = run + 1 if b == a + 1 else 1
        if run >= need:
            return True
    return len(s) >= need and run >= need


def classify(cards: list[dict]) -> tuple[str, list[int]]:
    """Return (hand name, indices of scoring cards) for a played subset."""
    n = len(cards)
    vals = [RANK_VAL.get(c["rank"], 0) for c in cards]
    stone = [c.get("enh") == "stone" for c in cards]
    suits = [c["suit"] for c in cards]
    wild = [c.get("enh") == "wild" for c in cards]
    real = [i for i in range(n) if not stone[i]]
    cnt = Counter(vals[i] for i in real)
    counts = sorted(cnt.values(), reverse=True)
    flush = n == 5 and all(not stone[i] for i in range(n)) and (
        len({suits[i] for i in range(n) if not wild[i]}) <= 1)
    straight = n == 5 and len(real) == 5 and len(cnt) == 5 and _straight_ranks(vals)
    all_idx = list(range(n))

    def of(k_vals):
        return [i for i in real if vals[i] in k_vals] + [i for i in range(n) if stone[i]]

    if counts and counts[0] == 5:
        return ("Flush Five" if flush else "Five of a Kind"), all_idx
    if flush and counts[:2] == [3, 2]:
        return "Flush House", all_idx
    if straight and flush:
        return "Straight Flush", all_idx
    if counts and counts[0] == 4:
        return "Four of a Kind", of([v for v, c in cnt.items() if c == 4])
    if counts[:2] == [3, 2]:
        return "Full House", all_idx
    if flush:
        return "Flush", all_idx
    if straight:
        return "Straight", all_idx
    if counts and counts[0] == 3:
        return "Three of a Kind", of([v for v, c in cnt.items() if c == 3])
    if counts[:2] == [2, 2]:
        return "Two Pair", of([v for v, c in cnt.items() if c == 2])
    if counts and counts[0] == 2:
        return "Pair", of([v for v, c in cnt.items() if c == 2])
    if real:
        top = max(real, key=lambda i: vals[i])
        return "High Card", [top] + [i for i in range(n) if stone[i]]
    return "High Card", all_idx


def level_stats(state: dict, hand: str) -> tuple[int, int]:
    lv = state.get("levels", {}).get(hand)
    if lv:
        return lv[1], lv[2]
    c, m, _, _ = HAND_BASE[hand]
    return c, m


def estimate(state: dict, cards: list[dict]) -> tuple[str, list[int], int]:
    """Joker-free score estimate of playing `cards`: (hand, scoring idx, chips*mult)."""
    hand, idx = classify(cards)
    chips, mult = level_stats(state, hand)
    xm = 1.0
    for i in idx:
        c = cards[i]
        if c.get("debuff"):
            continue
        e = c.get("enh")
        chips += 50 if e == "stone" else CHIPS.get(c["rank"], 0)
        if e == "bonus":
            chips += 30
        elif e == "mult":
            mult += 4
        elif e == "glass":
            xm *= 2
        if c.get("ed") == "foil":
            chips += 50
        elif c.get("ed") == "holo":
            mult += 10
        elif c.get("ed") == "polychrome":
            xm *= 1.5
    for c in state.get("hand", []):  # held steel cards
        if c.get("enh") == "steel" and not any(c is cards[i] for i in range(len(cards))):
            xm *= 1.5
    return hand, idx, int(chips * mult * xm)


# ---------------------------------------------------------------- candidate generation

def _cards_txt(state, idxs):
    return " ".join(card_str(state["hand"][i]) for i in idxs)


def play_candidates(state: dict, k: int = 7) -> list[dict]:
    hand = state.get("hand", [])
    visible = [i for i, c in enumerate(hand) if not c.get("hidden")]
    best: dict[tuple, tuple] = {}
    for size in range(1, min(5, len(visible)) + 1):
        for sub in itertools.combinations(visible, size):
            cards = [hand[i] for i in sub]
            name, sidx, score = estimate(state, cards)
            scoring = tuple(sorted(sub[i] for i in sidx))
            key = (name, scoring)
            # prefer the variant without kickers; a 5-card variant with junk kickers is added below
            if key not in best or len(sub) < len(best[key][0]):
                best[key] = (sub, name, score)
    ranked = sorted(best.values(), key=lambda x: -x[2])
    out, seen_types = [], Counter()
    for sub, name, score in ranked:
        if seen_types[name] >= 2:
            continue
        seen_types[name] += 1
        out.append({"t": "play", "cards": list(sub), "hand": name, "est": score})
        if len(out) >= k:
            break
    # face-down cards (The Fish/House/Mark...): offer blind plays, at most 4 hidden at a time
    hidden = [i for i, c in enumerate(hand) if c.get("hidden")]
    if hidden:
        best_vis = out[0]["cards"] if out else []
        for n in sorted({1, min(4, len(hidden))}):
            cards = sorted(best_vis[: 5 - n] + hidden[:n]) if best_vis else hidden[:n]
            out.append({"t": "play", "cards": cards, "hand": "face-down mix", "est": 0, "blind": True})
    # best hand padded with the lowest junk kickers (cycles cards without lowering the score)
    if out and not out[0].get("blind") and len(out[0]["cards"]) < 5:
        junk = sorted((i for i in visible if i not in out[0]["cards"]),
                      key=lambda i: RANK_VAL.get(hand[i]["rank"], 0))
        pad = out[0]["cards"] + junk[: 5 - len(out[0]["cards"])]
        if len(pad) > len(out[0]["cards"]):
            out.append({"t": "play", "cards": sorted(pad), "hand": out[0]["hand"], "est": out[0]["est"],
                        "kick": True})
    return out


def discard_candidates(state: dict, k: int = 6) -> list[dict]:
    hand = state.get("hand", [])
    n = len(hand)
    if n == 0 or state.get("discards_left", 0) <= 0:
        return []
    vals = [RANK_VAL.get(c["rank"], 0) for c in hand]
    # debuffed cards score nothing: discard them first and never build a draw around them
    dead = [bool(c.get("debuff")) for c in hand]
    # hidden cards carry throwaway ids and cannot be targeted
    order_low = sorted((i for i in range(n) if not hand[i].get("hidden")), key=lambda i: (not dead[i], vals[i]))
    cands: list[tuple[str, list[int]]] = []
    rc = Counter(vals)
    # keep pairs+ : discard singles (lowest first)
    singles = [i for i in order_low if rc[vals[i]] == 1]
    if singles:
        cands.append(("keep pairs", singles[:5]))
    # flush chase: keep most common suit
    sc = Counter(c["suit"] for c, d in zip(hand, dead) if not c.get("hidden") and not d)
    if sc:
        suit, num = sc.most_common(1)[0]
        others = [i for i in order_low if hand[i]["suit"] != suit or dead[i]]
        if num >= 3 and others:
            cands.append((f"chase {SUIT_SYM.get(suit, suit)} flush", others[:5]))
    # straight chase: best 5-wide rank window
    best_win, best_keep = None, []
    for lo in range(1, 11):
        win = set(range(lo, lo + 5))
        keep, used = [], set()
        for i in range(n):
            if dead[i]:
                continue
            v = 1 if vals[i] == 14 and lo == 1 else vals[i]
            if v in win and v not in used:
                keep.append(i)
                used.add(v)
        if len(keep) > len(best_keep):
            best_win, best_keep = lo, keep
    if len(best_keep) >= 3:
        others = [i for i in order_low if i not in best_keep]
        if others:
            cands.append(("chase straight", others[:5]))
    # keep best made hand, discard the rest
    pc = play_candidates(state, k=1)
    if dead.count(True):
        cands.insert(0, ("debuffed", [i for i in order_low if dead[i]][:5]))
    if pc:
        rest = [i for i in order_low if i not in pc[0]["cards"]]
        if rest:
            cands.append((f"keep {pc[0]['hand']}", rest[:5]))
    for m in (2, 3, 5):
        low = [i for i in order_low][:m]
        cands.append((f"lowest {m}", low))
    hidden = [i for i in range(n) if hand[i].get("hidden")]
    if hidden:
        cands.insert(0, ("face-down cards", hidden[:4]))
    out, seen = [], set()
    for why, idxs in cands:
        key = tuple(sorted(idxs))
        if not key or key in seen:
            continue
        seen.add(key)
        out.append({"t": "discard", "cards": list(key), "why": why})
        if len(out) >= k:
            break
    return out


def target_sets(state: dict, m: int) -> list[list[int]]:
    hand = state.get("hand", [])
    vis = [i for i, c in enumerate(hand) if not c.get("hidden")]
    if not vis:
        return []
    hi = sorted(vis, key=lambda i: -RANK_VAL.get(hand[i]["rank"], 0))
    lo = hi[::-1]
    sets = [sorted(hi[:m]), sorted(lo[:m])]
    pc = play_candidates(state, k=1)
    if pc:
        sets.append(sorted(pc[0]["cards"][:m]))
    out = []
    for s in sets:
        if s and s not in out:
            out.append(s)
    return out


def consumable_candidates(state: dict, in_round: bool) -> list[dict]:
    out = []
    for i, c in enumerate(state.get("consumables", [])):
        key = c.get("key", "")
        if key in TARGETS:
            if not in_round:
                continue
            for s in target_sets(state, TARGETS[key]):
                out.append({"t": "use", "slot": i, "key": key, "targets": s})
        else:
            out.append({"t": "use", "slot": i, "key": key})
    return out


MIN_TARGETS = {"c_death": 2}  # Death converts the left card into the right one


def card_labels(hand: list[dict]) -> list[str]:
    """Click label per hand card; position-tagged when two cards would read the same."""
    names = ["face-down card" if c.get("hidden") else card_str(c) for c in hand]
    dup = Counter(names)
    return [f"{n} #{i + 1}" if dup[n] > 1 else n for i, n in enumerate(names)]


def _clicks(state: dict, cap: int = 5) -> list[dict]:
    """Select/deselect clicks; at most `cap` cards selected (5 for a hand, a card's target count in packs).
    A forced card (Cerulean Bell) is selected by the runner and counts toward the cap."""
    sel = state.get("selected", [])
    hand = state.get("hand", [])
    out = []
    for i in range(len(hand)):
        if i in sel:
            if state.get("sel_budget", SELECT_BUDGET) > 0 and not hand[i].get("forced"):
                out.append({"t": "deselect", "card": i, "raw": True})
        elif len(sel) < cap:
            out.append({"t": "select", "card": i, "raw": True})
    return out


PICK_TRIES = 2  # target selections a pack may open; a take/cancel cycle cannot repeat forever


def _targets_ok(state: dict, key: str, sel: list[int]) -> bool:
    if key == "c_aura" and any(state["hand"][i].get("ed") for i in sel):  # Aura needs an editionless card
        return False
    return MIN_TARGETS.get(key, 1) <= len(sel) <= TARGETS[key]


def _offerable(state: dict, a: dict) -> bool:
    """False for moves the game greys out: a consumable it cannot use now (Judgement with full jokers,
    The Fool with nothing to copy...), a pack card with nowhere to go."""
    if a["t"] == "use":
        return bool(state["consumables"][a["slot"]].get("usable", True))
    return not (a["t"] == "pick" and a["item"].get("blocked"))


def raw_candidates(state: dict) -> list[dict]:
    return [a for a in _raw_moves(state) if _offerable(state, a)]


def _raw_moves(state: dict) -> list[dict]:
    """Primitive moves: click cards, then commit them. Shop and blind moves are already primitive."""
    ph = state["phase"]
    sel = list(state.get("selected", []))
    if ph == "hand":
        out = _clicks(state)
        if sel and state.get("hands_left", 0) > 0:
            out.append({"t": "play", "cards": sel, "raw": True})
        if sel and state.get("discards_left", 0) > 0:
            out.append({"t": "discard", "cards": sel, "raw": True})
        for i, c in enumerate(state.get("consumables", [])):
            key = c.get("key", "")
            if key not in TARGETS:
                out.append({"t": "use", "slot": i, "key": key, "raw": True})
            elif _targets_ok(state, key, sel):
                out.append({"t": "use", "slot": i, "key": key, "targets": sel, "raw": True})
        return out
    if ph == "pack":
        items = state.get("pack", [])
        pend = state.get("pending_pick")
        if pend is not None and pend < len(items):
            # Second step of a targeted pack card: click hand cards, then apply (or cancel).
            it = items[pend]
            out = _clicks(state, cap=TARGETS.get(it.get("key", ""), 1))
            if _targets_ok(state, it.get("key", ""), sel):
                out.append({"t": "pick", "slot": pend, "item": it, "targets": sel, "raw": True})
            out.append({"t": "cancel_pick", "slot": pend, "item": it, "raw": True})
            return out
        out = []
        full = len(state.get("jokers", [])) >= state.get("joker_slots", 5)
        for i, it in enumerate(items):
            key = it.get("key", "")
            if it["kind"] == "joker" and full and it.get("ed") != "negative":  # a Negative joker brings its slot
                continue
            if key in TARGETS:  # always visible: choosing it opens target selection
                if (len(state.get("hand", [])) >= MIN_TARGETS.get(key, 1)
                        and state.get("pick_tries", 0) < PICK_TRIES):
                    out.append({"t": "choose_pick", "slot": i, "item": it, "raw": True})
            else:
                out.append({"t": "pick", "slot": i, "item": it, "raw": True})
        out.append({"t": "skip_pack"})
        return out
    if ph == "shop":  # targeted consumables cannot be used without a hand
        return [a for a in combo_candidates(state) if not a.get("targets")]
    return combo_candidates(state)


def candidates(state: dict) -> list[dict]:
    return raw_candidates(state) if RAW else combo_candidates(state)


def combo_candidates(state: dict) -> list[dict]:
    ph = state["phase"]
    if ph == "blind":
        out = [{"t": "select_blind"}]
        if state.get("can_skip"):
            out.append({"t": "skip_blind"})
        return out
    if ph == "hand":
        out = []
        if state.get("hands_left", 0) > 0:
            out += play_candidates(state)
        out += discard_candidates(state)
        out += consumable_candidates(state, True)[:4]
        return out
    if ph == "shop":
        out = []
        money = state.get("money", 0)
        njok = len(state.get("jokers", []))
        ncons = len(state.get("consumables", []))
        for i, it in enumerate(state.get("shop", [])):
            if it.get("cost", 0) > money:
                continue
            if it["kind"] == "joker" and njok >= state.get("joker_slots", 5):
                continue
            if it["kind"] in ("tarot", "planet", "spectral") and ncons >= state.get("consumable_slots", 2):
                continue
            out.append({"t": "buy", "slot": i, "item": it})
        rc = state.get("reroll_cost", 5)
        if rc is not None and rc <= money:
            out.append({"t": "reroll", "cost": rc})
        for i, j in enumerate(state.get("jokers", [])):
            out.append({"t": "sell_joker", "slot": i, "key": j.get("key"), "sell": j.get("sell")})
        out += consumable_candidates(state, False)
        out.append({"t": "leave"})
        return out
    if ph == "pack":
        out = []
        has_hand = bool(state.get("hand"))
        for i, it in enumerate(state.get("pack", [])):
            key = it.get("key", "")
            if it["kind"] == "joker" and len(state.get("jokers", [])) >= state.get("joker_slots", 5):
                continue
            if key in TARGETS:
                if not has_hand:
                    continue
                for s in target_sets(state, TARGETS[key])[:2]:
                    out.append({"t": "pick", "slot": i, "item": it, "targets": s})
            else:
                out.append({"t": "pick", "slot": i, "item": it})
        out.append({"t": "skip_pack"})
        return out
    return []


def action_key(a: dict) -> tuple:
    """Identity used to match a teacher action to a generated candidate."""
    t = a["t"]
    if t in ("play", "discard"):
        return (t, tuple(sorted(a["cards"])))
    if t in ("select", "deselect"):
        return (t, a["card"])
    if t in ("choose_pick", "cancel_pick"):
        return (t, a["slot"])
    if t in ("buy", "sell_joker", "pick"):
        return (t, a["slot"], tuple(sorted(a.get("targets", []))))
    if t == "use":
        return (t, a["slot"], tuple(sorted(a.get("targets", []))))
    return (t,)


def item_str(it: dict) -> str:
    if it.get("kind") == "card":
        return "card " + card_str(it["card"])
    from .desc import name_of
    name = name_of(it.get("key")) if it.get("key") else "?"
    if it.get("key") in PLANETS:
        name += f" (+{PLANETS[it['key']]})"
    ed = f" {it['ed']}" if it.get("ed") else ""
    return f"{it['kind']} {name}{ed}"


def action_text(state: dict, a: dict) -> str:
    t = a["t"]
    if t == "select_blind":
        return "play this blind"
    if t == "skip_blind":
        return "skip this blind for the tag"
    if a.get("raw"):
        from .desc import name_of
        note = f" → {a['note']}" if a.get("note") else ""  # computed consequence (calc.py, Stage 3)
        if t in ("select", "deselect"):
            return f"{t} {card_labels(state['hand'])[a['card']]}{note}"
        if t in ("play", "discard"):
            return f"{t} selected{note}"
        tg = " on selected" if a.get("targets") else ""
        if t == "use":
            return f"use {name_of(a['key'])}{tg}"
        if t == "choose_pick":
            return f"take {item_str(a['item'])} (then choose its target cards)"
        if t == "cancel_pick":
            return f"cancel {name_of(a['item'].get('key'))}"
        if t == "pick" and a.get("targets"):
            return f"apply {name_of(a['item'].get('key'))} to selected"
        if t == "pick":
            return f"take {item_str(a['item'])}{tg}"
    if t == "play":
        tag = " +kickers" if a.get("kick") else ""
        return f"play {a['hand']}{tag}: {_cards_txt(state, a['cards'])} (~{a['est']})"
    if t == "discard":
        return f"discard {_cards_txt(state, a['cards'])} ({a.get('why', '')})"
    if t == "use":
        tg = f" on {_cards_txt(state, a['targets'])}" if a.get("targets") else ""
        from .desc import name_of
        return f"use {name_of(a['key'])}{tg}"
    if t == "buy":
        return f"buy {item_str(a['item'])} ${a['item'].get('cost', '?')}"
    if t == "reroll":
        return f"reroll shop ${a['cost']}"
    if t == "sell_joker":
        from .desc import name_of
        return f"sell joker {name_of(a['key'])}" + (f" +${a['sell']}" if a.get("sell") else "")
    if t == "leave":
        return "leave shop"
    if t == "pick":
        tg = f" on {_cards_txt(state, a['targets'])}" if a.get("targets") else ""
        return f"take {item_str(a['item'])}{tg}"
    if t == "skip_pack":
        return "skip pack"
    return t


def _describe(key, ability=None, levels=None):
    from .desc import describe
    if key in PLANETS and levels:
        ability = {"level": (levels.get(PLANETS[key]) or [1])[0]}
    return describe(key, ability)


def _item_desc(it: dict, levels: dict) -> str:
    if it.get("kind") == "card":
        return "playing card " + card_str(it["card"])
    d = it.get("desc") or _describe(it.get("key"), levels=levels)
    ed = f" [{it['ed']}]" if it.get("ed") else ""
    return f"{it['kind']} {d}{ed}"


def deck_text(s: dict) -> str:
    dc = s.get("deck_counts")
    if not dc:
        return f"deck {s['deck_left']} cards" if s.get("deck_left") is not None else ""
    sc = dc.get("suits", {})
    suits = " ".join(f"{SUIT_SYM[k]}{sc[k]}" for k in ("S", "H", "D", "C") if sc.get(k))
    ranks = " ".join(f"{r}:{dc['ranks'][r]}" for r in reversed(RANKS) if dc.get("ranks", {}).get(r))
    return f"deck {s.get('deck_left', '?')} cards left ({suits}; {ranks})"


def selected_text(s: dict) -> str:
    """What the game screen shows for the current selection: poker hand and its level chips x mult."""
    sel = s.get("selected", [])
    if not sel:
        return "Selected (0/5): none"
    cards = [s["hand"][i] for i in sel]
    txt = f"Selected ({len(sel)}/5): " + " ".join(card_labels(s["hand"])[i] for i in sel)
    if s["phase"] == "hand" and not any(c.get("hidden") for c in cards):
        hand, _ = classify(cards)
        chips, mult = level_stats(s, hand)
        txt += f" = {hand} ({chips} x {mult})"
    return txt


def state_text(s: dict) -> str:
    """Full-information prompt: every effect the decision depends on, in words."""
    ph = s["phase"]
    levels = s.get("levels", {})
    lines = [f"Ante {s.get('ante', '?')}, ${s.get('money', 0)}"]
    if ph == "hand" and s.get("blind"):
        b = s["blind"]
        lines.append(f"Blind {_describe(b.get('name'))}. Score {b.get('scored', 0)}/{b.get('target', '?')}, "
                     f"{s.get('hands_left', 0)} hands and {s.get('discards_left', 0)} discards left.")
    if ph == "blind" and s.get("blinds"):
        lines.append("Upcoming: " + "; ".join(
            f"{_describe(b.get('name'))} (needs {b.get('target', '?')})"
            + (f", skip reward {_describe(b['tag'])}" if b.get("tag") else "") for b in s["blinds"]))
    j = s.get("jokers", [])
    lines.append(f"Jokers {len(j)}/{s.get('joker_slots', 5)}:" + ("".join(
        f"\n- {x.get('desc') or _describe(x.get('key'))}" + (f" [{x['ed']}]" if x.get("ed") else "") for x in j)
        if j else " none"))
    c = s.get("consumables", [])
    if c:
        lines.append(f"Consumables {len(c)}/{s.get('consumable_slots', 2)}:" + "".join(
            f"\n- {_describe(x.get('key'), levels=levels)}" for x in c))
    if s.get("vouchers"):
        lines.append("Vouchers: " + "; ".join(_describe(v) for v in s["vouchers"]))
    lv = {k: v for k, v in levels.items() if v[0] > 1}
    if lv:
        # Ties in a fixed hand order: the mod sends levels alphabetically, the simulator in HAND_BASE order,
        # and the differing line flipped a near-tie choice (seed U919ZL9K: real 14 rounds vs sim 8).
        order = list(HAND_BASE)
        lines.append("Hand levels: " + ", ".join(
            f"{k} L{v[0]} ({v[1]}x{v[2]})" for k, v in sorted(
                lv.items(), key=lambda x: (-x[1][0], order.index(x[0]) if x[0] in order else len(order)))))
    if s.get("hand"):
        lines.append("Hand: " + " ".join(card_str(x) for x in s["hand"]))
        if s.get("pending_pick") is not None and ph == "pack":
            it = s["pack"][s["pending_pick"]]
            k = it.get("key", "")
            lines.append(f"Using {_describe(k)}: select {MIN_TARGETS.get(k, 1)}-{TARGETS.get(k, 1)} hand cards, then apply")
        if "selected" in s:
            lines.append(selected_text(s))
        from .desc import card_legend
        leg = card_legend(s["hand"])
        if leg:
            lines.append("Card effects: " + leg)
    if ph == "shop":
        lines.append(f"Shop (reroll ${s.get('reroll_cost', '?')}):" + ("".join(
            f"\n- ${x.get('cost')} {_item_desc(x, levels)}" for x in s.get("shop", [])) or " empty"))
    if ph == "pack":
        lines.append(f"Pack, {s.get('pack_picks', 1)} pick(s):" + "".join(
            f"\n- {_item_desc(x, levels)}" for x in s.get("pack", [])))
    dt = deck_text(s)
    if dt:
        lines.append(dt)
    return "\n".join(lines)


QUESTION = {
    "blind": "Balatro: play the upcoming blind or skip it for its tag?",
    "hand": ("Balatro: which play, discard or consumable gives the best chance to beat the blind and win the run?"
             if not RAW else
             "Balatro: next click to beat the blind and win the run: select or deselect a card, play or "
             "discard the selected cards, or use a consumable"),
    "shop": "Balatro shop: which purchase or action best improves the run?",
    "pack": ("Balatro booster pack: which card should be taken?" if not RAW else
             "Balatro booster pack: which card should be taken (select hand cards first for cards that need targets)?"),
}
