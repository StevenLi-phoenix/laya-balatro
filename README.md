# laya-balatro — a non-generative decision model learns to play Balatro

[![Laya beats real Balatro on seed UP2YINZS (click for the video)](reports/win_UP2YINZS.jpg)](https://huggingface.co/Steven10429/laya-balatro/blob/main/media/laya_balatro_win_UP2YINZS.mp4)

*v1.3: Laya `raw0056` beats real Balatro (Red Deck, White Stake) on seed UP2YINZS, 27 rounds, every click its own.
The seed was picked by the simulator; see [v1.3](#v13-2026-10-09-a-recorded-real-win-stages-3-and-4-hosted-decision-apis).*

[Laya](https://huggingface.co/convaiinnovations/laya) (ConvAI, 421M-parameter ModernBERT-large) cannot
generate text. It reads a state and scores a list of options. This repo turns
[Balatro](https://www.playbalatro.com/) into exactly that kind of problem and trains Laya on it, in a
simulator and in the real game.

- **Interface**: every decision point becomes `choice` questions. The game state is rendered as text with
  full effect descriptions (jokers, boss blinds, tags, planets, enhancements).
  - **v1.1+ (Stage 2, default)**: raw clicks. Each call offers primitive moves (`select K♥`, `deselect K♥`,
    `play selected`, `discard selected`, `use Strength on selected`, buy/sell/reroll/leave, take a pack card, play or
    skip a blind); a decision takes several calls. No pre-built combinations, hand labels or score estimates.
  - v1.0 (Stage 1, `LAYA_ACTIONS=combo`): pre-built plays/discards with hand type and a score estimate.
- **Real game**: a modded Balatro ([balatro-agent](https://github.com/Arcadi4/balatro-agent) + `mod/balatro-agent.patch`)
  exposes JSON-RPC over a named pipe; `bridge.py`/`live.py` drive it.
- **Simulator**: [jackdaw](https://github.com/TylerFlar/jackdaw-balatro), a Python re-implementation of Balatro
  (~270 decisions/s), aligned with the real game until seed-for-seed replays match.
- **Training**: a one-time imitation kickoff on a heuristic teacher ([makemake/5k-balatro-games](https://huggingface.co/datasets/makemake/5k-balatro-games)),
  then pure RL (outcome-weighted self-play) in the simulator on random seeds; each iteration the new weights play
  the champion on the same fresh random seeds. Real Balatro validates the champion. From v1.2 a share of hand
  decisions is also labelled by a simulator search (expert iteration, within a trust region).

Weights and videos (the v1.3 win, side-by-side API runs): [Steven10429/laya-balatro](https://huggingface.co/Steven10429/laya-balatro). Changes: [`CHANGELOG.md`](CHANGELOG.md). Write-up with charts: [`reports/REPORT.md`](reports/REPORT.md).

## Results (Red Deck, White Stake)

### v1.3 (2026-10-09): a recorded real win, Stages 3 and 4, hosted decision APIs

| | result |
|---|---|
| real win, recorded | `raw0056` on seed UP2YINZS: 27 rounds, Ante 10; simulator twin 27 |
| how the seed was found | 2,592 fresh random seeds in the simulator, raw0056 won 3 (0.12%); replayed alone on the validator PC, then real |
| random seeds, real game | 9 recorded runs today, best 14, no win; one win in 541 earlier raw-click runs |
| Stage 3: computed notes in the options | 45 iterations; champions with notes 4.59–5.21 on the 128 fixed seeds vs raw0056's 5.63 without |
| Stage 4: teacher imitation (aborted) | agreement 70.8% → 81.1%, ladder 5.63 → 4.02–4.89 |
| hosted decision APIs, zero-shot (64 seeds) | Jev 1.13 0.02 rounds, GPT-6 Luna Decisions 0.20, Laya raw0056 6.06 |

1. **The simulator now draws the real game's bosses.** Steamodded draws the same 'boss' pseudoseed as jackdaw but
   indexes a pool built by iterating a hash table, so the order is LuaJIT's, not alphabetical. A mod RPC reads that
   order per ante; all 646 recorded real boss sequences now match. Before this, no simulated seed could predict a
   real run, and twin replays had to force the bosses.
2. **So the simulator can pick the seed.** A seed raw0056 wins in jackdaw, replayed alone on the validator PC (batched
   play can flip near-ties), won in real Balatro move for move. The play is Laya's; the seed is chosen.
3. **Telling Laya the consequences did not help** (Stage 3), and **imitating the teacher again made it worse**
   (Stage 4), as in Stage 1.
4. **Zero-shot hosted decision models barely clear a blind**: they skip the first blind or play single cards.

![decision models](reports/decision_models.png)

### Stage 2 (v1.1–v1.2, ended 2026-10-07): raw clicks, pure RL, then search labels

| model | simulator (same 128 fresh seeds, greedy) | real Balatro (random seeds) |
|---|---|---|
| `raw_init` (one-time teacher kickoff, clicks) | 1.64 | 0.25 rounds (4 runs) |
| `raw0008` (PPO + same-seed credit), v1.1 champion | – | 4.1 rounds (7 runs, best 16) |
| `raw0032` | – | **first win**: seed MST5TRB3, beat Ante 8, round 26 in endless |
| `raw0046`, last champion before search labels | 5.70 (median 3.5) | 5.7 rounds (20 runs, best 19) |
| **`raw0056`**, final Stage 2 champion (search labels) | **5.63 (median 4)**, vs raw0046 −0.07, t −0.2 | 4.9 rounds (60 runs, best 17) |

All 285 real Stage 2 runs average 5.7 rounds; the simulator twin of the same seed reached the same round in 272 of 285.
Stage 2 did not overtake Stage 1's 7.9 real rounds.

![stage 2](reports/stage2_rl.png)

1. **Clicks make every teacher move expressible** (card plays and discards 100%, Stage 1: 36% / 34%) and removed a
   label leak in the Stage 1 teacher data. The cost is a much harder start: the kickoff policy matches 72% of teacher
   clicks, but whole decisions compound that error, and it plays pairs plus junk without ever discarding.
2. **Plain advantage-weighted updates wrecked the click policy** (iterations 3–6: four head-to-head losses, three
   rollbacks, across two learning rates). **PPO's clipped surrogate fixed it**: the next two iterations both took the title.
3. **Same-seed credit**: each seed is played 4 times and decisions are judged against siblings on the same deal; one
   deal produced 0, 10 and 2 rounds from sampled play, so seed-level baselines are mostly luck.
4. **Real-game speed**: a mod wait ran into its 8 s timeout on every shop/pack action (a background event never
   drains); ignoring non-blocking background events cut a 10-round run from ~14 to ~4 minutes.
5. **Simulator fidelity** (v1.2): five sim/real mismatches found by twin replays and fixed (hand-level print order,
   per-frame joker values, scoring order, face-down card order, Satellite payouts).
6. **Search labels** (v1.2): with a fixed shop rule (24 seeds), search hand play reaches 10.46 rounds and greedy hand
   play 8.75, while Laya's champion averages ~6.2 with its own shop play. Copying its clicks outright broke the policy; within a trust
   region it gave two promotions, but the same-seed ladder shows no gain. Laya's click distribution is nearly 0/1, and
   training did not move the third of searched clicks it disagreed with (fit 0.683 → 0.683). Softening that
   distribution is the open problem.

### Stage 1 (v1.0): pre-built candidate moves

| model | simulator (128 fixed seeds) | real Balatro (random seeds) |
|---|---|---|
| stock Laya, zero-shot | – | 0.3 rounds |
| imitation, names only (gen1) | – | 5.3 rounds |
| imitation, full descriptions (`rich_init`) | 7.50* | 7.8 rounds |
| **Stage 1 champion `sim0053`** | **9.01** | **7.9 rounds over 81 runs, best 17 (Ante 6), 0 wins** |

\* scored on 64 seeds. "Rounds" = blinds beaten per run (24 = win at Ante 8).

![real game](reports/real_game.png)

Stage 1 findings:

1. **The simulator is a faithful proxy.** Replaying each real run's seed in jackdaw with the same weights gave
   the identical round count in 73 of 81 runs. Getting there took fixing several mismatches: deck suit order, jokers
   still locked on the save profile, new cards going to the top of the deck, booster-pack hand order, and how
   Bonus/Mult enhancements are detected. One boss-blind selection difference is still unexplained, so twin runs
   force the bosses seen in the real game.
2. **Self-play helped, then plateaued** (7.5 → 9.0 in ~50 iterations, flat for the next 50).
   ![sim](reports/sim_training.png)
3. **Imitating the teacher more closely made Laya worse.** The teacher wins 74.6% of its games (22.4 rounds), but
   it played the Blue Deck in a different simulator. Training on 160k of its decisions raised agreement from 77% to
   84% while the simulator score fell from 9.01 to 7–8.3. Mixing those teacher examples into self-play
   ("replay") also pulled every update down; with replay off, self-play holds ~9.0.
   ![imitation](reports/imitation.png)
4. **Noisy validation needs a second check.** Iteration 101 scored 9.21 on the validation seeds but lost
   7.86 vs 8.31 to the champion on 64 fresh seeds, so it was not promoted.

## Layout

```
laya_player/
  bridge.py    JSON-RPC client for the mod (named pipe, PeekNamedPipe polling)
  live.py      real-game payload -> canonical state; candidate actions -> RPC calls
  game.py      canonical state -> prompt text; candidate generation (play/discard/shop/pack/blind)
  desc.py      effect text from the game's own localization + loc_vars, filled with live values
  sim.py       jackdaw adapter (+ fidelity patches: unlock filter, deck insertion, boss forcing)
  hf_convert.py  decode the HF dataset's token observations into the same text/options
  policy.py    Laya choice-question wrapper: logits, sampling, weighted CE / unlikelihood training
  pretrain.py  imitation on HF data        imitate.py  chunked imitation with sim validation
  simloop.py   self-play training loop     realloop.py champion vs real game + sim twin replay
  evolve.py    real-game run driver        record.py   record a real run with decision subtitles
  report.py    charts + reports/REPORT.md  remote_sync.py  mirror a remote trainer's champion + logs
  search.py    simulator search for hand decisions (labels for self-play)
  ladder.py    same-seed comparison of checkpoints
  calc.py      computed consequences in the options (Stage 3, LAYA_CALC=1) + the real-game twin
  teach.py     chunked teacher imitation with the ladder after each chunk (Stage 4)
  screen.py    simulator screening of fresh seeds for wins
  apiplay.py   hosted decision APIs (OpenRouter) on the same click interface
  compare_video.py  side-by-side real-game videos
  boss_order.json   the real game's boss pool order per ante (mod RPC boss_pool_order)
run_stage2_n8.sh         Stage 2 on a Linux GPU box: kickoff imitation, then pure RL (simloop)
run_stage3_n8.sh, run_stage4_n8.sh  Stages 3 and 4 on the GPU box
mod/balatro-agent.patch  changes to the mod (seed/won/ability in state, shop-settle guard, go_to_menu, endless_mode)
runs/, runs_sim/         logs and per-run results behind the report
```

## Reproduce

Windows, Python 3.12, CUDA GPU (8 GB is enough), Balatro with [Steamodded](https://github.com/Steamodded/smods) +
[Lovely](https://github.com/ethangreen-dev/lovely-injector) and the patched balatro-agent mod.

```bash
uv venv .venv -p 3.12
uv pip install laya==0.3.21 polars huggingface_hub matplotlib pywin32 "jackdaw @ git+https://github.com/TylerFlar/jackdaw-balatro@e66de78"
uv pip install torch --index-url https://download.pytorch.org/whl/cu128
BALATRO_EXE="/path/to/Balatro.exe" python -m laya_player.desc       # effect text from YOUR copy of the game
python -m laya_player.hf_convert --per-shard 1500 --out data/hf_rich.jsonl
python -m laya_player.pretrain --data data/hf_rich.jsonl --out ckpt/rich_init.pt
# Stage 2 (raw clicks) on a GPU box (Linux): kickoff from a Stage 1 checkpoint, then pure RL
./run_stage2_n8.sh                                                   # needs ckpt/sim0053.pt and data/*.lua/json
# on the Windows PC with the game:
python -m laya_player.remote_sync --host <gpu-box>                   # pulls the champion every 2 min
python -m laya_player.realloop                                       # play the champion in the real game
python -m laya_player.report                                         # charts
```

Game text and assets are not redistributed here; `desc.py` extracts them from your own installation.

## Credits and licenses

Code: MIT (see `LICENSE`). Laya: Apache-2.0, ConvAI Innovations. Teacher data: makemake/5k-balatro-games (MIT).
Simulator: jackdaw (MIT). Mod: balatro-agent by 4rcadia (MIT). Balatro is © LocalThunk / Playstack; this is an
unaffiliated fan research project.
