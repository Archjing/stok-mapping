# Strategy Failure Fold Attribution

Generated at: 2026-06-26T00:43:41

## Scope

- This report is research-only fold-level attribution.
- It reads existing admission CSV artifacts only; it does not rerun backtests or admission.
- Benchmark / market context labels are diagnostic labels, not admission gates and not trading rules.
- Do not infer a regime filter from this report alone; use it only to decide whether a later isolated I8 test is justified.

## Inputs

- folds: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/admission/strategy_admission_candidate_folds.csv`
- window_matrix: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/admission/strategy_admission_window_matrix.csv`
- constraint_review: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/admission/strategy_admission_constraint_review.csv`

## Fold Summary

| strategy_id | preset | fold | valid_window | primary_label | severity | ann | bench_ann | excess_ann | sharpe | drawdown | turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| strong_market_benchmark_aware_core_v1 | baseline_2y_1y_5fold | 1 | 2021-04-01..2022-03-31 | absolute_failure_market_weak_but_outperform | medium | -0.0466 | -0.1796 | 0.1330 | -0.9454 | -0.0705 | 0.71 |
| strong_market_benchmark_aware_core_v1 | baseline_2y_1y_5fold | 2 | 2022-04-01..2023-03-31 | absolute_failure_market_weak_but_outperform | medium | -0.0091 | -0.0546 | 0.0455 | -0.3040 | -0.0401 | 0.16 |
| strong_market_benchmark_aware_core_v1 | baseline_2y_1y_5fold | 3 | 2023-04-03..2024-03-29 | absolute_failure_market_weak_but_outperform | medium | -0.0127 | -0.1409 | 0.1282 | -0.5919 | -0.0300 | 0.16 |
| strong_market_benchmark_aware_core_v1 | baseline_2y_1y_5fold | 4 | 2024-04-01..2025-03-31 | relative_failure_benchmark_strong | medium | 0.0211 | 0.0850 | -0.0638 | 0.7073 | -0.0176 | 0.17 |
| strong_market_benchmark_aware_core_v1 | baseline_2y_1y_5fold | 5 | 2025-04-01..2026-03-31 | relative_failure_benchmark_strong | medium | 0.0122 | 0.1511 | -0.1389 | 0.1832 | -0.0567 | 1.77 |

## Label Counts

| primary_label | fold_count |
| --- | --- |
| absolute_failure_market_weak_but_outperform | 3 |
| relative_failure_benchmark_strong | 2 |

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
- Existing fold attribution: `negative_absolute_but_positive_excess: market_down_or_benchmark_weaker`
- Evidence: ann=-0.0466 vs gate=0.0000；benchmark_ann=-0.1796；excess_ann=0.1330；sharpe=-0.9454 vs gate=0.5000；max_drawdown=-0.0705 vs gate=-0.2500；turnover=0.71 vs gate=5.00
- Next diagnostic action: 该 fold 负收益但正超额，适合作为市场状态归因样本，而不是 alpha 失败样本。

### baseline_2y_1y_5fold fold 2

- Valid window: `2022-04-01` to `2023-03-31`
- Primary diagnostic label: `absolute_failure_market_weak_but_outperform`
- Severity: `medium`
- Absolute status: `negative_or_below_gate_absolute`
- Benchmark-relative status: `positive_excess`
- Risk-adjusted status: `sharpe_below_gate`
- Drawdown status: `drawdown_pass`
- Turnover status: `turnover_pass`
- Existing fold attribution: `negative_absolute_but_positive_excess: market_down_or_benchmark_weaker`
- Evidence: ann=-0.0091 vs gate=0.0000；benchmark_ann=-0.0546；excess_ann=0.0455；sharpe=-0.3040 vs gate=0.5000；max_drawdown=-0.0401 vs gate=-0.2500；turnover=0.16 vs gate=5.00
- Next diagnostic action: 该 fold 负收益但正超额，适合作为市场状态归因样本，而不是 alpha 失败样本。

### baseline_2y_1y_5fold fold 3

- Valid window: `2023-04-03` to `2024-03-29`
- Primary diagnostic label: `absolute_failure_market_weak_but_outperform`
- Severity: `medium`
- Absolute status: `negative_or_below_gate_absolute`
- Benchmark-relative status: `positive_excess`
- Risk-adjusted status: `sharpe_below_gate`
- Drawdown status: `drawdown_pass`
- Turnover status: `turnover_pass`
- Existing fold attribution: `negative_absolute_but_positive_excess: market_down_or_benchmark_weaker`
- Evidence: ann=-0.0127 vs gate=0.0000；benchmark_ann=-0.1409；excess_ann=0.1282；sharpe=-0.5919 vs gate=0.5000；max_drawdown=-0.0300 vs gate=-0.2500；turnover=0.16 vs gate=5.00
- Next diagnostic action: 该 fold 负收益但正超额，适合作为市场状态归因样本，而不是 alpha 失败样本。

### baseline_2y_1y_5fold fold 4

- Valid window: `2024-04-01` to `2025-03-31`
- Primary diagnostic label: `relative_failure_benchmark_strong`
- Severity: `medium`
- Absolute status: `positive_absolute`
- Benchmark-relative status: `negative_excess`
- Risk-adjusted status: `sharpe_pass`
- Drawdown status: `drawdown_pass`
- Turnover status: `turnover_pass`
- Existing fold attribution: `positive_fold`
- Evidence: ann=0.0211 vs gate=0.0000；benchmark_ann=0.0850；excess_ann=-0.0638；sharpe=0.7073 vs gate=0.5000；max_drawdown=-0.0176 vs gate=-0.2500；turnover=0.17 vs gate=5.00
- Next diagnostic action: 优先解释为何绝对赚钱但跑输沪深300；不要用该 fold 直接调选股参数。

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
- Evidence: ann=0.0122 vs gate=0.0000；benchmark_ann=0.1511；excess_ann=-0.1389；sharpe=0.1832 vs gate=0.5000；max_drawdown=-0.0567 vs gate=-0.2500；turnover=1.77 vs gate=5.00
- Next diagnostic action: 优先解释为何绝对赚钱但跑输沪深300；不要用该 fold 直接调选股参数。

## Interpretation Guardrails

- Admission failure remains governed by the admission window matrix and constraint review.
- Positive absolute return with negative excess is benchmark-context evidence, not proof that a market-state filter will work.
- Negative absolute return with positive excess is market-context evidence, not standalone alpha failure.
- Any I8 market-context test must keep I7 selection logic fixed and test one pre-declared variable only.
