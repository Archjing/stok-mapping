# Phase 0 Data Source & Quality Report

Generated at: 2026-05-30T19:23:07

## Connectivity

| source | target | status | rows | latest_date | error |
| --- | --- | --- | --- | --- | --- |
| tushare | trade_cal | OK | 11 | 2026-05-30 |  |
| yfinance | ^NDX | OK | 1269 | 2026-05-29 |  |
| yfinance | ^SOX | OK | 1269 | 2026-05-29 |  |
| yfinance | ^GSPC | OK | 1269 | 2026-05-29 |  |
| yfinance | ^VIX | OK | 1270 | 2026-05-29 |  |
| yfinance | NVDA | OK | 1269 | 2026-05-29 |  |
| yfinance | AAPL | OK | 1269 | 2026-05-29 |  |
| yfinance | TSLA | OK | 1269 | 2026-05-29 |  |
| yfinance | KWEB | OK | 1269 | 2026-05-29 |  |
| yfinance | CNY=X | OK | 1314 | 2026-05-29 |  |
| akshare-cn | SZ.300750 | OK | 1225 | 2026-05-29 |  |
| akshare-cn | SH.600519 | OK | 1225 | 2026-05-29 |  |
| akshare-hk | HK.00700 | OK | 1240 | 2026-05-29 |  |
| akshare-hk | HK.09988 | OK | 1240 | 2026-05-29 |  |
| manual-history | pre_run_update | OK | 0 | 2026-05-29 | up_to_date |
| us-market-history | pre_run_update | OK | 7660 | 2026-05-29 | updated |

## Quality Audit

| symbol | rows | missing_ratio | ohlc_viol | non_pos | dup_date | latest_date | delay_days |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ^NDX | 1269 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| ^SOX | 1269 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| NVDA | 1269 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| KWEB | 1269 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| ^VIX | 1270 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| CNY=X | 1314 | 0.0000 | 30 | 0 | 0 | 2026-05-29 | 1 |

## Quality Summary

| metric | value |
| --- | --- |
| coverage | 1.0 |
| avg_missing_ratio | 0.0 |
| avg_delay_days | 1.0 |
| total_integrity_violations | 30 |
| score | 96.0 |
