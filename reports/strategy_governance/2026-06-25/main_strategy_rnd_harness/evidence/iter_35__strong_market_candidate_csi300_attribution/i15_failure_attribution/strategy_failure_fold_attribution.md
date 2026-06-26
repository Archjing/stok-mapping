# Strategy Failure Fold Attribution

Generated at: 2026-06-25T10:24:04

## Scope

- This report is research-only fold-level attribution.
- It reads existing admission CSV artifacts only; it does not rerun backtests or admission.
- Benchmark / market context labels are diagnostic labels, not admission gates and not trading rules.
- Do not infer a regime filter from this report alone; use it only to decide whether a later isolated I8 test is justified.

## Inputs

- folds: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-24/main_strategy_admission_breakthrough/evidence/iter_15__strong_index_participation_minimal/admission/strategy_admission_candidate_folds.csv`
- window_matrix: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-24/main_strategy_admission_breakthrough/evidence/iter_15__strong_index_participation_minimal/admission/strategy_admission_window_matrix.csv`
- constraint_review: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-24/main_strategy_admission_breakthrough/evidence/iter_15__strong_index_participation_minimal/admission/strategy_admission_constraint_review.csv`

## Fold Summary

| strategy_id | preset | fold | valid_window | primary_label | severity | ann | bench_ann | excess_ann | sharpe | drawdown | turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| strong_index_participation_v1 | baseline_2y_1y_5fold | 1 | 2021-04-01..2022-03-31 | absolute_failure_market_weak_but_outperform | medium | 0.0000 | -0.1796 | 0.1796 | 0.0000 | 0.0000 | 0.00 |
| strong_index_participation_v1 | baseline_2y_1y_5fold | 2 | 2022-04-01..2023-03-31 | absolute_failure_market_weak_but_outperform | medium | 0.0000 | -0.0546 | 0.0546 | 0.0000 | 0.0000 | 0.00 |
| strong_index_participation_v1 | baseline_2y_1y_5fold | 3 | 2023-04-03..2024-03-29 | absolute_failure_market_weak_but_outperform | medium | 0.0000 | -0.1409 | 0.1409 | 0.0000 | 0.0000 | 0.00 |
| strong_index_participation_v1 | baseline_2y_1y_5fold | 4 | 2024-04-01..2025-03-31 | strategy_specific_underperformance | high | 0.0000 | 0.0850 | -0.0850 | 0.0000 | 0.0000 | 0.00 |
| strong_index_participation_v1 | baseline_2y_1y_5fold | 5 | 2025-04-01..2026-03-31 | relative_failure_benchmark_strong | medium | 0.0090 | 0.1511 | -0.1421 | 0.1803 | -0.0497 | 1.67 |

## Label Counts

| primary_label | fold_count |
| --- | --- |
| absolute_failure_market_weak_but_outperform | 3 |
| strategy_specific_underperformance | 1 |
| relative_failure_benchmark_strong | 1 |

## Evidence By Fold

### baseline_2y_1y_5fold fold 1

- Valid window: `2021-04-01` to `2022-03-31`
- Primary diagnostic label: `absolute_failure_market_weak_but_outperform`
- Severity: `medium`
- Absolute status: `negative_or_below_gate_absolute`
- Benchmark-relative status: `positive_excess`
- Risk-adjusted status: `sharpe_below_gate`
- Drawdown status: `drawdown_pass`
- Turnover status: `turnover_pass`
- Existing fold attribution: `positive_fold`
- Evidence: ann=0.0000 vs gate=0.0000；benchmark_ann=-0.1796；excess_ann=0.1796；sharpe=0.0000 vs gate=0.5000；max_drawdown=0.0000 vs gate=-0.2500；turnover=0.00 vs gate=5.00
- Next diagnostic action: 该 fold 更像市场下行背景中的相对抗跌，不应单独触发选股参数调整。

### baseline_2y_1y_5fold fold 2

- Valid window: `2022-04-01` to `2023-03-31`
- Primary diagnostic label: `absolute_failure_market_weak_but_outperform`
- Severity: `medium`
- Absolute status: `negative_or_below_gate_absolute`
- Benchmark-relative status: `positive_excess`
- Risk-adjusted status: `sharpe_below_gate`
- Drawdown status: `drawdown_pass`
- Turnover status: `turnover_pass`
- Existing fold attribution: `positive_fold`
- Evidence: ann=0.0000 vs gate=0.0000；benchmark_ann=-0.0546；excess_ann=0.0546；sharpe=0.0000 vs gate=0.5000；max_drawdown=0.0000 vs gate=-0.2500；turnover=0.00 vs gate=5.00
- Next diagnostic action: 该 fold 更像市场下行背景中的相对抗跌，不应单独触发选股参数调整。

### baseline_2y_1y_5fold fold 3

- Valid window: `2023-04-03` to `2024-03-29`
- Primary diagnostic label: `absolute_failure_market_weak_but_outperform`
- Severity: `medium`
- Absolute status: `negative_or_below_gate_absolute`
- Benchmark-relative status: `positive_excess`
- Risk-adjusted status: `sharpe_below_gate`
- Drawdown status: `drawdown_pass`
- Turnover status: `turnover_pass`
- Existing fold attribution: `positive_fold`
- Evidence: ann=0.0000 vs gate=0.0000；benchmark_ann=-0.1409；excess_ann=0.1409；sharpe=0.0000 vs gate=0.5000；max_drawdown=0.0000 vs gate=-0.2500；turnover=0.00 vs gate=5.00
- Next diagnostic action: 该 fold 更像市场下行背景中的相对抗跌，不应单独触发选股参数调整。

### baseline_2y_1y_5fold fold 4

- Valid window: `2024-04-01` to `2025-03-31`
- Primary diagnostic label: `strategy_specific_underperformance`
- Severity: `high`
- Absolute status: `negative_or_below_gate_absolute`
- Benchmark-relative status: `negative_excess`
- Risk-adjusted status: `sharpe_below_gate`
- Drawdown status: `drawdown_pass`
- Turnover status: `turnover_pass`
- Existing fold attribution: `positive_fold`
- Evidence: ann=0.0000 vs gate=0.0000；benchmark_ann=0.0850；excess_ann=-0.0850；sharpe=0.0000 vs gate=0.5000；max_drawdown=0.0000 vs gate=-0.2500；turnover=0.00 vs gate=5.00
- Next diagnostic action: 先复核该 fold 的持仓、行业暴露和信号来源，再考虑策略假设调整。

### baseline_2y_1y_5fold fold 5

- Valid window: `2025-04-01` to `2026-03-31`
- Primary diagnostic label: `relative_failure_benchmark_strong`
- Severity: `medium`
- Absolute status: `positive_absolute`
- Benchmark-relative status: `negative_excess`
- Risk-adjusted status: `sharpe_below_gate`
- Drawdown status: `drawdown_pass`
- Turnover status: `turnover_pass`
- Existing fold attribution: `positive_fold`
- Evidence: ann=0.0090 vs gate=0.0000；benchmark_ann=0.1511；excess_ann=-0.1421；sharpe=0.1803 vs gate=0.5000；max_drawdown=-0.0497 vs gate=-0.2500；turnover=1.67 vs gate=5.00
- Next diagnostic action: 优先解释为何绝对赚钱但跑输沪深300；不要用该 fold 直接调选股参数。

## Interpretation Guardrails

- Admission failure remains governed by the admission window matrix and constraint review.
- Positive absolute return with negative excess is benchmark-context evidence, not proof that a market-state filter will work.
- Negative absolute return with positive excess is market-context evidence, not standalone alpha failure.
- Any I8 market-context test must keep I7 selection logic fixed and test one pre-declared variable only.
