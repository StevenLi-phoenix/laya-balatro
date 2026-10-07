# laya-balatro — a non-generative decision model learns to play Balatro

[Laya](https://huggingface.co/convaiinnovations/laya) (ConvAI, 421M-parameter ModernBERT-large) cannot
generate text. It reads a state and scores a list of options. This repo turns
[Balatro](https://www.playbalatro.com/) into exactly that kind of problem and trains Laya on it, in a
simulator and in the real game.

- **Interface**: every decision point becomes one `choice` question. The game state is rendered as text with
  full effect descriptions (jokers, boss blinds, tags, planets, enhancements), and the legal moves are enumerated
  as options (which 1–5 cards to play or discard, what to buy/sell/use, which pack card to take, play or skip a blind).
- **Real game**: a modded Balatro ([balatro-agent](https://github.com/Arcadi4/balatro-agent) + `mod/balatro-agent.patch`)
  exposes JSON-RPC over a named pipe; `bridge.py`/`live.py` drive it.
- **Simulator**: [jackdaw](https://github.com/TylerFlar/jackdaw-balatro), a Python re-implementation of Balatro
  (~270 decisions/s), aligned with the real game until seed-for-seed replays match.
- **Training**: imitation of a heuristic teacher ([makemake/5k-balatro-games](https://huggingface.co/datasets/makemake/5k-balatro-games)),
  then self-play with outcome-weighted fine-tuning in the simulator. The real game is only the test set.

Weights: see the Hugging Face model repo linked in the release notes. Write-up with charts: [`reports/REPORT.md`](reports/REPORT.md).

## Results (Red Deck, White Stake)

| model | simulator (128 fixed seeds) | real Balatro (random seeds) |
|---|---|---|
| stock Laya, zero-shot | – | 0.3 rounds |
| imitation, names only (gen1) | – | 5.3 rounds |
| imitation, full descriptions (`rich_init`) | 7.50* | 7.8 rounds |
| **self-play champion `sim0053`** | **9.01** | **8.0 rounds over 81 runs, best 17 (Ante 6), 0 wins** |

\* scored on 64 seeds. "Rounds" = blinds beaten per run (24 = win at Ante 8).

![real game](reports/real_game.png)

Findings:

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
  report.py    charts + reports/REPORT.md
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
powershell -File run_simloop.ps1 --init ckpt/rich_init.pt            # self-play (state in runs_sim/state.json)
python -m laya_player.realloop                                       # play the champion in the real game
python -m laya_player.report                                         # charts
```

Game text and assets are not redistributed here; `desc.py` extracts them from your own installation.

## Credits and licenses

Code: MIT (see `LICENSE`). Laya: Apache-2.0, ConvAI Innovations. Teacher data: makemake/5k-balatro-games (MIT).
Simulator: jackdaw (MIT). Mod: balatro-agent by 4rcadia (MIT). Balatro is © LocalThunk / Playstack; this is an
unaffiliated fan research project.
