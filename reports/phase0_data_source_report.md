# Phase 0 Data Source & Quality Report

Generated at: 2026-06-05T09:18:41

## Connectivity

| source | target | status | rows | latest_date | error |
| --- | --- | --- | --- | --- | --- |
| tiingo | NVDA | OK | 1771 | 2026-06-04 |  |
| tiingo | AAPL | OK | 1771 | 2026-06-04 |  |
| tiingo | TSLA | OK | 1771 | 2026-06-04 |  |
| tiingo | KWEB | OK | 1771 | 2026-06-04 |  |
| tushare | trade_cal | OK | 11 | 2026-06-05 |  |
| yfinance | ^NDX | OK | 1771 | 2026-06-04 |  |
| yfinance | ^SOX | FAIL | 0 |  | empty_or_rate_limited |
| yfinance | ^GSPC | OK | 1771 | 2026-06-04 |  |
| yfinance | ^VIX | FAIL | 0 |  | empty_or_rate_limited |
| yfinance | NVDA | OK | 1771 | 2026-06-04 |  |
| yfinance | AAPL | FAIL | 0 |  | empty_or_rate_limited |
| yfinance | TSLA | OK | 1771 | 2026-06-04 |  |
| yfinance | KWEB | FAIL | 0 |  | empty_or_rate_limited |
| yfinance | CNY=X | OK | 1832 | 2026-06-04 |  |
| akshare-cn | SZ.300750 | OK | 1709 | 2026-06-04 |  |
| akshare-cn | SH.600519 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| akshare-hk | HK.00700 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| akshare-hk | HK.09988 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| manual-history | pre_run_update | OK | 0 | 2026-06-04 | up_to_date |
| us-market-history | pre_run_update | OK | 6390 | 2026-06-04 | updated; yfinance ^VIX returned empty data. |

## Quality Audit

| symbol | rows | missing_ratio | ohlc_viol | non_pos | dup_date | latest_date | delay_days |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ^NDX | 1273 | 0.0000 | 0 | 0 | 0 | 2026-06-04 | 1 |
| ^SOX | 1273 | 0.0000 | 0 | 0 | 0 | 2026-06-04 | 1 |
| NVDA | 1273 | 0.0000 | 0 | 0 | 0 | 2026-06-04 | 1 |
| KWEB | 1273 | 0.0000 | 0 | 0 | 0 | 2026-06-04 | 1 |
| ^VIX | 1272 | 0.0000 | 0 | 0 | 0 | 2026-06-02 | 3 |
| CNY=X | 1318 | 0.0000 | 30 | 0 | 0 | 2026-06-04 | 1 |

## Quality Summary

| metric | value |
| --- | --- |
| coverage | 1.0 |
| avg_missing_ratio | 0.0 |
| avg_delay_days | 1.33 |
| total_integrity_violations | 30 |
| score | 95.67 |
