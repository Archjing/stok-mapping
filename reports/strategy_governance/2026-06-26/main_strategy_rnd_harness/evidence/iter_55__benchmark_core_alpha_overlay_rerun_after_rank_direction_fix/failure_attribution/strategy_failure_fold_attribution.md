# Strategy Failure Fold Attribution

Generated at: 2026-06-26T01:56:17

## Scope

- This report is research-only fold-level attribution.
- It reads existing admission CSV artifacts only; it does not rerun backtests or admission.
- Benchmark / market context labels are diagnostic labels, not admission gates and not trading rules.
- Do not infer a regime filter from this report alone; use it only to decide whether a later isolated I8 test is justified.

## Inputs

- folds: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/admission/strategy_admission_candidate_folds.csv`
- window_matrix: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/admission/strategy_admission_window_matrix.csv`
- constraint_review: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/admission/strategy_admission_constraint_review.csv`

## Fold Summary

| strategy_id | preset | fold | valid_window | primary_label | severity | ann | bench_ann | excess_ann | sharpe | drawdown | turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| benchmark_core_alpha_overlay_v1 | baseline_2y_1y_5fold | 1 | 2021-04-01..2022-03-31 | absolute_failure_market_weak_but_outperform | medium | -0.0425 | -0.1796 | 0.1371 | -0.8694 | -0.0660 | 0.71 |
| benchmark_core_alpha_overlay_v1 | baseline_2y_1y_5fold | 2 | 2022-04-01..2023-03-31 | absolute_failure_market_weak_but_outperform | medium | -0.0088 | -0.0546 | 0.0458 | -0.2974 | -0.0394 | 0.16 |
| benchmark_core_alpha_overlay_v1 | baseline_2y_1y_5fold | 3 | 2023-04-03..2024-03-29 | absolute_failure_market_weak_but_outperform | medium | -0.0125 | -0.1409 | 0.1284 | -0.5898 | -0.0301 | 0.16 |
| benchmark_core_alpha_overlay_v1 | baseline_2y_1y_5fold | 4 | 2024-04-01..2025-03-31 | relative_failure_benchmark_strong | medium | 0.0208 | 0.0850 | -0.0641 | 0.7001 | -0.0174 | 0.18 |
| benchmark_core_alpha_overlay_v1 | baseline_2y_1y_5fold | 5 | 2025-04-01..2026-03-31 | relative_failure_benchmark_strong | medium | 0.0337 | 0.1511 | -0.1173 | 0.5572 | -0.0412 | 1.70 |

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
- Evidence: ann=-0.0425 vs gate=0.0000；benchmark_ann=-0.1796；excess_ann=0.1371；sharpe=-0.8694 vs gate=0.5000；max_drawdown=-0.0660 vs gate=-0.2500；turnover=0.71 vs gate=5.00
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
- Evidence: ann=-0.0088 vs gate=0.0000；benchmark_ann=-0.0546；excess_ann=0.0458；sharpe=-0.2974 vs gate=0.5000；max_drawdown=-0.0394 vs gate=-0.2500；turnover=0.16 vs gate=5.00
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
- Evidence: ann=-0.0125 vs gate=0.0000；benchmark_ann=-0.1409；excess_ann=0.1284；sharpe=-0.5898 vs gate=0.5000；max_drawdown=-0.0301 vs gate=-0.2500；turnover=0.16 vs gate=5.00
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
- Evidence: ann=0.0208 vs gate=0.0000；benchmark_ann=0.0850；excess_ann=-0.0641；sharpe=0.7001 vs gate=0.5000；max_drawdown=-0.0174 vs gate=-0.2500；turnover=0.18 vs gate=5.00
- Next diagnostic action: 优先解释为何绝对赚钱但跑输沪深300；不要用该 fold 直接调选股参数。

### baseline_2y_1y_5fold fold 5

- Valid window: `2025-04-01` to `2026-03-31`
- Primary diagnostic label: `relative_failure_benchmark_strong`
- Severity: `medium`
- Absolute status: `positive_absolute`
- Benchmark-relative status: `negative_excess`
- Risk-adjusted status: `sharpe_pass`
- Drawdown status: `drawdown_pass`
- Turnover status: `turnover_pass`
- Existing fold attribution: `positive_fold`
- Evidence: ann=0.0337 vs gate=0.0000；benchmark_ann=0.1511；excess_ann=-0.1173；sharpe=0.5572 vs gate=0.5000；max_drawdown=-0.0412 vs gate=-0.2500；turnover=1.70 vs gate=5.00
- Next diagnostic action: 优先解释为何绝对赚钱但跑输沪深300；不要用该 fold 直接调选股参数。

## Interpretation Guardrails

- Admission failure remains governed by the admission window matrix and constraint review.
- Positive absolute return with negative excess is benchmark-context evidence, not proof that a market-state filter will work.
- Negative absolute return with positive excess is market-context evidence, not standalone alpha failure.
- Any I8 market-context test must keep I7 selection logic fixed and test one pre-declared variable only.
