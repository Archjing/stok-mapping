# Phase 0 Strategy Effectiveness Gate

Generated at: 2026-06-03T21:51:08

Overall verdict: FAIL

## Base Gate

| gate | status |
| --- | --- |
| selected_candidate_eligible == True | PASS |
| annualized_return_mean > 0.00 | PASS |
| sharpe_mean > 0.50 | FAIL |
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
| universe_mode | point_in_time |
| universe_lookahead_guard | True |
| fold_count | 4 |
| symbol_count | 1 |
| annualized_return_mean | 0.01720626072664841 |
| sharpe_mean | 0.010184350245621643 |
| max_drawdown_mean | -0.10893979140221807 |
| win_rate_mean | 0.4621513944223108 |
| turnover_annual_mean | 1.8732107860640914 |
| positive_fold_count | 3 |
| negative_fold_count | 1 |
| positive_fold_ratio | 0.75 |
| min_fold_annualized_return | -0.14670077704842488 |
| min_fold_sharpe | -1.533148050529403 |
| selected_candidate | legacy_momentum_low_turnover_v1 |
| selected_candidate_eligible | True |
| selected_candidate_governance_reason | eligible |
| candidate_comparison | legacy_momentum: score=-2.4680, selection_score=-2.4680, eligible=True, ann=-0.2571, sharpe=-2.1792, mdd=-0.3204; legacy_momentum_low_turnover_v1: score=-0.0357, selection_score=-0.0357, eligible=True, ann=0.0172, sharpe=0.0102, mdd=-0.1089; ma_kline_baseline_v1: score=-4.6233, selection_score=-4.6233, eligible=True, ann=-0.4733, sharpe=-4.1393, mdd=-0.4947; residual_momentum_reversal_v1: score=-3.4191, selection_score=-3.4191, eligible=True, ann=-0.3181, sharpe=-3.0893, mdd=-0.3415; residual_momentum_reversal_v2: score=-4.3548, selection_score=-4.3548, eligible=True, ann=-0.4300, sharpe=-3.9108, mdd=-0.4580; quality_growth_price_v1: score=-2.8104, selection_score=-2.8104, eligible=True, ann=-0.2226, sharpe=-2.5648, mdd=-0.2686; multifactor_volume_price_filter_v1: score=-2.4613, selection_score=-2.4613, eligible=True, ann=-0.1687, sharpe=-2.2864, mdd=-0.1813 |
| candidate_summary_rows | [{'candidate': 'legacy_momentum_low_turnover_v1', 'score': -0.03568241509216319, 'selection_score': -0.03568241509216319, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': 0.01720626072664841, 'sharpe_mean': 0.010184350245621643, 'max_drawdown_mean': -0.10893979140221807, 'win_rate_mean': 0.4621513944223108, 'turnover_annual_mean': 1.8732107860640914}, {'candidate': 'multifactor_volume_price_filter_v1', 'score': -2.461329030137581, 'selection_score': -2.461329030137581, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.16867114540827643, 'sharpe_mean': -2.286367423590237, 'max_drawdown_mean': -0.18125206768641144, 'win_rate_mean': 0.3579040891540892, 'turnover_annual_mean': 38.85740499265508}, {'candidate': 'legacy_momentum', 'score': -2.4680071770790617, 'selection_score': -2.4680071770790617, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.25714968784625825, 'sharpe_mean': -2.1792093677715427, 'max_drawdown_mean': -0.32044593076878003, 'win_rate_mean': 0.4073705179282869, 'turnover_annual_mean': 15.096177275803607}, {'candidate': 'quality_growth_price_v1', 'score': -2.8104373119859085, 'selection_score': -2.8104373119859085, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.22263789751939955, 'sharpe_mean': -2.56480967851168, 'max_drawdown_mean': -0.26861736942905734, 'win_rate_mean': 0.40852090433446936, 'turnover_annual_mean': 23.1748762935221}, {'candidate': 'residual_momentum_reversal_v1', 'score': -3.419107311781983, 'selection_score': -3.419107311781983, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.3181209479911882, 'sharpe_mean': -3.0892948297220437, 'max_drawdown_mean': -0.34150401612868964, 'win_rate_mean': 0.386931185638988, 'turnover_annual_mean': 29.822795799377047}, {'candidate': 'residual_momentum_reversal_v2', 'score': -4.354818491828333, 'selection_score': -4.354818491828333, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.4299932956688449, 'sharpe_mean': -3.910812819150047, 'max_drawdown_mean': -0.45801804968772597, 'win_rate_mean': 0.3630954238481604, 'turnover_annual_mean': 62.34209513679688}, {'candidate': 'ma_kline_baseline_v1', 'score': -4.623291442377276, 'selection_score': -4.623291442377276, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.4732630143103249, 'sharpe_mean': -4.139305492524455, 'max_drawdown_mean': -0.4947088853953165, 'win_rate_mean': 0.33920782805875976, 'turnover_annual_mean': 43.74933298864714}] |
| universe_fold_count | 4 |
| universe_symbol_count_mean | 120.0 |
| universe_symbol_count_min | 120 |
| universe_source | local_history_sqlite_as_of |
| oos_fold_count | 1 |
| oos_annualized_return_mean | 0.17335412856165466 |
| oos_sharpe_mean | 1.0658456032586796 |
| oos_positive_fold_count | 1 |
| oos_positive_fold_ratio | 1.0 |
| oos_min_fold_annualized_return | 0.17335412856165466 |
| oos_return_decay_ratio | -5.975288767005338 |
