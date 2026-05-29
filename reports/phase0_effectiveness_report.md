# Phase 0 Strategy Effectiveness Gate

Generated at: 2026-05-30T01:04:47

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
| fold_count | 228 |
| symbol_count | 118 |
| annualized_return_mean | 0.3286934644837701 |
| sharpe_mean | 0.3399689819348769 |
| max_drawdown_mean | -0.2994954485586279 |
| win_rate_mean | 0.46205891053967063 |
| turnover_annual_mean | 52.34649122807018 |
| selected_candidate | legacy_momentum |
| candidate_comparison | legacy_momentum: score=0.3546, ann=0.3287, sharpe=0.3400, mdd=-0.2995; residual_momentum_reversal_v1: score=-0.8733, ann=-0.0789, sharpe=-0.7372, mdd=-0.1931 |
| candidate_summary_rows | [{'candidate': 'legacy_momentum', 'score': 0.3545679898974481, 'fold_count': 228, 'annualized_return_mean': 0.3286934644837701, 'sharpe_mean': 0.3399689819348769, 'max_drawdown_mean': -0.2994954485586279, 'win_rate_mean': 0.46205891053967063, 'turnover_annual_mean': 52.34649122807018}, {'candidate': 'residual_momentum_reversal_v1', 'score': -0.8732561790048554, 'fold_count': 2, 'annualized_return_mean': -0.07892305761559193, 'sharpe_mean': -0.7372491101833379, 'max_drawdown_mean': -0.19309108002744307, 'win_rate_mean': 0.46319444444444446, 'turnover_annual_mean': 33.20910399141714}] |
| oos_fold_count | 45 |
| oos_annualized_return_mean | 0.6377716184227763 |
| oos_sharpe_mean | 0.8544386681095053 |
| oos_return_decay_ratio | -1.5239226077673829 |
