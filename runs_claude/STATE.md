# Stage 5 — Claude plays real Balatro itself (resume notes)

User (2026-10-09): "麻了，你去玩吧。作为 stage5" — after v1.3 (Laya's recorded win), Claude plays real Balatro
directly, Red Deck / White Stake, random seeds, through the same mod bridge and state text Laya reads
(no simulator lookahead, no score calculator). Log runs in the parent repo's `rounds.md` (CN), lessons in
`learnings.md`; compare with Laya at the end.

## How to play

`./bal <command>` (wrapper for `python -m laya_player.claude_cli`):
`show` · `play i j ..` / `discard i j ..` (hand indices) · `do N <text>` (always pass the expected option text:
options re-index after every action; the guard refuses a mismatch) · `use SLOT targets..` · `pick N targets..` ·
`jokers <new slot order>` · `new [SEED] | deck=.. stake=.. model=.. effort=..` · `report [model]` · `annotate tokens=N`. Moves log: `runs_claude/moves.jsonl`; finished runs: `runs_claude/runs.jsonl`.
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

## All-modes campaign (2026-10-10)

Sub-agents (Haiku/Sonnet) play one run each; results, per-mode table and plan are in [MODES.md](MODES.md), the agent
brief in [PLAYER.md](PLAYER.md). Launch prompt for an agent: "Read PLAYER.md, play one run: deck=b_x stake=1 model=haiku effort=high".
Logs are tagged per run/model/effort; compare models with `./bal report model`. Run 2 (M31Z2DGN) was overwritten by the campaign.

## Next

More random-seed runs (`new` with no seed) if the user wants a win rate. Remember: a forced Cerulean Bell card goes
along with every discard; discard indices shift after every draw, so never loop discards with fixed indices.

## Challenge campaign — ended 2026-10-16

Rule Breaker: 15/20 challenges completed (profile 2), all 20 unlocked. 2026-10-16: 13 Sonnet runs on mod v0.2.6, 10 won
(Medusa, Double or Nothing, Mad World, Inflation, Typecast, Monolith, Blast Off, Five-Card Draw, Knife's Edge, Bram
Poker), 3 lost (Cruelty Ante 5, Golden Needle Ante 4, Non-Perishable Ante 8 boss Violet Vessel). Left: Non-Perishable,
Fragile, Golden Needle, Cruelty, Jokerless. Rows in MODES.md; per-challenge tips in PLAYER.md "Challenge notes"; challenge
rules in `balatro-agent/mcp/data/reference/challenges.md`. Launch: "Read PLAYER.md, play one run: challenge=c_x model=sonnet".
