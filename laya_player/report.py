"""Charts + summary for the write-up: simulator training curve, imitation sweep, real-game results.

  python -m laya_player.report      # -> reports/*.png, reports/REPORT.md
"""
from __future__ import annotations

import json
import re
import statistics as st
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

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


def real(rt: list[dict], ck: str) -> dict:
    rs = [r for r in rt if r["ckpt"] == ck and r["real_outcome"] in ("won", "lost")]
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
    fig.savefig(OUT / "real_game.png", dpi=130)
    return {"runs": len(rs), "mean": st.mean(r["real_rounds"] for r in rs), "best": max(r["real_rounds"] for r in rs),
            "ante": st.mean(r["real_ante"] for r in rs), "wins": sum(r["real_outcome"] == "won" for r in rs),
            "same": same, "twins": len(m)}


def main():
    OUT.mkdir(exist_ok=True)
    its = rows(ROOT / "runs_sim" / "iters.jsonl")
    log = (ROOT / "runs_sim" / "simloop.log").read_text(encoding="utf8")
    champ = json.loads((ROOT / "runs_sim" / "state.json").read_text())
    sim_curve(its, champ["best"])
    imit = imitation(log)
    ck = Path(champ["champion"]).name
    r = real(rows(ROOT / "runs" / "real_test.jsonl"), ck)
    chal = [(int(m[1]), float(m[2]), float(m[3])) for m in CHAL.finditer(log)]
    md = [f"# Laya plays Balatro: results\n",
          f"Champion: **{ck}**, simulator validation {champ['best']:.2f} rounds over {champ['val_games']} fixed seeds "
          f"after {champ['iter']} self-play iterations.\n",
          "## Real game (test set)\n",
          f"{r['runs']} runs on random seeds: mean {r['mean']:.2f} rounds won, best {r['best']}, mean max ante "
          f"{r['ante']:.1f}, {r['wins']} wins. The simulator replay of the same seed matched the real round count in "
          f"{r['same']}/{r['twins']} runs.\n", "![real](real_game.png)\n",
          "## Simulator self-play\n", "![sim](sim_training.png)\n",
          "Head-to-head checks (challenger beat the champion on the validation seeds, then both played 64 fresh seeds):\n",
          "| iter | challenger | champion |", "|---|---|---|"]
    md += [f"| {i} | {a:.2f} | {c:.2f} |" for i, a, c in chal]
    md += ["\n## Imitation of the HF teacher (V68 heuristic, 74.6% win rate in Pylatro)\n", "![imit](imitation.png)\n",
           "| chunk | decisions | agreement | sim val |", "|---|---|---|---|"]
    md += [f"| {k} | {n} | {a:.1%} | {v:.2f} |" for k, n, a, v in imit]
    (OUT / "REPORT.md").write_text("\n".join(md) + "\n", encoding="utf8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
