# Phase 0 Data Source & Quality Report

Generated at: 2026-05-30T05:02:04

## Connectivity

| source | target | status | rows | latest_date | error |
| --- | --- | --- | --- | --- | --- |
| yfinance | ^NDX | FAIL | 0 |  | empty_or_rate_limited |
| yfinance | ^SOX | FAIL | 0 |  | empty_or_rate_limited |
| yfinance | ^GSPC | FAIL | 0 |  | empty_or_rate_limited |
| yfinance | ^VIX | FAIL | 0 |  | empty_or_rate_limited |
| yfinance | NVDA | FAIL | 0 |  | empty_or_rate_limited |
| yfinance | AAPL | FAIL | 0 |  | empty_or_rate_limited |
| yfinance | TSLA | FAIL | 0 |  | empty_or_rate_limited |
| yfinance | KWEB | FAIL | 0 |  | empty_or_rate_limited |
| yfinance | CNY=X | FAIL | 0 |  | empty_or_rate_limited |
| akshare-cn | SZ.300750 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| akshare-cn | SH.600519 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| akshare-hk | HK.00700 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |
| akshare-hk | HK.09988 | FAIL | 0 |  | ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')) |

## Quality Audit

| symbol | rows | missing_ratio | ohlc_viol | non_pos | dup_date | latest_date | delay_days |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SZ.300750 | 1168 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| SZ.002594 | 1168 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| SH.688981 | 1162 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| SZ.002475 | 1168 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| SZ.300308 | 1168 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| SZ.300502 | 1168 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| SZ.300394 | 1168 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| SZ.002415 | 1168 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| SZ.000063 | 1168 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| SH.688012 | 1159 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| SZ.002371 | 1168 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| SH.603986 | 1168 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| SZ.002241 | 1168 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| SZ.000725 | 1168 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| SZ.000333 | 1168 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| SZ.000651 | 1168 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| SZ.000858 | 1168 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| SH.600519 | 1168 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| SH.601318 | 1168 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| SH.600036 | 1168 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| SH.600276 | 1168 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| SH.600900 | 1157 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |
| SH.600030 | 1162 | 0.0000 | 0 | 0 | 0 | 2026-05-29 | 1 |

## Quality Summary

| metric | value |
| --- | --- |
| coverage | 1.0 |
| avg_missing_ratio | 0.0 |
| avg_delay_days | 1.0 |
| total_integrity_violations | 0 |
| score | 99.0 |
