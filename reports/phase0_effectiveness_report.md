# Phase 0 Strategy Effectiveness Gate

Generated at: 2026-06-05T09:22:33

Overall verdict: FAIL

## Base Gate

| gate | status |
| --- | --- |
| selected_candidate_eligible == True | PASS |
| annualized_return_mean > 0.00 | FAIL |
| sharpe_mean > 0.50 | FAIL |
| max_drawdown_mean > -0.25 | PASS |
| win_rate_mean > 0.45 | PASS |
| oos_return_decay_ratio < 0.30 | PASS |

## Robustness Gate

| gate | status |
| --- | --- |
| oos_fold_count >= 2 | FAIL |
| oos_annualized_return_mean > 0.00 | PASS |
| oos_sharpe_mean > 0.50 | FAIL |
| positive_fold_ratio >= 0.75 | FAIL |
| negative_fold_count <= 1 | FAIL |
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
| annualized_return_mean | -0.025532506411103884 |
| sharpe_mean | -0.2432513671297904 |
| max_drawdown_mean | -0.14465572657744502 |
| win_rate_mean | 0.4820717131474104 |
| turnover_annual_mean | 2.1039271245251743 |
| positive_fold_count | 2 |
| negative_fold_count | 2 |
| positive_fold_ratio | 0.5 |
| min_fold_annualized_return | -0.10573668205755271 |
| min_fold_sharpe | -0.9920788327043395 |
| selected_candidate | legacy_momentum_low_turnover_v1 |
| selected_candidate_eligible | True |
| selected_candidate_governance_reason | eligible |
| candidate_comparison | legacy_momentum: score=-2.5362, selection_score=-2.5362, eligible=True, ann=-0.2664, sharpe=-2.2413, mdd=-0.3233; legacy_momentum_low_turnover_v1: score=-0.3283, selection_score=-0.3283, eligible=True, ann=-0.0255, sharpe=-0.2433, mdd=-0.1447; ma_kline_baseline_v1: score=-4.7518, selection_score=-4.7518, eligible=True, ann=-0.4824, sharpe=-4.2597, mdd=-0.5018; residual_momentum_reversal_v1: score=-3.3162, selection_score=-3.3162, eligible=True, ann=-0.3004, sharpe=-3.0075, mdd=-0.3170; residual_momentum_reversal_v2: score=-5.5284, selection_score=-5.5284, eligible=True, ann=-0.4960, sharpe=-5.0267, mdd=-0.5074; quality_growth_price_v1: score=-2.2383, selection_score=-2.2383, eligible=True, ann=-0.1675, sharpe=-2.0362, mdd=-0.2366; multifactor_volume_price_filter_v1: score=-1.8829, selection_score=-1.8829, eligible=True, ann=-0.1736, sharpe=-1.6975, mdd=-0.1972 |
| candidate_summary_rows | [{'candidate': 'legacy_momentum_low_turnover_v1', 'score': -0.3283454836240649, 'selection_score': -0.3283454836240649, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.025532506411103884, 'sharpe_mean': -0.2432513671297904, 'max_drawdown_mean': -0.14465572657744502, 'win_rate_mean': 0.4820717131474104, 'turnover_annual_mean': 2.1039271245251743}, {'candidate': 'multifactor_volume_price_filter_v1', 'score': -1.882889885843736, 'selection_score': -1.882889885843736, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.17361161840107914, 'sharpe_mean': -1.6974762819612503, 'max_drawdown_mean': -0.1972155893638924, 'win_rate_mean': 0.35066866598735014, 'turnover_annual_mean': 38.73649697002608}, {'candidate': 'quality_growth_price_v1', 'score': -2.23825436570778, 'selection_score': -2.23825436570778, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.16746558506466175, 'sharpe_mean': -2.0362210454897083, 'max_drawdown_mean': -0.23660105537148152, 'win_rate_mean': 0.4132630638219244, 'turnover_annual_mean': 23.57448373176523}, {'candidate': 'legacy_momentum', 'score': -2.536169087936023, 'selection_score': -2.536169087936023, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.2663706492530915, 'sharpe_mean': -2.24131593451157, 'max_drawdown_mean': -0.3233356575958144, 'win_rate_mean': 0.4123505976095618, 'turnover_annual_mean': 15.113012641063715}, {'candidate': 'residual_momentum_reversal_v1', 'score': -3.3162322647456324, 'selection_score': -3.3162322647456324, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.30042267363120523, 'sharpe_mean': -3.007528009806733, 'max_drawdown_mean': -0.31698583624659327, 'win_rate_mean': 0.3849165218508854, 'turnover_annual_mean': 28.662151769780454}, {'candidate': 'ma_kline_baseline_v1', 'score': -4.751801930586018, 'selection_score': -4.751801930586018, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.4824491233852628, 'sharpe_mean': -4.259693464719366, 'max_drawdown_mean': -0.5017678083480444, 'win_rate_mean': 0.34505323868677906, 'turnover_annual_mean': 42.09171025132792}, {'candidate': 'residual_momentum_reversal_v2', 'score': -5.5283753835137075, 'selection_score': -5.5283753835137075, 'eligible_for_selection': True, 'governance_reason': 'eligible', 'fold_count': 4, 'symbol_count': 1, 'panel_scope': 'portfolio', 'annualized_return_mean': -0.4960321509111384, 'sharpe_mean': -5.026654327997665, 'max_drawdown_mean': -0.507409960120946, 'win_rate_mean': 0.3290376230419148, 'turnover_annual_mean': 64.04845144390329}] |
| universe_fold_count | 4 |
| universe_symbol_count_mean | 120.0 |
| universe_symbol_count_min | 120 |
| universe_source | local_history_sqlite_as_of |
| oos_fold_count | 1 |
| oos_annualized_return_mean | 0.04085704284890257 |
| oos_sharpe_mean | 0.36759750664643603 |
| oos_positive_fold_count | 1 |
| oos_positive_fold_ratio | 1.0 |
| oos_min_fold_annualized_return | 0.04085704284890257 |
| oos_return_decay_ratio | -1.857218277416713 |
