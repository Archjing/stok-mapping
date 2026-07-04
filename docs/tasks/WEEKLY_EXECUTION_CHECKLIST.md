# T0｜周执行计划总清单（开发计划书附件）

> 本文件是 `docs/DEVELOPMENT_PLAN.md` 的统一周执行附件。  
> 后续每一周的任务清单都追加在同一个文件中，避免多个附件分散。  
> 主计划中的长期路线、阶段划分和项目定位以 `docs/DEVELOPMENT_PLAN.md` 为准；本文件只管理**当前周目标、执行节奏、检查点与归档要求**。
> 任务拆解总索引见：[`docs/tasks/README.md`](./README.md)。

---

# W3｜当前阶段：策略池完善、文档同步与架构收口

## W3.0 当前目标

当前主线不是继续扩大候选数量，而是在 `qfq_asof`、PIT 股票池、成本后、过拟合、行业集中、因子诊断和 `strategy-admission` 口径下，把策略池治理成可复查、可解释、可迭代的研究资产。

优先目标：

- [ ] 按 `baseline_admission_all_v1` 当前 13 个候选重跑全量 admission，并落盘日期、背景、命令、数据口径、候选结论和治理动作明确的报告
- [ ] 完成 13 个默认候选的策略角色卡和治理状态枚举：`active_research`、`baseline`、`failure_sample`、`research_only`、`deferred` 或 `admission_pass_candidate`
- [ ] 继续推进低波、低换手、质量和 sleeve 降 churn 主线，重点解释相对沪深300跑输、参数不稳定、行业集中、换手成本和正超额折比例不足
- [ ] 把 T5.2 情报库和 T2.13 因子传导框架用于失败归因、特征注册和策略选择方法论，不直接改写策略权重
- [x] 同步 `docs/DEVELOPMENT_PLAN.md`、`README.md` 和 `docs/PROJECT_ARCHITECTURE_OVERVIEW.md` 到当前代码与目录状态

## W3.1 工程边界

- [x] 主分支只承载全局代码、配置、目录规则和解释这些规则的文档
- [x] 常规 `reports/`、`logs/` 和 SQLite 数据库作为本地运行资产维护，不随远端 Git 同步
- [x] `reports/` 根目录白名单为：`archive/`、`runs/`、`database_health/`、`strategy_admission/`、`phase0/`、`strategy_governance/` 和 `README.md`
- [x] Python 模块分层已完成一轮 main 集成：`data_access`、`data_governance`、`research`、`reporting`、`execution`、`intelligence`、`strategies`
- [ ] 后续 Python 精简应以“合并重复逻辑、删除过期兼容、减少行数”为目标，不再只做机械拆分

## W3.2 验收标准

- [ ] 全候选 admission 报告覆盖 13 个默认候选，报告能区分 reject / retest / research_only / eligible_for_paper_review
- [ ] 每个候选都有角色、适用市场环境、失败模式、相对基准表现和下一步动作
- [ ] 新产生的报告默认写入 `reports/runs/...` 或白名单分类目录，不新增根目录杂项
- [ ] 文档中候选数量、CLI 入口、报告目录、数据源角色和架构边界与实际代码一致
- [ ] 重要 Harness / 策略治理迭代结束后，有简明中文报告或 briefing，避免只在会话窗口留下抽象结论

---

# W1｜本土主策略候选验证（已完成并归档）

## W1.0.1 本周目标

> 在现有 compare / report / gate 链路下，验证 A 股本土候选策略，修正候选比较口径，并判断当前失败到底来自策略逻辑、参数、样本治理还是交易成本。

## W1.0.2 当前基线与门槛缺口

### W1.0.2.1 当前基线
- 当前 selected candidate：无；`legacy_momentum_low_turnover_v1` 仅保留为旧 `qfq_current` 兼容基线
- 当前 gate：严格 `qfq_asof` 口径未通过
- 当前口径：portfolio-scope
- 当前样本：7 年窗口，4 个 portfolio fold

### W1.0.2.2 当前缺口
- 严格 `qfq_asof` 口径下当前仍有门禁缺口；以下数值仅作为旧 `qfq_current` 兼容参考
- `annualized_return_mean = 0.1331`
- `sharpe_mean = 1.0083`
- `max_drawdown_mean = -0.1042`
- `win_rate_mean = 0.5110`
- 当前主测试成本口径：`slippage = 0.00246`，`commission = 0.00025`，`stamp_duty_sell = 0.0005`

### W1.0.2.3 当前判断
- 低换手改造曾在旧 `qfq_current` 口径下替代旧 `legacy_momentum` 成为主候选，但已被严格 `qfq_asof` 复核降级。
- 当前主要工作已回到“在严格口径下重建有效 candidate，同时维护解释链路、账户仿真约束和日常输出”。
- 成本敏感性仍保留单独 CLI 路径；旧 `qfq_current` / `main_personal_execution` 结论只能作为兼容参考，不能替代当前准入判断。

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

参考文档：`docs/tasks/strategy/STRATEGY_BLOCKS_PLAN.md`

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
- [x] 当前不再优先加因子复杂度，先完成低换手策略收口、执行诊断与账户约束

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
- [x] `reports/phase0/phase0_cost_sensitivity_report.md`

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
- [x] 当时在旧 `qfq_current` 口径下曾提升为主候选，后经严格 `qfq_asof` 复核已降级
- [x] 在变更日志中记录晋级原因
- [x] 进入下一轮更细的参数与稳定性验证

### W1.0.11.2 如果没有候选通过 gate
- [x] 保留 `ma_kline_baseline_v1` 作为诊断地板
- [x] 保留 `legacy_momentum` 作为 portfolio baseline
- [x] residual / multifactor 不再作为 W1.5 主线继续补研发，仅保留低换手改造方向作为后续备选
- [x] 下一轮重点转向：**持有期、换手、滑点敏感性控制**，而不是继续加大因子复杂度

---

# W1.5｜Sharpe 修复与成本敏感性收敛

## W1.5.1 本周目标

- [x] 在当时旧 `qfq_current` / current-cost 假设下将候选 `sharpe_mean` 提升到 `> 0.5`
- [x] 保持 `max_drawdown_mean > -0.25`
- [x] 保持 `win_rate_mean > 0.45`
- [x] 降低 current-cost 与 low-slippage 场景之间的表现差距

## W1.5.2 当前基线

- 旧 `qfq_current` 兼容基线：`legacy_momentum_low_turnover_v1`（当前无 selected candidate）
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
- [x] 降低交易频率方向已归档为后续备选，不在 W1.5 继续补研发
- [x] 避免短周期反转信号导致频繁换仓的要求已转入后续备选研发约束
- [x] 已确认不进入当前主线，只保留为后续备选

### W1.5.3.3 multifactor slippage-aware 版本
- [x] 对 `amount_ratio20`、波动率、上影线等交易质量过滤的重设已归档为后续备选，不在 W1.5 继续补研发
- [x] 增加持有期或调仓频率限制的要求已转入后续备选研发约束
- [x] 已确认 current-cost 下未胜出，暂不继续占用当前主线

## W1.5.4 验收要求

- [x] 每次策略逻辑或参数修改都写明理由和参考依据
- [x] 成本敏感性测试改为显式路径，按需要输出 base / main / stress / low / zero 等场景
- [x] 不用零成本结果替代 current-cost gate
- [x] 不因单个 fold 表现好直接晋级
- [x] 变更写入 `reports/phase0_strategy_change_log.md`

## W1.5.5 归档结论

- [x] W1.5 在当时旧 `qfq_current` / current-cost 口径下完成：`legacy_momentum_low_turnover_v1` 的 `sharpe_mean = 1.0083`，`max_drawdown_mean = -0.1042`，`win_rate_mean = 0.5110`。
- [x] 成本敏感性证据见 `reports/phase0/phase0_cost_sensitivity_report.md`：`main_personal_execution` Sharpe `1.0083`，`low_slippage` Sharpe `1.0094`，二者差距可解释。
- [x] residual / multifactor 在 current-cost 下未胜出，不作为 W1.5 继续研发范围；后续若重开，必须以低换手、持有期和滑点敏感性为硬约束。
- [x] 后续严格 `qfq_asof` 复核已推翻旧口径 selected candidate 解释；`legacy_momentum_low_turnover_v1` 当前只作为兼容 baseline 与研究样本，不代表可进入模拟或实盘。

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
- [x] 为未来通过严格 `qfq_asof` 门禁的 candidate 预留接入 `07:30` 盘前日报 / 观察池输出的链路
- [x] 补连续样本外资金曲线验证，避免把 walk-forward 分折重置误读成长期横盘
- [x] 生成“连续 OOS 资金曲线 + 基准对比 + 各 fold 收益分解”HTML 报表
- [x] 补行情分段验证，区分顺风行情与更普遍的策略有效性
- [x] 将 `execution-gate` 做成独立“实盘仿真回测”管线，支持 `research` / `live` profile
- [x] 将 `oos-report` 补齐 `--profile` 参数，保持与 `execution-gate` 相同配置逻辑
- [x] 统一 HTML 报表展示体验：生成时间、横向滚动、纵向滚动和固定表头

## W1.6.2 当前状态

- [x] 当时旧 `qfq_current` selected candidate：`legacy_momentum_low_turnover_v1`；现已降级为兼容基线
- [x] 当时旧 `qfq_current` / current-cost gate：PASS；现不能作为当前准入依据
- [x] 策略账单导出脚本：`scripts/export_strategy_bill.py`（旧 `scripts/export_low_turnover_bill.py` 保留兼容）
- [x] 账单导出缓存：默认 `reports/cache/low_turnover_panel.pkl`
- [x] 预览产物：`reports/phase0_low_turnover_bill_preview.html`
- [x] 日资产产物：`reports/phase0_low_turnover_daily_assets.csv`
- [x] 连续 OOS 报表脚本：`scripts/export_strategy_oos_report.py`（旧 `scripts/export_low_turnover_oos_report.py` 保留兼容）
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
- [x] 最后把未来通过严格 `qfq_asof` 门禁的 candidate 输出接入日报 / 观察池

## W1.6.4 通过后执行优先级表

| 优先级 | 任务 | 目的 | 完成标准 |
| --- | --- | --- | --- |
| `P0` | 账单导出正式化 | 把当前单独脚本产物纳入统一回测输出，保证每次 Phase 0 重跑后账单和日资产自动更新。 | `phase0 run` 后稳定产出账单 CSV、日资产 CSV 和 HTML 预览。 |
| `P0` | 账户级实盘约束 | 让组合权重回测更接近 A 股真实执行。 | 支持 `100` 股整手、现金检查、卖出回款和账户余额联动。 |
| `P1` | 连续 OOS 与基准对比报表 | 纠正 fold 重置带来的阅读偏差，直接回答“是否只是跟上行情”。 | 有连续拼接后的样本外资金曲线、基准曲线和 fold 收益分解表。 |
| `P1` | 行情分段验证 | 识别策略是不是只在顺风阶段有效。 | 能按顺风 / 震荡 / 回撤等阶段输出分段表现。 |
| `P1` | 财务因子 PTI 校验 | 为后续质量成长 / 多因子扩展建立可信时间线。 | 明确公告日可见性规则，并形成校验结论。 |
| `P1` | 日报 / 观察池接入 | 仅在严格 `qfq_asof` 门禁通过后，让候选进入日常使用链路。 | 当前无 selected candidate；`07:30` 输出现阶段只可引用旧 `qfq_current` 兼容基线或留空，待未来重新产生合格 candidate 后再恢复正式接入。 |
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

- [x] 当前账单脚本：`scripts/export_strategy_bill.py`（旧低换手入口保留兼容）
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
- [x] 真实账户持仓 CSV 输入格式预留：`docs/tasks/account/ACCOUNT_RECONCILIATION_CSV_SCHEMA.md`
- [x] 券商成交回报 CSV 输入格式预留：`docs/tasks/account/ACCOUNT_RECONCILIATION_CSV_SCHEMA.md`

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
- [x] 港股映射策略记录见：`docs/tasks/cross-market/HK_A_SHARE_MAPPING_STRATEGIES.md`
- [x] 港股库完成 30 标的批量落库与验收报告：`reports/hk_market_history_batch_load_report.md`（coverage `30/30`，latest `2026-06-01`）

### W2.10.2 如果本周方案不充分
- [ ] 继续保持 `yfinance` 不动
- [ ] 先补完 FRED 序列定义和用途口径
- [ ] 推迟 Tiingo 实现

---

## W2.11 结尾提醒

> 统一附件的目的不是增加文档数量，而是把“当前周”和“后续周”都放进同一个执行清单里，保持项目附件简洁、高效、连续可维护。

## W2.12 统一调度器后续待解决事项

参考专项任务：[`docs/tasks/ops/SCHEDULER_PIPELINE_TASKS.md`](ops/SCHEDULER_PIPELINE_TASKS.md)

### W2.12.0 已完成基线

- [x] 统一调度器 `scripts/run_project_scheduler.sh` 已作为项目内唯一 cron 入口。
- [x] `07:20` 调度任务已从旧 `daily-brief` 兼容入口切换为 `brief watchlist`。
- [x] 阶段试用观察池已固定生成 `reports/watchlist_today/index.html`。
- [x] 阶段试用观察池已在程序内执行远端同步，远端目录优先读取 `BRIEF_SYNC_REMOTE_DIR`，未设置时 fallback 到代码默认静态站点目录。
- [x] 模拟账户确认账单已接入 latest 镜像与远端同步，存在账单 HTML 时输出 `reports/account_bill_today/index.html` 并同步到 `ACCOUNT_BILL_SYNC_REMOTE_DIR`。
- [x] 当前 `brief` 命令路由已整理为 `brief daily`、`brief watchlist`、`brief premarket`、`brief account-bill`。
- [x] 模拟账户 SQLite 主账本已接入 watchlist pipeline，当前能维护账户配置、日资产、成交流水和持仓快照。
- [x] watchlist 与正式模拟账单边界已明确：watchlist 是计划层，正式账单只记录本地 OHLCV 已确认的执行日。
- [x] 会话归档目录边界已调整：人工会话记忆统一进入 `memory/session_archive/`，机器运行日志保留在 `logs/`，程序报告保留在 `reports/`。

### W2.12.1 交易日判断

- [x] 当前调度入口已由 shell weekday 判断迁移到 `maintain tick`，A 股任务不再只按周一到周五判断。
- [x] A 股任务已读取 `data/manual_history/a_share_history.sqlite` 的 `trading_calendar`。
- [ ] 港股任务仍需独立交易日历或数据源最新交易日判断；当前为 weekday fallback，并显式记录 fallback reason。
- [ ] 美股任务仍需独立交易日历或数据源最新交易日判断；当前为 weekday fallback，并显式记录 fallback reason。
- [x] 日报任务已绑定 A 股交易日历；watchlist 内的下一个 `07:30` 复核时间也读取 `trading_calendar`。

### W2.12.2 失败重试

- [x] 当前任务已由每分钟 cron 调用 `maintain tick`，失败后可在 retry window 内重试，不再只依赖精确分钟触发。
- [x] 每个任务已通过 `schedule_value + retry_window_minutes` 实现等效运行窗口，例如 `07:20` 加 `20` 分钟 retry window。
- [x] 每个任务已支持最大重试次数，默认 `3` 次，可通过 `*_MAX_RETRIES` 环境变量覆盖。
- [x] 每个任务已支持重试间隔，默认 `5` 分钟，可通过 `*_RETRY_INTERVAL_MINUTES` 环境变量覆盖。
- [x] 失败次数、最后失败时间、最后错误摘要已写入 `logs/scheduler/<task_name>.state`。

### W2.12.3 正式日报产物后续拆分

- [ ] 当前 `brief daily` 仍复用 `brief watchlist` 阶段试用观察池代码。
- [ ] 后续需要独立重写正式 daily brief 产物生成代码。
- [ ] 正式 daily brief 应在观察池之外增加市场状态、账户变动、风险解释、候选变化和外部事件摘要。

---

## W2.13 策略过拟合诊断工具 MVP（T2.4）

参考专项任务：[`docs/tasks/strategy/STRATEGY_OVERFITTING_DIAGNOSTIC_TOOL.md`](strategy/STRATEGY_OVERFITTING_DIAGNOSTIC_TOOL.md)

### W2.13.0 立项定位

> `T2.4` 不再只是附属文档。它是策略治理主线的一部分，用来补齐 effectiveness gate 无法覆盖的过拟合风险、参数脆弱性、收益集中度和成本敏感性判断。

### W2.13.1 本周目标

- [x] 冻结过拟合诊断报告 schema
- [x] 实现只读现有产物的 MVP，不触发重新回测
- [x] 新增 `phase0.cli overfit-diagnostic`
- [x] 输出 CSV / Markdown 诊断报告
- [x] 至少覆盖当时旧 `qfq_current` 主候选 / 当前兼容基线：`legacy_momentum_low_turnover_v1`
- [x] 报告结论能解释风险来源，而不是只给分数
- [x] 不改变现有 `phase0 run`、walk-forward、effectiveness gate 的默认行为

### W2.13.2 输入产物

- [x] `reports/phase0_walk_forward_candidates.csv`
- [x] `reports/phase0_walk_forward_folds.csv`
- [x] `reports/phase0_effectiveness_report.md`
- [x] `reports/phase0/phase0_cost_sensitivity.csv`，若存在则读取
- [x] `config.yaml`

### W2.13.3 输出产物

- [x] `reports/overfit_diagnostic/strategy_overfit_diagnostic.csv`
- [x] `reports/overfit_diagnostic/strategy_overfit_diagnostic.md`
- [ ] 后续增强：`reports/overfit_diagnostic/strategy_overfit_diagnostic.html`

### W2.13.4 MVP 诊断维度

#### W2.13.4.1 OOS / fold 稳定性

- [x] 读取每个候选的 fold 级年化、Sharpe、最大回撤、胜率、换手
- [x] 计算正收益折占比
- [x] 计算最差 fold 表现
- [x] 标记“只靠最后一折拉高”的风险
- [x] 标记 OOS 折数不足的证据风险

#### W2.13.4.2 成本敏感性

- [ ] 若成本敏感性 CSV 存在，读取不同 scenario 的结果
- [ ] 检查 research / live / stress 口径下是否仍为正收益
- [ ] 检查滑点升高后 Sharpe 和年化是否快速坍塌
- [x] 对高换手候选上调风险分

#### W2.13.4.3 参数稳定性占位

- [x] 第一版先从 `selected_params` 解析参数变化
- [x] 记录各 fold 选中参数是否高度集中或频繁切换
- [x] 标记“尚未执行参数邻域扰动”的待验证风险
- [ ] 后续再增加 `--run-param-perturbation`

#### W2.13.4.4 收益集中度占位

- [x] 第一版先标记为 `not_available`
- [x] 明确后续需要账户账单 / 单票收益贡献输入
- [x] 不用空字段伪装已完成诊断

### W2.13.5 评分与等级

- [x] 使用 `0-100` overfit score，分数越高风险越高
- [x] 等级：`low / medium / high / critical`
- [ ] 初始权重：
  - [ ] OOS / fold 稳定性：`35`
  - [ ] 成本敏感性：`25`
  - [ ] 参数稳定性：`20`
  - [ ] 收益集中度：`10`
  - [ ] 数据挖掘 / 候选数量风险：`10`
- [x] 输出 `recommended_action`：`keep / observe / retest / reject`

### W2.13.6 代码拆分

- [x] 新增 `phase0/overfit.py`
- [x] 在 `phase0/cli.py` 增加 `overfit-diagnostic` 子命令
- [x] 在 `phase0/reporting.py` 增加 Markdown 报告输出函数，或在 `phase0/overfit.py` 内保持 MVP 输出
- [x] 避免循环导入，不复用私有回测函数触发新回测
- [x] 保持输出路径可通过 CLI 覆盖

### W2.13.7 CLI 设计

```bash
python -m phase0.cli overfit-diagnostic --config config.yaml
```

可选：

```bash
python -m phase0.cli overfit-diagnostic \
  --config config.yaml \
  --candidates reports/phase0_walk_forward_candidates.csv \
  --folds reports/phase0_walk_forward_folds.csv \
  --output-dir reports/overfit_diagnostic
```

### W2.13.8 验收标准

- [x] 命令可运行并生成 CSV / Markdown
- [x] 当时旧 `qfq_current` 主候选 / 当前兼容基线出现在报告中
- [x] 所有 compare 候选都有风险等级
- [x] 报告展示每个候选的主要风险原因
- [x] 对 OOS 折数不足、负收益折、最差 fold 超阈值、高换手、高成本敏感性给出明确标记
- [x] 不破坏 `phase0 run`
- [x] 不改变当时旧 `qfq_current` 主候选的历史归档结论
- [x] 不把过拟合分数当成交易信号

### W2.13.9 后续集成规则

- [ ] `execution-gate` 后续读取 overfit report，作为附加治理结论
- [ ] `brief watchlist` 后续展示当前兼容基线或未来新 candidate 的 overfit risk 摘要
- [ ] `overfit_risk_level = high / critical` 时，不允许新策略直接作为准入候选进入观察池长期试用
- [ ] 新增策略进入 compare 前，必须保存完整候选结果，避免只记录 winner

## W2.14 A 股历史 as-of 前复权与复权因子治理（T1.4）

参考专项任务：[`docs/tasks/data-sources/ASOF_PRICE_ADJUSTMENT_GOVERNANCE_TASKS.md`](data-sources/ASOF_PRICE_ADJUSTMENT_GOVERNANCE_TASKS.md)

### W2.14.0 立项定位

> `T1.4` 用来封住价格特征层的 future leakage：回测某个历史 as-of date 时，只能使用该日之前可见的未复权价格和复权因子，不能把未来分红送转导致的全历史前复权变化折回过去。

### W2.14.1 本周目标

- [x] 审计当前本地 A 股日线库是否同时具备 `bfq_raw`、`qfq_current` 和每日复权因子
- [x] 明确当前 `phase0` 回测实际使用的价格口径
- [x] 冻结 `market_adj_factors` 表结构和导入规则
- [x] 设计并实现 `qfq_asof` 最小 loader，先不静默改变现有默认回测行为
- [x] 新增 `adjustment-audit` 报告，标记当前策略结果是否存在复权未来函数风险
- [x] 输出 `qfq_current` / `qfq_asof` 差异样例，覆盖除权除息样本股和普通样本股

### W2.14.2 输入产物

- [x] 本地历史库中的 A 股日线 OHLCV 表
- [x] 当前 `phase0/local_history.py` 行情加载逻辑
- [x] 当前 `phase0/walk_forward.py` 特征生成和训练窗口边界
- [x] Tushare 或其他数据源可提供的未复权日线与复权因子字段
- [x] `config.yaml`

### W2.14.3 输出产物

- [x] `reports/price_adjustment_audit.csv`
- [x] `reports/price_adjustment_audit.md`
- [ ] 后续增强：`reports/price_adjustment_audit.html`
- [x] 新增或预留 `market_adj_factors` 表
- [x] 新增 `phase0/adjustment.py`
- [x] 扩展后的历史行情加载参数：`price_adjustment = bfq_raw / qfq_current / qfq_asof`

### W2.14.4 P0 数据可用性审计

- [x] 列出本地库已有的价格字段和表名
- [x] 检查是否有未复权 OHLCV
- [x] 检查是否有当前全历史前复权 OHLCV
- [x] 检查是否有按股票、交易日保存的复权因子
- [ ] 检查停牌日、除权除息日、复权因子跳变日覆盖情况
- [x] 若缺少 `bfq_raw` 或复权因子，报告必须标记为 `cannot_build_qfq_asof`

### W2.14.5 P1 复权因子落表

- [x] 新增 `market_adj_factors` 表结构设计
- [x] 字段至少包含 `market`、`symbol`、`date`、`adj_factor`、`source`、`updated_at`
- [x] 对同一 `market / symbol / date / source` 建唯一约束
- [x] 导入链路支持幂等更新
- [x] 不用字符串拼接推导复权因子，必须来自结构化字段或可信数据源
- [x] 2026-06-04 执行 Tushare 历史补全：`backfill-tushare-history --start-date 2016-01-01 --end-date 2026-06-04 --no-financial --max-requests-per-minute 180`
- [x] `market_adj_factors` 验收：2016-01-04 到 2026-06-04，交易日覆盖完整，`adj_factor` 非空率 100%
- [x] `market_daily_basic` 验收：2016-01-04 到 2026-06-03，`pb_ratio` 覆盖率约 99.37%，`pe_ratio` 覆盖率约 81.47%，`turnover_rate` 覆盖率 100%
- [x] 输出 Tushare 补全验收报告：`reports/tushare_history_backfill_audit.md` / `reports/tushare_history_backfill_audit.csv`
- [x] 后续单独批次补齐 Tushare 财务因子 2016Q1-2018Q1；当前 `market_financial_factors` 已覆盖 2016-03-31 到 2026-03-31
- [x] 更新 `data/manual_history/README.md`：重定义 `a_share_history.sqlite` 为 A 股研究主库，而不是“离线缓存 / fallback”；明确 `bfq_raw / qfq_current / qfq_asof / market_adj_factors / market_daily_basic / market_financial_factors / source audit` 的职责边界，以及 `import-history`、`update-history`、`backfill-tushare-history`、`backfill-tushare-financials`、`update-financials` 的维护分工

### W2.14.6 P2 `qfq_asof` loader MVP

- [x] 新增 `phase0/adjustment.py`
- [x] 实现 `compute_qfq_asof(raw_ohlcv, adj_factors, as_of_date)`
- [x] 只读取 `date <= as_of_date` 的复权因子
- [x] 计算公式固定为 `qfq_asof(t, asof) = bfq_raw(t) * adj_factor(t) / adj_factor(asof)`
- [x] `volume`、`amount`、`turnover` 不按价格复权比例乱调，保持原始成交含义
- [x] 交易执行仍使用 `bfq_raw`，不使用复权价成交

### W2.14.7 P3 walk-forward 接入计划

- [x] 在历史行情加载函数中增加显式 `price_adjustment` 参数
- [x] 当 `price_adjustment = qfq_asof` 时，必须传入当前训练折的 `as_of_date`
- [x] walk-forward 每折使用训练窗口结束日作为 `as_of_date`
- [ ] 后续增强：验证期逐日滚动 `as_of_date`，默认不启用，避免把验证期价格构造成本放大约一个交易年倍数
- [x] 保留 `qfq_current` 兼容口径，但报告中必须标记为非严格 point-in-time
- [x] 对 `legacy_momentum_low_turnover_v1` 跑一次 `qfq_current` / `qfq_asof` 对照

### W2.14.8 CLI 设计

```bash
python -m phase0.cli adjustment-audit --config config.yaml
```

可选：

```bash
python -m phase0.cli adjustment-audit \
  --config config.yaml \
  --sample-size 200 \
  --output reports/price_adjustment_audit.md
```

### W2.14.9 验收标准

- [x] 审计命令可运行并输出 CSV / Markdown
- [x] 报告能明确区分 `bfq_raw`、`qfq_current`、`qfq_asof`
- [x] 缺少未复权价格或复权因子时，报告明确标记无法进行 as-of 前复权
- [x] `qfq_asof` 计算不会使用 `as_of_date` 之后的复权因子
- [x] 现有 `phase0 run` 默认行为不被静默改变
- [x] 执行成交、涨跌停、停牌判断继续基于真实未复权价格
- [x] 报告给出当前主策略价格口径 future leakage 风险结论
- [x] 报告列出 `qfq_current` 与 `qfq_asof` 的价格和核心特征差异样例

---

# W2.15｜有效量化策略重建：因子诊断与低频低换手候选

参考专项任务：[`docs/tasks/strategy/EFFECTIVE_QUANT_STRATEGY_RESEARCH_TASKS.md`](strategy/EFFECTIVE_QUANT_STRATEGY_RESEARCH_TASKS.md)

## W2.15.1 当前结论

- [x] 最新版本全候选策略池 `qfq_asof` compare 已完成
- [x] 当前无可用于实盘模拟的合格 candidate
- [x] `legacy_momentum_low_turnover_v1` 降级为兼容基线和动量 sleeve 研究样本
- [x] 下一步研发主线从“调动量候选”切换为“因子有效性诊断 -> 低频低换手多因子策略”

## W2.15.2 本周目标

- [x] 实现 `T2.5` 因子有效性诊断报告 MVP
- [x] 用 `qfq_asof` / PIT 股票池跑第一批低波、低换手、质量、动量、反转因子诊断
- [x] 基于诊断结果确认 `low_vol_low_turnover_quality_v1` 的首版因子权重
- [x] 设计 walk-forward 窗口 preset，已落地 `baseline_2y_1y`、`quality_3y_1y` 与 `quality_4y_1y`
- [x] 建立 `strategy-admission` 报告 MVP，明确实盘模拟准入规则

## W2.15.3 第一优先级任务

- [x] 新增 `phase0/factor_effectiveness.py`
- [x] 新增 CLI：`python -m phase0.cli factor-effectiveness --config config.yaml`
- [x] 输出 `reports/factor_effectiveness/factor_effectiveness.csv`
- [x] 输出 `reports/factor_effectiveness/factor_effectiveness.md`
- [x] 输出 `reports/factor_effectiveness/factor_group_returns.csv`
- [x] 输出 `reports/factor_effectiveness/factor_ic_by_year.csv`
- [x] 输出 `reports/factor_effectiveness/factor_correlation.csv`

## W2.15.4 第二优先级任务

- [x] 新增 `low_vol_low_turnover_quality_v1` 策略说明文档
- [x] 新增 `quality_low_turnover_monthly_v1` 策略说明文档
- [x] 设计两者在 `phase0/strategies/` 中的实现接口
- [x] 明确调仓周期、top_n、换手上限、行业约束、单票权重上限；已新增通用策略修饰层 `strategy_v2.constraints`，行业约束支持 `audit/enforce`
- [x] 制定并实现回测窗口期配置模块 V1（KISS 收缩版）：先解决 T2.7 折数不足和窗口单一问题
- [x] 扩展 walk-forward preset schema：支持 `start_date` / `end_date`、`expected_folds`
- [x] 新增 `baseline_2y_1y_5fold`：固定 `2019-04-01` 到 `2026-03-31`，作为所有策略第一道公共 smoke/admission baseline
- [x] 新增 `quality_3y_1y_4fold`：固定 `2019-04-01` 到 `2026-03-31`，作为低频质量/低估值策略专用窗口
- [x] `strategy-admission` 报告输出 `expected_folds`、`actual_folds`、`window_start`、`window_end`、`fold_generation_warning`
- [x] `strategy-admission` 支持默认 `strategy_set`、CLI `--strategy-set`、CLI `--strategies` 覆盖和 `diagnostics.suites`
- [x] `strategy-admission` 启动时打印 walk-forward preset 自然语言说明：训练期、验证期、固定起止日期、预计折数和滚动方式
- [x] `strategy-admission` 报告可信化：用 `price_adjustment_status`、`account_execution_status`、`industry_diagnostic_status`、`financial_diagnostic_status` 区分真实数值与未启用/不可用诊断
- [x] admission 默认要求 `qfq_asof`，并在报告中把非 `qfq_asof` 口径作为准入阻断原因
- [x] 行业约束默认进入 `audit` 模式，admission 可输出真实行业集中度并在超限时阻断准入
- [x] 用 T2.7 跑 `baseline_2y_1y_5fold` + `quality_3y_1y_4fold`，复核能否区分折数不足、参数不稳定、收益不达标和组合构造失败
- [ ] 后续补完整 `qfq_current` / `qfq_asof` 双口径矩阵，不只依赖当前默认 `qfq_asof` 硬阻断
- [ ] V2 候选暂不实施：`momentum_1y_6m`、`short_horizon_6m_3m`、`event_rolling_n_events`、`ml_purged_walk_forward`、`validation_family`、`strategy_window_policy`
- [x] 策略准入报告应输出窗口稳健性矩阵，低频质量策略至少比较 `baseline_2y_1y`、`quality_3y_1y` 和 `quality_4y_1y`

## W2.15.5 验收标准

- [x] 因子诊断必须使用 `qfq_asof` 价格特征
- [x] 因子诊断必须使用 point-in-time 股票池
- [x] 财务因子必须保留公告日 point-in-time 说明
- [x] 报告必须能区分“因子无效”“数据覆盖不足”“组合构造失败”
- [x] 在 T2.5 完成前，不新增复杂 ML 主策略

---

# W2.16｜Tushare 财务因子逐股票历史补齐（T1.5）

## W2.16.1 立项定位

立项时 `market_financial_factors` 覆盖 2018-06-30 到 2026-03-31。为了让质量类因子在更长历史窗口中可用，需要补齐 2016Q1-2018Q1。当前 T1.5 已完成目标季度末补齐，主表覆盖已前推到 2016-03-31；本节保留立项背景、执行记录和验收结果。

## W2.16.2 目标季度

- [x] `2016-03-31`
- [x] `2016-06-30`
- [x] `2016-09-30`
- [x] `2016-12-31`
- [x] `2017-03-31`
- [x] `2017-06-30`
- [x] `2017-09-30`
- [x] `2017-12-31`
- [x] `2018-03-31`

## W2.16.3 目标字段

- [x] `announce_date`
- [x] `roe`
- [x] `revenue`
- [x] `revenue_growth`
- [x] `net_profit`
- [x] `profit_growth`
- [x] `operating_cash_flow`
- [x] `operating_cash_flow_to_net_profit`
- [x] `debt_to_asset`
- [x] `total_assets`
- [x] `total_liabilities`
- [x] `total_equity`
- [x] `source`
- [x] `updated_at`

## W2.16.4 代码任务

- [x] 新增财务回填专用进度表：`tushare_financial_backfill_tasks`
- [x] 任务粒度固定为 `period + symbol`
- [x] 状态枚举：`pending / fetched / empty / failed`
- [x] 记录 `request_count`、`last_error`、`updated_at`
- [x] 从 `market_stocks` 生成目标 symbol：`list_date <= period`，且 `delist_date` 为空或 `delist_date >= period`
- [x] 跳过已有有效记录，避免重复请求
- [x] 不允许空行覆盖已有有效财务记录
- [x] 支持 `retry-failed`
- [x] 支持 `max-runtime-minutes` 到时自动退出
- [x] 支持 `shard-index / shard-count` 分片运行
- [x] 支持 `limit-symbols` 小批量验证
- [x] 支持 `limit-tasks` 小批量验证，且 `0` 明确表示选择 0 个任务
- [x] 执行过程中输出进度：目标任务数、已处理数、完成率、fetched/empty/failed、inserted_rows、rate、elapsed、eta

## W2.16.5 CLI 设计

```bash
python -m phase0.cli backfill-tushare-financials \
  --config config.yaml \
  --start-period 2016-03-31 \
  --end-period 2018-03-31 \
  --max-requests-per-minute 120 \
  --max-runtime-minutes 180 \
  --shard-index 0 \
  --shard-count 1
```

可选参数：

- [x] `--period YYYY-MM-DD`
- [x] `--limit-symbols N`
- [x] `--limit-tasks N`
- [x] `--retry-failed`
- [x] `--replace-existing`
- [x] `--missing-fields-only`
- [x] `--missing-fields field1,field2`
- [x] `--shard-index N`
- [x] `--shard-count N`
- [x] `--max-runtime-minutes N`

## W2.16.6 验收报告

输出：

- [x] 当次详细报告按日期目录输出，文件名带短日期与回填区间
- [x] 汇总报告固定文件名，按运行历史每次追加 1 行关键结论
- [x] `reports/tushare_financial_backfill_audit_summary.csv`
- [x] `reports/tushare_financial_backfill_audit_summary.md`
- [x] `reports/tushare_history_backfill_audit_summary.csv`
- [x] `reports/tushare_history_backfill_audit_summary.md`

验收维度：

- [x] `period`
- [x] `target_symbols`
- [x] `fetched_symbols`
- [x] `empty_symbols`
- [x] `failed_symbols`
- [x] `roe_coverage`
- [x] `revenue_growth_coverage`
- [x] `profit_growth_coverage`
- [x] `cash_flow_quality_coverage`
- [x] `debt_to_asset_coverage`
- [x] `announce_date_coverage`
- [x] Markdown 报告中的覆盖率按百分数展示，CSV 保持 0-1 机器可读口径
- [x] 汇总表每次只新增 1 行，包含运行时间、区间、分片、任务量和关键结论

## W2.16.7 执行顺序

- [x] 单只股票单季度验证：`--period 2016-03-31 --limit-symbols 1`
- [x] 50 只股票单季度验证：`--period 2016-03-31 --limit-symbols 50`
- [x] 默认覆盖行为修正为“跳过已有有效记录”，显式传 `--replace-existing` 时才覆盖
- [x] 200 个任务小批量验证：`--start-period 2016-03-31 --end-period 2018-03-31 --limit-tasks 200 --max-runtime-minutes 10`
- [x] 单季度全市场分批验证
- [x] 跑完 2016Q1-2018Q1 全部季度
- [x] 重试 failed，直到 failed ratio 低于 1%
- [x] 重跑 `financial-pti`
- [x] 重跑 `factor-effectiveness`，观察 `cash_flow_quality` 历史覆盖变化

完成记录（2026-06-06）：2016Q1-2018Q1 全部 9 个目标季度末已完成回填闭环；目标季度末任务状态均为 `pending=0`、`failed=0`，仅保留每季 `empty=2`。本次收尾补跑处理残余任务 `35` 个，其中 `fetched=28`、`empty=7`、`failed=0`，新增审计报告位于 `reports/2026-06-06/tushare_financial_backfill_audit_260606_20160331_20180331.md`。

## W2.16.8 验收标准

- [x] 2016Q1-2018Q1 每个季度均有任务覆盖
- [x] 每季度 `fetched + empty + failed = target_symbols`
- [x] `failed_symbols` 经重试后低于 1%
- [x] 所有有效记录保留 `announce_date`
- [x] `financial-pti` 仍为 PASS
- [x] 不因补历史财务字段改变已存在的有效日线、复权和 daily_basic 数据
- [x] `factor-effectiveness` 已重跑，`cash_flow_quality` 覆盖率 `0.9959` 并列为 `use`

说明：任务表中曾误生成的非目标 period（如 `2017-07-01`、`2017-08-01`、`2017-09-01`、`2017-10-01`、`2017-11-01`）不属于 T1.5 原始季度末验收范围，后续单独清理，不影响 T1.5 验收。

---

# W2.17｜数据库健康检查与数据质量门禁（T6.2）

## W2.17.1 立项定位

基于 `refdocs/dirty_data_avoidance_for_quant_2026-06-03.md` 的数据治理原则，项目需要一个统一的、只读的数据库健康检查入口，在回测、日报和调度任务前识别数据缺失、异常价格、PIT 财务风险、跨市场 freshness 和调度状态问题。

第一版不写数据库健康状态表，只生成 CSV / Markdown 报告和退出码，避免检查模块自身引入新的状态污染。

## W2.17.2 已有能力盘点

- [x] `phase0/quality.py` 已有简单 `QualityResult` / `audit_quality` / `aggregate_quality`
- [x] 已有 `financial-pti`、`universe-pti`、`adjustment-audit` 等专项审计命令
- [x] 已有本地历史一致性旁路校验能力；实现现位于 `phase0.data_governance.local_history_consistency`，`scripts/check_local_history_consistency.py` 只保留兼容入口，但它不是统一 CLI 健康检查入口
- [x] 结论：项目已有分散质量检查能力，但缺少统一、可调度、可作为门禁的数据库健康检查模块

## W2.17.3 MVP 实现范围

- [x] 新增 `phase0/db_health.py`
- [x] 新增 CLI：`python -m phase0.cli db-health --config config.yaml`
- [x] 支持 `--scope all|cn|financial|cross_market|scheduler`
- [x] 支持 `--as-of YYYY-MM-DD`
- [x] 支持 `--output-dir`
- [x] 支持 `--fail-on error|warning|never`
- [x] 输出 `database_health_summary.csv`
- [x] 输出 `database_health_findings.csv`
- [x] 输出 `database_health_report.md`

## W2.17.4 检查维度

### W2.17.4.1 A 股本地库

- [x] 检查本地 SQLite 数据库存在性
- [x] 检查 `market_daily_bars` 表结构
- [x] 检查最新交易日、覆盖率和滞后
- [x] 检查最近窗口 OHLC 逻辑
- [x] 检查非正价格
- [x] 检查负成交量 / 成交额
- [x] 检查 `market_daily_basic` 最新字段覆盖率
- [x] 检查 `market_adj_factors` 非正复权因子
- [x] 检查 `trading_calendar` 基本结构

### W2.17.4.2 财务因子

- [x] 检查 `market_financial_factors` 表结构
- [x] 检查 `announce_date` 覆盖率
- [x] 检查 `announce_date < report_date` 的不可能时间线
- [x] 检查最新财务因子覆盖率
- [x] 检查 `tushare_financial_backfill_tasks` 的 pending / failed 状态

### W2.17.4.3 跨市场数据

- [x] 检查 US / HK 数据库存在性
- [x] 检查配置标的 freshness 覆盖率
- [x] 检查最近窗口 OHLC 逻辑
- [x] 检查 source audit 最新运行记录

### W2.17.4.4 调度状态

- [x] 检查 `logs/scheduler/*.last`
- [x] 检查 A 股 source audit 最新运行记录
- [x] 已接入调度器前置门禁：默认任务实际执行前先跑 `db-health --scope scheduler`；`daily_brief` 已收窄为 `cn`

## W2.17.5 验收结果

- [x] `./.venv/bin/python -m compileall phase0/db_health.py phase0/cli.py`
- [x] `./.venv/bin/python -m phase0.cli db-health --config config.yaml --scope scheduler --output-dir /tmp/stok-db-health-scheduler --fail-on never`
- [x] `./.venv/bin/python -m phase0.cli db-health --config config.yaml --scope cn --output-dir /tmp/stok-db-health-cn --fail-on never`
- [x] `./.venv/bin/python -m phase0.cli db-health --config config.yaml --scope financial --output-dir /tmp/stok-db-health-financial --fail-on never`
- [x] `./.venv/bin/python -m phase0.cli db-health --config config.yaml --scope all --output-dir /tmp/stok-db-health-final --fail-on never`
- [x] `./.venv/bin/python -m phase0.cli db-health --config config.yaml --scope all --output-dir /tmp/stok-db-health-final-fail --fail-on warning`

当前验收结论（2026-06-05）：

- [x] `scheduler` 范围：PASS
- [x] `cn` 范围：PASS
- [x] `all` 范围：WARNING，`errors=0`、`warnings=6`
- [x] `--fail-on warning` 正确返回退出码 `2`
- [x] 全量检查约 15 秒，适合手工检查和低频调度；高频前置门禁建议先用 `scheduler` 或 `cn` 范围

## W2.17.6 当前发现

- [x] `cn.daily_basic.pe_ratio` 最新覆盖率约 `72%`，已确认不是整行缺失；PE 为空多为亏损 / TTM 盈利不可计算，已改为诊断项而非硬覆盖率 warning
- [x] T1.5 目标季度末任务已清空 `pending/failed`；全表剩余 `pending/failed` 属于目标外 period，已拆为 W2.20 清理 / 重分类任务
- [x] US 行情 recent OHLC 违规 `3` 行，`db-health` 已输出 sample rows 定位：当前样本集中在 `CNY=X`
- [ ] HK 配置标的 freshness 当前覆盖 `25/30`，疑似 yfinance 更新延迟 / 交易日差异，需先跑增量更新再判断是否调整门禁阈值
- [x] HK 行情 recent OHLC 违规 `1` 行，`db-health` 已输出 sample rows 定位：当前样本为 `HK.09633`

## W2.17.7 后续任务

- [x] 将 `db-health --scope scheduler --fail-on warning` 接入调度器前置检查；`daily_brief` 默认改为 `cn`
- [x] 调度器支持环境变量开关和按任务 scope 配置：`SCHEDULER_HEALTH_ENABLED`、`SCHEDULER_HEALTH_FAIL_ON`、`*_HEALTH_SCOPE`
- [x] 将 `db-health --scope cn --fail-on error` 接入 `factor-effectiveness` 前置检查
- [x] 将 `db-health --scope cn --fail-on error` 接入 `run` 前置检查
- [x] 为 OHLC 异常增加 sample rows 输出，包含 `symbol/date/open/high/low/close/source`
- [ ] 继续评估哪些其他研究命令需要 `cn/error` 门禁，避免重复或过度阻断
- [x] 为 `daily_basic.pe_ratio` 覆盖不足建立口径判断：PE 为空多为亏损 / TTM 盈利不可计算，不适合作为硬门槛；`db-health` 已保留 PE 覆盖率和缺失分解诊断
- [ ] 评估是否需要可选落库 `database_health_runs` / `database_health_findings`，默认仍保持只读

# W2.18｜数据治理与维护编排器专项（T6.3）

参考专项任务：[`docs/tasks/ops/DATA_GOVERNANCE_ORCHESTRATOR_TASKS.md`](ops/DATA_GOVERNANCE_ORCHESTRATOR_TASKS.md)

## W2.18.1 背景

当前项目已经具备统一 cron 入口、`db-health` 门禁、backfill 审计报告和部分断点任务能力；T6.3 V1 已把调度判断、重试、跳过原因、长任务分片监督和运行状态收敛到 `maintenance_orchestrator`。

后续阶段继续把本地数据治理控制平面从“可用 V1”扩展为“可配置、可巡检、可供 TUI / System Orchestrator 统一调用”的长期维护入口。

## W2.18.2 本周目标

- [x] 建立 `T6.3` 专项任务单，明确最终形态架构模式
- [x] 将 `T6.3` 加入任务索引和主开发计划
- [x] 在架构文档中明确维护编排器是交付与运维层的目标 control plane
- [x] 设计 `maintenance_orchestrator` 第一版最小实现边界
- [x] 实现状态库 schema 初始化：`data/maintenance/maintenance.sqlite`
- [x] 实现 `maintain tick --dry-run`
- [x] 实现 `maintain status`
- [x] 将当前 shell 调度任务映射为内置 registry，但不立即替换 cron 行为

# W2.28｜Report Dashboard Astro 静态报表门户专项（T6.4）

参考专项任务：[`docs/tasks/ops/REPORT_DASHBOARD_ASTRO_TASKS.md`](ops/REPORT_DASHBOARD_ASTRO_TASKS.md)

## W2.28.1 背景

当前 `reports/` 下已经有 Markdown、HTML、CSV 等多种产物，但分散在日期目录、策略目录、维护目录和专项目录中。继续让每个命令各自输出路径会增加复盘成本，也不利于把 `compare`、`strategy-admission`、`brief`、`maintenance`、`db-health` 的运行结果统一展示。

## W2.28.2 本周目标

- [x] 草拟 T6.4 模块开发计划，明确 Python 报表登记层与 Astro 静态渲染层边界
- [x] 实现 P0 manifest MVP：扫描 Markdown / HTML / CSV 并生成 `reports/runs/report_dashboard/manifest.json`
- [x] 新增 `dashboard scan` CLI
- [x] 用现有 `reports/strategy_admission/`、`reports/2026-06-23/`、`reports/database_health/` 做扫描验收

## W2.28.3 第一版验收标准

- [x] `./.venv/bin/python -m pytest tests/test_report_registry.py -q` 通过
- [x] `./.venv/bin/python -m phase0.cli dashboard scan --config config.yaml` 能生成 manifest
- [x] manifest 至少包含 Markdown、HTML、CSV 三类产物
- [ ] P1 Astro 站点不直接扫描业务目录，只消费 manifest

# W2.29｜Report Output Path Standardization（T6.5）

参考专项计划：[`docs/superpowers/plans/2026-06-23-report-output-path-standardization.md`](../superpowers/plans/2026-06-23-report-output-path-standardization.md)

## W2.29.1 本周目标

- [x] 实现 `phase0/report_paths.py`，统一 run / latest / scratch 路径 helper
- [x] 默认新产物采用 `reports/runs/YYYY-MM-DD/YYYYMMDD_HHMMSS__<command>__<scope>/`
- [x] 文件名采用 `<family>__<artifact>.<ext>`，不再在文件名中重复 timestamp
- [x] 迁移 `strategy-admission` 默认输出，并保留显式 `--output-dir` 兼容
- [x] 迁移 `db-health` 默认输出，并保留显式 `--output-dir` 兼容
- [x] 迁移 `factor-effectiveness` 默认输出，并保留显式输出目录兼容
- [x] watchlist latest 新增 `reports/latest/watchlist/index.html`，旧 `reports/watchlist_today/index.html` 继续作为兼容镜像
- [x] account-bill latest 新增 `reports/runs/latest/account_bill/index.html` 与 `reports/account_bill_today/index.html`
- [x] `dashboard scan` 识别 `standard_run`、legacy module/date/experiment/latest/scratch/root-flat 分类

## W2.29.2 验收标准

- [x] `./.venv/bin/python -m pytest tests/test_report_paths.py tests/test_report_registry.py tests/test_strategy_admission_config.py tests/test_daily_coverage_eligibility.py -q` 通过
- [x] `./.venv/bin/python -m phase0.cli dashboard scan --config config.yaml` 通过，并在 manifest 中显示 `standard_run`
- [x] `db-health --scope scheduler --fail-on never` 可生成标准 run 目录下的 `database_health__summary.csv`、`database_health__findings.csv`、`database_health__report.md`
- [ ] 未批量移动历史 `reports/` 文件；历史产物继续通过 scanner 兼容索引
- [ ] 尚未实现 Astro 前端、`dashboard build`、`dashboard serve`

## W2.18.3 第一版验收标准

- [x] `maintain tick --dry-run` 能输出当前时刻每个任务的 `will_run / skipped / blocked` 判断和原因
- [x] `maintain status` 能展示最近运行、当前运行、失败次数、最后错误摘要和报告路径
- [x] 当前 `scripts/run_project_scheduler.sh` 行为不被破坏
- [x] `db-health` 门禁策略仍按任务 scope 控制，不使用全局单一阻断标准
- [x] 运行产物继续写入既有 `reports/` 和 `logs/` 路径

## W2.18.4 后续任务

- [x] 将 `scripts/run_project_scheduler.sh` 降级为 wrapper，正式由 `maintain tick` 接管调度判断
- [x] 接入最小重试次数、重试间隔和 `.state` 状态文件
- [x] 为 `backfill-tushare-financials` 增加 3 shard 编排运行模式
- [x] 实现 `maintain stop`，中断一个长任务 run 的全部 shard
- [x] 实现 `maintain resume`，只重启未完成、失败或中断的 shard
- [x] 当前优先 1：补持续 supervisor，使后台 shard 可基于 pid、日志和 audit 报告保守归类为成功、失败或 unknown
- [x] 当前优先 2：新增 `reports/database_health/maintenance/maintenance_status_YYYY-MM-DD.md` 输出能力
- [x] 当前优先 3：接入交易日历和更细的运行窗口口径
- [x] 当前优先 4：从 backfill audit 中提取报告路径和关键结论，登记到维护状态
- [x] 当前优先 5：新增 `phase0.cli system status` 只读入口，汇总 maintenance state DB、任务状态分布、决策分布和 running shard 数
- [x] `system status` 默认不启动任务、不生成维护 Markdown 报告，作为 System Orchestrator 的最小只读汇总 MVP

# W2.19｜文本事件数据层后续任务（T1.3 / T2.11）

参考专项任务：[`docs/tasks/data-sources/NEWS_SOURCE_IMPLEMENTATION_TASKS.md`](data-sources/NEWS_SOURCE_IMPLEMENTATION_TASKS.md)  
参考调查归档：[`refdocs/tushare_news_dashboard_upstream_mapping_note_2026-06-06.md`](../../refdocs/tushare_news_dashboard_upstream_mapping_note_2026-06-06.md)

## W2.19.1 背景

前期已明确 Tiingo 不继续承担新闻源角色，并完成 Tushare 聚合新闻看板上游来源调查。后续不应把新闻讨论直接转成交易信号，而应先建设统一文本事件数据层，用于公告、研报、新闻、政策、快讯的采集、去重、as-of 审计和事件时间线。

## W2.19.2 后续任务

- [ ] 设计 `market_text_events` 第一版字段口径，覆盖 `source/provider/published_at/ingested_at/as_of_time/dedupe_key/content_hash`
- [ ] 对 Tushare `research_report`、`anns_d`、`major_news`、`npr`、`cctv_news` 做权限、字段和延迟 probe
- [ ] 明确新浪财经、财联社、华尔街见闻、中证网等公开上游只作为替代源候选，并记录授权和维护风险
- [ ] 生成 `reports/news_source_probe_report.md`
- [ ] 生成文本事件覆盖率、抓取延迟、重复率和来源失败原因报告
- [ ] 为关注个股分析工具输出单股事件时间线输入
- [ ] 为 `T2.11` PEAD / 文本因子研究提供数据层前置验收，不直接进入主 ranker

## W2.19.3 暂不做事项

- [ ] 不把网页抓取结果绕过标准化直接接入策略因子
- [ ] 不让 LLM 直接对文本事件生成买卖评分
- [x] 不在没有 as-of 口径和覆盖率诊断前做文本因子回测

# W2.20｜Tushare 财务回填目标外任务清理 / 重分类

## W2.20.1 背景

`T1.5` 已完成 2016Q1-2018Q1 原始目标季度末验收，目标季度末任务均已清空 `pending/failed`。但 `tushare_financial_backfill_tasks` 全表仍存在目标外 period 的 `pending/failed`，导致 `db-health --scope all` 继续产生 `financial.backfill_tasks.pending` 与 `financial.backfill_tasks.failed` warning。

这些任务主要来自非 T1.5 季度末或后续补跑范围，不应继续被误读为 T1.5 未完成，也不应长期污染数据库健康检查结论。

## W2.20.2 目标

- [x] 本地盘点 `tushare_financial_backfill_tasks` 中所有目标外 period，区分季度末、非季度末和误生成 period
- [x] 明确目标外任务处置策略：保留重试、标记 skipped、归档迁移或删除重建
- [x] 不影响 2016Q1-2018Q1 已验收任务状态和审计报告
- [ ] 调整 `db-health` 对财务回填任务队列的检查口径，避免目标外历史任务阻塞 `scope all`
- [ ] 输出清理前后任务状态审计报告

2026-06-23 审核记录：

- `tushare_financial_backfill_tasks` 当前全表状态：`fetched=26477`、`empty=8803`、`failed=3850`、`pending=3036`。
- T1.5 原始目标季度末 `2016-03-31` 至 `2018-03-31` 均已确认 `pending=0`、`failed=0`，不需要重开 T1.5。
- 主要误生成 / 非季度末 period 为 `2017-07-01`、`2017-08-01`、`2017-09-01`、`2017-10-01`、`2017-11-01`；其中 failed 任务集中在 `2017-07-01/2017-08-01/2017-09-01`，pending 任务集中在 `2017-09-01/2017-10-01/2017-11-01`。
- 少量目标外季度末 pending 仅为每期 `1` 个左右，例如 `2018-06-30`、`2018-12-31`、`2019-12-31`、`2020-03-31`、`2021-03-31`、`2021-09-30`、`2022-06-30`、`2023-03-31`、`2025-12-31`。
- 处置策略：误生成非季度末任务应重分类为 skipped / archived 或迁移到清理审计表；少量合法季度末 pending 不应删除，应保留给后续 backfill 或字段缺失补录模式处理。
- W2.20 仍有必要保留：2026-06-23 `db-health` 仍报告 `financial.backfill_tasks.failed=3850`、`financial.backfill_tasks.pending=3036`，说明本地盘点已完成，但检查口径调整和可追溯清理报告尚未完成。

## W2.20.3 验收标准

- [ ] 清理后 `db-health --scope all --fail-on never` 不再因目标外 Tushare financial 任务产生误导性 warning
- [ ] 保留需要继续补录的合法任务，且能被后续 backfill / 字段缺失补录模式继续选择
- [ ] 清理动作可追溯，报告记录 period、status、task_count、处置方式和原因
- [ ] 若采用重分类而非删除，任务表状态语义需补充到项目文档

# W2.21｜Tushare 财务因子字段缺失补录模式

## W2.21.1 背景

`market_financial_factors` 中部分已有 `fetched` 行仍存在字段级空值。直接用 `--replace-existing` 全量重跑会把请求量放大到数十万级，并增加覆盖已有有效值和 SQLite 写锁风险。

## W2.21.2 实现范围

- [x] 新增 `--missing-fields-only` 显式模式，不改变常规 `backfill-tushare-financials` 默认行为
- [x] 新增 `--missing-fields` 参数，默认覆盖 `roe,revenue_growth,profit_growth,operating_cash_flow_to_net_profit,debt_to_asset`
- [x] 新增独立任务表 `tushare_financial_missing_field_tasks`
- [x] 缺字段任务粒度为 `period + symbol`，任务记录 `missing_fields`、`interfaces`、`status`、`request_count`、`last_error`、`updated_at`
- [x] 按缺失字段选择最少 Tushare 接口：`fina_indicator` / `income` / `cashflow` / `balancesheet`
- [x] 写入时只填补已有行中的空字段，不用空值覆盖已有有效字段
- [x] 保留 `--limit-tasks`、`--limit-symbols`、`--retry-failed`、`--shard-index`、`--shard-count`、`--max-runtime-minutes` 的运行控制能力

## W2.21.3 验收方式

- [x] `compileall` 通过
- [x] CLI help 显示 `--missing-fields-only` 与 `--missing-fields`
- [x] `/tmp` 最小 SQLite 样本验证：能创建缺字段任务、选择最少接口、只合并空字段
- [x] 小批量联网验证：`--start-period 2018-06-30 --end-period 2026-03-31 --missing-fields-only --limit-tasks 5`
- [x] 修正单接口归一化问题：只调用 `fina_indicator` 等部分接口时不再触发 `combine_first` 类型异常
- [x] 修正补录计数口径：只有核心缺字段被填上才计入 `inserted_rows / fetched`，无字段改善标记为 `empty`
- [ ] 大批量运行前先估算任务量和接口请求量

# W2.22｜投资策略情报工作流模块 V1（T5.2）

参考专项任务：[`docs/tasks/research/STRATEGY_INTELLIGENCE_WORKFLOW_TASKS.md`](research/STRATEGY_INTELLIGENCE_WORKFLOW_TASKS.md)

## W2.22.1 背景

项目启动阶段的候选策略来自 `refdocs/papers/` 论文搜集与解读，说明外部情报对系统迭代方向具有持续影响。后续需要把论文、研究报告、公告新闻和策略线索从零散归档升级为可登记、可评分、可追溯、可转化的研究情报工作流。

## W2.22.2 V1 范围

- [x] 先将 T5.2 计划写入开发计划和周任务清单
- [x] 新建 `docs/tasks/research/STRATEGY_INTELLIGENCE_WORKFLOW_TASKS.md`
- [x] 新建 `knowledge/intelligence/README.md`
- [x] 新建 `knowledge/intelligence/strategy_intelligence_ledger.csv`
- [x] 新建情报解读模板与情报转候选策略模板
- [x] 从现有 `refdocs/papers/` 补录首批 20 条情报
- [x] 为至少 3 条核心情报生成完整 Markdown 解读 note
- [x] 为至少 1 条情报生成候选策略转化任务草案
- [x] 建立 RAG-ready 语料规范与 manifest，不引入向量库或自动交易信号

## W2.22.3 边界

- [x] V1 使用 Markdown + CSV，不引入 SQLite
- [x] V1 不做全网自动爬取
- [x] 新闻公告类情报只作为研究线索和解释材料，不直接进入主 ranker
- [x] LLM 只用于摘要、标签、反方审查，不作为最终评分唯一依据

# W2.23｜投资策略情报自动采集器 V1（T5.2）

参考专项任务：[`docs/tasks/research/STRATEGY_INTELLIGENCE_WORKFLOW_TASKS.md`](research/STRATEGY_INTELLIGENCE_WORKFLOW_TASKS.md)

## W2.23.1 目标

在 T5.2 情报工作流基础上，新增最小自动采集器，使论文/研报索引和本地资料可以进入候选情报 inbox，再由人工筛选并入正式情报台账。

## W2.23.2 范围

- [x] 新增 `phase0.intelligence` 情报包；核心 API 位于 `phase0/intelligence/__init__.py`
- [x] 新增 CLI：`phase0.cli intelligence collect`
- [x] 新增 CLI：`phase0.cli intelligence import-local`
- [x] 新增 CLI：`phase0.cli intelligence validate`
- [x] 在 `config.yaml` 预留 `local_dir`、`arxiv`、`openalex`、`crossref`、`rss` source 配置
- [x] 默认只启用 `refdocs/papers/` 本地扫描
- [x] 候选输出到 `data/intelligence/inbox/`，不直接写正式台账
- [x] Markdown 报告输出到 `reports/intelligence/`

## W2.23.3 边界

- [x] 不做全网爬虫
- [x] 不抓取付费研报全文
- [x] 不替代 T1.3 新闻/文本事件数据层
- [x] 不自动把候选情报转成交易信号

## W2.23.4 验收

- [x] `compileall` 通过
- [x] `intelligence --help` 可显示子命令
- [x] `intelligence validate` 可校验正式台账
- [x] `intelligence import-local --limit 5` 可生成候选 CSV 与 Markdown 报告
- [x] `intelligence collect --limit 5` 可按配置生成候选 CSV 与 Markdown 报告

# W2.24｜下一日策略准入收口计划（T2.8 / W2.15）

## W2.24.1 选择理由

当前 `T6.3` / `W2.12` 已满足本地调度 V1，继续扩展运维入口的边际收益低于策略研发收口。下一日优先处理 `T2.8` 与 `W2.15` 的策略准入闭环：先补过拟合诊断的最后折风险标记，再用固定双 preset 复测 `quality_low_turnover_monthly_v1`，形成可复查的 reject / retest / research-only 结论。

## W2.24.2 上午任务：过拟合诊断补强

- [x] 实现 W2.13.4.1 “只靠最后一折拉高”的风险标记
- [x] 在 `strategy_overfit_diagnostic.csv` 增加最近折贡献或最后折风险字段
- [x] 在 `strategy_overfit_diagnostic.md` 输出最后折拉高的主要风险原因
- [x] 增加最小测试或样例，证明最后一折异常拉高会被标记

验收：

- [x] 最后一折显著高于前序折均值时，报告给出明确风险原因
- [x] 正常稳定折序列不被误报为最后折拉高

## W2.24.3 下午前半：T2.7 双窗口复测

- [x] 用 `quality_low_turnover_monthly_v1` 跑 `baseline_2y_1y_5fold`
- [x] 用 `quality_low_turnover_monthly_v1` 跑 `quality_3y_1y_4fold`
- [x] 报告输出固定目录，包含 `strategy_admission_report.md`、`strategy_admission_window_matrix.csv`、`strategy_admission_constraint_review.csv`
- [x] 复核报告能区分折数不足、参数不稳定、收益不达标、组合构造失败、行业集中度和财务诊断状态

验收：

- [x] `baseline_2y_1y_5fold` 与 `quality_3y_1y_4fold` 都有可读报告
- [x] 结论明确落入 `eligible_for_paper_review / research_only / retest / reject` 之一

## W2.24.4 下午后半：结论归档与销项

- [x] 解读 `quality_low_turnover_monthly_v1` 的双窗口复测结果
- [x] 更新 `docs/tasks/strategy/EFFECTIVE_QUANT_STRATEGY_RESEARCH_TASKS.md` 对应 checkbox
- [x] 更新本周清单中 `W2.13`、`W2.15`、`W2.24` 对应 checkbox
- [x] 明确下一步是继续优化 T2.7、降级 research-only，还是 reject

2026-06-10 结论：`quality_low_turnover_monthly_v1` 双 preset 复测完成，报告目录 `reports/strategy_admission_t2_7_quality_low_turnover_dual_preset_20260610/`，最终 action 为 `reject`。最近一折转好按“regime 依赖风险”记录，不作为单一否定依据；准入失败由正收益折比例、均值收益、Sharpe、参数稳定性和行业集中度共同触发。

不做：

- [ ] 不在同一天推进 HK/US 独立交易日历
- [ ] 不推进 TUI / 桌面 UI / System Orchestrator
- [ ] 不运行全策略 `qfq_current / qfq_asof` 双口径矩阵

# W2.25｜近 30 天策略情报月度扫描（T5.2）

参考专项任务：[`docs/tasks/research/STRATEGY_INTELLIGENCE_WORKFLOW_TASKS.md`](research/STRATEGY_INTELLIGENCE_WORKFLOW_TASKS.md)

## W2.25.1 目标

在 T5.2 情报工作流基础上，建立 `Strategy Intelligence Monthly Scan`，每月搜集近 30 天发布的量化策略情报，并把高价值线索转化为可验证策略假设、数据建设任务或反方证据。

## W2.25.2 范围

- [x] 扫描近 30 天发布的论文、预印本、券商金工、指数公司、交易所/数据源资料和高质量 quant research
- [x] 输出月度扫描报告：`knowledge/intelligence/monthly/strategy_intelligence_scan_YYYY-MM.md`
- [x] 建立月度扫描索引和运行规约：`knowledge/intelligence/monthly/index.md`、`knowledge/intelligence/monthly/README.md`
- [x] 对每条高价值情报记录发布时间、来源链接、核心观点、可验证假设、所需数据、实现成本和主要风险
- [x] 至少筛出 3 条可进入后续复核的策略或数据建设线索
- [ ] 将通过人工复核的情报补录到 `knowledge/intelligence/strategy_intelligence_ledger.csv`

2026-06-10 A 股专项扫描完成：报告 `knowledge/intelligence/monthly/strategy_intelligence_scan_2026-06_a_share.md`，候选 CSV `data/intelligence/inbox/a_share_strategy_intelligence_candidates_2026-06-10.csv`。本次仅进入候选 inbox，不自动写入正式台账。

2026-06-23 RAG-ready foundation 完成：新增三篇核心情报 note、一个因子冗余诊断转化草案、RAG 语料规范、RAG manifest、月度扫描索引和 wiki ingest log。当前仍不自动入账月扫候选，正式入账必须逐条人工评分和风险复核。

## W2.25.3 边界

- [x] 不抓取付费研报全文
- [x] 不把营销材料、新闻标题或未验证观点直接作为策略有效性证据
- [x] 不自动把候选情报转为交易信号
- [x] 不绕过 T5.2 评分、偏差风险和策略转化门禁

# W2.26｜策略失败归因诊断模块 V1（T2.9）

参考专项任务：[`docs/tasks/strategy/EFFECTIVE_QUANT_STRATEGY_RESEARCH_TASKS.md`](strategy/EFFECTIVE_QUANT_STRATEGY_RESEARCH_TASKS.md)

## W2.26.1 选择理由

`strategy-admission` 已能给出准入结论，但当前 T2.7 复测显示，仅有 `reject` 结论不足以指导下一轮研发。下一步需要一个只读归因层，把策略失败拆成收益、执行、构造、因子、参数、regime 和数据质量问题，避免继续盲目调参。

## W2.26.2 输入产物

- [x] `strategy_admission_candidate_folds.csv`
- [x] `strategy_admission_window_matrix.csv`
- [x] `strategy_admission_constraint_review.csv`
- [x] `overfit_diagnostic/strategy_overfit_diagnostic.csv`
- [x] 当前 T2.7 双 preset 报告目录：`reports/strategy_admission_t2_7_quality_low_turnover_dual_preset_20260610/`

## W2.26.3 开发任务

- [x] 新增只读失败归因模块，输入已有报告 CSV，不重新回测
- [x] 复用 admission gate 阈值，避免 T2.9 自定义另一套准入标准
- [x] 输出 `strategy_failure_attribution.csv`
- [x] 输出 `strategy_failure_attribution.md`
- [x] 每个 `strategy_id + preset` 输出归因标签、严重度、证据和建议动作
- [x] 为策略级结论输出自然语言摘要，说明应继续优化、重构、降级 research-only 还是当前 spec reject

## W2.26.4 V1 归因标签

- [x] `return_failure`：收益、Sharpe、回撤或正收益折比例不达标
- [x] `execution_failure`：换手、交易次数、持仓数或账户执行成本暴露异常
- [x] `construction_failure`：行业集中、持仓过少、股票池过窄或组合构造暴露失衡
- [x] `factor_failure`：财务 PIT / 字段覆盖可用，但质量暴露没有转化为收益
- [x] `parameter_failure`：不同折参数选择频繁变化
- [x] `regime_failure`：最后一折显著拉高或不同市场阶段表现断裂
- [x] `data_failure`：价格口径、财务诊断、行业诊断或必要诊断缺失

## W2.26.5 验收标准

- [x] 能解释 `quality_low_turnover_monthly_v1` 不是单纯因为最后一折转好而失败
- [x] 能区分收益不达标、参数不稳、行业集中、构造失效和 regime 依赖
- [x] 报告能给出下一轮研发建议，而不是只重复 admission 的 pass/fail
- [x] 不新增回测耗时，不修改已有 admission 产物

## W2.26.6 不做

- [x] 不自动调参
- [x] 不自动重写策略权重
- [x] 不直接生成交易信号
- [x] 不在 V1 中做复杂 SHAP / ML explainability

# W2.27｜规则型 sleeve 组合 V1（T2.10.1）

参考专项任务：[`docs/tasks/strategy/EFFECTIVE_QUANT_STRATEGY_RESEARCH_TASKS.md`](strategy/EFFECTIVE_QUANT_STRATEGY_RESEARCH_TASKS.md)

## W2.27.1 范围

- [x] 新增 `sleeve_composite_v1` 作为 research-only / compare / admission 候选
- [x] 将 `legacy_momentum_low_turnover_v1` 的动量口径降级为 low-turnover momentum sleeve 输入
- [x] 新增 defensive quality sleeve 分数
- [x] 新增 risk overlay sleeve 分数
- [x] 输出 `defensive_quality_score`、`low_turnover_momentum_score`、`risk_overlay_score`、`final_score` 和降级原因字段

## W2.27.2 不做

- [x] 不做二阶段 ML rerank
- [x] 不新增 sklearn / xgboost 依赖
- [x] 不接入模拟账户或 `07:30` 正式输出
- [x] 不把组合分数直接解释为交易信号

# W2.30｜因子传导图工程化与市场环境诊断（T2.13 / T5.2）

参考架构文档：[`docs/PROJECT_ARCHITECTURE_OVERVIEW.md`](../PROJECT_ARCHITECTURE_OVERVIEW.md)

## W2.30.1 背景结论

`INT-KMS-001` A 股个股行情影响因子全景图已通过情报采集器入库，并已与 marklogseq HTML 结构化接口知识整合为项目知识资产。其第二部分“因子传导逻辑图（从定价公式到六域关系矩阵）”可以作为项目因子体系设计的理论框架，但只能作为因子本体、特征注册、市场环境归因和报告解释的基础，不可直接作为交易 alpha、因果证明或准入豁免。

核心分解：

- [x] 股价变化拆解为未来现金流预期、折现率/风险溢价、资金供需、信息事件冲击、交易制度与微观结构放大
- [x] 六域矩阵覆盖宏观制度、行业主题、公司价值、风格风险溢价、资金交易、信息事件
- [x] 工程角色定位为研究情报层到策略治理层之间的只读元数据和诊断框架
- [x] 具体因子进入主 ranker 前仍必须经过 as-of 可见性、覆盖率、样本外、成本后和 admission 验证

## W2.30.2 本周目标

- [x] 将 Logseq 全景图和 marklogseq HTML 结构化知识资产纳入 T5.2 情报库
- [x] 复核“因子传导逻辑图”是否适合作为代码设计基础理论依据
- [x] 在开发计划书中新增 T2.13，并引用项目架构总览约束模块边界
- [ ] 设计第一版因子本体 schema，明确因子域、影响通道、数据来源、可见时间、使用位置和验证状态
- [ ] 设计 feature registry 草案，先把现有低波、低换手、质量、成长、估值、动量、反转因子映射到六域传导框架
- [ ] 设计 market regime / strategy failure attribution 的扩展字段，用于解释策略失败是否与市场风格切换、板块轮动、资金结构或外部事件相关
- [ ] 设计 admission 报告扩展字段，使报告能区分“策略本身失效”“因子域缺失”“当前市场环境未覆盖”“外部事件未建模”

## W2.30.3 架构边界

- [x] 研究情报层保存来源、摘要、六域分类、可验证假设和反方风险
- [x] 股票池与特征层负责把可落地字段注册为 factor / feature spec，并记录数据源、频率、覆盖率、as-of 可见性和缺失处理
- [x] 策略治理层负责把因子域和影响通道用于 `factor-effectiveness`、`strategy-admission`、失败归因和 regime 解释
- [x] 交付与运维层只展示诊断结果、报告和知识资产，不直接重写策略结论
- [x] LLM / Agent 只能做摘要、标签、反方审查和计划生成，不能越过策略治理层生成交易动作

## W2.30.4 开发任务拆解

- [ ] 新增只读因子本体模块计划：`phase0/factor_ontology.py` 或等价模块，先定义数据结构和校验函数，不接入策略打分
- [ ] 新增因子注册表草案：记录因子中文名、内部字段、六域分类、影响通道、数据源、频率、可见时间、缺失处理、当前验证状态
- [ ] 从 `knowledge/intelligence/wiki/a_share_factor_data_interface_index.csv` 抽取可用接口候选，标记哪些可进入数据建设，哪些仅保留研究线索
- [ ] 为 `factor-effectiveness` 规划按因子域和影响通道聚合的诊断输出，避免只看单字段 IC 或分组收益
- [ ] 为 `strategy_failure_attribution` 规划外部市场、新闻、政策、行业轮动和资金结构缺失归因标签
- [ ] 为 `strategy-admission` 规划 regime coverage / factor domain coverage 段落，作为 reject 后研发方向输入
- [ ] 补充最小测试计划：schema 校验、未知因子域拒绝、缺失 as-of 字段阻断、registry CSV round-trip、报告字段稳定性

## W2.30.5 第一版验收标准

- [ ] 每个注册因子必须至少具备：因子域、影响通道、数据来源、可见时间、使用位置、验证状态
- [ ] registry 不允许缺失 as-of 可见性字段的因子进入历史回测候选
- [ ] 报告能把当前策略失败原因映射到收益、执行、构造、因子、参数、regime、数据质量以及外部因子覆盖缺口
- [ ] 计划能明确哪些数据来自 Tushare，哪些来自情报库，哪些来自公告新闻或后续文本事件层
- [ ] 不改变任何现有候选策略排序、权重、admission gate 或日报输出

## W2.30.6 不做

- [x] 不把六域矩阵直接转成主 ranker 权重
- [x] 不在没有数据覆盖率和 as-of 审计前启动外部因子回测
- [x] 不把新闻、政策或情绪材料直接当作已验证交易信号
- [x] 不因为策略 admission 过严就降低门槛；优先补齐缺失解释变量、市场环境诊断和反方证据

# W2.31｜AI 语料库开发计划（T1.7）

任务文档：[`docs/tasks/data-sources/AI_CORPUS_IMPLEMENTATION_TASKS.md`](data-sources/AI_CORPUS_IMPLEMENTATION_TASKS.md)

## W2.31.1 背景结论

原 `T1.3A｜自建中文文本事件 API` 和 `T1.3B｜自建国家政策法规库 API` 已合并为 `T1.7｜AI 语料库`。该任务不依赖 Tushare 网站或高权限接口，首期基于国家公开网站和公开新闻 / 公告入口自建 provider。

核心结论：

- [x] gov.cn 政策文件库已有可验证官方入口、列表接口、部门字典、字段映射和正文页样例
- [x] CCTV 新闻联播公开页面可作为 `cctv_news` 风格 MVP 的首个新闻文本 provider
- [x] CNInfo / AkShare 可作为异常波动公告、交易风险提示公告的低成本 fallback
- [x] 央行报告和券商研报库先作为扩展 provider；研报首期只做元数据和授权摘要
- [x] 文本语料只进入研究情报和解释层，不直接进入主 ranker 或替代 admission

## W2.31.2 本周目标

- [x] 将自建中文文本事件 API 和国家政策法规库 API 合并为统一 `T1.7｜AI 语料库` 任务文档
- [x] 在 `docs/DEVELOPMENT_PLAN.md` 中分配 `T1.7` 开发任务序号
- [x] 在 `docs/tasks/README.md` 中把 `T1.7` 纳入子任务索引
- [x] 定义 `ai_corpus_documents` schema、provider registry、raw archive 路径和 fixture 规则
- [x] 固化 gov.cn 政策库 fixtures：列表 JSON、国务院文件正文 HTML、国务院部门文件正文 HTML
- [x] 实现 gov.cn 政策库 provider P0/P1：列表查询、分页、字段清洗、错误记录
- [x] 设计 `npr` 兼容 API 的字段选择、limit、多页循环和正文懒加载策略

## W2.31.3 开发任务拆解

- [x] `T1.7.1` 新增 AI 语料库 schema 草案，明确 `published_at / issued_at / ingested_at / as_of_time` 边界
- [x] `T1.7.1` 新增 provider registry 草案，定义 provider 名称、源站、支持参数、parser 版本和 raw archive 目录
- [x] `T1.7.2` 实现 gov.cn `/search-gov/data` 参数映射：`org`、`ptype`、`keyword`、`start_date`、`end_date`、`limit`
- [x] `T1.7.3` 实现 gov.cn 正文 parser，抽取元数据表、`#UCAP-CONTENT`、正文 hash 和 parse status
- [x] `T1.7.4` 实现主题映射 MVP，支持 `ptype=科技` 到 `subchildtype=2220` 的映射；完整 `bmzcfwjg.json` / 主题树缓存后续随 live provider 增强
- [x] `T1.7.5` 准备 CCTV `20260703` fixture，解析日期页、完整节目页和分段页；当前为 fixture MVP，不声明生产 live provider 可用
- [x] `T1.7.6` 保留 CNInfo 异常波动 / 风险提示公告专项 provider 计划，不在 gov.cn MVP 未完成前扩散实现面

## W2.31.4 第一版验收标准

- [x] `npr(org="国务院", ptype="科技", end_date="2025-08-26 17:00:00")` 能返回 `国务院关于深入实施“人工智能+”行动的意见` 和 `国发〔2025〕11号`
- [x] gov.cn 正文 parser 能从样例页抽取非空 `content_html`，并保留原始 URL、raw path、content hash 和 parser version
- [x] `published_at`、`issued_at`、`ingested_at`、`as_of_time` 不混用，回测可见时间以本系统抓取成功时间为准
- [x] 同一政策文件重复抓取不会重复入库，去重键至少覆盖 `source_id / url / pcode + title + puborg + pubtime / content_hash`
- [x] CCTV 和 CNInfo provider 仅完成 fixture / 计划准备时，不声称已经生产可用

## W2.31.5 不做

- [x] 不依赖 Tushare 网站或 Tushare 高权限接口作为首期主源
- [x] 不抓取、保存或再分发无授权券商研报全文
- [x] 不在 MVP 阶段建设 HTTP 服务或多租户权限系统
- [x] 不把政策、公告、新闻或 LLM 摘要直接接入主 ranker
- [x] 不降低策略 admission 门槛，不把语料覆盖当作策略有效性的替代证据
