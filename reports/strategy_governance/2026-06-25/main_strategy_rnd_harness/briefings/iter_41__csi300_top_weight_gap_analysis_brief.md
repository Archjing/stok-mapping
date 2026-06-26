# Harness Iteration Brief - 2026-06-25 - I41 CSI300 Top 权重缺口分析

## 一句话结论

I40 没过完整 Top20 `35%` 门槛，主要不是因为成交、价格或行业字段过滤，而是少数沪深300高权重成分没有进入当前 PIT panel。这个问题需要单独做数据覆盖治理，但不推翻“强市场核心权重大体可达”的判断。

## 缺口在哪里

I40 的不可达原因全部是：

```text
missing_from_pit_panel
```

没有出现大面积：

- `invalid_price`
- `amount_below_min`
- `amount_ratio20_below_min`
- `missing_industry`

说明基础交易数据过滤不是主瓶颈。

## 经常缺失的核心成分

| 股票 | 缺失天数 | 涉及折数 | 平均排名 | 最高进入排名 | 平均权重 | 说明 |
| ---- | -------: | -------: | -------: | -----------: | -------: | ---- |
| `SH.601816` | 1150 | 5 | 36.33 | 19 | 0.63% | 长期缺失，中等偏高权重 |
| `SH.601328` | 727 | 3 | 27.76 | 14 | 0.73% | 部分时期进入 Top20 |
| `SH.600000` | 967 | 4 | 47.70 | 25 | 0.53% | 长期缺失 |
| `SH.600016` | 1008 | 5 | 51.34 | 34 | 0.49% | 长期缺失 |
| `SH.600837` | 930 | 4 | 50.28 | 35 | 0.50% | 长期缺失 |

Top20 缺口主要来自：

| 股票 | Top20 缺失天数 | 涉及折数 | 平均排名 | 平均权重 |
| ---- | -------------: | -------: | -------: | -------: |
| `SH.601328` | 120 | 1 | 17.95 | 0.92% |
| `SH.601816` | 39 | 2 | 19.56 | 0.87% |
| `SH.600900` | 11 | 2 | 13.00 | 1.18% |
| `SH.600919` | 15 | 1 | 20.00 | 0.82% |
| `SH.600030` | 6 | 1 | 15.00 | 1.02% |

## 这意味着什么

I40 的核心结论应拆成两句话：

1. 本地 PIT panel 已经能覆盖大部分沪深300核心权重，五折平均可达核心权重约 `53%` 到 `58%`。
2. 当前 PIT panel 仍漏掉少数高权重成分，使完整 Top20 可达权重停在约 `31%` 到 `34%`，略低于 I39 的 `35%` 门槛。

所以，下一步有两个并行方向：

| 方向 | 目的 | 优先级 |
| ---- | ---- | ------ |
| 数据覆盖治理 | 查清为什么上述高权重成分没进入 PIT panel，是否因 universe 上限、停牌、历史数据缺失、上市状态或代码映射问题 | 高 |
| 策略过滤重构 | 在可达核心池上，把 alpha 从硬过滤改成排序，避免把约 `55%` 的可达核心权重砍到约 `9%` | 高 |

## 下一步建议

I42 应先做一个很窄的数据覆盖追踪：

```text
CSI300 missing core member audit
```

只查 Top 缺失股票为什么没有进入 PIT panel，不碰策略收益、不调参数。

如果这些股票因为 universe 构造规则被排除，要把原因写清楚：

- 行业上限；
- 市值 / 流动性排序；
- PE / PB / daily_basic 缺失；
- 股票历史数据缺口；
- 代码规范化或交易所前缀问题；
- 当期确实不可交易。

## 原始证据

| 类型 | 路径 |
| ---- | ---- |
| I40 failure reasons | `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_40__csi300_core_reachability_diagnostic/core_reachability/strategy_core_reachability_failure_reasons.csv` |
| I40 daily diagnostic | `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_40__csi300_core_reachability_diagnostic/core_reachability/strategy_core_reachability_daily.csv` |
