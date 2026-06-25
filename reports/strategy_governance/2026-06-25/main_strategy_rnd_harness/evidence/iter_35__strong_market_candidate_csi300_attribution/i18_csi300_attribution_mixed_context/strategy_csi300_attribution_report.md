# I34 沪深300权重归因报告

本报告是 research-only 诊断，用来解释策略在强沪深300阶段跑输时，问题更接近仓位参与不足、高权重成分遗漏、行业结构偏离，还是持仓选择不足。

## 运行口径

- 生成时间：2026-06-25 10:29:33
- 基准：`SH.000300`
- 过滤市场状态：`mixed_or_unresolved_context`
- 高权重成分检查范围：沪深300权重前 20
- 本地历史库：`/home/zj/workspace/stok-mapping/data/manual_history/a_share_history.sqlite`
- 持仓输入：`/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_35__strong_market_candidate_csi300_attribution/i18_holdings_exposure/strategy_daily_holdings.csv`
- 日度暴露输入：`/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_35__strong_market_candidate_csi300_attribution/i18_holdings_exposure/strategy_daily_exposure.csv`
- 候选折输入：`/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-24/main_strategy_admission_breakthrough/evidence/iter_18__strong_index_dynamic_trigger/admission/strategy_admission_candidate_folds.csv`
- 市场状态输入：`/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_35__strong_market_candidate_csi300_attribution/i18_market_context/strategy_market_context_diagnostic.csv`
- 权重日期保守滞后：`1` 天

权重使用规则：每个持仓日默认只使用 `cn_index_weights_asof.trade_date <= date - 1 day` 的最近一条记录；这是按日线研究归因的保守可见性口径。`asof_time` 仍是治理代理字段，不代表盘中真实发布时间。

## 折级结论

| strategy_id | walk_forward_preset | fold | days | avg_live_exposure | avg_benchmark_weight_held | avg_top_n_coverage_ratio | avg_industry_l1_gap_normalized | excess_total_return | primary_driver | plain_language_summary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| strong_index_participation_dynamic_trigger_v1 | baseline_2y_1y_5fold | 4 | 241 | 0.0000 | 0.0000 | 0.0000 |  | -0.0989 | low_participation | 强沪深300阶段主要问题是仓位参与不足，策略没有充分吃到指数上涨。 |
| strong_index_participation_dynamic_trigger_v1 | baseline_2y_1y_5fold | 5 | 242 | 0.2709 | 0.0354 | 0.0583 | 1.4987 | -0.0614 | low_participation | 强沪深300阶段主要问题是仓位参与不足，策略没有充分吃到指数上涨。 |

## 最常遗漏的沪深300高权重成分

| strategy_id | fold | symbol | name | industry | missed_days | avg_benchmark_weight | avg_benchmark_rank |
| --- | --- | --- | --- | --- | --- | --- | --- |
| strong_index_participation_dynamic_trigger_v1 | 4 | SH.600519 | 贵州茅台 | 白酒 | 241 | 0.0509 | 1.0000 |
| strong_index_participation_dynamic_trigger_v1 | 4 | SZ.300750 | 宁德时代 | 电气设备 | 241 | 0.0311 | 2.0000 |
| strong_index_participation_dynamic_trigger_v1 | 4 | SH.601318 | 中国平安 | 保险 | 241 | 0.0269 | 3.0000 |
| strong_index_participation_dynamic_trigger_v1 | 4 | SH.600036 | 招商银行 | 银行 | 241 | 0.0235 | 4.0000 |
| strong_index_participation_dynamic_trigger_v1 | 4 | SZ.000333 | 美的集团 | 家用电器 | 241 | 0.0178 | 5.3568 |
| strong_index_participation_dynamic_trigger_v1 | 4 | SH.600900 | 长江电力 | 水力发电 | 241 | 0.0172 | 6.3154 |
| strong_index_participation_dynamic_trigger_v1 | 4 | SH.601899 | 紫金矿业 | 铜 | 241 | 0.0145 | 8.4813 |
| strong_index_participation_dynamic_trigger_v1 | 4 | SZ.000858 | 五 粮 液 | 白酒 | 241 | 0.0143 | 8.6598 |
| strong_index_participation_dynamic_trigger_v1 | 4 | SH.601166 | 兴业银行 | 银行 | 241 | 0.0138 | 8.9087 |
| strong_index_participation_dynamic_trigger_v1 | 4 | SZ.300059 | 东方财富 | 证券 | 177 | 0.0130 | 11.3164 |
| strong_index_participation_dynamic_trigger_v1 | 4 | SZ.002594 | 比亚迪 | 汽车整车 | 241 | 0.0127 | 10.4191 |
| strong_index_participation_dynamic_trigger_v1 | 4 | SH.600030 | 中信证券 | 证券 | 241 | 0.0120 | 11.9087 |
| strong_index_participation_dynamic_trigger_v1 | 4 | SH.601398 | 工商银行 | 银行 | 241 | 0.0111 | 12.8714 |
| strong_index_participation_dynamic_trigger_v1 | 4 | SH.600276 | 恒瑞医药 | 化学制药 | 241 | 0.0107 | 13.6307 |
| strong_index_participation_dynamic_trigger_v1 | 4 | SZ.002475 | 立讯精密 | 元器件 | 201 | 0.0104 | 14.7264 |
| strong_index_participation_dynamic_trigger_v1 | 4 | SH.601328 | 交通银行 | 银行 | 241 | 0.0100 | 15.3776 |
| strong_index_participation_dynamic_trigger_v1 | 4 | SZ.000651 | 格力电器 | 家用电器 | 241 | 0.0100 | 15.3734 |
| strong_index_participation_dynamic_trigger_v1 | 4 | SZ.300760 | 迈瑞医疗 | 医疗保健 | 141 | 0.0094 | 16.7092 |
| strong_index_participation_dynamic_trigger_v1 | 4 | SH.600887 | 伊利股份 | 乳制品 | 241 | 0.0091 | 17.4896 |
| strong_index_participation_dynamic_trigger_v1 | 4 | SH.688981 | 中芯国际 | 半导体 | 100 | 0.0091 | 17.5000 |
| strong_index_participation_dynamic_trigger_v1 | 4 | SH.601816 | 京沪高铁 | 铁路 | 19 | 0.0088 | 19.1053 |
| strong_index_participation_dynamic_trigger_v1 | 4 | SH.600309 | 万华化学 | 化工原料 | 101 | 0.0088 | 18.9901 |
| strong_index_participation_dynamic_trigger_v1 | 4 | SZ.000725 | 京东方Ａ | 元器件 | 163 | 0.0085 | 19.6503 |
| strong_index_participation_dynamic_trigger_v1 | 4 | SH.601288 | 农业银行 | 银行 | 62 | 0.0084 | 18.7419 |
| strong_index_participation_dynamic_trigger_v1 | 5 | SH.600519 | 贵州茅台 | 白酒 | 230 | 0.0404 | 1.3565 |
| strong_index_participation_dynamic_trigger_v1 | 5 | SZ.300750 | 宁德时代 | 电气设备 | 213 | 0.0359 | 1.5587 |
| strong_index_participation_dynamic_trigger_v1 | 5 | SH.601318 | 中国平安 | 保险 | 229 | 0.0270 | 3.0961 |
| strong_index_participation_dynamic_trigger_v1 | 5 | SH.600036 | 招商银行 | 银行 | 242 | 0.0230 | 4.5289 |
| strong_index_participation_dynamic_trigger_v1 | 5 | SZ.300308 | 中际旭创 | 通信设备 | 145 | 0.0191 | 8.0759 |
| strong_index_participation_dynamic_trigger_v1 | 5 | SH.601899 | 紫金矿业 | 铜 | 186 | 0.0179 | 6.6828 |

## 风险说明

- 这不是交易建议，也不改变 admission 结论。
- 归因使用日线持仓和日线基准权重，只解释已发生研究样本，不提供盘中择时能力。
- 如果策略本身不是指数增强策略，低沪深300覆盖不一定是错误；它只说明强指数行情下跟随基准上涨的能力不足。
- 日度归因行数：483；行业主动权重行数：33483。
