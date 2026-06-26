# Strategy Core Reachability Diagnostic

Generated at: 2026-06-25T13:09:01

## Scope

- Benchmark: `SH.000300`
- Weight lookup lag days: `1`
- Core top N: `60`
- Core cumulative weight target: `0.60`
- Full benchmark top N: `20`
- Minimum amount: `0.00`
- Minimum amount_ratio20: `0.0000`
- Seed benchmark core panel: `True`
- Seed top N: `20`
- Seed core top N: `60`
- Seed core cumulative weight: `0.60`
- Overall status: `pass`

## Fold Summary

| fold | days | asof | reachable_core_w | core_cov | min_core_w | reachable_top_w | top_cov | min_top_w | reachable_names | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 243 | 100.00% | 59.46% | 99.02% | 57.25% | 34.28% | 99.78% | 31.95% | 62.4 | pass |
| 2 | 243 | 100.00% | 59.39% | 99.20% | 57.97% | 32.70% | 99.98% | 30.76% | 67.8 | pass |
| 3 | 241 | 100.00% | 59.27% | 99.16% | 59.10% | 31.51% | 100.00% | 30.73% | 71.4 | pass |
| 4 | 241 | 100.00% | 59.39% | 99.20% | 58.98% | 32.54% | 100.00% | 31.82% | 69.3 | pass |
| 5 | 242 | 100.00% | 59.73% | 99.81% | 58.69% | 33.08% | 100.00% | 31.41% | 67.8 | pass |

## Interpretation

This is a read-only reachability diagnostic. It does not create a strategy, admission decision, watchlist, or trading signal.
The Top-N metric uses the complete benchmark weight table, not only stocks visible in the strategy panel.
Top-N absolute weight is benchmark concentration; Top-N coverage ratio is the reachability gate because the benchmark Top-N total weight changes by period.

## Latest Fold Dates

| fold | date | weight_date | reachable_core_w | reachable_top_w |
| --- | --- | --- | --- | --- |
| 1 | 2022-03-31 | 2022-03-01 | 59.19% | 33.71% |
| 2 | 2023-03-31 | 2023-03-01 | 59.52% | 32.05% |
| 3 | 2024-03-29 | 2024-03-01 | 59.15% | 31.21% |
| 4 | 2025-03-31 | 2025-03-03 | 59.27% | 32.58% |
| 5 | 2026-03-31 | 2026-03-02 | 59.70% | 31.48% |
