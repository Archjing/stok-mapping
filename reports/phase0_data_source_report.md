# Phase 0 Data Source & Quality Report

Generated at: 2026-05-30T01:04:31

## Connectivity

| source | target | status | rows | latest_date | error |
| --- | --- | --- | --- | --- | --- |
| yfinance | ^NDX | OK | 1269 | 2026-05-29 |  |
| yfinance | ^SOX | OK | 1269 | 2026-05-29 |  |
| yfinance | ^GSPC | OK | 1269 | 2026-05-29 |  |
| yfinance | ^VIX | OK | 1270 | 2026-05-29 |  |
| yfinance | NVDA | OK | 1269 | 2026-05-29 |  |
| yfinance | AAPL | OK | 1269 | 2026-05-29 |  |
| yfinance | TSLA | OK | 1269 | 2026-05-29 |  |
| yfinance | KWEB | OK | 1269 | 2026-05-29 |  |
| yfinance | CNY=X | OK | 1314 | 2026-05-29 |  |
| akshare-cn | SZ.300750 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| akshare-cn | SH.600519 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| akshare-hk | HK.00700 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| akshare-hk | HK.09988 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |

## Quality Audit

| symbol | rows | missing_ratio | ohlc_viol | non_pos | dup_date | latest_date | delay_days |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ^NDX | 1269 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| ^SOX | 1269 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| ^GSPC | 1269 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| ^VIX | 1270 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| NVDA | 1269 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| AAPL | 1269 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| TSLA | 1269 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| KWEB | 1269 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| CNY=X | 1314 | 0.0000 | 30 | 0 | 0 | 2026-05-29 | 1 |

## Quality Summary

| metric | value |
| --- | --- |
| coverage | 1.0 |
| avg_missing_ratio | 0.0 |
| avg_delay_days | 1.0 |
| total_integrity_violations | 30 |
| score | 96.0 |
