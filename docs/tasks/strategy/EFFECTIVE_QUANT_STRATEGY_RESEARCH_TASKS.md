# T2.5-T2.11｜有效量化策略研发任务清单

父级计划：[`DEVELOPMENT_PLAN.md`](../../DEVELOPMENT_PLAN.md)  
实施方案：[`EFFECTIVE_QUANT_STRATEGY_RESEARCH_PLAN_2026-06-04.md`](../../EFFECTIVE_QUANT_STRATEGY_RESEARCH_PLAN_2026-06-04.md)  
任务索引：[`docs/tasks/README.md`](../README.md)

---

## T2.5 因子有效性诊断报告

### T2.5.1 目标

- [x] 新增 `factor-effectiveness` 离线诊断命令
- [x] 在 `qfq_asof` / PIT 股票池口径下评估候选因子
- [x] 输出因子覆盖率、缺失率、Rank IC、ICIR、分组收益、年度稳定性、相关矩阵、因子换手
- [x] 生成“可进入策略组合 / 仅观察 / 淘汰”的因子分层结论

### T2.5.2 输入

- [x] `data/manual_history/a_share_history.sqlite`
- [x] `market_daily_bars` 的 `bfq/qfq` 日线
- [x] `market_adj_factors`
- [x] `market_daily_basic`
- [x] `market_financial_factors`
- [x] point-in-time universe
- [x] `config.yaml`

### T2.5.3 第一批因子

- [x] `vol20`
- [x] `vol60`
- [x] `turnover_rate`
- [x] `amount_ratio20`
- [x] `mom20`
- [x] `mom60`
- [x] `mom3`
- [x] `mom5`
- [x] `roe`
- [x] `cash_flow_quality`
- [x] `profit_growth`
- [x] `revenue_growth`
- [x] `debt_to_asset`
- [x] `pe / ep / pb`，若字段可得

### T2.5.4 输出

- [x] `reports/factor_effectiveness/factor_effectiveness.csv`
- [x] `reports/factor_effectiveness/factor_effectiveness.md`
- [x] `reports/factor_effectiveness/factor_group_returns.csv`
- [x] `reports/factor_effectiveness/factor_ic_by_year.csv`
- [x] `reports/factor_effectiveness/factor_correlation.csv`

### T2.5.5 验收

- [x] 所有价格特征默认使用 `qfq_asof`
- [x] 所有执行/流动性字段使用未复权含义
- [x] 财务字段必须保留公告日 point-in-time 说明
- [x] 报告能解释低波、低换手、质量、动量、反转各自是否有效
- [x] 因子缺失时报告明确标记，不静默填充为有效信号

---

## T2.6 `low_vol_low_turnover_quality_v1`

### T2.6.1 目标

- [x] 新增低波低换手质量三因子候选
- [x] 接入 `phase0/strategies/registry.py`
- [x] 加入 compare，但通过 gate 前不得进入模拟账户

### T2.6.2 初始评分

```text
score =
  0.40 * low_vol_rank
+ 0.25 * low_turnover_rank
+ 0.25 * quality_rank
+ 0.10 * medium_momentum_rank
```

### T2.6.3 参数范围

- [x] 调仓周期：`20 / 40` 个交易日
- [x] top_n：`10 / 20`
- [x] 低波窗口：`20 / 60`
- [x] 中期动量窗口：`20 / 60`
- [x] 单票权重上限：`10%`
- [ ] 年化换手目标：`<= 3`

### T2.6.4 验收

- [ ] `qfq_asof` 年化收益为正
- [ ] Sharpe `> 0.5`
- [ ] 最大回撤 `> -0.25`
- [ ] 正收益折比例 `>= 0.75`
- [ ] 年化换手 `<= 3`
- [ ] overfit risk 不高于 `medium`

### T2.6.5 行业约束复核

- [x] 新增通用策略修饰层模块，行业约束不写死在 T2.6 内部
- [x] 支持 `strategy_v2.constraints.industry.mode = audit/enforce`
- [x] 支持 `max_names_per_industry`
- [x] 支持 `max_industry_weight`
- [x] 支持 `unknown_industry_policy = allow/cap/reject`
- [x] 在 PIT universe 折内携带历史 `industry/name` 元数据
- [x] 在 candidate fold 和 strategy-admission 输出行业集中度复核指标
- [ ] 后续增加 `shadow` 模式，输出原策略与约束版并行对照候选

---

## T2.7 `quality_low_turnover_monthly_v1`

### T2.7.1 目标

- [x] 重做 `quality_growth_price_v1` 的低频质量版本
- [x] 质量因子作为核心 ranker，低波和低换手作为联合约束
- [x] 月频或 20 日以上调仓，避免财务慢变量被日频交易化

### T2.7.2 信号

- [x] ROE
- [x] 现金流质量
- [x] 利润增长
- [x] 营收增长
- [x] 低负债
- [x] 低波
- [x] 低换手

### T2.7.3 输出解释

- [x] 输出质量字段贡献拆解
- [x] 输出财务字段公告日 point-in-time 覆盖率
- [x] 输出缺失财务字段对候选池影响

### T2.7.4 验收

- [x] 年化换手 `<= 3`
- [x] 不依赖短线趋势过滤
- [x] 至少一个质量子因子在 T2.5 中有正向证据
- [x] 若失败，报告明确区分“质量因子无效”还是“组合构造无效”

---

## T2.8 策略准入报告

### T2.8.1 目标

- [x] 新增 `strategy-admission` 报告 MVP
- [ ] 合并 effectiveness gate、qfq_asof compare、factor diagnostic、overfit diagnostic
- [x] 加入 walk-forward 窗口稳健性矩阵，避免只因单一训练/验证窗口成立就进入模拟账户
- [x] 将 walk-forward 窗口配置模块化为 preset，保留当前 `baseline_2y_1y` 作为 baseline
- [x] 建立回测窗口期配置模块 V1，优先解决固定研究区间、期望折数和 T2.7 复测问题
- [x] 新增全局 admission 配置层：`strategy_sets`、`gate`、`diagnostics.suites`
- [x] 回测 / admission 启动时打印当前 preset 的自然语言说明，包含训练期、验证期、固定起止日期、预计折数和滚动方式
- [x] 准入报告区分真实数值、`not_enabled`、`not_available`、`not_applicable`，避免把未接入诊断误读为 `0`
- [x] 给出策略是否可进入观察池 / 模拟账户的明确结论

### T2.8.2 硬规则

- [x] 当前 admission 默认要求 `qfq_asof`，非 `qfq_asof` 价格口径阻断进入模拟审查
- [ ] 完整 `qfq_current` / `qfq_asof` 双口径矩阵：`qfq_current` 通过但 `qfq_asof` 失败时拒绝进入模拟账户
- [x] `overfit_risk_level in {high, critical}`：阻断进入模拟审查，进入 retest / reject
- [x] 年化换手 `> 3`：第一阶段拒绝作为主候选
- [x] 正收益折比例不足：拒绝或降级复核
- [x] 缺少必要因子诊断：阻断 `eligible_for_paper_review`，在 constraint review 中显式给出原因
- [x] 要求行业集中度检查但未接入或超限：阻断 `eligible_for_paper_review`
- [x] 仅在单一窗口 preset 下通过、但在同类策略推荐窗口下失效：仅 research-only
- [x] 选中参数在窗口内频繁切换：阻断进入模拟审查，进入 retest

### T2.8.3 输出

- [x] `reports/strategy_admission/strategy_admission_constraint_review.csv`
- [x] `reports/strategy_admission/strategy_admission_report.md`
- [x] `reports/strategy_admission/strategy_admission_window_matrix.csv`
- [x] `reports/strategy_admission/strategy_admission_candidate_folds.csv`
- [x] `strategy_admission_window_matrix.csv` 输出 `price_adjustment_status`、`account_execution_status`、`industry_diagnostic_status`、`financial_diagnostic_status`
- [x] `strategy_admission_constraint_review.csv` 输出行业诊断缺失、因子诊断缺失和价格口径失败计数
- [x] 每次 `compare` / `strategy-admission` 代码验证通过后，必须生成带日期、运行背景、命令口径、验证结果、候选结论和下一步动作的策略治理报告

### T2.8.4 Walk-forward preset 设计

- [x] `baseline_2y_1y`：2 年训练 + 1 年验证，作为当前候选统一可比口径
- [x] `quality_3y_1y`：3 年训练 + 1 年验证，作为 T2.6/T2.7 低频质量策略推荐稳健性窗口
- [x] `quality_4y_1y`：4 年训练 + 1 年验证，作为质量/低换手策略严格复核窗口
- [x] `baseline_2y_1y_5fold`：2 年训练 + 1 年验证，固定 `2019-04-01` 到 `2026-03-31`，作为所有策略第一道公共 baseline
- [x] `quality_3y_1y_4fold`：3 年训练 + 1 年验证，固定 `2019-04-01` 到 `2026-03-31`，作为低频质量/低估值策略专用窗口
- [ ] `momentum_1y_6m`：V2 候选，1 年训练 + 6 个月验证，用于中期动量、行业轮动和风险 overlay
- [ ] `short_horizon_6m_3m`：V2 候选，6 个月训练 + 3 个月验证，用于短线反转、K 线和技术形态
- [ ] `event_rolling_n_events`：V2 候选，按事件数滚动，用于 PEAD、公告、新闻和文本事件策略
- [ ] `ml_purged_walk_forward`：V2 候选，带 purge / embargo 的 ML 专用窗口

设计依据：

- A 股资产特征组合选择论文采用滚动 `10 年训练 + 1 年测试`。
- A 股 LASSO 定价因子研究采用滚动 `5 年` 时间窗口考察因子有效性时变。
- S&P 500 相对收益 ML 研究采用约 `1 年训练 + 10 日 gap + 1 个月测试`。
- StockMixer 窗口敏感性结论显示：窗口过短信息不足，窗口过长早期信息贡献下降且学习成本增加。

### T2.8.5 回测窗口期配置模块 V1（KISS 收缩版）

定位：不同策略的信号半衰期不同，不能用单一 `2y/1y` 节奏替代所有策略族的验证窗口。但 V1 不做完整策略族框架，只解决当前真实痛点：T2.7 因折数不足和窗口单一导致准入结论不够稳。`2y/1y/5fold` 先作为公共 smoke/admission baseline，`quality_3y_1y_4fold` 先作为低频质量复核窗口。

策略类型与窗口适配：

| 策略类型 | 是否适合 `2y/1y` | 更合适窗口 |
| --- | --- | --- |
| 低频质量 / 财务因子 | 勉强适合作为 baseline | `3y/1y` 或 `4y/1y` |
| 低波 / 低换手 / 低估值 | 适合 | `2y/1y` + `3y/1y` |
| 中期动量 | 适合 | `1y/6m`、`2y/6m`、`2y/1y` |
| 短线反转 / K 线 / 技术形态 | 不太适合 | `6m/3m`、`1y/3m` |
| 文本 / 新闻 / 情绪 | 不建议只用年份窗口 | 时间窗口 + 事件覆盖率 + 延迟审计 |
| 跨市场 overlay | 适合作为风险缩放验证 | `1y/6m` + regime split |
| 机器学习模型 | 适合作为外层 OOS | 内层 CV + purged walk-forward |

主要原因：

- 财务慢变量：财报季度更新，`2` 年只有约 `8` 个季度，训练样本偏少。
- 短线策略：`1` 年验证期太长，市场结构可能已变化，参数滞后。
- 事件策略：关键不是日历长度，而是事件数量、事件类型覆盖和信号延迟。
- 机器学习策略：普通 walk-forward 不够，还要防止标签泄漏、样本重叠和参数搜索泄漏。

V1 preset：

| Preset | 用途 |
| --- | --- |
| `baseline_2y_1y_5fold` | 通用 baseline，所有策略第一道公共 smoke/admission 口径 |
| `quality_3y_1y_4fold` | 财务质量、低估值、低频策略 |

V1 开发任务：

- [x] 扩展 preset schema：支持 `start_date` / `end_date`、`expected_folds`
- [x] 保持 `train_years` / `validate_years` 兼容，不破坏现有 `baseline_2y_1y`、`quality_3y_1y`、`quality_4y_1y`
- [x] 在 fold 生成逻辑中支持 preset 级固定 `start_date` / `end_date`
- [x] 输出 `expected_folds`、`actual_folds`、`window_start`、`window_end`、`fold_generation_warning`
- [x] 新增 `baseline_2y_1y_5fold` 与 `quality_3y_1y_4fold`
- [x] `strategy-admission` 支持 `walk_forward.admission.strategy_sets`、CLI `--strategy-set`、CLI `--strategies` 覆盖和 `diagnostics.suites` 报告说明
- [x] `strategy-admission` 启动阶段输出 preset 说明，避免运行前误解回测窗口
- [x] `strategy-admission` 报告可信化：账户执行、行业约束和财务 PIT 诊断均有状态字段
- [x] `quality_4y_1y` 固定 `2020-04-01` 到 `2026-03-31`，作为低频质量近期严格复核窗口
- [x] 用 T2.7 跑 `baseline_2y_1y_5fold` + `quality_3y_1y_4fold`，验证报告能区分折数不足、参数不稳定、收益不达标和组合构造失败
- [x] 下一日优先：先补 overfit “最后一折拉高”风险标记，再复测 `quality_low_turnover_monthly_v1` 的双 preset 准入报告

2026-06-10 复测结论：`quality_low_turnover_monthly_v1` 双 preset 准入报告已生成到 `reports/strategy_admission_t2_7_quality_low_turnover_dual_preset_20260610/`，最终 action 为 `reject`。主要证据不是“最后一折转好所以失败”，而是正收益折比例不足、均值收益和 Sharpe 未达标、参数频繁变化、行业集中度超审计阈值；“最后一折拉高”作为 regime 依赖风险标记，用于提示结论可能过度依赖最近行情阶段。

V1 不做：

- [ ] 不支持 `train_months` / `validate_months`
- [ ] 不实现 `momentum_1y_6m`、`short_horizon_6m_3m`
- [ ] 不实现完整事件驱动回测或事件窗口占位
- [ ] 不实现 ML 内层 CV / purged splitter 或 ML 窗口占位
- [ ] 不做 `validation_family`、`strategy_window_policy`、自动策略族 preset 选择或 `family_pass`

V2 候选：

- [ ] `momentum_1y_6m`：中期动量、行业轮动
- [ ] `short_horizon_6m_3m`：短线反转、K 线形态
- [ ] `event_rolling_n_events`：PEAD、公告、新闻事件
- [ ] `ml_purged_walk_forward`：机器学习模型

---

## T2.9 策略失败归因诊断模块 V1

### T2.9.1 目标

`strategy-admission` 已能回答“是否准入”，但研发阶段还需要回答“为什么失败、应该优先改什么”。T2.9 的目标是在不重新回测的前提下，读取已有 admission / overfit / window matrix / fold 明细产物，把 `reject`、`retest` 或 `research_only` 结论拆解成可行动的失败归因。

### T2.9.2 输入

- [x] `strategy_admission_candidate_folds.csv`
- [x] `strategy_admission_window_matrix.csv`
- [x] `strategy_admission_constraint_review.csv`
- [x] `overfit_diagnostic/strategy_overfit_diagnostic.csv`
- [x] 可选：策略配置中的 gate、preset、industry constraint 和 diagnostics suites

### T2.9.3 输出

- [x] `strategy_failure_attribution.csv`
- [x] `strategy_failure_attribution.md`
- [x] 每个 `strategy_id + preset` 一行窗口级归因
- [x] 每个策略一段自然语言研发建议：继续优化、重构、降级 research-only 或当前 spec reject

### T2.9.4 V1 归因维度

- [x] `return_failure`：年化收益、Sharpe、最大回撤、正收益折比例未达 gate
- [x] `execution_failure`：换手、交易次数、持仓数、账户执行成本暴露异常
- [x] `construction_failure`：行业集中度、持仓过少、股票池过窄或组合构造导致暴露失衡
- [x] `factor_failure`：财务 PIT / 字段覆盖可用但质量暴露没有转化为收益
- [x] `parameter_failure`：不同折选出的参数组合频繁变化
- [x] `regime_failure`：最后一折显著拉高、不同市场阶段表现断裂
- [x] `data_failure`：价格口径、财务诊断、行业诊断或其他必要诊断缺失

### T2.9.5 开发任务

- [x] 新增只读归因函数，输入已有 CSV，不重新调用回测
- [x] 复用 admission gate 阈值，不在 T2.9 另造一套准入标准
- [x] 为每条归因输出 `severity`、`evidence`、`recommended_next_action`
- [x] 在 Markdown 报告中按策略输出“主要失败原因 -> 证据 -> 下一步建议”
- [x] 用当前 T2.7 双 preset 报告做最小验收样例

### T2.9.6 验收

- [x] 能解释 `quality_low_turnover_monthly_v1` 为什么不是单纯因为最后一折转好而失败
- [x] 能区分收益不达标、参数不稳、行业集中、构造失效和 regime 依赖
- [x] 输出结果可直接指导下一轮策略改造，而不是只重复 admission 的 pass/fail
- [x] 不引入新的回测耗时，不修改已有 admission 产物

### T2.9.7 不做

- [ ] 不做自动调参
- [ ] 不自动重写策略权重
- [ ] 不把失败归因直接转成交易信号
- [ ] 不在 V1 中做复杂 SHAP / ML explainability

---

## T2.10 sleeve 组合与二阶段 rerank

### T2.10.1 sleeve 组合

- [x] 将 `legacy_momentum_low_turnover_v1` 降级为动量 sleeve
- [x] 新增 defensive quality sleeve
- [x] 新增 risk overlay sleeve
- [x] 支持组合打分：

```text
final_score =
  0.55 * defensive_quality_score
+ 0.25 * low_turnover_momentum_score
+ 0.20 * risk_overlay_score
```

实现状态：`sleeve_composite_v1` 已作为 research-only / compare / admission 候选接入，输出三段 sleeve 分数、`final_score`、排名、权重和降级原因；不进入模拟账户或日报主线。

### T2.10.2 二阶段 ML rerank

启动条件：

- [ ] T2.5 找到至少 5 个稳定候选因子
- [x] T2.6 或 T2.7 至少一个线性 baseline 可跑通
- [x] T2.8 策略准入报告可用

候选模型：

- [ ] Logistic / SVM
- [ ] XGBoost
- [ ] Lasso / Elastic Net

禁止：

- [ ] 不用 ML 直接生成交易信号
- [ ] 不用 LLM 直接决定买卖
- [ ] 未解释模型不得进入模拟账户

---

## T2.11 PEAD / 文本 / 跨市场增强

### T2.11.1 PEAD

- [ ] 设计盈利超预期 / ROE 改善 / 公告后漂移因子
- [ ] 确认公告日 point-in-time 数据可用
- [ ] 先作为增强因子，不作为主 ranker

### T2.11.2 文本因子

- [ ] 依赖 `T1.3` 文本事件数据层先完成 provider probe、去重、as-of 口径和覆盖率诊断
- [ ] 分析师文本或财报摘要只做解释因子
- [ ] 新闻、公告、研报、政策和快讯统一从文本事件表读取，不直接散抓网页进入因子实验
- [ ] 输出文本信号覆盖率和滞后性说明
- [ ] 输出文本事件来源分布、重复率、抓取延迟和股票映射覆盖率
- [ ] 先服务 PEAD 解释、关注个股事件时间线和日报风险提示
- [ ] 不直接生成交易动作

### T2.11.3 跨市场 overlay

- [ ] 保留为风险缩放、隔夜情绪解释、开盘情景推演
- [ ] 不恢复为主选股 ranker

---

## 近期执行顺序

1. [x] T2.5 因子有效性诊断报告
2. [x] T2.6 `low_vol_low_turnover_quality_v1`
3. [x] T2.7 `quality_low_turnover_monthly_v1`
4. [ ] T2.8 策略准入报告与策略回测窗口期配置模块 V1
5. [ ] T2.9 策略失败归因诊断模块 V1
6. [ ] T2.10 sleeve 组合与二阶段 rerank
7. [ ] T2.11 PEAD / 文本 / 跨市场增强
