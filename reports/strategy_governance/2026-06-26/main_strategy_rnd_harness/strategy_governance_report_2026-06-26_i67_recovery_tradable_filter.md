# Strategy Governance Report - I67 Recovery Tradable Filter

日期：2026-06-26

报告性质：Harness 策略研发专项实验报告。本报告记录 I67 `strong_benchmark_recovery_tradable_v1` 的 research-only scoped admission，不改变默认 12 个候选策略池，不进入 paper review。

## 背景

I66 发现：recovery 策略失败不只是仓位问题，还和 recovery 是否可交易、是否应该承担行业偏离有关。I67 因此新增一个最小研究策略：在 I63 的 recovery quality 基础上，增加横截面宽度过滤。

## 实验变量

新增策略：`strong_benchmark_recovery_tradable_v1`。

新增判断：

- `recovery_breadth_mom20_positive_ratio >= 0.45`
- `recovery_breadth_mom60_positive_ratio >= 0.35`
- `recovery_breadth_industry_positive_ratio >= 0.50`
- `recovery_breadth_avg_amount_ratio20 >= 0.90`

数据安全口径：breadth 特征按日生成后整体 shift 一天，避免当天收盘后才知道的信息影响当天持仓。策略持仓仍由下一日权重生效。

## 命令

```bash
./.venv/bin/python -m phase0.cli strategy-admission \
  --config config.main_strategy_i67_recovery_tradable_20260626.yaml \
  --presets baseline_2y_1y_5fold \
  --strategy-set i67_strong_benchmark_recovery_tradable_v1 \
  --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_67__recovery_tradable/admission
```

```bash
./.venv/bin/python -m phase0.cli strategy-holdings-exposure \
  --config config.main_strategy_i67_recovery_tradable_20260626.yaml \
  --candidate-folds reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_67__recovery_tradable/admission/strategy_admission_candidate_folds.csv \
  --market-context reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/market_context/strategy_market_context_diagnostic.csv \
  --strategy strong_benchmark_recovery_tradable_v1 \
  --presets baseline_2y_1y_5fold \
  --benchmark-symbol SH.000300 \
  --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_67__recovery_tradable/holdings_exposure
```

## Admission 摘要

| 指标 | 数值 |
| --- | ---: |
| 年化收益均值 | -0.0067 |
| Sharpe 均值 | -0.3168 |
| 最大回撤最差值 | -0.0780 |
| 正收益 fold 比例 | 0.40 |
| 相对沪深300正超额 fold 比例 | 0.40 |
| 年化换手均值 | 1.4164 |
| admission action | reject |

## Recovery 过滤情况

|   fold |   recovery_days |   tradable_recovery_days |   tradable_ratio_of_recovery |   avg_live_exposure |   sum_benchmark_return |
|-------:|----------------:|-------------------------:|-----------------------------:|--------------------:|-----------------------:|
|      1 |               0 |                        0 |                              |              0.211  |                -0.1754 |
|      2 |              56 |                       28 |                         0.5  |              0.2333 |                -0.0256 |
|      3 |              22 |                        6 |                         0.27 |              0.166  |                -0.1259 |
|      4 |              49 |                        8 |                         0.16 |              0.1989 |                 0.1154 |
|      5 |              46 |                       36 |                         0.78 |              0.468  |                 0.1467 |

## I63 vs I67

|   fold |   annualized_return_i63_quality |   annualized_return_i67_tradable |   annualized_return_delta_i67_minus_i63 |   excess_annualized_return_i63_quality |   excess_annualized_return_i67_tradable |   excess_annualized_return_delta_i67_minus_i63 |
|-------:|--------------------------------:|---------------------------------:|----------------------------------------:|---------------------------------------:|----------------------------------------:|-----------------------------------------------:|
|      1 |                         -0.0465 |                          -0.0465 |                                  0      |                                 0.1331 |                                  0.1331 |                                         0      |
|      2 |                         -0.0618 |                          -0.0623 |                                 -0.0004 |                                -0.0073 |                                 -0.0077 |                                        -0.0004 |
|      3 |                         -0.0176 |                          -0.0166 |                                  0.001  |                                 0.1233 |                                  0.1243 |                                         0.001  |
|      4 |                         -0.001  |                           0.0127 |                                  0.0137 |                                -0.086  |                                 -0.0722 |                                         0.0137 |
|      5 |                          0.0793 |                           0.0793 |                                  0      |                                -0.0717 |                                 -0.0717 |                                         0      |

## 判断

I67 没有通过准入。主要原因是正收益 fold 比例仍只有 0.40，Sharpe 为负，且 overfit risk 为 high。

但 I67 给出一个有用证据：fold4 明显改善。fold4 的 recovery 天数从 49 天中只保留 8 个 tradable recovery 日，年化收益从 -0.0010 改为 0.0127，说明市场宽度过滤能减少一部分错误 recovery。

不足也很明确：

- fold2 几乎没有改善，说明宽度过滤没有识别出该窗口的假 recovery；
- fold5 不变，说明它保留了已有有效窗口，但没有新增优势；
- 整体仍跑不过强沪深300阶段，不能作为实盘候选。

## 下一步

I68 不建议继续微调阈值。更值得做的是“negative recovery classifier”审计：找出 fold2 这类假 recovery 的共同特征，例如恢复前跌幅结构、行业领导缺失、银行/白酒/科技的轮动方向、成交额扩散失败、指数上涨但成分收益分布偏斜。

在没有找到 fold2 的失败特征前，不应把 recovery 策略加入默认候选池或 paper review。
