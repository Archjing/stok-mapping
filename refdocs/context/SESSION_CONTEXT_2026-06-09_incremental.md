# 2026-06-09 Session 增量知识归档

归档日期：2026-06-09
定位：在 `2026-06-04`、`2026-06-06`、`2026-06-08` 已有归档基础上，补充本次会话新增的策略研究、回测解读、窗口期方法论和参数漂移解释。
范围：保留股票、策略、回测、准入诊断相关解释性内容原文；代码修改、提交、运行产物和文件操作压缩摘要。

导航：[`refdocs 索引`](../README.md)

---

## 2026-06-09 增量归档：股票 / 策略解释类问答

> 来源 session：当前 Codex 会话上下文。
> 完整归档规则：命中解释、解读、回答、详解、是非判断、研判、考虑、计划、为什么、是什么、如何、怎么、哪个；以及策略验证报告解读、参数依据讨论、方法论总结。
> 其他内容：未命中原文归档规则的会话内容、项目开发文档更新内容已压缩摘要归档。
> 上次已归档时间戳：`2026-06-08`

### 👤 User / 用户
reports/strategy_admission_baseline_2y_1y_5fold_all_strategies_20260609/ 请先查看最新的输出报告，为我解释报告结果，分析

### 🤖 Assistant / 助手
**结论**
这份 `20260609` admission 报告的核心结论很明确：**11 个策略全部未通过准入。**
`quality_low_turnover_monthly_v1` 被标为 selected candidate，但它只是“本轮相对最不差”的候选，不是通过验收的策略。

**本次测试口径**
- 窗口：`2019-04-01 ~ 2026-03-31`
- preset：`baseline_2y_1y_5fold`
- 结构：2 年训练 + 1 年验证，共 5 折
- 策略数：11 个
- 股票池：point-in-time universe
- 准入门槛：
  - 年化收益 `> 0`
  - Sharpe `> 0.5`
  - 最大回撤 `> -0.25`
  - 正收益折比例 `>= 0.75`
  - 年化换手均值 `<= 3`
  - 年化换手最大值 `<= 5`
  - overfit risk 不高于 `medium`
  - 参数稳定
  - 行业集中度检查

**总体结果**
| 策略 | 年化均值 | Sharpe | 最差回撤 | 正收益折 | 年化换手 | 过拟合风险 | 结论 |
|---|---:|---:|---:|---:|---:|---|---|
| `quality_low_turnover_monthly_v1` | -3.18% | -0.27 | -16.21% | 2/5 | 1.78 | high | 相对最好，但未通过 |
| `low_vol_low_turnover_quality_v1` | -4.66% | -0.41 | -16.60% | 2/5 | 2.05 | high | 可复核，但未通过 |
| `legacy_momentum_low_turnover_v1` | -5.36% | -0.45 | -19.11% | 1/5 | 1.96 | high | 换手改善，但收益不行 |
| `quality_growth_price_v1` | -9.44% | -1.26 | -26.36% | 1/5 | 22.74 | critical | 失败 |
| `legacy_momentum` | -23.08% | -1.90 | -32.63% | 0/5 | 13.88 | critical | 失败 |
| `ma_kline_baseline_v1` | -43.50% | -3.60 | -46.46% | 0/5 | 43.86 | critical | 失败 |

**关键解释**
1. **没有任何策略年化收益为正**
所有策略 `annualized_return_mean` 都是负数。
这意味着在 2019-2026 这组 walk-forward 验证里，策略整体没有跑赢“现金不动”的基础要求。

2. **Sharpe 全部为负**
Sharpe 为负说明：承担波动后没有获得正收益补偿。
这不是“收益低但稳定”，而是“波动换来了亏损”。

3. **低换手方向明显改善了执行可行性**
三个低换手策略换手都达标：
- `quality_low_turnover_monthly_v1`: 1.78
- `legacy_momentum_low_turnover_v1`: 1.96
- `low_vol_low_turnover_quality_v1`: 2.05

这说明低换手改造有效降低交易频率和成本敏感性。
但它只解决了“少交易”，没有解决“赚不赚钱”。

4. **正收益折比例严重不足**
门槛是 `>= 0.75`，5 折里至少要 4 折为正。
实际最好也只有 2/5：
- `quality_low_turnover_monthly_v1`: 2/5
- `low_vol_low_turnover_quality_v1`: 2/5

这说明策略不是稳定失效到完全没希望，但远没到可准入状态。

5. **`quality_low_turnover_monthly_v1` 为什么被选中**
它不是因为通过验收，而是因为相对其他策略：
- 年化亏损最小：`-3.18%`
- Sharpe 最接近 0：`-0.27`
- 回撤较低：`-16.21%`
- 换手达标：`1.78`
- 财务 PIT 覆盖为 `1.0`
- 质量因子有一定 lift：`0.178`

所以它是“当前最值得复核的失败候选”，不是“可用策略”。

**重要异常/限制**
- `account_annualized_return_mean`、`account_sharpe_mean`、`account_executed_order_count_total` 全是 `0`。
  这说明本轮 admission 报告没有真正接入账户级执行仿真结果，不能用这份报告判断真实成交、整手、涨跌停、停牌、部分成交后的表现。

- 行业集中度字段也全是 `0`。
  这不应直接理解为“没有行业集中风险”，更可能是本轮行业暴露统计没有实际产出或未接入 admission 矩阵。

**策略层判断**
- 动量、K线、残差动量、主题动量方向目前表现很差，且换手过高，短期不应继续作为主线。
- 低换手质量方向是当前唯一还值得继续复核的方向。
- 但 `quality_low_turnover_monthly_v1` 也必须先解决两个问题：
  - 参数不稳定：5 折里有 4 套不同参数。
  - 收益不稳定：只有 2/5 折为正。

**建议下一步**
1. 不推进任何策略进入模拟实盘。
2. 优先复核 `quality_low_turnover_monthly_v1` 和 `low_vol_low_turnover_quality_v1`。
3. 给低换手质量策略做参数固定版测试，减少参数搜索空间。
4. 接入真实账户执行仿真，重新生成带 `account_*` 指标的报告。
5. 修复或确认行业暴露统计为什么为 0。
6. 对 2021-2023 亏损折单独做归因：市场风格、行业暴露、质量因子失效、股票池问题还是参数漂移。

### 👤 User / 用户
几个策略财务PIT覆盖率都是1.0吗

### 🤖 Assistant / 助手
不是。严格按这份 `20260609` 报告的数据看：

只有 `quality_low_turnover_monthly_v1` 的财务 PIT 覆盖率是 `1.0`。

其他 10 个策略在 `strategy_admission_window_matrix.csv` 里都是 `0.0`，在 `strategy_admission_candidate_folds.csv` 的逐折字段里是 `NaN`，最终汇总时被填成了 `0.0`。

具体：

| 策略 | financial PIT 覆盖 | selected financial PIT 覆盖 | 含义 |
|---|---:|---:|---|
| `quality_low_turnover_monthly_v1` | 1.0 | 1.0 | 财务 PIT 审计实际生效 |
| 其他 10 个策略 | 0.0 | 0.0 | 本轮没有财务 PIT 解释数据，不能理解为财务数据覆盖良好 |

逐折看，`quality_low_turnover_monthly_v1` 的 5 折都是：
- `financial_pit_announce_coverage = 1.0`
- `selected_financial_pit_announce_coverage = 1.0`
- `financial_field_coverage_mean = 1.0`
- `selected_financial_field_coverage_mean = 1.0`
- `financial_missing_blocked_ratio = 0.0`

所以我前面说“几个策略财务 PIT 覆盖率为 1.0”不严谨。准确表述应是：

> 本轮只有 `quality_low_turnover_monthly_v1` 产生了完整财务 PIT 诊断覆盖；其他策略没有产出财务 PIT 诊断，报告中汇总为 0.0，不代表它们财务数据真实覆盖率差，也不代表覆盖率好。

### 👤 User / 用户
报告里数据是否有异常，比如财务PIT覆盖率为0 会不会影响结果

### 🤖 Assistant / 助手
有异常，但分两类：

**1. 不影响本次准入结果的异常**
财务 PIT 覆盖率为 `0.0` 对多数策略**没有直接影响本次 reject 结果**。

原因看代码是这样：
- `strategy_admission` 的窗口准入只看：
  - `annualized_return_mean`
  - `sharpe_mean`
  - `max_drawdown_worst`
  - `positive_fold_ratio`
  - `turnover_annual_mean/max`
- 财务 PIT 覆盖率没有进入 `is_window_pass` 的 gate 计算。
- 也没有进入 `constraint_review` 的 reject 判断。

所以这些策略失败主要不是因为财务 PIT 为 0，而是因为：
- 年化收益为负
- Sharpe 为负
- 正收益折比例不足
- 换手过高
- 过拟合风险 high/critical
- 参数不稳定

**2. 报告语义上确实有异常**
财务 PIT 覆盖率为 `0.0` 对非财务策略不应该显示成“0 覆盖率”。

更准确应该区分：
- `1.0`：财务 PIT 诊断实际运行，覆盖完整
- `0.0`：诊断运行了但覆盖很差
- `N/A`：该策略不依赖财务因子，或本轮没有产出财务 PIT 诊断

现在报告把 `NaN` 汇总成 `0.0`，容易误导成“这些策略财务数据缺失”。这在语义上不对。

例如：
- `legacy_momentum`
- `ma_kline_baseline_v1`
- `theme_exposure_momentum_v1`

这些不是财务质量策略，财务 PIT 覆盖为 `0.0` 不应被当作数据质量失败。

**对结果有没有实质影响**
对本轮最终结论影响不大。
因为即使忽略财务 PIT 字段，所有策略仍然因为收益、Sharpe、正收益折比例、换手或过拟合失败。

但对“诊断报告可信度”有影响：
- 容易误读数据质量问题。
- 会让非财务策略看起来像财务数据缺失。
- 会让质量策略和非质量策略的诊断口径混在一起。

**真正需要关注的异常**
- `account_*` 全是 0：说明账户级执行仿真没有接入本轮 admission 结果。
- `top_industry_*` 全是 0：说明行业暴露统计没有实际生效或没有接入。
- 财务 PIT 非适用策略显示为 0：应该改成 `N/A`。
- 只有 `quality_low_turnover_monthly_v1` 有完整财务 PIT 诊断，这说明当前 quality diagnostics 可能只对这个策略实际接入。

**建议修复**
把报告逻辑改成：
- 对不依赖财务因子的策略，显示 `N/A`。
- 对依赖财务因子但没有诊断结果的策略，显示 `missing_diagnostic`。
- 对诊断结果真实为 0 的策略，才显示 `0.0`。
- 在 admission report 加一列：`uses_financial_factors`。

### 👤 User / 用户
现在选一个适用于低换手策略的回测窗口preset

### 🤖 Assistant / 助手
建议选：`quality_3y_1y_4fold`

理由：
- 低换手策略信号变化慢，不适合太短窗口。
- 如果策略含质量、低波、低换手、低估值等慢变量，`3 年训练 + 1 年验证` 比 `2 年 + 1 年` 更稳。
- 当前 `baseline_2y_1y_5fold` 已证明：低换手方向换手达标，但参数不稳定、收益折不稳定。下一步需要更长训练期来减少参数漂移。
- `4y/1y` 也可考虑，但样本折数会更少，当前阶段不如 `3y/1y` 平衡。

所以低换手策略当前优先用：

```bash
--preset-name quality_3y_1y_4fold
```

适用对象：
- `quality_low_turnover_monthly_v1`
- `low_vol_low_turnover_quality_v1`
- `legacy_momentum_low_turnover_v1`

不建议继续用 `baseline_2y_1y_5fold` 作为主结论窗口；它可以保留为公共 smoke/admission baseline。

### 👤 User / 用户
reports/strategy_admission_quality_4y_1y_all_strategies_20260609/ 解释

### 🤖 Assistant / 助手
**结论**
这次 `quality_4y_1y` 报告比上一份 `baseline_2y_1y_5fold` 明显更有信息量：**低换手策略方向在 4 年训练窗口下显著改善**，但仍然**没有通过 admission**。

本轮 selected candidate 是：

```text
low_vol_low_turnover_quality_v1
```

但它的状态是 `observe` / `reject`，不是准入通过。

**测试口径**
- preset：`quality_4y_1y`
- 策略集：`baseline_admission_all_v1`
- 策略数量：11 个
- 实际折数：3 折
- 注意：报告里 `walk_forward_start_date/end_date` 是空，说明这次 `quality_4y_1y` 没有固定起止日期，而是按默认历史窗口生成了 3 折。不是你前面说的固定 `2020-04-01 ~ 2026-03-31` 两折版本。

**核心排名**
| 策略 | 年化 | Sharpe | 最差回撤 | 正收益折 | 换手 | 结论 |
|---|---:|---:|---:|---:|---:|---|
| `quality_low_turnover_monthly_v1` | 12.11% | 1.03 | -21.15% | 2/3 | 1.84 | 表现好，但折数少/参数不稳 |
| `low_vol_low_turnover_quality_v1` | 12.03% | 1.05 | -17.52% | 2/3 | 1.88 | 本轮 selected candidate |
| `legacy_momentum_low_turnover_v1` | 11.47% | 0.58 | -17.29% | 1/3 | 2.55 | 收益改善但稳定性弱 |
| `core_selection_quality_momentum_v1` | -0.15% | -0.23 | -17.45% | 1/3 | 9.27 | 换手过高 |
| `quality_growth_price_v1` | -3.19% | -0.44 | -19.46% | 1/3 | 27.70 | 换手过高 |
| 其他动量/K线/残差策略 | 明显为负 | 明显为负 | 较大 | 不足 | 高 | 失败 |

**最重要变化**
和 `2y/1y/5fold` 相比，三个低换手策略明显改善：

- `quality_low_turnover_monthly_v1`
  - 从 `-3.18%` 年化变成 `+12.11%`
  - Sharpe 从 `-0.27` 变成 `1.03`
  - 换手仍低：`1.84`

- `low_vol_low_turnover_quality_v1`
  - 从 `-4.66%` 年化变成 `+12.03%`
  - Sharpe 从 `-0.41` 变成 `1.05`
  - 换手仍低：`1.88`

- `legacy_momentum_low_turnover_v1`
  - 从 `-5.36%` 年化变成 `+11.47%`
  - Sharpe 从 `-0.45` 变成 `0.58`
  - 换手仍达标：`2.55`

这说明一个重要事实：

> 低换手/质量/低波这类慢变量策略，对训练窗口长度非常敏感。`2y/1y` 可能训练不足，`4y/1y` 明显更适配。

**为什么仍然没有通过**
准入失败的主要原因不是收益、Sharpe、回撤、换手，而是：

1. **正收益折比例不足**
门槛是 `>= 75%`。
3 折时至少需要 3/3 为正才可能通过，实际最好只有 2/3。

2. **折数不足**
过拟合诊断提示：

```text
OOS fold count below governance floor
```

3 折太少，统计说服力不够。

3. **参数仍不稳定**
`low_vol_low_turnover_quality_v1` 和 `quality_low_turnover_monthly_v1` 都是 3 折 3 套参数。
这说明策略不是稳定选同一组规则，而是每折训练期都换了一套最优参数。

4. **账户执行仿真仍未接入**
报告里：
- `acct_ann = 0`
- `acct_sharpe = 0`
- `acct_orders = 0`

所以这份报告仍然不能回答“整手、涨跌停、停牌、真实撮合后是否还成立”。

**财务 PIT 诊断**
只有 `quality_low_turnover_monthly_v1` 财务 PIT 是完整的：
- `pit_ann = 1.00`
- `field_cov = 1.00`
- `selected_field_cov = 1.00`
- `failure_attribution = passed`

`low_vol_low_turnover_quality_v1` 虽然本轮 selected candidate，但财务 PIT 显示为 0，这仍然是报告语义问题或诊断未接入问题，需要修。

**策略含义**
`low_vol_low_turnover_quality_v1` 的交易特征大致是：
- 买低波动、低换手、质量较好的股票
- 持仓约 11 只
- 年化换手约 1.88
- 平均每年换不到 2 次完整组合
- 更像慢变量资产筛选，不是短线交易策略

`quality_low_turnover_monthly_v1` 很接近：
- 年化略高
- Sharpe 略低
- 回撤更大
- 财务 PIT 诊断更完整

所以目前不能简单说 selected candidate 一定优于 monthly quality。它们应并列进入下一轮复核。

**我的判断**
这份报告给出的信号是：

> 低换手质量/低波方向值得继续推进，但不能准入。
> 4y/1y 是更适合该策略族的窗口，但当前样本折数太少，必须用更严格的固定窗口、参数固定版和执行仿真复核。

**下一步建议**
1. 固定 `quality_4y_1y` 的 `start_date: 2020-04-01`、`end_date: 2026-03-31`、`expected_folds: 2` 后重新跑，确认窗口口径。
2. 对 `low_vol_low_turnover_quality_v1` 和 `quality_low_turnover_monthly_v1` 做参数固定版，不再每折自由调参。
3. 修复财务 PIT 诊断：`low_vol_low_turnover_quality_v1` 如果使用质量因子，应产出 PIT 覆盖，不应显示 0。
4. 接入账户执行仿真到 admission，生成真实 `acct_*` 指标。
5. 保留 `2y/1y/5fold` 作为公共 baseline，但低换手质量策略的主复核窗口应转向 `3y/1y` 和 `4y/1y`。

### 👤 User / 用户
"4y/1y 是更适合该策略族的窗口，但当前样本折数太少，必须用更严格的固定窗口、参数固定版和执行仿真复核。"，请展开论述

### 🤖 Assistant / 助手
这句话的意思是：

`4y/1y` 更符合低换手、质量、低波这类慢变量策略的信号周期，但单靠这一次 `4y/1y` 结果还不能认定策略有效，因为样本折数太少、参数还在漂移、执行层还没验证。

**1. 为什么 4y/1y 更适合低换手策略**
低换手策略通常不是靠短期价格形态取胜，而是靠慢变量：

- 公司质量
- 财务稳定性
- 低波动
- 低换手
- 估值或经营质量
- 中长期持有

这些信号变化慢。训练期太短会有两个问题：

- `2y` 训练期只有大约 8 个季度财报，质量因子样本偏少。
- 市场风格可能刚好偏向某类股票，参数容易被短期行情带偏。

`4y` 训练期大约覆盖 16 个季度，更适合学习慢变量关系。
所以这次 `4y/1y` 下低换手策略明显改善，是合理现象。

例如本轮：
- `low_vol_low_turnover_quality_v1` 年化约 `12.03%`，Sharpe `1.05`
- `quality_low_turnover_monthly_v1` 年化约 `12.11%`，Sharpe `1.03`
- 换手都在 `2` 以下

这说明低换手质量方向不是完全没信号，而是对窗口长度敏感。

**2. 为什么“样本折数太少”是大问题**
`4y/1y` 的代价是折数变少。

如果固定窗口为：

```text
2020-04-01 ~ 2026-03-31
```

那么最多只有 2 折：

```text
fold1: 2020-04-01 ~ 2024-03-31 训练，2024-04-01 ~ 2025-03-31 验证
fold2: 2021-04-01 ~ 2025-03-31 训练，2025-04-01 ~ 2026-03-31 验证
```

2 折太少的问题是：

- 只覆盖很少的市场状态。
- 如果 2 折都赚钱，也可能只是刚好碰到有利年份。
- 如果 1 折亏损，正收益折比例就只有 `50%`。
- 无法充分判断策略是否跨行情稳定。

所以 `4y/1y` 可以作为低换手策略的专用复核窗口，但不能单独作为最终准入证据。

**3. 为什么需要“更严格的固定窗口”**
前一次 `quality_4y_1y` 报告里，窗口起止日期没有固定，报告中 `start/end` 为空，实际生成了 3 折。

这会带来问题：

- 不容易复现。
- 不容易和其他报告比较。
- 不清楚样本期到底覆盖了哪些市场阶段。
- 后续结论可能因为默认历史长度变化而变化。

所以要固定：

```yaml
start_date: "2020-04-01"
end_date: "2026-03-31"
expected_folds: 2
```

这样每次跑出来的验证范围一致，才方便做归因和比较。

**4. 为什么需要“参数固定版”**
当前 walk-forward 是每一折训练期内重新选参数。

这对研究是必要的，但也容易过拟合。比如某策略每折都换参数：

```text
fold1 用一套质量阈值、波动窗口、调仓周期
fold2 换另一套
fold3 又换另一套
```

这说明策略可能不是“一个稳定逻辑有效”，而是“每段行情都临时找到一个事后最优参数”。

低换手质量策略如果真的有效，应该满足：

- 参数变化不大。
- 核心逻辑稳定。
- 不依赖精确调参。
- 调仓周期、持仓数量、质量阈值大致稳定。

所以需要做“参数固定版”：

- 先选择一组有经济含义的参数。
- 后续所有折都用同一组参数。
- 不在每折里重新搜索最优参数。
- 看收益是否仍然为正，Sharpe 是否还能接受。

如果固定参数后表现大幅变差，说明之前结果可能主要来自参数搜索，而不是策略逻辑。

**5. 为什么还要执行仿真复核**
当前 admission 报告里 `account_*` 指标为 0，说明账户级执行仿真没有真正接入这次报告：

```text
acct_ann = 0
acct_sharpe = 0
acct_orders = 0
```

所以现在看到的是策略层回测，不是完整账户执行结果。

真实可执行性还要考虑：

- A 股 100 股整手
- 现金是否够买
- 卖出回款
- 涨跌停不能成交
- 停牌不能成交
- 成交量参与率限制
- 滑点、佣金、印花税
- 低流动性股票的部分成交

低换手策略虽然交易少，但如果选出的股票流动性差，或者集中在涨停/停牌/低成交量股票上，真实结果仍可能比回测差。

**最终判断**
`4y/1y` 现在给出的信号是：

```text
低换手质量方向值得继续研究，但还不能准入。
```

下一步应按这个顺序做：

1. 用固定 `2020-04-01 ~ 2026-03-31` 的 `quality_4y_1y` 重新跑。
2. 对 `low_vol_low_turnover_quality_v1` 和 `quality_low_turnover_monthly_v1` 做参数固定版。
3. 修复 admission 中 `account_*` 执行仿真接入。
4. 修复财务 PIT / 行业暴露诊断的 N/A 与 0 混淆问题。
5. 再用 `3y/1y`、`4y/1y`、`2y/1y baseline` 三个窗口交叉判断。

### 👤 User / 用户
如果我把start date定的更早，比如2016年，拉长窗口期，这样折数变多，可以达到按下参数飘移，验证执行层的效果吗？这样与a股市场客观规律是否吻合？

### 🤖 Assistant / 助手
结论：**可以把 start date 提早到 2016，且这对低换手/质量策略是合理的；但它只能“增加证据”，不能自动解决参数漂移，也不能替代执行仿真。**

**1. 折数会明显增加**
如果设：

```yaml
start_date: "2016-04-01"
end_date: "2026-03-31"
train_years: 4
validate_years: 1
```

理论上可以得到 6 折：

```text
2016-04-01 ~ 2020-03-31 训练，2020-04-01 ~ 2021-03-31 验证
2017-04-01 ~ 2021-03-31 训练，2021-04-01 ~ 2022-03-31 验证
2018-04-01 ~ 2022-03-31 训练，2022-04-01 ~ 2023-03-31 验证
2019-04-01 ~ 2023-03-31 训练，2023-04-01 ~ 2024-03-31 验证
2020-04-01 ~ 2024-03-31 训练，2024-04-01 ~ 2025-03-31 验证
2021-04-01 ~ 2025-03-31 训练，2025-04-01 ~ 2026-03-31 验证
```

这比 `2020-04-01 ~ 2026-03-31` 的 2 折更有统计意义。

**2. 对参数漂移有帮助，但不能“自动压住”**
拉长训练期会降低短期噪声影响，参数通常会更稳一些。

但如果每折仍然自由搜索大量参数，参数仍可能漂移。
所以它只能帮助你观察参数漂移，不能自动消除参数漂移。

真正要压住参数漂移，需要同时做：

- 缩小参数网格。
- 增加参数稳定性惩罚。
- 跑固定参数版。
- 比较每折参数是否集中在同一组附近。
- 不允许每折都自由换一套完全不同的参数。

否则长窗口也可能只是“用更长历史找到另一套过拟合参数”。

**3. 对执行层验证有帮助，但前提是 admission 真接入执行仿真**
更早开始会带来更多交易样本，对验证这些问题有帮助：

- 整手限制
- 现金约束
- 卖出回款
- 涨跌停
- 停牌
- 流动性参与率
- 部分成交
- 交易成本

但当前报告里 `account_*` 仍是 0，说明 admission 还没有真正纳入账户执行仿真。
所以拉长窗口后，如果不修 execution gate 接入，仍然不能回答执行层是否可行。

**4. 与 A 股客观规律是否吻合**
总体吻合，但要注意制度变迁。

A 股 2016-2026 覆盖了多个重要市场阶段：

- 2016 年初有熔断机制冲击，随后熔断很快暂停，属于特殊波动阶段。
- 2018 年是明显熊市环境。
- 2019 年科创板推出并试点注册制，改变了部分股票供给和交易制度。上海证券交易所官方资料显示科创板和注册制试点在 2019 年启动。来源：SSE STAR Market。
  https://star.sse.com.cn/star/en/infodisclosure/newsrelease/c/c_20190711_4860948.shtml
- 2020 年创业板注册制改革推进。来源：中国政府网。
  https://english.www.gov.cn/statecouncil/ministries/202004/28/content_WS5ea78bd9c6d0b3f0e94968fc.html
- 2021 年北交所开市。来源：北京政府英文网。
  https://english.beijing.gov.cn/investinginbeijing/Investmentnews/202111/t20211115_2537027.html

所以，2016 起跑是合理的，因为它覆盖了多种市场状态。
但也不能把 2016-2018 和 2023-2026 当成完全同质市场。A 股制度、投资者结构、上市公司结构、退市规则、涨跌停规则、注册制影响都在变化。

**我的建议**
不要只用一个长窗口。采用“双层验证”：

1. **长期稳健性窗口**
```yaml
quality_4y_1y_2016_2026
```

用途：看策略是否跨周期有效、参数是否稳定、是否只吃最近行情。

2. **近期有效性窗口**
```yaml
quality_4y_1y_2020_2026
```

用途：看策略是否仍适用于当前 A 股制度和市场结构。

3. **固定参数版**
选择一组经济含义清晰的参数，不再每折自由搜索，用来判断策略逻辑本身是否有效。

结论：
把 start date 提到 2016 是合理的，而且应该做；但它应作为“长期稳健性测试”，不能单独作为最终准入。最终还要结合近期窗口、固定参数版和真实账户执行仿真。

### 👤 User / 用户
这里所说的参数和“参数飘移”，具体指什么？解释

### 🤖 Assistant / 助手
这里的“参数”，不是模型训练出来的神经网络权重，而是**策略规则里的可调旋钮**。

例如低换手质量策略里这些都是参数：

```text
质量分位阈值
波动率窗口
波动率分位阈值
换手率分位阈值
买入股票数量
继续持有股票数量
调仓周期
最短持有天数
单票最大权重
目标波动率
换手惩罚系数
```

拿 `quality_low_turnover_monthly_v1` 举例，报告里每折选出来的参数类似：

```text
fold1:
quality@q0.6, vol_window=20, vol_q=0.6, turnover_q=0.5,
top_n=10, hold_top=20, rebalance=20d, min_hold=20d

fold2:
quality@q0.7, vol_window=20, vol_q=0.6, turnover_q=0.5,
top_n=10, hold_top=20, rebalance=40d, min_hold=20d

fold3:
quality@q0.6, vol_window=60, vol_q=0.5, turnover_q=0.5,
top_n=20, hold_top=40, rebalance=40d, min_hold=20d
```

这说明策略每个训练窗口选出来的“最佳规则”不同。

**参数漂移是什么意思**
参数漂移就是：

> 同一个策略逻辑，在不同训练期里选出来的最佳参数不断变化，而且变化幅度较大。

比如：

```text
fold1 认为 20 日波动率最好
fold2 认为 60 日波动率最好
fold3 认为买 10 只最好
fold4 认为买 20 只最好
fold5 认为 20 天调仓最好
```

这就叫参数漂移。

**为什么它重要**
如果一个策略真的有稳定规律，参数不应该每段时间都大幅换。

可以有小幅变化，比如：

```text
quality_q 在 0.6 ~ 0.7 之间变化
top_n 在 10 ~ 20 之间变化
```

这还算正常。

但如果每折都换成完全不同组合，就说明可能不是策略逻辑稳定有效，而是程序在每个历史窗口里“挑到了当时最幸运的一组参数”。

这就是过拟合风险。

**直观比喻**
你在研究一个钓鱼方法。

稳定策略像这样：

```text
一直在深水区，用类似鱼饵，早晨或傍晚钓，长期都还行。
```

参数漂移严重像这样：

```text
2019 年用红色鱼饵最好；
2020 年用蓝色鱼饵最好；
2021 年必须中午钓；
2022 年必须夜里钓；
2023 年必须换到浅水区。
```

如果每年最佳方法都完全不一样，那你很难相信这是一套稳定规律。

**在本项目里怎么判断**
当前代码里过拟合诊断会看：

```text
parameter_unique_count
```

例如：
- 3 折里有 3 套不同参数：参数不稳定
- 5 折里有 4 套不同参数：参数不稳定
- 5 折里只有 1-2 套相近参数：较稳定

但这只是 MVP 版本，比较粗。
更好的判断应该不是只数“不同参数文本数量”，还应该看变化幅度：

```text
quality_q: 0.6 -> 0.7   小变化
rebalance: 20d -> 40d   中等变化
top_n: 10 -> 40         大变化
vol_window: 20 -> 120   大变化
```

**为什么长窗口可能减少参数漂移**
训练窗口越短，越容易被短期行情影响。

例如 2 年训练期：
- 可能只覆盖一轮成长股行情。
- 或只覆盖一段低波风格行情。
- 参数容易偏向当时最强的市场风格。

4 年训练期：
- 覆盖更多财报周期。
- 覆盖更多市场状态。
- 参数更可能选择长期有效的组合。

但注意：长窗口不能保证没有参数漂移。
如果策略本身不稳定，4 年窗口也会漂移。

**怎么处理参数漂移**
下一步应该做三件事：

1. **参数固定版**
选一组有业务含义的参数，所有折都用同一套，不再每折自由搜索。

例如：

```text
quality_q=0.6
vol_window=60
vol_q=0.5
turnover_q=0.5
top_n=20
hold_top=40
rebalance=40d
min_hold=20d
max_w=0.1
target_vol=0.18
turnover_penalty=0.02
```

2. **缩小参数搜索空间**
不要让程序在太多组合里乱挑。
只保留符合策略逻辑的少数几组。

3. **参数邻域测试**
如果最优参数附近的小变化也能赚钱，说明策略稳。
如果只有一个精确参数赚钱，旁边都亏，说明很可能过拟合。

**一句话总结**
这里的参数，就是策略规则里的可调配置；参数漂移，就是不同训练窗口选出来的最佳配置变化太大。
它反映的是：策略是否真的有稳定逻辑，还是只是在每段历史里临时找到了最幸运的组合。

---

## 其他会话内容压缩摘要

- 本轮先完成了策略报告导出模块的通用化重构：将原 `scripts/export_low_turnover_bill.py`、`scripts/export_low_turnover_oos_report.py`、`scripts/export_low_turnover_period_compare.py` 中的真实实现迁移为 `scripts/export_strategy_bill.py`、`scripts/export_strategy_oos_report.py`、`scripts/export_strategy_period_compare.py`；旧 `export_low_turnover*.py` 保留为兼容 wrapper。
- `phase0/cli.py`、`scripts/export_execution_effectiveness_report.py`、`scripts/export_premarket_watchlist.py` 已切换到新的 `export_strategy_*` 模块；文档 [docs/PROJECT_ARCHITECTURE_OVERVIEW.md](../../docs/PROJECT_ARCHITECTURE_OVERVIEW.md) 和 [docs/tasks/WEEKLY_EXECUTION_CHECKLIST.md](../../docs/tasks/WEEKLY_EXECUTION_CHECKLIST.md) 已更新脚本路径说明。
- 已提交并推送：`9b63ef7 Generalize strategy report exports`、`dfdea4f Rename strategy report exporters`。剩余未提交项主要是运行产物、日志、strategy admission 报告目录和 `config.yaml` 后续 preset 修改。
- 已为 `quality_4y_1y` preset 修改 [config.yaml](../../config.yaml)：新增 `start_date: "2020-04-01"`、`end_date: "2026-03-31"`、`expected_folds: 2`，并验证配置可正常读取。对应建议运行命令：`./.venv/bin/python -m phase0.cli strategy-admission --config config.yaml --presets quality_4y_1y --strategy-set baseline_admission_all_v1 --output-dir reports/strategy_admission_quality_4y_1y_20200401_20260331_all_strategies_20260609 --trace-run`。
- 本轮查看并解读了两个 strategy admission 输出目录：`reports/strategy_admission_baseline_2y_1y_5fold_all_strategies_20260609/` 与 `reports/strategy_admission_quality_4y_1y_all_strategies_20260609/`。前者 11 个策略全部未通过，低换手方向换手达标但收益/Sharpe 不足；后者显示低换手质量/低波方向在 4y/1y 窗口下显著改善，但仍因折数少、正收益折比例不足、参数不稳定和执行仿真未接入而不能准入。
- 明确发现 admission 报告语义问题：非财务策略财务 PIT 诊断缺失时被汇总为 `0.0`，应区分 `N/A`、`missing_diagnostic` 与真实 `0.0`；`account_*` 和行业集中度字段为 0 也提示执行仿真与行业暴露统计尚未有效接入 admission。
- 当前归档请求本身未纳入原文归档，留待下一次增量归档时处理。
