# `stok-mapping` 策略开发 Guideline

目标：把“策略想法 -> 数据准备 -> smoke test -> walk-forward -> gate -> 报告归档”固化成统一开发标准，减少拍脑袋试错、口径漂移和无效回测。

适用范围：

- `phase0/strategies/` 下的规则型、因子型、轻量机器学习型候选；
- 当前 Phase 0 / Phase 1 前的研究与验证流程；
- 不适用于自动交易执行，不替代账户级实盘风控。

---

## 1. 总原则

### 1.1 先过常识，再跑回测

任何新策略必须先通过：

1. 运行 smoke test：确认数据、股票池、关键链路没坏；
2. 策略常识 smoke test：确认时间线、执行假设、经济解释没明显错误；
3. 再进入完整 walk-forward / compare / gate。

不能反过来做。没有先过 smoke test 的“漂亮回测”，默认不可信。

### 1.2 先保可解释，再谈复杂度

当前项目主线优先顺序：

1. 可解释、可复盘、可实现；
2. 成本敏感性可接受；
3. 风险调整收益过线；
4. 再考虑增加策略复杂度。

如果简单规则版本都说不清楚，不能直接上更复杂的模型。

### 1.3 KISS 原则：能用简单方案证明的，不先上复杂方案

KISS 原则在本项目中的含义是：策略、数据流和模型设计应优先保持简单、清晰、可复现。复杂度只有在带来可验证收益时才允许增加。

执行要求：

- 新策略必须先给出最小可解释 baseline，再考虑多层过滤、机器学习、深度学习或复杂组合器；
- 每新增一个因子、过滤条件、参数维度或模型层，都必须说明它解决的具体问题；
- 如果复杂版本没有在 current-cost、连续 OOS、过拟合诊断或风险控制上明显改善简单版本，默认回退到简单版本；
- 复杂模型只能作为 rerank、overlay、解释层或对照实验逐步接入，不能绕过数据质量、PIT、成本和样本治理门禁；
- 策略报告必须能说明复杂度带来的边际收益，而不是只报告最终收益指标。

不符合 KISS 的典型情况：

- 简单规则还没验证，就直接引入 Transformer、GNN、RL 或多模型 ensemble；
- 因子越加越多，但没有 IC、分组收益、相关性或边际贡献证据；
- 用复杂参数搜索替代经济解释；
- 只在单一回测窗口改善，样本外、成本后或参数邻域稳定性没有改善。

### 1.4 先保样本治理，再谈收益

任何收益结论都必须服从样本治理要求。

- `portfolio` 候选至少 `4` 个有效 fold；
- 不能靠极少样本、极短窗口或单段顺风行情直接晋级；
- 低样本高收益，只能当线索，不能当结论。

### 1.5 先保连续 OOS，再谈“赚到钱”

walk-forward 分折账本不等于连续复利资金曲线。

正式评价一个候选时，至少要同时看：

- fold 结果；
- 连续 OOS 曲线；
- 与基准对比；
- 成本敏感性；
- 后续应补的行情分段验证。

---

## 2. 标准开发流程

### Stage 0：立项判断

每个候选先回答 5 个问题：

1. 这是不是本土主因子、组合规则或合理 overlay，而不是跨市场主 ranker？
2. 它需要的数据，当前项目是否已有，或者补数据路径是否清楚？
3. 它改善的目标是什么：年化、Sharpe、回撤、换手、解释性，还是账户执行现实性？
4. 它最终输出的是什么：排名、候选池、权重、风控缩放还是解释标签？
5. 它为什么在 A 股市场里应该有效？

如果第 2、5 条答不清，就不进入开发。

### Stage 1：数据准备

新策略只能使用三类已确认数据：

1. 本地历史库：`data/manual_history/a_share_history.sqlite`
2. 股票池：`data/universe/local_factor_universe.csv`
3. 项目内已验证可用的辅助数据：
   - `us_market_history.sqlite`
   - 指数日线
   - 财务因子表

规则：

- 使用财务因子进入正式历史回测前，必须受公告日 `point-in-time` 约束；
- 使用跨市场特征时，必须遵守可见性时间线，不能把美股当日收盘直接给 A 股同日使用；
- 缺数据时先降级，不允许静默补未来值。

### Stage 2：Operational Smoke Test

进入完整回测前，先做运行链路体检。

至少检查：

1. 本地数据库能读；
2. 关键表存在；
3. 最新交易日和覆盖率过线；
4. 股票池不空；
5. 基准指数可加载；
6. 最小策略链路能跑通并能写出输出文件。

通过标准：

- `PASS`：可进入完整回测；
- `WARN`：允许继续，但必须在报告里写清风险；
- `FAIL`：停止，不得继续跑 compare / gate。

### Stage 3：Strategy Smoke Test

在跑完整 walk-forward 之前，先做策略常识校验。

必须明确：

1. 信号何时生成；
2. 何时成交；
3. 用到了哪些字段；
4. 这些字段在当时是否真实可见；
5. 手续费、滑点、印花税是否计入；
6. 是否存在明显“好得离谱”的结果。

出现以下任一情况，直接打回：

- 有未来函数；
- 经济逻辑说不通；
- 执行假设明显脱离 A 股现实；
- 只在零成本场景下成立；
- 小样本结果异常完美。

### Stage 4：实现与接入

新策略接入必须遵守项目现有形态：

1. 放入 `phase0/strategies/`
2. 使用注册表注册
3. 复用已有 `prepare_panel / select_params / apply` 结构
4. 输出标准化 `returns / exposure / signal_frame / metadata`
5. 与现有 report/csv 体系兼容

不允许：

- 在 `walk_forward.py` 里临时散落一套只服务单一候选的硬编码分支；
- 绕过策略注册表直接拼接临时策略；
- 单独定义一套 incompatible 输出格式。

### Stage 5：正式验证

正式验证的默认要求：

1. 使用 walk-forward；
2. 保持训练窗 / 验证窗分离；
3. 与当前 baseline 比较；
4. 主测试先使用默认执行成本，当前主滑点为 `0.00246`；
5. 输出连续 OOS 曲线；
6. 成本敏感性是单独验证路径，必须先明确场景参数再运行；
7. 后续补行情分段验证。

当前 baseline 的默认参照：

- 主 baseline：`legacy_momentum_low_turnover_v1`
- 旧 baseline：`legacy_momentum`
- 基准指数：`SH.000300`

### Stage 6：Gate 与晋级

当前 effectiveness gate 最低要求：

- `annualized_return_mean > 0`
- `sharpe_mean > 0.5`
- `max_drawdown_mean > -0.25`
- `win_rate_mean > 0.45`
- `oos_return_decay_ratio < 0.30`

额外要求：

- 样本治理通过；
- current-cost 场景不能失真；
- 不能只靠单折、单阶段或零成本结果晋级。

### Stage 7：归档与复盘

每轮策略实验结束，必须更新：

- `reports/phase0_walk_forward_report.md`
- `reports/phase0_effectiveness_report.md`
- `reports/phase0_strategy_change_log.md`

每次策略治理运行 `compare` 或 `strategy-admission` 后，如果代码验证、测试和 smoke check 没有阻塞问题，必须额外生成一份当次治理报告，不能只留下 CSV 或控制台输出。报告必须放入 `reports/strategy_governance/YYYY-MM-DD/` 或本次 admission 输出目录，文件名建议：

```text
strategy_governance_report_YYYY-MM-DD_<short_context>.md
```

报告至少包含：

1. 报告日期和生成时间；
2. 本次回测 / admission 背景：为什么跑、对应任务编号、变更范围、是否为新策略 / 参数复核 / 口径复核；
3. 运行命令和关键配置：price mode、universe 口径、walk-forward preset、strategy set、成本参数、数据截止日期；
4. 输入产物和输出产物路径；
5. 代码验证结果：测试命令、smoke check、`git diff --check` 或等价检查；
6. compare/admission 摘要：候选列表、selected candidate、窗口通过数、主要指标、准入 action；
7. 失败或降级原因：收益、换手、参数稳定性、行业集中、因子诊断、价格口径、过拟合、数据质量；
8. 结论边界：是否允许进入下一轮研究、是否允许 paper review、是否禁止进入模拟账户 / 日报；
9. 下一步动作：继续优化、重构、降级 research-only、reject 或补数据 / 补诊断。

模板：

```markdown
# Strategy Governance Report - YYYY-MM-DD - <context>

## Background
- Task:
- Reason:
- Code changes under validation:
- Backtest/admission scope:

## Run Context
- Command:
- Price mode:
- Universe:
- Presets:
- Strategy set / strategies:
- Cost assumptions:
- Data as-of:

## Code Verification
- Tests:
- Smoke checks:
- Static checks:
- Known warnings:

## Results
- Selected candidate:
- Overall verdict / admission action:
- Key metrics:
- Candidate comparison:

## Diagnostics
- Return:
- Execution / turnover:
- Construction / industry:
- Factor / PIT:
- Parameter stability:
- Regime / overfit:
- Data quality:

## Decision
- Decision:
- Boundary:
- Next action:
```

如果是当前主候选，还应尽量补：

- 账单导出；
- 连续 OOS 报表；
- 资产轨迹；
- 买卖原因说明。

---

## 3. 统一判断标准

### 3.1 什么样的策略值得继续

值得继续的候选，一般同时满足：

- 逻辑可解释；
- 成本后仍成立；
- 能在连续 OOS 中维持正收益或显著超额；
- 回撤与换手水平可接受；
- 不是靠单段顺风行情支撑。

### 3.2 什么样的策略应该暂停

遇到以下情况，应暂停而不是继续调参：

- 数据前提本身不成立；
- 财务因子时间线无法证明真实可见；
- current-cost 下全面失效；
- 连续 OOS 明显不如基准；
- 结果只在某一折或某一极端行情里成立。

### 3.3 什么样的策略只适合作为辅助层

以下候选更适合作为 overlay、过滤器或解释层，而不是主 ranker：

- 跨市场直接映射信号；
- 文本情绪但数据源尚不稳定；
- 高频短反转但交易成本极敏感；
- 只能改善解释性，不能改善主收益/风险结构的因子。

---

## 4. 本项目中的强制规则

### 4.1 时间线强制规则

- 不允许使用未来数据；
- 不允许用更正后的财务数据回填过去；
- 不允许把外盘同日收盘信息当作 A 股同日已知。

### 4.2 执行假设强制规则

- 至少计入佣金、滑点、卖出印花税；
- 账户级仿真未完善前，不把理论权重账单当作实盘成交回单；
- 后续要补 A 股 `100` 股整手、现金约束、最低佣金和停牌/涨跌停限制。

### 4.3 文档与口径强制规则

- 策略名、参数口径、报告口径必须一致；
- 新增产物必须说明它是 fold 账本、连续 OOS 曲线，还是旁路校验报表；
- 任何容易引发误读的结果，都要在报表里直接写明解释。

---

## 5. 当前推荐执行顺序

对于未来通过 Phase 0 严格门禁的主候选，默认按这个顺序继续开发；当前无已通过候选：

1. 固化账单、OOS、报表输出；
2. 补账户级执行现实性；
3. 补财务因子 PTI 校验；
4. 补行情分段验证；
5. 再接入日报 / 观察池；
6. 最后才恢复备选策略的继续扩展。

---

## 6. 配套文件

- 策略开发检查清单：`docs/STRATEGY_DEV_CHECKLIST.md`
- 周任务清单：`docs/tasks/WEEKLY_EXECUTION_CHECKLIST.md`
- 主计划：`docs/DEVELOPMENT_PLAN.md`
- 架构说明：`docs/PROJECT_ARCHITECTURE_OVERVIEW.md`
- 文档索引：`docs/README.md`
- 变更日志：`reports/phase0_strategy_change_log.md`
- 数据一致性旁路校验脚本：`scripts/check_local_history_consistency.py`

这份 guideline 是“标准”；Checklist 是“执行单”；主计划是“当前阶段优先级”。
