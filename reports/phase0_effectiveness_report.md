# Phase 0 Strategy Effectiveness Gate

Generated at: 2026-05-30T22:05:00

Overall verdict: FAIL

| gate | status |
| --- | --- |
| selected_candidate_eligible == True | PASS |
| annualized_return_mean > 0 | PASS |
| sharpe_mean > 0.5 | FAIL |
| max_drawdown_mean > -0.25 | PASS |
| win_rate_mean > 0.45 | PASS |
| oos_return_decay_ratio < 0.30 | PASS |

## Snapshot

| metric | value |
| --- | --- |
| status | ok |
| fold_count | 4 |
| symbol_count | 1 |
| annualized_return_mean | 0.0724299941587006 |
| sharpe_mean | 0.2952365417912636 |
| max_drawdown_mean | -0.18002976991347383 |
| win_rate_mean | 0.4765418326693227 |
| turnover_annual_mean | 13.475825891070368 |
| selected_candidate | legacy_momentum |
| selected_candidate_eligible | True |
| selected_candidate_governance_reason | eligible |
| candidate_comparison | legacy_momentum: score=0.2414, selection_score=0.2414, eligible=True, ann=0.0724, sharpe=0.2952, mdd=-0.1800; ma_kline_baseline_v1: score=-2.0617, selection_score=-2.0617, eligible=True, ann=-0.2410, sharpe=-1.7831, mdd=-0.3162; residual_momentum_reversal_v1: score=-0.9010, selection_score=-0.9010, eligible=True, ann=-0.0878, sharpe=-0.7766, mdd=-0.1610; residual_momentum_reversal_v2: score=-1.6348, selection_score=-1.6348, eligible=True, ann=-0.1896, sharpe=-1.4056, mdd=-0.2688; quality_growth_price_v1: score=-0.8184, selection_score=-0.8184, eligible=True, ann=-0.0308, sharpe=-0.7194, mdd=-0.1672; multifactor_volume_price_filter_v1: score=-0.6869, selection_score=-0.6869, eligible=True, ann=-0.0766, sharpe=-0.5597, mdd=-0.1778 |
| candidate_summary_rows | [{'candidate': 'legacy_momentum', 'score': 0.24143665391387692, 'selection_score': 0.24143665391387692, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': 0.0724299941587006, 'sharpe_mean': 0.2952365417912636, 'max_drawdown_mean': -0.18002976991347383, 'win_rate_mean': 0.4765418326693227, 'turnover_annual_mean': 13.475825891070368}, {'candidate': 'multifactor_volume_price_filter_v1', 'score': -0.686893268409359, 'selection_score': -0.686893268409359, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.07655993954754903, 'sharpe_mean': -0.559706635670556, 'max_drawdown_mean': -0.17781332593005686, 'win_rate_mean': 0.4494419138506755, 'turnover_annual_mean': 48.381046368410466}, {'candidate': 'quality_growth_price_v1', 'score': -0.8184366142134296, 'selection_score': -0.8184366142134296, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.030816463852599285, 'sharpe_mean': -0.7194290300780789, 'max_drawdown_mean': -0.16719870441810192, 'win_rate_mean': 0.46088135559296395, 'turnover_annual_mean': 24.547474126481077}, {'candidate': 'residual_momentum_reversal_v1', 'score': -0.9010192624101534, 'selection_score': -0.9010192624101534, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.08782238731414624, 'sharpe_mean': -0.7765915416782879, 'max_drawdown_mean': -0.16103305414958474, 'win_rate_mean': 0.45855951407219603, 'turnover_annual_mean': 30.169983989125225}, {'candidate': 'residual_momentum_reversal_v2', 'score': -1.6348331706211154, 'selection_score': -1.6348331706211154, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.18959038479912477, 'sharpe_mean': -1.4056290364290576, 'max_drawdown_mean': -0.2688178835849908, 'win_rate_mean': 0.4059143164297136, 'turnover_annual_mean': 59.08127092061222}, {'candidate': 'ma_kline_baseline_v1', 'score': -2.0616781867920233, 'selection_score': -2.0616781867920233, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.2410350096496815, 'sharpe_mean': -1.783079823540779, 'max_drawdown_mean': -0.3161617168528075, 'win_rate_mean': 0.4005151988933546, 'turnover_annual_mean': 41.964290607779056}] |
| oos_fold_count | 1 |
| oos_annualized_return_mean | 0.4026510273368835 |
| oos_sharpe_mean | 2.3475923307726827 |
| oos_return_decay_ratio | -11.696376899895348 |
