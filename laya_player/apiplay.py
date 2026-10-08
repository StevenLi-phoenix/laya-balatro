"""How do hosted decision APIs play Balatro through Laya's interface? Same simulator, same prompts.

Every call is the exact choice question Laya gets (raw clicks; LAYA_CALC=1 adds Stage 3's notes): the state text,
the phase's question and the legal click options. A policy picks one option; games run in threads.
  jev     TypeSafe Jev (OpenRouter /api/alpha/decisions): a choice question, argmax of its probabilities
  openai  an OpenAI chat model (OpenRouter chat/completions): numbered options, it answers a number
Results pair seed for seed with Laya on the ladder seeds (runs/ladder.json).

  python -m laya_player.apiplay jev --model typesafe/jev-1.13 --seeds 128
  python -m laya_player.apiplay openai --model openai/gpt-5.6-luna --seeds 128
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import calc, game
from .sim import SimGame

ROOT = Path(__file__).resolve().parent.parent
KEY = ROOT / ".secrets" / "openrouter.key"
SYSTEM = ("You are playing Balatro (Red Deck, White Stake) one click at a time. Each turn you see the game state and "
          "a numbered list of the legal clicks. Choose the click that gives the best chance to beat the current blind "
          "and win the run. Reply with the number of your choice only.")
_lock = threading.Lock()


def _post(url: str, body: dict, tries: int = 6) -> dict:
    key = KEY.read_text().strip()
    for k in range(tries):
        req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            return json.load(urllib.request.urlopen(req, timeout=60))
        except urllib.error.HTTPError as e:
            if e.code not in (408, 429, 500, 502, 503, 504) or k == tries - 1:
                raise RuntimeError(f"HTTP {e.code}: {e.read()[:200]!r}") from None
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if k == tries - 1:
                raise
        time.sleep(min(30, 2 ** k))
    raise RuntimeError("unreachable")


def jev_choose(model: str):
    def choose(phase: str, state: str, options: list[str]) -> tuple[int, float]:
        r = _post("https://openrouter.ai/api/alpha/decisions", {
            "model": model, "state": state,
            "questions": {"a": {"type": "choice", "instructions": game.QUESTION[phase],
                                "criteria": {str(i): o for i, o in enumerate(options)}}}})
        probs = r["answers"]["a"]["probabilities"]
        return int(max(probs, key=probs.get)), float((r.get("usage") or {}).get("cost") or 0)
    return choose


def openai_choose(model: str):
    def choose(phase: str, state: str, options: list[str]) -> tuple[int, float]:
        user = (f"{game.QUESTION[phase]}\n\n{state}\n\nOptions:\n"
                + "\n".join(f"{i + 1}) {o}" for i, o in enumerate(options)))
        r = _post("https://openrouter.ai/api/v1/chat/completions", {
            "model": model, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            "max_tokens": 4000})  # reasoning tokens count against it: 400 left 73% of answers empty
        text = (r["choices"][0]["message"].get("content") or "").strip()
        m = re.search(r"\d+", text)
        k = int(m.group()) - 1 if m else -1
        if not 0 <= k < len(options):
            raise ValueError(f"no option in answer {text[:40]!r} (finish {r['choices'][0].get('finish_reason')})")
        return k, float((r.get("usage") or {}).get("cost") or 0)
    return choose


LOCAL = ("select", "deselect", "choose_pick", "cancel_pick")


def play_one(seed: str, choose, max_calls: int, trace: Path | None = None) -> dict:
    g = SimGame(seed)
    calls = cost = errors = invalid = forced = clicks = 0
    banned: dict[str, set] = {}
    kinds: dict[str, int] = {}
    tf = open(trace, "a", encoding="utf8", buffering=1) if trace else None
    while calls < max_calls:
        s = g.pending()
        if s is None:
            break
        cands = game.candidates(s)
        calc.annotate(s, cands, g.gs, g.calc_cache)  # LAYA_CALC=1: the Stage 3 computed notes
        txt = game.state_text(s)
        opts, acts = [], []
        for a in cands:
            o = game.action_text(s, a)
            if o not in opts and o not in banned.get(txt, ()):
                opts.append(o)
                acts.append(a)
        if not acts:
            fb = {"shop": {"t": "leave"}, "pack": {"t": "skip_pack"}, "blind": {"t": "select_blind"}}.get(s["phase"])
            if fb is None:
                break
            acts, opts = [fb], [game.action_text(s, fb)]
        if len(acts) == 1:
            k = 0
        else:
            k = -1
            for _ in range(3):  # an API failure or an unreadable answer is asked again, not defaulted
                try:
                    k, c = choose(s["phase"], txt, opts)
                    cost += c
                    break
                except Exception as e:  # noqa: BLE001
                    errors += 1
                    why = f"{type(e).__name__}: {str(e)[:60]}"
                    kinds[why] = kinds.get(why, 0) + 1
            calls += 1
            if k < 0:
                invalid += 1
                k = 0
            if calls % 100 == 0:
                print(f"  {seed}: {calls} calls, {g.rounds_won} rounds, ante {s.get('ante')}, ${cost:.3f}", flush=True)
        if acts[k]["t"] in LOCAL and clicks >= 60:
            # the real runner's safety net: 60 clicks without a game action is a click loop; take a commit
            k = next((i for typ in ("play", "discard", "pick", "cancel_pick", "skip_pack", "leave")
                      for i, x in enumerate(acts) if x["t"] == typ), k)
            forced += 1
        clicks = clicks + 1 if acts[k]["t"] in LOCAL else 0
        if tf:
            tf.write("\t".join((seed, s["phase"], f"a{s.get('ante')}", f"r{g.rounds_won}", opts[k])) + "\n")
        if not g.apply(s, acts[k]):
            banned.setdefault(txt, set()).add(opts[k])
    if tf:
        tf.close()
    return {"seed": seed, "rounds": g.rounds_won, "ante": g.max_ante, "won": bool(g.gs.get("won")), "calls": calls,
            "cost": round(cost, 5), "errors": errors, "invalid": invalid, "forced": forced, "capped": calls >= max_calls,
            "error_kinds": kinds}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=("jev", "openai"))
    ap.add_argument("--model", required=True)
    ap.add_argument("--seeds", type=int, default=128, help="first N ladder seeds")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--max-calls", type=int, default=4000, help="API calls per game at most")
    ap.add_argument("--ladder", default=str(ROOT / "runs" / "ladder.json"))
    args = ap.parse_args()
    lad = json.loads(Path(args.ladder).read_text())
    seeds = lad["seeds"][: args.seeds]
    choose = (jev_choose if args.kind == "jev" else openai_choose)(args.model)
    out = ROOT / "runs" / f"api_{args.model.replace('/', '_')}{'+calc' if calc.ON else ''}.jsonl"
    done = {json.loads(l)["seed"] for l in open(out, encoding="utf8")} if out.exists() else set()
    todo = [s for s in seeds if s not in done]
    t0 = time.time()

    trace = out.with_suffix(".trace.tsv")

    def run(seed):
        rec = play_one(seed, choose, args.max_calls, trace)
        with _lock:
            with open(out, "a", encoding="utf8") as f:
                f.write(json.dumps(rec) + "\n")
            print(f"{time.strftime('%H:%M:%S')} {seed}: {rec['rounds']} rounds (ante {rec['ante']}) | "
                  f"{rec['calls']} calls ${rec['cost']:.4f} | errors {rec['errors']} invalid {rec['invalid']} forced {rec['forced']}", flush=True)

    with ThreadPoolExecutor(args.workers) as ex:
        list(ex.map(run, todo))
    rows = {r["seed"]: r for r in map(json.loads, open(out, encoding="utf8"))}
    mine = [rows[s]["rounds"] for s in seeds if s in rows]
    print(f"{args.model}: {len(mine)} games, mean {statistics.mean(mine):.2f} rounds (median {statistics.median(mine)}), "
          f"wins {sum(rows[s]['won'] for s in seeds if s in rows)}, cost ${sum(rows[s]['cost'] for s in seeds if s in rows):.2f}, "
          f"{(time.time() - t0) / 60:.1f} min")
    for name, res in lad["results"].items():
        base = res["rounds"][: len(mine)] if len(mine) == len(seeds) else None
        if base:
            d = [a - b for a, b in zip(mine, base)]
            se = (statistics.pstdev(d) or 1.0) / len(d) ** 0.5
            print(f"  vs {name} ({statistics.mean(base):.2f}): {statistics.mean(d):+.2f}, paired t {statistics.mean(d) / se:+.2f}")


if __name__ == "__main__":
    main()


class ApiPolicy:
    """A decision API in place of Laya for the real-game runner (`evolve.play_run`, `record.py`):
    the same choose() signature, the API's own probabilities as `probs`."""

    def __init__(self, model: str):
        self.ckpt = model
        self.cost = 0.0

    def choose(self, phase: str, state: str, options: list[str], temperature: float = 0.3,
               greedy: bool = True) -> tuple[int, list[float]]:
        if len(options) == 1:
            return 0, [1.0]
        for k in range(3):
            try:
                r = _post("https://openrouter.ai/api/alpha/decisions", {
                    "model": self.ckpt, "state": state,
                    "questions": {"a": {"type": "choice", "instructions": game.QUESTION[phase],
                                        "criteria": {str(i): o for i, o in enumerate(options)}}}})
                break
            except Exception:  # noqa: BLE001
                if k == 2:
                    raise
        self.cost += float((r.get("usage") or {}).get("cost") or 0)
        probs = r["answers"]["a"]["probabilities"]
        p = [round(float(probs.get(str(i), 0.0)), 4) for i in range(len(options))]
        return max(range(len(options)), key=p.__getitem__), p
