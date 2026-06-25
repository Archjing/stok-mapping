# Harness Iteration Brief - 2026-06-25 - I43 强市场 Panel 上限实验

## 一句话结论

把强市场研究 panel 从 `120` 扩到 `200` / `300`，确实能明显减少“核心成分被截断”的问题，也能提高沪深300核心权重可达性；但完整 Top20 可达权重几乎没有跨越式改善，仍低于 I39 设定的 `35%` 研究门槛。

所以 I43 不能直接进入新交易策略实现。下一步应继续做 panel / universe 治理，但方向要从“单纯扩大数量”转为“显式保留 CSI300 Top 权重成分，并修复少数成分的行业 / 元数据 / panel 构建缺口”。

## 实验变量

只改变一个变量：

```yaml
universe.walk_forward_limit
```

| 组别 | 配置 | 说明 |
| ---- | ---- | ---- |
| baseline | `120` | I37/I40 原始口径 |
| treatment | `200` | I43 扩 panel 实验 |
| treatment | `300` | I43 扩 panel 实验 |

保持不变：

- `qfq_asof`
- point-in-time universe
- 历史权重 as-of 口径
- 成本口径
- I37 候选和 fold 划分
- 不运行 admission，不输出交易信号

## 运行命令

```bash
./.venv/bin/python -m phase0.cli strategy-core-reachability-diagnostic --config config.main_strategy_i43_panel_limit_200_20260625.yaml --candidate-folds reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/admission/strategy_admission_candidate_folds.csv --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_43__strong_market_panel_limit_experiment/panel_limit_200/core_reachability
```

```bash
./.venv/bin/python -m phase0.cli strategy-core-reachability-diagnostic --config config.main_strategy_i43_panel_limit_300_20260625.yaml --candidate-folds reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/admission/strategy_admission_candidate_folds.csv --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_43__strong_market_panel_limit_experiment/panel_limit_300/core_reachability
```

```bash
./.venv/bin/python -m phase0.cli strategy-missing-core-audit --config config.main_strategy_i43_panel_limit_200_20260625.yaml --missing-reasons reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_43__strong_market_panel_limit_experiment/panel_limit_200/core_reachability/strategy_core_reachability_failure_reasons.csv --candidate-folds reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/admission/strategy_admission_candidate_folds.csv --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_43__strong_market_panel_limit_experiment/panel_limit_200/missing_core_audit
```

```bash
./.venv/bin/python -m phase0.cli strategy-missing-core-audit --config config.main_strategy_i43_panel_limit_300_20260625.yaml --missing-reasons reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_43__strong_market_panel_limit_experiment/panel_limit_300/core_reachability/strategy_core_reachability_failure_reasons.csv --candidate-folds reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/admission/strategy_admission_candidate_folds.csv --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_43__strong_market_panel_limit_experiment/panel_limit_300/missing_core_audit
```

## 核心结果

| panel 上限 | 平均可达核心权重 | 最低可达核心权重 | 平均完整 Top20 可达权重 | 最低完整 Top20 可达权重 | 缺失原因行数 | 缺失股票数 |
| ----------: | ---------------: | ---------------: | ----------------------: | ----------------------: | -----------: | ---------: |
| 120 | 55.38% | 52.01% | 32.69% | 29.89% | 10570 | 44 |
| 200 | 57.72% | 55.20% | 32.73% | 29.89% | 4979 | 30 |
| 300 | 58.55% | 56.50% | 32.82% | 30.73% | 3265 | 23 |

解释：

- 扩 panel 对“核心权重”有帮助：平均可达核心权重从 `55.38%` 提高到 `58.55%`。
- 扩 panel 对“完整 Top20”帮助很小：平均 Top20 可达权重只从 `32.69%` 提高到 `32.82%`。
- 所以 I39 的完整 Top20 `35%` 门槛仍未达成。

## 缺失原因变化

| panel 上限 | `beyond_walk_forward_limit` 缺失权重 | `ranked_out_or_balanced_out` 缺失权重 | `universe_member_but_panel_missing` 缺失权重 |
| ----------: | -----------------------------------: | ------------------------------------: | ------------------------------------------: |
| 120 | 50.4466 | 2.6715 | 0.1660 |
| 200 | 21.4540 | 2.7521 | 0.5573 |
| 300 | 9.2103 | 2.7521 | 0.8236 |

这说明单纯扩大 panel 后，`walk_forward_limit` 截断大幅下降，但没有完全消失；同时更深层的问题开始显现：

- 少数股票仍被 ranking / industry balance 排除。
- 少数股票进入 universe 后仍在 panel 中缺部分日期。
- `SH.600837` 在报告中缺名称和行业，提示还有元数据 / 行业字段治理问题。

## 代表性剩余缺口

panel=300 后仍然靠前的缺口：

| 股票 | 名称 | 行业 | 缺失折数 | 缺失日 | 缺失权重 | 主要原因 |
| ---- | ---- | ---- | -------: | -----: | -------: | ---- |
| `SH.600000` | 浦发银行 | 银行 | 3 | 725 | 3.5659 | 截断 / 排名或均衡剔除 |
| `SH.600016` | 民生银行 | 银行 | 2 | 484 | 2.3901 | 截断 / 排名或均衡剔除 |
| `SH.600837` |  |  | 2 | 295 | 1.4757 | 截断 / panel 缺失 |
| `SH.601229` | 上海银行 | 银行 | 3 | 309 | 1.4014 | 截断 |
| `SH.601816` | 京沪高铁 | 铁路 | 1 | 243 | 1.2809 | 截断 |

## 决策

I43 的实验回答了一个关键问题：

> 只把 panel 从 120 扩大到 200 或 300，够不够？

答案：不够。

它能减少候选池截断，但不能让完整 Top20 稳定超过 `35%`。因此下一步不应把 I43 变成交易策略，而应继续做一个更精确的 universe / panel 治理方案。

## 下一步建议

I44 建议做 `csi300_core_seed_panel` 只读实验：

1. 在常规 PIT universe 之外，显式把 as-of 可见的 CSI300 Top 权重核心成分 seed 进研究 panel。
2. 基础过滤只剔除不可交易、无价格、无复权、严重缺行业或停牌不可用标的。
3. 保留常规 120/200/300 实验作为对照，不污染主线默认 universe。
4. 先只跑 `strategy-core-reachability-diagnostic` 和 missing-core audit。
5. 只有完整 Top20 可达权重稳定超过 `35%`，才预注册新的强市场核心参与交易策略。

这一步的目的不是“扩大股票越多越好”，而是确保强市场参与型策略的候选池真的包含沪深300高权重核心成分。

## 产物

- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_43__strong_market_panel_limit_experiment/panel_limit_reachability_summary.csv`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_43__strong_market_panel_limit_experiment/panel_limit_missing_core_classification_summary.csv`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_43__strong_market_panel_limit_experiment/panel_limit_200/core_reachability/`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_43__strong_market_panel_limit_experiment/panel_limit_300/core_reachability/`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_43__strong_market_panel_limit_experiment/panel_limit_200/missing_core_audit/`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_43__strong_market_panel_limit_experiment/panel_limit_300/missing_core_audit/`

## Agent 管理说明

本轮按用户要求不再新建子 agent。执行方式为 Team Lead 直接推进、用本地产物做可复查核验，并继续记录归档。
