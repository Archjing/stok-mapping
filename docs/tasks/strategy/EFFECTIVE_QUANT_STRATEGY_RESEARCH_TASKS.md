# T2.5-T2.10｜有效量化策略研发任务清单

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

- [ ] 新增低波低换手质量三因子候选
- [ ] 接入 `phase0/strategies/registry.py`
- [ ] 加入 compare，但通过 gate 前不得进入模拟账户

### T2.6.2 初始评分

```text
score =
  0.40 * low_vol_rank
+ 0.25 * low_turnover_rank
+ 0.25 * quality_rank
+ 0.10 * medium_momentum_rank
```

### T2.6.3 参数范围

- [ ] 调仓周期：`20 / 40` 个交易日
- [ ] top_n：`10 / 20`
- [ ] 低波窗口：`20 / 60`
- [ ] 中期动量窗口：`20 / 60`
- [ ] 单票权重上限：`10%`
- [ ] 年化换手目标：`<= 3`

### T2.6.4 验收

- [ ] `qfq_asof` 年化收益为正
- [ ] Sharpe `> 0.5`
- [ ] 最大回撤 `> -0.25`
- [ ] 正收益折比例 `>= 0.75`
- [ ] 年化换手 `<= 3`
- [ ] overfit risk 不高于 `medium`

---

## T2.7 `quality_low_turnover_monthly_v1`

### T2.7.1 目标

- [ ] 重做 `quality_growth_price_v1` 的低频质量版本
- [ ] 质量因子作为核心 ranker，低波和低换手作为联合约束
- [ ] 月频或 20 日以上调仓，避免财务慢变量被日频交易化

### T2.7.2 信号

- [ ] ROE
- [ ] 现金流质量
- [ ] 利润增长
- [ ] 营收增长
- [ ] 低负债
- [ ] 低波
- [ ] 低换手

### T2.7.3 输出解释

- [ ] 输出质量字段贡献拆解
- [ ] 输出财务字段公告日 point-in-time 覆盖率
- [ ] 输出缺失财务字段对候选池影响

### T2.7.4 验收

- [ ] 年化换手 `<= 3`
- [ ] 不依赖短线趋势过滤
- [ ] 至少一个质量子因子在 T2.5 中有正向证据
- [ ] 若失败，报告明确区分“质量因子无效”还是“组合构造无效”

---

## T2.8 策略准入报告

### T2.8.1 目标

- [x] 新增 `strategy-admission` 报告 MVP
- [ ] 合并 effectiveness gate、qfq_asof compare、factor diagnostic、overfit diagnostic
- [x] 加入 walk-forward 窗口稳健性矩阵，避免只因单一训练/验证窗口成立就进入模拟账户
- [x] 将 walk-forward 窗口配置模块化为 preset，保留当前 `baseline_2y_1y` 作为 baseline
- [x] 给出策略是否可进入观察池 / 模拟账户的明确结论

### T2.8.2 硬规则

- [ ] `qfq_current` 通过但 `qfq_asof` 失败：拒绝进入模拟账户
- [x] `overfit_risk_level in {high, critical}`：阻断进入模拟审查，进入 retest / reject
- [x] 年化换手 `> 3`：第一阶段拒绝作为主候选
- [x] 正收益折比例不足：拒绝或降级复核
- [ ] 缺少因子诊断：仅 research-only
- [x] 仅在单一窗口 preset 下通过、但在同类策略推荐窗口下失效：仅 research-only
- [x] 选中参数在窗口内频繁切换：阻断进入模拟审查，进入 retest

### T2.8.3 输出

- [x] `reports/strategy_admission/strategy_admission_constraint_review.csv`
- [x] `reports/strategy_admission/strategy_admission_report.md`
- [x] `reports/strategy_admission/strategy_admission_window_matrix.csv`
- [x] `reports/strategy_admission/strategy_admission_candidate_folds.csv`

### T2.8.4 Walk-forward preset 设计

- [x] `baseline_2y_1y`：2 年训练 + 1 年验证，作为当前候选统一可比口径
- [x] `quality_3y_1y`：3 年训练 + 1 年验证，作为 T2.6/T2.7 低频质量策略推荐稳健性窗口
- [x] `quality_4y_1y`：4 年训练 + 1 年验证，作为质量/低换手策略严格复核窗口
- [ ] `factor_stability_5y_1y`：5 年训练 + 1 年验证，参考滚动 5 年因子有效性检验，用于因子稳定性分析
- [ ] `ml_asset_10y_1y`：10 年训练 + 1 年验证，参考资产特征组合选择论文，用于后续高维 ML / 资产特征模型
- [ ] `short_signal_1y_1m`：1 年训练 + 1 个月验证，用于短周期技术、文本、事件策略
- [ ] `short_signal_1y_1m_embargo10d`：1 年训练 + 10 交易日 embargo + 1 个月验证，用于标签含未来收益的短周期 ML 分类策略

设计依据：

- A 股资产特征组合选择论文采用滚动 `10 年训练 + 1 年测试`。
- A 股 LASSO 定价因子研究采用滚动 `5 年` 时间窗口考察因子有效性时变。
- S&P 500 相对收益 ML 研究采用约 `1 年训练 + 10 日 gap + 1 个月测试`。
- StockMixer 窗口敏感性结论显示：窗口过短信息不足，窗口过长早期信息贡献下降且学习成本增加。

---

## T2.9 sleeve 组合与二阶段 rerank

### T2.9.1 sleeve 组合

- [ ] 将 `legacy_momentum_low_turnover_v1` 降级为动量 sleeve
- [ ] 新增 defensive quality sleeve
- [ ] 新增 risk overlay sleeve
- [ ] 支持组合打分：

```text
final_score =
  0.55 * defensive_quality_score
+ 0.25 * low_turnover_momentum_score
+ 0.20 * risk_overlay_score
```

### T2.9.2 二阶段 ML rerank

启动条件：

- [ ] T2.5 找到至少 5 个稳定候选因子
- [ ] T2.6 或 T2.7 至少一个线性 baseline 可跑通
- [ ] T2.8 策略准入报告可用

候选模型：

- [ ] Logistic / SVM
- [ ] XGBoost
- [ ] Lasso / Elastic Net

禁止：

- [ ] 不用 ML 直接生成交易信号
- [ ] 不用 LLM 直接决定买卖
- [ ] 未解释模型不得进入模拟账户

---

## T2.10 PEAD / 文本 / 跨市场增强

### T2.10.1 PEAD

- [ ] 设计盈利超预期 / ROE 改善 / 公告后漂移因子
- [ ] 确认公告日 point-in-time 数据可用
- [ ] 先作为增强因子，不作为主 ranker

### T2.10.2 文本因子

- [ ] 依赖 `T1.3` 文本事件数据层先完成 provider probe、去重、as-of 口径和覆盖率诊断
- [ ] 分析师文本或财报摘要只做解释因子
- [ ] 新闻、公告、研报、政策和快讯统一从文本事件表读取，不直接散抓网页进入因子实验
- [ ] 输出文本信号覆盖率和滞后性说明
- [ ] 输出文本事件来源分布、重复率、抓取延迟和股票映射覆盖率
- [ ] 先服务 PEAD 解释、关注个股事件时间线和日报风险提示
- [ ] 不直接生成交易动作

### T2.10.3 跨市场 overlay

- [ ] 保留为风险缩放、隔夜情绪解释、开盘情景推演
- [ ] 不恢复为主选股 ranker

---

## 近期执行顺序

1. [x] T2.5 因子有效性诊断报告
2. [ ] T2.6 `low_vol_low_turnover_quality_v1`
3. [ ] T2.7 `quality_low_turnover_monthly_v1`
4. [ ] T2.8 策略准入报告
5. [ ] T2.9 sleeve 组合与二阶段 rerank
6. [ ] T2.10 PEAD / 文本 / 跨市场增强
