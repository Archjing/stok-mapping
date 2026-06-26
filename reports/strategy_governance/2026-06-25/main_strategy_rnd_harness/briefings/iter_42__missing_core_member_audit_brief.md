# Harness Iteration Brief - 2026-06-25 - I42 缺失核心成分审计

## 一句话结论

I42 查清了 I41 里那些缺失的沪深300高权重成分：主因不是本地数据库没有这些股票，也不是大面积价格、复权或估值数据缺口，而是它们大多进入了历史 PIT 500 只候选序列，却被当前 `walk_forward_limit = 120` 截在回测 panel 之外。

这说明下一步不该先写新交易策略，而应先修强市场研究用的 universe / PIT panel 口径。

## 审计范围

| 项目 | 数值 |
| ---- | ---: |
| 审计股票数 | 30 |
| fold-symbol 行数 | 67 |
| 覆盖缺失交易日 | 10328 |
| 覆盖缺失权重合计 | 53.2842 |
| 原始缺失原因 | `missing_from_pit_panel` |

原始产物：

- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_42__missing_core_member_audit/missing_core_audit/missing_core_symbol_audit.csv`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_42__missing_core_member_audit/missing_core_audit/missing_core_event_audit.csv`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_42__missing_core_member_audit/missing_core_audit/missing_core_audit_report.md`

## 缺失原因拆解

| 原因 | fold-symbol 行 | 缺失日 | 缺失权重合计 | 解释 |
| ---- | -------------: | -----: | -----------: | ---- |
| `beyond_walk_forward_limit` | 61 | 9746 | 50.4466 | 股票通过基础过滤并进入候选序列，但排名在 120 名之后，没有进入本轮回测 panel |
| `ranked_out_or_balanced_out_of_pit_universe` | 3 | 560 | 2.6715 | 股票进入快照和基础过滤，但未进入 PIT universe 选中名单 |
| `universe_member_but_panel_missing` | 3 | 22 | 0.1660 | 股票进入 PIT universe，但在 panel 构建中仍缺少对应日期的可用记录，需要单独查 qfq_asof / 交易日对齐 |

主因非常集中：`beyond_walk_forward_limit` 占审计缺失权重约 `94.7%`。

## 代表性缺失股票

| 股票 | 名称 | 行业 | 涉及折数 | 缺失日 | 最好排名 | 平均权重 | 主要原因 |
| ---- | ---- | ---- | -------: | -----: | -------: | -------: | ---- |
| `SH.601816` | 京沪高铁 | 铁路 | 5 | 1150 | 19 | 0.6263% | `beyond_walk_forward_limit` |
| `SH.601328` | 交通银行 | 银行 | 3 | 727 | 14 | 0.7339% | `beyond_walk_forward_limit` |
| `SH.600000` | 浦发银行 | 银行 | 4 | 967 | 25 | 0.5281% | `beyond_walk_forward_limit` / 排名或均衡剔除 |
| `SH.600016` | 民生银行 | 银行 | 5 | 1008 | 34 | 0.4883% | `beyond_walk_forward_limit` / 排名或均衡剔除 |
| `SH.600837` |  |  | 4 | 930 | 35 | 0.5018% | `beyond_walk_forward_limit` |
| `SH.600406` | 国电南瑞 | 电气设备 | 4 | 782 | 34 | 0.4842% | `beyond_walk_forward_limit` |

这些股票在数据库里大多有价格、daily_basic 和复权因子覆盖。以 `SH.601328` 为例，全库日线有 `4900` 行、daily_basic 有 `2534` 行、复权因子有 `2534` 行；但在对应 fold 中仍被 120 只 panel 上限挡在外面。

## 对策略研发的含义

I40 说“完整 CSI300 Top20 可达权重只有约 31% 到 34%，略低于 35% 门槛”。I42 进一步说明，这个缺口主要不是数据表缺行，而是当前回测 panel 太窄。

因此不能把 I37 的失败简单解释为“强市场策略选股不好”。更准确的说法是：

1. 历史本地库和 as-of 权重已经足以支撑核心成分研究。
2. 但当前 `walk_forward_limit = 120` 把不少沪深300高权重成分挡在 panel 外。
3. 强市场参与型策略如果继续基于这个 120 只 panel 研发，会天然低配沪深300核心成分。
4. 直接写 I43 新策略会继续撞到同一个 universe / panel 上限问题。

## 下一步建议

I43 应先做 `strong_market_core_panel` 或类似的 research-only universe / panel 治理实验，而不是先写新策略。

最小方案：

| 动作 | 目的 |
| ---- | ---- |
| 保留常规 `walk_forward_limit = 120` 作为原主线对照 | 不破坏既有策略回测口径 |
| 新增强市场专项 panel 实验配置 | 验证扩大到 200 / 300 或引入 CSI300 core seed 后，Top20 可达权重能否超过 35% |
| 只运行 `strategy-core-reachability-diagnostic` 和 I42 审计 | 先验证可达性，不急于 admission |
| 若核心可达性过关，再预注册 I43 交易策略 | 避免在错误候选池上继续调参 |

停止条件：

- 如果扩大 panel 后仍无法稳定覆盖完整 Top20 `35%` 以上，需要先查数据 / 成分权重 / 复权时间线。
- 如果扩大 panel 后可达性明显改善，再进入强市场核心参与候选设计。

## Harness 过程记录

- Reviewer 指出首版 I42 分类只看全库行数，不看 fold 的日期窗口，会误判数据缺口。
- 已按 Reviewer 意见返工：
  - 审计键升级为 `strategy_id + walk_forward_preset + fold + symbol`。
  - 增加 fold-aware 快照窗口和验证窗口数据覆盖字段。
  - 移除重建完整 panel 的重路径，改为直接查 SQLite 覆盖。
- Planner 结论：I43 不应先写新策略，应先修 universe / data。

本轮因用户要求清理旧 agent，后续不再新建 Verifier；结果核对改由本地产物解析完成。
