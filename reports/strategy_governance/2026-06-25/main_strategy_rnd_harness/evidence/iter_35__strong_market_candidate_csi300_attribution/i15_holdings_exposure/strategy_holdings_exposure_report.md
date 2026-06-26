# Strategy Holdings Exposure Diagnostic

This is a research-only diagnostic. It rebuilds daily strategy holdings for existing fold evidence and does not rerun admission, change strategy weights, or create trading signals.

## Scope

- Strategy: `strong_index_participation_v1`
- Candidate folds: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-24/main_strategy_admission_breakthrough/evidence/iter_15__strong_index_participation_minimal/admission/strategy_admission_candidate_folds.csv`
- Market context: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_35__strong_market_candidate_csi300_attribution/i15_market_context/strategy_market_context_diagnostic.csv`
- Boundary: holdings/industry exposure only; CSI300 constituent and style exposure are explicitly marked unavailable when no local table exists.

## Summary

| market_context_label | fold_count | daily_count | avg_strategy_ann | avg_benchmark_ann | avg_excess_ann | avg_live_holding_count | avg_live_exposure | avg_live_top_industry_share | avg_live_top3_industries_share | dominant_live_top_industry | interpretation |
| ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- |
| relative_lag_in_strong_benchmark_context | 1 | 82 | 0.0090 | 0.1511 | -0.1421 | 4.8780 | 0.2439 | 0.0854 | 0.1707 | 保险 | Strong benchmark context: average excess -14.21%; average live exposure 24.39%; top industry share 8.54%. This supports a holdings-breadth/concentration check, not a full CSI300 constituent attribution. |

## Coverage

| artifact | status | rows | note |
| ---- | ---- | ---- | ---- |
| strategy_daily_holdings | available | 418 | daily target/live holdings rebuilt from fold-local strategy signal_frame |
| strategy_daily_exposure | available | 82 | daily strategy industry concentration summary |
| fold_point_in_time_universe | available | 5 | industry metadata comes from fold-local PIT universe snapshots |
| benchmark_index_price | available | 82 | SH.000300 price context can be joined by date; this is not constituent exposure |
| benchmark_constituents | available | 60900 | cn_index_weights_asof is available for follow-up CSI300 constituent weight attribution |
| benchmark_style_exposure | not_available | 0 | cannot claim full holdings-vs-CSI300 style attribution without constituent weights or style factors |
| fold_metrics | available | 5 | fold metrics rebuilt for audit only; no admission action is changed |

## Decision Boundary

- This diagnostic can support a holdings breadth and industry concentration discussion.
- It cannot prove CSI300 constituent underweight or style underexposure until benchmark constituents/weights or style factors are available.
- Admission, paper review, simulated trading, daily brief, and watchlist eligibility are unchanged.
