# Phase 0 Data Source & Quality Report

Generated at: 2026-05-31T04:09:17

## Connectivity

| source | target | status | rows | latest_date | error |
| --- | --- | --- | --- | --- | --- |
| tushare | trade_cal | OK | 11 | 2026-05-31 |  |
| yfinance | ^NDX | OK | 1772 | 2026-05-29 |  |
| yfinance | ^SOX | OK | 1772 | 2026-05-29 |  |
| yfinance | ^GSPC | OK | 1772 | 2026-05-29 |  |
| yfinance | ^VIX | OK | 1773 | 2026-05-29 |  |
| yfinance | NVDA | OK | 1772 | 2026-05-29 |  |
| yfinance | AAPL | OK | 1772 | 2026-05-29 |  |
| yfinance | TSLA | OK | 1772 | 2026-05-29 |  |
| yfinance | KWEB | OK | 1772 | 2026-05-29 |  |
| yfinance | CNY=X | OK | 1833 | 2026-05-29 |  |
| akshare-cn | SZ.300750 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| akshare-cn | SH.600519 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| akshare-hk | HK.00700 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| akshare-hk | HK.09988 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| manual-history | pre_run_update | OK | 0 | 2026-05-29 | up_to_date |
| us-market-history | pre_run_update | OK | 7654 | 2026-05-29 | updated |

## Quality Audit

| symbol | rows | missing_ratio | ohlc_viol | non_pos | dup_date | latest_date | delay_days |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ^NDX | 1269 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 2 |
| ^SOX | 1269 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 2 |
| NVDA | 1269 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 2 |
| KWEB | 1269 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 2 |
| ^VIX | 1270 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 2 |
| CNY=X | 1314 | 0.0000 | 30 | 0 | 0 | 2026-05-29 | 2 |

## Quality Summary

| metric | value |
| --- | --- |
| coverage | 1.0 |
| avg_missing_ratio | 0.0 |
| avg_delay_days | 2.0 |
| total_integrity_violations | 30 |
| score | 95.0 |
