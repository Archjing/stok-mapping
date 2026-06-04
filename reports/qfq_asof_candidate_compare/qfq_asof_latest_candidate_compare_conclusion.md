# qfq_asof 最新候选策略池 Compare 报告

Generated at: 2026-06-04T01:58:50

## 运行口径

- 价格口径：`qfq_asof`。
- 股票池：每折 point-in-time universe。
- 策略版本过滤：同一策略族只保留最新版本；本次排除 `residual_momentum_reversal_v1`，保留 `residual_momentum_reversal_v2`。
- 成本、窗口、股票池规模等其它参数沿用当前 `config.yaml`。
- 验证期使用折级 `valid_end` as-of，未启用逐日滚动 as-of。

## 结论

- 本次 `qfq_asof` 最新候选池没有出现可用于实盘模拟的有效 candidate。
- 6 个有有效输出的候选，4 个验证折全部为负年化收益。
- 相对最好的仍是 `legacy_momentum_low_turnover_v1`，但折均年化 `-7.51%`、Sharpe `-0.730`、正收益折数 `0/4`，不满足采用门槛。
- `core_selection_quality_momentum_v1` 与 `theme_exposure_momentum_v1` 本次没有有效 candidate folds，需后续单独排查输入特征或策略启用条件。

## Candidate Summary

| candidate                          | annualized_return_mean   |   sharpe_mean | max_drawdown_mean   | win_rate_mean   |   turnover_annual_mean |   fold_count |   positive_fold_count |
|:-----------------------------------|:-------------------------|--------------:|:--------------------|:----------------|-----------------------:|-------------:|----------------------:|
| legacy_momentum_low_turnover_v1    | -7.51%                   |        -0.73  | -16.71%             | 44.92%          |                  2.206 |            4 |                     0 |
| multifactor_volume_price_filter_v1 | -18.53%                  |        -1.878 | -20.50%             | 37.75%          |                 41.326 |            4 |                     0 |
| quality_growth_price_v1            | -19.95%                  |        -2.261 | -24.99%             | 40.63%          |                 25.845 |            4 |                     0 |
| legacy_momentum                    | -29.13%                  |        -2.519 | -33.67%             | 40.14%          |                 15.637 |            4 |                     0 |
| residual_momentum_reversal_v2      | -44.87%                  |        -4.238 | -47.25%             | 34.06%          |                 72.178 |            4 |                     0 |
| ma_kline_baseline_v1               | -49.79%                  |        -4.43  | -51.06%             | 33.12%          |                 46.044 |            4 |                     0 |

## Missing Effective Outputs

- `core_selection_quality_momentum_v1`
- `theme_exposure_momentum_v1`

## 产物

- `qfq_asof_latest_walk_forward_report.md`：原始 walk-forward 报告。
- `qfq_asof_latest_candidate_summary.csv`：候选汇总。
- `qfq_asof_latest_candidate_folds.csv`：候选逐折结果。
- `qfq_asof_latest_universe_audit.csv`：股票池 point-in-time 审计。
