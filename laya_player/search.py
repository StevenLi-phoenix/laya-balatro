"""Simulator search for hand decisions: training labels for expert iteration.

Stage 2's RL judges a hand decision only by the run's final round count, and a seed whose games
all die in Ante 1-2 has no better sibling to learn from. This search gives every hand decision a
direct target instead. It sees what a player sees (hand, deck composition, jokers, levels, blind,
hands and discards left), never the draw order or the RNG. Each rollout reshuffles the deck and
reseeds the RNG (the same K shuffles for every candidate). It then applies a candidate play or
discard in the real engine and finishes the round with a fast greedy continuation. A candidate's
value is P(blind cleared) plus a little per hand to spare; every candidate within noise of the best
is returned. Laya never sees these values: they only become click labels (simloop --search).

  python -m laya_player.search --bench 32     # search vs greedy hand play, same seeds, scripted shop
"""
from __future__ import annotations

import argparse
import copy
import itertools
import pickle
import random
import statistics
import time
from collections import Counter

from jackdaw.engine import game as engine
from jackdaw.engine.actions import Discard, PlayHand
from jackdaw.engine.game import IllegalActionError
from jackdaw.engine.rng import PseudoRandom
from jackdaw.engine.scoring import score_hand

from .sim import _val

SUITS = ("Spades", "Hearts", "Clubs", "Diamonds")
ORDER = ["Flush Five", "Flush House", "Five of a Kind", "Straight Flush", "Four of a Kind", "Full House",
         "Flush", "Straight", "Three of a Kind", "Two Pair", "Pair", "High Card"]
WIN, HAND_BONUS, LOSS_PARTIAL = 1.0, 0.02, 0.4


# --------------------------------------------------------------------------- fast approximate scoring

def _feat(c, smeared: bool) -> tuple:
    """(rank, suit, chips, mult, xmult) of a playing card as it would score; rank 0 = Stone, suit 4 = Wild."""
    ck = c.center_key or "c_base"
    ab = c.ability if isinstance(c.ability, dict) else {}
    ed = c.edition if isinstance(c.edition, dict) else {}
    stone = ck == "m_stone"
    chips = (50 if stone else c.base.nominal) + ab.get("perma_bonus", 0) + 30 * (ck == "m_bonus") + 50 * bool(ed.get("foil"))
    mult = 4 * (ck == "m_mult") + 10 * bool(ed.get("holo"))
    x = (2.0 if ck == "m_glass" else 1.0) * (1.5 if ed.get("polychrome") else 1.0)
    rep = 2 if c.seal == "Red" else 1
    if c.debuff:  # still forms the hand, adds nothing
        chips, mult, x = 0, 0, 1.0
    if stone:
        return 0, -1, chips * rep, mult * rep, x ** rep
    s = 4 if ck == "m_wild" else SUITS.index(_val(c.base.suit))
    if smeared and s < 4:
        s = 0 if s in (0, 2) else 1
    return c.get_id(), s, chips * rep, mult * rep, x ** rep


def _run(ranks: set[int], need: int, shortcut: bool) -> list[int] | None:
    """Ranks forming a straight of `need` cards (Ace high or low; Shortcut allows one-rank gaps)."""
    rs = sorted(ranks | ({1} if 14 in ranks else set()))
    best = None
    for i in range(len(rs)):
        run = [rs[i]]
        for r in rs[i + 1:]:
            if r - run[-1] == 1 or (shortcut and r - run[-1] == 2):
                run.append(r)
            elif r != run[-1]:
                break
        if len(run) >= need and (best is None or run[-1] > best[-1]):
            best = run
    return [14 if r == 1 else r for r in best] if best else None


def classify(cs: list[tuple], ff: bool, sc: bool) -> tuple[str, list[int]]:
    """Hand type and scoring positions of a played set of feature tuples (Four Fingers / Shortcut aware)."""
    need = 4 if ff else 5
    pos = [i for i, c in enumerate(cs) if c[0]]
    cnt = Counter(cs[i][0] for i in pos)
    stones = [i for i, c in enumerate(cs) if not c[0]]
    flush = None
    if len(pos) >= need:
        for s in range(4):
            fc = [i for i in pos if cs[i][1] in (s, 4)]
            if len(fc) >= need:
                flush = fc
                break
    run = _run(set(cnt), need, sc) if len(cnt) >= need else None
    straight = None
    if run:
        straight, used = [], set()
        for i in pos:
            if cs[i][0] in run and cs[i][0] not in used:
                used.add(cs[i][0])
                straight.append(i)
    groups = sorted(cnt.values(), reverse=True) + [0, 0]
    by = lambda k: [i for i in pos if cnt[cs[i][0]] >= k]
    if groups[0] >= 5:
        ht, sco = ("Flush Five" if flush else "Five of a Kind"), pos
    elif groups[0] == 3 and groups[1] >= 2 and flush:
        ht, sco = "Flush House", pos
    elif flush and straight:
        ht, sco = "Straight Flush", sorted(set(flush) | set(straight))
    elif groups[0] == 4:
        ht, sco = "Four of a Kind", by(4)
    elif groups[0] == 3 and groups[1] >= 2:
        ht, sco = "Full House", pos
    elif flush:
        ht, sco = "Flush", flush
    elif straight:
        ht, sco = "Straight", straight
    elif groups[0] == 3:
        ht, sco = "Three of a Kind", by(3)
    elif groups[0] == 2 and groups[1] == 2:
        ht, sco = "Two Pair", by(2)
    elif groups[0] == 2:
        ht, sco = "Pair", by(2)
    else:
        ht = "High Card"
        sco = [max(pos, key=lambda i: cs[i][0])] if pos else []
    return ht, sco + stones


class Ctx:
    """Per-state constants: level table, joker flags, per-hand-type joker factor (exact / approximate)."""

    def __init__(self, gs: dict, factor: dict[str, float] | None = None):
        names = {j.ability.get("name") for j in gs.get("jokers", []) if not j.debuff}
        self.ff, self.sc = "Four Fingers" in names, "Shortcut" in names
        self.smeared, self.splash = "Smeared Joker" in names, "Splash" in names
        hl = gs["hand_levels"]
        self.lv = {h: (hl.get_state(h).chips, hl.get_state(h).mult) for h in ORDER}
        self.factor = factor or {}
        b = gs["blind"]
        self.psychic = getattr(b, "name", "") == "The Psychic" and not getattr(b, "disabled", False)

    def approx(self, cs: list[tuple]) -> tuple[float, str]:
        ht, sco = classify(cs, self.ff, self.sc)
        if self.splash:
            sco = range(len(cs))
        ch, mu = self.lv[ht]
        x = 1.0
        for i in sco:
            ch += cs[i][2]
            mu += cs[i][3]
            x *= cs[i][4]
        return ch * mu * x * self.factor.get(ht, self.factor.get("*", 1.0)), ht


def _subsets(n: int, forced: list[int], psychic: bool):
    sizes = (5,) if psychic and n >= 5 else range(1, 6)
    for k in sizes:
        for sub in itertools.combinations(range(n), k):
            if all(f in sub for f in forced):
                yield sub


def _forced(hand) -> list[int]:
    return [i for i, c in enumerate(hand) if isinstance(c.ability, dict) and c.ability.get("forced_selection")]


# --------------------------------------------------------------------------- exact scoring (no side effects)

def _score_ctx(gs: dict) -> dict:
    """The derived values _handle_play_hand puts on game_state before score_hand."""
    cr = gs["current_round"]
    g = dict(gs)
    g.update(hands_left=cr.get("hands_left", 0) - 1, current_round_hands_played=cr.get("hands_played", 0),
             discards_left=cr.get("discards_left", 0), discards_used=cr.get("discards_used", 0),
             money=gs.get("dollars", 0), deck_cards_remaining=len(gs.get("deck", [])))
    allc = gs.get("deck", []) + gs.get("hand", []) + gs.get("discard_pile", [])
    g["playing_cards_count"] = len(allc)
    g["stone_tally"] = sum(1 for c in allc if c.center_key == "m_stone")
    g["steel_tally"] = sum(1 for c in allc if c.center_key == "m_steel")
    g["enhanced_card_count"] = sum(1 for c in allc if c.center_key not in ("", "c_base", None))
    g["mail_card_id"] = cr.get("mail_card", {}).get("id")
    g["idol_card"] = cr.get("idol_card")
    g["ancient_suit"] = cr.get("ancient_card", {}).get("suit")
    g["consumable_usage_tarot"] = gs.get("consumable_usage_total", {}).get("tarot", 0)
    return g


def exact(gs: dict, sub: tuple[int, ...], sctx: dict, rng_seed: str) -> tuple[int, str]:
    """Score of playing hand[sub] through jackdaw's full pipeline, on copies (jokers, cards, levels,
    blind) and with a fresh RNG, so nothing in `gs` changes and no future luck is read."""
    J, H, L, B = copy.deepcopy((gs["jokers"], gs["hand"], gs["hand_levels"], gs["blind"]))
    s = set(sub)
    played = [H[i] for i in sub]
    held = [c for i, c in enumerate(H) if i not in s]
    r = score_hand(played, held, J, L, B, PseudoRandom(rng_seed),
                   probabilities_normal=gs.get("probabilities", {}).get("normal", 1), game_state=dict(sctx),
                   back_key=gs.get("selected_back_key"), blind_chips=0)
    return int(r.total), r.hand_type


# --------------------------------------------------------------------------- greedy continuation

def _keep_sets(fs: list[tuple], ctx: Ctx) -> list[tuple[str, set[int]]]:
    """Cards worth keeping for a discard: a suit (flush draw), a rank window (straight draw), the kinds."""
    out = []
    need = 4 if ctx.ff else 5
    nsuits = 2 if ctx.smeared else 4
    for s in range(nsuits):
        k = {i for i, c in enumerate(fs) if c[0] and c[1] in (s, 4)}
        if len(k) >= 2:
            out.append((f"flush{len(k)}", k))
    ranks = {c[0] for c in fs if c[0]}
    span = need + (need - 1 if ctx.sc else 0)
    for lo in range(1, 15 - need + 1):
        win = {r for r in range(lo, lo + span) if (r if r > 1 else 14) in ranks}
        if len(win) >= 3:
            want = {(r if r > 1 else 14) for r in win}
            k, used = set(), set()
            for i, c in enumerate(fs):
                if c[0] in want and c[0] not in used:
                    used.add(c[0])
                    k.add(i)
            out.append((f"straight{len(k)}", k))
    cnt = Counter(c[0] for c in fs if c[0])
    kinds = {i for i, c in enumerate(fs) if c[0] and cnt[c[0]] >= 2}
    if kinds:
        out.append((f"kinds{len(kinds)}", kinds))
    return out


def _discard_for(fs: list[tuple], keep: set[int], forced: list[int]) -> tuple[int, ...]:
    """Discard up to 5 cards outside `keep`, lowest chips first; a forced card always goes along."""
    rest = sorted((i for i in range(len(fs)) if i not in keep and i not in forced), key=lambda i: fs[i][2])
    d = list(forced) + rest
    return tuple(sorted(d[:5]))


def _best_plays(gs: dict, ctx: Ctx, sctx: dict, top: int, seed: str) -> list[tuple[int, tuple[int, ...]]]:
    hand = gs["hand"]
    fs = [_feat(c, ctx.smeared) for c in hand]
    ranked = sorted(((ctx.approx([fs[i] for i in sub])[0], sub) for sub in _subsets(len(hand), _forced(hand), ctx.psychic)),
                    reverse=True)
    out = []
    for _, sub in ranked[:top]:
        out.append((exact(gs, sub, sctx, seed)[0], sub))
    if out and max(out)[0] == 0:  # The Eye / The Mouth / The Psychic blocked the obvious plays: look further
        out += [(exact(gs, sub, sctx, seed)[0], sub) for _, sub in ranked[top:top + 12]]
    return sorted(out, reverse=True)


def greedy(gs: dict, ctx: Ctx, seed: str = "g"):
    """Fast continuation policy: play the best hand if it clears or keeps pace, else discard toward a
    flush/straight/kinds draw."""
    cr = gs["current_round"]
    need = int(gs["blind"].chips) - gs.get("chips", 0)
    hl, dl = cr.get("hands_left", 0), cr.get("discards_left", 0)
    plays = _best_plays(gs, ctx, _score_ctx(gs), 3, seed)
    best, sub = plays[0] if plays else (0, (0,))
    if best >= need or hl <= 1 or dl <= 0 or best * hl >= need:
        return PlayHand(sub)
    hand = gs["hand"]
    fs = [_feat(c, ctx.smeared) for c in hand]
    ks = dict(_keep_sets(fs, ctx))
    need_n = 4 if ctx.ff else 5
    pick = None
    for name, k in sorted(ks.items(), key=lambda kv: -len(kv[1])):
        if name.startswith(("flush", "straight")) and len(k) >= need_n - 1:
            pick = k
            break
    if pick is None:
        pick = next((k for name, k in ks.items() if name.startswith("kinds")), None)
    if pick is None:
        pick = set(sorted(range(len(fs)), key=lambda i: -fs[i][2])[:2])
    d = _discard_for(fs, pick, _forced(hand))
    return Discard(d) if d else PlayHand(sub)


def _outcome(g: dict, target: int) -> float:
    if _val(g["phase"]) == "round_eval":
        return WIN + HAND_BONUS * g["current_round"].get("hands_left", 0)
    return LOSS_PARTIAL * min(1.0, g.get("chips", 0) / max(1, target))


def rollout(root: dict, action, k: int, factor: dict) -> float:
    """Determinization k: reshuffle the deck, reseed the RNG, apply `action`, finish the round greedily."""
    g = copy.deepcopy(root)
    random.Random(k).shuffle(g["deck"])
    g["rng"] = PseudoRandom(f"LAYA{k:04d}")
    target = int(g["blind"].chips)
    try:
        g = engine.step(g, action)
        for step in range(40):
            if _val(g["phase"]) != "selecting_hand":
                break
            g = engine.step(g, greedy(g, Ctx(g, factor), f"g{k}.{step}"))
    except IllegalActionError:
        return 0.0
    return _outcome(g, target)


# --------------------------------------------------------------------------- the search

def _factors(gs: dict, ctx: Ctx, sctx: dict, scored: list[tuple[int, str, tuple]]) -> dict[str, float]:
    """exact / approximate score per hand type, from the root's best play of each type: the jokers'
    effect the fast scorer leaves out. Types not in hand take the median."""
    fs = [_feat(c, ctx.smeared) for c in gs["hand"]]
    best: dict[str, tuple[int, tuple]] = {}
    for tot, ht, sub in scored:
        if tot > best.get(ht, (-1,))[0]:
            best[ht] = (tot, sub)
    f = {}
    for ht, (tot, sub) in best.items():
        ap, aht = ctx.approx([fs[i] for i in sub])
        if aht == ht and ap > 0 and tot > 0:
            f[ht] = tot / ap
    f["*"] = statistics.median(f.values()) if f else 1.0
    return f


def search(gs: dict, k1: int = 6, k2: int = 10, top: int = 5, max_disc: int = 12) -> dict | None:
    """Best hand moves at `gs` (selecting_hand): {"targets": [(kind, engine idx tuple)], "values": {...}}.
    None when the hand shows face-down cards (the search would see what the player cannot)."""
    hand = gs["hand"]
    if any(getattr(c, "facing", "front") == "back" for c in hand):
        return None
    cr = gs["current_round"]
    need = int(gs["blind"].chips) - gs.get("chips", 0)
    hl, dl = cr.get("hands_left", 0), cr.get("discards_left", 0)
    ctx, sctx = Ctx(gs), _score_ctx(gs)
    forced = _forced(hand)
    scored = []
    for sub in _subsets(len(hand), forced, ctx.psychic):
        tot, ht = exact(gs, sub, sctx, "root")
        scored.append((tot, ht, sub))
    clear = [("play", sub) for tot, _, sub in scored if tot >= need]
    if clear and hl > 0:  # any clearing play wins the round with the same hands to spare
        return {"targets": clear, "values": {}, "kind": "clear"}
    factor = _factors(gs, ctx, sctx, scored)
    ctx.factor = factor
    fs = [_feat(c, ctx.smeared) for c in hand]
    # plays: the best few distinct scores, each alone and padded with the lowest cards (a free discard)
    cands: list[tuple[str, tuple[int, ...]]] = []
    seen_core = []
    for tot, ht, sub in sorted(scored, reverse=True):
        if len(seen_core) >= 4:
            break
        if any(set(c) <= set(sub) for c in seen_core):  # an earlier core plus kickers
            continue
        seen_core.append(sub)
        cands.append(("play", sub))
        pad = sorted((i for i in range(len(hand)) if i not in sub), key=lambda i: fs[i][2])[:5 - len(sub)]
        if pad and not ctx.psychic:
            cands.append(("play", tuple(sorted(sub + tuple(pad)))))
    if dl > 0:
        keeps = _keep_sets(fs, ctx) + [("play", set(sub)) for sub in seen_core]
        discs = {_discard_for(fs, k, forced) for _, k in keeps}
        low = sorted((i for i in range(len(hand)) if i not in forced), key=lambda i: fs[i][2])
        discs |= {tuple(sorted((forced + low)[:n])) for n in (1, 2, 3, 5)}
        discs.discard(())
        dl_sorted = sorted(discs, key=lambda d: (-len(d), d))[:max_disc]
        cands += [("discard", d) for d in dl_sorted]
    cands = list(dict.fromkeys(cands))
    act = lambda c: PlayHand(c[1]) if c[0] == "play" else Discard(c[1])
    vals = {c: [rollout(gs, act(c), k, factor) for k in range(k1)] for c in cands}
    lead = sorted(cands, key=lambda c: -statistics.mean(vals[c]))[:top]
    for c in lead:
        vals[c] += [rollout(gs, act(c), k, factor) for k in range(k1, k1 + k2)]
    best = max(lead, key=lambda c: statistics.mean(vals[c]))
    ok = [best]
    for c in lead:
        if c == best:
            continue
        d = [a - b for a, b in zip(vals[best], vals[c])]
        se = statistics.pstdev(d) / len(d) ** 0.5
        if statistics.mean(d) <= max(0.02, se):
            ok.append(c)
    return {"targets": ok, "values": {f"{k} {v}": round(statistics.mean(x), 3) for (k, v), x in vals.items()},
            "kind": "search"}


def search_blob(blob: bytes) -> dict | None:
    """Process-pool entry: the state arrives pickled (a snapshot taken when the turn began)."""
    return search(pickle.loads(blob))


# --------------------------------------------------------------------------- benchmark

def _scripted(s: dict) -> dict:
    """Fixed non-hand policy for the benchmark: play every blind, buy the cheapest affordable joker."""
    if s["phase"] == "blind":
        return {"t": "select_blind"}
    if s["phase"] == "pack":
        return {"t": "skip_pack"}
    if len(s["jokers"]) < s["joker_slots"]:
        js = [it for it in s["shop"] if it["kind"] == "joker" and it["cost"] <= s["money"]]
        if js:
            return {"t": "buy", "item": min(js, key=lambda it: it["cost"])}
    return {"t": "leave"}


def bench_one(args: tuple[str, str]) -> dict:
    from .sim import SimGame
    seed, mode = args
    g = SimGame(seed)
    t_search, n_search = 0.0, 0
    while True:
        s = g.pending()
        if s is None:
            break
        if s["phase"] != "hand":
            if not g.apply(s, _scripted(s)):
                g.apply(s, {"t": "leave"} if s["phase"] == "shop" else {"t": "skip_pack"})
            continue
        a = None
        if mode == "search":
            t = time.time()
            r = search(g.gs)
            t_search += time.time() - t
            n_search += 1
            if r:
                kind, sub = r["targets"][0]
                a = PlayHand(sub) if kind == "play" else Discard(sub)
        if a is None:
            a = greedy(g.gs, Ctx(g.gs))
        g.steps += 1
        g.gs = engine.step(g.gs, a)
        if g.steps > 3000:
            break
    return {"seed": seed, "mode": mode, "rounds": g.rounds_won, "search_s": t_search, "n": n_search}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", type=int, default=16, help="seeds to play with each hand policy")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    from concurrent.futures import ProcessPoolExecutor
    from .simloop import rand_seeds
    seeds = rand_seeds(args.bench)
    jobs = [(s, m) for s in seeds for m in ("greedy", "search")]
    t0 = time.time()
    with ProcessPoolExecutor(args.workers) as ex:
        res = list(ex.map(bench_one, jobs))
    for m in ("greedy", "search"):
        r = [x for x in res if x["mode"] == m]
        rounds = [x["rounds"] for x in r]
        n = sum(x["n"] for x in r)
        per = sum(x["search_s"] for x in r) / max(1, n)
        print(f"{m:7s} mean {statistics.mean(rounds):.2f} median {statistics.median(rounds)} "
              f"{sorted(rounds)}" + (f" | {n} searches, {per:.2f}s each" if n else ""))
    print(f"wall {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
