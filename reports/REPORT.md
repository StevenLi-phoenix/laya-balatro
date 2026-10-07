# Laya plays Balatro: results

Champion: **sim0053.pt**, simulator validation 9.01 rounds over 128 fixed seeds after 101 self-play iterations.

## Real game (test set)

81 runs on random seeds: mean 7.89 rounds won, best 17, mean max ante 3.1, 0 wins. The simulator replay of the same seed matched the real round count in 73/81 runs.

![real](real_game.png)

## Simulator self-play

![sim](sim_training.png)

Head-to-head checks (challenger beat the champion on the validation seeds, then both played 64 fresh seeds):

| iter | challenger | champion |
|---|---|---|
| 99 | 7.94 | 8.00 |
| 101 | 7.86 | 8.31 |

## Imitation of the HF teacher (V68 heuristic, 74.6% win rate in Pylatro)

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
