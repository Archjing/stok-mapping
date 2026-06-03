# T2.4｜策略过拟合诊断工具立项

> 定位：在策略进入盘前观察池、账户级仿真或长期试用前，增加一层专门的“过拟合风险诊断”。
>
> 父级计划：[`DEVELOPMENT_PLAN.md`](../../docs/DEVELOPMENT_PLAN.md)  
> 任务索引：[`tasks/README.md`](../README.md)  
> 参考链接：[`JoinQuant 社区讨论`](https://www.joinquant.com/view/community/detail/3cf8435f4a772fc2f702589704db44db)

---

## T2.4.1 立项背景

当前项目已经具备：

- `phase0/walk_forward.py` 滚动样本外验证
- `phase0/strategies/` 策略注册结构
- `reports/phase0_walk_forward_candidates.csv` 候选策略折级结果
- `reports/phase0_effectiveness_report.md` 有效性门槛
- `research` / `live` profile 成本口径
- 连续 OOS 报告和账户级仿真报告

这些能力可以判断一个策略是否通过当前 gate，但还不能系统回答：

- 策略是不是靠某几个参数偶然跑赢
- 样本内表现是否明显好于样本外
- 换一段市场环境后收益是否崩塌
- 参数轻微扰动后是否失效
- 收益是否只来自少数年份、少数股票或少数极端交易
- 多候选比较是否存在数据挖掘偏差

因此需要单独立项一个子模块：

> **策略过拟合诊断工具，用来给每个候选策略输出可复核的 overfit risk score 和风险解释。**

---

## T2.4.2 模块定位

### T2.4.2.1 是什么

这是一个策略治理模块，服务于：

- 策略研发复核
- 候选策略淘汰
- selected candidate 长期观察
- 盘前观察池上线前检查
- 模拟账户试运行前检查

### T2.4.2.2 不是什么

本模块不做：

- 自动找最优参数
- 自动生成交易信号
- 自动提高收益
- 自动接券商下单
- 用单一评分替代人工判断

它的职责是把“这个策略可能过拟合在哪里”说清楚。

---

## T2.4.3 第一版目标

第一版只做离线诊断，基于已有报告和回测产物生成诊断结果。

### T2.4.3.1 输入

最小输入：

- `reports/phase0_walk_forward_candidates.csv`
- `reports/phase0_walk_forward_folds.csv`
- `reports/phase0_effectiveness_report.md`
- `config.yaml`

后续可扩展输入：

- 参数网格实验结果
- 成本敏感性结果
- 连续 OOS 资金曲线
- 分市场状态报告
- 账户级仿真账单
- 单票交易明细

### T2.4.3.2 输出

第一版输出：

- `reports/strategy_overfit_diagnostic.csv`
- `reports/strategy_overfit_diagnostic.md`
- `reports/strategy_overfit_diagnostic.html`

每个候选策略至少输出：

- `strategy_id`
- `overfit_risk_level`: `low / medium / high / critical`
- `overfit_score`: `0-100`
- `is_oos_pass`
- `is_parameter_stable`
- `is_cost_robust`
- `is_fold_stable`
- `is_market_regime_stable`
- `main_risk_reasons`
- `recommended_action`: `keep / observe / retest / reject`

---

## T2.4.4 诊断维度

### T2.4.4.1 样本内 / 样本外衰减

目标：识别“训练期好看，验证期塌陷”。

建议指标：

- `train_annualized_return_mean`
- `valid_annualized_return_mean`
- `oos_return_decay_ratio`
- `train_valid_sharpe_gap`
- `oos_positive_fold_ratio`
- `oos_min_fold_annualized_return`

初始规则：

- OOS 收益为负：高风险
- OOS 正收益折占比低于门槛：高风险
- 样本内夏普显著高于样本外夏普：中高风险
- OOS 表现只来自最后一折：中高风险

### T2.4.4.2 参数稳定性

目标：识别“只在某一组参数上赚钱”。

建议方法：

- 对核心参数做邻域扰动
- 比较邻近参数组合的年化、夏普、回撤和换手
- 计算参数结果曲面的尖锐程度

需要记录：

- 最优参数
- 相邻参数表现中位数
- 最优参数相对邻域的优势
- 邻域内通过 gate 的比例

初始规则：

- 只有最优参数通过，邻域参数大多失败：高风险
- 最优参数收益远高于邻域中位数：中高风险
- 参数小幅变化后最大回撤显著扩大：高风险

### T2.4.4.3 时间分段稳定性

目标：识别“只适配某一段行情”。

建议分段：

- 牛市 / 熊市 / 震荡市
- 小盘占优 / 大盘占优
- 高波动 / 低波动
- 近一年 / 早期历史 / 中间历史

初始规则：

- 总收益为正，但多数年份为负：高风险
- 只在单一年份贡献主要收益：中高风险
- 分段最大回撤明显超出整体报告：高风险

### T2.4.4.4 成本敏感性

目标：识别“只在理想成交成本下有效”。

建议场景：

- `base_research_cost`
- `main_personal_execution`
- `stress_slippage_0_003`
- `stress_slippage_0_005`

初始规则：

- 主测试口径通过，但 live profile 失败：高风险
- 滑点提高后年化转负：高风险
- 换手越高、成本越敏感，风险加权越高

### T2.4.4.5 候选数量与数据挖掘风险

目标：识别“试了很多策略，总会有一个偶然好看”。

建议记录：

- 本轮 compare 候选数量
- 同一策略家族参数组合数量
- 失败候选数量
- selected candidate 是否来自大规模调参
- 是否存在人工反复调参记录

初始规则：

- 候选数量越多，单个 winner 的置信度折扣越大
- 未保存失败实验记录：风险上调
- 只报告最好结果、不报告完整候选池：风险上调

### T2.4.4.6 收益集中度

目标：识别“收益来自极少数股票或极少数交易”。

建议指标：

- 单票收益贡献 Top 5 占比
- 单日收益贡献 Top 5 占比
- 单折收益贡献 Top 1 占比
- 最大单笔盈利 / 总盈利

初始规则：

- 少数交易贡献多数收益：中高风险
- 剔除最大盈利交易后策略转负：高风险
- 收益高度集中在流动性差股票：高风险

---

## T2.4.5 风险评分框架

第一版使用规则评分，不上复杂模型。

建议满分 `100`，分数越高表示过拟合风险越高：

| 维度 | 权重 |
| --- | ---: |
| 样本内 / 样本外衰减 | 25 |
| 参数稳定性 | 20 |
| 时间分段稳定性 | 15 |
| 成本敏感性 | 15 |
| 候选数量 / 数据挖掘风险 | 15 |
| 收益集中度 | 10 |

建议等级：

| 分数 | 等级 | 动作 |
| ---: | --- | --- |
| `0-24` | `low` | 可保留，继续观察 |
| `25-49` | `medium` | 保留但不得放大资金假设 |
| `50-74` | `high` | 需要重测或降级为观察 |
| `75-100` | `critical` | 不进入盘前观察池或模拟账户 |

---

## T2.4.6 CLI 设计

建议新增命令：

```bash
python -m phase0.cli overfit-diagnostic --config config.yaml
```

可选参数：

```bash
python -m phase0.cli overfit-diagnostic \
  --config config.yaml \
  --profile live \
  --input reports/phase0_walk_forward_candidates.csv \
  --output-dir reports/overfit_diagnostic
```

第一版命令只读现有产物，不触发重新回测。

后续版本再增加：

```bash
python -m phase0.cli overfit-diagnostic --run-param-perturbation
python -m phase0.cli overfit-diagnostic --run-cost-scenarios
python -m phase0.cli overfit-diagnostic --run-market-regime-splits
```

---

## T2.4.7 建议代码结构

```text
phase0/
  overfit.py
  reporting.py
  cli.py

reports/
  overfit_diagnostic/
    strategy_overfit_diagnostic.csv
    strategy_overfit_diagnostic.md
    strategy_overfit_diagnostic.html
```

`phase0/overfit.py` 建议包含：

- `load_overfit_inputs(...)`
- `diagnose_oos_decay(...)`
- `diagnose_parameter_stability(...)`
- `diagnose_regime_stability(...)`
- `diagnose_cost_sensitivity(...)`
- `diagnose_data_mining_risk(...)`
- `diagnose_return_concentration(...)`
- `build_overfit_scorecard(...)`

`phase0/reporting.py` 后续增加：

- `write_overfit_diagnostic_report(...)`
- `write_overfit_diagnostic_html(...)`

---

## T2.4.8 与现有 gate 的关系

现有 effectiveness gate 判断：

> 策略是否满足当前收益、夏普、回撤、胜率和 OOS 衰减门槛。

过拟合诊断工具判断：

> 策略通过 gate 的证据是否稳定，是否可能只是调参、选样本或成本假设造成的偶然结果。

因此二者关系是：

- gate 通过，不代表 overfit risk 低
- overfit risk 高，即使 gate 通过，也不能直接进入应用链路
- overfit diagnostic 应作为 `brief watchlist` 和模拟账户试运行前的附加检查

---

## T2.4.9 实施步骤

### T2.4.9.1 P0：立项与接口冻结

- [x] 新增本任务文档
- [ ] 确认第一版输入输出文件名
- [ ] 确认评分权重和风险等级
- [ ] 确认是否纳入 `phase0 run` 默认产物

### T2.4.9.2 P1：离线诊断 MVP

- [ ] 新增 `phase0/overfit.py`
- [ ] 从现有 walk-forward candidates 产物读取策略折级指标
- [ ] 实现 OOS 衰减诊断
- [ ] 实现 fold 稳定性诊断
- [ ] 实现成本敏感性诊断的占位读取
- [ ] 输出 CSV / Markdown 报告

### T2.4.9.3 P2：增强诊断

- [ ] 接入参数扰动实验
- [ ] 接入市场状态分段
- [ ] 接入收益集中度分析
- [ ] 接入候选数量 / 数据挖掘风险记录
- [ ] 输出 HTML 报告

### T2.4.9.4 P3：流程集成

- [ ] `phase0 run` 可选生成过拟合诊断报告
- [ ] `execution-gate` 读取 overfit risk
- [ ] `brief watchlist` 展示 selected candidate 的过拟合风险摘要
- [ ] 模拟账户试运行前检查 overfit risk 是否超过阈值

---

## T2.4.10 验收标准

第一版验收：

- [ ] CLI 可生成 `strategy_overfit_diagnostic.csv`
- [ ] CLI 可生成 `strategy_overfit_diagnostic.md`
- [ ] 报告能覆盖当前 selected candidate
- [ ] 报告能解释主要风险来源，而不是只给分数
- [ ] 当 OOS 失败、fold 不稳定或成本敏感时，风险等级会自动上调
- [ ] 不改变现有 `phase0 run`、walk-forward、effectiveness gate 的默认行为

长期验收：

- [ ] 每个候选策略都有过拟合风险记录
- [ ] selected candidate 进入观察池前必须有诊断报告
- [ ] 失败实验和参数搜索过程可追踪
- [ ] 能识别“回测漂亮但样本外/成本/参数扰动脆弱”的策略

---

## T2.4.11 当前结论

本模块应进入 `T2` 策略治理主线，但优先级低于当前 selected strategy 的账单、盘前观察池和模拟账户链路稳定性。

建议实施顺序：

1. 先冻结诊断报告 schema
2. 再做只读现有产物的 MVP
3. 最后补参数扰动、分市场状态和收益集中度

第一版不要追求复杂统计检验，先把个人量化最容易忽略的过拟合证据稳定暴露出来。
