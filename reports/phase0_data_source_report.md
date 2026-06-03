# Phase 0 Data Source & Quality Report

Generated at: 2026-06-03T17:38:20

## Connectivity

| source | target | status | rows | latest_date | error |
| --- | --- | --- | --- | --- | --- |
| tiingo | NVDA | OK | 1771 | 2026-06-02 |  |
| tiingo | AAPL | OK | 1771 | 2026-06-02 |  |
| tiingo | TSLA | OK | 1771 | 2026-06-02 |  |
| tiingo | KWEB | OK | 1771 | 2026-06-02 |  |
| tushare | trade_cal | OK | 11 | 2026-06-03 |  |
| yfinance | ^NDX | OK | 1771 | 2026-06-02 |  |
| yfinance | ^SOX | FAIL | 0 |  | empty_or_rate_limited |
| yfinance | ^GSPC | OK | 1771 | 2026-06-02 |  |
| yfinance | ^VIX | FAIL | 0 |  | empty_or_rate_limited |
| yfinance | NVDA | OK | 1771 | 2026-06-02 |  |
| yfinance | AAPL | FAIL | 0 |  | empty_or_rate_limited |
| yfinance | TSLA | OK | 1771 | 2026-06-02 |  |
| yfinance | KWEB | FAIL | 0 |  | empty_or_rate_limited |
| yfinance | CNY=X | OK | 1833 | 2026-06-03 |  |
| akshare-cn | SZ.300750 | OK | 1710 | 2026-06-03 |  |
| akshare-cn | SH.600519 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| akshare-hk | HK.00700 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| akshare-hk | HK.09988 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| manual-history | pre_run_update | OK | 0 | 2026-06-03 | up_to_date |
| us-market-history | pre_run_update | OK | 5113 | 2026-06-02 | updated; yfinance NVDA returned empty data.; yfinance ^VIX returned empty data. |

## Quality Audit

| symbol | rows | missing_ratio | ohlc_viol | non_pos | dup_date | latest_date | delay_days |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ^NDX | 1271 | 0.0000 | 0 | 0 | 0 | 2026-06-02 | 1 |
| ^SOX | 1271 | 0.0000 | 0 | 0 | 0 | 2026-06-02 | 1 |
| NVDA | 1270 | 0.0000 | 0 | 0 | 0 | 2026-06-01 | 2 |
| KWEB | 1271 | 0.0000 | 0 | 0 | 0 | 2026-06-02 | 1 |
| ^VIX | 1271 | 0.0000 | 0 | 0 | 0 | 2026-06-01 | 2 |
| CNY=X | 1316 | 0.0000 | 30 | 0 | 0 | 2026-06-02 | 1 |

## Quality Summary

| metric | value |
| --- | --- |
| coverage | 1.0 |
| avg_missing_ratio | 0.0 |
| avg_delay_days | 1.33 |
| total_integrity_violations | 30 |
| score | 95.67 |
