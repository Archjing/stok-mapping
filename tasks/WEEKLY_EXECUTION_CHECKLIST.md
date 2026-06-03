# T0｜周执行计划总清单（开发计划书附件）

> 本文件是 `DEVELOPMENT_PLAN.md` 的统一周执行附件。  
> 后续每一周的任务清单都追加在同一个文件中，避免多个附件分散。  
> 主计划中的长期路线、阶段划分和项目定位以 `DEVELOPMENT_PLAN.md` 为准；本文件只管理**当前周目标、执行节奏、检查点与归档要求**。
> 任务拆解总索引见：[`tasks/README.md`](./README.md)。

---

# W1｜本土主策略候选验证（已完成并归档）

## W1.0.1 本周目标

> 在现有 compare / report / gate 链路下，验证 A 股本土候选策略，修正候选比较口径，并判断当前失败到底来自策略逻辑、参数、样本治理还是交易成本。

## W1.0.2 当前基线与门槛缺口

### W1.0.2.1 当前基线
- 当前 selected candidate：`legacy_momentum_low_turnover_v1`
- 当前 gate：`PASS`
- 当前口径：portfolio-scope
- 当前样本：7 年窗口，4 个 portfolio fold

### W1.0.2.2 当前缺口
- 当前 gate 已无硬性缺口
- `annualized_return_mean = 0.1331`
- `sharpe_mean = 1.0083`
- `max_drawdown_mean = -0.1042`
- `win_rate_mean = 0.5110`
- 当前主测试成本口径：`slippage = 0.00246`，`commission = 0.00025`，`stamp_duty_sell = 0.0005`

### W1.0.2.3 当前判断
- 低换手改造已经替代旧 `legacy_momentum` 成为当前主候选。
- 当前主要工作从“修复 Sharpe”切换为“收口解释链路、补齐账户仿真约束、接入日常输出”。
- 成本敏感性已改为单独 CLI 路径，显示新候选在 `main_personal_execution` 下仍可通过 gate，后续不需要再靠零成本结论证明有效。

## W1.0.3 本周候选范围

### W1.0.3.1 候选 1：MA/K 线低复杂度 baseline
- [x] 建立低复杂度、可解释、可复现的技术基线
- [x] 作为本周的诊断地板
- [x] 结论：current-cost 下表现弱，不作为下一轮主攻方向

### W1.0.3.2 候选 2：短周期残差动量 + 反转增强 v2
- [x] 在已有 `residual_momentum_reversal_v1` 基础上最小增强
- [x] 完成 portfolio compare
- [x] 已降级为备选，只在主线收口后再考虑低换手版本

### W1.0.3.3 候选 3：多因子 + 量价二次筛选 v1
- [x] 作为本周最重要的冲门槛候选
- [x] 用更完整的本土特征组合争取超过 `legacy_momentum`
- [x] 已完成 32 季度财务因子覆盖后的 portfolio compare
- [x] 已确认 current-cost 下不胜出，暂不继续占用主线

### W1.0.3.4 本周新增治理/框架修复
- [x] 将 `legacy_momentum` 从 symbol-scope 改为 portfolio-scope baseline
- [x] 将回测窗口从 `5` 年扩大到 `7` 年
- [x] 将财务因子维护窗口从 `8` 季度扩大到 `32` 季度
- [x] 新增成本敏感性报告：`base_research_cost` / `main_personal_execution` / `stress_slippage_0_003` / `stress_slippage_0_005` / `low_slippage` / `zero_cost`
- [x] 将成本敏感性从主测试中拆出，必须显式调用 `phase0.cli cost-sensitivity`
- [x] 修复 point-in-time 财务因子 merge 的 datetime dtype 边界
- [x] 更新 `README.md`、`DEVELOPMENT_PLAN.md`、`reports/phase0_strategy_change_log.md`

## W1.0.4 数据源升级准备项（仅准备，不实施）

> 目的：为 Week 2 的 FRED / Tiingo 数据源升级做口径确认，不改变当前 Week 1 以策略验证为主的顺序。

- [x] 确认 `FRED` 首批序列清单：`GDP`、`CPIAUCSL`、`FEDFUNDS`、`DFF`、`VIXCLS`
- [x] 确认 `Tiingo` 首批标的清单：`NVDA`、`AAPL`、`TSLA`、`KWEB`
- [x] 确认 `yfinance` 在过渡期继续保留为 fallback
- [x] 确认 Week 1 已按治理需要修改 `phase0` 正式回测链路，并完成报告/变更日志同步
- [x] 把 US/HK market history 和 yfinance fallback 结论写入变更日志和主计划书

## W1.0.5 策略积木迭代（主线工程增强）

> 目的：把当前“配置参数 + 代码里写死的候选实现”升级为“可插拔策略模块”，从而让新策略更快接入、更快测试、更快输出统一报告，并为后续策略选定后的研判简报与模拟交易预留统一接口。

参考文档：`tasks/strategy/STRATEGY_BLOCKS_PLAN.md`

- [x] 设计最小策略契约：策略元信息、输入声明、参数选择/拟合、信号/排序输出、说明文本
- [x] 建立 `phase0/strategies/` 目录与 `base.py` / `registry.py` 雏形
- [x] 先迁移 `legacy_momentum` 到策略模块
- [x] 再迁移 `residual_momentum_reversal_v1` 到策略模块
- [x] 让 compare 候选从 registry + config 生成，而不是只在 `_run_compare` 里手工拼装
- [x] 统一策略摘要输出格式，确保继续兼容现有 report/csv 体系
- [x] 预留“选定策略 → 研判简报 / 模拟交易”所需的标准化 signal/weight 输出接口

## W1.0.6 推荐执行顺序

### W1.0.6.1 研究优先级
1. 低换手 legacy momentum 改造
2. 账单 / 资产轨迹 / 买卖原因导出
3. 账户级仿真与实盘约束补齐

### W1.0.6.2 实现顺序
1. **低换手 / 延长持有 baseline**
2. **账单 / HTML 预览 / 日资产导出**
3. **账户级仿真与解释链路收口**

### W1.0.6.3 原因
- [x] 原 baseline 已落地并证明 MA/K 线 current-cost 表现弱
- [x] residual v2 可复用现有实现，但成本敏感性偏高
- [x] multifactor v1 已进入 compare，但 current-cost 下仍不胜出
- [x] 当前不再优先加因子复杂度，先完成低换手策略收口与执行约束

## W1.0.7 Day 1 - Day 7 节奏

### W1.0.7.1 Day 1：统一共享特征与候选比较口径
- [x] 让候选在同一条 compare / report / gate 链路里比较
- [x] 共享价格 / 量能特征可复用
- [x] 候选比较报告更清晰
- [x] 已统一为 portfolio-scope 比较

### W1.0.7.2 Day 2：完成 MA/K 线 baseline
- [x] 形成第一个低复杂度 compare-only 候选
- [x] `ma_kline_baseline_v1` 进入 compare 结果
- [x] 作为诊断地板保留
- [x] 结论：current-cost 下不适合作为主候选

### W1.0.7.3 Day 3-4：完成 residual momentum + reversal v2
- [x] 复用现有残差动量候选，做最小增强
- [x] `residual_momentum_reversal_v2` 进入 compare
- [x] 完成成本敏感性观察
- [ ] 下一轮只研究低换手/持有期约束版本

### W1.0.7.4 Day 5-6：完成 multifactor + volume/price filter v1
- [x] 作为本周最强候选，尝试直接改善主 gate
- [x] `multifactor_volume_price_filter_v1` 进入 compare
- [x] 已在 32 季度财务因子下重跑
- [ ] current-cost 下未优于 `legacy_momentum`，下一轮需要先做成本约束

### W1.0.7.5 Day 7：统一 compare、决策、归档
- [x] 更新 compare 结果
- [x] 更新 effectiveness report
- [x] 更新 change log
- [x] 明确每个候选是保留、淘汰还是晋级

## W1.0.8 本周比较与归档要求

- [x] 记录候选名称
- [x] 记录变更原因
- [x] 记录参数或规则摘要
- [x] 记录最新回测结果摘要
- [x] 记录是否保留
- [x] 记录是否晋级
- [x] 记录下一步建议

归档位置：
- [x] `reports/phase0_walk_forward_report.md`
- [x] `reports/phase0_effectiveness_report.md`
- [x] `reports/phase0_walk_forward_candidates.csv`
- [x] `reports/phase0_strategy_change_log.md`
- [x] `reports/phase0_cost_sensitivity_report.md`

## W1.0.9 本周成功标准

### W1.0.9.1 硬门槛
- [x] compare mode 中出现一个不是 `legacy_momentum` 的新优胜候选
- [x] `annualized_return_mean > 0`
- [x] `sharpe_mean > 0.5`
- [x] `max_drawdown_mean > -0.25`
- [x] `win_rate_mean > 0.45`
- [x] `oos_return_decay_ratio < 0.30`

### W1.0.9.2 软判断
- [x] 新候选显著改善当前失败项（Sharpe）
- [x] 结果不是由少数 fold 偶然支撑
- [x] 候选逻辑可解释、可延续、可复盘
- [x] 成本敏感性已可解释

## W1.0.10 本周不做事项

- [ ] 不重开跨市场主 ranker 路线
- [ ] 不把跨市场映射重新作为主选股核心
- [ ] 不推进 Web / PWA / App / Dashboard
- [ ] 不推进自动交易与下单执行
- [ ] 不让 LLM 直接生成交易信号
- [ ] 不大规模重构基础设施
- [ ] 不修改 universe 主评分逻辑，除非本周结果明确要求下一轮再做

## W1.0.11 本周结束后的决策规则

### W1.0.11.1 如果有候选通过 gate
- [x] 提升为新的主候选
- [x] 在变更日志中记录晋级原因
- [x] 进入下一轮更细的参数与稳定性验证

### W1.0.11.2 如果没有候选通过 gate
- [ ] 保留 `ma_kline_baseline_v1` 作为诊断地板
- [ ] 保留 `legacy_momentum` 作为 portfolio baseline
- [ ] 在 residual / multifactor 中只保留低换手改造版本继续 compare
- [ ] 下一轮重点转向：**持有期、换手、滑点敏感性控制**，而不是继续加大因子复杂度

---

# W1.5｜Sharpe 修复与成本敏感性收敛

## W1.5.1 本周目标

- [x] 在 current-cost 假设下将 selected candidate 的 `sharpe_mean` 提升到 `> 0.5`
- [x] 保持 `max_drawdown_mean > -0.25`
- [x] 保持 `win_rate_mean > 0.45`
- [x] 降低 current-cost 与 low-slippage 场景之间的表现差距

## W1.5.2 当前基线

- selected candidate：`legacy_momentum_low_turnover_v1`
- annualized_return_mean：`0.1331`
- sharpe_mean：`1.0083`
- max_drawdown_mean：`-0.1042`
- win_rate_mean：`0.5110`
- turnover_annual_mean：`1.50`
- main_personal_execution Sharpe：`1.0083`
- low_slippage Sharpe：`1.0094`
- zero_cost Sharpe：`0.8371`

## W1.5.3 优先实验方向

### W1.5.3.1 低换手 legacy momentum
- [x] 增加最小持有期约束
- [x] 增加换手惩罚或 trade cooldown
- [x] 测试更宽组合与更慢调仓，降低单票波动
- [x] 在参数选择阶段加入 cost-aware score

### W1.5.3.2 residual momentum 低换手版本
- [ ] 降低交易频率
- [ ] 避免短周期反转信号导致频繁换仓
- [x] 已确认不进入当前主线，只保留为后续备选

### W1.5.3.3 multifactor slippage-aware 版本
- [ ] 对 `amount_ratio20`、波动率、上影线等交易质量过滤重新设定
- [ ] 增加持有期或调仓频率限制
- [x] 已确认 current-cost 下未胜出，暂不继续占用当前主线

## W1.5.4 验收要求

- [x] 每次策略逻辑或参数修改都写明理由和参考依据
- [x] 成本敏感性测试改为显式路径，按需要输出 base / main / stress / low / zero 等场景
- [x] 不用零成本结果替代 current-cost gate
- [x] 不因单个 fold 表现好直接晋级
- [x] 变更写入 `reports/phase0_strategy_change_log.md`

---

# W1.6｜通过后收口与下一步开发

## W1.6.1 本周目标

- [x] 跑完整 Phase 0，正式确认 `legacy_momentum_low_turnover_v1` 替代旧 `legacy_momentum`
- [x] 生成低换手策略账单 CSV、资产日表与 HTML 预览
- [x] 在账单中补充卖出原因、买入驱动力和中间年份折叠预览
- [x] 在通过策略与回测代码补充中文注释，解释模拟了什么看盘、研判和交易行为
- [x] 将主测试默认滑点更新为 `0.00246`
- [x] 将成本敏感性测试拆分为显式 CLI 路径，主测试不再自动运行压力场景
- [x] 为账单导出脚本增加行情面板缓存，支持 `--refresh-cache` 和 `--no-panel-cache`
- [x] 将账单导出纳入标准 CLI / report 链路
- [x] 在账户仿真中补齐 A 股整手成交、现金约束和撮合细节
- [x] 完成财务因子公告日 point-in-time 校验方案
- [x] 将当前 selected strategy 接入 `07:30` 盘前日报 / 观察池输出
- [x] 补连续样本外资金曲线验证，避免把 walk-forward 分折重置误读成长期横盘
- [x] 生成“连续 OOS 资金曲线 + 基准对比 + 各 fold 收益分解”HTML 报表
- [x] 补行情分段验证，区分顺风行情与更普遍的策略有效性
- [x] 将 `execution-gate` 做成独立“实盘仿真回测”管线，支持 `research` / `live` profile
- [x] 将 `oos-report` 补齐 `--profile` 参数，保持与 `execution-gate` 相同配置逻辑
- [x] 统一 HTML 报表展示体验：生成时间、横向滚动、纵向滚动和固定表头

## W1.6.2 当前状态

- [x] 当前 selected candidate：`legacy_momentum_low_turnover_v1`
- [x] current-cost gate：PASS
- [x] 账单导出脚本：`scripts/export_low_turnover_bill.py`
- [x] 账单导出缓存：默认 `reports/cache/low_turnover_panel.pkl`
- [x] 预览产物：`reports/phase0_low_turnover_bill_preview.html`
- [x] 日资产产物：`reports/phase0_low_turnover_daily_assets.csv`
- [x] 连续 OOS 报表脚本：`scripts/export_low_turnover_oos_report.py`
- [x] 连续 OOS 报表：`reports/phase0_low_turnover_oos_report.html`
- [x] 成本敏感性命令：`phase0.cli cost-sensitivity`
- [x] 账单导出命令：`phase0.cli bill`
- [x] 行情分段命令：`phase0.cli market-regime`
- [x] 行情分段报表：`reports/phase0_market_regime_report.html`
- [x] 财务 PTI 命令：`phase0.cli financial-pti`
- [x] 财务 PTI 报表：`reports/phase0_financial_pti_report.html`
- [x] 盘前观察池命令：`phase0.cli premarket`
- [x] 盘前观察池报表：`reports/phase0_premarket_report.html`
- [x] 实盘仿真 gate 命令：`phase0.cli execution-gate --profile research|live`
- [x] profile 化 OOS 命令：`phase0.cli oos-report --profile research|live`
- [x] 当前 HTML 报表规范：标题显示生成时间；表格横向按 `96vw` 滚动，纵向按 `70vh` 滚动，表头固定

## W1.6.3 下一步实际编码顺序

- [x] 先把账单导出接入正式命令入口，避免每次靠单独脚本调用
- [x] 再补账户级交易约束，优先 A 股 `100` 股 / `1` 手整手买入与现金检查
- [x] 然后做行情分段验证，回答策略是否依赖顺风行情
- [x] 接着做公告日 PTI 校验，给质量成长类候选扫清后续回测前提
- [x] 最后把 selected strategy 输出接入日报 / 观察池

## W1.6.4 通过后执行优先级表

| 优先级 | 任务 | 目的 | 完成标准 |
| --- | --- | --- | --- |
| `P0` | 账单导出正式化 | 把当前单独脚本产物纳入统一回测输出，保证每次 Phase 0 重跑后账单和日资产自动更新。 | `phase0 run` 后稳定产出账单 CSV、日资产 CSV 和 HTML 预览。 |
| `P0` | 账户级实盘约束 | 让组合权重回测更接近 A 股真实执行。 | 支持 `100` 股整手、现金检查、卖出回款和账户余额联动。 |
| `P1` | 连续 OOS 与基准对比报表 | 纠正 fold 重置带来的阅读偏差，直接回答“是否只是跟上行情”。 | 有连续拼接后的样本外资金曲线、基准曲线和 fold 收益分解表。 |
| `P1` | 行情分段验证 | 识别策略是不是只在顺风阶段有效。 | 能按顺风 / 震荡 / 回撤等阶段输出分段表现。 |
| `P1` | 财务因子 PTI 校验 | 为后续质量成长 / 多因子扩展建立可信时间线。 | 明确公告日可见性规则，并形成校验结论。 |
| `P1` | 日报 / 观察池接入 | 让已通过策略进入日常使用链路。 | `07:30` 输出可直接引用当前 selected strategy 的候选、权重和理由。 |
| `P1` | profile 化实盘仿真与 OOS 报告 | 避免策略研究口径和实盘仿真口径混用。 | `execution-gate` 与 `oos-report` 均支持 `research` / `live` profile，并由 `config.yaml` 管理参数。 |
| `P1` | HTML 报表可读性收口 | 长表和宽表需要适合人工检查。 | 所有 HTML 标题显示生成时间，表格支持横纵滚动和固定表头。 |
| `P2` | 备选策略继续精修 | 避免主线未收口前重新发散。 | 仅在前四项完成后，再恢复 residual / multifactor 迭代。 |
| `P2` | FRED / Tiingo 升级 | 继续平台能力建设，但不打断当前主线。 | 在不影响当前策略收口的前提下分阶段推进。 |

---

# W1.7｜账户级仿真 v2：A 股真实交易约束增强

## W1.7.1 本周目标

> 在已完成的账户级 v1 基础上，把当前“目标权重 + 整手 + 现金约束”的账单模拟，升级为更接近 A 股真实交易环境的执行仿真。

- [x] 成交价口径从固定收盘价扩展为可配置口径
- [x] 补涨跌停约束，避免模拟中出现现实无法成交的买卖
- [x] 补停牌约束，停牌日不允许生成成交
- [x] 补流动性约束，限制单笔/单日成交量占市场成交量比例
- [x] 在账单中记录未成交、部分成交和约束原因
- [x] 为未来真实账户持仓 CSV / 券商成交回报导入预留接口
- [x] 保持项目边界：只做研究和模拟，不接自动下单

## W1.7.2 当前基线

- [x] 当前账单脚本：`scripts/export_low_turnover_bill.py`
- [x] 当前账单命令：`phase0.cli bill`
- [x] 当前盘前观察池命令：`phase0.cli premarket`
- [x] 已支持 `100` 股整手成交
- [x] 已支持买入现金约束
- [x] 已支持卖出回款进入现金
- [x] 已支持佣金、滑点、卖出印花税
- [x] 已输出现金资产、股票资产、账户总资产、交易成本和交易原因

账户级仿真 v2 已覆盖：

- [x] `close` / `next_open` / `conservative` 三类成交价口径，其中默认 `next_open`
- [x] 涨停买不进、跌停卖不出
- [x] 停牌或无有效成交数据时不生成成交
- [x] 成交量不足导致部分成交或不成交
- [x] 真实账户持仓 CSV 输入格式预留：`tasks/account/ACCOUNT_RECONCILIATION_CSV_SCHEMA.md`
- [x] 券商成交回报 CSV 输入格式预留：`tasks/account/ACCOUNT_RECONCILIATION_CSV_SCHEMA.md`

## W1.7.3 开发模块拆分

### W1.7.3.1 执行价格模型

- [x] 新增成交价配置项，例如 `execution.price_mode`
- [x] 支持至少三种口径：
  - [x] `close`：沿用当前收盘价近似，作为研究基线
  - [x] `next_open`：使用开盘价口径，模拟盘前信号次日开盘执行
  - [x] `conservative`：买入取更不利价格、卖出取更不利价格，用于压力测试
- [x] 报表中记录本次使用的成交价口径
- [x] 保持历史报告可复现，默认值变更写入变更日志

### W1.7.3.2 涨跌停交易约束

- [x] 在行情面板中保留 `pre_close` 或可推导的前收盘价
- [x] 按 A 股常见规则计算涨跌停边界，先支持主板 `10%`、创业板/科创板 `20%`
- [x] 买入遇到涨停时标记为未成交
- [x] 卖出遇到跌停时标记为未成交
- [x] 对无法判断涨跌停规则的股票使用保守默认，并在报告中提示

### W1.7.3.3 停牌约束

- [x] 明确停牌识别规则：无当日 bar、成交量为 0、金额为 0 或数据源停牌标记
- [x] 停牌日不允许买入或卖出
- [x] 已持仓股票停牌时继续按可用价格估值，无法估值时沿用上一有效价并标记
- [x] 账单中增加停牌导致未成交的原因说明

### W1.7.3.4 流动性与成交量约束

- [x] 新增配置项，例如 `execution.max_participation_rate`
- [x] 限制单票单日模拟成交量不超过当日市场成交量的一定比例
- [x] 超出限制时按可成交数量部分成交
- [x] 部分成交后现金、持仓、目标权重和实际权重必须一致
- [x] 报表增加“目标成交量 / 实际成交量 / 未成交量”

### W1.7.3.5 未成交与部分成交账单

- [x] 在账单中增加交易状态：`全部成交` / `部分成交` / `未成交`
- [x] 在账单中增加未成交原因字段
- [x] 在日资产表中保留当日未成交订单数量
- [x] HTML 预览用颜色区分成交、部分成交、未成交
- [x] 盘前观察池中对可能无法成交的标的给出风险提示

### W1.7.3.6 真实账户对账预留

- [x] 定义本地持仓 CSV 输入格式，但暂不接券商 API
- [x] 定义成交回报 CSV 输入格式，但暂不自动下单
- [x] 预留模拟持仓 vs 真实持仓差异表字段
- [x] 预留模拟成交 vs 真实成交差异表字段
- [x] 文档明确：该模块只用于复盘和研究，不产生交易指令

## W1.7.4 验收标准

- [x] 单元或脚本级校验：成交量仍满足 `100` 股整手规则
- [x] 单元或脚本级校验：现金余额不为负
- [x] 单元或脚本级校验：涨停买入不会生成已成交买单
- [x] 单元或脚本级校验：跌停卖出不会生成已成交卖单
- [x] 单元或脚本级校验：停牌日不会生成成交
- [x] 单元或脚本级校验：成交量不超过配置的参与率限制
- [x] 报表可展示全部成交、部分成交、未成交及原因
- [x] README / 开发计划说明当前仍不是自动交易系统
- [x] `execution-gate --profile live` 可按实盘仿真参数生成独立 gate 报告
- [x] `oos-report --profile live` 可按实盘仿真参数生成独立连续 OOS 报告
- [x] HTML 账单和报告支持横向/纵向滚动，避免长表撑爆页面

## W1.7.5 暂不做事项

- [x] 不接券商 API
- [x] 不自动下单
- [x] 不做盘中高频撮合
- [x] 不做逐笔盘口回放
- [x] 不把真实账户文件纳入 Git
- [x] 不因为执行仿真更真实就跳过 walk-forward / gate 验证

## W1.7.6 推荐执行顺序

1. 先做成交价口径配置，解决“收盘价近似成交”的最大阅读偏差。
2. 再做涨跌停和停牌约束，解决现实中无法成交的问题。
3. 然后做流动性参与率限制，解决成交量过大的可实现性问题。
4. 接着改账单和 HTML，让未成交 / 部分成交可见。
5. 最后预留真实账户 CSV 对账，不接自动交易。

---

# W2｜数据源升级（FRED / Tiingo 分层替换）

## W2.1 本周目标

- [x] 明确形成项目级结论：**FRED 先、Tiingo 后、yfinance 保留 fallback**
- [x] 完成第二周文档、边界和接入设计准备
- [x] 为下一周正式编码实施做好输入条件
- [x] 开始 FRED adapter 最小实现，先覆盖宏观 / 利率 / VIX 序列
- [x] FRED 稳定后再推进 Tiingo adapter，不与 FRED 同时硬切

## W2.2 当前基线确认

- [x] A 股盘后主源仍是 `Tushare Pro`
- [x] A 股 fallback 仍是本地 SQLite / AkShare / 新浪原始快照
- [x] 美股 / ETF / VIX / CNH 当前已落库到 `us_market_history.sqlite`，过渡 provider 仍为 `yfinance`
- [x] 宏观 / 利率当前尚未拆独立主源
- [x] 当前第二周工作**不修改** `phase0` 主回测逻辑

## W2.3 数据源分层结论

### W2.3.1 FRED 接管范围
- [x] GDP → `GDP`
- [x] CPI → `CPIAUCSL`
- [x] 联邦基金利率（月）→ `FEDFUNDS`
- [x] 联邦基金利率（日）→ `DFF`
- [x] VIX → `VIXCLS`

### W2.3.2 Tiingo 接管范围
- [x] `NVDA`
- [x] `AAPL`
- [x] `TSLA`
- [x] `KWEB`

### W2.3.3 暂不处理范围
- [x] CNH / FX 主源替换
- [x] 所有美股指数一次性替换
- [x] 当前 A 股正式主链路改造
- [x] 直接移除 `yfinance`

## W2.4 FRED 接入任务

### W2.4.1 文档与映射
- [x] 形成 FRED 序列映射表
- [x] 每个序列都能映射到项目中的明确用途：
  - [x] 风险解释层
  - [x] 宏观 overlay
  - [x] 日报结构化摘要输入

### W2.4.2 代码设计准备
- [x] 明确 FRED adapter 入口
- [x] 明确 FRED 数据缓存策略
- [x] 明确 FRED 对 `config.yaml` 的新增配置项
- [x] 明确 FRED 与现有 `yfinance` 的职责边界

### W2.4.3 验收
- [x] FRED 引入不会破坏当前 `phase0.cli` 正式链路
- [x] FRED 仅承接宏观 / 利率 / VIX，不与美股个股职责混淆

## W2.5 Tiingo 接入任务

### W2.5.1 覆盖范围确认
- [x] 明确首批接入标的：`NVDA` / `AAPL` / `TSLA` / `KWEB`
- [x] 明确这些标的在项目中的用途：
  - [x] 美股日线
  - [x] 产业映射核心触发标的
  - [x] 隔夜解释层输入

### W2.5.2 代码设计准备
- [x] 明确 Tiingo adapter 入口
- [x] 明确 Tiingo 与 `yfinance` fallback 关系
- [x] 明确 Tiingo 对 `config.yaml` 的新增配置项
- [x] 明确 Tiingo 不处理宏观序列

### W2.5.3 验收
- [x] Tiingo 只替换最关键的美股个股 / ETF，不扩大范围
- [x] `yfinance` 仍保留为 fallback

## W2.6 配置层重构草案

- [x] 宏观、利率、VIX、个股、ETF、FX 的配置职责清晰拆分
- [x] `tushare`：A 股盘后主源
- [x] `fred`：宏观 / 利率 / VIX
- [x] `tiingo`：美股个股 / ETF / EOD
- [x] `yfinance`：fallback / FX 代理 / 临时研究源

## W2.7 本周归档要求

- [x] `yfinance` 当前保留职责
- [x] `FRED` 建议接管的宏观 / 利率序列
- [x] `Tiingo` 建议接管的美股标的范围
- [x] 暂不替换的数据范围
- [x] `config.yaml` 的目标重构方向
- [x] 下一步实际编码顺序

归档位置：
- [x] `DEVELOPMENT_PLAN.md`
- [x] `reports/phase0_strategy_change_log.md`
- [x] 本附件

## W2.8 本周成功标准

### W2.8.1 硬门槛
- [x] 明确形成“FRED 先、Tiingo 后、yfinance 保留 fallback”的项目级结论
- [x] 明确 FRED 的首批序列清单
- [x] 明确 Tiingo 的首批标的清单
- [x] 明确哪些数据源不在本周替换范围内
- [x] 明确下一步实施顺序：**先实现 FRED，再实现 Tiingo**

### W2.8.2 软判断
- [x] 数据源职责边界清楚
- [x] 不与当前正式链路冲突
- [x] 不引入一次性大替换风险
- [x] 文档口径统一

## W2.9 本周不做事项

- [x] 不重写 `phase0` 回测逻辑
- [x] 不改当前 A 股 Tushare 主链路
- [x] 不直接移除 `yfinance`
- [x] 不把 FRED / Tiingo 一起一次性硬切进生产链路
- [x] 不处理 CNH / FX 主源替换
- [x] 不推进前端 / PWA / agent 自动化扩展

## W2.10 本周结束后的分流

### W2.10.1 如果本周方案成熟
- [x] 下一周进入 **FRED 实现周**
- [x] FRED 稳定后再进入 **Tiingo 接入周**
- [x] 港股映射 A 股候选策略后续补代码，先完成 `hk_market_history.sqlite` 数据质量验证；2026-06-02 已确认 Tiingo 不适合作为港股正式源，港股链路继续保持预留状态
- [x] 港股映射策略记录见：`tasks/cross-market/HK_A_SHARE_MAPPING_STRATEGIES.md`
- [x] 港股库完成 30 标的批量落库与验收报告：`reports/hk_market_history_batch_load_report.md`（coverage `30/30`，latest `2026-06-01`）

### W2.10.2 如果本周方案不充分
- [ ] 继续保持 `yfinance` 不动
- [ ] 先补完 FRED 序列定义和用途口径
- [ ] 推迟 Tiingo 实现

---

## W2.11 结尾提醒

> 统一附件的目的不是增加文档数量，而是把“当前周”和“后续周”都放进同一个执行清单里，保持项目附件简洁、高效、连续可维护。

## W2.12 统一调度器后续待解决事项

参考专项任务：[`tasks/ops/SCHEDULER_PIPELINE_TASKS.md`](ops/SCHEDULER_PIPELINE_TASKS.md)

### W2.12.0 已完成基线

- [x] 统一调度器 `scripts/run_project_scheduler.sh` 已作为项目内唯一 cron 入口。
- [x] `07:20` 调度任务已从旧 `daily-brief` 兼容入口切换为 `brief watchlist`。
- [x] 阶段试用观察池已固定生成 `reports/watchlist_today/index.html`。
- [x] 阶段试用观察池已在程序内执行 ECS 同步，远端目录默认为 `BRIEF_SYNC_REMOTE_DIR=/brief/`。
- [x] 当前 `brief` 命令路由已整理为 `brief daily`、`brief watchlist`、`brief premarket`、`brief account-bill`。
- [x] 模拟账户 SQLite 主账本已接入 watchlist pipeline，当前能维护账户配置、日资产、成交流水和持仓快照。
- [x] watchlist 与正式模拟账单边界已明确：watchlist 是计划层，正式账单只记录本地 OHLCV 已确认的执行日。

### W2.12.1 交易日判断

- [ ] 当前调度器仍按周一到周五判断，不等同于交易所交易日历。
- [ ] A 股任务需要读取 `data/manual_history/a_share_history.sqlite` 的 `trading_calendar`。
- [ ] 港股任务需要独立交易日历或数据源最新交易日判断。
- [ ] 美股任务需要独立交易日历或数据源最新交易日判断。
- [ ] 日报任务需要和 A 股下一个盘前检查日绑定。

### W2.12.2 失败重试

- [ ] 当前任务只有精确分钟触发，失败后实际重试能力不足。
- [ ] 每个任务需要运行窗口，例如 `07:20-07:40`。
- [ ] 每个任务需要最大重试次数，例如 `3` 次。
- [ ] 每个任务需要重试间隔，例如 `5` 分钟。
- [ ] 失败次数、最后失败时间、最后错误摘要需要写入调度状态文件。

### W2.12.3 正式日报产物后续拆分

- [ ] 当前 `brief daily` 仍复用 `brief watchlist` 阶段试用观察池代码。
- [ ] 后续需要独立重写正式 daily brief 产物生成代码。
- [ ] 正式 daily brief 应在观察池之外增加市场状态、账户变动、风险解释、候选变化和外部事件摘要。
