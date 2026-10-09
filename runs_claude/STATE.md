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

## Run 1 — seed JYZLZ1JC (in progress, paused 2026-10-09 for compaction)

- Now: **Ante 4 shop after the Small Blind, Jumbo Celestial pack open (1 pick), $20.** Plan: take Saturn
  (Straight L4 -> L5), leave shop, then Big Blind 7,500 (skip reward Uncommon Tag = free uncommon joker in the next
  shop; consider skipping) and boss **The Head 10,000 (Hearts debuffed)**.
- Jokers (5/5): Hallucination, Scary Face, Ice Cream (+55, -5 per hand), Supernova, Mystic Summit (+15 Mult at 0
  discards: burn all discards before the scoring hand). Vouchers: Paint Brush (+1 hand size), Seed Money.
- Levels: Straight L4 (120x13), Pair L2. Deck: Mult cards 6♠ 6♦ 8♦ 7♥; Glass 6♥ (a Heart: debuffed by The Head).
- Engine: straights (~7–9k with Mystic + Supernova). Weakness: no xMult joker; Ice Cream fading. Replace
  Hallucination with an xMult joker when one shows up.
- Path so far: skipped Ante 1 Small (Coupon Tag: free Hallucination, Scary Face, Ice Cream via Buffoon, Empress via
  Jumbo Arcana); Gros Michel bought Ante 2 and destroyed after one round; every boss cleared in one hand
  (The Window, The Club, The Goad); skipped Ante 3 Big for Meteor Tag (Saturn + Mercury), Fool copied Saturn.
