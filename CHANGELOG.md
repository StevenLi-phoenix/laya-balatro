# Changelog

## v1.2 (unreleased)

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
