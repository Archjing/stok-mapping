# I34 沪深300权重归因报告

本报告是 research-only 诊断，用来解释策略在强沪深300阶段跑输时，问题更接近仓位参与不足、高权重成分遗漏、行业结构偏离，还是持仓选择不足。

## 运行口径

- 生成时间：2026-06-25 10:20:19
- 基准：`SH.000300`
- 过滤市场状态：`relative_lag_in_strong_benchmark_context`
- 高权重成分检查范围：沪深300权重前 20
- 本地历史库：`/home/zj/workspace/stok-mapping/data/manual_history/a_share_history.sqlite`
- 持仓输入：`/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-24/main_strategy_admission_breakthrough/evidence/iter_10__daily_holdings_exposure/strategy_daily_holdings.csv`
- 日度暴露输入：`/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-24/main_strategy_admission_breakthrough/evidence/iter_10__daily_holdings_exposure/strategy_daily_exposure.csv`
- 候选折输入：未提供
- 市场状态输入：未提供
- 权重日期保守滞后：`1` 天

权重使用规则：每个持仓日默认只使用 `cn_index_weights_asof.trade_date <= date - 1 day` 的最近一条记录；这是按日线研究归因的保守可见性口径。`asof_time` 仍是治理代理字段，不代表盘中真实发布时间。

## 折级结论

| strategy_id | walk_forward_preset | fold | days | avg_live_exposure | avg_benchmark_weight_held | avg_top_n_coverage_ratio | avg_industry_l1_gap_normalized | excess_total_return | primary_driver | plain_language_summary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| price_volume_low_turnover_v1 | baseline_2y_1y_5fold | 4 | 241 | 0.4257 | 0.0364 | 0.0265 | 1.6681 | -0.0127 | low_participation | 强沪深300阶段主要问题是仓位参与不足，策略没有充分吃到指数上涨。 |
| price_volume_low_turnover_v1 | baseline_2y_1y_5fold | 5 | 203 | 0.4607 | 0.0491 | 0.0978 | 1.5574 | -0.1006 | low_participation | 强沪深300阶段主要问题是仓位参与不足，策略没有充分吃到指数上涨。 |

## 最常遗漏的沪深300高权重成分

| strategy_id | fold | symbol | name | industry | missed_days | avg_benchmark_weight | avg_benchmark_rank |
| --- | --- | --- | --- | --- | --- | --- | --- |
| price_volume_low_turnover_v1 | 4 | SH.600519 | 贵州茅台 | 白酒 | 241 | 0.0509 | 1.0000 |
| price_volume_low_turnover_v1 | 4 | SZ.300750 | 宁德时代 | 电气设备 | 241 | 0.0311 | 2.0000 |
| price_volume_low_turnover_v1 | 4 | SH.601318 | 中国平安 | 保险 | 241 | 0.0269 | 3.0000 |
| price_volume_low_turnover_v1 | 4 | SH.600036 | 招商银行 | 银行 | 241 | 0.0235 | 4.0000 |
| price_volume_low_turnover_v1 | 4 | SZ.000333 | 美的集团 | 家用电器 | 241 | 0.0178 | 5.3568 |
| price_volume_low_turnover_v1 | 4 | SH.600900 | 长江电力 | 水力发电 | 201 | 0.0171 | 6.3085 |
| price_volume_low_turnover_v1 | 4 | SH.601899 | 紫金矿业 | 铜 | 201 | 0.0143 | 8.7811 |
| price_volume_low_turnover_v1 | 4 | SZ.000858 | 五 粮 液 | 白酒 | 241 | 0.0143 | 8.6598 |
| price_volume_low_turnover_v1 | 4 | SH.601166 | 兴业银行 | 银行 | 201 | 0.0136 | 9.1791 |
| price_volume_low_turnover_v1 | 4 | SZ.300059 | 东方财富 | 证券 | 177 | 0.0130 | 11.3164 |
| price_volume_low_turnover_v1 | 4 | SZ.002594 | 比亚迪 | 汽车整车 | 241 | 0.0127 | 10.4191 |
| price_volume_low_turnover_v1 | 4 | SH.600030 | 中信证券 | 证券 | 241 | 0.0120 | 11.9087 |
| price_volume_low_turnover_v1 | 4 | SH.601398 | 工商银行 | 银行 | 241 | 0.0111 | 12.8714 |
| price_volume_low_turnover_v1 | 4 | SH.600276 | 恒瑞医药 | 化学制药 | 241 | 0.0107 | 13.6307 |
| price_volume_low_turnover_v1 | 4 | SZ.002475 | 立讯精密 | 元器件 | 201 | 0.0104 | 14.7264 |
| price_volume_low_turnover_v1 | 4 | SH.601328 | 交通银行 | 银行 | 241 | 0.0100 | 15.3776 |
| price_volume_low_turnover_v1 | 4 | SZ.000651 | 格力电器 | 家用电器 | 241 | 0.0100 | 15.3734 |
| price_volume_low_turnover_v1 | 4 | SZ.300760 | 迈瑞医疗 | 医疗保健 | 141 | 0.0094 | 16.7092 |
| price_volume_low_turnover_v1 | 4 | SH.600887 | 伊利股份 | 乳制品 | 241 | 0.0091 | 17.4896 |
| price_volume_low_turnover_v1 | 4 | SH.688981 | 中芯国际 | 半导体 | 100 | 0.0091 | 17.5000 |
| price_volume_low_turnover_v1 | 4 | SH.600309 | 万华化学 | 化工原料 | 83 | 0.0089 | 18.7711 |
| price_volume_low_turnover_v1 | 4 | SH.601816 | 京沪高铁 | 铁路 | 19 | 0.0088 | 19.1053 |
| price_volume_low_turnover_v1 | 4 | SZ.000725 | 京东方Ａ | 元器件 | 163 | 0.0085 | 19.6503 |
| price_volume_low_turnover_v1 | 4 | SH.601288 | 农业银行 | 银行 | 62 | 0.0084 | 18.7419 |
| price_volume_low_turnover_v1 | 5 | SH.600519 | 贵州茅台 | 白酒 | 203 | 0.0408 | 1.2956 |
| price_volume_low_turnover_v1 | 5 | SZ.300750 | 宁德时代 | 电气设备 | 163 | 0.0351 | 1.6319 |
| price_volume_low_turnover_v1 | 5 | SH.601318 | 中国平安 | 保险 | 203 | 0.0276 | 3.1084 |
| price_volume_low_turnover_v1 | 5 | SH.600036 | 招商银行 | 银行 | 203 | 0.0234 | 4.5517 |
| price_volume_low_turnover_v1 | 5 | SZ.300308 | 中际旭创 | 通信设备 | 120 | 0.0199 | 8.2667 |
| price_volume_low_turnover_v1 | 5 | SH.601899 | 紫金矿业 | 铜 | 163 | 0.0167 | 7.2699 |

## 风险说明

- 这不是交易建议，也不改变 admission 结论。
- 归因使用日线持仓和日线基准权重，只解释已发生研究样本，不提供盘中择时能力。
- 如果策略本身不是指数增强策略，低沪深300覆盖不一定是错误；它只说明强指数行情下跟随基准上涨的能力不足。
- 日度归因行数：444；行业主动权重行数：30810。
