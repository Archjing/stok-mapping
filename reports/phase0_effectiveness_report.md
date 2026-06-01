# Phase 0 Strategy Effectiveness Gate

Generated at: 2026-06-02T01:51:58

Overall verdict: PASS

| gate | status |
| --- | --- |
| selected_candidate_eligible == True | PASS |
| annualized_return_mean > 0 | PASS |
| sharpe_mean > 0.5 | PASS |
| max_drawdown_mean > -0.25 | PASS |
| win_rate_mean > 0.45 | PASS |
| oos_return_decay_ratio < 0.30 | PASS |

## Snapshot

| metric | value |
| --- | --- |
| status | ok |
| fold_count | 4 |
| symbol_count | 1 |
| annualized_return_mean | 0.13312709618858617 |
| sharpe_mean | 1.008292015623601 |
| max_drawdown_mean | -0.10417008645710835 |
| win_rate_mean | 0.5109561752988048 |
| turnover_annual_mean | 1.5023090842074356 |
| selected_candidate | legacy_momentum_low_turnover_v1 |
| selected_candidate_eligible | True |
| selected_candidate_governance_reason | eligible |
| candidate_comparison | legacy_momentum: score=-0.6398, selection_score=-0.6398, eligible=True, ann=-0.0439, sharpe=-0.5082, mdd=-0.2193; legacy_momentum_low_turnover_v1: score=1.0228, selection_score=1.0228, eligible=True, ann=0.1331, sharpe=1.0083, mdd=-0.1042; ma_kline_baseline_v1: score=-4.0468, selection_score=-4.0468, eligible=True, ann=-0.4253, sharpe=-3.6044, mdd=-0.4596; residual_momentum_reversal_v1: score=-2.7442, selection_score=-2.7442, eligible=True, ann=-0.2525, sharpe=-2.4770, mdd=-0.2818; residual_momentum_reversal_v2: score=-3.2179, selection_score=-3.2179, eligible=True, ann=-0.3433, sharpe=-2.8521, mdd=-0.3883; quality_growth_price_v1: score=-1.5837, selection_score=-1.5837, eligible=True, ann=-0.1095, sharpe=-1.4224, mdd=-0.2130; multifactor_volume_price_filter_v1: score=-1.9371, selection_score=-1.9371, eligible=True, ann=-0.2059, sharpe=-1.7095, mdd=-0.2493 |
| candidate_summary_rows | [{'candidate': 'legacy_momentum_low_turnover_v1', 'score': 1.0227705204893398, 'selection_score': 1.0227705204893398, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': 0.13312709618858617, 'sharpe_mean': 1.008292015623601, 'max_drawdown_mean': -0.10417008645710835, 'win_rate_mean': 0.5109561752988048, 'turnover_annual_mean': 1.5023090842074356}, {'candidate': 'legacy_momentum', 'score': -0.639800813999546, 'selection_score': -0.639800813999546, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.04388803620203885, 'sharpe_mean': -0.5081821109556561, 'max_drawdown_mean': -0.2193493698857409, 'win_rate_mean': 0.44862948207171316, 'turnover_annual_mean': 13.475825891070368}, {'candidate': 'quality_growth_price_v1', 'score': -1.5836605095470437, 'selection_score': -1.5836605095470437, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.1095160268299259, 'sharpe_mean': -1.4223777987880144, 'max_drawdown_mean': -0.21304939468813267, 'win_rate_mean': 0.43814122213446804, 'turnover_annual_mean': 24.79228539531689}, {'candidate': 'multifactor_volume_price_filter_v1', 'score': -1.9370563211386487, 'selection_score': -1.9370563211386487, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.20587823633882896, 'sharpe_mean': -1.709464368408745, 'max_drawdown_mean': -0.2493056691209785, 'win_rate_mean': 0.37991624655979533, 'turnover_annual_mean': 44.58351893621584}, {'candidate': 'residual_momentum_reversal_v1', 'score': -2.7441629714093954, 'selection_score': -2.7441629714093954, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.2524717285496828, 'sharpe_mean': -2.477032353795738, 'max_drawdown_mean': -0.2817895066776318, 'win_rate_mean': 0.4057084052839571, 'turnover_annual_mean': 30.00128633987981}, {'candidate': 'residual_momentum_reversal_v2', 'score': -3.2179198095012453, 'selection_score': -3.2179198095012453, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.3432955886465955, 'sharpe_mean': -2.8521194297467463, 'max_drawdown_mean': -0.3883051708624021, 'win_rate_mean': 0.3634294149866897, 'turnover_annual_mean': 63.41078969952978}, {'candidate': 'ma_kline_baseline_v1', 'score': -4.046846342750388, 'selection_score': -4.046846342750388, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.42528995437531203, 'sharpe_mean': -3.604413988437761, 'max_drawdown_mean': -0.4595747542499415, 'win_rate_mean': 0.35129223470358484, 'turnover_annual_mean': 40.34468929876793}] |
| oos_fold_count | 1 |
| oos_annualized_return_mean | 0.28334493863104626 |
| oos_sharpe_mean | 2.0430343095309547 |
| oos_return_decay_ratio | -2.411555062023421 |
