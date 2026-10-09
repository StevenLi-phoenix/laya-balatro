# Changelog

## v1.3 — A recorded real win; Stages 3 and 4; hosted decision APIs (2026-10-09)

- **A real win, on video.** The ladder champion `raw0056` (Stage 2, no notes) beat real Balatro on seed UP2YINZS:
  27 rounds, Ante 10, every click Laya's, greedy; the simulator twin also reached 27. The seed was picked by the
  simulator (below). On random seeds the same weights played 9 recorded runs today (best 14, no win), and before
  that real raw-click runs had produced one win in 541. Video (4x, win screen at normal speed):
  `media/laya_balatro_win_UP2YINZS.mp4` on Hugging Face; the cover is its win screen.
- **Simulator: the real boss order.** jackdaw's bosses never matched the real game on the same seed, so twin replays
  forced the real bosses and no simulated seed could predict a real run. Cause: Steamodded draws the same 'boss'
  pseudoseed, but indexes `SMODS.create_blind_pool`'s array, built by iterating a hash table, while jackdaw sorts
  the pool by key. On Ante 1 the real index was a fixed permutation of jackdaw's in 645/645 recorded runs. A new
  read-only mod RPC (`boss_pool_order`) reads the pool order per ante from the game (`laya_player/boss_order.json`);
  jackdaw now draws from it. All 646 recorded real boss sequences match at every ante, finale included.
- **Seed screening** (`screen.py`): fresh random seeds played greedily in the simulator. 2,592 seeds, raw0056 won 3
  (0.12%). A sim win is replayed alone on the validator PC before the real game plays it, because batched play on
  the GPU box can flip a near-tie (X0OVDA6S: 25 rounds batched, 15 alone). Simulator summaries count a run that
  reaches Ante 9 as won: jackdaw clears `won` at the endless game over, so won runs had reported `won: False`
  (no published number changes; no ladder or API run had reached Ante 9).
- **Validator recording** (`realloop --ckpt --record --stop-on-win --seeds-file`): every real run is screen-recorded;
  a won run is rendered with decision captions and a cover still, the longest run so far is kept, the rest deleted.
- **Stage 3 (ended): computed consequences in the options** (`LAYA_CALC=1`). Each click option carried the exact
  score of the selected cards (jackdaw's scoring on copies) and flush/straight draw odds; in real Balatro a lockstep
  simulator twin computed the same notes (every move annotated in 248/256 runs). 45 RL iterations from raw0056, six
  promotions (raw0068 … raw0100; promotion moved from paired t ≥ 1 to t ≥ 2, self-play temperature 0.3 → 0.5).
  On the 128 fixed seeds every champion with notes scored 4.59–5.21 against raw0056's 5.63 without them; real
  Balatro with notes: 256 runs, 5.78 rounds on average, best 22, no win. The notes did not help.
- **Simulator fixes found by the Stage 3 twin**: Marble Joker's Stone card joins the deck before the round shuffle;
  a round Mr. Bones saves pays no blind reward; `Card.set_base` keeps the original suit (Steamodded); To Do List's
  hand and near-equal round scores are taken over from the real game; identical-looking cards are paired by sort
  order; face-down choices are searched across the moves since the first hidden one.
- **Stage 4 (aborted): imitate the teacher once more.** From raw0056 without notes, 100k-click chunks of the HF
  teacher (1.25M clicks available): held-out agreement 70.8% → 81.1% after 500k clicks, while the 128-seed ladder
  fell to 4.48, 4.74, 4.08, 4.02, 4.89 (raw0056: 5.63). As in Stage 1, closer imitation played worse.
- **Hosted decision APIs, zero-shot.** OpenRouter's decisions endpoint returns a probability per option, the same
  contract as Laya, so the same raw-click interface ran on it (`apiplay.py`). Same 64 seeds in the simulator:
  raw0056 6.06 rounds; TypeSafe Jev 1.13 0.02, Jev with computed notes 0.08, OpenAI GPT-6 Luna Decisions 0.20
  ($0.045 for 1,195 clicks, 0 errors). GPT-6 Luna Decisions skipped the very first blind in 34 of 62 traced games;
  it reached 13 rounds on one seed (BXEMK4GS), where real Balatro then gave it 5, Laya 11 and Jev 2
  (`media/compare_BXEMK4GS.mp4`). Chart: `reports/decision_models.png`.

## v1.2 — Stage 2 ends: search labels for hand decisions (2026-10-07)

- **Stage 2 result.** 65 RL iterations; final champion `raw0056`. Same 128 fresh seeds, greedy: raw_init 1.64,
  raw0046 (last champion before search labels) 5.70, raw0056 5.63 (−0.07 per seed, paired t −0.2; `ladder.py`).
  Real Balatro: 285 Stage 2 runs average 5.7 rounds, twin replay identical in 272. First win: raw0032 (seed
  MST5TRB3, round 26). Stage 1's champion still holds the best real average (7.9 rounds over 81 runs).
- **Search labels for hand decisions** (`simloop --search 0.25`, new `search.py`). RL judged a hand click only
  through the run's final round count, and stalled: the champion's median run still died in Ante 1–2. Now a quarter
  of self-play hand turns are searched on CPU workers while the GPU keeps playing. The search sees only what a player
  sees (no draw order, no RNG). It scores every possible play exactly with jackdaw's pipeline. Then it rolls out the
  best plays and a set of discard draws (flush, straight, kinds, low cards) on reshuffled decks, scoring each by
  P(blind cleared) plus a little per hand to spare. Every click toward one of the best moves becomes a label;
  consumable clicks are left out of the judgement. Laya's interface is unchanged: raw clicks, no estimates. Shop,
  pack and blind decisions stay pure RL. Benchmark on 24 seeds with a fixed shop rule: greedy hand play
  8.75 rounds (median 9.5), search 10.46 (median 11). Laya's champion averages ~6.2 with its own shop play, so hand
  play is where it loses.
- **Search labels within a trust region** (`--search-step`). Imitating the labels outright broke the click sequences
  (iterations 48–49: 2.48 vs 5.64 and 2.37 vs 6.24, both rolled back). The champion's click distribution is nearly
  0/1: some search-approved clicks sat at log p −40 to −60. Each searched click now trains toward a soft target,
  the playing distribution moved a step (0.3; 0.5 from iteration 59) onto the search's clicks, in the spirit of
  conservative policy iteration. Next two promotions: raw0050 (6.45 vs 5.95, t +1.3) and raw0056 (6.62 vs 5.92,
  t +2.0).
- **Diagnostics: agreement and fit.** Each iteration logs how much probability self-play puts on the search's clicks
  (flat at 0.67–0.70 from iteration 55 on), plus the same number on the trained clicks before and after training. The
  fit did not move (0.683 → 0.683, 0.639 → 0.641): about a third of the searched clicks sit near p = 0, and a bounded
  step cannot move them. Softening the click distribution is the open problem for the next stage.
- **Targeted pack tarots are usable.** In v1.1 a targeted card in an Arcana/Spectral pack was only offered after
  hand cards were selected, so Laya never saw it (19 such packs in real runs: 9 untargeted takes, 10 skips, 0 uses).
  Now it is always visible as a two-step choice: `take tarot Strength (then choose its target cards)`, then
  select/deselect hand cards and `apply Strength to selected` (or `cancel Strength`). Teacher pack picks of targeted
  cards (the dataset has no targets) now teach the first step.
- **Balatro spells The Hierophant `c_heirophant`**: added to the targeted list (it was offered without targets and
  always rejected).
- **Simulator: pack tarots hit the wrong cards.** jackdaw deals an opened pack into `gs["hand"]` and indexes targets
  there; the adapter mapped targets through `gs["pack_hand"]`, so every simulated pack tarot (Stage 1 included) was
  applied to other cards than chosen. Verified: Magician on K♣ → K♣ Lucky, Tower on 10♥ → 10♥ Stone, Hanged Man
  on 10♠ → 10♠ destroyed.
- Video captions come from millisecond send times recorded on every decision (`ts`); within a decision the caption
  grows click by click. The log shows milliseconds.
- **Click-interface audit** (1,700 simulated runs with worst-case click policies, then fixes verified on 1,900):
  engine rejections 4,521 → 0, dead-ended runs 99 → 0, no infinite loops (longest click run: 25 in hand, 50 in a pack).
  - Cerulean Bell: the forced card is shown `(forced)`, starts selected and cannot be deselected (sim + mod + runner);
    jackdaw's forced flag is cleared at end of round like the real game.
  - Mega packs and back-to-back tag packs no longer inherit the take/cancel limit.
  - Consumables the game greys out (Judgement with full jokers, The Fool with nothing to copy, …) and blocked pack
    cards are no longer offered; Aura is not offered on cards that already have an edition; Negative jokers can be
    taken with full slots; choose needs enough hand cards.
  - A rejected move keeps the selection in the real game too (matches the simulator).
  - Take/cancel loop on The Hierophant (832 cancels in one pack): target clicks capped at the card's target count,
    2 target selections per pick, 60-click safety net in the real-game runner.
- **Sim/real prompt mismatch: hand-level order.** Tied hand levels printed alphabetically in the real game (mod order)
  and in hand order in the simulator; on seed U919ZL9K the differing line flipped a near-tie (play 0.47 vs discard
  0.52) at decision 36 and the runs ended at 14 vs 8 rounds. Ties now sort by hand order on both sides; with that, the
  simulator replays the real run exactly (329/329 decisions, 14 rounds).
- **Sim/real prompt mismatch: per-frame joker values.** The real game recomputes Cloud 9, Steel Joker, Stone Joker,
  Driver's License, Joker Stencil, Swashbuckler and Throwback values every frame (card.lua `Card:update`); jackdaw only
  when scoring, so their descriptions read e.g. "(Currently $0)" instead of "$4". On seed TZIUSW9J that flipped a
  near-tie click and the runs ended at 1 vs 19 rounds; the simulator now computes the same values (replays 1 round).
- Self-play sampling temperature 0.4 → 0.3 (sampled games had slid to ~2 rounds while greedy held ~5–6).
- **Self-play credit: best game per seed** (`--credit best`). With PPO's clip, a near-certain click can only be pushed
  down after a loss, never much further up after a win, so the training weights kept flattening: their greedy test held
  ~5.3 rounds while their sampled games fell 4.1 → 1.2 (iterations 11–19), poisoning the training data. The champion
  itself samples fine (raw0010: greedy 6.54, T 0.1 6.62, T 0.3 5.08, T 0.6 2.00). Training weights were reset to the
  champion and now learn only from each seed's best sibling game (positive examples sharpen instead of flatten).
- **Simulator scored played cards in click order.** The real game scores the selection left to right as it sits in the
  hand; jackdaw got the click order, so Hanging Chad, Photograph, Mult-vs-xMult order and per-card luck (Lucky, Glass,
  Bloodstone) were wrong in every raw-click simulation (seed X8AXHXRD: real 13 rounds vs sim 7). Play/discard indices
  are now sorted.
- Simulator blind previews use each boss's own multiple (The Wall x4, The Needle x1, Violet Vessel x6), not a flat x2.
- **Descriptions no longer truncated** (both sides): the localization parser stopped at the first `{},` inside a line,
  cutting 16 texts short (Fibonacci, Aura and Hone were bare names; Mail-In Rebate, Campfire, Hack, To Do List, Seance,
  Sixth Sense, Ankh, Hex, Wraith, Wheel of Fortune, Glow Up, Illusion, Showman lost their second half).
- **Simulator leaked face-down cards' ranks.** With a face-down card in hand, the mod lists the hand by card id with
  hidden cards last, so a hidden card's place reveals nothing; the simulator kept the rank-sorted order, where `??`
  between a 9 and a 6 must be a 7 or 8. Training learned from that leak and the runs diverged (seed C6HRB2UR: real 12
  vs sim 11; with the fix 12 = 12). The mod now compares ids numerically (text order broke at 999 → 1000).
- **jackdaw's Satellite never paid out**: it reads `ability["planet_types_used"]`, which jackdaw never sets; the real
  game pays $1 per distinct Planet used. The adapter now syncs the count from jackdaw's own consumable usage before
  every engine step (seed 2IRGPA5L: sim $1 short from the first cash-out, real 2 vs sim 3; with the fix 2 = 2).
- **First real-game win**: raw0032 on seed MST5TRB3 beat Ante 8 (Cerulean Bell, playable since the audit fixes) and
  reached round 26 in endless; simulator twin identical.
- RL iterations record every game (self-play, new weights, champion per seed); the Stage 2 chart plots all of them.

## v1.1 — Stage 2: raw clicks, pure RL (2026-10-07)

- **Raw action interface** (`LAYA_ACTIONS=raw`, now the default). Laya clicks like a player: each call is one
  `choice` question over primitive moves (`select K♥`, `deselect K♥`, `play selected`, `discard selected`,
  `use Strength on selected`, `take … on selected`, shop and blind moves). A decision takes several calls. The state
  shows only what the game screen shows for the selection (`Selected (2/5): K♥ K♦ = Pair (25 x 3)`); the pre-built
  combinations, hand labels, score estimates and discard reasons of Stage 1 are gone (`LAYA_ACTIONS=combo` keeps them).
- Teacher card plays and discards are now 100% expressible (Stage 1: 36% / 34%).
- **Fixed a label leak**: Stage 1 appended missing teacher discards with the reason text "(teacher)" (11% of hand
  examples). Raw conversion skips a teacher move that is not among the options instead of appending it.
- Multi-label training (`labels`): any of the teacher's remaining cards is a correct next click.
- **PPO-clipped self-play.** With clicks, plain advantage-weighted updates kept wrecking the policy (iterations 4–6
  all lost the head-to-head by 1.2–2.8 rounds and rolled back): every click of a lost round was pushed down,
  including confident correct ones. Self-play now records log p(click) while playing and trains on the clipped
  surrogate (each click's probability moves at most ±20% per update), 2 epochs per iteration, batch 32, lr 3e-6,
  128 games and 128 head-to-head seeds per iteration, sampling temperature 0.4. First PPO iteration: new champion
  raw0007 (6.09 vs 5.16, paired t +2.8) after three rollbacks.
- **Same-seed credit** (`--group 4 --credit seed`): each seed is played 4 times; a decision in round r is judged
  against the mean final round of the siblings on the same seed that also reached round r, so deal luck cancels
  (same deal, sampled play: 0, 10 and 2 rounds in one test). `--credit best` keeps only each seed's best game.
- **Teacher only for the kickoff** (`raw_init`: imitation of 95,642 teacher clicks from sim0053; held-out click
  agreement 37.7% → 72.0%). Afterwards pure RL; no teacher replay.
- **Random seeds everywhere**: self-play on random seeds; each iteration the new weights and the champion play the
  same fresh random seeds and the title changes hands only on a paired t ≥ 1 win. Real Balatro validates.
- Training moved to a 16 GB GPU box (`run_stage2_n8.sh`); `remote_sync.py` mirrors champions and logs to the PC that
  runs the game. Inference batch sized from GPU memory (16 on 8 GB, 64 on 16 GB).
- Real-game runner keeps the selection by card id, mirrors clicks on screen and skips the 10 s animation wait for clicks.
- **Mod: actions no longer wait out an 8 s timeout.** A background watcher event (non-blocking, non-blockable) sits in
  the base queue for the whole shop, so every buy / leave / pack / reroll settle timed out. The drain check now ignores
  such events like the game does: buy 9 s → 1 s, leave shop 8 s → 1 s, take 9 s → 2.5 s; a 10-round real run takes
  ~5 min instead of ~14. Timed-out settles now log the pending events.
- Validator runs Laya on the PC's GPU (default when available); clicks are instant.
- `record.py`: fixed the ffmpeg font crash on Windows (explicit font file / folder).

## v1.0 — Stage 1 (2026-10-07)

Candidate-action interface, HF teacher imitation, simulator self-play in jackdaw with sim/real twin runs; champion
`sim0053` (9.01 rounds on 128 simulator seeds, 7.9 rounds over 81 real random-seed runs, best 17).
