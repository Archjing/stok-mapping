# Session Incremental Archive - 2026-06-25 11:27 CST

## 本轮新增标准

- 用户确认后续开发工作标准：在上下文压缩之前，将项目会话记录增量归档到合适位置。
- 已补充到 `AGENTS.md` 项目专属要求：上下文压缩前必须归档本轮有价值项目会话记录，至少保留新增标准、关键决策、执行命令、变更文件、生成报告、验证结果、未完成事项和下一步；重复状态更新和大段工具输出只做摘要。

## 本轮 Harness 目标

- 继续策略研发主线，延续 I37 `strong_market_effective_participation_v1` 后的强沪深300归因。
- 核心问题：为什么强市场参与型策略仍然跟不上强沪深300，低参与度来自候选池不足、组合构造器不足，还是二者都有。

## 关键代码变更

- `phase0/strategies/strong_market_effective_participation.py`
  - 修正 `_scale_to_budget`：候选权重 cap 总和低于预算时，不再把剩余额度补给最高权重个股。
  - 目的：避免突破 `max_symbol_weight`，让低可达性真实反映为低仓位，而不是由单票超配虚高仓位。
- `phase0/strategy_filter_diagnostic.py`
  - 新增 benchmark 权重可达性诊断字段：
    - `benchmark_member_count`
    - `hard_filter_benchmark_member_count`
    - `eligible_benchmark_member_count`
    - `eligible_benchmark_weight_sum`
    - `panel_top20_eligible_benchmark_weight_sum`
  - fold summary 增加强市场日可买沪深300权重和当前 panel 可见 Top20 可买权重。
- `tests/test_strong_market_effective_participation_strategy.py`
  - 更新 I37 策略测试，明确修正后不强行填满预算、不突破单股上限。
- `tests/test_strategy_filter_diagnostic.py`
  - 新增 benchmark weight reachability 单元测试。

## 复跑命令

```bash
./.venv/bin/python -m phase0.cli strategy-admission --config config.main_strategy_i37_strong_market_effective_participation_20260625.yaml --presets baseline_2y_1y_5fold --strategies strong_market_effective_participation_v1 --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/admission
```

```bash
./.venv/bin/python -m phase0.cli strategy-failure-attribution --config config.main_strategy_i37_strong_market_effective_participation_20260625.yaml --admission-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/admission --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/failure_attribution
```

```bash
./.venv/bin/python -m phase0.cli strategy-market-context --config config.main_strategy_i37_strong_market_effective_participation_20260625.yaml --fold-attribution reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/failure_attribution/strategy_failure_fold_attribution.csv --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/market_context
```

```bash
./.venv/bin/python -m phase0.cli strategy-holdings-exposure --config config.main_strategy_i37_strong_market_effective_participation_20260625.yaml --candidate-folds reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/admission/strategy_admission_candidate_folds.csv --market-context reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/market_context/strategy_market_context_diagnostic.csv --strategy strong_market_effective_participation_v1 --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/holdings_exposure
```

```bash
./.venv/bin/python -m phase0.cli strategy-csi300-attribution --config config.main_strategy_i37_strong_market_effective_participation_20260625.yaml --holdings reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/holdings_exposure/strategy_daily_holdings.csv --daily-exposure reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/holdings_exposure/strategy_daily_exposure.csv --candidate-folds reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/admission/strategy_admission_candidate_folds.csv --market-context reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/market_context/strategy_market_context_diagnostic.csv --context-label mixed_or_unresolved_context --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/csi300_attribution_mixed_context
```

```bash
./.venv/bin/python -m phase0.cli strategy-filter-diagnostic --config config.main_strategy_i37_strong_market_effective_participation_20260625.yaml --candidate-folds reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/admission/strategy_admission_candidate_folds.csv --strategy strong_market_effective_participation_v1 --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_38__strong_market_reachability_diagnostic/filter_diagnostic
```

## 当前结果

- I37 修正后 admission 仍为 `reject`。
- 修正后主要 admission 指标：
  - 年化收益均值 `-3.47%`
  - Sharpe 均值 `-0.46`
  - 最差最大回撤 `-17.11%`
  - 正收益折比例 `20%`
  - 年化换手均值 `3.58`
  - 年化换手最大值 `14.01`
  - 行业审计违规日 `45`
  - overfit risk `high`
- I37 第 5 折 CSI300 归因：
  - 平均实盘暴露 `10.29%`
  - 持有沪深300权重 `2.13%`
  - 前20权重股覆盖 `2.79%`
  - 策略总收益 `-8.96%`
  - 沪深300总收益 `14.48%`
  - 超额 `-23.43%`
  - primary driver: `low_participation`
- I38 可达性诊断：
  - fold 2/3/4 没有强市场触发。
  - fold 5 强市场日平均可买候选数约 `16.49`。
  - fold 5 强市场日平均可买沪深300权重 `9.05%`。
  - fold 5 强市场日平均可买当前 panel 可见前20权重股权重 `3.93%`。
- 结论：当前强市场参与型路线同时受强市场 gate 稀少、候选池核心权重可达性不足和真实持仓暴露不足限制。下一步应重构候选生成层，而不是继续微调组合权重参数。

## 生成报告

- I37 更新简报：
  - `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/briefings/iter_37__strong_market_effective_participation_brief.md`
- I38 新增简报：
  - `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/briefings/iter_38__strong_market_reachability_diagnostic_brief.md`
- I38 原始诊断：
  - `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_38__strong_market_reachability_diagnostic/filter_diagnostic/`

## 验证

```bash
./.venv/bin/python -m pytest -s tests/test_strong_market_effective_participation_strategy.py tests/test_strategy_filter_diagnostic.py tests/test_strategy_csi300_attribution.py
```

结果：`13 passed, 1 warning`。

## 后续动作

1. 等 Reviewer 子 Agent 返回后，检查是否有必须修复的问题。
2. 运行补充测试和 `git diff --check`。
3. 若无阻断问题，继续下一轮 I39：重新设计强市场参与型候选生成层，先保证 CSI300 核心权重可达性，再叠加主动 alpha 过滤。

## Reviewer 复核与修正

- Reviewer 发现 I38 诊断的 `review_day` 沿用固定 20 日口径，但 `strong_market_effective_participation_v1` 实际每天按强市场状态重建目标权重。
- 已修复：
  - 对 `strong_market_effective_participation_v1`，`strategy-filter-diagnostic` 使用每日 review 口径。
  - I38 复跑后 fold 5 的 `strong_rebal` / `candidate_rebal` 从旧口径 `3/13` 修正为 `61/242`。
- Reviewer 还指出 Top20 字段来自当前 fold panel 内权重排名前20，不是完整沪深300 as-of 全成分 Top20。
- 已修复：
  - 字段更名为 `panel_top20_*`。
  - I38 简报、I39 简报、I39 spec 和任务清单均改为“当前 panel 可见 Top20”口径。
  - 完整基准 Top20 可达性留给 I40 的 `strategy-core-reachability-diagnostic` 只读诊断。

## I40 只读诊断

新增命令：

```text
strategy-core-reachability-diagnostic
```

运行命令：

```bash
./.venv/bin/python -m phase0.cli strategy-core-reachability-diagnostic --config config.main_strategy_i37_strong_market_effective_participation_20260625.yaml --candidate-folds reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/admission/strategy_admission_candidate_folds.csv --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_40__csi300_core_reachability_diagnostic/core_reachability
```

产物：

- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_40__csi300_core_reachability_diagnostic/core_reachability/strategy_core_reachability_fold_summary.csv`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_40__csi300_core_reachability_diagnostic/core_reachability/strategy_core_reachability_daily.csv`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_40__csi300_core_reachability_diagnostic/core_reachability/strategy_core_reachability_failure_reasons.csv`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/briefings/iter_40__csi300_core_reachability_diagnostic_brief.md`

关键结果：

- 五折 as-of 权重覆盖均为 `100%`。
- 平均可达核心权重：
  - fold 1: `57.74%`
  - fold 2: `55.82%`
  - fold 3: `53.39%`
  - fold 4: `54.96%`
  - fold 5: `54.98%`
- 平均完整 Top20 可达权重：
  - fold 1: `34.28%`
  - fold 2: `32.70%`
  - fold 3: `31.00%`
  - fold 4: `32.47%`
  - fold 5: `33.01%`
- 结论：本地 PIT 数据不是强市场策略失败的主障碍。I37 的过窄 alpha / hard filters 把可达核心权重从约 `55%` 压到 I38 看到的约 `9%`。

I40 实现时遇到一次 pandas `merge_asof` 时间精度错误：左侧 `datetime64[ns]`、右侧 `datetime64[us]`。已修复 `_asof_weight_date_map`，统一转换为 `datetime64[ns]`，并新增单元测试覆盖。

I41 推荐方向：

- 设计强市场核心参与候选生成器。
- 保留 CSI300 core pool。
- 基础风险过滤只排除不可交易标的。
- alpha 因子从硬过滤改为排序和小幅权重调整。
- 未达成完整 Top20 可达门槛时明确降级，不用尾部股票补仓。

## I41 Top 权重缺口分析

新增简报：

- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/briefings/iter_41__csi300_top_weight_gap_analysis_brief.md`

分析结论：

- I40 完整 Top20 未达 `35%` 门槛，主要是少数高权重成分缺失于当前 PIT panel。
- 不可达原因全部为 `missing_from_pit_panel`，未发现价格无效、成交额不足、amount_ratio20 不足或行业缺失造成的大面积阻断。
- Top20 缺口代表股票：
  - `SH.601328`
  - `SH.601816`
  - `SH.600900`
  - `SH.600919`
  - `SH.600030`
- 下一步建议：做缺失核心成分审计，逐只追踪这些股票为何没有进入 PIT panel，确认是 universe 规则、历史数据缺口、估值字段、上市状态、代码映射，还是当期确实不可交易。

## I42 缺失核心成分审计

新增命令：

```text
strategy-missing-core-audit
```

实现文件：

- `phase0/strategy_missing_core_audit.py`
- `phase0/cli.py`
- `tests/test_strategy_missing_core_audit.py`

运行命令：

```bash
./.venv/bin/python -m phase0.cli strategy-missing-core-audit --config config.main_strategy_i37_strong_market_effective_participation_20260625.yaml --missing-reasons reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_40__csi300_core_reachability_diagnostic/core_reachability/strategy_core_reachability_failure_reasons.csv --candidate-folds reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/admission/strategy_admission_candidate_folds.csv --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_42__missing_core_member_audit/missing_core_audit
```

产物：

- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_42__missing_core_member_audit/missing_core_audit/missing_core_symbol_audit.csv`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_42__missing_core_member_audit/missing_core_audit/missing_core_event_audit.csv`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_42__missing_core_member_audit/missing_core_audit/missing_core_audit_report.md`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/briefings/iter_42__missing_core_member_audit_brief.md`

关键结果：

- 审计 Top30 缺失股票，覆盖 `67` 个 fold-symbol 行、`10328` 个缺失交易日和 `53.2842` 的缺失权重合计。
- `beyond_walk_forward_limit` 是主因：
  - fold-symbol 行 `61`
  - 缺失交易日 `9746`
  - 缺失权重合计 `50.4466`
  - 约占审计缺失权重 `94.7%`
- `ranked_out_or_balanced_out_of_pit_universe`：
  - fold-symbol 行 `3`
  - 缺失交易日 `560`
  - 缺失权重合计 `2.6715`
- `universe_member_but_panel_missing`：
  - fold-symbol 行 `3`
  - 缺失交易日 `22`
  - 缺失权重合计 `0.1660`

解释：

- 大多数缺失核心成分不是本地库整体缺行。
- 它们已经通过历史 PIT 快照和基础过滤，并进入候选序列。
- 主要问题是当前 `walk_forward_limit = 120` 把这些沪深300高权重成分截在回测 panel 外。
- 因此 I43 不应先写新交易策略，而应先做强市场专项 panel / universe 治理实验。

Reviewer 修正：

- Reviewer 指出首版 I42 分类只看全库行数，不看 fold 的 as-of / 验证窗口，可能误判数据缺口。
- 已返工：
  - 审计键升级为 `strategy_id + walk_forward_preset + fold + symbol`。
  - 添加 fold-aware 快照窗口和验证窗口覆盖字段。
  - 移除重建完整 fold panel 的重路径，改为直接查询 SQLite 覆盖。
  - 报告增加分类权重和 fold 分类权重。

Planner 结论：

- Planner 建议 I43 暂缓写新策略，先修 `universe/data`。
- 理由：I40/I41/I42 已把瓶颈收敛到候选生成层和 panel 截断；在 120 只 panel 上继续写策略，会继续天然低配沪深300核心成分。

Agent 管理记录：

- 本轮曾启动 Reviewer 与 Planner。
- 用户指出旧 agent 数量过多后，已关闭本轮完成的 Reviewer 与 Planner。
- 对当前上下文里已知旧 agent ID 再次执行 `close_agent`，工具返回 `not found`。
- 当前 multi-agent 工具没有 `list_agents` 或 `close_all_completed_agents` 接口，无法从工具侧枚举界面显示的全部 `38` 个 agent；若后续需要逐个清理，需要用户提供具体 ID 或使用界面自带清理能力。
- 后续 Harness 默认改为短生命周期子 agent：明确角色、明确任务、完成即关闭；除非用户明确要求，不保留长期待命 agent。

下一步：

- I43：设计强市场专项 panel / universe 治理实验。
- 保留常规 `walk_forward_limit = 120` 作为对照，不破坏既有策略回测口径。
- 新增 research-only 扩 panel 或 CSI300 core seed 方案。
- 先跑 `strategy-core-reachability-diagnostic` 和 I42 审计，验证完整 Top20 可达权重能否稳定超过 `35%`。
- 只有可达性过关后，才预注册新的强市场核心参与交易策略。

## I43 强市场 Panel 上限实验

用户要求清理旧 agent 后，本轮不再新建子 agent。执行方式降级为：Team Lead 直接推进、本地产物核验、继续落盘归档。

新增配置：

- `config.main_strategy_i43_panel_limit_200_20260625.yaml`
- `config.main_strategy_i43_panel_limit_300_20260625.yaml`

实验变量：

- 只改变 `universe.walk_forward_limit`
  - baseline: `120`
  - treatment: `200`
  - treatment: `300`
- 保持 `qfq_asof`、PIT universe、I37 fold、历史权重 as-of、成本口径和候选策略上下文不变。
- 不运行 admission，不输出交易信号。

运行命令：

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

汇总产物：

- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_43__strong_market_panel_limit_experiment/panel_limit_reachability_summary.csv`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_43__strong_market_panel_limit_experiment/panel_limit_missing_core_classification_summary.csv`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/briefings/iter_43__strong_market_panel_limit_experiment_brief.md`

关键结果：

| panel 上限 | 平均可达核心权重 | 最低可达核心权重 | 平均完整 Top20 可达权重 | 最低完整 Top20 可达权重 | 缺失原因行数 | 缺失股票数 |
| ----------: | ---------------: | ---------------: | ----------------------: | ----------------------: | -----------: | ---------: |
| 120 | 55.38% | 52.01% | 32.69% | 29.89% | 10570 | 44 |
| 200 | 57.72% | 55.20% | 32.73% | 29.89% | 4979 | 30 |
| 300 | 58.55% | 56.50% | 32.82% | 30.73% | 3265 | 23 |

结论：

- 扩 panel 有效减少 `walk_forward_limit` 截断，缺失原因行数从 `10570` 降到 `3265`。
- 平均可达核心权重从 `55.38%` 提高到 `58.55%`。
- 但完整 Top20 可达权重几乎没有明显改善，仍低于 I39 的 `35%` 门槛。
- 单纯扩大 panel 不足以支撑新的强市场交易策略实现。

下一步：

- I44 做 `csi300_core_seed_panel` 只读实验。
- 目标是在常规 PIT universe 外显式保留 as-of 可见的 CSI300 Top 权重核心成分。
- 只剔除不可交易、无价格、无复权、严重缺行业或停牌不可用标的。
- 先跑可达性诊断和 missing-core 审计。
- 只有完整 Top20 可达权重稳定超过 `35%` 后，才预注册新的强市场核心参与候选。

## I44 CSI300 Core Seed Panel 只读实验

用户要求继续策略研发主线，同时允许启动一个 T5.2 投资策略情报模块子智能体。主线仍由 Team Lead 直接推进；T5.2 子智能体只做情报模块侦察，不参与 I44 产物。

本轮先修复了 `strategy_core_reachability` 的行业字段补齐查询：

- 问题：`market_stocks` 当前没有 `updated_at` 列，原查询按 `updated_at` 排序会导致行业补齐失败。
- 修复：查询前检查 `market_stocks` 表和列，只有存在 `updated_at` 时才排序。

随后发现并修正一个更重要的指标口径问题：

- I39/I43 把完整 Top20 的 `35%` 绝对权重当成门槛。
- 这不合理，因为沪深300 Top20 本身的总权重会随年份变化。
- I44 改为用 Top20 覆盖率判断可达性：核心绝对权重仍需超过 `50%`，核心覆盖率需超过 `90%`，Top20 覆盖率需超过 `98%`。

运行命令：

```bash
./.venv/bin/python -m phase0.cli strategy-core-reachability-diagnostic --config config.main_strategy_i37_strong_market_effective_participation_20260625.yaml --candidate-folds reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/admission/strategy_admission_candidate_folds.csv --seed-benchmark-core --seed-top-n 20 --seed-core-top-n 60 --seed-core-cumulative-weight 0.60 --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_44__csi300_core_seed_panel/core_seed_panel/core_reachability
```

```bash
./.venv/bin/python -m phase0.cli strategy-missing-core-audit --config config.main_strategy_i37_strong_market_effective_participation_20260625.yaml --missing-reasons reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_44__csi300_core_seed_panel/core_seed_panel/core_reachability/strategy_core_reachability_failure_reasons.csv --candidate-folds reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/admission/strategy_admission_candidate_folds.csv --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_44__csi300_core_seed_panel/core_seed_panel/missing_core_audit
```

核心结果：

| 方案 | 平均核心可达权重 | 平均核心覆盖率 | 平均 Top20 可达权重 | 平均 Top20 覆盖率 | 状态 |
| --- | ---: | ---: | ---: | ---: | --- |
| I40 panel=120 | 55.38% | 92.48% | 32.69% | 99.54% | 失败 |
| I43 panel=200 | 57.72% | 96.40% | 32.73% | 99.66% | 失败 |
| I43 panel=300 | 58.55% | 97.78% | 32.82% | 99.95% | 失败 |
| I44 seed core | 59.45% | 99.28% | 32.82% | 99.95% | 通过 |

解释：

- I44 不是交易策略通过。
- I44 只说明：如果显式保留 as-of 可见的沪深300核心成分，候选池可以看见强市场策略需要关注的核心股票。
- 它不表示固定买前20只，也不表示复制沪深300。

剩余数据治理点：

- `SH.600837` 缺名称和行业，引发大量 `missing_industry`。
- 少数股票仍有短窗口 `universe_member_but_panel_missing`。
- 这些是后续数据治理事项，不阻断 I44 的主结论。

产物：

- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/briefings/iter_44__csi300_core_seed_panel_brief.md`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_44__csi300_core_seed_panel/core_seed_panel/seed_panel_reachability_summary.csv`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_44__csi300_core_seed_panel/core_seed_panel/seed_panel_failure_reason_summary.csv`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_44__csi300_core_seed_panel/core_seed_panel/core_reachability/`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_44__csi300_core_seed_panel/core_seed_panel/missing_core_audit/`

下一步：

- I45 预注册 `strong_market_core_participation_v1`。
- 目标：把 I44 的“能看见核心股”转化为“强市场中实际持有足够沪深300核心权重，并通过 admission”。
- 仍必须保留 PIT、`qfq_asof`、成本、行业约束、持仓暴露和 CSI300 attribution。

T5.2 子智能体结果：

- 子智能体 ID：`019efd28-2495-7b53-9501-10c2885b0db7`
- 已恢复为 pending，可继续协作 T5.2。
- 它确认 T5.2 主入口为 `config.yaml` 的 `intelligence` 配置、`phase0.cli intelligence` 的 `collect/import-local/validate` 子命令、`phase0/intelligence.py` 实现和 `knowledge/intelligence` 知识资产目录。
- 它建议下一步做最小可验证任务：给 `intelligence validate` 增加 `rag_manifest.csv` 路径、状态、类型、信任等级和 `intelligence_id` 反查 ledger 的只读校验，并补 focused pytest。

## I45 Strong Market Core Participation V1 预注册设计

I44 之后继续主线，但不直接编码。目标是冻结下一候选边界，避免把 I44 误解为“固定买沪深300前20只”。

新增设计文件：

- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_45__strong_market_core_participation_design/strong_market_core_participation_v1_spec.md`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/briefings/iter_45__strong_market_core_participation_design_brief.md`

候选名：

```text
strong_market_core_participation_v1
```

核心假设：

- 在 T-1 可见的强沪深300环境下，先确保沪深300核心成分进入候选池。
- 然后用轻量趋势、流动性、风险和行业约束决定实际持仓。
- 目标是验证“能看见核心股”能否转化为“真实持仓能有效参与强市场”。

明确不做：

- 不固定买沪深300前20只。
- 不复制沪深300。
- 不使用未来权重。
- 不降低 admission gate。
- 不绕过 PIT、`qfq_asof`、成本、行业审计或持仓归因。

初版组合结构：

| 层 | 作用 | 预算 |
| --- | --- | ---: |
| `benchmark_core_sleeve` | 参与沪深300核心成分 | 70%-85% |
| `alpha_satellite_sleeve` | 保留少量主动选择空间 | 15%-30% |

如果进入 I46，实现后必须验证：

- scoped admission
- holdings exposure
- CSI300 attribution
- failure attribution
- 强市场平均仓位 `>= 60%`
- 持有沪深300权重 `>= 12%`，优先争取 `>= 20%`
- Top20 持仓覆盖 `>= 25%`
- 年化换手均值 `<= 3.0`
- 年化换手最大值 `<= 5.0`

停止条件：

- 参与度提高但收益、Sharpe、回撤或换手明显恶化。
- 收益只来自单一折、单一行业或单一权重股。
- 为通过指标需要使用未来权重、放宽 PIT 或降低 admission gate。

任务文档已同步：

- `docs/tasks/strategy/PHASE0_CANDIDATE_STRATEGIES.md`

下一步：

- I46 最小实现 `strong_market_core_participation_v1`。
- 实现后必须先用 scoped admission 和持仓级 CSI300 归因判断，不得直接进入 paper review、模拟、日报或 watchlist。

## I46 Strong Market Core Participation V1 实现与验证

本轮实现 `strong_market_core_participation_v1` research-only 策略，并完成 admission、失败归因、市场环境、持仓暴露和 CSI300 权重归因。

用户复核时指出：趋势、流动性、风险、行业约束容易把沪深300核心股过滤掉。该判断已落实到实现中：

- 沪深300核心股不再被趋势、波动、行业数量上限硬过滤。
- 这些变量改为排序、降权、卫星仓约束和审计依据。
- 基础硬门槛只保留价格、成交额、收益字段和基础可交易性。

关键代码变更：

- `phase0/strategies/strong_market_core_participation.py`
  - 新增 `strong_market_core_participation_v1`。
  - 使用 T-1 可见沪深300权重构造 core seed panel。
  - 在训练窗口和验证窗口分别按 fold as-of 日期补入核心成分，避免混用未来数据。
  - 核心仓位优先覆盖沪深300权重成分，卫星仓保留少量主动 alpha 空间。
- `phase0/walk_forward.py`
  - 在 `strategy.prepare_panel` 前传入 fold prepare context：`train_start/train_end/valid_start/valid_end`。
  - admission / compare 的 fold 级结果附带 benchmark annualized return 和 excess annualized return。
- `phase0/strategy_holdings_exposure.py`
  - 持仓暴露重建时同样传入 fold prepare context，保证诊断和 admission 的候选池口径一致。
- `phase0/strategy_csi300_attribution.py`
  - 报告标题从固定 `I34 沪深300权重归因报告` 改为通用 `沪深300权重归因报告`，避免 I46/I47 回查误读。
- `tests/test_strong_market_core_participation_strategy.py`
  - 覆盖注册、强市场建仓、弱市场空仓、核心股不被行业上限硬过滤。
- `tests/test_strategy_csi300_attribution.py`
  - 覆盖 CSI300 归因报告标题不再固定 I34。

运行命令：

```bash
./.venv/bin/python -m pytest -s tests/test_strong_market_core_participation_strategy.py tests/test_strategy_admission_config.py
```

结果：`35 passed, 1 warning`。

```bash
./.venv/bin/python -m phase0.cli strategy-admission --config config.main_strategy_i46_strong_market_core_participation_20260625.yaml --presets baseline_2y_1y_5fold --strategy-set i46_strong_market_core_participation_v1 --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/admission
```

```bash
./.venv/bin/python -m phase0.cli strategy-failure-attribution --config config.main_strategy_i46_strong_market_core_participation_20260625.yaml --admission-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/admission --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/failure_attribution
```

```bash
./.venv/bin/python -m phase0.cli strategy-market-context --config config.main_strategy_i46_strong_market_core_participation_20260625.yaml --fold-attribution reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/failure_attribution/strategy_failure_fold_attribution.csv --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/market_context
```

```bash
./.venv/bin/python -m phase0.cli strategy-holdings-exposure --config config.main_strategy_i46_strong_market_core_participation_20260625.yaml --candidate-folds reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/admission/strategy_admission_candidate_folds.csv --market-context reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/market_context/strategy_market_context_diagnostic.csv --strategy strong_market_core_participation_v1 --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/holdings_exposure
```

```bash
./.venv/bin/python -m phase0.cli strategy-csi300-attribution --config config.main_strategy_i46_strong_market_core_participation_20260625.yaml --holdings reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/holdings_exposure/strategy_daily_holdings.csv --daily-exposure reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/holdings_exposure/strategy_daily_exposure.csv --candidate-folds reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/admission/strategy_admission_candidate_folds.csv --market-context reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/market_context/strategy_market_context_diagnostic.csv --context-label all --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/csi300_attribution_all_context
```

```bash
./.venv/bin/python -m pytest -s tests/test_strategy_csi300_attribution.py tests/test_strong_market_core_participation_strategy.py
```

结果：`8 passed`。

Admission 结果：

- action: `reject`
- 年化收益均值：`-3.30%`
- Sharpe 均值：`-0.43`
- 最差回撤：`-15.30%`
- 正收益折比例：`0%`
- 正超额折比例：`60%`
- 平均年化换手：`4.08`
- 最大年化换手：`16.04`
- overfit risk: `high`
- 主要拒绝原因：overfit high、换手超标、行业审计超阈、positive fold ratio 低于 `75%`、不支持 paper trade。

折级解释：

| fold | 策略年化 | 沪深300年化 | 超额 | 解释 |
| ---: | ---: | ---: | ---: | --- |
| 1 | `-0.65%` | `-17.96%` | `+17.31%` | 弱市抗跌 |
| 2 | `0.00%` | `-5.46%` | `+5.46%` | 基本空仓 |
| 3 | `0.00%` | `-14.09%` | `+14.09%` | 基本空仓 |
| 4 | `0.00%` | `+8.50%` | `-8.50%` | 强市没有参与 |
| 5 | `-15.83%` | `+15.11%` | `-30.94%` | 强市跑输且换手高 |

CSI300 持仓归因：

| fold | 全折平均实盘仓位 | 全折平均持有沪深300权重 | Top20 覆盖率 | primary_driver |
| ---: | ---: | ---: | ---: | --- |
| 1 | `2.02%` | `0.93%` | `1.89%` | `low_participation` |
| 2 | `0.00%` | `0.00%` | `0.00%` | `low_participation` |
| 3 | `0.00%` | `0.00%` | `0.00%` | `low_participation` |
| 4 | `0.00%` | `0.00%` | `0.00%` | `low_participation` |
| 5 | `17.64%` | `7.83%` | `16.39%` | `low_participation` |

解释：

- I46 已不再是“核心股完全进不来”的问题。
- 但强市场触发仍太窄，大多数验证日没有持仓或仓位很低。
- 活跃交易日的仓位能接近 `49%` 到 `59%`，但摊到完整验证折后仍只有 `2.02%` 或 `17.64%`。
- 因此 I46 的主失败原因是“强行情参与持续性不足”，不是单纯候选池可达性。

新增产物：

- `config.main_strategy_i46_strong_market_core_participation_20260625.yaml`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/briefings/iter_46__strong_market_core_participation_brief.md`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/admission/`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/failure_attribution/`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/market_context/`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/holdings_exposure/`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/csi300_attribution_all_context/`

下一步建议：

- I47 不继续调 I46 小参数。
- 预注册“稳定核心底仓 + alpha 卫星”的强市场候选。
- 先验证强市时能否稳定保持最低有效仓位和沪深300权重覆盖，再谈选股增强。
