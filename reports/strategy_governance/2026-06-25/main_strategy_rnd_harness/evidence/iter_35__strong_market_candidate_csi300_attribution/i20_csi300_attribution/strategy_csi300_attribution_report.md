# I34 沪深300权重归因报告

本报告是 research-only 诊断，用来解释策略在强沪深300阶段跑输时，问题更接近仓位参与不足、高权重成分遗漏、行业结构偏离，还是持仓选择不足。

## 运行口径

- 生成时间：2026-06-25 10:28:24
- 基准：`SH.000300`
- 过滤市场状态：`relative_lag_in_strong_benchmark_context`
- 高权重成分检查范围：沪深300权重前 20
- 本地历史库：`/home/zj/workspace/stok-mapping/data/manual_history/a_share_history.sqlite`
- 持仓输入：`/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_35__strong_market_candidate_csi300_attribution/i20_holdings_exposure/strategy_daily_holdings.csv`
- 日度暴露输入：`/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_35__strong_market_candidate_csi300_attribution/i20_holdings_exposure/strategy_daily_exposure.csv`
- 候选折输入：`/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-24/main_strategy_admission_breakthrough/evidence/iter_20__strong_market_liquid_breadth/admission/strategy_admission_candidate_folds.csv`
- 市场状态输入：`/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_35__strong_market_candidate_csi300_attribution/i20_market_context/strategy_market_context_diagnostic.csv`
- 权重日期保守滞后：`1` 天

权重使用规则：每个持仓日默认只使用 `cn_index_weights_asof.trade_date <= date - 1 day` 的最近一条记录；这是按日线研究归因的保守可见性口径。`asof_time` 仍是治理代理字段，不代表盘中真实发布时间。

## 折级结论

| strategy_id | walk_forward_preset | fold | days | avg_live_exposure | avg_benchmark_weight_held | avg_top_n_coverage_ratio | avg_industry_l1_gap_normalized | excess_total_return | primary_driver | plain_language_summary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| strong_market_liquid_breadth_participation_v1 | baseline_2y_1y_5fold | 5 | 242 | 0.1355 | 0.0168 | 0.0179 | 1.6103 | -0.1028 | low_participation | 强沪深300阶段主要问题是仓位参与不足，策略没有充分吃到指数上涨。 |

## 最常遗漏的沪深300高权重成分

| strategy_id | fold | symbol | name | industry | missed_days | avg_benchmark_weight | avg_benchmark_rank |
| --- | --- | --- | --- | --- | --- | --- | --- |
| strong_market_liquid_breadth_participation_v1 | 5 | SH.600519 | 贵州茅台 | 白酒 | 242 | 0.0402 | 1.3884 |
| strong_market_liquid_breadth_participation_v1 | 5 | SZ.300750 | 宁德时代 | 电气设备 | 242 | 0.0357 | 1.6116 |
| strong_market_liquid_breadth_participation_v1 | 5 | SH.601318 | 中国平安 | 保险 | 242 | 0.0272 | 3.0909 |
| strong_market_liquid_breadth_participation_v1 | 5 | SH.600036 | 招商银行 | 银行 | 242 | 0.0230 | 4.5289 |
| strong_market_liquid_breadth_participation_v1 | 5 | SZ.300308 | 中际旭创 | 通信设备 | 159 | 0.0188 | 7.9434 |
| strong_market_liquid_breadth_participation_v1 | 5 | SH.601899 | 紫金矿业 | 铜 | 202 | 0.0173 | 6.7525 |
| strong_market_liquid_breadth_participation_v1 | 5 | SZ.000333 | 美的集团 | 家用电器 | 242 | 0.0162 | 6.5041 |
| strong_market_liquid_breadth_participation_v1 | 5 | SZ.300502 | 新易盛 | 通信设备 | 138 | 0.0152 | 7.5942 |
| strong_market_liquid_breadth_participation_v1 | 5 | SH.600900 | 长江电力 | 水力发电 | 242 | 0.0151 | 8.0702 |
| strong_market_liquid_breadth_participation_v1 | 5 | SH.601166 | 兴业银行 | 银行 | 242 | 0.0150 | 8.3636 |
| strong_market_liquid_breadth_participation_v1 | 5 | SZ.300059 | 东方财富 | 证券 | 242 | 0.0129 | 10.2231 |
| strong_market_liquid_breadth_participation_v1 | 5 | SZ.002594 | 比亚迪 | 汽车整车 | 242 | 0.0127 | 12.6570 |
| strong_market_liquid_breadth_participation_v1 | 5 | SH.600030 | 中信证券 | 证券 | 242 | 0.0119 | 12.8388 |
| strong_market_liquid_breadth_participation_v1 | 5 | SZ.000858 | 五 粮 液 | 白酒 | 126 | 0.0115 | 13.9127 |
| strong_market_liquid_breadth_participation_v1 | 5 | SH.600276 | 恒瑞医药 | 化学制药 | 242 | 0.0115 | 13.9835 |
| strong_market_liquid_breadth_participation_v1 | 5 | SH.688256 | 寒武纪 | 半导体 | 138 | 0.0112 | 14.4638 |
| strong_market_liquid_breadth_participation_v1 | 5 | SH.601398 | 工商银行 | 银行 | 242 | 0.0112 | 15.2355 |
| strong_market_liquid_breadth_participation_v1 | 5 | SZ.002475 | 立讯精密 | 元器件 | 140 | 0.0110 | 13.8714 |
| strong_market_liquid_breadth_participation_v1 | 5 | SZ.300274 | 阳光电源 | 电气设备 | 63 | 0.0107 | 17.0159 |
| strong_market_liquid_breadth_participation_v1 | 5 | SH.601138 | 工业富联 | 通信设备 | 65 | 0.0105 | 17.5538 |
| strong_market_liquid_breadth_participation_v1 | 5 | SH.603259 | XD药明康 | 化学制药 | 118 | 0.0101 | 17.4068 |
| strong_market_liquid_breadth_participation_v1 | 5 | SZ.000651 | 格力电器 | 家用电器 | 104 | 0.0099 | 16.0481 |
| strong_market_liquid_breadth_participation_v1 | 5 | SH.601211 | 国泰海通 | 证券 | 126 | 0.0098 | 16.8175 |
| strong_market_liquid_breadth_participation_v1 | 5 | SH.601288 | 农业银行 | 银行 | 126 | 0.0095 | 19.1270 |
| strong_market_liquid_breadth_participation_v1 | 5 | SH.688981 | 中芯国际 | 半导体 | 113 | 0.0094 | 18.6991 |
| strong_market_liquid_breadth_participation_v1 | 5 | SH.688041 | 海光信息 | 半导体 | 36 | 0.0093 | 17.3333 |
| strong_market_liquid_breadth_participation_v1 | 5 | SH.600887 | 伊利股份 | 乳制品 | 61 | 0.0093 | 16.7377 |
| strong_market_liquid_breadth_participation_v1 | 5 | SH.601328 | 交通银行 | 银行 | 104 | 0.0092 | 17.9519 |
| strong_market_liquid_breadth_participation_v1 | 5 | SH.601816 | 京沪高铁 | 铁路 | 20 | 0.0086 | 20.0000 |
| strong_market_liquid_breadth_participation_v1 | 5 | SH.600919 | 江苏银行 | 银行 | 22 | 0.0085 | 19.0000 |

## 风险说明

- 这不是交易建议，也不改变 admission 结论。
- 归因使用日线持仓和日线基准权重，只解释已发生研究样本，不提供盘中择时能力。
- 如果策略本身不是指数增强策略，低沪深300覆盖不一定是错误；它只说明强指数行情下跟随基准上涨的能力不足。
- 日度归因行数：242；行业主动权重行数：16470。
