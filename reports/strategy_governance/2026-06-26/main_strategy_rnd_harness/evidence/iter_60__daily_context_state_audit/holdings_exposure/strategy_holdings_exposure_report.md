# Strategy Holdings Exposure Diagnostic

This is a research-only diagnostic. It rebuilds daily strategy holdings for existing fold evidence and does not rerun admission, change strategy weights, or create trading signals.

## Scope

- Strategy: `strong_benchmark_participation_boost_v1`
- Candidate folds: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/admission/strategy_admission_candidate_folds.csv`
- Market context: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/market_context/strategy_market_context_diagnostic.csv`
- Boundary: holdings/industry exposure only; CSI300 constituent and style exposure are explicitly marked unavailable when no local table exists.

## Summary

| market_context_label | fold_count | daily_count | avg_strategy_ann | avg_benchmark_ann | avg_excess_ann | avg_live_holding_count | avg_live_exposure | avg_live_top_industry_share | avg_live_top3_industries_share | dominant_live_top_industry | interpretation |
| ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- |
| absolute_loss_but_benchmark_weak_context | 2 | 484 | -0.0296 | -0.1603 | 0.1306 | 79.6446 | 0.1803 | 0.0288 | 0.0714 | 白酒 | Control context: average excess 13.06%; average live exposure 18.03%; top industry share 2.88%. |
| relative_lag_in_strong_benchmark_context | 2 | 483 | 0.0286 | 0.1180 | -0.0894 | 79.4762 | 0.2677 | 0.0423 | 0.0938 | 银行 | Strong benchmark context: average excess -8.94%; average live exposure 26.77%; top industry share 4.23%. This supports a holdings-breadth/concentration check, not a full CSI300 constituent attribution. |
| risk_context_pressure | 1 | 243 | -0.0089 | -0.0546 | 0.0456 | 79.6667 | 0.1494 | 0.0238 | 0.0650 | 白酒 | Control context: average excess 4.56%; average live exposure 14.94%; top industry share 2.38%. |

## Coverage

| artifact | status | rows | note |
| ---- | ---- | ---- | ---- |
| strategy_daily_holdings | available | 96879 | daily target/live holdings rebuilt from fold-local strategy signal_frame |
| strategy_daily_exposure | available | 1210 | daily strategy industry concentration summary |
| fold_point_in_time_universe | available | 5 | industry metadata comes from fold-local PIT universe snapshots |
| benchmark_index_price | available | 1210 | SH.000300 price context can be joined by date; this is not constituent exposure |
| benchmark_constituents | available | 60900 | cn_index_weights_asof is available for follow-up CSI300 constituent weight attribution |
| benchmark_style_exposure | not_available | 0 | cannot claim full holdings-vs-CSI300 style attribution without constituent weights or style factors |
| fold_metrics | available | 5 | fold metrics rebuilt for audit only; no admission action is changed |

## Decision Boundary

- This diagnostic can support a holdings breadth and industry concentration discussion.
- It cannot prove CSI300 constituent underweight or style underexposure until benchmark constituents/weights or style factors are available.
- Admission, paper review, simulated trading, daily brief, and watchlist eligibility are unchanged.
