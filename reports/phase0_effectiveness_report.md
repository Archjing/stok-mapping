# Phase 0 Strategy Effectiveness Gate

Generated at: 2026-05-29T07:07:15

Overall verdict: FAIL

| gate | status |
| --- | --- |
| annualized_return_mean > 0 | PASS |
| sharpe_mean > 0.5 | FAIL |
| max_drawdown_mean > -0.25 | FAIL |
| win_rate_mean > 0.45 | PASS |
| oos_return_decay_ratio < 0.30 | PASS |

## Snapshot

| metric | value |
| --- | --- |
| status | ok |
| fold_count | 230 |
| symbol_count | 119 |
| annualized_return_mean | 0.33599064897406206 |
| sharpe_mean | 0.3357946743577156 |
| max_drawdown_mean | -0.30737744830217145 |
| win_rate_mean | 0.46218977423976626 |
| turnover_annual_mean | 51.64782608695652 |
| selected_candidate | legacy_momentum |
| candidate_comparison | legacy_momentum: score=0.3501, ann=0.3360, sharpe=0.3358, mdd=-0.3074; xmarket_single_v2: score=-0.0063, ann=0.0204, sharpe=0.0083, mdd=-0.0497; xmarket_portfolio_v2: score=-0.8181, ann=-0.0636, sharpe=-0.7310, mdd=-0.1106; xmarket_next_open_v1: score=-1.9034, ann=-0.1517, sharpe=-1.7316, mdd=-0.1918; xmarket_magnitude_soft_risk_v1: score=-0.4044, ann=-0.0037, sharpe=-0.3430, mdd=-0.1190; residual_momentum_reversal_v1: score=-0.6410, ann=-0.0670, sharpe=-0.5249, mdd=-0.1652 |
| oos_fold_count | 46 |
| oos_annualized_return_mean | 0.7021640346715546 |
| oos_sharpe_mean | 1.0942470414044476 |
| oos_return_decay_ratio | -1.8724556472813825 |
