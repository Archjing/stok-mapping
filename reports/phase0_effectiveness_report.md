# Phase 0 Strategy Effectiveness Gate

Generated at: 2026-05-30T19:23:35

Overall verdict: FAIL

| gate | status |
| --- | --- |
| selected_candidate_eligible == True | PASS |
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
| selected_candidate_eligible | True |
| selected_candidate_governance_reason | eligible |
| candidate_comparison | legacy_momentum: score=0.3546, selection_score=0.3546, eligible=True, ann=0.3287, sharpe=0.3400, mdd=-0.2995; ma_kline_baseline_v1: score=-3.4433, selection_score=-1000000.0000, eligible=False, ann=-0.3641, sharpe=-3.0551, mdd=-0.4123; residual_momentum_reversal_v1: score=-0.8733, selection_score=-1000000.0000, eligible=False, ann=-0.0789, sharpe=-0.7372, mdd=-0.1931; residual_momentum_reversal_v2: score=-1.0221, selection_score=-1000000.0000, eligible=False, ann=-0.1167, sharpe=-0.8768, mdd=-0.1740; quality_growth_price_v1: score=0.9902, selection_score=-1000000.0000, eligible=False, ann=0.1278, sharpe=0.9543, mdd=-0.0561; multifactor_volume_price_filter_v1: score=-0.4769, selection_score=-1000000.0000, eligible=False, ann=-0.0521, sharpe=-0.4047, mdd=-0.0921 |
| candidate_summary_rows | [{'candidate': 'legacy_momentum', 'score': 0.3545679898974481, 'selection_score': 0.3545679898974481, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 228, 'symbol_count': 118, 'panel_scope': 'symbol', 'annualized_return_mean': 0.3286934644837701, 'sharpe_mean': 0.3399689819348769, 'max_drawdown_mean': -0.2994954485586279, 'win_rate_mean': 0.46205891053967063, 'turnover_annual_mean': 52.34649122807018}, {'candidate': 'ma_kline_baseline_v1', 'score': -3.4433395832733136, 'selection_score': -1000000.0, 'eligible_for_selection': False, 'governance_reason': 'portfolio_fold_count<4', 'fold_count': 2, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.3641392951791935, 'sharpe_mean': -3.055128682237379, 'max_drawdown_mean': -0.41228250689267565, 'win_rate_mean': 0.3698031581224313, 'turnover_annual_mean': 46.36625900059713}, {'candidate': 'residual_momentum_reversal_v1', 'score': -0.8732561790048554, 'selection_score': -1000000.0, 'eligible_for_selection': False, 'governance_reason': 'portfolio_fold_count<4', 'fold_count': 2, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.07892305761559193, 'sharpe_mean': -0.7372491101833379, 'max_drawdown_mean': -0.19309108002744307, 'win_rate_mean': 0.46319444444444446, 'turnover_annual_mean': 33.20910399141714}, {'candidate': 'residual_momentum_reversal_v2', 'score': -1.0221231522709011, 'selection_score': -1000000.0, 'eligible_for_selection': False, 'governance_reason': 'portfolio_fold_count<4', 'fold_count': 2, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.11672974288743493, 'sharpe_mean': -0.8767824583304377, 'max_drawdown_mean': -0.17395164499349197, 'win_rate_mean': 0.412600303621774, 'turnover_annual_mean': 67.1516698566065}, {'candidate': 'quality_growth_price_v1', 'score': 0.9901563785179793, 'selection_score': -1000000.0, 'eligible_for_selection': False, 'governance_reason': 'portfolio_fold_count<4', 'fold_count': 2, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': 0.12781019012171402, 'sharpe_mean': 0.9543019987115807, 'max_drawdown_mean': -0.05610143050891675, 'win_rate_mean': 0.2581967213114754, 'turnover_annual_mean': 13.419150675756377}, {'candidate': 'multifactor_volume_price_filter_v1', 'score': -0.4768546920362081, 'selection_score': -1000000.0, 'eligible_for_selection': False, 'governance_reason': 'portfolio_fold_count<4', 'fold_count': 2, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.05206494905328152, 'sharpe_mean': -0.4047477305216181, 'max_drawdown_mean': -0.09214897397589844, 'win_rate_mean': 0.22727272727272727, 'turnover_annual_mean': 26.37457496336278}] |
| oos_fold_count | 45 |
| oos_annualized_return_mean | 0.6377716184227763 |
| oos_sharpe_mean | 0.8544386681095053 |
| oos_return_decay_ratio | -1.5239226077673829 |
