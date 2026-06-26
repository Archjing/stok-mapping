# 沪深300权重归因报告

本报告是 research-only 诊断，用来解释策略在强沪深300阶段跑输时，问题更接近仓位参与不足、高权重成分遗漏、行业结构偏离，还是持仓选择不足。

## 运行口径

- 生成时间：2026-06-26 02:03:47
- 基准：`SH.000300`
- 过滤市场状态：`all`
- 高权重成分检查范围：沪深300权重前 20
- 本地历史库：`/home/zj/workspace/stok-mapping/data/manual_history/a_share_history.sqlite`
- 持仓输入：`/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/holdings_exposure/strategy_daily_holdings.csv`
- 日度暴露输入：`/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/holdings_exposure/strategy_daily_exposure.csv`
- 候选折输入：`/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/admission/strategy_admission_candidate_folds.csv`
- 市场状态输入：`/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/market_context/strategy_market_context_diagnostic.csv`
- 权重日期保守滞后：`1` 天

权重使用规则：每个持仓日默认只使用 `cn_index_weights_asof.trade_date <= date - 1 day` 的最近一条记录；这是按日线研究归因的保守可见性口径。`asof_time` 仍是治理代理字段，不代表盘中真实发布时间。

## 折级结论

| strategy_id | walk_forward_preset | fold | days | avg_live_exposure | avg_benchmark_weight_held | avg_top_n_coverage_ratio | avg_industry_l1_gap_normalized | excess_total_return | primary_driver | plain_language_summary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| benchmark_core_alpha_overlay_v1 | baseline_2y_1y_5fold | 1 | 243 | 0.2110 | 0.6558 | 0.9826 | 0.3157 | 0.1254 | low_participation | 强沪深300阶段主要问题是仓位参与不足，策略没有充分吃到指数上涨。 |
| benchmark_core_alpha_overlay_v1 | baseline_2y_1y_5fold | 2 | 243 | 0.1494 | 0.6371 | 0.9957 | 0.3541 | 0.0334 | low_participation | 强沪深300阶段主要问题是仓位参与不足，策略没有充分吃到指数上涨。 |
| benchmark_core_alpha_overlay_v1 | baseline_2y_1y_5fold | 3 | 241 | 0.1494 | 0.6230 | 0.9959 | 0.3540 | 0.1158 | low_participation | 强沪深300阶段主要问题是仓位参与不足，策略没有充分吃到指数上涨。 |
| benchmark_core_alpha_overlay_v1 | baseline_2y_1y_5fold | 4 | 241 | 0.1490 | 0.6306 | 0.9959 | 0.3518 | -0.0779 | low_participation | 强沪深300阶段主要问题是仓位参与不足，策略没有充分吃到指数上涨。 |
| benchmark_core_alpha_overlay_v1 | baseline_2y_1y_5fold | 5 | 242 | 0.3486 | 0.6385 | 0.9959 | 0.3372 | -0.1064 | low_participation | 强沪深300阶段主要问题是仓位参与不足，策略没有充分吃到指数上涨。 |

## 最常遗漏的沪深300高权重成分

| strategy_id | fold | symbol | name | industry | missed_days | avg_benchmark_weight | avg_benchmark_rank |
| --- | --- | --- | --- | --- | --- | --- | --- |
| benchmark_core_alpha_overlay_v1 | 1 | SH.600519 | 贵州茅台 | 白酒 | 1 | 0.0531 | 1.0000 |
| benchmark_core_alpha_overlay_v1 | 1 | SH.601318 | 中国平安 | 保险 | 1 | 0.0448 | 2.0000 |
| benchmark_core_alpha_overlay_v1 | 1 | SZ.300750 | 宁德时代 | 电气设备 | 16 | 0.0361 | 2.0000 |
| benchmark_core_alpha_overlay_v1 | 1 | SH.600036 | 招商银行 | 银行 | 1 | 0.0333 | 3.0000 |
| benchmark_core_alpha_overlay_v1 | 1 | SZ.000858 | 五 粮 液 | 白酒 | 1 | 0.0273 | 4.0000 |
| benchmark_core_alpha_overlay_v1 | 1 | SZ.000333 | 美的集团 | 家用电器 | 1 | 0.0213 | 5.0000 |
| benchmark_core_alpha_overlay_v1 | 1 | SH.601166 | 兴业银行 | 银行 | 1 | 0.0184 | 6.0000 |
| benchmark_core_alpha_overlay_v1 | 1 | SH.600276 | 恒瑞医药 | 化学制药 | 1 | 0.0181 | 7.0000 |
| benchmark_core_alpha_overlay_v1 | 1 | SZ.000651 | 格力电器 | 家用电器 | 1 | 0.0159 | 8.0000 |
| benchmark_core_alpha_overlay_v1 | 1 | SH.601888 | 中国中免 | 旅游服务 | 1 | 0.0157 | 9.0000 |
| benchmark_core_alpha_overlay_v1 | 1 | SH.600887 | 伊利股份 | 乳制品 | 1 | 0.0128 | 10.0000 |
| benchmark_core_alpha_overlay_v1 | 1 | SH.601012 | 隆基绿能 | 电气设备 | 1 | 0.0122 | 11.0000 |
| benchmark_core_alpha_overlay_v1 | 1 | SH.600030 | 中信证券 | 证券 | 25 | 0.0113 | 12.2400 |
| benchmark_core_alpha_overlay_v1 | 1 | SH.600900 | 长江电力 | 水力发电 | 21 | 0.0113 | 13.9524 |
| benchmark_core_alpha_overlay_v1 | 1 | SZ.000001 | 平安银行 | 银行 | 1 | 0.0112 | 12.0000 |
| benchmark_core_alpha_overlay_v1 | 1 | SZ.002415 | 海康威视 | IT设备 | 1 | 0.0110 | 13.0000 |
| benchmark_core_alpha_overlay_v1 | 1 | SZ.000002 | 万 科Ａ | 全国地产 | 1 | 0.0107 | 14.0000 |
| benchmark_core_alpha_overlay_v1 | 1 | SH.600031 | 三一重工 | 工程机械 | 1 | 0.0106 | 16.0000 |
| benchmark_core_alpha_overlay_v1 | 1 | SH.601398 | 工商银行 | 银行 | 1 | 0.0102 | 18.0000 |
| benchmark_core_alpha_overlay_v1 | 1 | SZ.300059 | 东方财富 | 证券 | 1 | 0.0099 | 19.0000 |
| benchmark_core_alpha_overlay_v1 | 1 | SZ.002714 | 牧原股份 | 农业综合 | 1 | 0.0099 | 20.0000 |
| benchmark_core_alpha_overlay_v1 | 1 | SZ.300760 | 迈瑞医疗 | 医疗保健 | 1 | 0.0083 | 20.0000 |
| benchmark_core_alpha_overlay_v1 | 2 | SH.600519 | 贵州茅台 | 白酒 | 1 | 0.0568 | 1.0000 |
| benchmark_core_alpha_overlay_v1 | 2 | SZ.300750 | 宁德时代 | 电气设备 | 1 | 0.0377 | 2.0000 |
| benchmark_core_alpha_overlay_v1 | 2 | SH.600036 | 招商银行 | 银行 | 1 | 0.0305 | 3.0000 |
| benchmark_core_alpha_overlay_v1 | 2 | SH.601318 | 中国平安 | 保险 | 1 | 0.0276 | 4.0000 |
| benchmark_core_alpha_overlay_v1 | 2 | SH.601012 | 隆基绿能 | 电气设备 | 1 | 0.0164 | 5.0000 |
| benchmark_core_alpha_overlay_v1 | 2 | SZ.000858 | 五 粮 液 | 白酒 | 1 | 0.0158 | 6.0000 |
| benchmark_core_alpha_overlay_v1 | 2 | SH.601166 | 兴业银行 | 银行 | 1 | 0.0158 | 7.0000 |
| benchmark_core_alpha_overlay_v1 | 2 | SZ.000333 | 美的集团 | 家用电器 | 1 | 0.0147 | 8.0000 |

## 风险说明

- 这不是交易建议，也不改变 admission 结论。
- 归因使用日线持仓和日线基准权重，只解释已发生研究样本，不提供盘中择时能力。
- 如果策略本身不是指数增强策略，低沪深300覆盖不一定是错误；它只说明强指数行情下跟随基准上涨的能力不足。
- 日度归因行数：1210；行业主动权重行数：85201。
