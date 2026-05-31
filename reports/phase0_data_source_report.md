# Phase 0 Data Source & Quality Report

Generated at: 2026-05-31T18:53:58

## Connectivity

| source | target | status | rows | latest_date | error |
| --- | --- | --- | --- | --- | --- |
| tushare | trade_cal | FAIL | 0 |  | HTTPConnectionPool(host='api.tushare.pro', port=80): Max retries exceeded with url: / (Caused by NameResolutionError("HT |
| yfinance | ^NDX | FAIL | 0 |  | empty_or_rate_limited |
| yfinance | ^SOX | FAIL | 0 |  | empty_or_rate_limited |
| yfinance | ^GSPC | FAIL | 0 |  | empty_or_rate_limited |
| yfinance | ^VIX | FAIL | 0 |  | empty_or_rate_limited |
| yfinance | NVDA | FAIL | 0 |  | empty_or_rate_limited |
| yfinance | AAPL | FAIL | 0 |  | empty_or_rate_limited |
| yfinance | TSLA | FAIL | 0 |  | empty_or_rate_limited |
| yfinance | KWEB | FAIL | 0 |  | empty_or_rate_limited |
| yfinance | CNY=X | FAIL | 0 |  | empty_or_rate_limited |
| akshare-cn | SZ.300750 | FAIL | 0 |  | HTTPSConnectionPool(host='push2his.eastmoney.com', port=443): Max retries exceeded with url: /api/qt/stock/kline/get?fie |
| akshare-cn | SH.600519 | FAIL | 0 |  | HTTPSConnectionPool(host='push2his.eastmoney.com', port=443): Max retries exceeded with url: /api/qt/stock/kline/get?fie |
| akshare-hk | HK.00700 | FAIL | 0 |  | HTTPSConnectionPool(host='33.push2his.eastmoney.com', port=443): Max retries exceeded with url: /api/qt/stock/kline/get? |
| akshare-hk | HK.09988 | FAIL | 0 |  | HTTPSConnectionPool(host='33.push2his.eastmoney.com', port=443): Max retries exceeded with url: /api/qt/stock/kline/get? |
| manual-history | pre_run_update | OK | 0 | 2026-05-29 | up_to_date |
| us-market-history | pre_run_update | OK | 0 | 2026-05-29 | up_to_date; yfinance KWEB returned empty data.; yfinance ^VIX returned empty data.; yfinance CNY=X returned empty data. |

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
