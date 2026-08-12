# 有效量化策略研发实施方案

生成日期：2026-06-04

参考资料：

- `refdocs/context/SESSION_CONTEXT_2026-06-04.md`
- `docs/STRATEGY_POOL_REVIEW_2026-06-03.md`
- `refdocs/papers/cn/A股有效量化策略报告.md`
- `refdocs/papers/cn/cn_INDEX.md`
- `refdocs/papers/cn/markdown/cn03_svm_multifactor_hs300.md`
- `refdocs/papers/cn/markdown/cn05_ml_asset_characteristics_portfolio.md`
- `refdocs/papers/cn/markdown/cn07_lasso_pricing_factors_china.md`
- `refdocs/papers/cn/markdown/cn09_svm_price_volume_cs1000.md`
- `refdocs/papers/en/quant-strategy-papers-2024-2026-index.md`
- `reports/qfq_asof_candidate_compare/qfq_asof_latest_candidate_compare_conclusion.md`

导航：[`docs 索引`](./README.md) · [`refdocs 索引`](../refdocs/README.md)

---

## 1. 当前基线结论

`qfq_asof` 最新候选策略池 compare 已经改变项目基线：

- 当前没有可用于实盘模拟的有效 candidate。
- 旧 selected candidate `legacy_momentum_low_turnover_v1` 在严格 `qfq_asof` 口径下折均年化为 `-7.51%`，Sharpe 为 `-0.730`，正收益折数为 `0/4`。
- 旧 `qfq_current` 结果只能作为兼容口径参考，不能作为严格 point-in-time 结论。
- 下一步不是继续调已有动量、K 线、量价过滤候选，而是重建“因子有效性诊断 -> 低频低换手多因子策略 -> 过拟合准入”的研发链路。

---

## 2. 文献转化为工程原则

### 2.1 A 股有效因子优先级

`A股有效量化策略报告.md` 与中文文献共同支持以下优先级：

1. 低波 / 低 Beta：作为核心防御因子，而不是只做风控缩仓。
2. 低换手：A 股中稳定性强，应作为独立 alpha 和成本约束。
3. 高质量：ROE、现金流质量、低杠杆、盈利稳定性，适合低频调仓。
4. 中期动量 + 短期反转：只作为确认或过滤，不再做主 ranker。
5. 公告事件 / PEAD：作为后续低频增强，不直接进入第一阶段主线。

### 2.2 机器学习使用边界

`cn03`、`cn05`、`cn07`、`cn09` 和英文 MASTER / StockMixer 相关文献给出的工程启发是：

- 先做 IC、ICIR、分组收益、相关性和因子冗余诊断，再做模型。
- SVM / XGBoost / MLP 只做二阶段 rerank，不直接替代可解释多因子主线。
- 高维模型必须和线性打分 baseline 对照，且默认不能绕过过拟合诊断。
- 因子共线性、数据挖掘和参数稳定性是策略准入问题，不是报告附录问题。

---

## 3. 研发总路线

```text
T2.5 因子有效性诊断
  -> T2.6 low_vol_low_turnover_quality_v1
  -> T2.7 quality_low_turnover_monthly_v1
  -> T2.8 strategy admission gate 升级
  -> T2.9 sleeve 组合与二阶段 ML rerank
  -> T2.10 PEAD / 文本 / 跨市场 overlay 增强
```

核心原则：

- `qfq_asof` 是研究价格默认可信口径。
- 股票池必须 point-in-time。
- 执行、估值、涨跌停和停牌判断必须使用 `bfq_raw`。
- 年化换手 `<= 3` 是第一阶段硬约束。
- 新策略未通过 gate、overfit diagnostic 和 qfq_asof compare 前，不进入实盘模拟。

---

## 4. 阶段方案

### 4.1 P0：因子有效性诊断

目标：先回答“哪些因子在当前数据、股票池、成本和 qfq_asof 口径下真的有效”。

第一批诊断因子：

| 因子组 | 字段 / 构造 | 方向 |
| --- | --- | --- |
| 低波 | `vol20`、`vol60`、可选 `ivol` | 越低越好 |
| 低换手 | `turnover_rate`、`amount_ratio20`、换手稳定性 | 越低越好 |
| 质量 | `roe`、`cash_flow_quality`、`profit_growth`、`revenue_growth`、`debt_to_asset` | 高 ROE / 高现金流 / 低负债 |
| 动量 | `mom20`、`mom60` | 越高越好 |
| 反转 | `mom3`、`mom5` | 近期过热越低越好 |
| 估值 | `pe`、`pb`、`ep`，若字段可得 | 低估值或高 EP |

输出：

- `reports/factor_effectiveness/factor_effectiveness.csv`
- `reports/factor_effectiveness/factor_effectiveness.md`
- `reports/factor_effectiveness/factor_group_returns.csv`
- `reports/factor_effectiveness/factor_ic_by_year.csv`
- `reports/factor_effectiveness/factor_correlation.csv`

验收：

- 能按 qfq_asof / point-in-time universe 生成诊断。
- 至少输出 Rank IC、ICIR、分组收益、年度稳定性、覆盖率、缺失率、相关矩阵、因子换手。
- 明确标出推荐进入策略组合的因子、仅观察因子、淘汰因子。

### 4.2 P1：`low_vol_low_turnover_quality_v1`

目标：构造下一轮核心候选，不再以动量为主 ranker。

初始打分：

```text
score =
  0.40 * low_vol_rank
+ 0.25 * low_turnover_rank
+ 0.25 * quality_rank
+ 0.10 * medium_momentum_rank
```

组合约束：

- 调仓周期：20 个交易日 / 月频。
- top_n：`10 / 20`。
- 年化换手目标：`<= 3`。
- 单票权重上限：`10%`。
- 行业权重上限：沿用 universe 行业上限或新增策略内上限。
- 流动性：沿用 `amount` / `min_amount` 过滤。
- 风险过滤：高波动、高换手、ST、退市风险、新股不足样本全部排除。

验收：

- `qfq_asof` 口径年化收益为正。
- Sharpe `> 0.5`。
- 最大回撤 `> -0.25`。
- 正收益折比例 `>= 0.75`。
- 年化换手 `<= 3`。
- overfit risk 不高于 `medium`。

### 4.3 P1：`quality_low_turnover_monthly_v1`

目标：重做当前失败的 `quality_growth_price_v1`，保留质量方向，降低交易化程度。

核心变化：

- 月频调仓。
- 质量因子先横截面排名，不叠强短线趋势过滤。
- 叠加低波和低换手。
- 财务因子必须按公告日 point-in-time。
- 输出质量字段贡献拆解。

验收：

- 能解释 ROE、现金流质量、利润增长、营收增长、低杠杆各自贡献。
- 年化换手 `<= 3`。
- 不因为单一财务字段缺失导致策略整体失效。

### 4.4 P1：策略准入 gate 升级

目标：把 `qfq_asof`、因子诊断和过拟合诊断纳入策略准入。

新增硬规则：

- `qfq_current` 通过但 `qfq_asof` 失败：不能进入实盘模拟。
- `overfit_risk_level in {high, critical}`：不能进入实盘模拟。
- 年化换手 `> 3`：第一阶段不得作为主候选。
- 正收益折数不足：不得靠最后一折 OOS 拉高结论。
- 缺少因子诊断或 PTI 说明：只允许 research-only。

输出：

- `reports/strategy_admission_report.md`
- `reports/strategy_admission_report.csv`

### 4.5 P2：sleeve 组合

目标：把旧动量候选降级为组件，而不是彻底丢弃。

候选组合：

```text
final_score =
  0.55 * defensive_quality_score
+ 0.25 * low_turnover_momentum_score
+ 0.20 * risk_overlay_score
```

其中：

- `defensive_quality_score` 来自低波、低换手、质量。
- `low_turnover_momentum_score` 保留旧低换手动量的确认能力。
- `risk_overlay_score` 只做缩放或风险提示，不做主 ranker。

### 4.6 P2：二阶段 ML rerank

启动条件：

- P0 因子诊断确认至少 5 个稳定候选因子。
- 线性多因子 baseline 已跑通。
- 过拟合诊断链路可用。

第一批模型：

- Logistic / SVM：上涨概率或收益分位分类。
- XGBoost：非线性 rerank。
- Lasso / Elastic Net：因子稀疏化与冗余筛选。

禁止事项：

- 不用 ML 直接生成交易信号。
- 不用 LLM 直接决定买卖。
- 不用未解释、未过拟合诊断的模型进入模拟账户。

### 4.7 P3：PEAD / 文本 / 跨市场增强

目标：在主策略稳定后，再引入增强因子。

优先顺序：

1. PEAD：盈利超预期、ROE 改善、公告后 15-60 天漂移。
2. 分析师 / 财报文本情绪：仅做因子或观察理由。
3. 跨市场 overlay：只做风险缩放、情绪解释和开盘情景推演。

---

## 5. 决策规则

### 5.1 策略保留

策略满足以下条件才可保留为 candidate：

- qfq_asof 年化收益为正。
- Sharpe `> 0.5`。
- 最大回撤 `> -0.25`。
- 正收益折比例 `>= 0.75`。
- 年化换手 `<= 3`。
- 样本外和参数邻域不过度依赖单折或单参数。

### 5.2 策略进入实盘模拟

策略必须额外满足：

- overfit risk 不高于 `medium`。
- 因子诊断报告支持核心 alpha。
- 执行价格为 `bfq_raw`。
- 账单 / 资产轨迹 / 阻断原因可导出。
- 当前策略说明文档已更新。

### 5.3 策略淘汰

满足任一条件则淘汰当前版本：

- qfq_asof 下 4 折全部负收益。
- 年化换手远高于 3 且收益不显著。
- 只在 qfq_current 下有效。
- 成本压力稍增即转负。
- 因子诊断显示核心因子无 IC 或分组收益倒挂。

---

## 6. 近期执行顺序

1. 实现 `factor-effectiveness` 报告 CLI。
2. 用当前 PIT 股票池和 qfq_asof 跑第一批因子诊断。
3. 按诊断结果实现 `low_vol_low_turnover_quality_v1`。
4. 实现 `quality_low_turnover_monthly_v1`。
5. 将 `qfq_asof` compare、overfit diagnostic、factor diagnostic 合并到 `strategy-admission` 报告。
6. 若仍无候选通过，再进入 sleeve 组合和 ML rerank。

---

## 7. 当前暂不推进

- 不继续优化 `ma_kline_baseline_v1`。
- 不继续独立优化高换手 residual reversal。
- 不把 `multifactor_volume_price_filter_v1` 当前版本加更多过滤救火。
- 不把 LLM / Transformer / RL 作为下一步主策略。
- 不恢复任何 `qfq_current` 单口径策略为实盘模拟候选。
