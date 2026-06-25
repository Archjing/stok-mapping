# 沪深300权重归因报告

本报告是 research-only 诊断，用来解释策略在强沪深300阶段跑输时，问题更接近仓位参与不足、高权重成分遗漏、行业结构偏离，还是持仓选择不足。

## 运行口径

- 生成时间：2026-06-25 13:45:44
- 基准：`SH.000300`
- 过滤市场状态：`all`
- 高权重成分检查范围：沪深300权重前 20
- 本地历史库：`/home/zj/workspace/stok-mapping/data/manual_history/a_share_history.sqlite`
- 持仓输入：`/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/holdings_exposure/strategy_daily_holdings.csv`
- 日度暴露输入：`/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/holdings_exposure/strategy_daily_exposure.csv`
- 候选折输入：`/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/admission/strategy_admission_candidate_folds.csv`
- 市场状态输入：`/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/market_context/strategy_market_context_diagnostic.csv`
- 权重日期保守滞后：`1` 天

权重使用规则：每个持仓日默认只使用 `cn_index_weights_asof.trade_date <= date - 1 day` 的最近一条记录；这是按日线研究归因的保守可见性口径。`asof_time` 仍是治理代理字段，不代表盘中真实发布时间。

## 折级结论

| strategy_id | walk_forward_preset | fold | days | avg_live_exposure | avg_benchmark_weight_held | avg_top_n_coverage_ratio | avg_industry_l1_gap_normalized | excess_total_return | primary_driver | plain_language_summary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| strong_market_core_participation_v1 | baseline_2y_1y_5fold | 1 | 243 | 0.0202 | 0.0093 | 0.0189 | 0.8993 | 0.1717 | low_participation | 强沪深300阶段主要问题是仓位参与不足，策略没有充分吃到指数上涨。 |
| strong_market_core_participation_v1 | baseline_2y_1y_5fold | 2 | 243 | 0.0000 | 0.0000 | 0.0000 |  | 0.0407 | low_participation | 强沪深300阶段主要问题是仓位参与不足，策略没有充分吃到指数上涨。 |
| strong_market_core_participation_v1 | baseline_2y_1y_5fold | 3 | 241 | 0.0000 | 0.0000 | 0.0000 |  | 0.1267 | low_participation | 强沪深300阶段主要问题是仓位参与不足，策略没有充分吃到指数上涨。 |
| strong_market_core_participation_v1 | baseline_2y_1y_5fold | 4 | 241 | 0.0000 | 0.0000 | 0.0000 |  | -0.0989 | low_participation | 强沪深300阶段主要问题是仓位参与不足，策略没有充分吃到指数上涨。 |
| strong_market_core_participation_v1 | baseline_2y_1y_5fold | 5 | 242 | 0.1764 | 0.0783 | 0.1639 | 0.8711 | -0.2220 | low_participation | 强沪深300阶段主要问题是仓位参与不足，策略没有充分吃到指数上涨。 |

## 最常遗漏的沪深300高权重成分

| strategy_id | fold | symbol | name | industry | missed_days | avg_benchmark_weight | avg_benchmark_rank |
| --- | --- | --- | --- | --- | --- | --- | --- |
| strong_market_core_participation_v1 | 1 | SH.600519 | 贵州茅台 | 白酒 | 236 | 0.0563 | 1.0000 |
| strong_market_core_participation_v1 | 1 | SZ.300750 | 宁德时代 | 电气设备 | 58 | 0.0369 | 2.0000 |
| strong_market_core_participation_v1 | 1 | SH.600036 | 招商银行 | 银行 | 236 | 0.0315 | 2.5678 |
| strong_market_core_participation_v1 | 1 | SH.601318 | 中国平安 | 保险 | 243 | 0.0311 | 2.8971 |
| strong_market_core_participation_v1 | 1 | SZ.000858 | 五 粮 液 | 白酒 | 236 | 0.0228 | 4.3390 |
| strong_market_core_participation_v1 | 1 | SZ.000333 | 美的集团 | 家用电器 | 243 | 0.0178 | 5.7901 |
| strong_market_core_participation_v1 | 1 | SH.601012 | 隆基绿能 | 电气设备 | 236 | 0.0168 | 6.6356 |
| strong_market_core_participation_v1 | 1 | SH.601166 | 兴业银行 | 银行 | 243 | 0.0147 | 7.8066 |
| strong_market_core_participation_v1 | 1 | SZ.300059 | 东方财富 | 证券 | 236 | 0.0127 | 10.4576 |
| strong_market_core_participation_v1 | 1 | SH.600276 | 恒瑞医药 | 化学制药 | 240 | 0.0125 | 12.0958 |
| strong_market_core_participation_v1 | 1 | SH.601888 | 中国中免 | 旅游服务 | 236 | 0.0123 | 12.5042 |
| strong_market_core_participation_v1 | 1 | SZ.002415 | 海康威视 | IT设备 | 237 | 0.0121 | 11.4557 |
| strong_market_core_participation_v1 | 1 | SZ.002594 | 比亚迪 | 汽车整车 | 183 | 0.0120 | 11.4973 |
| strong_market_core_participation_v1 | 1 | SH.603259 | XD药明康 | 化学制药 | 215 | 0.0119 | 12.3581 |
| strong_market_core_participation_v1 | 1 | SH.600900 | 长江电力 | 水力发电 | 221 | 0.0114 | 13.3529 |
| strong_market_core_participation_v1 | 1 | SH.600887 | 伊利股份 | 乳制品 | 240 | 0.0112 | 13.8750 |
| strong_market_core_participation_v1 | 1 | SZ.000651 | 格力电器 | 家用电器 | 241 | 0.0108 | 15.4149 |
| strong_market_core_participation_v1 | 1 | SH.600030 | 中信证券 | 证券 | 239 | 0.0107 | 14.9749 |
| strong_market_core_participation_v1 | 1 | SZ.000002 | 万 科Ａ | 全国地产 | 40 | 0.0102 | 16.9500 |
| strong_market_core_participation_v1 | 1 | SZ.002714 | 牧原股份 | 农业综合 | 39 | 0.0102 | 17.1026 |
| strong_market_core_participation_v1 | 1 | SZ.002475 | 立讯精密 | 元器件 | 163 | 0.0101 | 16.0368 |
| strong_market_core_participation_v1 | 1 | SZ.000001 | 平安银行 | 银行 | 156 | 0.0100 | 15.9679 |
| strong_market_core_participation_v1 | 1 | SH.600031 | 三一重工 | 工程机械 | 60 | 0.0096 | 17.2667 |
| strong_market_core_participation_v1 | 1 | SZ.000725 | 京东方Ａ | 元器件 | 81 | 0.0095 | 18.7160 |
| strong_market_core_participation_v1 | 1 | SZ.002460 | 赣锋锂业 | 小金属 | 1 | 0.0090 | 18.0000 |
| strong_market_core_participation_v1 | 1 | SH.600309 | 万华化学 | 化工原料 | 53 | 0.0090 | 19.3208 |
| strong_market_core_participation_v1 | 1 | SZ.000568 | 泸州老窖 | 白酒 | 80 | 0.0088 | 18.9125 |
| strong_market_core_participation_v1 | 1 | SH.601398 | 工商银行 | 银行 | 78 | 0.0087 | 19.9487 |
| strong_market_core_participation_v1 | 1 | SZ.300760 | 迈瑞医疗 | 医疗保健 | 1 | 0.0083 | 20.0000 |
| strong_market_core_participation_v1 | 2 | SH.600519 | 贵州茅台 | 白酒 | 243 | 0.0594 | 1.0000 |

## 风险说明

- 这不是交易建议，也不改变 admission 结论。
- 归因使用日线持仓和日线基准权重，只解释已发生研究样本，不提供盘中择时能力。
- 如果策略本身不是指数增强策略，低沪深300覆盖不一定是错误；它只说明强指数行情下跟随基准上涨的能力不足。
- 日度归因行数：1210；行业主动权重行数：85266。
