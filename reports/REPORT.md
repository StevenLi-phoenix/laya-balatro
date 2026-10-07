# Laya plays Balatro: results (v1.1)

## Stage 2 (v1.1+): raw clicks, pure RL

Laya clicks like a player (`select K♥` ... `play selected`): one choice question per click, several clicks per decision, no pre-built combinations, hand labels or score estimates. The HF teacher is used once (kickoff imitation from sim0053); afterwards training is pure RL in the simulator on random seeds. Each iteration the new weights and the champion play the same fresh random seeds; a paired t >= 1 win takes the title. Real Balatro validates the champion on random seeds.

Kickoff (teacher clicks, held-out games): agreement 37.7% before -> **72.0%** after (hand 71.2%, shop 66.0%, pack 83.3%).

RL: 38 iterations, champion **raw0035.pt**.

![rl](stage2_rl.png)

| iter | train | new weights | champion | paired t | champion after |
|---|---|---|---|---|---|
| 24 | 5.12 | 6.11 | 6.01 | +0.3 | raw0021.pt |
| 25 | 6.38 | 5.63 | 5.75 | -0.3 | raw0021.pt |
| 26 | 4.48 | 6.69 | 6.35 | +0.9 | raw0021.pt |
| 27 | 5.02 | 6.41 | 6.43 | -0.1 | raw0021.pt |
| 28 | 6.49 | 6.14 | 6.20 | -0.1 | raw0021.pt |
| 29 | 5.26 | 5.84 | 5.62 | +0.4 | raw0021.pt |
| 30 | 5.87 | 5.95 | 6.25 | -0.7 | raw0021.pt |
| 31 | 5.68 | 5.09 | 6.47 | -3.3 | raw0021.pt |
| 32 | 5.11 | 6.23 | 5.73 | +1.7 | raw0032.pt |
| 33 | 5.49 | 5.90 | 5.54 | +1.4 | raw0033.pt |
| 34 | 6.20 | 6.02 | 5.73 | +1.3 | raw0034.pt |
| 35 | 5.61 | 6.50 | 6.17 | +1.2 | raw0035.pt |
| 36 | 6.07 | 5.39 | 5.73 | -1.5 | raw0035.pt |
| 37 | 5.52 | 5.67 | 5.42 | +0.8 | raw0035.pt |
| 38 | 5.86 | 5.08 | 6.16 | -2.5 | raw0035.pt |

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
| raw0035.pt | 12 | 7.67 | 15 | 3.1 | 0 | 10/12 |

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
