# strong_market_benchmark_aware_core_v1 预注册规格

## 状态

- 迭代：I50
- 日期：2026-06-25
- 类型：research-only pre-registration
- 是否已实现：否
- 是否可交易：否

## 目标

构建强沪深300 / 强市场环境下的 benchmark-aware 核心参与候选，解决 I49 暴露的问题：

- `strong_market_stable_core_base_v1` 的强基准阶段平均仓位仍只有约 `39.18%`。
- 平均持有沪深300权重约 `22.33%`。
- Top20 覆盖约 `59.14%`。
- 行业 L1 偏离约 `1.1456`。

新候选的目标不是复制沪深300，而是在强市场中先保证核心权重参与，再保留有限主动增强。

## 输入数据

| 数据 | 口径 |
| ---- | ---- |
| 股票价格 | `qfq_asof` |
| 股票池 | PIT universe + research-only CSI300 core seed panel |
| 指数成分权重 | `cn_index_weights_asof.trade_date <= date - 1 day` |
| 指数行情 | 本地历史库，T-1 可见 |
| 行业 | fold-local PIT universe metadata |

## 市场状态

使用三档状态，不使用单一二元开关：

| 状态 | 说明 | 目标仓位 |
| ---- | ---- | ---: |
| `risk_pressure` | 指数弱趋势或明显回撤压力 | `0%` - `20%` |
| `mixed_or_neutral` | 不强不弱或信号不一致 | `35%` - `45%` |
| `strong_csi300` | 沪深300强趋势且风险压力可控 | `65%` - `75%` |

## 候选生成

1. 取 T-1 CSI300 core seed：
   - Top 80；
   - 或累计权重达到 `70%`。
2. 合并 PIT panel 与本地价格。
3. 基础硬过滤只处理数据与交易可行性。
4. 趋势、流动性、波动、行业相对强弱不再硬剔除核心权重股。

## 打分

```text
core_score =
  0.55 * benchmark_weight_rank
  + 0.15 * mom60_rank
  + 0.10 * mom20_rank
  + 0.10 * liquidity_rank
  + 0.05 * low_vol_rank
  + 0.05 * industry_relative_rank
```

## 权重构造

- `benchmark_aware_core_sleeve`：`75%` - `90%`
- `alpha_adjustment_sleeve`：`10%` - `25%`
- 单票上限：初始 `6%` - `8%`
- 行业主动偏离：强基准阶段 L1 目标 `<= 0.90`
- 如果 alpha sleeve 降低 Top20 覆盖或扩大行业偏离，应自动缩小 alpha sleeve。

## 验收指标

| 指标 | 最低要求 |
| ---- | ---: |
| 强基准阶段平均 live exposure | `>= 60%` |
| 强基准阶段持有沪深300权重 | `>= 35%` |
| 强基准阶段 Top20 覆盖率 | `>= 70%` |
| 强基准阶段 Top20 漏配权重 | `<= 8%` |
| 强基准阶段行业 L1 偏离 | `<= 0.90` |
| 年化换手均值 | `<= 3.0` |
| 年化换手最大值 | `<= 5.0` |
| 正超额折比例 | `>= 60%` |

最终是否进入下一阶段仍以 `strategy-admission` 为准。

## 必跑验证

I51 若实现，必须运行：

1. scoped admission；
2. holdings exposure；
3. CSI300 attribution；
4. failure attribution；
5. industry active weight review；
6. long-window stability check。

## 禁止解释

- 不能解释为指数复制策略。
- 不能解释为固定买沪深300前20只。
- 不能凭强基准阶段单折收益进入模拟或日报。
- 不能降低 admission gate。
