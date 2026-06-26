# Strategy Governance Report - I66 Recovery Active Industry Audit

日期：2026-06-26

报告性质：Harness 策略研发专项审计报告。本报告只解释 I63 recovery quality 策略在 recovery 日期的行业偏离，不新增策略，不改变 admission 结论。

## 背景

I63 的 `strong_benchmark_recovery_quality_v1` 仍然未通过 admission。I64 说明单独用 drawdown 修复信号不能区分有效 recovery 和错误 recovery。I65 进一步看到 recovery 期间组合头部行业差异明显。

I66 的问题是：这些 recovery 期持仓，相对沪深300行业权重，到底偏在哪里？

## 命令

```bash
./.venv/bin/python -m phase0.cli strategy-csi300-attribution \
  --config config.main_strategy_i63_recovery_quality_20260626.yaml \
  --holdings reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_63__recovery_quality/holdings_exposure/strategy_daily_holdings.csv \
  --daily-exposure reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_63__recovery_quality/holdings_exposure/strategy_daily_exposure.csv \
  --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_66__recovery_active_industry_audit/csi300_attribution_all \
  --context-label all \
  --top-n 20 \
  --weight-date-lag-days 1
```

随后用 I63 daily exposure 的 `recovery_index_context` 和 `recovery_quality_index_context` 对归因结果做 join 过滤和聚合。

## 核心结果

|   fold |   recovery_days |   quality_days |   benchmark_return_sum |   avg_live_exposure |   avg_industry_l1_gap_norm | top_overweight_modes   | top_underweight_modes        |
|-------:|----------------:|---------------:|-----------------------:|--------------------:|---------------------------:|:-----------------------|:-----------------------------|
|      2 |              56 |             34 |                -0.0415 |              0.3866 |                     0.3861 | 白酒=56                  | 软件服务=25; 证券=21; 半导体=10       |
|      3 |              22 |             11 |                 0.0147 |              0.2    |                     0.3761 | 白酒=21                  | 半导体=16; 证券=5                 |
|      4 |              49 |             17 |                -0.0221 |              0.3459 |                     0.3745 | 白酒=35; 银行=13           | 证券=18; 半导体=17; 软件服务=13       |
|      5 |              46 |             41 |                 0.1432 |              0.4633 |                     0.3797 | 银行=46                  | 小金属=37; 软件服务=3; 半导体=3; 元器件=3 |

## 超配行业 Top3（recovery 全部日期，归一化口径）

|   fold | industry   |   days |   avg_normalized_active_weight |   avg_strategy_industry_weight_normalized |   avg_benchmark_industry_weight |
|-------:|:-----------|-------:|-------------------------------:|------------------------------------------:|--------------------------------:|
|      2 | 白酒         |     56 |                      0.0527655 |                                 0.155756  |                       0.102991  |
|      2 | 电气设备       |     56 |                      0.0311898 |                                 0.137269  |                       0.106079  |
|      2 | 银行         |     56 |                      0.028036  |                                 0.138367  |                       0.110331  |
|      4 | 白酒         |     48 |                      0.0424136 |                                 0.134632  |                       0.0922186 |
|      4 | 银行         |     48 |                      0.0407237 |                                 0.166966  |                       0.126243  |
|      4 | 家用电器       |     48 |                      0.0157569 |                                 0.0535679 |                       0.0378109 |
|      5 | 银行         |     46 |                      0.0588861 |                                 0.208548  |                       0.149662  |
|      5 | 白酒         |     46 |                      0.0308719 |                                 0.0956038 |                       0.0647319 |
|      5 | 保险         |     46 |                      0.0137734 |                                 0.0551496 |                       0.0413762 |

## 低配行业 Top3（recovery 全部日期，归一化口径）

|   fold | industry   |   days |   avg_normalized_active_weight |   avg_strategy_industry_weight_normalized |   avg_benchmark_industry_weight |
|-------:|:-----------|-------:|-------------------------------:|------------------------------------------:|--------------------------------:|
|      2 | 软件服务       |     56 |                    -0.0144512  |                                0.00714022 |                      0.0215914  |
|      2 | 证券         |     56 |                    -0.0143643  |                                0.0385194  |                      0.0528837  |
|      2 | 半导体        |     56 |                    -0.0139378  |                                0.0240428  |                      0.0379807  |
|      4 | 证券         |     48 |                    -0.0139834  |                                0.0428013  |                      0.0567847  |
|      4 | 半导体        |     48 |                    -0.0134005  |                                0.033966   |                      0.0473665  |
|      4 | 小金属        |     48 |                    -0.0127275  |                                0          |                      0.0127275  |
|      5 | 小金属        |     46 |                    -0.0119209  |                                0.00131407 |                      0.013235   |
|      5 | 软件服务       |     46 |                    -0.0108992  |                                0.00824234 |                      0.0191416  |
|      5 | 航空         |     46 |                    -0.00992589 |                                0          |                      0.00992589 |

## 判断

这轮结果说明：recovery 策略的问题不只是仓位不够，也不是单个行业一定错。真正的问题是 recovery 是否可交易、以及 recovery 阶段是否应该承担行业偏离，目前没有方法论。

- fold2：recovery 期间指数收益为负，策略还超配白酒/电气设备/银行，低配软件服务/证券/半导体。这不是有效恢复窗口。
- fold4：recovery 期间指数收益也为负，策略超配白酒/银行，没有救回收益。
- fold5：recovery 期间指数收益明显为正，策略超配银行，与当时市场主线一致，所以表现好。

因此，下一步不应继续简单调大 recovery target exposure。更合理的策略构造方向是：

1. 增加 recovery 可交易性过滤，例如指数恢复宽度、上涨行业数量、成交额扩散、核心行业同步性；
2. 在 recovery 早期降低 alpha tilt，让组合更贴近沪深300；
3. 只有在行业领导明确、且历史审计显示该行业偏离有效时，才允许主动行业倾斜；
4. admission 中继续同时看绝对收益和相对沪深300超额，避免“指数涨了但策略没跟上”。

## 数据与泄漏控制

- 沪深300权重使用 `cn_index_weights_asof`。
- 本轮设置 `weight_date_lag_days=1`，每个持仓日只使用 `trade_date <= date - 1 day` 的最近权重。
- `asof_time` 仍是治理代理字段，不解释为盘中真实发布时间。
- 行业字段来自本地主库元数据，适合审计结构，不等同于完整历史 PIT 行业分类。
- 原始 `strategy_csi300_industry_active_weights.csv` 约 17MB，作为本地中间产物保留，不建议随本轮提交上传。

## 产物

- `recovery_active_industry_fold_summary.csv`
- `recovery_active_industry_by_industry.csv`
- `recovery_active_industry_focus_top.csv`
- `recovery_active_industry_daily_summary.csv`
- `recovery_active_industry_audit.md`
- `iter_66__recovery_active_industry_audit_brief.html`
