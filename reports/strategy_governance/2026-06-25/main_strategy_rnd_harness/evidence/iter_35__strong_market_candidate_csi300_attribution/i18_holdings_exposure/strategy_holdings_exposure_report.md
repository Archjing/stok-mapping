# Strategy Holdings Exposure Diagnostic

This is a research-only diagnostic. It rebuilds daily strategy holdings for existing fold evidence and does not rerun admission, change strategy weights, or create trading signals.

## Scope

- Strategy: `strong_index_participation_dynamic_trigger_v1`
- Candidate folds: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-24/main_strategy_admission_breakthrough/evidence/iter_18__strong_index_dynamic_trigger/admission/strategy_admission_candidate_folds.csv`
- Market context: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_35__strong_market_candidate_csi300_attribution/i18_market_context/strategy_market_context_diagnostic.csv`
- Boundary: holdings/industry exposure only; CSI300 constituent and style exposure are explicitly marked unavailable when no local table exists.

## Summary

| market_context_label | fold_count | daily_count | avg_strategy_ann | avg_benchmark_ann | avg_excess_ann | avg_live_holding_count | avg_live_exposure | avg_live_top_industry_share | avg_live_top3_industries_share | dominant_live_top_industry | interpretation |
| ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- |
| mixed_or_unresolved_context | 1 | 120 | 0.0604 | 0.1511 | -0.0907 | 10.9250 | 0.5463 | 0.1179 | 0.2813 | 元器件 | Control context: average excess -9.07%; average live exposure 54.63%; top industry share 11.79%. |
| risk_context_pressure | 1 | 44 | 0.0112 | -0.1796 | 0.1909 | 10.4545 | 0.5227 | 0.0898 | 0.2455 | 化学制药 | Control context: average excess 19.09%; average live exposure 52.27%; top industry share 8.98%. |

## Coverage

| artifact | status | rows | note |
| ---- | ---- | ---- | ---- |
| strategy_daily_holdings | available | 1871 | daily target/live holdings rebuilt from fold-local strategy signal_frame |
| strategy_daily_exposure | available | 164 | daily strategy industry concentration summary |
| fold_point_in_time_universe | available | 5 | industry metadata comes from fold-local PIT universe snapshots |
| benchmark_index_price | available | 164 | SH.000300 price context can be joined by date; this is not constituent exposure |
| benchmark_constituents | available | 60900 | cn_index_weights_asof is available for follow-up CSI300 constituent weight attribution |
| benchmark_style_exposure | not_available | 0 | cannot claim full holdings-vs-CSI300 style attribution without constituent weights or style factors |
| fold_metrics | available | 5 | fold metrics rebuilt for audit only; no admission action is changed |

## Decision Boundary

- This diagnostic can support a holdings breadth and industry concentration discussion.
- It cannot prove CSI300 constituent underweight or style underexposure until benchmark constituents/weights or style factors are available.
- Admission, paper review, simulated trading, daily brief, and watchlist eligibility are unchanged.
