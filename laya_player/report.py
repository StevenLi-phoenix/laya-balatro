"""Charts + summary for the write-up: simulator training curve, imitation sweep, real-game results.

  python -m laya_player.report      # -> reports/*.png, reports/REPORT.md
"""
from __future__ import annotations

import json
import random
import re
import statistics as st
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports"
IMIT = re.compile(r"imit (\d+): (\d+) examples, agreement ([\d.]+) .*? val ([\d.]+)")
CHAL = re.compile(r"iter (\d+): challenger ([\d.]+) vs champion ([\d.]+)")


def rows(p: Path) -> list[dict]:
    return [json.loads(l) for l in open(p, encoding="utf8")] if p.exists() else []


def sim_curve(its: list[dict], rebaseline: float) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.2))
    x = [r["iter"] for r in its]
    ax.scatter(x, [r["val_rounds"] for r in its], s=14, c="#4a7bd0", label="validation (greedy)")
    ax.scatter(x, [r["train_rounds"] for r in its], s=8, c="#bbbbbb", label="self-play games (sampled)")
    best, b = [], 7.50
    for r in its:  # 64 val seeds up to iter 85; then the champion was re-scored on 128 seeds
        b = max(b, r["val_rounds"]) if r["iter"] <= 85 else rebaseline
        best.append(b)
    ax.step(x, best, where="post", c="#d04a4a", lw=1.5, label="champion")
    for at, txt in [(85.5, "128 val seeds +\nhead-to-head check"), (98.5, "teacher replay off")]:
        ax.axvline(at, c="k", ls=":", lw=0.8)
        ax.text(at - 0.8, 2.3, txt, fontsize=8, ha="right")
    ax.axhline(7.50, c="#888", lw=0.8, ls="--")
    ax.text(14, 7.0, "rich_init (imitation) 7.50", fontsize=8, color="#666")
    ax.set(xlabel="iteration", ylabel="rounds won per run", ylim=(2, 10.5),
           title="Laya self-play in the jackdaw simulator (Red Deck / White Stake)")
    ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "sim_training.png", dpi=130)


def imitation(log: str) -> list[tuple]:
    pts = [(int(m[1]), int(m[2]), float(m[3]), float(m[4])) for m in IMIT.finditer(log)]
    if not pts:
        return pts
    fig, ax = plt.subplots(figsize=(7, 3.8))
    x = [0] + [p[1] / 1000 for p in pts]
    ax.plot(x, [9.01] + [p[3] for p in pts], "o-", c="#d04a4a", label="sim validation rounds")
    ax.set(xlabel="teacher decisions trained (thousands)", ylabel="rounds won", ylim=(6, 10))
    ax2 = ax.twinx()
    ax2.plot(x, [77.1] + [p[2] * 100 for p in pts], "s--", c="#4a7bd0", label="agreement with teacher (%)")
    ax2.set(ylabel="teacher agreement %", ylim=(70, 90))
    ax.set_title("Imitating the HF teacher more closely made Laya play worse")
    fig.legend(loc="lower left", bbox_to_anchor=(0.1, 0.15), fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "imitation.png", dpi=130)
    return pts


def real(rt: list[dict], ck: str, png: str = "real_game.png") -> dict | None:
    rs = [r for r in rt if r["ckpt"] == ck and r["real_outcome"] in ("won", "lost")]
    if not rs:
        return None
    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 3.8))
    a.hist([r["real_rounds"] for r in rs], bins=range(0, 20), color="#4a7bd0", edgecolor="white")
    a.set(xlabel="rounds won", ylabel="runs", title=f"Real Balatro, {ck}, {len(rs)} random seeds")
    m = [r for r in rs if r["sim_rounds"] is not None]
    b.scatter([r["real_rounds"] for r in m], [r["sim_rounds"] for r in m], s=18, alpha=0.6, c="#d04a4a")
    b.plot([0, 18], [0, 18], c="#888", lw=0.8)
    same = sum(r["sim_rounds"] == r["real_rounds"] for r in m)
    b.set(xlabel="real game rounds", ylabel="simulator rounds (same seed)",
          title=f"Sim/real twin runs: {same}/{len(m)} identical")
    fig.tight_layout()
    fig.savefig(OUT / png, dpi=130)
    return {"runs": len(rs), "mean": st.mean(r["real_rounds"] for r in rs), "best": max(r["real_rounds"] for r in rs),
            "ante": st.mean(r["real_ante"] for r in rs), "wins": sum(r["real_outcome"] == "won" for r in rs),
            "same": same, "twins": len(m)}


def _setting_changes(its: list[dict]) -> list[tuple[float, str]]:
    """Restarts with new settings (runs/stage2_n8.log) -> (x between iterations, short label)."""
    log = ROOT / "runs" / "stage2_n8.log"
    times = {}
    for l in (ROOT / "runs_sim" / "simloop.log").read_text(encoding="utf8").splitlines():
        m = re.match(r"(\d\d:\d\d:\d\d) iter (\d+):", l)
        if m:
            times[int(m[2])] = m[1]
    out, prev = [], {}
    for l in (log.read_text(encoding="utf8").splitlines() if log.exists() else []):
        m = re.match(r"(\d\d:\d\d:\d\d) simloop \(re\)started: (.*)", l)
        if not m:
            continue
        args = dict(re.findall(r"--([\w-]+) (\S+)", m[2]))
        diff = {k: v for k, v in args.items() if prev.get(k) != v}
        prev = args
        nxt = [i for i, t in sorted(times.items()) if t > m[1]]
        if nxt and diff:
            short = {"batch": "batch", "lr": "lr", "games": "games", "test-games": "test", "temperature": "T",
                     "epochs": "PPO clip, epochs", "group": "same-seed credit, group", "search": "search labels",
                     "search-workers": None, "search-step": "search step"}
            lab = ", ".join(f"{short.get(k, k)} {v}" for k, v in diff.items() if short.get(k, k))
            if lab:
                out.append((nxt[0] - 0.5, lab))
    return out


def rl_curve(its: list[dict]) -> None:
    """Stage 2 in the Stage 1 chart style. Seeds are fresh every iteration, so the champion line is the running
    mean of every head-to-head score the reigning champion has posted."""
    x = [r["iter"] for r in its]
    fig, ax = plt.subplots(figsize=(max(10.0, 0.32 * len(x)), 5.0))
    rng = random.Random(0)
    jit = lambda i, n, off: [i + off + rng.uniform(-0.11, 0.11) for _ in range(n)]
    for i, r in zip(x, its):  # every game, when the iteration recorded them (older ones kept means only)
        if r.get("train_games"):
            ax.scatter(jit(i, len(r["train_games"]), -0.25), r["train_games"], s=3, c="#bbbbbb", alpha=0.5, lw=0)
            ax.scatter(jit(i, len(r["champion_games"]), 0.0), r["champion_games"], s=3, c="#e8a0a0", alpha=0.5, lw=0)
            ax.scatter(jit(i, len(r["test_games"]), 0.25), r["test_games"], s=3, c="#7fa3e0", alpha=0.6, lw=0)
    ax.scatter([i - 0.25 for i in x], [r["train_rounds"] for r in its], s=16, c="#888888", marker="_",
               label="self-play games (sampled): each game + mean")
    ax.scatter([i + 0.25 for i in x], [r["test_rounds"] for r in its], s=18, c="#4a7bd0",
               label="new weights, greedy: each game + mean")
    ax.scatter(x, [r["champion_rounds"] for r in its], s=14, c="#d04a4a", marker="x",
               label="champion on the same seeds: each game + mean")
    scores: dict[str, list[float]] = {}
    before, line = "raw_init.pt", []
    for r in its:
        scores.setdefault(before, []).append(r["champion_rounds"])
        if r["champion"] != before:
            scores.setdefault(r["champion"], []).append(r["test_rounds"])
        before = r["champion"]
        line.append(st.mean(scores[before]))
    ax.step(x, line, where="post", c="#d04a4a", lw=1.5, label="champion (mean of its head-to-heads)")
    base = st.mean(scores.get("raw_init.pt", [0]))
    ax.axhline(base, c="#888", lw=0.8, ls="--")
    ax.text(x[-1] + 0.6, base, f"raw_init {base:.2f}", fontsize=8, color="#666", va="center")
    ax.axhline(9.01, c="#d9a0a0", lw=0.8, ls="--")
    ax.text(x[-1] + 0.6, 9.01, "Stage 1\nsim0053 9.01", fontsize=8, color="#b07070", va="center")
    top = max([9.5] + [max(r.get("test_games") or [0]) + 0.8 for r in its] + [max(r.get("train_games") or [0]) + 0.8 for r in its])
    for k, (at, txt) in enumerate(_setting_changes(its)):  # staggered so close changes stay readable
        ax.axvline(at, c="k", ls=":", lw=0.8)
        ax.text(at - 0.15, top * (0.97 - 0.2 * (k % 3)), txt, fontsize=7, ha="right", rotation=90, va="top",
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.7, pad=0.5))
    ax.set(xlabel="iteration", ylabel="rounds won per run", ylim=(0, top), xlim=(x[0] - 0.8, x[-1] + 2.6),
           title="Stage 2: Laya clicks (raw actions), pure RL in the jackdaw simulator (Red Deck / White Stake)")
    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=4, fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "stage2_rl.png", dpi=130)


def stage1(rt: list[dict]) -> list[str]:
    base = ROOT / "runs_sim_v2_combo"
    its = rows(base / "iters.jsonl")
    log = (base / "simloop.log").read_text(encoding="utf8")
    champ = json.loads((base / "state.json").read_text())
    sim_curve(its, champ["best"])
    imit = imitation(log)
    ck = Path(champ["champion"]).name
    r = real(rt, ck)
    chal = [(int(m[1]), float(m[2]), float(m[3])) for m in CHAL.finditer(log)]
    md = ["## Stage 1 (v1.0): pre-built candidate moves\n",
          f"Champion **{ck}**: simulator validation {champ['best']:.2f} rounds over {champ['val_games']} fixed seeds "
          f"after {champ['iter']} self-play iterations.\n",
          f"Real game: {r['runs']} runs on random seeds, mean {r['mean']:.2f} rounds won, best {r['best']}, mean max "
          f"ante {r['ante']:.1f}, {r['wins']} wins; simulator replay of the same seed matched in "
          f"{r['same']}/{r['twins']} runs.\n", "![real](real_game.png)\n", "![sim](sim_training.png)\n",
          "Head-to-head checks (challenger beat the champion on the validation seeds, then both played 64 fresh seeds):\n",
          "| iter | challenger | champion |", "|---|---|---|"]
    md += [f"| {i} | {a:.2f} | {c:.2f} |" for i, a, c in chal]
    md += ["\nImitation of the HF teacher (V68 heuristic, 74.6% win rate in Pylatro):\n", "![imit](imitation.png)\n",
           "| chunk | decisions | agreement | sim val |", "|---|---|---|---|"]
    md += [f"| {k} | {n} | {a:.1%} | {v:.2f} |" for k, n, a, v in imit]
    return md


def stage2(rt: list[dict]) -> list[str]:
    its = rows(ROOT / "runs_sim" / "iters.jsonl")
    ev = ROOT / "runs" / "raw_init_eval.json"
    md = ["## Stage 2 (v1.1+): raw clicks, pure RL\n",
          "Laya clicks like a player (`select K♥` ... `play selected`): one choice question per click, several "
          "clicks per decision, no pre-built combinations, hand labels or score estimates. The HF teacher is used "
          "once (kickoff imitation from sim0053); afterwards training is pure RL in the simulator on random seeds. "
          "Each iteration the new weights and the champion play the same fresh random seeds; a paired t >= 1 win "
          "takes the title. Real Balatro validates the champion on random seeds.\n",
          "From iteration 48 (v1.2) a quarter of self-play hand turns are also searched in the simulator "
          "(`search.py`): every play scored exactly, candidate plays and discards rolled out on reshuffled decks, "
          "no draw order or RNG seen. The clicks toward the best moves become a soft target: the playing policy "
          "moved a step (0.3; 0.5 from iteration 59) toward them. Laya's interface is unchanged.\n"]
    if ev.exists():
        e = json.loads(ev.read_text())
        md.append(f"Kickoff (teacher clicks, held-out games): agreement {e['before']['all']:.1%} before -> "
                  f"**{e['after']['all']:.1%}** after (hand {e['after'].get('hand', 0):.1%}, "
                  f"shop {e['after'].get('shop', 0):.1%}, pack {e['after'].get('pack', 0):.1%}).\n")
    if its:
        rl_curve(its)
        last = its[-1]
        md += [f"RL: {len(its)} iterations, champion **{last['champion']}**.\n", "![rl](stage2_rl.png)\n",
               "| iter | train | new weights | champion | paired t | champion after |", "|---|---|---|---|---|---|"]
        md += [f"| {r['iter']} | {r['train_rounds']:.2f} | {r['test_rounds']:.2f} | {r['champion_rounds']:.2f} | "
               f"{r['t']:+.1f} | {r['champion']} |" for r in its[-15:]]
    lad = ROOT / "runs" / "ladder.json"
    if lad.exists():
        L = json.loads(lad.read_text())
        res, n = L["results"], len(L["seeds"])
        md += [f"\nSame {n} fresh seeds, greedy, every checkpoint (deal luck cancels):\n",
               "| checkpoint | mean rounds | median | >= 9 rounds | wins |", "|---|---|---|---|---|"]
        for name, r in res.items():
            md.append(f"| {name} | {st.mean(r['rounds']):.2f} | {st.median(r['rounds'])} | "
                      f"{sum(x >= 9 for x in r['rounds'])}/{n} | {sum(r['won'])} |")
        names = list(res)
        if len(names) >= 2:
            a, b = res[names[-1]]["rounds"], res[names[-2]]["rounds"]
            d = [x - y for x, y in zip(a, b)]
            t = st.mean(d) / ((st.pstdev(d) or 1) / len(d) ** 0.5)
            md.append(f"\n{names[-1]} vs {names[-2]}: {st.mean(d):+.2f} rounds per seed (paired t {t:+.1f}).\n")
    cks = list(dict.fromkeys(r["ckpt"] for r in rt if r["ckpt"].startswith("raw")))
    if cks:
        md += ["\nReal Balatro validation:\n", "| checkpoint | runs | mean rounds | best | mean ante | wins | sim twin identical |",
               "|---|---|---|---|---|---|---|"]
        for ck in cks:
            r = real(rt, ck, "stage2_real.png")
            if r:
                md.append(f"| {ck} | {r['runs']} | {r['mean']:.2f} | {r['best']} | {r['ante']:.1f} | {r['wins']} | "
                          f"{r['same']}/{r['twins']} |")
        md.append("\n![real2](stage2_real.png)\n")
    return md


def main():
    OUT.mkdir(exist_ok=True)
    rt = rows(ROOT / "runs" / "real_test.jsonl")
    ver = (ROOT / "VERSION").read_text().strip() if (ROOT / "VERSION").exists() else "?"
    md = [f"# Laya plays Balatro: results (v{ver})\n"] + stage2(rt) + stage1(rt)
    (OUT / "REPORT.md").write_text("\n".join(md) + "\n", encoding="utf8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
