# legacy_momentum_low_turnover_v1 qfq_current / qfq_asof 对照

Generated at: 2026-06-04T01:22:52

## Summary

| metric                     |   qfq_current |    qfq_asof |   delta_asof_minus_current |
|:---------------------------|--------------:|------------:|---------------------------:|
| annualized_return_mean     |    -0.0420626 | -0.0751239  |                -0.0330613  |
| sharpe_mean                |    -0.458634  | -0.730412   |                -0.271778   |
| max_drawdown_mean          |    -0.161351  | -0.167112   |                -0.00576154 |
| win_rate_mean              |     0.461155  |  0.449203   |                -0.0119522  |
| turnover_annual_mean       |     2.42738   |  2.20556    |                -0.221825   |
| oos_annualized_return_mean |     0.0902916 | -0.00734146 |                -0.0976331  |
| oos_sharpe_mean            |     0.645598  |  0.0129383  |                -0.63266    |

## Conclusion

- `qfq_asof` 口径下，`legacy_momentum_low_turnover_v1` 的折均年化收益从 `-4.21%` 降到 `-7.51%`，Sharpe 从 `-0.459` 降到 `-0.730`。
- 最后一折 OOS 差异最大：`qfq_current` 的 OOS 年化收益为 `9.03%`、Sharpe 为 `0.646`；`qfq_asof` 降为 `-0.73%`、Sharpe 为 `0.013`。
- 当前结论：该策略在严格折级 as-of 价格口径下不具备可采用表现；既有 `qfq_current` 结果应降级为兼容口径参考，不能作为严格 point-in-time 结论。

## Notes

- 其它配置保持 `config.yaml` 当前口径；本次仅收窄 `compare_strategies` 为 `legacy_momentum_low_turnover_v1`。
- `qfq_current` 使用当前全历史前复权价格。
- `qfq_asof` 使用折级 as-of：训练窗按 `train_end`，验证窗按 `valid_end`。验证期逐日滚动 as-of 未启用。
- 交易执行价格链路另行使用 `bfq_raw`；本报告比较的是研究特征价格口径。
