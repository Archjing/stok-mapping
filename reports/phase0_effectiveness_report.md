# Phase 0 Strategy Effectiveness Gate

Generated at: 2026-06-03T17:41:07

Overall verdict: FAIL

## Base Gate

| gate | status |
| --- | --- |
| selected_candidate_eligible == True | PASS |
| annualized_return_mean > 0.00 | PASS |
| sharpe_mean > 0.50 | PASS |
| max_drawdown_mean > -0.25 | PASS |
| win_rate_mean > 0.45 | PASS |
| oos_return_decay_ratio < 0.30 | PASS |

## Robustness Gate

| gate | status |
| --- | --- |
| oos_fold_count >= 2 | FAIL |
| oos_annualized_return_mean > 0.00 | PASS |
| oos_sharpe_mean > 0.50 | PASS |
| positive_fold_ratio >= 0.75 | PASS |
| negative_fold_count <= 1 | PASS |
| min_fold_annualized_return > -0.10 | FAIL |
| oos_positive_fold_ratio >= 1.00 | PASS |

## Snapshot

| metric | value |
| --- | --- |
| status | ok |
| fold_count | 4 |
| symbol_count | 1 |
| annualized_return_mean | 0.11212763383832514 |
| sharpe_mean | 0.82036890964417 |
| max_drawdown_mean | -0.11099878689840137 |
| win_rate_mean | 0.5 |
| turnover_annual_mean | 1.4864332695558795 |
| positive_fold_count | 3 |
| negative_fold_count | 1 |
| positive_fold_ratio | 0.75 |
| min_fold_annualized_return | -0.11172374473701674 |
| min_fold_sharpe | -0.9761356411380427 |
| selected_candidate | legacy_momentum_low_turnover_v1 |
| selected_candidate_eligible | True |
| selected_candidate_governance_reason | eligible |
| candidate_comparison | legacy_momentum: score=-0.6982, selection_score=-0.6982, eligible=True, ann=-0.0536, sharpe=-0.5634, mdd=-0.2160; legacy_momentum_low_turnover_v1: score=0.8209, selection_score=0.8209, eligible=True, ann=0.1121, sharpe=0.8204, mdd=-0.1110; ma_kline_baseline_v1: score=-3.9748, selection_score=-3.9748, eligible=True, ann=-0.4203, sharpe=-3.5391, mdd=-0.4512; residual_momentum_reversal_v1: score=-2.7499, selection_score=-2.7499, eligible=True, ann=-0.2593, sharpe=-2.4780, mdd=-0.2845; residual_momentum_reversal_v2: score=-3.5346, selection_score=-3.5346, eligible=True, ann=-0.3676, sharpe=-3.1566, mdd=-0.3884; quality_growth_price_v1: score=-1.6060, selection_score=-1.6060, eligible=True, ann=-0.1173, sharpe=-1.4395, mdd=-0.2158; multifactor_volume_price_filter_v1: score=-2.3810, selection_score=-2.3810, eligible=True, ann=-0.2528, sharpe=-2.1113, mdd=-0.2866 |
| candidate_summary_rows | [{'candidate': 'legacy_momentum_low_turnover_v1', 'score': 0.8209333331141317, 'selection_score': 0.8209333331141317, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': 0.11212763383832514, 'sharpe_mean': 0.82036890964417, 'max_drawdown_mean': -0.11099878689840137, 'win_rate_mean': 0.5, 'turnover_annual_mean': 1.4864332695558795}, {'candidate': 'legacy_momentum', 'score': -0.698212792870187, 'selection_score': -0.698212792870187, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.05364503246099306, 'sharpe_mean': -0.563384634756551, 'max_drawdown_mean': -0.21601128376627918, 'win_rate_mean': 0.4456414342629482, 'turnover_annual_mean': 13.330491943793891}, {'candidate': 'quality_growth_price_v1', 'score': -1.6060274807827206, 'selection_score': -1.6060274807827206, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.11733829958624692, 'sharpe_mean': -1.439470208594304, 'max_drawdown_mean': -0.21577624479058616, 'win_rate_mean': 0.4368095728752457, 'turnover_annual_mean': 24.889889382742616}, {'candidate': 'multifactor_volume_price_filter_v1', 'score': -2.381035007013952, 'selection_score': -2.381035007013952, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.25282610917176457, 'sharpe_mean': -2.1113161616125318, 'max_drawdown_mean': -0.28661158163107536, 'win_rate_mean': 0.3661421552879421, 'turnover_annual_mean': 49.40227651427101}, {'candidate': 'residual_momentum_reversal_v1', 'score': -2.7499319165190093, 'selection_score': -2.7499319165190093, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.25928417928709685, 'sharpe_mean': -2.478017936544697, 'max_drawdown_mean': -0.28454378066152786, 'win_rate_mean': 0.4038791691404132, 'turnover_annual_mean': 29.223392209388788}, {'candidate': 'residual_momentum_reversal_v2', 'score': -3.5346068523979555, 'selection_score': -3.5346068523979555, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.3676420457837456, 'sharpe_mean': -3.156599293178434, 'max_drawdown_mean': -0.3883730726552978, 'win_rate_mean': 0.3672483479406185, 'turnover_annual_mean': 65.22436687171049}, {'candidate': 'ma_kline_baseline_v1', 'score': -3.9748156488447477, 'selection_score': -3.9748156488447477, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.42027169949276166, 'sharpe_mean': -3.5390618422554643, 'max_drawdown_mean': -0.4512359136858049, 'win_rate_mean': 0.3483543825791566, 'turnover_annual_mean': 40.4374587328078}] |
| oos_fold_count | 1 |
| oos_annualized_return_mean | 0.2921301628510151 |
| oos_sharpe_mean | 2.103897672084983 |
| oos_positive_fold_count | 1 |
| oos_positive_fold_ratio | 1.0 |
| oos_min_fold_annualized_return | 0.2921301628510151 |
| oos_return_decay_ratio | -4.60422305260999 |
