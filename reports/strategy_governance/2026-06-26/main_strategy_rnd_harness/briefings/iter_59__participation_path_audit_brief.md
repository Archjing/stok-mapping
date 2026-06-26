# I59 Participation Path Audit Brief

日期：2026-06-26

本轮问题：I58 把强市场目标仓位设到 0.85，但回测里的平均 live exposure 仍然不高。需要确认问题到底是“仓位执行没跟上”，还是“策略多数时间没有进入强市场状态”。

## 结论

不是执行链路失败。I58 的 live exposure 基本跟着前一交易日 target exposure 走，符合 T+1 持仓生效逻辑。

真正的问题是强市场触发识别不足：回测诊断里的 `relative_lag_in_strong_benchmark_context` 是事后市场环境标签，不等于策略日频 `strong_index_context`。在这些“强基准落后”窗口里，策略自己的日频触发器很多天仍然给出低仓或中仓。

| fold | 诊断标签 | 天数 | 平均目标仓位 | 平均实盘仓位 | 高目标仓天数 | 目标仓状态 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 4 | relative_lag_in_strong_benchmark_context | 241 | 0.149718 | 0.149091 | 0 | risk_or_low=241 |
| 5 | relative_lag_in_strong_benchmark_context | 242 | 0.387402 | 0.385749 | 60 | mixed_mid=62; risk_or_low=120; strong_high=60 |

T+1 影响存在，但不是主因：

| fold | live 对同日 target 平均误差 | live 对前一日 target 平均误差 |
| --- | ---: | ---: |
| 4 | 0.000644 | 0.000047 |
| 5 | 0.009137 | 0.000075 |

## 对策略研发的含义

继续简单提高 `strong_target_exposure` 没有意义，因为很多日期根本不会触发强仓位。下一轮应优先重做或审计强市场触发信号，让它能在不使用未来信息的前提下，更早识别“沪深300强势且策略可能跑输强基准”的环境。

## 本轮产物

- 审计代码：`phase0/strategy_participation_path_audit.py`
- 单测：`tests/test_strategy_participation_path_audit.py`
- 审计明细：`reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_59__participation_path_audit/strategy_participation_path_daily.csv`
- 审计汇总：`reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_59__participation_path_audit/strategy_participation_path_summary.csv`
- 审计报告：`reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_59__participation_path_audit/strategy_participation_path_audit.md`
