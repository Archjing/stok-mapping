# Strategy Filter Diagnostic Report

Generated at: 2026-06-25T11:42:12

## Scope

- Config: `/home/zj/workspace/stok-mapping/config.main_strategy_i37_strong_market_effective_participation_20260625.yaml`
- Candidate folds: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/admission/strategy_admission_candidate_folds.csv`
- Command: `/home/zj/workspace/stok-mapping/phase0/cli.py strategy-filter-diagnostic --config config.main_strategy_i37_strong_market_effective_participation_20260625.yaml --candidate-folds reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/admission/strategy_admission_candidate_folds.csv --strategy strong_market_effective_participation_v1 --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_38__strong_market_reachability_diagnostic/filter_diagnostic`

## Fold Summary

| fold | strong_days | eligible_days | strong_rebal | candidate_rebal | fixed_rebal | dynamic_rebal | avg_candidates | avg_bench_members | eligible_bench_w | panel_top20_eligible_w | max_candidates | trades | avg_live | main_bottleneck |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 7/243 | 7/243 | 7/243 | 7/243 | 243 | 0 | 0.52 | 110.81 | 0.1118 | 0.0579 | 25 | 10 | 18.00 | strong_index_context_too_rare |
| 2 | 0/243 | 0/243 | 0/243 | 0/243 | 243 | 0 | 0.00 | 102.49 | 0.0000 | 0.0000 | 0 | 0 | 0.00 | strong_index_context_too_rare |
| 3 | 0/241 | 0/241 | 0/241 | 0/241 | 241 | 0 | 0.00 | 108.46 | 0.0000 | 0.0000 | 0 | 0 | 0.00 | strong_index_context_too_rare |
| 4 | 0/241 | 0/241 | 0/241 | 0/241 | 241 | 0 | 0.00 | 108.66 | 0.0000 | 0.0000 | 0 | 0 | 0.00 | strong_index_context_too_rare |
| 5 | 61/242 | 61/242 | 61/242 | 61/242 | 242 | 0 | 4.16 | 95.39 | 0.0905 | 0.0393 | 48 | 68 | 15.34 | eligible_but_construction_or_hold_rules_limit_trades |

## Interpretation

- Fold 1: Strong-index gate was rarely true, so the strategy mostly stayed in cash. eligible_new_buy_days=7, trades=10.
- Fold 2: Strong-index gate was rarely true, so the strategy mostly stayed in cash. eligible_new_buy_days=0, trades=0.
- Fold 3: Strong-index gate was rarely true, so the strategy mostly stayed in cash. eligible_new_buy_days=0, trades=0.
- Fold 4: Strong-index gate was rarely true, so the strategy mostly stayed in cash. eligible_new_buy_days=0, trades=0.
- Fold 5: The strategy opened positions, so failure should be explained by return quality rather than only by empty exposure. eligible_new_buy_days=61, trades=68.

## Funnel Notes

The funnel is diagnostic only. It does not change admission status and must not be used to tune thresholds inside this run.

| fold | step | avg_count | days_nonzero | valid_days |
| --- | --- | --- | --- | --- |
| 1 | hard_base | 9.58 | 237 | 243 |
| 1 | strong_index_context | 3.45 | 7 | 243 |
| 1 | eligible_for_new_buy | 0.52 | 7 | 243 |
| 2 | hard_base | 10.20 | 237 | 243 |
| 2 | strong_index_context | 0.00 | 0 | 243 |
| 2 | eligible_for_new_buy | 0.00 | 0 | 243 |
| 3 | hard_base | 8.53 | 234 | 241 |
| 3 | strong_index_context | 0.00 | 0 | 241 |
| 3 | eligible_for_new_buy | 0.00 | 0 | 241 |
| 4 | hard_base | 13.49 | 236 | 241 |
| 4 | strong_index_context | 0.00 | 0 | 241 |
| 4 | eligible_for_new_buy | 0.00 | 0 | 241 |
| 5 | hard_base | 15.38 | 242 | 242 |
| 5 | strong_index_context | 30.15 | 61 | 242 |
| 5 | eligible_for_new_buy | 4.16 | 61 | 242 |
