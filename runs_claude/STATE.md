# Stage 5 — Claude plays real Balatro itself (resume notes)

User (2026-10-09): "麻了，你去玩吧。作为 stage5" — after v1.3 (Laya's recorded win), Claude plays real Balatro
directly, Red Deck / White Stake, random seeds, through the same mod bridge and state text Laya reads
(no simulator lookahead, no score calculator). Log runs in the parent repo's `rounds.md` (CN), lessons in
`learnings.md`; compare with Laya at the end.

## How to play

`laya_player/claude_cli.py` (run from laya-player with `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m laya_player.claude_cli ...`):
`show` · `play i j ..` / `discard i j ..` (hand indices) · `do N <text>` (always pass the expected option text:
options re-index after every action; the guard refuses a mismatch) · `use SLOT targets..` · `pick N targets..` ·
`jokers <new slot order>` · `new [SEED]`. Moves log: `runs_claude/moves.jsonl`; finished runs: `runs_claude/runs.jsonl`.
Never chain two `do` commands without a `show` in between (run 1 bought Seed Money by accident that way).

## Run 1 — seed JYZLZ1JC: WON (2026-10-09)

Ante 8 boss Cerulean Bell 155,731 / 100,000; 20 rounds, 4 skips, 210 commands, best hand 91,219, Straight played 28
times. Final jokers: Scary Face, Supernova, Shortcut, Hologram (x2.25), Pareidolia; Straight L9. Screenshot
`runs_claude/win_JYZLZ1JC.png`; recap in the parent repo's `rounds.md`, mechanics in `learnings.md`.
The game was left on the win overlay (endless not entered).

## Laya on the same footing (reports/REPORT.md)

Laya on random real seeds: 1 win in 541 raw-click runs before v1.3; raw0056 9 runs mean 4.89 rounds; with computed
notes 256 runs mean 5.78, best 22. Its recorded win (UP2YINZS) was a simulator-screened seed (0.12% sim win rate).
Claude: 1 random seed, 1 win. n = 1, not a win rate.

## Next

More random-seed runs (`new` with no seed) if the user wants a win rate. Remember: a forced Cerulean Bell card goes
along with every discard; discard indices shift after every draw, so never loop discards with fixed indices.
