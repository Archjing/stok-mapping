# Claude Agent Output

- generated_at: 2026-06-03T16:58:13
- model: claude-opus-4-8[1M]
- dry_run: true

## Prompt Preview

# Task
基于当前 Phase 0 报告生成研究摘要、风险提示、失效条件和下一步验证建议。

# Constraints
- 输出语言：中文。
- 只做研究辅助、风险提示、验证建议和待办整理。
- 不输出买入、卖出、清仓、满仓等交易指令。
- 不擅自改变策略逻辑或策略参数。
- 若引用结论，注明来自哪个本地文件。

# Project Context
## reports/phase0_effectiveness_report.md

```text
# Phase 0 Strategy Effectiveness Gate

Generated at: 2026-06-02T02:10:40

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

```

## reports/phase0_walk_forward_report.md

```text
# Phase 0 Walk-Forward Report

Generated at: 2026-06-02T02:10:40

## Summary

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
| oos_fold_count | 1 |
| oos_annualized_return_mean | 0.28334493863104626 |
| oos_sharpe_mean | 2.0430343095309547 |
| oos_return_decay_ratio | -2.411555062023421 |

## Candidate Summary

| candidate | score | selection_score | eligible | governance_reason | fold_count | symbol_count | panel_scope | annualized_return_mean | sharpe_mean | max_drawdown_mean | win_rate_mean | turnover_annual_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| legacy_momentum_low_turnover_v1 | 1.0228 | 1.0228 | True | eligible | 4 | 1 | portfolio | 0.1331 | 1.0083 | -0.1042 | 0.5110 | 1.50 |
| legacy_momentum | -0.6398 | -0.6398 | True | eligible | 4 | 1 | portfolio | -0.0439 | -0.5082 | -0.2193 | 0.4486 | 13.48 |
| quality_growth_price_v1 | -1.5837 | -1.5837 | True | eligible | 4 | 1 | portfolio | -0.1095 | -1.4224 | -0.2130 | 0.4381 | 24.79 |
| multifactor_volume_price_filter_v1 | -1.9371 | -1.9371 | True | eligible | 4 | 1 | portfolio | -0.2059 | -1.7095 | -0.2493 | 0.3799 | 44.58 |
| residual_momentum_reversal_v1 | -2.7442 | -2.7442 | True | eligible | 4 | 1 | portfolio | -0.2525 | -2.4770 | -0.2818 | 0.4057 | 30.00 |
| residual_momentum_reversal_v2 | -3.2179 | -3.2179 | True | eligible | 4 | 1 | portfolio | -0.3433 | -2.8521 | -0.3883 | 0.3634 | 63.41 |
| ma_kline_baseline_v1 | -4.0468 | -4.0468 | True | eligible | 4 | 1 | portfolio | -0.4253 | -3.6044 | -0.4596 | 0.3513 | 40.34 |

## Fold Details

| symbol | fold | train_start | train_end | valid_start | valid_end | annual_ret | sharpe | max_dd | win_rate | turnover_annual | trades | selected_params |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PORTFOLIO | 1 | 2019-07-30 | 2021-08-23 | 2021-08-24 | 2022-09-06 | -0.0326 | -0.2618 | -0.1624 | 0.5139 | 1.15 | 13 | mom20@q0.6,hold_q=0.4,buy_top=10,hold_top=20,rebalance=20d,min_hold=5d,turnover_penalty=0.01,target_vol=0.18 |
| PORTFOLIO | 2 | 2020-08-12 | 2022-09-06 | 2022-09-07 | 2023-09-19 | 0.1667 | 1.3865 | -0.0708 | 0.5020 | 1.17 | 13 | mom20@q0.6,hold_q=0.4,buy_top=5,hold_top=10,rebalance=20d,min_hold=5d,turnover_penalty=0.01,target_vol=0.18 |
| PORTFOLIO | 3 | 2021-08-24 | 2023-09-19 | 2023-09-20 | 2024-10-11 | 0.1150 | 0.8654 | -0.1059 | 0.5020 | 2.28 | 13 | mom20@q0.6,hold_q=0.4,buy_top=5,hold_top=10,rebalance=20d,min_hold=5d,turnover_penalty=0.01,target_vol=0.18 |
| PORTFOLIO | 4 | 2022-09-07 | 2024-10-11 | 2024-10-14 | 2025-10-24 | 0.2833 | 2.0430 | -0.0776 | 0.5259 | 1.40 | 16 | mom20@q0.6,hold_q=0.4,buy_top=5,hold_top=10,rebalance=20d,min_hold=5d,turnover_penalty=0.01,target_vol=0.18 |

```

## reports/phase0_data_source_report.md

```text
# Phase 0 Data Source & Quality Report

Generated at: 2026-06-02T02:08:04

## Connectivity

| source | target | status | rows | latest_date | error |
| --- | --- | --- | --- | --- | --- |
| tiingo | NVDA | OK | 1770 | 2026-05-29 |  |
| tiingo | AAPL | OK | 1770 | 2026-05-29 |  |
| tiingo | TSLA | OK | 1770 | 2026-05-29 |  |
| tiingo | KWEB | OK | 1770 | 2026-05-29 |  |
| tushare | trade_cal | OK | 11 | 2026-06-02 |  |
| yfinance | ^NDX | OK | 1771 | 2026-06-01 |  |
| yfinance | ^SOX | OK | 1771 | 2026-06-01 |  |
| yfinance | ^GSPC | OK | 1771 | 2026-06-01 |  |
| yfinance | ^VIX | OK | 1772 | 2026-06-01 |  |
| yfinance | NVDA | OK | 1771 | 2026-06-01 |  |
| yfinance | AAPL | OK | 1771 | 2026-06-01 |  |
| yfinance | TSLA | OK | 1771 | 2026-06-01 |  |
| yfinance | KWEB | OK | 1771 | 2026-06-01 |  |
| yfinance | CNY=X | OK | 1832 | 2026-06-01 |  |
| akshare-cn | SZ.300750 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| akshare-cn | SH.600519 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| akshare-hk | HK.00700 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| akshare-hk | HK.09988 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| manual-history | pre_run_update | FAIL | 0 | 2026-05-29 | too_early; Skipped live spot write before configured min_run_time=16:30; writing now could label intraday quotes as dail |
| us-market-history | pre_run_update | OK | 7648 | 2026-06-01 | updated |

## Quality Audit

| symbol | rows | missing_ratio | ohlc_viol | non_pos | dup_date | latest_date | delay_days |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ^NDX | 1270 | 0.0000 | 0 | 0 | 0 | 2026-06-01 | 1 |
| ^SOX | 1270 | 0.0000 | 0 | 0 | 0 | 2026-06-01 | 1 |
| NVDA | 1270 | 0.0000 | 0 | 0 | 0 | 2026-06-01 | 1 |
| KWEB | 1270 | 0.0000 | 0 | 0 | 0 | 2026-06-01 | 1 |
| ^VIX | 1271 | 0.0000 | 0 | 0 | 0 | 2026-06-01 | 1 |
| CNY=X | 1315 | 0.0000 | 30 | 0 | 0 | 2026-06-01 | 1 |

## Quality Summary

| metric | value |
| --- | --- |
| coverage | 1.0 |
| avg_missing_ratio | 0.0 |
| avg_delay_days | 1.0 |
| total_integrity_violations | 30 |
| score | 96.0 |

```

## data/universe/local_factor_universe_report.md

```text
# Local Factor Universe Report

Generated at: 2026-06-03

## Summary

| metric | value |
| --- | --- |
| source | local_history_sqlite |
| target_size | 500 |
| snapshot_count | 5502 |
| selected_count | 500 |
| has_industry | True |
| has_market_cap | True |
| has_valuation | True |
| has_financial_factors | True |

## Warnings

- AkShare all-A snapshot failed: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
- AkShare all-A snapshot was empty; used configured local history fallback.

## Top Industries

| industry | count |
| --- | --- |
| 半导体 | 60 |
| 电气设备 | 52 |
| 元器件 | 52 |
| 通信设备 | 29 |
| 小金属 | 28 |
| 软件服务 | 21 |
| 专用机械 | 18 |
| 汽车配件 | 14 |
| 化工原料 | 14 |
| 银行 | 13 |
| 火力发电 | 12 |
| 互联网 | 10 |
| 新型电力 | 9 |
| 证券 | 7 |
| IT设备 | 7 |
| 农药化肥 | 7 |
| 航空 | 7 |
| 铜 | 6 |
| 家用电器 | 6 |
| 铝 | 6 |

## Top 20 Symbols

| rank | symbol | name | industry | amount | total_mv | pe_ttm | pb | roe | debt_to_asset |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | SZ.300750 | 宁德时代 | 电气设备 | 15079407518.29 | 1972829068731.00 | 24.98 | 5.48 | 5.98 | 62.32 |
| 2 | SZ.300308 | 中际旭创 | 通信设备 | 22873790484.33 | 1421510493525.00 | 95.09 | 41.05 | 17.54 | 32.64 |
| 3 | SZ.300502 | 新易盛 | 通信设备 | 21433477014.68 | 779040922632.00 | 72.54 | 38.17 | 14.52 | 31.03 |
| 4 | SH.601138 | 工业富联 | 通信设备 | 13175330820.64 | 1608363679618.00 | 39.57 | 9.13 | 6.18 | 61.38 |
| 5 | SH.688256 | 寒武纪 | 半导体 | 13724119385.66 | 865850540579.00 | 318.68 | 70.75 | 8.20 | 16.38 |
| 6 | SZ.300394 | 天孚通信 | 通信设备 | 15356846087.39 | 387538989254.00 | 178.44 | 64.46 | 8.57 | 14.25 |
| 7 | SH.688981 | 中芯国际 | 半导体 | 8605893017.33 | 1073807499602.00 | 212.82 | 7.17 | 0.90 | 34.89 |
| 8 | SZ.002384 | 东山精密 | 元器件 | 14130158555.46 | 410261771093.00 | 201.10 | 18.12 | 5.05 | 63.69 |
| 9 | SH.601899 | 紫金矿业 | 铜 | 9731894286.26 | 831491646230.00 | 13.48 | 4.21 | 10.35 | 51.37 |
| 10 | SZ.002475 | 立讯精密 | 元器件 | 11891588603.71 | 544991768284.00 | 31.66 | 6.17 | 4.20 | 66.53 |
| 11 | SH.603986 | 兆易创新 | 半导体 | 14723507669.34 | 345103659456.00 | 120.05 | 13.94 | 6.12 | 8.13 |
| 12 | SH.688041 | 海光信息 | 半导体 | 8991485640.84 | 664621233741.00 | 243.80 | 28.28 | 2.99 | 22.80 |
| 13 | SZ.300476 | 胜宏科技 | 元器件 | 13982625749.95 | 347355464307.00 | 74.22 | 9.73 | 7.62 | 55.23 |
| 14 | SZ.300274 | 阳光电源 | 电气设备 | 12526911869.64 | 354104511219.00 | 29.69 | 7.50 | 4.81 | 57.51 |
| 15 | SH.688008 | 澜起科技 | 半导体 | 11369561998.44 | 310316585332.00 | 121.33 | 14.89 | 5.39 | 4.17 |
| 16 | SH.600519 | 贵州茅台 | 白酒 | 5594354397.77 | 1602492105138.00 | 19.37 | 5.98 | 10.57 | 12.12 |
| 17 | SZ.002594 | 比亚迪 | 汽车整车 | 5684093570.45 | 864492673113.00 | 31.38 | 3.73 | 1.65 | 70.94 |
| 18 | SZ.002371 | 北方华创 | 半导体 | 5941844498.88 | 445656085621.00 | 79.92 | 11.34 | 4.25 | 50.01 |
| 19 | SH.601869 | 长飞光纤 | 通信设备 | 5806850972.75 | 368409494009.00 | 318.37 | 25.89 | 3.53 | 49.30 |
| 20 | SH.600487 | 亨通光电 | 通信设备 | 10390658114.46 | 225502244058.00 | 69.84 | 6.96 | 3.44 | 51.88 |

```

## config.yaml

```text
phase0:
  benchmark_symbol: "SH.000300"
  years: 7
  symbols:
    - "SZ.300750"
    - "SZ.002594"
    - "SH.688981"
    - "SZ.002475"
    - "SZ.300308"
    - "SZ.300502"
    - "SZ.300394"
    - "SZ.002415"
    - "SZ.000063"
    - "SH.688012"
    - "SZ.002371"
    - "SH.603986"
    - "SZ.002241"
    - "SZ.000725"
    - "SZ.000333"
    - "SZ.000651"
    - "SZ.000858"
    - "SH.600519"
    - "SH.601318"
    - "SH.600036"
    - "SH.600276"
    - "SH.600900"
    - "SH.600030"
  universe:
    enabled: true
    target_size: 500
    min_usable_size: 100
    walk_forward_limit: 120
    output_dir: "data/universe"
    output_file: "local_factor_universe.csv"
    snapshot_file: "a_share_snapshot.csv"
    report_file: "local_factor_universe_report.md"
    markets: ["SH", "SZ"]
    exclude_name_patterns: ["ST", "*ST", "退"]
    min_amount: 50000000
    min_total_mv: 5000000000
    max_industry_weight: 0.12
    fallback_days: 90
    fetch_industry: true
    industry_max_boards: 120
  local_history:
    enabled: true
    path: "data/manual_history/a_share_history.sqlite"
    market: "CN"
    adjust_type: "qfq"
    daily_table: "market_daily_bars"
    meta_table: "market_stocks"
    financial_table: "market_financial_factors"
    index_table: "market_index_bars"
    index_meta_table: "market_indices"
    calendar_table: "trading_calendar"
    use_for_daily_fallback: true
    use_for_universe_fallback: true
    prefer_daily_for_backtest: true
    min_history_days: 200
    max_snapshot_staleness_days: 1
    min_snapshot_coverage: 0.80
    allow_stale_universe_fallback: false
  manual_history_update:
    enabled: true
    adjust_types: ["qfq"]
    markets: ["SH", "SZ"]
    max_staleness_days: 1
    min_latest_coverage: 0.80
    refresh_metadata: true
    min_metadata_coverage: 0.80
    min_run_time: "16:30"
    source_audit_table: "market_data_source_runs"
    rebuild_universe_after: true
    run_before_phase0: true
    max_symbols: 0
  us_market_history:
    enabled: true
    path: "data/us_market_history.sqlite"
    daily_table: "us_daily_bars"
    source_audit_table: "us_data_source_runs"
    provider: "yfinance"
    years: 5
    max_staleness_days: 3
    min_symbol_coverage: 1.0
    run_before_phase0: true
    runtime_yfinance_fallback: false
    symbols: ["^NDX", "^SOX", "NVDA", "KWEB", "^VIX", "CNY=X"]
  hk_market_history:
    enabled: true
    path: "data/hk_market_history.sqlite"
    daily_table: "hk_daily_bars"
    source_audit_table: "hk_data_source_runs"
    provider: "yfinance"
    years: 5
    max_staleness_days: 3
    min_symbol_coverage: 1.0
    run_before_phase0: true
    symbols:
      - "HK.00700"  # 腾讯控股
      - "HK.09988"  # 阿里巴巴-W
      - "HK.03690"  # 美团-W
      - "HK.01810"  # 小米集团-W
      - "HK.00981"  # 中芯国际
      - "HK.01211"  # 比亚迪股份
      - "HK.09618"  # 京东集团-SW
      - "HK.09888"  # 百度集团-SW
      - "HK.01024"  # 快手-W
      - "HK.09999"  # 网易-S
      - "HK.02015"  # 理想汽车-W
      - "HK.09868"  # 小鹏汽车-W
      - "HK.01347"  # 华虹半导体
      - "HK.00992"  # 联想集团
      - "HK.00005"  # 汇丰控股
      - "HK.00388"  # 香港交易所
      - "HK.01299"  # 友邦保险
      - "HK.02318"  # 中国平安
      - "HK.00939"  # 建设银行
      - "HK.01398"  # 工商银行
      - "HK.03988"  # 中国银行
      - "HK.00941"  # 中国移动
      - "HK.00728"  # 中国电信
      - "HK.00883"  # 中国海洋石油
      - "HK.01088"  # 中国神华
      - "HK.02899"  # 紫金矿业
      - "HK.02020"  # 安踏体育
      - "HK.09633"  # 农夫山泉
      - "HK.02269"  # 药明生物
      - "HK.06160"  # 百济神州
  financial_factors:
    enabled: true
    table: "market_financial_factors"
    periods: 32
    markets: ["SH", "SZ"]
    min_factor_coverage: 0.60
    rebuild_universe_after: true
  cost_sensitivity:
    enabled: false
    scenarios:
      - name: "base_research_cost"
        slippage: 0.001
        commission: 0.00025
        stamp_duty_sell: 0.0005
      - name: "main_personal_execution"
        slippage: 0.00246
        commission: 0.00025
        stamp_duty_sell: 0.0005
      - name: "stress_slippage_0_003"
        slippage: 0.003
        commission: 0.00025
        stamp_duty_sell: 0.0005
      - name: "stress_slippage_0_005"
        slippage: 0.005
        commission: 0.00025
        stamp_duty_sell: 0.0005
      - name: "low_slippage"
        slippage: 0.0003
        commission: 0.00025
        stamp_duty_sell: 0.0005
      - name: "zero_cost"
        slippage: 0.0
        commission: 0.0
        stamp_duty_sell: 0.0
  manual_history_import:
    # Set A_SHARE_DATA_DIR to the external raw data directory in .env or shell.
    qfq_zip: "${A_SHARE_DATA_DIR}/daily_qfq.zip"
    bfq_zip: "${A_SHARE_DATA_DIR}/daily.zip"
    stock_list_csv: "${A_SHARE_DATA_DIR}/股票列表.csv"
    trading_calendar_csv: "${A_SHARE_DATA_DIR}/交易日历.csv"
    delisted_stock_csv: "${A_SHARE_DATA_DIR}/退市股票列表.csv"
    index_list_csv: "${A_SHARE_DATA_DIR}/指数/指数列表.csv"
    csi_index_list_csv: "${A_SHARE_DATA_DIR}/指数/中证指数列表.csv"
    index_daily_zip: "${A_SHARE_DATA_DIR}/指数/指数_日_kline.zip"
    csi_index_daily_zip: "${A_SHARE_DATA_DIR}/指数/中证指数_日_kline.zip"
    output_db: "data/manual_history/a_share_history.sqlite"
    years: 10
    chunk_size: 250000
  data_sources:
    fred:
      enabled: false
      api_key_env: "FRED_API_KEY"
      cache:
        enabled: true
        dir: "data/cache/fred"
        ttl_hours: 24
      series:
        gdp: "GDP"
        cpi: "CPIAUCSL"
        fedfunds: "FEDFUNDS"
        fedfunds_daily: "DFF"
        vix: "VIXCLS"
    tiingo:
      enabled: true
      token_env: "TIINGO_API_TOKEN"
      us_equities:
        - "NVDA"
        - "AAPL"
        - "TSLA"
      thematic_etfs:
        - "KWEB"
    yfinance:
      us_indices:
        - "^NDX"
        - "^SOX"
        - "^GSPC"
        - "^VIX"
      us_equities:
        - "NVDA"
        - "AAPL"
        - "TSLA"
      thematic_etfs:
        - "KWEB"
      cnh_proxy:
        - "CNY=X"
    tushare:
      enabled: true
      token_env: "TUSHARE_TOKEN"
      api_url: "http://api.tushare.pro"
      request_delay: 0.25
      max_retries: 3
      retry_backoff: 2
      min_coverage: 0.80
    akshare:
      anti_crawler:
        enabled: true
        request_delay: 0.8
        jitter: 0.4
        batch_size: 5
        batch_pause: 6
        max_retries: 1
        retry_backoff: 4
      cn_symbols:
        - "SZ.300750"
        - "SH.600519"
      hk_symbols:
        - "HK.00700"
        - "HK.09988"
  walk_forward:
    train_years: 2
    validate_years: 1
    min_samples: 200
    initial_cash: 1000000
    commission: 0.00025
    stamp_duty_sell: 0.0005
    slippage: 0.00246
    strategy_v2:
      mode: "compare"
      compare_strategies: ["legacy_momentum", "legacy_momentum_low_turnover_v1", "ma_kline_baseline_v1", "residual_momentum_reversal_v1", "residual_momentum_reversal_v2", "quality_growth_price_v1", "multifactor_volume_price_filter_v1"]
      candidate_governance:
        enabled: true
        selection_panel_scope: "portfolio"
        min_fold_count: 20
        min_symbol_count: 20
        min_portfolio_fold_count: 4
      top_n: 3
      mom_windows: [3, 5, 10, 20]
      mom_quantiles: [0.5, 0.6]
      trend_windows: [20, 60]
      vol_window: 20
      vol_quantiles: [0.6, 0.75]
      target_vol: 0.18
      train_min_trades: 5
      legacy_momentum_low_turnover:
        enabled: true
        mom_windows: [5, 20]
        buy_quantiles: [0.6]
        hold_quantiles: [0.4]
        buy_top_n_values: [5, 10]
        hold_rank_multipliers: [2.0]
        rebalance_days_values: [5, 10, 20]
        min_hold_days_values: [5, 10]
        turnover_penalties: [0.01, 0.02]
      cross_market:
        enabled: true
        tech_score_thresholds: [0.0, 0.5]
        vix_risk_off_level: 25
        cny_pressure_threshold: 0.003
        magnitude_z_window: 252
        magnitude_z_min_periods: 60
        magnitude_z_clip: 2.0
        magnitude_score_thresholds: [0.0]
        soft_risk_scale: 0.5
        mapped_symbols:
          SZ.300750: ev
          SZ.002594: ev
          SH.688981: semiconductor
          SZ.002475: consumer_electronics
          SZ.300308: ai_infra
          SZ.300502: ai_infra
          SZ.300394: ai_infra
          SZ.002415: tech_hardware
          SZ.000063: tech_hardware
          SH.688012: semiconductor
          SZ.002371: consumer_electronics
          SH.603986: semiconductor
          SZ.002241: semiconductor
          SZ.000725: semiconductor
          SZ.000333: domestic_core
          SZ.000651: domestic_core
          SZ.000858: domestic_core
          SH.600519: domestic_core
          SH.601318: financial
          SH.600036: financial
          SH.600276: healthcare
          SH.600900: defensive
          SH.600030: financial
      price_volume_features:
        amount_ma_window: 20
        breakout_window: 20
        shadow_clip: 5.0
      baseline_ma_kline:
        enabled: true
        top_n_values: [3, 5]
        trend_window_pairs: [[20, 60]]
        amount_ratio_mins: [1.0, 1.2]
        upper_shadow_max_values: [1.0, 1.5]
      local_factor:
        enabled: true
        residual_momentum_windows: [10, 20]
        residual_momentum_quantiles: [0.6]
        reversal_window: 3
        reversal_quantiles: [0.7]
        use_xmarket_overlay: true
        residual_reversal_v2:
          enabled: true
          residual_windows: [5, 10, 20]
          residual_quantiles: [0.6]
          reversal_windows: [1, 3]
          reversal_quantiles: [0.7]
          amount_ratio_mins: [1.0, 1.2]
          upper_shadow_max_values: [1.0, 1.5]
          gap_ret_max_values: [0.03, 0.05]
          use_xmarket_overlay: false
        multifactor_filter:
          enabled: true
          quality_quantiles: [0.7]
          residual_windows: [10, 20]
          residual_quantiles: [0.6]
          top_n_values: [5, 10]
          amount_ratio_mins: [1.0, 1.2]
          upper_shadow_max_values: [1.0, 1.5]
          breakout_required_values: [false, true]
          use_xmarket_overlay: false
          factor_weights:
            quality_growth: 0.45
            residual_momentum: 0.35
            low_volatility: 0.20
        quality_growth:
          enabled: true
          financial_table: "market_financial_factors"
          financial_lag_days: 1
          min_available_fields: 4
          quality_quantiles: [0.7]
          top_n_values: [5, 10]
          cash_flow_quality_clip: [-5, 5]
          growth_clip: [-100, 300]
          debt_to_asset_clip: [0, 100]
          use_xmarket_overlay: true
          weights:
            roe: 0.30
            cash_flow_quality: 0.20
            profit_growth: 0.20
            revenue_growth: 0.15
            low_debt: 0.15
  accounts:
    simulated:
      - account_id: "default"
        name: "默认模拟账户"
        enabled: true
        initial_cash: 1000000
        ledger_path: "data/simulated_trading/phase0_daily_account_ledger.csv"
        database_path: "data/simulated_trading/simulated_accounts.sqlite"
        execution_price_mode: "next_open"
        max_participation_rate: 0.05
        lot_size: 100
  execution:
    price_mode: "next_open"
    conservative_price_buffer: 0.001
    lot_size: 100
    max_participation_rate: 0.05
    enable_limit_check: true
    enable_suspension_check: true
    limit_up_down_pct:
      default: 0.10
      star: 0.20
      chinext: 0.20
      bj: 0.30
  live_execution_backtest:
    name: "实盘仿真回测"
    default_profile: "live"
    gate_source: "account_daily_assets"
    output_dir: "reports/live_execution_backtest"
    bill_output: "reports/live_execution_backtest/live_execution_bill.csv"
    daily_output: "reports/live_execution_backtest/live_execution_daily_assets.csv"
    preview_output: "reports/live_execution_backtest/live_execution_bill_preview.html"
    fold_output: "reports/live_execution_backtest/live_execution_walk_forward_folds.csv"
    report_output: "reports/live_execution_backtest/live_execution_effectiveness_report.md"
    profiles:
      research:
        name: "策略研究回测"
        walk_forward:
          slippage: 0.001
          commission: 0.00025
          stamp_d
```

[truncated]
