# Phase 0 Strategy Effectiveness Gate

Generated at: 2026-05-30T04:15:28

Overall verdict: FAIL

| gate | status |
| --- | --- |
| annualized_return_mean > 0 | PASS |
| sharpe_mean > 0.5 | PASS |
| max_drawdown_mean > -0.25 | PASS |
| win_rate_mean > 0.45 | FAIL |
| oos_return_decay_ratio < 0.30 | PASS |

## Snapshot

| metric | value |
| --- | --- |
| status | ok |
| fold_count | 2 |
| symbol_count | 1 |
| annualized_return_mean | 0.11205707183468916 |
| sharpe_mean | 0.7833169469012886 |
| max_drawdown_mean | -0.06442244506196493 |
| win_rate_mean | 0.2581967213114754 |
| turnover_annual_mean | 4.72775798738143 |
| selected_candidate | quality_growth_price_v1 |
| candidate_comparison | legacy_momentum: score=0.3546, ann=0.3287, sharpe=0.3400, mdd=-0.2995; ma_kline_baseline_v1: score=-3.4433, ann=-0.3641, sharpe=-3.0551, mdd=-0.4123; residual_momentum_reversal_v1: score=-0.7985, ann=-0.0743, sharpe=-0.6631, mdd=-0.1965; residual_momentum_reversal_v2: score=-1.0221, ann=-0.1167, sharpe=-0.8768, mdd=-0.1740; quality_growth_price_v1: score=0.8071, ann=0.1121, sharpe=0.7833, mdd=-0.0644; multifactor_volume_price_filter_v1: score=-0.4769, ann=-0.0521, sharpe=-0.4047, mdd=-0.0921 |
| candidate_summary_rows | [{'candidate': 'quality_growth_price_v1', 'score': 0.8071342602876508, 'fold_count': 2, 'annualized_return_mean': 0.11205707183468916, 'sharpe_mean': 0.7833169469012886, 'max_drawdown_mean': -0.06442244506196493, 'win_rate_mean': 0.2581967213114754, 'turnover_annual_mean': 4.72775798738143}, {'candidate': 'legacy_momentum', 'score': 0.3545679898974481, 'fold_count': 228, 'annualized_return_mean': 0.3286934644837701, 'sharpe_mean': 0.3399689819348769, 'max_drawdown_mean': -0.2994954485586279, 'win_rate_mean': 0.46205891053967063, 'turnover_annual_mean': 52.34649122807018}, {'candidate': 'multifactor_volume_price_filter_v1', 'score': -0.4768546920362081, 'fold_count': 2, 'annualized_return_mean': -0.05206494905328152, 'sharpe_mean': -0.4047477305216181, 'max_drawdown_mean': -0.09214897397589844, 'win_rate_mean': 0.22727272727272727, 'turnover_annual_mean': 26.37457496336278}, {'candidate': 'residual_momentum_reversal_v1', 'score': -0.7985225967432308, 'fold_count': 2, 'annualized_return_mean': -0.07427508856231668, 'sharpe_mean': -0.6631244766527817, 'max_drawdown_mean': -0.19652115161858147, 'win_rate_mean': 0.46111111111111114, 'turnover_annual_mean': 24.003015447456846}, {'candidate': 'residual_momentum_reversal_v2', 'score': -1.0221231522709011, 'fold_count': 2, 'annualized_return_mean': -0.11672974288743493, 'sharpe_mean': -0.8767824583304377, 'max_drawdown_mean': -0.17395164499349197, 'win_rate_mean': 0.412600303621774, 'turnover_annual_mean': 67.1516698566065}, {'candidate': 'ma_kline_baseline_v1', 'score': -3.4433395832733136, 'fold_count': 2, 'annualized_return_mean': -0.3641392951791935, 'sharpe_mean': -3.055128682237379, 'max_drawdown_mean': -0.41228250689267565, 'win_rate_mean': 0.3698031581224313, 'turnover_annual_mean': 46.36625900059713}] |
| oos_fold_count | 1 |
| oos_annualized_return_mean | 0.22411414366937832 |
| oos_sharpe_mean | 1.5666338938025772 |
| oos_return_decay_ratio | 0.0 |
