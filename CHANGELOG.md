# Changelog

Results tables and charts: [`README.md`](README.md), [`reports/REPORT.md`](reports/REPORT.md).

## v1.3 — A recorded real win; Stages 3 and 4; hosted decision APIs (2026-10-09)

- **Real win, on video.** `raw0056` (Stage 2, no notes) beat real Balatro on seed UP2YINZS: 27 rounds, Ante 10, every
  click Laya's, greedy; simulator twin 27. The seed was picked by the simulator. Random seeds: 9 runs today (best 14,
  no win); earlier raw-click real runs gave 1 win in 541. Video: `media/laya_balatro_win_UP2YINZS.mp4` on Hugging Face.
- **Simulator draws the real bosses.** Steamodded indexes `SMODS.create_blind_pool`'s hash-ordered array; jackdaw sorted
  by key. New read-only mod RPC `boss_pool_order` -> `laya_player/boss_order.json`; all 646 recorded real boss sequences
  match.
- **Seed screening** (`screen.py`): 2,592 fresh seeds, raw0056 won 3 (0.12%). Sim wins are replayed alone on the
  validator PC first (batched GPU play can flip near-ties: X0OVDA6S 25 rounds batched, 15 alone). Simulator summaries
  count Ante 9 reached as won (jackdaw clears `won` at the endless game over).
- **Recording** (`realloop --ckpt --record --stop-on-win --seeds-file`): every real run is screen-recorded; a won run is
  rendered with decision captions and a cover still, the longest other run kept, the rest deleted.
- **Stage 3 (ended): computed consequences in the options** (`LAYA_CALC=1`): exact score of the selected cards and
  flush/straight draw odds; a lockstep simulator twin computes the same notes in real Balatro (248/256 runs fully
  annotated). 45 RL iterations from raw0056, six promotions (raw0068 ... raw0100). Fixed 128 seeds: 4.59-5.21 with
  notes vs 5.63 for raw0056 without; real: 256 runs, 5.78 rounds, best 22, no win. No help.
- **Simulator fixes found by the Stage 3 twin**: Marble Joker's Stone card joins before the round shuffle; a round Mr.
  Bones saves pays no blind reward; `Card.set_base` keeps the suit; To Do List hand and near-equal round scores taken from
  the real game; identical-looking cards paired by sort order; face-down choices searched since the first hidden one.
- **Stage 4 (aborted): imitate the teacher again.** 100k-click chunks (1.25M available): held-out agreement 70.8% ->
  81.1%, ladder 5.63 -> 4.48, 4.74, 4.08, 4.02, 4.89. Closer imitation played worse, as in Stage 1.
- **Hosted decision APIs, zero-shot** (`apiplay.py`; OpenRouter decisions endpoint, probability per option). 64 seeds:
  raw0056 6.06; TypeSafe Jev 1.13 0.02 (0.08 with notes); OpenAI GPT-6 Luna Decisions 0.20 ($0.045, 1,195 clicks).
  Luna skipped the first blind in 34/62 traced games. Chart: `reports/decision_models.png`.

## v1.2 — Stage 2 ends: search labels for hand decisions (2026-10-07)

- **Result.** 65 RL iterations, champion `raw0056`. 128 fresh seeds, greedy: raw_init 1.64, raw0046 5.70, raw0056 5.63
  (paired t -0.2). Real: 285 Stage 2 runs average 5.7 rounds, twin identical in 272. First win: raw0032 (MST5TRB3,
  round 26). Stage 1's 7.9 real rounds stays the best average.
- **Search labels** (`simloop --search 0.25`, `search.py`): a quarter of self-play hand turns are searched on CPU
  workers. It sees only what a player sees, scores every play exactly with jackdaw, rolls out the best plays and discard
  draws on reshuffled decks (P(blind cleared) plus a little per spare hand). Clicks toward the best moves become labels;
  shop, pack and blind stay pure RL. 24 seeds, fixed shop rule: greedy hands 8.75 rounds, search 10.46.
- **Trust region** (`--search-step`): imitating labels outright broke click sequences (iterations 48-49 rolled back).
  Each searched click trains toward a soft target, the policy moved a step (0.3; 0.5 from iteration 59). Promotions
  raw0050 and raw0056. Fit did not move (0.683 -> 0.683): a third of searched clicks sit near p = 0. Softening the
  click distribution is the open problem.
- **Targeted pack tarots usable**: always shown as a two-step choice (`take tarot Strength`, then select cards and
  `apply Strength to selected` or `cancel`). The Hierophant is `c_heirophant` in the game. Simulator applied pack
  tarots to the wrong cards (targets indexed through `pack_hand` instead of `hand`); fixed.
- **Click-interface audit** (1,700 simulated runs with worst-case policies, fixes verified on 1,900): engine rejections
  4,521 -> 0, dead-ended runs 99 -> 0. Cerulean Bell forced card shown `(forced)`, selected, undeselectable; Mega and
  back-to-back tag packs no longer inherit the take/cancel limit; greyed-out consumables and blocked pack cards not
  offered; Negative jokers takeable with full slots; target clicks capped at the card's target count, 60-click safety net.
- **Sim/real mismatches fixed** (found by twin replays): hand-level print order for ties (sort by hand order on both
  sides); per-frame joker values (Cloud 9, Steel Joker, Stone Joker, Driver's License, Joker Stencil, Swashbuckler,
  Throwback); played cards scored in click order (now index-sorted); boss blind previews use each boss's own multiple;
  localization parser truncated 16 descriptions; face-down cards leaked ranks via rank-sorted order (mod now compares ids
  numerically); jackdaw's Satellite never paid (`planet_types_used` synced each step).
- Self-play temperature 0.4 -> 0.3. Credit `--credit best` (learn only from each seed's best sibling game) after PPO's
  clip kept flattening training weights (sampled games fell 4.1 -> 1.2 while greedy held ~5.3).
- Video captions use millisecond send times (`ts`) per decision; RL iterations record every game for the Stage 2 chart.

## v1.1 — Stage 2: raw clicks, pure RL (2026-10-07)

- **Raw click interface** (`LAYA_ACTIONS=raw`, default): one `choice` question per click over primitive moves; the state
  shows only what the screen shows for the selection. `LAYA_ACTIONS=combo` keeps Stage 1's pre-built moves.
- Teacher plays/discards 100% expressible (Stage 1: 36% / 34%). Label leak fixed: Stage 1 appended missing teacher
  discards as "(teacher)" (11% of hand examples). Multi-label training (`labels`).
- **PPO-clipped self-play**: plain advantage weighting kept wrecking the policy (iterations 4-6 rolled back). Clipped
  surrogate (+-20%), 2 epochs, batch 32, lr 3e-6, 128 games and 128 head-to-head seeds per iteration, T 0.4; first PPO
  champion raw0007.
- **Same-seed credit** (`--group 4 --credit seed`): each seed played 4 times, decisions judged against siblings that
  reached the same round.
- **Teacher only for the kickoff** (`raw_init`: 95,642 teacher clicks from sim0053; held-out agreement 37.7% -> 72.0%),
  then pure RL on random seeds; title changes on a paired t >= 1 win; real Balatro validates.
- Training on a 16 GB GPU box (`run_stage2_n8.sh`), `remote_sync.py` mirrors champions/logs to the game PC; inference
  batch from GPU memory. Validator runs Laya on the PC's GPU.
- **Mod: no more 8 s timeouts.** A non-blocking background event sat in the base queue for the whole shop; the drain check
  now ignores such events (buy 9 s -> 1 s, leave shop 8 s -> 1 s; a 10-round run ~14 -> ~5 min).
- `record.py`: ffmpeg font crash on Windows fixed.

## v1.0 — Stage 1 (2026-10-07)

Candidate-action interface, HF teacher imitation, simulator self-play in jackdaw with sim/real twin runs; champion
`sim0053` (9.01 rounds on 128 simulator seeds, 7.9 rounds over 81 real random-seed runs, best 17).
