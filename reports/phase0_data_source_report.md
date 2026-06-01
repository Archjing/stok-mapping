# Phase 0 Data Source & Quality Report

Generated at: 2026-06-01T19:30:38

## Connectivity

| source | target | status | rows | latest_date | error |
| --- | --- | --- | --- | --- | --- |
| fred | GDP | OK | 28 | 2026-01-01 |  |
| fred | CPIAUCSL | OK | 83 | 2026-04-01 |  |
| fred | FEDFUNDS | OK | 84 | 2026-04-01 |  |
| fred | DFF | OK | 2572 | 2026-05-28 |  |
| fred | VIXCLS | OK | 1800 | 2026-05-28 |  |
| tushare | trade_cal | OK | 11 | 2026-06-01 |  |
| yfinance | ^NDX | OK | 1771 | 2026-05-29 |  |
| yfinance | ^SOX | OK | 1771 | 2026-05-29 |  |
| yfinance | ^GSPC | OK | 1771 | 2026-05-29 |  |
| yfinance | ^VIX | OK | 1772 | 2026-05-29 |  |
| yfinance | NVDA | OK | 1771 | 2026-05-29 |  |
| yfinance | AAPL | OK | 1771 | 2026-05-29 |  |
| yfinance | TSLA | OK | 1771 | 2026-05-29 |  |
| yfinance | KWEB | OK | 1771 | 2026-05-29 |  |
| yfinance | CNY=X | OK | 1832 | 2026-05-29 |  |
| akshare-cn | SZ.300750 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| akshare-cn | SH.600519 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| akshare-hk | HK.00700 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| akshare-hk | HK.09988 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |

## Quality Audit

| symbol | rows | missing_ratio | ohlc_viol | non_pos | dup_date | latest_date | delay_days |
| --- | --- | --- | --- | --- | --- | --- | --- |

## Quality Summary

| metric | value |
| --- | --- |
| count | 0 |
| mean_score | 0.0 |
| mean_coverage | 0.0 |
| flags | [] |
