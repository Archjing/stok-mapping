# Claude Agent Output

- generated_at: 2026-05-29T20:50:43
- model: claude-sonnet-4-5-20250929
- dry_run: true

## Prompt Preview

# Task
基于当前 Phase 0 报告生成研究摘要、风险提示、失效条件和下一步验证建议。

# Constraints
- 输出语言：中文。
- 只做研究辅助、风险提示、验证建议和待办整理。
- 不输出买入、卖出、清仓、满仓等交易指令。
- 不擅自改变策略逻辑或策略参数。
- 若引用结论，注明来自哪个本地文件。

# Project Context
## reports/phase0_effectiveness_report.md

```text
# Phase 0 Strategy Effectiveness Gate

Generated at: 2026-05-29T07:07:15

Overall verdict: FAIL

| gate | status |
| --- | --- |
| annualized_return_mean > 0 | PASS |
| sharpe_mean > 0.5 | FAIL |
| max_drawdown_mean > -0.25 | FAIL |
| win_rate_mean > 0.45 | PASS |
| oos_return_decay_ratio < 0.30 | PASS |

## Snapshot

| metric | value |
| --- | --- |
| status | ok |
| fold_count | 230 |
| symbol_count | 119 |
| annualized_return_mean | 0.33599064897406206 |
| sharpe_mean | 0.3357946743577156 |
| max_drawdown_mean | -0.30737744830217145 |
| win_rate_mean | 0.46218977423976626 |
| turnover_annual_mean | 51.64782608695652 |
| selected_candidate | legacy_momentum |
| candidate_comparison | legacy_momentum: score=0.3501, ann=0.3360, sharpe=0.3358, mdd=-0.3074; xmarket_single_v2: score=-0.0063, ann=0.0204, sharpe=0.0083, mdd=-0.0497; xmarket_portfolio_v2: score=-0.8181, ann=-0.0636, sharpe=-0.7310, mdd=-0.1106; xmarket_next_open_v1: score=-1.9034, ann=-0.1517, sharpe=-1.7316, mdd=-0.1918; xmarket_magnitude_soft_risk_v1: score=-0.4044, ann=-0.0037, sharpe=-0.3430, mdd=-0.1190; residual_momentum_reversal_v1: score=-0.6410, ann=-0.0670, sharpe=-0.5249, mdd=-0.1652 |
| oos_fold_count | 46 |
| oos_annualized_return_mean | 0.7021640346715546 |
| oos_sharpe_mean | 1.0942470414044476 |
| oos_return_decay_ratio | -1.8724556472813825 |

```

## reports/phase0_walk_forward_report.md

```text
# Phase 0 Walk-Forward Report

Generated at: 2026-05-29T07:07:15

## Summary

| metric | value |
| --- | --- |
| status | ok |
| fold_count | 230 |
| symbol_count | 119 |
| annualized_return_mean | 0.33599064897406206 |
| sharpe_mean | 0.3357946743577156 |
| max_drawdown_mean | -0.30737744830217145 |
| win_rate_mean | 0.46218977423976626 |
| turnover_annual_mean | 51.64782608695652 |
| selected_candidate | legacy_momentum |
| candidate_comparison | legacy_momentum: score=0.3501, ann=0.3360, sharpe=0.3358, mdd=-0.3074; xmarket_single_v2: score=-0.0063, ann=0.0204, sharpe=0.0083, mdd=-0.0497; xmarket_portfolio_v2: score=-0.8181, ann=-0.0636, sharpe=-0.7310, mdd=-0.1106; xmarket_next_open_v1: score=-1.9034, ann=-0.1517, sharpe=-1.7316, mdd=-0.1918; xmarket_magnitude_soft_risk_v1: score=-0.4044, ann=-0.0037, sharpe=-0.3430, mdd=-0.1190; residual_momentum_reversal_v1: score=-0.6410, ann=-0.0670, sharpe=-0.5249, mdd=-0.1652 |
| oos_fold_count | 46 |
| oos_annualized_return_mean | 0.7021640346715546 |
| oos_sharpe_mean | 1.0942470414044476 |
| oos_return_decay_ratio | -1.8724556472813825 |

## Fold Details

| symbol | fold | train_start | train_end | valid_start | valid_end | annual_ret | sharpe | max_dd | win_rate | turnover_annual | trades | selected_params |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SZ.300308 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.0189 | 0.1714 | -0.2825 | 0.4444 | 46.00 | 46 | legacy_mom5_median |
| SZ.300308 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 2.1827 | 2.1342 | -0.4591 | 0.5000 | 46.00 | 46 | legacy_mom5_median |
| SZ.300502 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | 1.1696 | 1.6101 | -0.2038 | 0.5227 | 42.00 | 42 | legacy_mom5_median |
| SZ.300502 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 1.4157 | 1.7388 | -0.4396 | 0.4803 | 56.00 | 56 | legacy_mom5_median |
| SZ.300394 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.2811 | -0.4653 | -0.5335 | 0.4206 | 50.00 | 50 | legacy_mom5_median |
| SZ.300394 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 1.1211 | 1.4316 | -0.4144 | 0.4591 | 51.00 | 51 | legacy_mom5_median |
| SZ.300750 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.1273 | -0.5515 | -0.1975 | 0.4052 | 47.00 | 47 | legacy_mom5_median |
| SZ.300750 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 0.5431 | 1.2960 | -0.2315 | 0.4684 | 57.00 | 57 | legacy_mom5_median |
| SZ.300476 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.0140 | 0.2065 | -0.3991 | 0.4361 | 58.00 | 58 | legacy_mom5_median |
| SZ.300476 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 3.3940 | 2.4548 | -0.2827 | 0.4880 | 50.00 | 50 | legacy_mom5_median |
| SH.603986 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.2987 | -1.0001 | -0.3515 | 0.4545 | 51.00 | 51 | legacy_mom5_median |
| SH.603986 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 0.9983 | 1.7201 | -0.2312 | 0.5133 | 48.00 | 48 | legacy_mom5_median |
| SZ.002384 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.1052 | -0.1330 | -0.3097 | 0.4366 | 51.00 | 51 | legacy_mom5_median |
| SZ.002384 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 2.1439 | 2.2800 | -0.2477 | 0.5244 | 39.00 | 39 | legacy_mom5_median |
| SH.688256 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.0408 | 0.2163 | -0.3657 | 0.4615 | 46.00 | 46 | legacy_mom5_median |
| SH.688256 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 2.3587 | 2.0656 | -0.3090 | 0.5270 | 48.00 | 48 | legacy_mom5_median |
| SZ.000988 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.3697 | -1.5256 | -0.4041 | 0.4202 | 51.00 | 51 | legacy_mom5_median |
| SZ.000988 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 0.9805 | 1.8716 | -0.2120 | 0.5506 | 45.00 | 45 | legacy_mom5_median |
| SZ.300274 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | 0.5346 | 1.5914 | -0.1050 | 0.5046 | 37.00 | 37 | legacy_mom5_median |
| SZ.300274 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 0.6957 | 1.2720 | -0.5003 | 0.4733 | 45.00 | 45 | legacy_mom5_median |
| SH.601138 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | 0.0724 | 0.3709 | -0.3549 | 0.4722 | 40.00 | 40 | legacy_mom5_median |
| SH.601138 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 1.5911 | 2.3115 | -0.2991 | 0.5306 | 37.00 | 37 | legacy_mom5_median |
| SZ.002475 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | 0.0367 | 0.2672 | -0.1950 | 0.4966 | 51.00 | 51 | legacy_mom5_median |
| SZ.002475 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 0.3283 | 1.0107 | -0.2961 | 0.4296 | 61.00 | 61 | legacy_mom5_median |
| SH.688008 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.0830 | -0.1755 | -0.2916 | 0.5068 | 49.00 | 49 | legacy_mom5_median |
| SH.688008 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | -0.0283 | 0.1667 | -0.5106 | 0.4474 | 73.00 | 73 | legacy_mom5_median |
| SH.688525 | 1 | 2023-04-03 | 2025-05-06 | 2025-05-07 | 2026-05-20 | 1.7040 | 1.9087 | -0.2367 | 0.4904 | 51.00 | 51 | legacy_mom5_median |
| SH.601899 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | 0.1695 | 0.8267 | -0.1671 | 0.4961 | 44.00 | 44 | legacy_mom5_median |
| SH.601899 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 0.2085 | 0.9052 | -0.2307 | 0.5333 | 54.00 | 54 | legacy_mom5_median |
| SH.600487 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.1976 | -0.9389 | -0.2742 | 0.4240 | 57.00 | 57 | legacy_mom5_median |
| SH.600487 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 0.0106 | 0.1892 | -0.2845 | 0.5000 | 55.00 | 55 | legacy_mom5_median |
| SZ.002281 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.0758 | 0.0293 | -0.3403 | 0.4128 | 46.00 | 46 | legacy_mom5_median |
| SZ.002281 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 0.9164 | 1.5419 | -0.2826 | 0.5197 | 53.00 | 53 | legacy_mom5_median |
| SH.688041 | 1 | 2022-11-14 | 2024-12-10 | 2024-12-11 | 2026-01-08 | 0.2073 | 0.6259 | -0.2764 | 0.4486 | 47.00 | 47 | legacy_mom5_median |
| SH.688981 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.1513 | -0.4965 | -0.3488 | 0.4565 | 56.00 | 56 | legacy_mom5_median |
| SH.688981 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-30 | 1.4558 | 1.8710 | -0.2937 | 0.4754 | 41.00 | 41 | legacy_mom5_median |
| SZ.001309 | 1 | 2022-09-26 | 2024-10-29 | 2024-10-30 | 2025-11-11 | 1.6815 | 2.2365 | -0.2801 | 0.5396 | 51.00 | 51 | legacy_mom5_median |
| SH.600522 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.0272 | 0.0172 | -0.1797 | 0.4685 | 41.00 | 41 | legacy_mom5_median |
| SH.600522 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 0.2547 | 0.9222 | -0.1398 | 0.4815 | 47.00 | 47 | legacy_mom5_median |
| SZ.002463 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | 0.5599 | 1.3432 | -0.1521 | 0.5227 | 47.00 | 47 | legacy_mom5_median |
| SZ.002463 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 0.4583 | 1.0378 | -0.4214 | 0.4901 | 53.00 | 53 | legacy_mom5_median |
| SZ.301308 | 1 | 2022-11-07 | 2024-12-03 | 2024-12-04 | 2025-12-16 | 0.8608 | 1.4036 | -0.3006 | 0.4870 | 62.00 | 62 | legacy_mom5_median |
| SZ.300136 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.1986 | -0.4222 | -0.4136 | 0.4194 | 57.00 | 57 | legacy_mom5_median |
| SZ.300136 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 0.0356 | 0.2904 | -0.3804 | 0.4362 | 58.00 | 58 | legacy_mom5_median |
| SZ.300058 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.3328 | -1.0375 | -0.4346 | 0.4167 | 55.00 | 55 | legacy_mom5_median |
| SZ.300058 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 0.3961 | 0.8909 | -0.2727 | 0.5000 | 56.00 | 56 | legacy_mom5_median |
| SH.600584 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-13 | 0.0754 | 0.3854 | -0.2380 | 0.4538 | 52.00 | 52 | legacy_mom5_median |
| SH.600584 | 2 | 2022-08-12 | 2024-09-13 | 2024-09-18 | 2025-09-29 | 0.2163 | 0.7845 | -0.3250 | 0.4676 | 47.00 | 47 | legacy_mom5_median |
| SZ.300475 | 1 | 2021-07-29 | 2023-09-01 | 2023-09-04 | 2024-09-18 | -0.2325 | -0.3541 | -0.4458 | 0.4444 | 48.00 | 48 | legacy_mom5_median |
| SZ.300475 | 2 | 2022-08-12 | 2024-09-18 | 2024-09-19 | 2025-09-30 | 1.6676 | 1.8543 | -0.2912 | 0.4843 | 54.00 | 54 | legacy_mom5_median |
| SZ.002202 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.0336 | -0.1089 | -0.1720 | 0.4694 | 44.00 | 44 | legacy_mom5_median |
| SZ.002202 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 0.2855 | 1.0105 | -0.2360 | 0.4621 | 55.00 | 55 | legacy_mom5_median |
| SH.600111 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.2579 | -1.3638 | -0.2803 | 0.3643 | 57.00 | 57 | legacy_mom5_median |
| SH.600111 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 1.2744 | 2.0925 | -0.2386 | 0.5066 | 46.00 | 46 | legacy_mom5_median |
| SH.688521 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.3529 | -1.0991 | -0.4803 | 0.3980 | 51.00 | 51 | legacy_mom5_median |
| SH.688521 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-10-14 | 1.9666 | 1.7788 | -0.3089 | 0.4706 | 51.00 | 51 | legacy_mom5_median |
| SZ.002428 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | 0.1994 | 0.6749 | -0.2109 | 0.4960 | 40.00 | 40 | legacy_mom5_median |
| SZ.002428 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 1.4409 | 2.0828 | -0.2144 | 0.4815 | 42.00 | 42 | legacy_mom5_median |
| SZ.002594 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.0277 | -0.0346 | -0.2435 | 0.4526 | 53.00 | 53 | legacy_mom5_median |
| SZ.002594 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 0.0748 | 0.3984 | -0.2185 | 0.4889 | 51.00 | 51 | legacy_mom5_median |
| SZ.002156 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.4020 | -1.4269 | -0.4413 | 0.4262 | 60.00 | 60 | legacy_mom5_median |
| SZ.002156 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 0.5276 | 1.2202 | -0.3889 | 0.4895 | 45.00 | 45 | legacy_mom5_median |
| SH.600089 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.1732 | -1.1161 | -0.1875 | 0.4186 | 53.00 | 53 | legacy_mom5_median |
| SH.600089 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 0.1627 | 0.7147 | -0.2055 | 0.4565 | 55.00 | 55 | legacy_mom5_median |
| SH.600105 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.1821 | -0.5632 | -0.2266 | 0.4737 | 49.00 | 49 | legacy_mom5_median |
| SH.600105 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | -0.0119 | 0.2325 | -0.4622 | 0.4759 | 58.00 | 58 | legacy_mom5_median |
| SH.600498 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.3039 | -1.1046 | -0.4065 | 0.3929 | 55.00 | 55 | legacy_mom5_median |
| SH.600498 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 0.7635 | 1.6308 | -0.3401 | 0.5394 | 45.00 | 45 | legacy_mom5_median |
| SZ.300059 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.3099 | -2.1850 | -0.3328 | 0.3846 | 49.00 | 49 | legacy_mom5_median |
| SZ.300059 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 0.8331 | 1.3664 | -0.3335 | 0.4691 | 46.00 | 46 | legacy_mom5_median |
| SZ.002709 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.3312 | -1.1373 | -0.3807 | 0.3981 | 43.00 | 43 | legacy_mom5_median |
| SZ.002709 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 0.9599 | 1.7247 | -0.1923 | 0.5059 | 49.00 | 49 | legacy_mom5_median |
| SZ.002050 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | -0.3407 | -1.4626 | -0.4250 | 0.4369 | 55.00 | 55 | legacy_mom5_median |
| SZ.002050 | 2 | 2022-08-12 | 2024-09-06 | 2024-09-09 | 2025-09-22 | 0.4104 | 0.9958 | -0.3621 | 0.4675 | 53.00 | 53 | legacy_mom5_median |
| SZ.300442 | 1 | 2021-07-29 | 2023-08-24 | 2023-08-25 | 2024-09-06 | 0.4294 | 1.1181 | -0.1793 | 0.4661 | 48.00 | 48 | legacy_mom5_median |
| SZ.300442 | 2 | 2
```

[truncated]


## reports/phase0_data_source_report.md

```text
# Phase 0 Data Source & Quality Report

Generated at: 2026-05-29T15:40:14

## Connectivity

| source | target | status | rows | latest_date | error |
| --- | --- | --- | --- | --- | --- |
| yfinance | ^NDX | OK | 1269 | 2026-05-28 |  |
| yfinance | ^SOX | OK | 1269 | 2026-05-28 |  |
| yfinance | ^GSPC | OK | 1269 | 2026-05-28 |  |
| yfinance | ^VIX | OK | 1270 | 2026-05-28 |  |
| yfinance | NVDA | OK | 1269 | 2026-05-28 |  |
| yfinance | AAPL | OK | 1269 | 2026-05-28 |  |
| yfinance | TSLA | OK | 1269 | 2026-05-28 |  |
| yfinance | KWEB | OK | 1269 | 2026-05-28 |  |
| yfinance | CNY=X | OK | 1315 | 2026-05-29 |  |
| akshare-cn | SZ.300750 | OK | 1225 | 2026-05-28 |  |
| akshare-cn | SH.600519 | OK | 1225 | 2026-05-28 |  |
| akshare-hk | HK.00700 | OK | 1240 | 2026-05-28 |  |
| akshare-hk | HK.09988 | OK | 1240 | 2026-05-28 |  |

## Quality Audit

| symbol | rows | missing_ratio | ohlc_viol | non_pos | dup_date | latest_date | delay_days |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ^NDX | 1269 | 0.0000 | 0 | 0 | 0 | 2026-05-28 | 1 |
| ^SOX | 1269 | 0.0000 | 0 | 0 | 0 | 2026-05-28 | 1 |
| ^GSPC | 1269 | 0.0000 | 0 | 0 | 0 | 2026-05-28 | 1 |
| ^VIX | 1270 | 0.0000 | 0 | 0 | 0 | 2026-05-28 | 1 |
| NVDA | 1269 | 0.0000 | 0 | 0 | 0 | 2026-05-28 | 1 |
| AAPL | 1269 | 0.0000 | 0 | 0 | 0 | 2026-05-28 | 1 |
| TSLA | 1269 | 0.0000 | 0 | 0 | 0 | 2026-05-28 | 1 |
| KWEB | 1269 | 0.0000 | 0 | 0 | 0 | 2026-05-28 | 1 |
| CNY=X | 1315 | 0.0002 | 30 | 0 | 0 | 2026-05-29 | 0 |

## Quality Summary

| metric | value |
| --- | --- |
| coverage | 1.0 |
| avg_missing_ratio | 1.7e-05 |
| avg_delay_days | 0.89 |
| total_integrity_violations | 30 |
| score | 96.11 |

```

## data/universe/local_factor_universe_report.md

```text
# Local Factor Universe Report

Generated at: 2026-05-29

## Summary

| metric | value |
| --- | --- |
| source | local_history_sqlite |
| target_size | 500 |
| snapshot_count | 5499 |
| selected_count | 500 |
| has_industry | True |
| has_market_cap | True |
| has_valuation | True |
| has_financial_factors | True |

## Warnings

- AkShare all-A snapshot failed: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
- AkShare all-A snapshot was empty; used configured local history fallback.

## Top Industries

| industry | count |
| --- | --- |
| 半导体 | 60 |
| 电气设备 | 53 |
| 元器件 | 50 |
| 通信设备 | 30 |
| 小金属 | 28 |
| 软件服务 | 22 |
| 专用机械 | 18 |
| 汽车配件 | 14 |
| 银行 | 13 |
| 化工原料 | 13 |
| 火力发电 | 11 |
| 互联网 | 10 |
| 新型电力 | 9 |
| 证券 | 7 |
| IT设备 | 7 |
| 农药化肥 | 7 |
| 航空 | 7 |
| 铜 | 6 |
| 家用电器 | 6 |
| 铝 | 6 |

## Top 20 Symbols

| rank | symbol | name | industry | amount | total_mv | pe_ttm | pb | roe | debt_to_asset |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | SZ.300750 | 宁德时代 | 电气设备 | 14789202339.12 | 1961639922848.00 | 26.27 | 5.49 | 5.98 | 62.32 |
| 2 | SZ.300308 | 中际旭创 | 通信设备 | 22188352113.41 | 1293068396059.40 | 118.49 | 36.34 | 17.54 | 32.64 |
| 3 | SZ.300502 | 新易盛 | 通信设备 | 20946702912.48 | 703551882126.40 | 73.51 | 34.52 | 14.52 | 31.03 |
| 4 | SH.601138 | 工业富联 | 通信设备 | 12188309951.54 | 1456556373645.60 | 41.24 | 8.27 | 6.18 | 61.38 |
| 5 | SH.688256 | 寒武纪 | 半导体 | 13229115895.20 | 823063789390.00 | 265.72 | 63.95 | 8.20 | 16.38 |
| 6 | SH.688981 | 中芯国际 | 半导体 | 8179845831.87 | 1121122612041.70 | 222.08 | 7.48 | 0.90 | 34.89 |
| 7 | SH.601899 | 紫金矿业 | 铜 | 10120701575.77 | 809421353093.68 | 15.61 | 4.10 | 10.35 | 51.37 |
| 8 | SZ.300394 | 天孚通信 | 通信设备 | 14932297044.81 | 354673987511.20 | 175.36 | 59.31 | 8.57 | 14.25 |
| 9 | SZ.002384 | 东山精密 | 元器件 | 13315158738.54 | 390223984692.60 | 269.68 | 17.24 | 5.05 | 63.69 |
| 10 | SZ.002475 | 立讯精密 | 元器件 | 11314930964.20 | 534479239462.14 | 32.00 | 6.05 | 4.20 | 66.53 |
| 11 | SZ.300476 | 胜宏科技 | 元器件 | 13697562151.73 | 362175859286.76 | 73.56 | 20.81 | 7.62 | 55.23 |
| 12 | SH.688041 | 海光信息 | 半导体 | 8809864710.08 | 683122964944.90 | 267.18 | 29.07 | 2.99 | 22.80 |
| 13 | SH.603986 | 兆易创新 | 半导体 | 13863374058.74 | 327421855641.51 | 188.31 | 12.96 | 6.12 | 8.13 |
| 14 | SZ.300274 | 阳光电源 | 电气设备 | 12443946406.17 | 369010901357.76 | 27.17 | 7.58 | 4.81 | 57.51 |
| 15 | SZ.002594 | 比亚迪 | 汽车整车 | 5936746954.95 | 876892061801.70 | 26.87 | 3.78 | 1.65 | 70.94 |
| 16 | SH.688008 | 澜起科技 | 半导体 | 10759659787.48 | 309216605313.00 | 128.43 | 14.83 | 5.39 | 4.17 |
| 17 | SH.600519 | 贵州茅台 | 白酒 | 5613525106.11 | 1657608202926.00 | 20.20 | 6.12 | 10.57 | 12.12 |
| 18 | SZ.002371 | 北方华创 | 半导体 | 5691929613.37 | 456550319839.92 | 82.39 | 11.62 | 4.25 | 50.01 |
| 19 | SZ.002463 | 沪电股份 | 元器件 | 7668900205.55 | 254092961425.48 | 66.44 | 15.13 | 7.81 | 48.64 |
| 20 | SZ.301308 | 江波龙 | 半导体 | 7621678918.91 | 233229302549.03 | 161.67 | 19.14 | 39.40 | 65.55 |

```

## config.yaml

```text
phase0:
  benchmark_symbol: "SH.000300"
  years: 5
  symbols:
    - "SZ.300750"
    - "SZ.002594"
    - "SH.688981"
    - "SZ.002475"
    - "SZ.300308"
    - "SZ.300502"
    - "SZ.300394"
    - "SZ.002415"
    - "SZ.000063"
    - "SH.688012"
    - "SZ.002371"
    - "SH.603986"
    - "SZ.002241"
    - "SZ.000725"
    - "SZ.000333"
    - "SZ.000651"
    - "SZ.000858"
    - "SH.600519"
    - "SH.601318"
    - "SH.600036"
    - "SH.600276"
    - "SH.600900"
    - "SH.600030"
  universe:
    enabled: true
    target_size: 500
    min_usable_size: 100
    walk_forward_limit: 120
    output_dir: "data/universe"
    output_file: "local_factor_universe.csv"
    snapshot_file: "a_share_snapshot.csv"
    report_file: "local_factor_universe_report.md"
    markets: ["SH", "SZ"]
    exclude_name_patterns: ["ST", "*ST", "退"]
    min_amount: 50000000
    min_total_mv: 5000000000
    max_industry_weight: 0.12
    fallback_days: 90
    fetch_industry: true
    industry_max_boards: 120
  local_history:
    enabled: true
    path: "data/a_share_history.sqlite"
    market: "CN"
    adjust_type: "qfq"
    daily_table: "market_daily_bars"
    meta_table: "market_stocks"
    financial_table: "market_financial_factors"
    index_table: "market_index_bars"
    index_meta_table: "market_indices"
    calendar_table: "trading_calendar"
    use_for_daily_fallback: true
    use_for_universe_fallback: true
    prefer_daily_for_backtest: true
    min_history_days: 200
    max_snapshot_staleness_days: 1
    min_snapshot_coverage: 0.80
    allow_stale_universe_fallback: false
  manual_history_update:
    enabled: true
    adjust_types: ["qfq"]
    markets: ["SH", "SZ"]
    max_staleness_days: 1
    min_latest_coverage: 0.80
    refresh_metadata: true
    min_metadata_coverage: 0.80
    min_run_time: "16:30"
    source_audit_table: "market_data_source_runs"
    rebuild_universe_after: true
    max_symbols: 0
  financial_factors:
    enabled: true
    table: "market_financial_factors"
    periods: 8
    markets: ["SH", "SZ"]
    min_factor_coverage: 0.60
    rebuild_universe_after: true
  manual_history_import:
    qfq_zip: "/home/zj/workspace/tmp/A股数据_zip/daily_qfq.zip"
    bfq_zip: "/home/zj/workspace/tmp/A股数据_zip/daily.zip"
    stock_list_csv: "/home/zj/workspace/tmp/A股数据_zip/股票列表.csv"
    trading_calendar_csv: "/home/zj/workspace/tmp/A股数据_zip/交易日历.csv"
    delisted_stock_csv: "/home/zj/workspace/tmp/A股数据_zip/退市股票列表.csv"
    index_list_csv: "/home/zj/workspace/tmp/A股数据_zip/指数/指数列表.csv"
    csi_index_list_csv: "/home/zj/workspace/tmp/A股数据_zip/指数/中证指数列表.csv"
    index_daily_zip: "/home/zj/workspace/tmp/A股数据_zip/指数/指数_日_kline.zip"
    csi_index_daily_zip: "/home/zj/workspace/tmp/A股数据_zip/指数/中证指数_日_kline.zip"
    output_db: "data/a_share_history.sqlite"
    years: 10
    chunk_size: 250000
  data_sources:
    yfinance:
      us_indices:
        - "^NDX"
        - "^SOX"
        - "^GSPC"
        - "^VIX"
      us_equities:
        - "NVDA"
        - "AAPL"
        - "TSLA"
      thematic_etfs:
        - "KWEB"
      cnh_proxy:
        - "CNY=X"
    tushare:
      enabled: true
      token_env: "TUSHARE_TOKEN"
      api_url: "http://api.tushare.pro"
      request_delay: 0.25
      max_retries: 3
      retry_backoff: 2
      min_coverage: 0.80
    akshare:
      anti_crawler:
        enabled: true
        request_delay: 0.8
        jitter: 0.4
        batch_size: 5
        batch_pause: 6
        max_retries: 1
        retry_backoff: 4
      cn_symbols:
        - "SZ.300750"
        - "SH.600519"
      hk_symbols:
        - "HK.00700"
        - "HK.09988"
  walk_forward:
    train_years: 2
    validate_years: 1
    min_samples: 200
    initial_cash: 1000000
    commission: 0.00025
    stamp_duty_sell: 0.0005
    slippage: 0.001
    strategy_v2:
      mode: "compare"
      top_n: 3
      mom_windows: [3, 5, 10, 20]
      mom_quantiles: [0.5, 0.6]
      trend_windows: [20, 60]
      vol_window: 20
      vol_quantiles: [0.6, 0.75]
      target_vol: 0.18
      train_min_trades: 5
      cross_market:
        enabled: true
        tech_score_thresholds: [0.0, 0.5]
        vix_risk_off_level: 25
        cny_pressure_threshold: 0.003
        magnitude_z_window: 252
        magnitude_z_min_periods: 60
        magnitude_z_clip: 2.0
        magnitude_score_thresholds: [0.0]
        soft_risk_scale: 0.5
        mapped_symbols:
          SZ.300750: ev
          SZ.002594: ev
          SH.688981: semiconductor
          SZ.002475: consumer_electronics
          SZ.300308: ai_infra
          SZ.300502: ai_infra
          SZ.300394: ai_infra
          SZ.002415: tech_hardware
          SZ.000063: tech_hardware
          SH.688012: semiconductor
          SZ.002371: consumer_electronics
          SH.603986: semiconductor
          SZ.002241: semiconductor
          SZ.000725: semiconductor
          SZ.000333: domestic_core
          SZ.000651: domestic_core
          SZ.000858: domestic_core
          SH.600519: domestic_core
          SH.601318: financial
          SH.600036: financial
          SH.600276: healthcare
          SH.600900: defensive
          SH.600030: financial
      price_volume_features:
        amount_ma_window: 20
        breakout_window: 20
        shadow_clip: 5.0
      local_factor:
        enabled: true
        residual_momentum_windows: [10, 20]
        residual_momentum_quantiles: [0.6]
        reversal_window: 3
        reversal_quantiles: [0.7]
        use_xmarket_overlay: true
        quality_growth:
          enabled: true
          financial_table: "market_financial_factors"
          financial_lag_days: 1
          min_available_fields: 4
          quality_quantiles: [0.7]
          top_n_values: [5, 10]
          cash_flow_quality_clip: [-5, 5]
          growth_clip: [-100, 300]
          debt_to_asset_clip: [0, 100]
          use_xmarket_overlay: true
          weights:
            roe: 0.30
            cash_flow_quality: 0.20
            profit_growth: 0.20
            revenue_growth: 0.15
            low_debt: 0.15

```
