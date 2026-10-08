"""System 2 for Laya (Stage 3): computed consequences written next to the raw click options.

Laya scores options in one forward pass; it cannot work out chips x mult through five jokers, hand
levels and enhancements, or the odds of a draw. With LAYA_CALC=1 every hand-phase click says what it
leads to, computed only from what a player can see:

  select / deselect a card  -> the new selection's poker hand and exact score (jackdaw's scoring
                               pipeline: all jokers, the boss) and whether that clears the blind
  play selected             -> the same for the current selection, plus hands left afterwards
  discard selected          -> cards drawn, and the chance the kept cards then make a flush or a
                               straight (deck composition, never its order)

Nothing ranks the options or marks one as best; Laya still chooses. Face-down cards are unknown: no
score involving them, and they are left out of held-card effects. Random effects (Misprint,
Bloodstone, Space Joker, Lucky cards) are averaged over a few fixed draws and shown as a range.
"""
from __future__ import annotations

import copy
import hashlib
import itertools
import math
import os
import pickle
import re

import numpy as np

from . import game

ON = os.environ.get("LAYA_CALC", "0") == "1"
RANDOM_JOKERS = {"j_misprint", "j_bloodstone", "j_space"}
SAMPLES = 8  # fixed draws for a score with random effects
STRAIGHT_DRAWS = 1000  # Monte Carlo draws for straight odds (seeded by the state: same text in sim and real)


# --------------------------------------------------------------------------- exact scores

def _copy2(v):
    """Two levels deep: ability values are numbers, strings or small dicts/lists of them."""
    if isinstance(v, dict):
        return {k: (x.copy() if isinstance(x, (dict, list)) else x) for k, x in v.items()}
    if isinstance(v, list):
        return [x.copy() if isinstance(x, (dict, list)) else x for x in v]
    return v


def _clone(c):
    """Card copy for one scoring pass: its own ability/edition/base (what scoring may change), shared
    immutables. copy.deepcopy of a whole hand + jokers cost ~2.4 ms, ten times the scoring itself."""
    d = copy.copy(c)
    d.ability = {k: _copy2(v) for k, v in c.ability.items()} if isinstance(c.ability, dict) else copy.deepcopy(c.ability)
    d.edition = copy.copy(c.edition)
    d.base = copy.copy(c.base)
    return d


def _exact(gs: dict, eng: tuple[int, ...], held_ok: set[int], seeds: list[str], sctx: dict | None = None) -> list:
    """Score results of playing hand[eng] (engine indices, left to right) on copies: nothing in gs changes."""
    from jackdaw.engine.rng import PseudoRandom
    from jackdaw.engine.scoring import score_hand

    if sctx is None:
        from .search import _score_ctx
        sctx = _score_ctx(gs)
    out = []
    for sd in seeds:
        J = [_clone(j) for j in gs["jokers"]]
        H = [_clone(c) for c in gs["hand"]]
        L, B = copy.deepcopy((gs["hand_levels"], gs["blind"]))
        played = [H[i] for i in eng]
        held = [c for i, c in enumerate(H) if i not in eng and i in held_ok]
        out.append(score_hand(played, held, J, L, B, PseudoRandom(sd),
                              probabilities_normal=gs.get("probabilities", {}).get("normal", 1),
                              game_state=dict(sctx), back_key=gs.get("selected_back_key"), blind_chips=0))
    return out


def _result(s: dict, gs: dict, sel: list[int], cache: dict) -> tuple | None:
    """(hand, mean score, low, high, share of draws that clear, blocked) of playing canonical cards `sel`."""
    if not sel or any(s["hand"][i].get("hidden") for i in sel):
        return None
    key = ("score", frozenset(sel))
    if key not in cache:
        hidx = s.get("_hidx") or list(range(len(s["hand"])))
        eng = tuple(sorted(hidx[i] for i in sel))
        hand = gs["hand"]
        held_ok = {i for i, c in enumerate(hand) if getattr(c, "facing", "front") != "back"}
        rnd = (any(j.center_key in RANDOM_JOKERS and not j.debuff for j in gs.get("jokers", []))
               or any(hand[i].center_key == "m_lucky" for i in eng))
        if "sctx" not in cache:  # the derived game values are the same for every option this turn
            from .search import _score_ctx
            cache["sctx"] = _score_ctx(gs)
        rs = _exact(gs, eng, held_ok, [f"LAYACALC{k}" for k in range(SAMPLES if rnd else 1)], cache["sctx"])
        need = s["blind"]["target"] - s["blind"]["scored"]
        tot = [int(r.total) for r in rs]
        cache[key] = (rs[0].hand_type, round(sum(tot) / len(tot)), min(tot), max(tot),
                      sum(t >= need for t in tot) / len(tot), bool(rs[0].debuffed))
    return cache[key]


def _say(res: tuple, need: int) -> str:
    hand, mean, lo, hi, p, blocked = res
    if blocked:
        return f"{hand}: not allowed by the boss, scores 0"
    score = str(mean) if lo == hi else f"~{mean} ({lo}-{hi})"
    if p >= 1:
        return f"{hand}, {score}: clears the blind"
    if p <= 0:
        return f"{hand}, {score}: {need - mean} short"
    return f"{hand}, {score}: clears {round(100 * p)}% of the time"


# --------------------------------------------------------------------------- draw odds

def _hyper_tail(N: int, m: int, n: int, k: int) -> float:
    """P(at least k of n cards drawn without replacement from N come from a group of m)."""
    if k <= 0:
        return 1.0
    tot = math.comb(N, n)
    return sum(math.comb(m, x) * math.comb(N - m, n - x) for x in range(k, min(m, n) + 1)) / tot if tot else 0.0


def _odds(s: dict, kept: list[dict], n: int) -> dict[str, float]:
    """Chance the kept cards plus n drawn ones hold a flush / a straight (Four Fingers, Smeared aware)."""
    dc, N = s.get("deck_counts"), s.get("deck_left") or 0
    if not dc or n <= 0 or N <= 0:
        return {}
    n = min(n, N)
    keys = {j.get("key") for j in s.get("jokers", [])}
    need = 4 if "j_four_fingers" in keys else 5
    groups = [("S", "C"), ("H", "D")] if "j_smeared" in keys else [("S",), ("H",), ("D",), ("C",)]
    known = [c for c in kept if not c.get("hidden") and c.get("enh") != "stone"]
    out = {}
    flush = 0.0
    for g in groups:
        k = sum(1 for c in known if c["suit"] in g or c.get("enh") == "wild")
        m = sum(dc["suits"].get(x, 0) for x in g)
        flush = max(flush, _hyper_tail(N, m, n, need - k))
    out["flush"] = flush
    # straight: draw ranks from the deck's rank counts (stones and unknowns as blanks), seeded by the state
    vals = {game.RANK_VAL[c["rank"]] for c in known if c["rank"] in game.RANK_VAL}
    pool = [game.RANK_VAL[r] for r, x in sorted(dc["ranks"].items()) if r in game.RANK_VAL for _ in range(x)]
    pool = np.array(pool + [0] * max(0, N - len(pool)), dtype=np.int64)
    seed = int.from_bytes(hashlib.sha256(f"{sorted(vals)}|{pool.tolist()}|{n}".encode()).digest()[:8], "little")
    rng = np.random.default_rng(seed)
    drawn = pool[np.argpartition(rng.random((STRAIGHT_DRAWS, len(pool))), n - 1, axis=1)[:, :n]]
    bits = np.bitwise_or.reduce(np.left_shift(1, drawn), axis=1) | sum(1 << v for v in vals)
    bits = (bits | ((bits >> 14) & 1) << 1) & ~1  # an Ace (bit 14) also counts low (bit 1); bit 0 = blank
    hit = np.zeros(STRAIGHT_DRAWS, dtype=bool)
    for r in range(1, 16 - need):
        w = sum(1 << (r + d) for d in range(need))
        hit |= (bits & w) == w
    hits = int(hit.sum())
    out["straight"] = hits / STRAIGHT_DRAWS
    return out


# --------------------------------------------------------------------------- notes on the options

def annotate(s: dict, acts: list[dict], gs: dict | None, cache: dict) -> None:
    """Write a computed consequence into each hand-phase click (`a["note"]`, shown by game.action_text).
    `gs` is the jackdaw game state in sync with `s` (simulator, or the real game's twin); `cache` must be
    emptied whenever the engine state changes (clicks alone do not change it)."""
    if not ON or s.get("phase") != "hand" or gs is None or not s.get("blind"):
        return
    sel = list(s.get("selected", []))
    need = s["blind"]["target"] - s["blind"]["scored"]
    hands_after = s.get("hands_left", 0) - 1
    for a in acts:
        t = a["t"]
        if t in ("select", "deselect"):
            nxt = sel + [a["card"]] if t == "select" else [i for i in sel if i != a["card"]]
            res = _result(s, gs, nxt, cache)
            if res:
                a["note"] = _say(res, need)
        elif t == "play" and a.get("raw"):
            res = _result(s, gs, sel, cache)
            if res:
                tail = "" if res[4] >= 1 else (f", {hands_after} hand{'s' * (hands_after != 1)} left after"
                                              if hands_after > 0 else ", last hand")
                a["note"] = _say(res, need) + tail
        elif t == "discard" and a.get("raw"):
            n = min(len(sel), s.get("deck_left") or 0)
            key = ("odds", frozenset(sel))
            if key not in cache:
                cache[key] = _odds(s, [c for i, c in enumerate(s["hand"]) if i not in sel], n)
            od = cache[key]
            txt = f"draw {n} of {s.get('deck_left', '?')}"
            parts = [f"{k} {round(100 * p)}%" for k, p in od.items() if p >= 0.01]
            a["note"] = txt + (": " + ", ".join(parts) if parts else "")


# --------------------------------------------------------------------------- real game: lockstep twin

class Twin:
    """The real run replayed move by move in the simulator. While both render the same prompt, the
    simulator's engine state computes the real game's notes, exactly as in training. On the first
    difference the twin stops (no notes for the rest of the run) and `lost` says where it parted."""

    def __init__(self, seed: str):
        from .sim import SimGame
        self.g, self.ts, self.lost = SimGame(seed), None, None
        self.synced = self.calls = self.repairs = 0
        self.aligned = self.unaligned = 0  # hand states matched card-for-card by sort_id / left positional
        self.undo = None  # state before the last move that touched face-down cards (see _redo_hidden)
        self.hidden_fixes = 0

    def _align(self, s: dict, ts: dict) -> bool:
        """Order the twin's hand like the real one, card for card. Identical-looking cards (three 10♥
        after The Sun) read the same in both prompts, but the real game acted on particular cards and
        Balatro shuffles by each card's sort_id: The Hanged Man on "10♥ #2/#3" destroyed other copies
        in the twin and the next deal differed (2026-10-08 01:19). The mod's id of a visible card is its
        sort_id. The absolute values differ (Balatro's counter also counts menu cards and never resets;
        jackdaw's is per process), but both create cards in the same order, so within a group of
        identical-looking cards the k-th smallest real id is the twin's k-th smallest sort_id."""
        real = [c.get("id") for c in s.get("hand", [])]
        if not real or len(real) != len(ts.get("hand", [])) or any(c.get("hidden") for c in s["hand"]):
            return False  # face-down cards carry session tokens, not sort_ids: positional as before
        groups: dict[str, list[int]] = {}
        for i, c in enumerate(ts["hand"]):
            groups.setdefault(repr(sorted(c.items())), []).append(i)
        dup = [g for g in groups.values() if len(g) > 1]
        if not dup:
            return False
        if any(not isinstance(real[i], int) for g in dup for i in g):
            self.unaligned += 1
            return False
        hand = self.g.gs.get("hand", [])
        hidx = list(ts["_hidx"])
        for g in dup:
            by_real = sorted(g, key=lambda i: real[i])
            by_twin = sorted((hidx[i] for i in g), key=lambda e: hand[e].sort_id)
            for i, e in zip(by_real, by_twin):
                ts["_hidx"][i] = e
        self.aligned += 1
        return True

    def _repair(self, s: dict) -> bool:
        """Take over from the real game what jackdaw computes differently and nothing else depends on.
        To Do List: the real game named another poker hand than jackdaw for the same purchase (real Four
        of a Kind, sim Straight Flush; first real run with notes to part); the hand only decides its $4."""
        fixed = False
        for rj, j in zip(s.get("jokers", []), self.g.gs.get("jokers", [])):
            if rj.get("key") == j.center_key == "j_todo_list":
                m = re.search(r"poker hand is an? (.+?),", rj.get("desc") or "")
                if m and m[1] in game.HAND_BASE and j.ability.get("to_do_poker_hand") != m[1]:
                    j.ability["to_do_poker_hand"] = m[1]
                    fixed = True
        b, gs = s.get("blind"), self.g.gs
        if s.get("phase") == "hand" and b and isinstance(b.get("scored"), int):
            # Float rounding of chips x mult: real 26089 vs sim 26090 at Big Blind 30000 (2026-10-08 02:20).
            # Take the real round score when the two differ by at most 2.
            mine = int(gs.get("chips", 0))
            if mine != b["scored"] and abs(mine - b["scored"]) <= 2:
                gs["chips"] = b["scored"]
                fixed = True
        self.repairs += fixed
        return fixed

    def _redo_hidden(self, s: dict) -> dict | None:
        """The last move played or discarded face-down cards (The House, Wheel, Fish, Mark). Their real
        identity is hidden from the runner (the mod sends session tokens), so the twin took the cards at
        the same positions and the next prompt differs (2026-10-08 01:38, The House: score 2904 real vs
        1664 sim). Redo the move from the saved state with every other choice of face-down cards and keep
        the first one that renders the real prompt."""
        blob, ts0, act = self.undo
        hidden = [i for i, c in enumerate(ts0["hand"]) if c.get("hidden")]
        chosen = [i for i in (act.get("cards") or act.get("targets") or []) if i in hidden]
        others = [i for i in hidden if i not in chosen]
        eng = [ts0["_hidx"][i] for i in hidden]
        want = game.state_text(s)
        for combo in itertools.combinations(eng, len(chosen)):
            rest = [e for e in eng if e not in combo]
            hidx = list(ts0["_hidx"])
            for i, e in zip(chosen + others, list(combo) + rest):
                hidx[i] = e
            if hidx == ts0["_hidx"]:
                continue  # the choice already made
            self.g.__dict__.update(pickle.loads(blob))
            alt = dict(ts0, _hidx=hidx)
            if not self.g.apply(alt, act):
                continue
            ts = self.g.pending()
            if ts is None:
                continue
            for k in ("selected", "sel_budget", "pending_pick", "pick_tries"):
                if k in s:
                    ts[k] = s[k]
            if ts["phase"] == s["phase"] and game.state_text(ts) == want:
                self.hidden_fixes += 1
                return ts
        return None

    def annotate(self, s: dict, cands: list[dict]) -> bool:
        if s.get("phase") == "hand":
            self.calls += 1
        if self.lost:
            return False
        ts = self.g.pending()
        if ts is not None and ts["phase"] == "blind" and s["phase"] == "blind":
            real = next((b["name"] for b in s.get("blinds", []) if b.get("slot") == "Boss"), None)
            mine = next((b["name"] for b in ts.get("blinds", []) if b.get("slot") == "Boss"), None)
            if real and mine and real != mine:  # the boss draw differs under Steamodded (see sim._FORCED)
                self.g.force_boss(real)
                ts = self.g.pending()
        if ts is None:
            self.lost = "simulator run ended"
            return False
        if self._repair(s):
            ts = self.g.pending()
        for k in ("selected", "sel_budget", "pending_pick", "pick_tries"):  # local click state lives in the runner
            if k in s:
                ts[k] = s[k]
        self.g.selected = list(s.get("selected", []))
        a, b = game.state_text(s), game.state_text(ts)
        if (a != b or ts["phase"] != s["phase"]) and self.undo is not None:
            fixed = self._redo_hidden(s)
            if fixed is not None:
                ts, b = fixed, a
                self.g.selected = list(s.get("selected", []))
        self.undo = None
        if a != b or ts["phase"] != s["phase"]:
            diff = next(((x, y) for x, y in zip(a.splitlines(), b.splitlines()) if x != y), (a[-80:], b[-80:]))
            self.lost = f"real {diff[0][:100]!r} vs sim {diff[1][:100]!r}"
            return False
        if s.get("hand"):
            self._align(s, ts)
        s["_hidx"] = ts["_hidx"]
        self.ts = ts
        if s["phase"] == "hand":
            self.synced += 1
        annotate(s, cands, self.g.gs, self.g.calc_cache)
        return True

    def apply(self, a: dict) -> None:
        """Mirror a game action the real game accepted (clicks are carried by `annotate`)."""
        if self.lost or self.ts is None or a["t"] in ("select", "deselect", "choose_pick", "cancel_pick"):
            return
        key = game.action_key(a)
        mine = next((x for x in game.candidates(self.ts) if game.action_key(x) == key), None)
        hand = self.ts.get("hand", [])
        if mine is not None and any(hand[i].get("hidden") for i in (mine.get("cards") or mine.get("targets") or [])
                                    if i < len(hand)):
            keep = {k: v for k, v in self.g.__dict__.items() if k != "calc_cache"}
            self.undo = (pickle.dumps(keep, pickle.HIGHEST_PROTOCOL), dict(self.ts), mine)
        if mine is None or not self.g.apply(self.ts, mine):
            self.lost = f"simulator could not mirror {key}"
        self.ts = None
