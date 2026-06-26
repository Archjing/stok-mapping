# Session Incremental Archive - 2026-06-25 15:10 CST

## Scope

本次增量归档记录 I48 Harness 迭代后半段。目标是继续推进策略研发主线，并遵守两条工作标准：

- 每轮 Harness 结束后做一次 Git 提交。
- 远端提交只放代码、解释代码的文档和轻量简报；本地 evidence、日志、数据库和大 CSV 不上传。

## User Steering

- 用户指出：`baseline_2y_1y_5fold` 这类短窗口只适合策略之间横向对比，不能单独作为稳定性证据。
- 用户询问 `satellite-only` 含义。本轮将其定义为归因实验：拿掉沪深300核心底仓，只保留外围增强仓，用来判断 I47 的改善是否来自卫星增强。

## I48 Implementation

新增两个 research-only 归因变体：

- `strong_market_stable_core_only_v1`：只保留核心底仓，`core_budget_ratio=1.0`，`satellite_budget_ratio=0.0`。
- `strong_market_stable_satellite_only_v1`：只保留外围增强仓，`base_exposure=0.0`，`core_budget_ratio=0.0`，`satellite_budget_ratio=1.0`。

同时修正一个边界：

- 当策略初始目标为空仓时，调仓计数仍需推进，否则 `satellite-only` 可能在弱市场空仓后不再重试强市场信号。

## Evidence

最终 rerun 短窗口：

- Preset: `baseline_2y_1y_5fold`
- Output: `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_48__stable_core_attribution_final_rerun/admission_short/`

最终 rerun 长窗口：

- Presets: `quality_3y_1y_4fold`, `quality_4y_1y`
- Output: `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_48__stable_core_attribution_final_rerun/admission_long/`

## Results

短窗口 `baseline_2y_1y_5fold`：

- `core-only`: `reject`，年化 `-1.99%`，Sharpe `-0.35`，正收益折 `40%`，正超额折 `40%`。
- `core+satellite`: `reject`，年化 `-1.74%`，Sharpe `-0.34`，正收益折 `40%`，正超额折 `40%`。
- `satellite-only`: `reject`，年化 `0.78%`，Sharpe `0.14`，正收益折 `40%`，正超额折 `60%`；第 1 折和第 5 折有交易，但第 5 折明显跑输沪深300。

长窗口：

- `quality_3y_1y_4fold`: core-only 与 core+satellite 均未通过，年化约 `0.01%`，Sharpe `-0.09`，正超额折 `25%`。
- `quality_4y_1y`: core-only 与 core+satellite 单窗口通过，年化 `6.22%`，Sharpe `0.83`，但正超额折 `0%`，仍每折跑输沪深300。
- 综合长窗口 admission: core-only 与 core+satellite 为 `research_only`，satellite-only 为 `reject`。

## Decision

I48 结论：

- 短窗口只用于横向比较，不能单独判定强市场策略稳定有效。
- I47 的改善主要来自稳定核心底仓。
- 卫星增强没有稳定贡献，不应继续做小参数调优。
- 下一轮 I49 应做核心底仓相对沪深300跑输归因：核心暴露、行业偏离、权重贴近度和强市场识别时点。

## Reviewer Fixes

Reviewer 指出后已修正：

- `config.main_strategy_i48_stable_core_attribution_20260625.yaml` 的 `default_strategy_set` 改为 `i48_stable_core_attribution_v1`，避免只传 config 时误跑全局候选。
- `satellite-only` 在空仓后遇到强市场状态时立即重试入场，避免被 20 日调仓周期低估。
- 预算分配恢复 I47 原始直接比例口径，避免 I48 归因引入无关策略行为变化。

## Files To Commit

计划提交轻量文件：

- `phase0/strategies/strong_market_stable_core_base.py`
- `phase0/strategies/__init__.py`
- `phase0/strategy_admission.py`
- `tests/test_strong_market_stable_core_base_strategy.py`
- `tests/test_strategy_admission_config.py`
- `config.main_strategy_i48_stable_core_attribution_20260625.yaml`
- `docs/tasks/strategy/PHASE0_CANDIDATE_STRATEGIES.md`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/briefings/iter_48__stable_core_attribution_brief.md`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/session_archive/session_incremental_archive_20260625_1510.md`

不提交本地 evidence 目录、数据库、日志、数据快照、intelligence 产物和未关联的脏改动。
