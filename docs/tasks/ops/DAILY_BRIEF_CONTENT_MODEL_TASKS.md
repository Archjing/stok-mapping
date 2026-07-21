# T6.6｜Daily Brief 独立内容模型与页面设计

> 父级计划：[`docs/DEVELOPMENT_PLAN.md`](../../DEVELOPMENT_PLAN.md)
> 当前目标：把正式 daily brief 从阶段试用 watchlist 兼容页面中独立出来，先固化内容模型和页面结构，再实现生成代码与同步迁移。

## 1. 背景与问题

当前 `brief daily` 与 `brief watchlist` 仍共用阶段试用观察池生成路径。这个实现能满足“每天产出可复盘观察池”的最小闭环，但不适合作为正式日报长期形态：

- daily brief 应回答“今天盘前我需要知道什么、账户处于什么状态、哪些风险会影响执行”。
- watchlist 应回答“今天有哪些候选观察标的、目标权重和计划动作”。
- account bill 应回答“已确认交易日实际成交、持仓、资产和收益如何变化”。

因此正式 daily brief 需要独立内容模型。watchlist 和 account bill 是日报引用的数据组件，不应继续等同于日报本身。

## 2. 产品边界

- 本页面是个人自用量化研究、盘前研判与交易计划辅助页面，不对外提供投资建议。
- 页面可以展示策略引擎、风控约束和账户仿真的结果，但不能由 LLM 或页面层直接生成交易信号。
- 未通过 `strategy-admission` 的策略只能显示为 research-only、compatibility baseline 或 failure sample，不得包装为正式可执行策略。
- 模拟账户账单只使用本地日线库已有执行日 OHLCV 的确认日期；未确认日期不推导收益率。
- 缺数据、健康门禁失败、交易日历不确定、账单缺失时，页面必须显式展示状态，而不是静默降级。

## 3. 页面内容模型

### 3.1 `DailyBriefDocument`

| 字段 | 说明 | 最小来源 |
| --- | --- | --- |
| `metadata` | 简报日期、信号日期、生成时间、交易日历判断、运行 profile | `premarket_watchlist` summary、`maintain tick` decision |
| `data_freshness` | A 股、HK、US、财务因子、交易日历、账户账本的新鲜度 | local history DB、maintenance state、db-health |
| `account_summary` | 总资产、可用资金、持仓市值、当前仓位、当前收益率、账单确认状态 | simulated account SQLite、账户配置初始资金 |
| `market_context` | A 股最近交易日、隔夜 US/HK/ETF/VIX/汇率等市场背景 | 已入库跨市场数据；缺失时显示不可用 |
| `strategy_status` | 当前可用策略、admission 状态、research-only 边界、过拟合/行业/执行诊断摘要 | strategy-admission、overfit、execution diagnostics |
| `portfolio_plan` | 当前持仓、目标暴露、调仓方向、现金约束、成交价口径、阻断原因 | watchlist、account ledger、execution checks |
| `watchlist_digest` | 买入/加仓/减仓/卖出/观察摘要、重点标的和原因 | watchlist CSV/DF |
| `risk_checks` | 数据质量、流动性、停牌/涨跌停、集中度、单日异常、门禁阻断 | db-health、execution risk、strategy diagnostics |
| `artifacts` | watchlist、account bill、db-health、maintenance status、日志和报告链接 | report paths / manifest |
| `disclaimer` | 个人自用、非投资建议、数据口径和确认账单边界 | 静态文本 |

### 3.2 账户摘要固定展示

日报顶部账户摘要必须固定展示 5 个 span：

| 展示项 | 口径 |
| --- | --- |
| 总资产（元） | 最近确认账单 `total_asset`；无账单时用模拟账户初始资金 |
| 可用资金（元） | 最近确认账单 `cash_asset`；无账单时用模拟账户初始资金 |
| 持仓市值（元） | 最近确认账单 `stock_asset`；无账单时为 `0.00` |
| 当前仓位（%） | 最近确认账单持仓市值 / 总资产；无账单时为 `0.00%` |
| 当前收益率（%） | 最近确认账单收益率；无账单时显示 `暂无` |

## 4. 页面信息架构

### 4.1 顶部状态栏

展示：

- 简报日期、信号日期、生成时间。
- 是否交易日、交易日历来源。
- 数据健康状态：正常 / 警告 / 阻断。
- 账单状态：已确认到某日期 / 今日未确认 / 暂无账单。

验收标准：

- 用户打开第一页即可判断今天的日报是否可用、是否基于最新数据、账户数据是否确认。

### 4.2 账户与风险摘要

展示：

- 5 个账户 span。
- 当前总暴露、目标总暴露、目标变化。
- 现金约束、未成交风险、模拟账户账单链接。

验收标准：

- 无账单时显示初始资金、持仓市值 0、仓位 0、收益率暂无。
- 有账单时数值与 `account_daily_assets` 同日记录一致。

### 4.3 今日盘前结论

展示：

- 今日操作 stance：不操作 / 观察 / 小幅调仓 / 风险降低 / 仅研究。
- 为什么是这个 stance：策略准入、市场环境、数据健康、账户约束四类原因。
- 当前不可做事项：例如无合格 candidate、门禁失败、数据缺口、账单未确认。

验收标准：

- 页面必须能用 3-5 行文字解释今天“为什么可以看、为什么不能交易、为什么只能观察”。

### 4.4 市场环境与数据新鲜度

展示：

- A 股最近交易日行情状态。
- 隔夜 US/HK/ETF/VIX/汇率等 overlay 状态。
- 本地库最新日期、缺失项和 fallback。

验收标准：

- 任何跨市场数据缺失都显示为“不可用 / 未入库 / 过期”，不得伪造摘要。

### 4.5 策略与门禁状态

展示：

- 当前策略集合和正式准入状态。
- `strategy-admission`、过拟合诊断、行业集中、执行诊断摘要。
- research-only / compatibility baseline 的边界说明。

验收标准：

- 无正式 admission pass 时，页面不能出现“正式推荐”“可实盘执行”等措辞。

### 4.6 组合计划与 Watchlist 摘要

展示：

- 计划层动作统计：买入/加仓/减仓/卖出/观察数量。
- 重点标的摘要：股票代码、名称、动作、目标权重、理由、主要风险。
- 完整 watchlist 表格或链接作为下钻区域。

验收标准：

- daily brief 首屏不应被完整宽表淹没；完整 watchlist 作为组件或链接存在。

### 4.7 风险、阻断与人工检查清单

展示：

- 数据健康异常。
- 涨跌停、停牌、流动性、整手、现金不足、集中度等执行阻断。
- 人工复核 checklist：是否确认数据日期、是否确认账户状态、是否有重大事件。

验收标准：

- 页面必须把“不能执行”的原因放在和交易计划同等显眼的位置。

### 4.8 证据与产物链接

展示：

- watchlist HTML/CSV。
- account bill HTML。
- db-health report。
- maintenance status。
- strategy-admission / overfit / execution diagnostics。
- 生成日志。

验收标准：

- 每个摘要结论至少能追溯到一个本地 artifact 或明确的数据来源。

## 5. 实施计划

### P0 内容模型冻结

- [x] 新增 `DailyBriefDocument` schema 或等价 typed dict/dataclass。
- [x] 定义 `DailyBriefSection` 数据结构，保证 HTML renderer 不直接读取业务 DB。
- [x] 为缺数据、无账单、非交易日、无合格 candidate 定义固定展示口径。

### P1 独立生成代码

- [x] 新增 `phase0/reporting/daily_brief.py`（仅内容模型；独立 HTML renderer 与 `brief daily` CLI 接入仍待完成）。
- [ ] `brief daily` 调用 daily brief renderer。
- [ ] `brief watchlist` 保持观察池 renderer。
- [ ] 保留旧 `reports/watchlist_today/index.html` 兼容镜像，新增正式 daily brief latest 路径。

### P2 测试与验收

- [x] 单元测试覆盖账户摘要 5 span。
- [x] 单元测试覆盖无账单 fallback。
- [x] 明确累计收益率以确认账单快照相对初始资金计算，不从未确认账单推导。
- [x] 验证确认账单快照的必填字段、数值可表示性和日期边界。
- [ ] 单元测试覆盖数据健康 warning/error 的页面展示。
- [ ] 快照或 HTML 结构测试覆盖主要 section anchor。

### P3 同步与迁移

- [ ] 注册 daily brief artifact 到 report manifest。
- [ ] 明确 `/brief/` 远端页面从 watchlist 迁移到 daily brief 的切换日期。
- [ ] 在迁移窗口保留 watchlist 下钻链接，避免原观察池入口丢失。

## 6. 不做清单

- 不在本任务内新增策略 alpha。
- 不绕过 admission 或 execution gate。
- 不把 LLM 文案作为交易信号来源。
- 不把未确认账单推导为已实现收益。
- 不引入新的后台调度系统。
