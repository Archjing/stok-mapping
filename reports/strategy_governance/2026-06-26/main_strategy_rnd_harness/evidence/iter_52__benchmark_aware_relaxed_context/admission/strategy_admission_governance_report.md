# Strategy Admission Governance Report

Generated at: 2026-06-26T00:43:03

## Run Context

- Command: `phase0.cli strategy-admission --config config.main_strategy_i52_benchmark_aware_relaxed_context_20260626.yaml --presets baseline_2y_1y_5fold --strategy-set i52_benchmark_aware_relaxed_context_v1 --output-dir /home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/admission`
- Strategy scope source: `strategy_set`
- Strategy set: `i52_benchmark_aware_relaxed_context_v1`
- Strategy set description: I52 scoped admission for research-only strong_market_benchmark_aware_core_v1 with relaxed benchmark-aware context.
- Presets: `baseline_2y_1y_5fold`
- Strategies: `strong_market_benchmark_aware_core_v1`
- Diagnostics suites: `data_quality_v1, execution_feasibility_v1, factor_explainability_v1, overfit_v1`

## Governance Boundary

- Required price口径: `qfq_asof` = `True`
- Max overfit risk: `medium`
- Agent、compare、admission 报告和 workflow 成功都不等于策略准入通过。
- `reject`、`retest`、`research_only` 不得进入 paper review / 模拟账户 / 日报 / watchlist。
- 只有 `eligible_for_paper_review` 且 qfq_asof、PIT、成本、overfit、行业和因子诊断均满足门禁时，才允许进入下一阶段人工复核。

## Required Artifacts

- `strategy_admission_candidate_folds.csv`
- `strategy_admission_window_matrix.csv`
- `strategy_admission_constraint_review.csv`
- `strategy_admission_report.md`
- `overfit_diagnostic/strategy_overfit_diagnostic.csv`

## Summary

- Strategy count: `1`
- Preset count: `1`
- Matrix rows: `1`
- Action counts: `reject=1`
- Price adjustment status: `qfq_asof=1`
- Industry diagnostic status: `enabled:audited=1`
- Financial diagnostic status: `not_applicable=1`
- Account execution status: `not_enabled=1`

## Candidate Actions

| strategy_id | action | window_pass | reasons |
| --- | --- | --- | --- |
| strong_market_benchmark_aware_core_v1 | reject | 0/1 | overfit risk is high; industry concentration exceeds audit threshold in one or more windows; strategy does not support paper trade review; positive fold ratio below 75% in one or more windows |

## Next Research Actions

- 对 `reject` / `research_only` 候选先运行或复用 `strategy-failure-attribution`，再决定是否进入 T2.12 组合构造修正。
- 不新增高换手价格行为策略作为绕行路径；优先处理收益、Sharpe、正收益折比例、换手、行业集中、参数稳定性和 overfit risk。
