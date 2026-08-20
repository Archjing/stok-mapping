# stok-mapping 架构说明

> 面向对象：项目维护者、策略研究者与后续实现者
> 最后审视：2026-08-12
> 当前实现命名：`quant`（`phase0` 仅保留临时 CLI 兼容转发，其余 `phase0.*` 领域模块不再作为第二命名空间支持）

## 1. 系统定位与边界

`stok-mapping` 是本地优先、可复现、可审计的量化研究与模拟执行系统：A 股本土因子负责组合研究，跨市场数据负责风险、情绪和映射研究。系统输出研究报告、观察池、模拟账本和盘前页面；它不连接券商 API，不自动下单，也不让新闻或 LLM 直接改变订单。

两类策略执行模型必须分开理解：

| 模型 | 适用策略 | 主验证链路 | 当前状态 |
| --- | --- | --- | --- |
| 组合股票池 | A 股选股、多因子、低换手等 | PIT 股票池 → `qfq_asof` → walk-forward → admission | 主策略治理链路；当前没有批准的候选 |
| 单 ETF 跨市场映射 | `cross_market_semiconductor_timing_etf_v1` | 已完成美股日信号 → 下一个 A 股交易日 → 5 分钟模拟执行 | 已有专用模拟账户；每个 ETF 仍需独立验证 |

不能把“有模拟账户”解释为“已通过统一 admission”或“可实盘”。同样，组合策略的 `qfq_asof` 结论不能直接替代 ETF 的分钟级执行验证。

## 2. 分层与依赖方向

```text
外部 Provider / RSS / 本地导入包
        ↓
data_access（读取适配） ← data_governance（更新、回填、审计）
        ↓
SQLite 数据资产（A 股、ETF、US、HK、新闻、模拟账户）
        ↓
universe / features / strategies / research
        ↓
walk_forward 或 intraday execution
        ↓
reporting / brief / static site / maintenance orchestration
        ↓
本地报告、日志、受限远端静态站点
```

依赖原则：CLI 只负责参数解析与路由；数据写入由 `data_governance` 或执行模块负责；策略不得直接联网；报告读取已落库数据；`config.yaml` 是长期参数与受控 universe 的事实源。

## 3. 数据资产与生命周期

| 资产 | 路径 | 主要内容 | 生命周期与约束 |
| --- | --- | --- | --- |
| A 股研究主库 | `data/a_share_history.sqlite` | 日线、复权、财务、交易日历、股票和指数元数据 | 用于 PIT 股票池与组合研究；`qfq_asof` 不使用未来复权因子 |
| ETF 历史库 | `data/etf_history.sqlite` | catalog、日线、复权因子、5 分钟线、开盘快照 | 只接受配置声明的 universe/sector；回填可恢复且必须审计 |
| US 市场库 | `data/us_market_history.sqlite` | `us_daily_bars` 与 source audit | 策略、盘前页和比较图只读取本地已确认数据 |
| HK 市场库 | `data/hk_market_history.sqlite` | 港股日线与 source audit | 跨市场研究资产；交易日历仍待加强 |
| 新闻库 | `data/ai_corpus/ai_corpus.sqlite` | RSS 元数据与归档 | 盘前人工研判；不进入自动订单逻辑 |
| 模拟账本 | `data/simulated_trading/` | 账户、资产、成交、订单事件、运行状态 | 本地运行资产；不得进入 Git 或静态站点 |
| 研究原型库 | `data/custom_indices.sqlite` | `CN_PANIC_HO30` 试验性输出 | 尚未纳入正式配置、CLI、调度或数据治理 |

所有 SQLite、报告、日志、原始归档和账本默认是 local-only。Git 只保存代码、配置、文档与可复现测试夹具。

### 3.1 ETF 数据边界

ETF 采用独立库，避免把基金复权、分钟线与 A 股个股主库混写。`single_etf` 仅是显式的受控单标的回填入口，不代表全市场 ETF 自动下载。严格研究读取必须同时满足回填任务成功和 audit 通过；日线、复权、分钟线或开盘快照缺失时，执行模块应失败或报告不完整，而不能猜测补值。

### 3.2 US 数据分组

| 分组 | 标的 | 当前作用 |
| --- | --- | --- |
| `core_signal` | `^SOX`、`^VIX` | 半导体 ETF 映射策略的唯一自动交易输入 |
| `semiconductor_breadth` | AMD、TSM、ASML、AMAT、LRCX、INTC、SMH | 判断产业链广度与共振 |
| `mega_tech_beta` | AAPL、MSFT、GOOGL、AMZN、META | 区分半导体需求与大型科技 beta |
| `rates` | `^TNX` | 观察利率对科技估值的压力 |
| `china_tech_sentiment` | BABA、JD、KWEB | 中概与中国科技情绪观察 |
| `reference_and_fx` | `^NDX`、NVDA、`CNY=X` | 市场背景参考 |

除 `core_signal` 外，其余分组目前仅服务研究和盘前观察，不能写成会自动调整仓位或下单。US 主库当前仍使用 yfinance 过渡 provider，Yahoo 限流是已知风险；FRED 的参考序列不等于替换主库全部数据源。

## 4. 策略、研究与执行

### 4.1 组合策略研究链路

```text
A 股本地库
  → point-in-time universe folds
  → qfq_asof 特征与策略
  → walk-forward / compare / execution diagnostics
  → overfit、集中度、数据健康检查
  → strategy-admission 报告
```

`baseline_admission_all_v1` 当前有 14 个注册条目，其中含单 ETF 跨市场策略。它是配置范围，不是“14 个已经可比、已经通过的策略”。组合准入必须在明确数据截止日、成本、基准、样本外窗口和失败原因的报告中解释。

### 4.2 半导体 ETF 美股情绪映射账户

账户 `semiconductor_timing` 使用策略 ID `cross_market_semiconductor_timing_etf_v1`，当前账户名为“半导体ETF美股情绪映射择时_v1”，初始现金为 200,000，默认标的是 `SH.512480`。

执行时间线：

```text
完成的美股交易日：^SOX / ^VIX 生成信号
             ↓
其后的首个 A 股交易日：按开盘价或预先提交的弱信号限价单入场
             ↓
下一 A 股交易日：用已完成 5 分钟 K 线追踪止损；未触发则按 14:55 bar 收盘价退出
```

- 信号参数和账户标的来自 `config.yaml`；当前策略阈值为 SOX 涨幅大于 0.5%、VIX 小于 19，强信号阈值为 SOX 大于 1%。
- 强信号按开盘价入场。弱信号限价单若全天不触及会撤单，**当天不追价买入**；这是可执行、无未来函数的规则。
- 订单事件、资产、成交和运行状态保存到专用 SQLite 表。`intraday-account` 默认只读重放；`--recover-missing` 是盘后核验/恢复工具，不能代替盘中运行器。
- `09:25` 开盘快照任务只在存在 enabled 的 `single_etf_intraday` 账户时启用。当前维护编排器并未在此文档中承诺每五分钟自动抓取；`scripts/fetch_etf_5min_accounts.py` 是分钟数据采集依赖，持续实时调度需单独验证。
- 允许的半导体 ETF 白名单在配置中声明，但只有完成各自数据覆盖、回测、walk-forward 和 admission 的标的才可启用独立账户。

## 5. 交付与运维

### 5.1 维护编排

系统 cron 只调用 `scripts/run_project_scheduler.sh`，由 `quant.cli maintain tick` 根据时间窗、锁、重试状态与交易日条件决定执行。已知注册任务包括：

- `06:30`：`us_market_news` RSS 元数据采集；
- `07:20`：`brief watchlist --all-accounts`；
- `09:25`：对 enabled 的单 ETF 账户采集 ETF 开盘快照；
- `15:05`：`core_index_daily_tail` 收盘后快速刷新四个看板核心指数（`SH.000001`/`SZ.399001`/`SH.000300`/`SZ.399006`）；
- `15:10`：`china_options_ho` HO 期权链与 `CN_PANIC_HO30`（若启用）；
- `16:30`：`a_share_history` A 股个股日线/估值/复权因子（估值字段盘后较晚可用，故不提前）；
- `16:35`：`index_daily_tail` 全量指数尾部补数；
- `16:45`：模拟账户账本确认及量化静态站点发布。

调度必须记录成功 stamp、失败原因与日志。港股和美股的独立交易日历、以及 5 分钟实时采集的常驻调度仍是待加强项。

### 5.2 静态站点与盘前页面

`quant/reporting/quant_static_site.py` 生成 `reports/static_site/quant/`，包括账户页、资产/成交信息、盘前观察池和研究比较图。半导体账户页面展示 SOX/VIX 和 `us_market_news` 的来源、发布时间、标题、URL；新闻只做人工研判。

`site build` 只生成本地文件；`site sync` 与 `site publish` 通过 rsync 同步。远端参数从 `.env` 读取：

```bash
QUANT_SITE_SYNC_REMOTE=linuxuser@108.61.182.91
QUANT_SITE_SYNC_REMOTE_DIR=/var/www/share/quant/
QUANT_SITE_SYNC_PASSWORD=...
```

同步目标必须以 `/quant/` 结尾。密码通过临时 `SSH_ASKPASS` 传给 ssh，不进入命令行；`.env`、密码、SQLite 和原始数据都不得发布。

比较图模块 `market_comparison_chart.py` 目前支持 `us_daily_bars` 和 ETF `etf_qfq` 两种本地读取器。它可配置两个序列、起始日期、原始值观察区间、源市场单日映射阈值、连续天数和每日涨跌阈值；上涨使用红色、下跌使用绿色。观察区间和颜色是研究可视化，不是交易阈值。

## 6. 关键口径与失败处理

- **研究价格 vs 执行价格**：`qfq_asof` 服务历史研究；原始/开盘/分钟价格服务模拟成交语义。不得混用。
- **as-of 可见性**：特征、财务记录、交易日历和复权因子均不得读取决策时点之后的信息。
- **数据新鲜度**：当前盘前输出必须审计最新日期、覆盖率和 source audit；源端失败不能以旧快照伪装最新行情。
- **分钟数据**：缺关键 bar 时不得用日线或未来分钟线替代；恢复命令不静默覆盖与重放不一致的实时账本。
- **账户状态**：总资产、现金、证券市值和仓位必须由账本明确给出；空仓账户应显示“全部现金、证券市值 0、仓位 0%”，而非“暂无”。
- **密钥与网络**：token 和站点密码只从环境变量读取；错误日志不得回显 secret。

## 7. 当前架构债务与优先级

| 优先级 | 项目 | 完成标准 |
| --- | --- | --- |
| P0 | 各 ETF 的独立研究与准入 | 数据覆盖、成本后回测、walk-forward、admission 与账户配置逐标的一致 |
| P0 | US provider 稳定性 | Yahoo 限流可观测；关键信号有经许可的可靠来源与 freshness 审计 |
| P1 | 5 分钟实时调度 | 明确行情到达、开盘建单、bar 完成、盘后恢复和补数的可观测服务边界 |
| P1 | 多市场交易日历 | A 股、US、HK 的独立交易日、半日市和异常休市判断 |
| P1 | 统一策略治理 | 将专用单 ETF 执行的验证口径与组合 admission 并列管理，而不制造伪可比排名 |
| P2 | `CN_PANIC_HO30` 工程化 | 去除硬编码路径，接入配置/CLI/审计/调度，并先完成数据质量验证 |
| P2 | `quant` 命名空间收尾 | 观察期后移除 `stok-phase0` 与 `phase0.cli` 兼容转发（迁移计划 Task 12），不破坏现有命令 |

## 8. 维护入口

- [开发计划](DEVELOPMENT_PLAN.md)：状态、优先级和验收门槛。
- [编码规范](CODING_STYLE_RULES.md)：实施边界与测试要求。
- [CLI 使用说明](QUANT_CLI_USER_GUIDE.md)：实际命令和参数。
- [数据资产说明](../data/README.md)：数据库、回填和价格口径。
- [策略研发规范](STRATEGY_DEVELOPMENT_GUIDELINES.md)：从研究假设到准入的流程。
