# Phase 0 Strategy Effectiveness Gate

Generated at: 2026-05-29T01:24:00

Overall verdict: FAIL

| gate | status |
| --- | --- |
| annualized_return_mean > 0 | PASS |
| sharpe_mean > 0.5 | FAIL |
| max_drawdown_mean > -0.25 | PASS |
| win_rate_mean > 0.45 | PASS |
| oos_return_decay_ratio < 0.30 | PASS |

## Snapshot

| metric | value |
| --- | --- |
| status | ok |
| fold_count | 10 |
| symbol_count | 5 |
| annualized_return_mean | 0.2124481236571234 |
| sharpe_mean | 0.3217540894231791 |
| max_drawdown_mean | -0.23843754799092323 |
| win_rate_mean | 0.45756419089284356 |
| turnover_annual_mean | 51.3 |
| selected_candidate | legacy_momentum |
| candidate_comparison | legacy_momentum: score=0.3088, ann=0.2124, sharpe=0.3218, mdd=-0.2384; filtered_single_v2: score=-0.1651, ann=0.0068, sharpe=-0.1244, mdd=-0.0883; portfolio_v2: score=-0.7400, ann=-0.0783, sharpe=-0.6024, mdd=-0.1968 |
| oos_fold_count | 2 |
| oos_annualized_return_mean | 0.822730777832632 |
| oos_sharpe_mean | 1.391553622158883 |
| oos_return_decay_ratio | -12.74024175836119 |
