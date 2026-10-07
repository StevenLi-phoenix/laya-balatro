"""jackdaw (bit-exact Python Balatro) adapter: engine game_state <-> canonical state/actions.

Produces exactly the canonical dict `live.canonical` produces, so the Laya prompts in simulation
and in the real game are identical and a simulator-trained policy transfers without changes.
"""
from __future__ import annotations

from jackdaw.engine import game as engine
from jackdaw.engine.actions import (CashOut, Discard, NextRound, OpenBooster, PickPackCard, PlayHand,
                                    RedeemVoucher, Reroll, SelectBlind, SellCard, SkipBlind, SkipPack,
                                    UseConsumable, get_legal_actions)
from jackdaw.engine.consumables import can_use_consumable, pack_pick_block_reason
from jackdaw.engine.game import IllegalActionError
from jackdaw.engine.run_init import initialize_run

from . import game

RANK = {"Jack": "J", "Queen": "Q", "King": "K", "Ace": "A"}
SUIT = {"Spades": "S", "Hearts": "H", "Diamonds": "D", "Clubs": "C"}
KIND = {"Joker": "joker", "Tarot": "tarot", "Planet": "planet", "Spectral": "spectral", "Voucher": "voucher",
        "Booster": "booster", "Default": "card", "Enhanced": "card"}
HANDS = list(game.HAND_BASE)
BLIND_MULT = {"Small": 1.0, "Big": 1.5, "Boss": 2.0}


def _blind_mult(slot: str, key: str) -> float:
    """Score multiple of a blind: bosses differ (The Wall x4, The Needle x1, Violet Vessel x6)."""
    from jackdaw.engine.blind import BLINDS
    b = BLINDS.get(key)
    return b.mult if b is not None else BLIND_MULT[slot]


def _val(x):
    return getattr(x, "value", x)


def _edition(card) -> str | None:
    ed = card.edition
    if isinstance(ed, dict):
        for k in ("foil", "holo", "polychrome", "negative"):
            if ed.get(k):
                return k
    return None


def _card(c) -> dict:
    if getattr(c, "facing", "front") == "back":
        return {"hidden": True, "rank": "?", "suit": "?"}
    rank = str(_val(c.base.rank))
    ck = c.center_key or "c_base"
    d = {"rank": RANK.get(rank, rank), "suit": SUIT.get(str(_val(c.base.suit)), "?"),
         "enh": ck[2:] if ck.startswith("m_") else None, "ed": _edition(c),
         "seal": c.seal or None, "debuff": bool(c.debuff)}
    if isinstance(c.ability, dict) and c.ability.get("forced_selection"):  # Cerulean Bell
        d["forced"] = True
    return d


def _set(c) -> str:
    ab = c.ability if isinstance(c.ability, dict) else {}
    return ab.get("set") or ("Joker" if c.center_key.startswith("j_") else "Default")


def _item(c, src: tuple[str, int]) -> dict:
    kind = KIND.get(_set(c), "card")
    it = {"kind": kind, "cost": c.cost, "src": src}
    if kind == "card":
        it["card"] = _card(c)
    else:
        it["key"] = c.center_key
        it["ed"] = _edition(c)
    return it


def _usable(c, gs: dict) -> bool:
    """The mod's `usable`: targeted cards need enough hand cards (the selection is judged when used)."""
    hand = gs.get("hand", [])
    if c.center_key in game.TARGETS:
        return len(hand) >= game.MIN_TARGETS.get(c.center_key, 1)
    return can_use_consumable(c, hand_cards=hand, jokers=gs.get("jokers", []), consumables=gs.get("consumables", []),
                              consumable_limit=gs.get("consumable_slots", 2), joker_limit=gs.get("joker_slots", 5),
                              game_state=gs)


def _pack_item(c, i: int, gs: dict) -> dict:
    it = _item(c, ("pack", i))
    # untargeted cards only: a targeted one is judged against the selection it is applied to
    if it.get("key") not in game.TARGETS and pack_pick_block_reason(c, gs, None) is not None:
        it["blocked"] = True
    return it


def _frame_ability(j, gs: dict) -> dict:
    """Ability values the real game recomputes every frame (card.lua Card:update) while jackdaw only
    computes them when scoring. Descriptions must show the real game's numbers: a Cloud 9 shown as
    "(Currently $0)" instead of "$4" flipped a near-tie on seed TZIUSW9J (real 1 round, sim 19)."""
    ab = dict(j.ability) if isinstance(j.ability, dict) else {}
    k = j.center_key
    owned = gs.get("deck", []) + gs.get("hand", []) + gs.get("discard_pile", [])  # G.playing_cards
    if k == "j_cloud_9":
        ab["nine_tally"] = sum(1 for c in owned if c.get_id() == 9)
    elif k == "j_steel_joker":
        ab["steel_tally"] = sum(1 for c in owned if c.center_key == "m_steel")
    elif k == "j_stone":
        ab["stone_tally"] = sum(1 for c in owned if c.center_key == "m_stone")
    elif k == "j_drivers_license":
        ab["driver_tally"] = sum(1 for c in owned if c.center_key not in ("", "c_base"))
    elif k == "j_stencil":
        jokers = gs.get("jokers", [])
        ab["x_mult"] = gs.get("joker_slots", 5) - len(jokers) + sum(x.center_key == "j_stencil" for x in jokers)
    elif k == "j_swashbuckler":
        ab["mult"] = sum(x.sell_cost for x in gs.get("jokers", []) if x is not j)
    elif k == "j_throwback":
        ab["x_mult"] = 1 + gs.get("skips", 0) * ab.get("extra", 0)
    return ab


def _joker_desc(j, gs: dict) -> str:
    from .desc import describe
    return describe(j.center_key, _frame_ability(j, gs))


def _deck_counts(deck) -> dict:
    suits = {"S": 0, "H": 0, "D": 0, "C": 0}
    ranks: dict[str, int] = {}
    for c in deck:
        cc = _card(c) if getattr(c, "facing", "front") == "front" else None
        if cc is None or cc["enh"] == "stone":
            continue
        suits[cc["suit"]] = suits.get(cc["suit"], 0) + 1
        ranks[cc["rank"]] = ranks.get(cc["rank"], 0) + 1
    return {"suits": suits, "ranks": ranks}


def canonical(gs: dict) -> dict | None:
    ph = _val(gs["phase"])
    phase = {"blind_select": "blind", "selecting_hand": "hand", "shop": "shop", "pack_opening": "pack"}.get(ph)
    if phase is None:
        return None
    cr = gs.get("current_round", {})
    ante = gs["round_resets"]["ante"]
    s = {"phase": phase, "ante": ante, "money": gs.get("dollars", 0),
         "hands_left": cr.get("hands_left", 0), "discards_left": cr.get("discards_left", 0),
         "joker_slots": gs.get("joker_slots", 5), "consumable_slots": gs.get("consumable_slots", 2),
         "deck_left": len(gs.get("deck", []))}
    # Opening an Arcana/Spectral pack deals into gs["hand"] (sorted like the real game's pack hand),
    # and pack-card targets index that list. Mapping through gs["pack_hand"] instead sent every
    # pack tarot to the wrong cards.
    hand = gs.get("hand", [])
    order = list(range(len(hand)))
    hidden = [i for i, c in enumerate(hand) if getattr(c, "facing", "front") == "back"]
    if hidden:
        # The mod lists a hand with face-down cards by card id (creation order), hidden cards last, so a
        # hidden card's place cannot give its rank away; jackdaw's rank-sorted order leaked it ("??" between
        # a 9 and a 6 is a 7 or 8) and diverged from the real game (seed C6HRB2UR: real 12 vs sim 11).
        order = sorted((i for i in order if i not in hidden), key=lambda i: hand[i].sort_id)
        order += sorted(hidden, key=lambda i: hash(id(hand[i])))
    s["hand"] = [_card(hand[i]) for i in order] if phase in ("hand", "pack") else []
    s["_hidx"] = order
    s["jokers"] = [{"key": j.center_key, "sell": j.sell_cost, "ed": _edition(j), "eternal": bool(j.eternal),
                    "desc": _joker_desc(j, gs)} for j in gs.get("jokers", [])]
    s["vouchers"] = sorted(k for k, v in (gs.get("used_vouchers") or {}).items() if v)
    s["deck_counts"] = _deck_counts(gs.get("deck", []))
    s["consumables"] = [{"key": c.center_key, "usable": _usable(c, gs)} for c in gs.get("consumables", [])]
    hl = gs["hand_levels"]
    s["levels"] = {}
    for h in HANDS:
        st = hl.get_state(h)
        s["levels"][h] = [st.level, st.chips, st.mult]
    if phase == "hand":
        b = gs["blind"]
        s["blind"] = {"name": b.key, "target": int(b.chips), "scored": int(gs.get("chips", 0))}
    if phase == "blind":
        rr = gs["round_resets"]
        order = ["Small", "Big", "Boss"]
        cur = gs.get("blind_on_deck") or "Small"
        base = game.ANTE_BASE[min(ante, len(game.ANTE_BASE) - 1)]
        tags = rr.get("blind_tags") or {}
        s["blinds"] = [{"slot": sl, "name": rr["blind_choices"][sl], "target": int(base * _blind_mult(sl, rr["blind_choices"][sl])),
                        "tag": tags.get(sl)} for sl in order[order.index(cur):]]
        s["can_skip"] = any(isinstance(a, SkipBlind) for a in get_legal_actions(gs))
    if phase == "shop":
        s["shop"] = ([_item(c, ("cards", i)) for i, c in enumerate(gs.get("shop_cards", []))]
                     + [_item(c, ("vouchers", i)) for i, c in enumerate(gs.get("shop_vouchers", []))]
                     + [_item(c, ("boosters", i)) for i, c in enumerate(gs.get("shop_boosters", []))])
        s["reroll_cost"] = cr.get("reroll_cost", 5)
    if phase == "pack":
        s["pack"] = [_pack_item(c, i, gs) for i, c in enumerate(gs.get("pack_cards", []))]
        s["pack_picks"] = gs.get("pack_choices_remaining", 1)
    return s


def to_engine(s: dict, a: dict):
    t = a["t"]
    hidx = s.get("_hidx") or []
    remap = lambda idxs: tuple(hidx[i] if i < len(hidx) else i for i in idxs)
    tg = remap(a["targets"]) if a.get("targets") else None
    if t == "select_blind":
        return SelectBlind()
    if t == "skip_blind":
        return SkipBlind()
    if t == "play":
        # the real game scores the selection left to right as it sits in the hand, not in click order
        # (Hanging Chad / Photograph / Mult-vs-xMult order; seed X8AXHXRD: real 13 rounds vs sim 7)
        return PlayHand(tuple(sorted(remap(a["cards"]))))
    if t == "discard":
        return Discard(tuple(sorted(remap(a["cards"]))))
    if t == "use":
        return UseConsumable(a["slot"], tg)
    if t == "buy":
        area, i = a["item"]["src"]
        return {"cards": lambda: _buy(i), "vouchers": lambda: RedeemVoucher(i),
                "boosters": lambda: OpenBooster(i)}[area]()
    if t == "reroll":
        return Reroll()
    if t == "sell_joker":
        return SellCard("jokers", a["slot"])
    if t == "leave":
        return NextRound()
    if t == "pick":
        return PickPackCard(a["item"]["src"][1], tg)
    if t == "skip_pack":
        return SkipPack()
    raise ValueError(t)


def _buy(i):
    from jackdaw.engine.actions import BuyCard
    return BuyCard(i)


def _profile_locked() -> set[str]:
    """Centers still locked on the active Balatro profile (meta.jkr). The real game never
    offers them (common_events.lua: v.unlocked ~= false or rarity 4); jackdaw assumes a
    fully unlocked profile, so filter them out to match the user's game."""
    import json as _json
    import os
    import re
    import zlib
    from pathlib import Path
    base = Path(os.environ.get("APPDATA", "")) / "Balatro"
    try:
        settings = zlib.decompress((base / "settings.jkr").read_bytes(), -15).decode("utf8", "ignore")
        m = re.search(r'\["profile"\]=(\d+)', settings)
        meta = zlib.decompress((base / (m.group(1) if m else "1") / "meta.jkr").read_bytes(), -15).decode("utf8", "ignore")
    except OSError:
        return set()
    sec = re.search(r'\["unlocked"\]=\{(.*?)\}', meta, re.S)
    unlocked = set(re.findall(r'\["(\w+)"\]=true', sec.group(1))) if sec else set()
    from jackdaw.engine import data as jd
    centers = _json.loads((Path(jd.__file__).parent / "centers.json").read_text(encoding="utf8"))
    return {k for k, v in centers.items()
            if v.get("unlocked") is False and k not in unlocked and v.get("rarity") != 4}


LOCKED = _profile_locked()


def _install_unlock_filter() -> None:
    from jackdaw.engine import pools
    if getattr(pools._filter_key, "_laya_unlocks", False):
        return
    orig = pools._filter_key

    def _filter_key(*a, **kw):
        if kw.get("key", a[0] if a else None) in LOCKED:
            return pools.UNAVAILABLE
        return orig(*a, **kw)

    _filter_key._laya_unlocks = True
    pools._filter_key = _filter_key


_install_unlock_filter()


def _install_deck_insertion_fix() -> None:
    """Balatro's CardArea:emplace puts cards entering a deck-type area at index 1 (the
    bottom; draws take from the top), so a card bought from a Standard pack is not drawn
    next. jackdaw appends instead; move new deck cards to the bottom, last-added first."""
    if getattr(engine, "_laya_deck_fix", False):
        return
    for name in ("_handle_pick_pack_card", "_resolve_create_descriptors"):
        orig = getattr(engine, name)

        def wrapped(gs, *a, _orig=orig, **kw):
            before = {id(c) for c in gs.get("deck", [])}
            out = _orig(gs, *a, **kw)
            deck = gs.get("deck", [])
            new = [c for c in deck if id(c) not in before]
            if new:
                deck[:] = list(reversed(new)) + [c for c in deck if id(c) in before]
            return out

        setattr(engine, name, wrapped)
    engine._laya_deck_fix = True


_install_deck_insertion_fix()


# Boss forcing for sim/real twins. The real game (under Steamodded) draws the same 'boss'
# pseudoseed as jackdaw yet shows a different boss; everything else (cards, tags, shops)
# matches bit-for-bit. A twin replay therefore takes the bosses the real run showed.
# Keyed by the per-run bosses_used dict, since get_new_boss receives no other handle.
_FORCED: dict[int, list[str]] = {}
_orig_get_new_boss = None


def _install_boss_hook() -> None:
    global _orig_get_new_boss
    from jackdaw.engine import blind as jblind
    if _orig_get_new_boss is not None:
        return
    _orig_get_new_boss = jblind.get_new_boss

    def get_new_boss(ante, bosses_used, rng, **kw):
        key = _orig_get_new_boss(ante, bosses_used, rng, **kw)  # still advances the 'boss' stream
        queue = _FORCED.get(id(bosses_used))
        if queue:
            forced = queue.pop(0)
            if forced and forced != key:
                bosses_used[key] = bosses_used.get(key, 1) - 1
                bosses_used[forced] = bosses_used.get(forced, 0) + 1
                return forced
        return key

    jblind.get_new_boss = get_new_boss


class SimGame:
    """One simulated run. `pending()` -> canonical state needing a decision (or None when over)."""

    def __init__(self, seed: str, deck: str = "b_red", stake: int = 1, bosses: list[str] | None = None):
        self.seed = seed
        if bosses:
            # initialize_run creates bosses_used internally, so force through a pending slot
            _install_boss_hook()
            _FORCED[-1] = list(bosses)
            from jackdaw.engine import run_init as jri
            orig_init = jri.init_game_object

            def init_game_object():
                g = orig_init()
                _FORCED[id(g["bosses_used"])] = _FORCED.pop(-1)
                return g

            jri.init_game_object = init_game_object
            try:
                self.gs = initialize_run(deck, stake, seed)
            finally:
                jri.init_game_object = orig_init
        else:
            self.gs = initialize_run(deck, stake, seed)
        self.rounds_won = 0
        self.max_ante = 1
        self.illegal = 0
        self.steps = 0
        self.selected: list[int] = []  # raw mode: hand cards clicked so far in this decision
        self.deselects = 0
        self.pending_pick: int | None = None  # pack slot of a targeted card awaiting its targets
        self.pick_tries = 0

    @property
    def over(self) -> bool:
        # a won run continues into endless (the engine keeps advancing antes after `won`)
        return _val(self.gs["phase"]) == "game_over" or self.steps > (20000 if game.RAW else 6000)

    def pending(self) -> dict | None:
        while not self.over:
            ph = _val(self.gs["phase"])
            if ph == "round_eval":
                self.rounds_won += 1
                # the game clears Cerulean Bell's flag in end_round; jackdaw keeps it on the card for later rounds
                for area in ("deck", "hand", "play", "discard_pile"):
                    for c in self.gs.get(area, []):
                        c.ability.pop("forced_selection", None)
                self.gs = engine.step(self.gs, CashOut())
                continue
            s = canonical(self.gs)
            if s is None:
                raise RuntimeError(f"unhandled phase {ph}")
            self.max_ante = max(self.max_ante, s["ante"])
            if game.RAW and s.get("hand"):
                if s["phase"] == "hand":  # Cerulean Bell: the forced card starts (and stays) selected
                    forced = [i for i, c in enumerate(s["hand"]) if c.get("forced") and i not in self.selected]
                    self.selected = (forced + self.selected)[:5]
                s["selected"] = list(self.selected)
                s["sel_budget"] = game.SELECT_BUDGET - self.deselects
            if game.RAW and s["phase"] == "pack":
                s["pending_pick"] = self.pending_pick
                s["pick_tries"] = self.pick_tries
            return s
        return None

    def apply(self, s: dict, a: dict) -> bool:
        self.steps += 1
        if a["t"] == "select":  # a click changes only the selection, not the engine state
            self.selected.append(a["card"])
            return True
        if a["t"] == "deselect":
            self.selected.remove(a["card"])
            self.deselects += 1
            return True
        if a["t"] in ("choose_pick", "cancel_pick"):  # local: opens / closes target selection
            self.pending_pick = a["slot"] if a["t"] == "choose_pick" else None
            self.pick_tries += a["t"] == "choose_pick"
            self.selected, self.deselects = [], 0
            return True
        try:
            self.gs = engine.step(self.gs, to_engine(s, a))
        except (IllegalActionError, IndexError, KeyError, ValueError):
            self.illegal += 1
            return False
        self.selected, self.deselects, self.pending_pick = [], 0, None
        if a["t"] in ("skip_pack", "pick"):
            self.pick_tries = 0  # each pick (a Mega pack's next one, a queued tag pack) gets fresh tries
        return True
