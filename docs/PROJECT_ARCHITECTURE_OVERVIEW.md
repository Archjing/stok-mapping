# stok-mapping 项目架构说明

> 面向对象：项目维护者、策略研究者、后续产品实现者  
> 最后审视：2026-06-05  
> 审视角色：软件架构师  
> 依据：当前 `phase0/` 代码、`config.yaml`、`README.md`、`docs/DEVELOPMENT_PLAN.md`、`docs/tasks/WEEKLY_EXECUTION_CHECKLIST.md`、最近一次开发日志与已实现 CLI。  
> 旧版归档：[`docs/archive/PROJECT_ARCHITECTURE_OVERVIEW_2026-06-05_pre_review.md`](archive/PROJECT_ARCHITECTURE_OVERVIEW_2026-06-05_pre_review.md)

---

## 1. 架构结论

`stok-mapping` 当前已经不是单一回测脚本，而是一个围绕 **A 股本土因子研究、数据治理、策略验证、账户级仿真和盘前研判交付** 构建的本地研究系统。

当前最关键的架构事实是：

- Phase 0 工程链路已经可运行，但严格 `qfq_asof` 与 point-in-time 股票池复核后，当前没有可直接进入实盘模拟的合格策略。
- 系统主线已经从“维护一个 selected strategy”转为“先治理数据和因子，再重建有效候选策略”。
- A 股数据底座已以本地 SQLite 为核心，Tushare 是当前 A 股主源，US/HK 跨市场数据已独立落库。
- 策略评估不再只看 effectiveness gate，还需要同时考虑 `qfq_asof`、PIT 股票池、财务公告日、过拟合诊断、数据健康检查和账户级执行约束。
- 新增 `db-health` 后，数据质量已开始从分散脚本审计演进为可调度门禁。
- 系统仍不是自动交易系统，不输出自动下单指令，也不允许 LLM 直接生成交易决策。

一句话定位：

> `stok-mapping` 是一个本地优先、可审计、可复现的 A 股量化研究与盘前研判系统；它以 A 股本土因子为主，以跨市场风险/情绪 overlay 为辅，以数据质量和策略治理门禁控制研究结论进入日常输出。

---

## 2. 产品边界

### 2.1 系统应该做什么

系统当前和后续应持续输出：

- A 股研究股票池
- 因子有效性诊断
- 候选策略 walk-forward 结果
- 策略准入与风险诊断报告
- 盘前观察池
- 关注个股分析工具、可视化看板与单股评估报告
- 账户级模拟账单和资产轨迹
- 调仓计划草案、模拟订单和阻断原因
- 数据源、数据质量、复权、PIT 与调度健康报告
- 研究过程日志和变更记录

### 2.2 系统不应该做什么

明确禁止或暂不支持：

- 自动下单
- 券商 API 实盘交易
- LLM 直接生成交易信号或调仓动作
- 对外投资建议或荐股服务
- 绕过数据质量、PIT、过拟合、账户约束直接发布策略结论
- 把 `qfq_current` 历史结果解释为严格 point-in-time 回测结论

### 2.3 当前研发重心

当前最高优先级不是新增复杂策略，而是：

1. 跑完 Tushare 财务因子 2016Q1-2018Q1 历史回填。
2. 用 `db-health` 建立调度和研究任务的前置门禁。
3. 继续推进因子有效性诊断，基于真实覆盖率重建低频低换手候选。
4. 将过拟合诊断、因子诊断、`qfq_asof`、账户级执行约束合并为策略准入流程。

---

## 3. 系统分层

当前架构可以拆为 9 层。

```text
┌──────────────────────────────────────────────────────────────┐
│ 9. 交付与运维层                                               │
│ reports / watchlist HTML / desktop UI / scheduler / logs / ECS│
├──────────────────────────────────────────────────────────────┤
│ 8. 策略治理层                                                 │
│ walk-forward / gate / overfit / factor-effectiveness / admission│
├──────────────────────────────────────────────────────────────┤
│ 7. 账户与执行仿真层                                           │
│ accounts / bill / execution profile / constraints / reconciliation│
├──────────────────────────────────────────────────────────────┤
│ 6. 策略与信号层                                               │
│ strategies registry / stock focus / overlay / rebalance       │
├──────────────────────────────────────────────────────────────┤
│ 5. 股票池与特征层                                             │
│ universe / qfq_asof features / daily_basic / financial factors│
├──────────────────────────────────────────────────────────────┤
│ 4. 研究情报层                                                 │
│ papers / research reports / news clues / intelligence ledger  │
├──────────────────────────────────────────────────────────────┤
│ 3. 数据质量与审计层                                           │
│ db-health / financial-pti / universe-pti / adjustment-audit   │
├──────────────────────────────────────────────────────────────┤
│ 2. 本地数据资产层                                             │
│ a_share_history.sqlite / us_market_history.sqlite / hk db     │
├──────────────────────────────────────────────────────────────┤
│ 1. 数据源适配层                                               │
│ Tushare / yfinance / FRED / Tiingo / local raw packages       │
└──────────────────────────────────────────────────────────────┘
```

层级原则：

- 下层不依赖上层。
- 研究结论必须通过数据质量与策略治理层。
- 交付层只展示已生成结果，不直接重写策略结论。
- LLM/Agent 只能作为摘要、解释和审查辅助，不进入主信号路径。

---

## 4. 端到端数据流

### 4.1 日常数据更新流

```text
Tushare / yfinance / HK provider
    ↓
update-history / update-us-market-history / update-hk-market-history / update-financials
    ↓
SQLite 本地数据资产
    ↓
source audit tables + logs/scheduler/*.last
    ↓
db-health / 专项审计命令
    ↓
股票池、因子诊断、策略验证、日报输出
```

关键要求：

- 数据更新必须有覆盖率和 source audit。
- 当前股票池和日报不允许静默使用明显过期数据。
- 跨市场数据应先落库，再被策略或报告读取，避免运行时在线源漂移。

### 4.2 策略研究流

```text
SQLite 历史库
    ↓
point-in-time universe folds
    ↓
qfq_asof 行情与特征
    ↓
daily_basic + PIT 财务因子
    ↓
strategies registry 候选策略
    ↓
walk-forward compare
    ↓
effectiveness gate + overfit diagnostic + factor effectiveness
    ↓
策略准入判断
```

当前架构判断：

- `qfq_asof` 与 PIT 股票池是历史回测的默认正确方向。
- `qfq_current` 只能保留为兼容或对照口径。
- 财务因子必须保留 `announce_date` 可见性，不允许用未来公告污染历史样本。
- 当前无合格策略，因此日报/观察池更多是阶段试用与研究输出，不应被解释为实盘推荐。

### 4.3 盘前交付流

```text
最新本地数据与股票池
    ↓
brief watchlist / brief daily / premarket
    ↓
模拟账户快照 + 候选观察池 + 风险提示
    ↓
reports/watchlist_today/index.html
    ↓
可选 ECS 同步
```

当前限制：

- `brief daily` 仍主要复用 watchlist 路径，正式 daily brief 仍待拆分。
- watchlist 是观察池和计划层，不是自动交易信号。
- 关注个股分析工具是独立的数据分析与可视化工具，不等同于每日 watchlist 输出；它面向用户手动关注股票生成交互式分析看板和单股评估报告。
- 账户级账单基于已确认 OHLCV 交易日，不是盘中实时撮合。

---

## 5. 核心模块边界

### 5.1 CLI 控制层

主入口：[phase0/cli.py](../phase0/cli.py)

职责：

- 解析命令行参数。
- 调用具体应用服务。
- 输出人可读状态和报告路径。
- 控制退出码，例如 `db-health --fail-on`。

主要命令分组：

| 分组 | 命令 | 职责 |
| --- | --- | --- |
| 数据更新 | `update-history`, `update-us-market-history`, `update-hk-market-history`, `update-financials` | 维护本地数据资产 |
| 历史导入/回填 | `import-history`, `import-index-history`, `backfill-*` | 初始化或补齐历史数据 |
| 数据审计 | `db-health`, `financial-pti`, `universe-pti`, `adjustment-audit` | 检查数据质量与 PIT 边界 |
| 策略研究 | `run`, `factor-effectiveness`, `overfit-diagnostic`, `cost-sensitivity` | 策略验证和诊断 |
| 账户/执行 | `bill`, `execution-gate`, `oos-report` | 账户级仿真和执行假设验证 |
| 交付 | `brief daily`, `brief watchlist`, `brief premarket`, `brief account-bill` | 日常观察池和报告输出 |

CLI 不应该承载复杂业务逻辑；复杂逻辑应放入 `phase0/*` 模块或 `scripts/*` 的应用脚本中。

---

### 5.2 配置层

配置入口：`config.yaml` 与 [phase0/config.py](../phase0/config.py)

职责：

- 定义数据源路径、token env、表名、阈值和开关。
- 定义股票池、执行 profile、回测窗口和策略参数。
- 保证研究口径和实盘仿真口径可分离。

架构要求：

- 不在脚本里硬编码 profile 默认值。
- 数据库表名、路径和阈值应从配置读取。
- 研究口径与 live/profile 口径必须显式区分。

---

### 5.3 数据源适配层

核心模块：

- [phase0/data_access/providers/tushare.py](../phase0/data_access/providers/tushare.py)
- [phase0/tushare_source.py](../phase0/tushare_source.py)（兼容旧入口；新代码不要继续依赖）
- [phase0/data_access/connectivity.py](../phase0/data_access/connectivity.py)
- [phase0/data_sources.py](../phase0/data_sources.py)（兼容旧入口；新代码不要继续依赖）
- [phase0/data_access/throttle.py](../phase0/data_access/throttle.py)
- [phase0/data_governance/external_market_history.py](../phase0/data_governance/external_market_history.py)

职责：

- 统一外部源调用、规范化、节流和错误处理。
- 将源数据转换成项目内部表结构。
- 记录 source 和 fetched_at，支持审计。

当前源边界：

| 数据源 | 当前角色 | 说明 |
| --- | --- | --- |
| Tushare | A 股主源 | 日线、daily_basic、adj_factor、财务回填、港股可选源 |
| yfinance | US/HK 过渡源与 fallback | 当前 US/HK 历史库仍可使用；不作为长期唯一主源 |
| FRED | 宏观/利率/VIX 最小接入 | 服务风险解释和日报，不进主 ranker |
| Tiingo | 美股个股/ETF 最小接入 | 服务跨市场 overlay；当前新闻权限不可用 |
| 本地预下载包 | A 股历史初始化 | 用于重建本地历史库 |

---

### 5.4 本地数据资产层

核心模块：

- [phase0/data_governance/import_history.py](../phase0/data_governance/import_history.py)
- [phase0/data_governance/update_history.py](../phase0/data_governance/update_history.py)
- [phase0/data_access/local_history.py](../phase0/data_access/local_history.py)
- [phase0/data_governance/financial_factors.py](../phase0/data_governance/financial_factors.py)
- [phase0/data_governance/backfills/tushare_history.py](../phase0/data_governance/backfills/tushare_history.py)

主要数据库：

| 数据库 | 角色 | 主要表 |
| --- | --- | --- |
| `data/manual_history/a_share_history.sqlite` | A 股研究主库 | `market_daily_bars`, `market_stocks`, `market_daily_basic`, `market_financial_factors`, `market_adj_factors`, `trading_calendar`, `market_data_source_runs` |
| `data/us_market_history.sqlite` | US/FX/ETF/VIX 跨市场库 | `us_daily_bars`, `us_data_source_runs` |
| `data/hk_market_history.sqlite` | HK 跨市场库 | `hk_daily_bars`, `hk_data_source_runs` |
| `data/simulated_trading/simulated_accounts.sqlite` | 模拟账户账本 | 账户、资产、成交、持仓相关表 |

关键架构决策：

- SQLite 是当前正式研究数据底座，不是临时缓存。
- 回测与日报尽量读本地库，不在策略运行时临时在线抓取。
- 长任务回填必须可恢复、可分片、有限速、有验收报告。
- 数据库不进入 Git。

Tushare 财务历史回填当前状态：

- 任务表：`tushare_financial_backfill_tasks`
- 目标：2016Q1-2018Q1
- 当前能力：断点续跑、`retry-failed`、`limit-tasks`、`max-runtime-minutes`、`shard-index/shard-count`、进度显示、审计报告
- 当前未完成：pending 队列仍需跑完，failed 任务需重试，完成后需重跑 `financial-pti` 和 `factor-effectiveness`

---

### 5.5 数据质量与审计层

核心模块：

- [phase0/db_health.py](../phase0/db_health.py)
- [phase0/data_governance/adjustment.py](../phase0/data_governance/adjustment.py)
- [phase0/data_governance/universe_pit.py](../phase0/data_governance/universe_pit.py)
- [scripts/audit_financial_pti.py](../scripts/audit_financial_pti.py)
- [scripts/audit_universe_pit.py](../scripts/audit_universe_pit.py)（兼容旧入口；新代码不要继续依赖）
- [scripts/check_local_history_consistency.py](../scripts/check_local_history_consistency.py)

当前审计命令：

| 命令 | 目的 | 当前状态 |
| --- | --- | --- |
| `db-health` | 统一 SQLite 健康检查，输出 summary/findings/report | MVP 已完成 |
| `adjustment-audit` | 检查 `bfq_raw/qfq_current/qfq_asof` 可用性和复权未来函数风险 | 已完成 MVP |
| `financial-pti` | 检查财务因子公告日 point-in-time 有效性 | 已完成 |
| `universe-pti` | 检查股票池 listing/industry point-in-time 边界 | 已完成 |

`db-health` 当前检查范围：

- A 股库：表结构、最新交易日、覆盖率、滞后、OHLC、非正价格、负成交量/成交额、daily_basic 覆盖、复权因子。
- 财务因子：表结构、`announce_date` 覆盖、不可能时间线、核心因子覆盖、Tushare backfill task 状态。
- 跨市场：US/HK 数据库、配置标的 freshness、OHLC、source audit。
- 调度：`logs/scheduler/*.last` 与 source audit 最新运行记录。

架构建议：

- `db-health` 应成为调度器和关键研究命令的前置门禁。
- 默认保持只读，不写健康表。
- 只有当调度监控确实需要趋势分析时，再增加可选 `database_health_runs` / `database_health_findings` 落库。
- OHLC 异常后续需要 sample rows 输出，便于定位源数据问题。

---

### 5.6 股票池与特征层

核心模块：

- [phase0/universe.py](../phase0/universe.py)
- [phase0/data_access/local_history.py](../phase0/data_access/local_history.py)
- [phase0/data_governance/adjustment.py](../phase0/data_governance/adjustment.py)
- [phase0/research/diagnostics/factor_effectiveness.py](../phase0/research/diagnostics/factor_effectiveness.py)

职责：

- 构建当前和历史 point-in-time 股票池。
- 维护流动性、市值、行业、ST/退市等过滤约束。
- 构造价格、量能、估值、财务质量和成长因子。
- 对因子有效性做 IC、分组收益、年度稳定性和相关性诊断。

关键边界：

- 当前股票池用于日报和当前观察池。
- 历史回测必须使用每折 point-in-time 股票池。
- 价格特征应优先使用 `qfq_asof`。
- 交易执行价格、涨跌停和停牌判断应基于未复权或真实交易口径，不应使用复权价成交。
- 财务因子必须基于 `announce_date` 控制可见性。

当前因子诊断已覆盖：

- 低波：`low_vol20`, `low_vol60`
- 低换手/低成交额：`low_turnover_rate`, `low_amount_ratio20`
- 动量与反转：`mom20`, `mom60`, `reversal_mom3`, `reversal_mom5`
- 质量与成长：`roe`, `cash_flow_quality`, `profit_growth`, `revenue_growth`, `low_debt_to_asset`
- 估值：`ep`, `low_pb`

---

### 5.7 策略与信号层

核心模块：

- [phase0/walk_forward.py](../phase0/walk_forward.py)
- [phase0/strategies/base.py](../phase0/strategies/base.py)
- [phase0/strategies/registry.py](../phase0/strategies/registry.py)
- `phase0/strategies/*.py`

当前策略层形态：

- 已从单文件硬编码演进为 registry 候选工厂。
- 多个候选策略可以通过统一接口参与 compare。
- `legacy_momentum_low_turnover_v1` 当前降级为兼容基线和动量 sleeve 研究样本，不再是实盘模拟合格策略。

当前候选策略目录包括：

- `legacy_momentum`
- `legacy_momentum_low_turnover_v1`
- `ma_kline_baseline_v1`
- `residual_momentum_reversal_v1`
- `residual_momentum_reversal_v2`
- `quality_growth_price_v1`
- `multifactor_volume_price_filter_v1`
- `theme_exposure_momentum_v1`
- `core_selection_quality_momentum_v1`

架构风险：

- [phase0/walk_forward.py](../phase0/walk_forward.py) 仍承担较多职责：数据加载、特征构造、组合模拟、候选比较和指标计算都集中在一个大模块内。
- 短期可接受，因为系统仍处于研究迭代期。
- 若 T2.6/T2.7 新策略开始稳定，应逐步拆出 `factors/`、`portfolio/`、`evaluation/` 子模块，降低维护成本。

### 5.8 研究情报层

核心资料：

- `refdocs/papers/`
- `knowledge/intelligence/strategy_intelligence_ledger.csv`
- `docs/tasks/research/STRATEGY_INTELLIGENCE_WORKFLOW_TASKS.md`

职责：

- 管理论文、研究报告、公告新闻和策略线索。
- 评估情报质量、创新性、可落地性、数据可用性和偏差风险。
- 维护“情报来源 -> 策略假设 -> 候选任务 -> 实验结果”的追溯关系。
- 为候选策略池、因子诊断、文本事件层和数据建设任务提供上游研究依据。

边界：

- 研究情报层不直接生成交易信号。
- 公告新闻类情报默认只作为解释层、事件时间线或研究假设。
- LLM 可以用于摘要、标签和反方审查，但不能作为最终评分和交易判断的唯一来源。

---

### 5.7.1 关注个股分析工具（规划）

当前状态：

- 项目已有 `brief watchlist`、`brief premarket` 和阶段试用盘前观察池。
- 这些产物是策略驱动的每日观察池和计划层页面，不是用户主动使用的个股分析工具。
- 当前缺少独立工具支持用户添加关注股票、系统持续查询数据、跟踪变化、生成交互式可视化和单股评估报告。

模块定位：

- 关注个股分析工具是面向用户主动关注标的的数据分析可视化工具。
- 用户可以手动添加、分组、备注和归档关注股票。
- 系统定期为关注股票拉取和汇总行情、估值、财务、公告、新闻、行业、资金行为 proxy、策略信号和账户相关信息。
- 工具提供单股交互式看板和可复现评估报告，说明基本面、估值、技术状态、事件风险、数据质量、策略相关性和后续观察点。
- 它不直接生成买卖指令，不覆盖策略信号，不替代股票池，也不把用户关注等同于策略推荐。

核心输入：

- 用户手动加入的关注股票、分组、备注、关注原因和复核周期。
- 行情、估值、财务因子、公告、新闻、行业、指数和跨市场数据。
- 策略候选、每日观察池、模拟账户持仓和交易计划。
- 因子诊断、策略准入、过拟合诊断、回测报告和数据健康检查。
- 市场行为 proxy，例如换手异常、成交额放大、小单/大单资金流估算、龙虎榜、融资融券变化。

核心输出：

- 用户关注股票列表和分组。
- 单股分析看板。
- 单股评估报告。
- 关注理由、用户备注和系统自动生成的研究摘要。
- 基本面、估值、趋势、波动、流动性、拥挤度和事件风险标签。
- 数据质量与可见性说明，例如最新行情日、财务公告日、字段覆盖和异常数据。
- 与当前策略、观察池、模拟账户持仓和历史报告的关联。
- 下一次复核日期、需要继续观察的问题和失效条件。

建议可视化能力：

- 价格与成交：K 线、成交量、换手率、成交额、涨跌停和停牌标记。
- 估值：PE/PB/EP 历史分位、行业相对估值、亏损导致估值缺失提示。
- 财务：收入、利润、ROE、现金流质量、负债率、成长率趋势和公告日标记。
- 因子：当前因子分位、历史因子轨迹、同业对比、策略相关因子雷达。
- 事件：公告、财报、龙虎榜、融资融券、新闻和重大波动时间线。
- 市场行为 proxy：换手异常、成交额放大、小单/大单资金流估算、拥挤度和情绪标签。
- 数据质量：最新数据日、字段覆盖、异常样本、PIT 可见性和 source audit 状态。

建议最小字段：

```text
symbol
name
market
user_group
user_note
focus_reason
focus_level
review_cycle
risk_flags
invalid_condition
last_review_date
next_review_date
status
latest_data_date
latest_dashboard_path
latest_report_path
linked_reports
linked_strategy
linked_account
created_at
updated_at
```

关键边界：

- 股票池回答“哪些股票有资格被研究或交易”。
- 策略信号回答“规则当前如何排序或给权重”。
- 观察池回答“今天盘前需要看哪些计划项”。
- 关注个股分析工具回答“用户关心的这只股票当前发生了什么、质量如何、风险在哪里、数据是否可信、后续该观察什么”。
- 用户添加关注只表示研究兴趣，不表示策略选中，不表示持仓，也不表示交易建议。
- 市场行为 proxy 只能作为风险标签或情绪说明，不能被表述为真实个人账户交易行为。
- 个股分析看板和评估报告必须展示数据日期、价格口径、财务公告日和生成时间，避免把过期数据解释为当前事实。

推荐落地方式：

- 第一版可使用本地 SQLite，例如 `data/stock_focus/stock_focus.sqlite`，保存用户关注列表、备注、分组、复核周期和报告索引。
- 后续提供 CLI：`focus add/list/update/archive/refresh/report/dashboard`。
- `focus refresh` 只更新关注股票相关数据、分析缓存、看板和评估报告，不改变策略股票池或调仓计划。
- 单股报告建议输出到 `reports/stock_focus/YYYY-MM-DD/<symbol>_focus_report.md/html`。
- 单股可视化看板建议输出到 `reports/stock_focus/YYYY-MM-DD/<symbol>_focus_dashboard.html`。
- 桌面 UI 阶段可把它作为左侧 workspace 的一级入口，与报告库、数据治理和模拟账户并列。

---

### 5.8 策略治理层

核心模块：

- [phase0/walk_forward.py](../phase0/walk_forward.py)
- [phase0/research/diagnostics/overfit.py](../phase0/research/diagnostics/overfit.py)
- [phase0/research/diagnostics/factor_effectiveness.py](../phase0/research/diagnostics/factor_effectiveness.py)
- [phase0/strategy_admission.py](../phase0/strategy_admission.py)
- [phase0/reporting.py](../phase0/reporting.py)

当前治理能力：

- walk-forward compare
- effectiveness gate
- cost sensitivity
- OOS report
- market regime report
- overfit diagnostic
- factor effectiveness diagnostic
- qfq adjustment audit
- financial PTI audit
- strategy-admission MVP：窗口稳健性矩阵、全局 admission gate、strategy set、diagnostics suites 和约束复核

策略准入应逐步收敛为统一规则：

```text
data health PASS / acceptable warning
    + qfq_asof price safety
    + PIT universe
    + financial PTI PASS
    + factor effectiveness evidence
    + walk-forward gate
    + overfit risk not high/critical
    + account execution constraints
    = 可进入观察池长期试用
```

当前缺口：

- `overfit-diagnostic` 还未接入 `execution-gate` 和 `brief`。
- `strategy-admission` 已有 MVP，但尚未完整合并 `qfq_asof` 对照、factor diagnostic、financial PTI 和 execution gate。
- 成本敏感性、参数邻域扰动、收益集中度仍需进一步量化并进入 admission 结论。

---

### 5.9 账户与执行仿真层

核心模块：

- [phase0/execution/accounts.py](../phase0/execution/accounts.py)
- [phase0/execution/strategy_ledger.py](../phase0/execution/strategy_ledger.py)
- [phase0/reporting/account_bill.py](../phase0/reporting/account_bill.py)
- [phase0/reporting/strategy_bill.py](../phase0/reporting/strategy_bill.py)（策略账单导出编排；执行撮合核心已拆到 `phase0/execution/strategy_ledger.py`）
- [phase0/reporting/execution_effectiveness.py](../phase0/reporting/execution_effectiveness.py)
- [phase0/reporting/strategy_oos.py](../phase0/reporting/strategy_oos.py)
- [phase0/reporting/strategy_period_compare.py](../phase0/reporting/strategy_period_compare.py)
- [phase0/reporting/market_regime.py](../phase0/reporting/market_regime.py)
- [phase0/reporting/premarket_watchlist.py](../phase0/reporting/premarket_watchlist.py)
- [phase0/accounts.py](../phase0/accounts.py)（兼容旧入口；新代码不要继续依赖）
- [scripts/export_strategy_bill.py](../scripts/export_strategy_bill.py)（兼容旧入口；新代码不要继续依赖）
- [scripts/export_execution_effectiveness_report.py](../scripts/export_execution_effectiveness_report.py)（兼容旧入口；新代码不要继续依赖）
- [scripts/export_strategy_oos_report.py](../scripts/export_strategy_oos_report.py)（兼容旧入口；新代码不要继续依赖）
- [scripts/export_strategy_period_compare.py](../scripts/export_strategy_period_compare.py)（兼容旧入口；新代码不要继续依赖）
- [scripts/export_market_regime_report.py](../scripts/export_market_regime_report.py)（兼容旧入口；新代码不要继续依赖）
- [scripts/export_premarket_watchlist.py](../scripts/export_premarket_watchlist.py)（兼容旧入口；新代码不要继续依赖）

当前能力：

- 模拟账户 SQLite 主账本。
- 日资产、成交、持仓记录。
- 策略组合账单的折内执行撮合、整手约束、涨跌停/停牌阻断和未成交原因。
- A 股 100 股整手、现金约束、卖出回款。
- 成交价 profile：`research` / `live` 与 `close` / `next_open` / `conservative` 等口径。
- 涨跌停、停牌、流动性参与率、未成交原因。
- 真实账户 CSV 对账格式预留。
- 旧 `scripts/export_low_turnover_*.py` 仅保留为兼容入口；新开发应使用 `export_strategy_*` 通用报表模块。

边界：

- 账户层只做模拟、复盘和计划辅助。
- 不接券商 API。
- 不自动下单。
- 不把未成交/部分成交忽略为已成交。

---

### 5.10 交付与运维层

核心入口：

- `brief daily`
- `brief watchlist`
- `brief premarket`
- `brief account-bill`
- `scripts/run_project_scheduler.sh`
- `logs/scheduler/*.last`
- 规划中：`phase0.cli maintain tick/status/run/stop/resume`
- 规划中：`phase0.cli system status/run/tui`
- 规划中：`data/maintenance/maintenance.sqlite`
- 规划中：本地桌面交互 UI

输出目录：

| 目录 | 用途 |
| --- | --- |
| `reports/` | 研究报告、审计报告、HTML 产物、CSV 导出 |
| `reports/watchlist_today/` | 当前阶段试用观察池页面 |
| `logs/` | 调度日志、开发日志、会话记录 |
| `data/` | 长期可复用数据资产，不进 Git |
| `docs/` | 当前有效项目文档 |
| `refdocs/` | 参考资料、论文、背景材料、非当前主线资料 |

当前调度：

- 单一 cron 入口应保持为 `scripts/run_project_scheduler.sh`。
- 已有 `07:20` watchlist、`16:20` HK、`16:30` A 股、`17:10` US、每周财务因子更新等任务。
- `db-health --scope scheduler` 已接入调度前置检查，`cn/error` 门禁已接入关键研究入口。
- 交易日历判断、失败重试、运行窗口和统一状态库仍需增强。

目标形态：

- `scripts/run_project_scheduler.sh` 逐步降级为 wrapper，只负责加载环境并调用 Python 维护编排器。
- 数据治理与维护编排器作为 control plane，统一管理任务 registry、状态机、门禁、重试、报告索引和长 backfill 分片监督。
- 现有 `update-*`、`backfill-*`、`brief`、`db-health` 命令继续作为 data plane，避免一次性重写稳定业务逻辑。
- 长期应在维护编排器之上增加轻量 `System Orchestrator`，作为 TUI / 桌面 UI 的统一入口。

总体编排器分层：

```text
System Orchestrator
    ├── Maintenance Orchestrator
    ├── Research Orchestrator
    ├── Delivery Orchestrator
    ├── Account Orchestrator
    └── Focus Orchestrator
```

原则：

- `System Orchestrator` 只做统一入口、任务注册、状态汇总、报告索引和权限边界。
- 具体业务状态机留在领域子编排器中，避免形成不可维护的单体超级编排器。
- 第一阶段优先落地 `Maintenance Orchestrator`，随后增加 `system status` 和系统级 TUI overview。

---

### 5.11 本地桌面交互 UI 预留

可行性结论：

- 建议预留并分阶段建设现代本地桌面 UI；方向可对标 Notion / Obsidian 的信息组织体验，但不应直接复制其视觉或交互细节。
- UI 的正确定位是“本地研究工作台”和“运维控制台”，不是交易终端。
- 当前阶段可做架构预留和只读原型，不应优先于 Tushare 财务回填、`T6.3` 维护编排器、策略准入报告和正式 daily brief。
- 最合适的触发点是 `T6.3` 第一版完成后：任务状态、报告路径、健康门禁和长任务运行账本都已有统一 API 或状态库，UI 才有稳定数据模型可读。

推荐产品形态：

- 左侧 workspace navigation：数据治理、维护任务、策略研究、观察池、模拟账户、报告库。
- 中心文档/看板区：Markdown 报告、表格、图表、任务详情、策略准入卡片。
- 右侧 inspector：数据口径、最近运行、风险提示、相关报告、命令复现。
- 全局 command palette：执行只读检查、打开报告、触发维护任务、复制 CLI 命令。
- Local-first：默认读取本机 SQLite、`reports/` 和 `logs/`，离线可用。

推荐技术路线：

- 首选：Tauri + Web 前端。
- 备选：Electron + Web 前端。
- 不建议第一版直接做传统 Qt/PySide 桌面端，原因是现有报告和未来交互都更适合 Web 技术栈，且后续可复用到浏览器/PWA。

Tauri 更符合当前项目的原因：

- 本项目偏本地优先、长时间运行、文件/SQLite/报告交互密集，Tauri 的本地 WebView + Rust shell 模式更轻量。
- UI 可以用 TypeScript/React/Vue/Svelte 构建，后端继续通过本地 Python CLI / API / 状态库完成实际工作。
- 权限面可以收窄到项目目录、报告目录和少量命令调用，适合个人本地研究系统。

Electron 适合作为备选的原因：

- 如果未来需要更强 Chromium 一致性、复杂图表、Node 生态集成或更快前端开发便利性，Electron 会更省心。
- 代价是安装包和运行资源更重，安全边界也需要更严格治理。

推荐架构：

```text
Desktop UI
    ↓
Local UI Backend / Command Broker
    ↓
maintenance_orchestrator + phase0 CLI
    ↓
SQLite / reports / logs / source audit
```

边界要求：

- UI 不直接写策略结论，不直接改交易信号。
- UI 不直连券商 API，不提供自动下单入口。
- UI 默认只读展示数据、报告、状态和风险；写操作必须走维护编排器或明确 CLI。
- 涉及 `TUSHARE_TOKEN`、远端同步密钥和账户 CSV 的路径不得在 UI 日志中明文暴露。
- UI 中所有回测、观察池和模拟账户结论都必须展示数据日期、价格口径、策略版本和门禁状态。

分阶段实现：

| 阶段 | 目标 | 完成标准 |
| --- | --- | --- |
| `UI-0` | 设计系统与静态原型 | 明确信息架构、字体/颜色/密度、Notion/Obsidian 风格参考边界 |
| `UI-1` | 只读报告库 | 能浏览 `reports/` Markdown/HTML/CSV，支持日期、任务、策略筛选 |
| `UI-2` | 数据治理控制台 | 展示 `db-health`、source audit、维护任务状态和 backfill summary |
| `UI-3` | 维护任务操作台 | 通过 `maintain run/stop/resume/status` 控制本地任务，保留命令复现 |
| `UI-4` | 策略研究工作台 | 展示 strategy admission、factor effectiveness、overfit、walk-forward 对比 |
| `UI-5` | 模拟账户与观察池 | 展示观察池、持仓、模拟成交、阻断原因和账户风险，不接自动交易 |

设计原则：

- 类 Notion：清晰层级、块状信息组织、轻量命令面板、低干扰阅读体验。
- 类 Obsidian：本地文件优先、报告之间可交叉引用、研究过程可追溯。
- 量化研究适配：高信息密度、表格可排序过滤、日期和口径始终可见、异常状态比装饰更突出。
- 桌面 UI 是现有 CLI / report / SQLite 体系的可视化入口，不是新的业务事实来源。

---

## 6. 关键数据口径

### 6.1 价格口径

| 口径 | 用途 | 风险 |
| --- | --- | --- |
| `bfq_raw` | 真实交易价格、执行、涨跌停、停牌判断 | 不适合直接做长期可比价格特征 |
| `qfq_current` | 兼容旧回测、对照分析 | 可能把未来复权因子折回过去 |
| `qfq_asof` | 严格历史特征与 walk-forward | 计算成本更高，但 PIT 风险更低 |

架构要求：

- 研究价格、交易执行价格和估值判断价格必须分离。
- 历史策略特征优先使用 `qfq_asof`。
- 交易执行和可成交性判断不得使用复权价。

### 6.2 财务因子口径

财务因子必须满足：

- `report_date` 表示报告期。
- `announce_date` 表示可见日。
- 回测某个 as-of date 时，只能使用 `announce_date <= as_of_date` 的记录。
- 历史回填不能用空行覆盖已有有效记录。

当前 Tushare 财务回填仍未完成，因此质量类因子在更长历史窗口的稳定性结论仍需等回填和复核完成后再定。

### 6.3 股票池口径

- 当前股票池用于当前日报/观察池。
- 历史回测使用 point-in-time universe folds。
- 退市、ST、行业、市值、流动性等约束必须按对应 as-of 口径处理。

### 6.4 跨市场口径

- 跨市场信号是 overlay，不是主 ranker。
- US/HK 数据应先落本地库，再被策略读取。
- 时区和交易日差异必须显式处理，不能把未来交易日信息注入 A 股历史样本。

---

## 7. 失败模式与防护

| 失败模式 | 当前防护 | 仍需增强 |
| --- | --- | --- |
| Tushare 请求长任务中断 | 任务表、状态、重试、分片、限速、进度显示 | 自动分片调度和 failed 原因聚合 |
| A 股日线覆盖不足 | update-history 覆盖率检查、source audit、db-health | 调度前置阻断 |
| 复权未来函数 | `adjustment-audit`, `qfq_asof` loader | 默认研究链路全面切换后的回归验证 |
| 财务未来函数 | `financial-pti`, `announce_date` | 回填完成后重新复核 |
| 股票池未来函数 | PIT universe folds, `universe-pti` | 正式 admission 报告合并 |
| 跨市场数据陈旧 | US/HK audit, db-health coverage | 交易日历与时区 aware freshness |
| 策略过拟合 | `overfit-diagnostic` MVP | gate/brief 集成、参数扰动、收益集中度 |
| 执行不可成交 | 账户级仿真 v2 | 与真实账户 CSV 对账闭环 |
| 调度静默失败 | logs/scheduler/*.last、db-health 前置检查 | 维护编排器、运行窗口、重试次数、统一状态库 |
| LLM 越权决策 | 文档边界约束 | 输出层模板继续强化“非交易指令” |

---

## 8. 架构债务

当前最重要的架构债务按优先级排列如下。

### P0

- Tushare 财务历史回填未完成，质量/现金流类因子长期历史诊断仍不完整。
- 调度仍由 shell 脚本承担主要状态判断，缺少统一维护编排器、运行账本和长任务监督。
- 统一 `strategy-admission` 报告已有 MVP，但完整准入判断仍分散在 qfq、factor、financial PTI、execution gate 等报告中。

### P1

- [phase0/walk_forward.py](../phase0/walk_forward.py) 职责过宽，后续稳定后应拆出因子、组合和评估子模块。
- `brief daily` 仍复用 watchlist 兼容路径，正式日报产物需要独立建模。
- `overfit-diagnostic` 已进入 `strategy-admission` MVP，仍未进入 execution gate / brief 主流程。
- `daily_basic.pe_ratio` 覆盖不足仍需建立口径判断，区分数据缺失和亏损公司自然为空。

### P2

- `data/raw_data/` 与 `data/features/` 仍是预留目录，feature store 尚未正式落地。
- FRED/Tiingo 虽有最小接入，但尚未形成完整宏观/跨市场特征资产。
- 港股映射策略仍停留在数据前置和研究阶段，未代码化为正式候选。
- 真实账户 CSV 对账只预留 schema，未形成复盘闭环。

---

## 9. 推荐演进路线

### 阶段 A：数据治理闭环

完成标准：

- Tushare 财务回填 2016Q1-2018Q1 完成。
- failed 任务重试到可接受比例。
- `financial-pti` 重新 PASS。
- `factor-effectiveness` 重跑并记录质量因子覆盖变化。
- `db-health --scope scheduler|cn` 接入调度和研究前置检查。
- 建立 `T6.3` 数据治理与维护编排器专项，先实现状态库、dry-run tick 和维护状态查询。

### 阶段 B：策略准入统一

完成标准：

- 完成 `strategy-admission` 从 MVP 到统一准入报告的升级。
- 合并 qfq_asof、PIT universe、financial PTI、factor effectiveness、overfit、execution gate。
- 明确何种策略能进入长期观察池，何种策略只能作为研究样本。

### 阶段 C：低频低换手候选重建

完成标准：

- 实现 `low_vol_low_turnover_quality_v1`。
- 实现 `quality_low_turnover_monthly_v1`。
- 双口径对照：`qfq_current` vs `qfq_asof`。
- 成本后、账户级执行后仍能通过准入。

### 阶段 D：日常研判产品化

完成标准：

- 正式 daily brief 从 watchlist 兼容路径拆出。
- 调度具备交易日历、运行窗口、重试、健康检查门禁和统一维护状态库。
- 长 backfill 能通过维护编排器统一启动、停止、恢复和查看 shard 状态。
- 报告能区分研究信号、观察信号、可执行计划和阻断原因。
- 本地桌面 UI 进入只读原型阶段，优先作为报告库和数据治理控制台。

### 阶段 E：跨市场和文本增强

完成标准：

- FRED/Tiingo/HK 数据形成稳定 feature assets。
- 跨市场增强只作为风险/情绪 overlay，不变成主 ranker。
- 文本/新闻只进入解释和事件风险层，未验证前不进入交易主信号。
- 桌面 UI 扩展到策略研究工作台、观察池和模拟账户视图，但仍不提供自动交易入口。

---

## 10. 当前推荐操作入口

```bash
# 数据库健康检查
./.venv/bin/python -m phase0.cli db-health --config config.yaml --scope all

# Tushare 财务历史回填
./.venv/bin/python -m phase0.cli backfill-tushare-financials \
  --config config.yaml \
  --start-period 2016-03-31 \
  --end-period 2018-03-31 \
  --max-requests-per-minute 120 \
  --max-runtime-minutes 180

# 因子有效性诊断
./.venv/bin/python -m phase0.cli factor-effectiveness --config config.yaml

# 策略过拟合诊断
./.venv/bin/python -m phase0.cli overfit-diagnostic --config config.yaml

# A 股数据更新
./.venv/bin/python -m phase0.cli update-history --config config.yaml

# 阶段试用观察池
./.venv/bin/python -m phase0.cli brief watchlist --config config.yaml
```

---

## 11. 架构治理规则

后续开发默认遵循：

- 任何新策略先进入 registry 和 compare，不直接进入日报。
- 任何新数据源先进入 adapter、落库、source audit，再进入策略或日报。
- 任何财务/公告/文本类数据必须有 as-of 可见性说明。
- 任何回测结果必须说明价格口径、股票池口径、成本口径和执行口径。
- 任何新调度任务必须有日志、锁、last marker、失败行为和健康检查策略。
- 任何 LLM 输出只能解释和总结，不能绕过策略与风控生成交易动作。
