# Laya plays Balatro: results (v1.2)

## Stage 2 (v1.1+): raw clicks, pure RL

Laya clicks like a player (`select K♥` ... `play selected`): one choice question per click, several clicks per decision, no pre-built combinations, hand labels or score estimates. The HF teacher is used once (kickoff imitation from sim0053); afterwards training is pure RL in the simulator on random seeds. Each iteration the new weights and the champion play the same fresh random seeds; a paired t >= 1 win takes the title. Real Balatro validates the champion on random seeds.

From iteration 48 (v1.2) a quarter of self-play hand turns are also searched in the simulator (`search.py`): every play scored exactly, candidate plays and discards rolled out on reshuffled decks, no draw order or RNG seen. The clicks toward the best moves become a soft target: the playing policy moved a step (0.3; 0.5 from iteration 59) toward them. Laya's interface is unchanged.

Kickoff (teacher clicks, held-out games): agreement 37.7% before -> **72.0%** after (hand 71.2%, shop 66.0%, pack 83.3%).

RL: 65 iterations, champion **raw0056.pt**.

![rl](stage2_rl.png)

| iter | train | new weights | champion | paired t | champion after |
|---|---|---|---|---|---|
| 51 | 6.61 | 5.44 | 5.67 | -0.7 | raw0050.pt |
| 52 | 6.21 | 5.69 | 5.74 | -0.2 | raw0050.pt |
| 53 | 4.94 | 5.58 | 5.83 | -0.8 | raw0050.pt |
| 54 | 6.46 | 6.21 | 5.83 | +0.9 | raw0050.pt |
| 55 | 6.34 | 5.92 | 5.59 | +0.8 | raw0050.pt |
| 56 | 5.93 | 6.62 | 5.92 | +2.0 | raw0056.pt |
| 57 | 5.86 | 5.16 | 4.99 | +0.7 | raw0056.pt |
| 58 | 6.57 | 5.58 | 5.60 | -0.1 | raw0056.pt |
| 59 | 7.09 | 6.09 | 6.20 | -0.4 | raw0056.pt |
| 60 | 5.46 | 6.52 | 6.43 | +0.3 | raw0056.pt |
| 61 | 6.06 | 5.43 | 5.23 | +0.8 | raw0056.pt |
| 62 | 5.79 | 6.27 | 6.02 | +0.7 | raw0056.pt |
| 63 | 5.07 | 5.68 | 5.57 | +0.4 | raw0056.pt |
| 64 | 7.01 | 6.43 | 6.19 | +0.8 | raw0056.pt |
| 65 | 5.48 | 5.66 | 5.63 | +0.1 | raw0056.pt |

Same 128 fresh seeds, greedy, every checkpoint (deal luck cancels):

| checkpoint | mean rounds | median | >= 9 rounds | wins |
|---|---|---|---|---|
| raw_init | 1.64 | 1.0 | 7/128 | 0 |
| raw0046 | 5.70 | 3.5 | 40/128 | 0 |
| raw0056 | 5.63 | 4.0 | 38/128 | 0 |

raw0056 vs raw0046: -0.07 rounds per seed (paired t -0.2).


Real Balatro validation:

| checkpoint | runs | mean rounds | best | mean ante | wins | sim twin identical |
|---|---|---|---|---|---|---|
| raw_init.pt | 4 | 0.25 | 1 | 1.0 | 0 | 4/4 |
| raw0002.pt | 12 | 5.33 | 12 | 2.5 | 0 | 11/12 |
| raw0007.pt | 3 | 9.00 | 11 | 3.3 | 0 | 3/3 |
| raw0008.pt | 7 | 4.14 | 16 | 2.0 | 0 | 6/7 |
| raw0010.pt | 37 | 6.76 | 17 | 2.9 | 0 | 34/37 |
| raw0021.pt | 51 | 5.33 | 20 | 2.4 | 0 | 50/51 |
| raw0032.pt | 1 | 26.00 | 26 | 9.0 | 1 | 1/1 |
| raw0033.pt | 1 | 5.00 | 5 | 2.0 | 0 | 1/1 |
| raw0034.pt | 6 | 4.83 | 14 | 2.2 | 0 | 6/6 |
| raw0035.pt | 24 | 7.29 | 15 | 3.0 | 0 | 22/24 |
| raw0041.pt | 15 | 4.80 | 11 | 2.2 | 0 | 14/15 |
| raw0044.pt | 6 | 8.17 | 14 | 3.2 | 0 | 5/6 |
| raw0046.pt | 20 | 5.65 | 19 | 2.5 | 0 | 18/20 |
| raw0050.pt | 38 | 5.50 | 14 | 2.4 | 0 | 38/38 |
| raw0056.pt | 60 | 4.93 | 17 | 2.2 | 0 | 59/60 |

![real2](stage2_real.png)

## Stage 1 (v1.0): pre-built candidate moves

Champion **sim0053.pt**: simulator validation 9.01 rounds over 128 fixed seeds after 101 self-play iterations.

Real game: 81 runs on random seeds, mean 7.89 rounds won, best 17, mean max ante 3.1, 0 wins; simulator replay of the same seed matched in 73/81 runs.

![real](real_game.png)

![sim](sim_training.png)

Head-to-head checks (challenger beat the champion on the validation seeds, then both played 64 fresh seeds):

| iter | challenger | champion |
|---|---|---|
| 99 | 7.94 | 8.00 |
| 101 | 7.86 | 8.31 |

Imitation of the HF teacher (V68 heuristic, 74.6% win rate in Pylatro):

![imit](imitation.png)

| chunk | decisions | agreement | sim val |
|---|---|---|---|
| 1 | 20000 | 80.2% | 8.95 |
| 2 | 40000 | 81.0% | 7.87 |
| 3 | 60000 | 82.8% | 7.95 |
| 4 | 80000 | 83.3% | 8.10 |
| 5 | 100000 | 83.9% | 8.34 |
| 6 | 120000 | 84.5% | 8.05 |
| 7 | 140000 | 84.3% | 7.97 |
| 8 | 160000 | 84.2% | 6.99 |
