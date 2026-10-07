# laya-player — Laya 自己玩 Balatro，并边玩边进化

[Laya](https://huggingface.co/convaiinnovations/laya)（ConvAI，421M ModernBERT-large，非生成式决策模型）
不能生成文本，只能「给定状态 + 候选项 → 每个候选的概率」。所以这里把 balatro-agent 的 MCP/mod 改造成
**候选动作接口**：每个决策点把游戏状态压成一行文本，枚举合法动作（出牌组合、弃牌方案、买/卖/跳过…）作为
`choice` 选项，Laya 选一个，执行，再观察。

> **v1.2（Stage 2 结束，2026-10-07）**：默认接口已改为原始点牌（`select K♥` … `play selected`），老师只用于开局，
> 之后在 jackdaw 模拟器里纯强化学习，从 v1.2 起部分出牌回合用模拟器搜索打标签。最终冠军 `raw0056`：同 128 个
> 新 seed 平均 5.63 关，和搜索前的 `raw0046`（5.70）没有差别；真实游戏 Stage 2 全部对局平均 5.7 关，`raw0032`
> 第一次通关（seed MST5TRB3，打到第 26 关）。下文描述的是 Stage 1 的组合候选接口（`LAYA_ACTIONS=combo`），
> 最新结果见英文 [README](README.md) 和 [CHANGELOG](CHANGELOG.md)。

```
Balatro + balatro-agent mod ──named pipe JSON-RPC──▶ bridge.py ─▶ live.py (状态→canonical, 动作→RPC)
                                                                     │
                       game.py: canonical state → 文本 + 候选动作（出牌估分、弃牌追同花/顺子…）
                                                                     │
                                       policy.py: Laya choice question → 选项概率 → 采样/训练
```

TS 的 MCP server 与这个 Python 客户端共用同一个 mod 管道（单客户端）：自对弈时请关闭占用
`\\.\pipe\balatro-mcp` 的 MCP 客户端（Codex/opencode）。

## 训练数据

HF 上没有人类对局数据；用的是 **[makemake/5k-balatro-games](https://huggingface.co/datasets/makemake/5k-balatro-games)**：
V68 启发式在 Pylatro 无头模拟器里生成的 5,000 局 / 113 万条决策（蓝牌组白注，74.6% 胜率，MIT）。
`hf_convert.py` 把它的 token 化观测（`tokens[160,47]` + scalars）解码成与实机完全相同的文本状态，
老师的动作 id 解码成候选动作并作为标签（按阶段配额采样：出牌 55% / 商店 25% / 卡包 12% / 盲注 8%）。

## 代际

| 代 | 来源 |
|---|---|
| gen0 | 原版 Laya 零样本（基线） |
| gen1 | 在 HF 老师数据上模仿学习（`pretrain.py`，训练顶部 6 层 + 决策头） |
| gen2+ | 每玩 N 局，用自己的决策微调：本回合过关的出牌/弃牌 = 正样本，失败回合 = 负样本（unlikelihood），商店/卡包/盲注按整局过关数相对基线加权；混入同量 HF 回放防遗忘 |

对比表自动写到 `runs/generations.md`（每局详情 `runs/runs.jsonl`，每步决策 `runs/decisions/*.jsonl`）。

## 模拟器训练，实机只做测试集

实机一局 10–20 分钟太慢，所以训练搬到 [jackdaw](https://github.com/TylerFlar/jackdaw-balatro) Python 模拟器
（`sim.py`，约 270 决策/秒），真 Balatro 只用来验证。

- **完整信息提示**（`desc.py`）：从 `Balatro.exe` 里抽出 `en-us.lua`，用卡牌的 `loc_vars` 填好当前数值，
  小丑/Boss/标签/星球/附魔都以「名字: 效果原文」给 Laya（不是只给名字）。`ckpt/rich_init.pt` = 在这种文本上重新模仿 HF。
- **保真度**：同一 seed 在实机和模拟器各跑一次（孪生对局）。修过的偏差：牌组花色顺序、存档未解锁的小丑
  （读 `meta.jkr`）、新牌插入牌组顶部、卡包手牌排序、Bonus/Mult 附魔识别。Boss 抽取仍有未解的差异，孪生对局强制用实机观察到的 Boss。
  sim0053 的 80 局随机 seed 实机对局里 72 局与模拟器回合数完全一致。
- **`simloop.py`**：每轮 128 局自对弈（T=0.6），按「之后还过了几关」（reward-to-go，按回合基线）加权微调，
  lr 3e-6；在 128 个固定验证 seed 上贪心评分。超过最佳分后还要在 64 个新 seed 上和冠军正面对比才晋升，
  否则继续在自己的权重上训练，掉分超过 1 关才回滚到冠军。
- **`realloop.py`**：实机持续用当前冠军（CPU，贪心，随机 seed，通关后进入无尽），每局再用模拟器复盘同一 seed，
  结果写 `runs/real_test.md`。mod 卡死/崩溃时自动重启游戏。
- **`imitate.py`**：在大批 HF 老师数据上分块模仿，每块后用模拟器验证。

### 结果（2026-10-07）

| 检查点 | 模拟器验证（128 seed） | 实机（随机 seed） |
|---|---|---|
| rich_init（模仿） | 7.50* | 7.83 关，6 局 |
| sim0053（自对弈冠军） | **9.01** | **7.96 关，80 局，最好 17 关（Ante 6），0 胜** |

\* 64 seed 时的分数。

结论：

1. 自对弈把 7.5 提到 ~9.0 后就平台了。
2. **模仿老师反而降分**：16 万条老师决策让一致率 77%→84%，模拟器分数却从 9.01 掉到 7–8.3。
   老师在 Pylatro + 蓝牌组下 74.6% 胜率，但 84% 一致率下每 6 个决策错 1 个，300 个决策一局里误差累积；
   混入的 HF 回放（还是旧的只有名字的格式）也一直在拖累自对弈，关掉后（`--replay 0`，现在的默认）分数稳定在 ~9.0。
3. 下一步若要再突破：在 jackdaw 里复现老师启发式，对 Laya 自己走到的局面打标签（DAgger），而不是离线模仿。

## 运行

```bash
uv venv .venv -p 3.12 && uv pip install laya==0.3.21 polars huggingface_hub
uv pip install torch --index-url https://download.pytorch.org/whl/cu128
python -m laya_player.hf_convert --shards 0-19 --per-shard 3000   # → data/hf_train.jsonl
python -m laya_player.pretrain                                    # GPU，→ ckpt/gen1.pt
python -m laya_player.evolve --runs-per-gen 2                     # 预训练期间 gen0 在 CPU 上玩
python -m laya_player.evolve --report                             # 只打印代际对比
python -m laya_player.desc                                        # 抽取本地化 + loc_vars（需本机 Balatro）
powershell -File run_simloop.ps1                                  # 模拟器自对弈（后台，simloop.pid）
python -m laya_player.realloop --default ckpt/rich_init.pt        # 实机测试冠军（另开，需游戏 + mod）
powershell -File run_imitate.ps1 -ConvertPid <pid>                # 大批模仿 → 再接 simloop
```

状态在 `runs_sim/state.json`（`champion` / `best` / `work`），日志 `runs_sim/simloop.log`、`runs/evolve.log`。
