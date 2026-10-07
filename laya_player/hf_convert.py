"""Convert makemake/5k-balatro-games (V68 heuristic, Pylatro simulator) into Laya choice examples.

Each row's tokenized observation is decoded into the canonical state from `game.py`; the
teacher's flat action id is decoded into a canonical action, merged into the generated
candidate list (if the generator did not already propose it) and becomes the label.

  python -m laya_player.hf_convert --shards 0-19 --per-shard 4000 --out data/hf_train.jsonl
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import random
from pathlib import Path

import numpy as np

from . import game

REPO = "makemake/5k-balatro-games"
ROOT = Path(__file__).resolve().parent.parent / "data" / "5k"
TT = {"META": 1, "DECK": 2, "JOKER": 3, "VOUCHER": 4, "CONS": 5, "SHOP": 6, "BLIND": 7, "LEVEL": 8}
RANK_ID = {i + 1: r for i, r in enumerate(game.RANKS)}
SUIT_ID = {1: "D", 2: "C", 3: "H", 4: "S"}
HAND_NAMES = ["Flush Five", "Flush House", "Five of a Kind", "Straight Flush", "Four of a Kind", "Full House",
              "Flush", "Straight", "Three of a Kind", "Two Pair", "Pair", "High Card"]
SUBSETS5 = [c for k in range(1, 6) for c in itertools.combinations(range(16), k)]
SUBSETS3 = [c for k in range(1, 4) for c in itertools.combinations(range(16), k)]


def _fetch(name: str) -> Path:
    from huggingface_hub import hf_hub_download
    return Path(hf_hub_download(REPO, name, repo_type="dataset", local_dir=str(ROOT)))


class Decoder:
    def __init__(self):
        v = json.loads(_fetch("metadata/vocabulary.json").read_text(encoding="utf8"))
        self.actions = json.loads(_fetch("metadata/actions.json").read_text(encoding="utf8"))
        inv = lambda d: {i: k for k, i in d.items()}
        self.joker, self.cons, self.vouch = inv(v["joker_to_id"]), inv(v["consumable_to_id"]), inv(v["voucher_to_id"])
        self.boost, self.boss = inv(v["booster_to_id"]), inv(v["boss_to_id"])
        self.enh, self.ed, self.seal = inv(v["enhancement_to_id"]), inv(v["edition_to_id"]), inv(v["seal_to_id"])
        self.cons_set = v["consumable_set_to_id"]  # key -> 1 tarot, 2 planet, 3 spectral

    def card(self, tok) -> dict:
        enh = self.enh.get(int(tok[2]), "c_base")
        return {"rank": RANK_ID.get(int(tok[0]), "?"), "suit": SUIT_ID.get(int(tok[1]), "?"),
                "enh": None if enh == "c_base" else enh[2:], "ed": self.ed.get(int(tok[3])),
                "seal": self.seal.get(int(tok[4]))}

    def cons_kind(self, key: str) -> str:
        return {1: "tarot", 2: "planet", 3: "spectral"}.get(self.cons_set.get(key), "tarot")

    def item(self, tok) -> dict:
        kid, kind, cost = int(tok[0]), int(tok[1]), int(tok[2])
        if kind == 1:
            return {"kind": "joker", "key": self.joker.get(kid), "cost": cost, "ed": self.ed.get(int(tok[3]))}
        if kind == 2:
            key = self.cons.get(kid)
            return {"kind": self.cons_kind(key), "key": key, "cost": cost}
        if kind == 3:
            return {"kind": "voucher", "key": self.vouch.get(kid), "cost": cost}
        if kind == 4:
            return {"kind": "booster", "key": self.boost.get(kid), "cost": cost}
        # kind 5: playing card inside a standard pack -> rank col 9, suit col 10, enhancement col 5
        enh = self.enh.get(int(tok[5]), "c_base")
        return {"kind": "card", "cost": cost, "card": {
            "rank": RANK_ID.get(int(tok[9]), "?"), "suit": SUIT_ID.get(int(tok[10]), "?"),
            "enh": None if enh == "c_base" else enh[2:], "ed": None, "seal": None}}

    def decode(self, obs) -> dict:
        tok = np.asarray(obs["tokens"])
        tt = np.asarray(obs["token_types"])
        am = np.asarray(obs["attention_mask"])
        sc = np.asarray(obs["scalars"])
        rows = [(int(tt[j]), tok[j]) for j in np.nonzero(am)[0]]
        meta = [int(t[0]) for ty, t in rows if ty == TT["META"]]
        phase = {0: "blind", 1: "hand", 2: "shop", 3: "pack"}.get(meta[8], "hand")
        ante = meta[2]
        s = {"phase": phase, "ante": ante, "money": meta[0], "hands_left": meta[5], "discards_left": meta[6],
             "joker_slots": 5, "consumable_slots": 2}
        hand = sorted(((int(t[11]), self.card(t)) for ty, t in rows if ty == TT["DECK"] and t[5] == 0),
                      key=lambda x: x[0])
        s["hand"] = [c for _, c in hand] if phase in ("hand", "pack") else []
        s["deck_left"] = sum(1 for ty, t in rows if ty == TT["DECK"] and t[5] == 1)
        suits, ranks = {"S": 0, "H": 0, "D": 0, "C": 0}, {}
        for ty, t in rows:
            if ty == TT["DECK"] and t[5] == 1:
                c = self.card(t)
                if c["enh"] != "stone":
                    suits[c["suit"]] = suits.get(c["suit"], 0) + 1
                    ranks[c["rank"]] = ranks.get(c["rank"], 0) + 1
        s["deck_counts"] = {"suits": suits, "ranks": ranks}
        s["vouchers"] = [self.vouch.get(int(t[0])) for ty, t in rows if ty == TT["VOUCHER"] and self.vouch.get(int(t[0]))]
        s["jokers"] = [{"key": self.joker.get(int(t[0])), "ed": self.ed.get(int(t[2]))}
                       for ty, t in sorted(((ty, t) for ty, t in rows if ty == TT["JOKER"]), key=lambda x: int(x[1][5]))]
        s["consumables"] = [{"key": self.cons.get(int(t[1]))} for ty, t in rows if ty == TT["CONS"]]
        s["levels"] = {HAND_NAMES[int(t[0]) - 1]: [int(t[1]), int(t[2]), int(t[3])]
                       for ty, t in rows if ty == TT["LEVEL"] and 1 <= int(t[0]) <= 12}
        blind_idx, boss = divmod(meta[3], 100)
        if phase == "hand":
            names = ["bl_small", "bl_big", self.boss.get(boss, "boss")]
            s["blind"] = {"name": names[min(blind_idx, 2)], "target": int(round(math.exp(sc[3]) / 50) * 50),
                          "scored": max(0, int(round(math.exp(sc[8]) - 1)))}
        items = sorted(((int(t[4]), t) for ty, t in rows if ty == TT["SHOP"]), key=lambda x: x[0])
        if phase == "shop":
            s["shop"] = [self.item(t) for _, t in items]
            s["reroll_cost"] = int(round(math.exp(sc[25]))) if sc[25] else 5
        if phase == "pack":
            s["pack"] = [self.item(t) for _, t in items]
        if phase == "blind":
            bl = []
            base = game.ANTE_BASE[min(ante, len(game.ANTE_BASE) - 1)]
            for ty, t in rows:
                if ty == TT["BLIND"]:
                    slot = int(t[0])
                    name = ["bl_small", "bl_big", self.boss.get(int(t[3]), "boss")][min(slot, 2)]
                    bl.append({"slot": slot, "name": name, "target": int(base * int(t[2]) / 10)})
            s["blinds"] = [b for b in bl if b["slot"] >= min(blind_idx, 2)]
            s["can_skip"] = blind_idx < 2
        return s

    def action(self, aid: int, s: dict) -> dict | None:
        a = self.actions[str(aid)]
        t, i, d = a["action_type"], a["index"], a["detail"]
        if t == "blind_play":
            return {"t": "select_blind"}
        if t == "blind_skip":
            return {"t": "skip_blind"}
        if t == "play_subset":
            return {"t": "play", "cards": list(SUBSETS5[i])}
        if t == "discard_subset":
            return {"t": "discard", "cards": list(SUBSETS5[i]), "why": "teacher"}
        if t == "shop_buy":
            return {"t": "buy", "slot": i, "item": s["shop"][i]} if i < len(s.get("shop", [])) else None
        if t == "shop_reroll":
            return {"t": "reroll", "cost": s.get("reroll_cost", 5)}
        if t == "shop_sell_joker":
            j = s["jokers"][i] if i < len(s["jokers"]) else {}
            return {"t": "sell_joker", "slot": i, "key": j.get("key")}
        if t == "shop_leave":
            return {"t": "leave"}
        if t == "pack_claim":
            return {"t": "pick", "slot": i, "item": s["pack"][i]} if i < len(s.get("pack", [])) else None
        if t == "pack_skip":
            return {"t": "skip_pack"}
        if t.startswith("use_consumable"):
            if i >= len(s["consumables"]):
                return None
            key = s["consumables"][i]["key"]
            if t == "use_consumable_hand_subset":
                return {"t": "use", "slot": i, "key": key, "targets": list(SUBSETS3[d])}
            if t == "use_consumable_no_target":
                return {"t": "use", "slot": i, "key": key}
        return None  # sell consumable / joker-target consumables: not modelled


def make_example(s: dict, teacher: dict, rng: random.Random, max_opts: int = 14) -> dict | None:
    if teacher["t"] == "play":
        name, idx, est = game.estimate(s, [s["hand"][i] for i in teacher["cards"]])
        teacher.update(hand=name, est=est, kick=len(idx) < len(teacher["cards"]))
    cands = game.candidates(s)
    if s["phase"] == "pack" and teacher["t"] == "pick" and "targets" not in teacher:
        cands = [c for c in cands if not (c["t"] == "pick" and c["slot"] == teacher["slot"])]
    keys = [game.action_key(c) for c in cands]
    tk = game.action_key(teacher)
    if tk in keys:
        label = keys.index(tk)
    else:
        if len(cands) >= max_opts:
            cands = cands[: max_opts - 1]
        cands.append(teacher)
        label = len(cands) - 1
    if len(cands) < 2:
        return None
    order = list(range(len(cands)))
    rng.shuffle(order)
    opts = [game.action_text(s, cands[i]) for i in order]
    if len(set(opts)) != len(opts):
        return None
    return {"phase": s["phase"], "state": game.state_text(s), "options": opts, "label": order.index(label)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shards", default="0-19")
    ap.add_argument("--per-shard", type=int, default=4000)
    ap.add_argument("--out", default="data/hf_train.jsonl")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    import polars as pl
    lo, hi = (int(x) for x in args.shards.split("-"))
    dec, rng = Decoder(), random.Random(args.seed)
    # per-phase quotas keep shop/pack/blind decisions from being drowned by hand decisions
    share = {"hand": 0.55, "shop": 0.25, "pack": 0.12, "blind": 0.08}
    n_ok = n_skip = 0
    with open(args.out, "w", encoding="utf8") as f:
        for sh in range(lo, hi + 1):
            df = pl.read_parquet(_fetch(f"data/train-{sh:05d}-of-00020.parquet"))
            idx = list(range(len(df)))
            rng.shuffle(idx)
            got = {k: 0 for k in share}
            for i in idx:
                r = df.row(i, named=True)
                try:
                    s = dec.decode(r["obs"])
                    if got[s["phase"]] >= share[s["phase"]] * args.per_shard:
                        continue
                    a = dec.action(r["action"], s)
                    ex = make_example(s, a, rng) if a else None
                except (IndexError, KeyError, ValueError):
                    ex = None
                if ex is None:
                    n_skip += 1
                    continue
                ex.update(seed=r["seed"], step=r["step"], won=r["won"], ret=r["return_target"])
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
                got[s["phase"]] += 1
                n_ok += 1
                if sum(got.values()) >= args.per_shard:
                    break
            print(f"shard {sh}: {got}", flush=True)
    print(f"wrote {n_ok} examples, skipped {n_skip}")


if __name__ == "__main__":
    main()
