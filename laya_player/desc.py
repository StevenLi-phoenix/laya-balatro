"""Natural-language effect text for every Balatro object, built from the game's own data.

Laya reads text, so the prompt should say what a card does, not just its name. Text comes from
the game's English localization (extracted once from Balatro.exe into data/en-us.lua); the
#1#/#2# placeholders are filled the way the game fills them: joker values by evaluating the
vanilla `loc_vars` expressions (parsed from the Lovely dump of card.lua, cached in
data/joker_loc_vars.json) against the card's ability table, other sets from their config.

  python -m laya_player.desc --build     # extract localization + loc_vars once
"""
from __future__ import annotations

import json
import math
import os
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
GAME_EXE = Path(os.environ.get("BALATRO_EXE", r"C:\Program Files (x86)\Steam\steamapps\common\Balatro\Balatro.exe"))
DUMP = Path(os.environ.get("APPDATA", "")) / "Balatro" / "Mods" / "lovely" / "dump"

ENH = {"bonus": "+30 chips", "mult": "+4 Mult", "wild": "counts as every suit", "glass": "X2 Mult, 1 in 4 breaks",
       "steel": "X1.5 Mult while held", "stone": "+50 chips, no rank/suit, always scores",
       "gold": "$3 if held at round end", "lucky": "1 in 5 +20 Mult, 1 in 15 $20"}
EDITION = {"foil": "+50 chips", "holo": "+10 Mult", "polychrome": "X1.5 Mult", "negative": "+1 slot"}
SEAL = {"Red": "retrigger", "Blue": "Planet of last hand if held at round end", "Gold": "$3 when scored",
        "Purple": "Tarot when discarded"}


# --------------------------------------------------------------------------- build (one-off)

def build() -> None:
    import zipfile
    DATA.mkdir(exist_ok=True)
    src = zipfile.ZipFile(GAME_EXE).read("localization/en-us.lua").decode("utf8")
    (DATA / "en-us.lua").write_text(src, encoding="utf8")
    lua = (DUMP / "card.lua").read_text(encoding="utf8")
    a, b = lua.index("elseif self.ability.set == 'Joker' then -- all remaining jokers"), lua.index("if vars_only then")
    block = lua[a:b]
    out: dict[str, list[str]] = {}
    for m in re.finditer(r"((?:self\.ability\.name == (['\"])[^'\"]+\2\s*(?:or\s*)?)+)then", block):
        names = re.findall(r"self\.ability\.name == ['\"]([^'\"]+)['\"]", m.group(1))
        body = block[m.end(): m.end() + 1500]
        nxt = re.search(r"\n\s*elseif ", body)
        body = body[: nxt.start()] if nxt else body
        lv = body.find("loc_vars = {")
        if lv < 0:
            continue
        depth, i = 0, lv + len("loc_vars = ")
        for j in range(i, len(body)):
            depth += body[j] == "{"
            depth -= body[j] == "}"
            if depth == 0:
                break
        exprs = _split_top(body[i + 1: j])
        # `local a, b = SMODS.get_probability_vars(self, n, odds, ...)` feeds loc_vars = {a, b, ...}
        pm = re.search(r"local (\w+),\s*(\w+)\s*=\s*SMODS\.get_probability_vars\(self,\s*([^,]+),\s*([^,]+),", body)
        if pm:
            sub = {pm.group(1): pm.group(3).strip(), pm.group(2): pm.group(4).strip()}
            exprs = [sub.get(e, e) for e in exprs]
        for n in names:
            out[n] = [e for e in exprs if not re.match(r"^\s*\w+\s*=", e)]
    (DATA / "joker_loc_vars.json").write_text(json.dumps(out, indent=1), encoding="utf8")
    print(f"localization {len(src)} chars, loc_vars for {len(out)} jokers")


def _split_top(s: str) -> list[str]:
    parts, depth, cur = [], 0, ""
    for ch in s:
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur.strip())
    return parts


# --------------------------------------------------------------------------- data

@lru_cache(maxsize=1)
def _loc() -> dict[str, tuple[str, list[str]]]:
    src = (DATA / "en-us.lua").read_text(encoding="utf8")
    out = {}
    # text={ "line", "line", ... }: match the quoted lines themselves. A lazy `.*?},` stopped at the first
    # "{}," inside a line and cut 16 descriptions short (Fibonacci, Aura and Hone came out as bare names).
    for m in re.finditer(r'\b(\w+)=\{\s*name="([^"]*)",\s*text=\{((?:\s*"(?:[^"\\]|\\.)*",?)*)\s*\}', src, re.S):
        key = m.group(1)
        if key not in out:
            out[key] = (m.group(2), re.findall(r"\"((?:[^\"\\]|\\.)*)\"", m.group(3)))
    return out


@lru_cache(maxsize=1)
def _loc_vars() -> dict[str, list[str]]:
    return json.loads((DATA / "joker_loc_vars.json").read_text(encoding="utf8"))


@lru_cache(maxsize=1)
def _centers() -> dict:
    from jackdaw.engine import data as jd
    return json.loads((Path(jd.__file__).parent / "centers.json").read_text(encoding="utf8"))


def name_of(key: str) -> str:
    loc = _loc().get(key)
    if loc and loc[0]:
        return loc[0]
    c = _centers().get(key)
    return c["name"] if c and c.get("name") else key


# --------------------------------------------------------------------------- evaluation

class _Dot:
    def __init__(self, d):
        self._d = d

    def __getattr__(self, k):
        v = self._d.get(k) if isinstance(self._d, dict) else getattr(self._d, k, None)
        return _Dot(v) if isinstance(v, dict) else v


class _G:
    """Stand-in for G: probabilities are 1 (no Oops), everything else unknown."""

    def __getattr__(self, k):
        if k == "GAME":
            return _Dot({"probabilities": {"normal": 1}, "dollars": 0, "dollar_buffer": 0})
        return None


def _py(expr: str) -> str:
    e = expr.replace("self.ability", "A").replace("~=", "!=").replace("math.floor", "floor")
    e = e.replace("math.max", "max").replace("math.min", "min")
    e = re.sub(r"SMODS\.get_probability_vars\(self,\s*([^,]+),\s*([^,]+),[^)]*\)", r"__p(\1, \2)", e)
    e = re.sub(r"localize\(([^,()]+(?:\([^()]*\))?),\s*'[^']*'\)", r"\1", e)
    e = re.sub(r"localize\{[^}]*\}", "None", e)
    return e


def _eval(expr: str, ability: dict):
    ns = {"A": _Dot(ability), "G": _G(), "floor": math.floor, "max": max, "min": min,
          "__p": lambda a, b: (a, b), "nil": None, "true": True, "false": False}
    try:
        v = eval(_py(expr), {"__builtins__": {}}, ns)  # noqa: S307 -- expressions come from the game's own source
    except Exception:  # unparseable or depends on live G state
        return "?"
    return v


def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:g}"
    return "?" if v is None else str(v)


def _fill(lines: list[str], vars_: list) -> str:
    txt = " ".join(lines)
    txt = re.sub(r"\{[^{}]*\}", "", txt)
    txt = re.sub(r"#(\d+)#", lambda m: _fmt(vars_[int(m.group(1)) - 1]) if int(m.group(1)) <= len(vars_) else "X", txt)
    return re.sub(r"\s+", " ", txt).strip()


def ability_from_config(key: str) -> dict:
    """The ability table Card:set_ability builds from a center's config (default values)."""
    cfg = (_centers().get(key) or {}).get("config") or {}
    a = {"mult": cfg.get("mult", 0), "h_mult": cfg.get("h_mult", 0), "x_mult": cfg.get("Xmult", 1),
         "t_mult": cfg.get("t_mult", 0), "t_chips": cfg.get("t_chips", 0), "h_size": cfg.get("h_size", 0),
         "d_size": cfg.get("d_size", 0), "type": cfg.get("type", ""), "extra": cfg.get("extra"),
         "name": (_centers().get(key) or {}).get("name")}
    a.update({k: v for k, v in cfg.items() if k not in a and k != "Xmult"})
    return a


def _vars_for(key: str, ability: dict) -> list:
    name = ability.get("name") or name_of(key)
    if key.startswith("j_"):
        exprs = _loc_vars().get(name)
        if exprs is None:
            return []
        out = []
        for e in exprs:
            v = _eval(e, ability)
            out.extend(v if isinstance(v, tuple) else [v])
        return out
    cfg = (_centers().get(key) or {}).get("config") or {}
    if key.startswith("c_") and cfg.get("hand_type"):
        from .game import HAND_BASE
        h = cfg["hand_type"]
        _, _, chips_up, mult_up = HAND_BASE.get(h, (0, 0, 0, 0))
        return [ability.get("level", "?") if ability else "?", h, mult_up, chips_up]
    if key.startswith("c_"):
        out = []
        if "max_highlighted" in cfg:
            out.append(cfg["max_highlighted"])
        conv = cfg.get("mod_conv") or cfg.get("suit_conv")
        if conv:
            out.append(name_of(conv) if isinstance(conv, str) and conv.startswith("m_") else conv)
        for k in ("extra", "dollars", "tarots", "planets", "hand_type"):
            if k in cfg and not isinstance(cfg[k], dict):
                out.append(cfg[k])
        return out
    extra = cfg.get("extra")
    if isinstance(extra, dict):
        return list(extra.values())
    return [v for v in (cfg.get("choose"), extra, cfg.get("size")) if v is not None] if key.startswith("p_") else (
        [extra] if extra is not None else [])


def describe(key: str | None, ability: dict | None = None) -> str:
    """'Name: effect text' for a joker/consumable/voucher/booster/blind/tag key."""
    if not key:
        return "?"
    loc = _loc().get(key)
    if loc is None and key.startswith("p_"):
        loc = _loc().get(re.sub(r"_\d+$", "", key))
    nm = name_of(key)
    if loc is None:
        return nm
    ab = ability if ability is not None else ability_from_config(key)
    text = _fill(loc[1], _vars_for(key, ab))
    return f"{nm}: {text}" if text else nm


def card_legend(cards: list[dict]) -> str:
    """Short glossary for the enhancements/editions/seals present on playing cards."""
    seen = []
    for c in cards:
        for k, table in (("enh", ENH), ("ed", EDITION), ("seal", SEAL)):
            v = c.get(k)
            if v and v in table and f"{v}" not in [s.split("=")[0] for s in seen]:
                seen.append(f"{v}={table[v]}")
    return "; ".join(seen)


if __name__ == "__main__":
    import sys
    if "--build" in sys.argv:
        build()
    for k in ("j_green_joker", "j_jolly", "j_supernova", "j_bloodstone", "j_hiker", "c_justice", "c_strength",
              "c_mercury", "v_grabber", "p_buffoon_normal_1", "bl_goad", "bl_ox", "tag_economy"):
        print(describe(k))
