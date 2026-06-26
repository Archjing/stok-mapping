# Strategy Market Context Diagnostic

Generated at: 2026-06-25T10:24:29

## Scope

- This is a research-only market-context diagnostic overlay.
- It reads existing fold attribution and local benchmark index history only.
- It does not rerun backtests, does not rerun admission, does not change strategy weights, and does not implement risk scaling.
- Market-context labels are explanatory diagnostics, not admission gates and not trading rules.

## Inputs

- Fold attribution: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_35__strong_market_candidate_csi300_attribution/i18_failure_attribution/strategy_failure_fold_attribution.csv`
- Benchmark symbol: `SH.000300`
- Trend window: `120` trading days
- Volatility window: `20` trading days
- Volatility high threshold: rolling `0.70` quantile

## Fold Context Summary

| preset | fold | failure_label | market_context | bench_bucket | trend_bucket | vol_bucket | above_trend | risk_off | strategy_ann | bench_ann | excess_ann |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline_2y_1y_5fold | 1 | clean_positive_fold | risk_context_pressure | weak_down | mostly_below_trend | mostly_normal_vol | 0.1111 | 0.8971 | 0.0112 | -0.1796 | 0.1909 |
| baseline_2y_1y_5fold | 2 | absolute_failure_market_weak_but_outperform | risk_context_pressure | flat_or_mild_down | mostly_below_trend | mixed_vol | 0.2963 | 0.7037 | 0.0000 | -0.0546 | 0.0546 |
| baseline_2y_1y_5fold | 3 | absolute_failure_market_weak_but_outperform | absolute_loss_but_benchmark_weak_context | weak_down | mostly_below_trend | mixed_vol | 0.2116 | 0.8548 | 0.0000 | -0.1409 | 0.1409 |
| baseline_2y_1y_5fold | 4 | strategy_specific_underperformance | mixed_or_unresolved_context | strong_up | mostly_above_trend | mixed_vol | 0.7344 | 0.5726 | 0.0000 | 0.0850 | -0.0850 |
| baseline_2y_1y_5fold | 5 | execution_pressure | mixed_or_unresolved_context | strong_up | mostly_above_trend | mixed_vol | 0.7934 | 0.2934 | 0.0604 | 0.1511 | -0.0907 |

## Label Counts

| market_context_label | count |
| --- | --- |
| risk_context_pressure | 2 |
| mixed_or_unresolved_context | 2 |
| absolute_loss_but_benchmark_weak_context | 1 |

## Label Summary

| primary_fold_failure | folds | avg_excess | avg_index_ann | avg_above_trend | avg_high_vol | avg_risk_off | dominant_context |
| --- | --- | --- | --- | --- | --- | --- | --- |
| absolute_failure_market_weak_but_outperform | 2 | 0.0977 | -0.0871 | 0.2540 | 0.2768 | 0.7792 | absolute_loss_but_benchmark_weak_context |
| clean_positive_fold | 1 | 0.1909 | -0.1691 | 0.1111 | 0.1687 | 0.8971 | risk_context_pressure |
| execution_pressure | 1 | -0.0907 | 0.1512 | 0.7934 | 0.2025 | 0.2934 | mixed_or_unresolved_context |
| strategy_specific_underperformance | 1 | -0.0850 | 0.1036 | 0.7344 | 0.3237 | 0.5726 | mixed_or_unresolved_context |

## Data Coverage

| index_symbol | requested | loaded | trading_days | missing_est | source | status | asof_shift |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SH.000300 | 2021-04-01..2026-03-31 | 2020-04-07..2026-03-31 | 1450 | 94.0000 | local_history_sqlite | available | True |

## Interpretation

- Relative lag in strong benchmark context folds: `0`
- Absolute loss but weak benchmark context folds: `1`
- Generic risk-context pressure folds: `2`

Current evidence includes weak-market pressure, but weak-market folds also show relative resilience; risk-off logic is not proven.

## I8 Decision Guardrail

- Do not implement a regime filter from this diagnostic alone.
- If I8b is pursued, keep I7 selection logic fixed and test one pre-declared variable only.
- A weak-market risk-off filter is not the first hypothesis if relative lag is concentrated in strong benchmark regimes.
