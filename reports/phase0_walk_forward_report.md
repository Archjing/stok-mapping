# Phase 0 Walk-Forward Report

Generated at: 2026-05-29T01:24:00

## Summary

| metric | value |
| --- | --- |
| status | ok |
| fold_count | 10 |
| symbol_count | 5 |
| annualized_return_mean | 0.2124481236571234 |
| sharpe_mean | 0.3217540894231791 |
| max_drawdown_mean | -0.23843754799092323 |
| win_rate_mean | 0.45756419089284356 |
| turnover_annual_mean | 51.3 |
| selected_candidate | legacy_momentum |
| candidate_comparison | legacy_momentum: score=0.3088, ann=0.2124, sharpe=0.3218, mdd=-0.2384; filtered_single_v2: score=-0.1651, ann=0.0068, sharpe=-0.1244, mdd=-0.0883; portfolio_v2: score=-0.7400, ann=-0.0783, sharpe=-0.6024, mdd=-0.1968 |
| oos_fold_count | 2 |
| oos_annualized_return_mean | 0.822730777832632 |
| oos_sharpe_mean | 1.391553622158883 |
| oos_return_decay_ratio | -12.74024175836119 |

## Fold Details

| symbol | fold | train_start | train_end | valid_start | valid_end | annual_ret | sharpe | max_dd | win_rate | turnover_annual | trades | selected_params |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SZ.300750 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.1273 | -0.5515 | -0.1975 | 0.4052 | 47.00 | 47 | legacy_mom5_median |
| SZ.300750 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 0.5431 | 1.2960 | -0.2315 | 0.4684 | 57.00 | 57 | legacy_mom5_median |
| SZ.002594 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.0277 | -0.0346 | -0.2435 | 0.4526 | 53.00 | 53 | legacy_mom5_median |
| SZ.002594 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 0.0748 | 0.3984 | -0.2185 | 0.4889 | 51.00 | 51 | legacy_mom5_median |
| SH.688981 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.1513 | -0.4965 | -0.3488 | 0.4565 | 56.00 | 56 | legacy_mom5_median |
| SH.688981 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-30 | 1.4558 | 1.8710 | -0.2937 | 0.4754 | 41.00 | 41 | legacy_mom5_median |
| SZ.002475 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | 0.0367 | 0.2672 | -0.1950 | 0.4966 | 51.00 | 51 | legacy_mom5_median |
| SZ.002475 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 0.3283 | 1.0107 | -0.2961 | 0.4296 | 61.00 | 61 | legacy_mom5_median |
| SH.600519 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.1976 | -1.4553 | -0.2203 | 0.4174 | 52.00 | 52 | legacy_mom5_median |
| SH.600519 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 0.1896 | 0.9121 | -0.1395 | 0.4851 | 44.00 | 44 | legacy_mom5_median |
