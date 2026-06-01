# Phase 0 Data Source & Quality Report

Generated at: 2026-06-02T01:49:16

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
