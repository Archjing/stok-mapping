# 机器学习、深度学习在本项目应用可行性评估

日期：2026-06-05  
类型：主题研究 note  
来源：本 session 对 `refdocs/papers/` 论文与当前项目状态的综合评估回答归档

---

**结论**
机器学习在本项目可行，而且应进入路线图；深度学习可研究，但不应马上作为主策略核心。当前最优路径是：

1. 先做 `T2.6/T2.7` 线性多因子 baseline。
2. 再做 `T2.8 strategy-admission`。
3. 最后启动 `T2.9 二阶段 ML rerank`。
4. 深度学习只放入研究沙盒，不进入模拟账户或日报主链路。

**当前依据**
项目已具备 ML 的前置基础：

- 已有 `factor-effectiveness`，并在 `qfq_asof / PIT` 口径下找出 6 个可用因子：`low_pb`、`low_vol60`、`low_turnover_rate`、`low_vol20`、`ep`、`cash_flow_quality`。见 [factor_effectiveness.md](/home/zj/workspace/stok-mapping/reports/factor_effectiveness/factor_effectiveness.md)。
- 当前计划已明确 ML 只能作为二阶段 rerank，不直接生成交易信号。见 [EFFECTIVE_QUANT_STRATEGY_RESEARCH_PLAN_2026-06-04.md](/home/zj/workspace/stok-mapping/docs/EFFECTIVE_QUANT_STRATEGY_RESEARCH_PLAN_2026-06-04.md)。
- 当前任务清单中 `T2.9` 的启动条件尚未完全满足：`T2.6/T2.7` baseline 和 `T2.8 strategy-admission` 还没完成。见 [EFFECTIVE_QUANT_STRATEGY_RESEARCH_TASKS.md](/home/zj/workspace/stok-mapping/docs/tasks/strategy/EFFECTIVE_QUANT_STRATEGY_RESEARCH_TASKS.md)。
- 当前依赖栈没有 `scikit-learn`、`xgboost`、`lightgbm`、`torch`、`jax`，所以第一版 ML 应优先控制依赖，不直接上深度学习框架。见 [pyproject.toml](/home/zj/workspace/stok-mapping/pyproject.toml)。

**论文转化判断**
最适合当前项目的方向：

| 方向 | 可行性 | 推荐阶段 | 判断 |
| --- | --- | --- | --- |
| LASSO / ElasticNet | 高 | 近期 | 最适合做因子稀疏化、冗余筛选、共线性处理。中文 LASSO 因子论文与当前因子诊断高度匹配。 |
| Logistic / SVM | 中高 | T2.9 | 适合做收益分位分类或上涨概率 rerank，但不能替代主策略。 |
| RandomForest / XGBoost | 中高 | T2.9 | 适合非线性 rerank、特征重要性分析；需要严格 walk-forward 和过拟合约束。 |
| StockMixer / 简单 MLP | 中 | P3 研究 | 论文强调简单 MLP 在有限股票数据下优于复杂结构，适合作为第一类 DL baseline。 |
| LSTM / Transformer / MASTER | 中低 | P3+ | 有论文价值，但对样本量、训练稳定性、特征工程和防泄漏要求高。暂不适合主链路。 |
| GNN / MDGNN | 低到中 | P4 | 需要行业、供应链、股东、研报、资金、事件等动态图谱数据。当前数据层未准备好。 |
| DRL / FinRL | 低 | 长期研究 | 对交易环境、成本、滑点、奖惩函数极敏感，当前不应进入策略准入链路。 |
| 文本 / LLM 因子 | 中 | T2.10 | 可做公告、研报、新闻解释因子，不应直接输出买卖。 |

**推荐最小方案**
先做 `ml_rerank_v1`，但要等 `T2.6/T2.7/T2.8` 完成后启动。

设计口径：

- 输入：线性多因子策略筛出的候选池，例如 top 100 或 top 200。
- 特征：当前 `factor-effectiveness` 已验证因子，加少量风险和流动性字段。
- 标签：未来 20 日相对收益分位，而不是明日涨跌。
- 模型：第一版只做 `LogisticRegression / ElasticNet / RandomForest`，暂不上深度学习。
- 输出：只输出 rerank 候选、特征重要性、fold 表现、模型卡，不直接下单。
- 验收：必须优于线性 baseline，且通过 `qfq_asof`、过拟合诊断、成本后回测和 `strategy-admission`。

**不建议现在做的事**
- 不要直接做“深度学习预测股价”。
- 不要把 LSTM/Transformer/GNN 结果接入日报或模拟账户。
- 不要用随机切分训练集，必须 walk-forward。
- 不要用 `qfq_current` 或非 point-in-time 财务字段训练模型。
- 不要让 LLM 直接给买卖信号。

**最终判断**
机器学习是本项目合理的增强层，不是当前主线替代品。当前工程顺序应保持为：

`因子诊断 -> 低频可解释 baseline -> 策略准入 -> ML 二阶段 rerank -> 深度学习研究沙盒`。
