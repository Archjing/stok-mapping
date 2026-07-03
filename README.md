<div align="center">
<img src=".\assets\brand\stok-mapping-wordmark.png"  width="90%" align="center">
</div>

# stok-mapping

A 股本土因子为主、跨市场风险/情绪 overlay 为辅的量化研究与盘前研判工具。

本项目不是自动交易系统，也不是通用量化平台。当前目标是形成一条可验证、可复盘、可解释的研究链路：

```text
数据源同步 -> 本地历史库 -> 股票池/特征 -> 候选策略 -> walk-forward/gate -> 报告/观察池
```

核心输出是观察池、风险暴露说明、信号等级、盘前情景推演和候选策略对比结果，不输出自动下单指令。

项目根目录还提供了一个短命令 wrapper：`./runit` 等价于 `./.venv/bin/python -m phase0.cli`。

## 常用补跑 / 维护命令

下面命令默认在项目根目录执行。涉及外部数据源时需确保 `.env` 中的 token 已配置，且当前环境具备联网能力。

```bash
# 项目内快捷入口，等价于 ./.venv/bin/python -m phase0.cli
./runit --help

# 重跑当前日报主入口：先更新 A 股日线历史库，再生成阶段试用观察池页面
./.venv/bin/python -m phase0.cli brief daily

# 直接运行阶段试用观察池入口，当前与 brief daily 同路径
./.venv/bin/python -m phase0.cli brief watchlist

# 只生成盘前观察池，不先更新 A 股历史库
./.venv/bin/python -m phase0.cli brief premarket

# 导出最新已确认模拟交易账单
./.venv/bin/python -m phase0.cli brief account-bill

# 更新 A 股日线历史数据
./.venv/bin/python -m phase0.cli update-history --config config.yaml

# 更新美股 / ETF / VIX / CNH 日线历史数据
./.venv/bin/python -m phase0.cli update-us-market-history --config config.yaml

# 更新港股日线历史数据
./.venv/bin/python -m phase0.cli update-hk-market-history --config config.yaml

# 更新 A 股季度财务因子
./.venv/bin/python -m phase0.cli update-financials --config config.yaml

# 重建本地因子股票池报告
./.venv/bin/python -m phase0.cli build-universe --config config.yaml

# 运行数据库健康检查门禁
./.venv/bin/python -m phase0.cli db-health --config config.yaml --scope cn --fail-on error

# 运行完整 Phase 0 主流程
./.venv/bin/python -m phase0.cli run --config config.yaml

# 运行当前全候选策略准入复核
./.venv/bin/python -m phase0.cli strategy-admission --config config.yaml \
  --presets baseline_2y_1y_5fold \
  --strategy-set baseline_admission_all_v1

# 校验投资策略情报台账
./.venv/bin/python -m phase0.cli intelligence validate --config config.yaml
```

## 当前状态

- `docs/DEVELOPMENT_PLAN.md` 是当前主线状态事实源；若其他文档与其冲突，以该文件为准。
- Phase 0 工程链路已验证可运行：数据链路、本地历史库、股票池、walk-forward、compare、报告与治理命令可闭环执行。
- 已创建本地 A 股研究主库 `data/manual_history/a_share_history.sqlite`，用于回测、股票池、数据新鲜度保护和相关数据审计。
- 已导入 A 股前复权/不复权日线、股票列表、交易日历、退市清单、指数元数据和指数日线。
- 已接入季度财务因子表，覆盖 `roe`, `revenue_growth`, `profit_growth`, `operating_cash_flow_to_net_profit`, `debt_to_asset`，当前本地库覆盖 2018-06-30 至 2026-03-31 共 32 个季度。
- 已新增 `data/us_market_history.sqlite`，当前跨市场 overlay 从美股/ETF/VIX/CNH 本地库读取，不再在策略运行时临时抓取 yfinance。
- 已实现股票池构建、walk-forward 回测、候选策略 compare、effectiveness gate 和报告输出。
- 策略层已拆分为 `phase0/strategies/` 注册表结构，便于新增候选策略。
- 已增加开发期统一调度入口：系统 cron 只调用 `scripts/run_project_scheduler.sh`，当前由 `phase0.cli maintain tick` 负责交易日历、运行窗口、重试和状态记录。
- 严格 `qfq_asof` + point-in-time 股票池 + `strategy-admission` 复核后，当前**无可用于 paper review 或实盘模拟的合格策略**，当前**没有 selected candidate**。
- `legacy_momentum_low_turnover_v1` 已降级为兼容基线和研究参考样本；旧 `qfq_current` / 旧 gate 结果不能视作当前准入结论。
- `baseline_admission_all_v1` 配置层已包含 12 个候选；main 上仍需重跑全候选 admission 以纳入 `sleeve_composite_v1`，当前 sleeve 证据来自 scoped admission 且结论为 `reject`。
- T5.2 投资策略情报工作流已建立 RAG-ready Markdown / CSV 语料基础：核心情报 note、策略转化草案、月度扫描索引、RAG 语料规范和 manifest 已落地；该层现位于 `knowledge/intelligence/`，只服务检索、摘要、反方审查和任务规划，不直接生成交易信号。
- 账单导出和策略解释性输出已补齐基础版本，但这些产物不代表策略已通过实盘模拟门禁。
- 账户级仿真 v2 已加入成交价口径、涨跌停、停牌、流动性参与率、未成交原因和真实账户 CSV 对账预留。
- 历史 walk-forward / execution-gate 已默认使用 point-in-time 股票池：每一折按训练窗口结束日从本地历史库只读生成股票池，避免用当前股票池回测过去；日报 / watchlist / 模拟账户仍使用当前每日更新股票池。
- 当前主阻塞点是：在 `qfq_asof`、PIT 股票池、成本后和 admission 口径下完善策略池，优先复核低波低换手质量主线、参数稳定性、行业集中和换手/churn。

旧 `reports/phase0_effectiveness_report.md` 中的 `PASS` 与旧 selected candidate 结论，只能作为兼容口径/研究参考，不得解释为当前可进入实盘模拟。当前准入判断应以 `docs/DEVELOPMENT_PLAN.md` 与后续 `strategy-admission`、`qfq_asof`、过拟合诊断、行业集中和执行诊断结论为准。

## 架构层次

当前系统可以理解为 6 层：

- 数据源接入层：`Tushare`, `AkShare`, `yfinance`，并已最小接入 `FRED` 和 `Tiingo`。
- 数据管理层：A 股 / US market 本地 SQLite 历史库、增量更新、覆盖率检查、新鲜度保护。
- 股票池与特征层：A 股股票池、流动性/市值/行业约束、技术特征、财务因子。
- 策略与信号层：本土主因子策略、跨市场 overlay、解释层。
- 策略评估与治理层：walk-forward、compare mode、effectiveness gate、strategy change log。
- 交付与交互层：Markdown/CSV 报告、Agent 辅助摘要，后续可扩展 Web/PWA/Tauri。

详细架构说明见：

```text
docs/PROJECT_ARCHITECTURE_OVERVIEW.md
```

项目级流程与标准：

```text
docs/STRATEGY_DEVELOPMENT_GUIDELINES.md
docs/strategy_explanations/INDEX.md
```

## 数据源策略

当前确认的数据源层级：

- 国内股票主源：`Tushare`
- 国内 fallback：`AkShare` / 新浪快照 / 本地 A 股研究主库
- 美股/ETF/VIX/CNH 当前库：`data/us_market_history.sqlite`，现阶段 provider 为 `yfinance`，后续美股个股与 ETF 计划主源升级为 `Tiingo`
- 港股库：`data/hk_market_history.sqlite` 已启用并完成 30 标的初始观察池批量落库，当前 provider 为 `yfinance`；策略主链路仍未挂载，需等覆盖率、新鲜度、复权口径和交易日历稳定后再接入应用链路。截至 2026-06-02，Tiingo 对 `HK.00700`、`HK.09988`、`0700.HK`、`9988.HK` 等格式实测均返回 `404 Ticker not found`，暂不适合作为港股正式源
- 宏观 / 利率 / VIX 计划主源：`FRED`
- `yfinance`：保留为 fallback，不再作为长期正式主源

当前 A 股主链路是：

```text
Tushare daily/daily_basic/adj_factor -> a_share_history.sqlite -> 股票池 / 回测 / 报告
```

`phase0 run` 启动时会先执行 `manual_history_update` 预检查：本地研究主库已新鲜则直接复用 SQLite；本地库落后时优先用 Tushare 增量补齐，低覆盖或失败时才进入 fallback。这样做是为了让回测可复现，避免每次 walk-forward 逐只股票在线抓取导致结果漂移。

跨市场 overlay 当前链路是：

```text
yfinance -> us_market_history.sqlite -> cross-market overlay -> walk-forward/report
```

`phase0 run` 会在策略评估前按 `us_market_history.run_before_phase0` 更新 US market 本地库。策略读取的是落库后的 `us_daily_bars`，不是运行时临时 yfinance 请求；若本地库覆盖率不足且 `runtime_yfinance_fallback: false`，跨市场特征会退化为空并记录告警，避免在线源静默改变回测结果。

Walk-forward 加速采用保守缓存边界：公共原始行情、fold 构造和 benchmark 数据可以复用；策略自己的 `prepare_panel` 只按 `strategy_id + strategy_cfg + fold 输入指纹` 缓存，不跨策略共享。诊断耗时时可运行：

```bash
./.venv/bin/python -m phase0.cli strategy-admission --config config.yaml \
  --presets baseline_2y_1y_5fold --profile
```

生成的 profile JSON/CSV 位于 `logs/perf/`，本地缓存默认位于 `data/cache/walk_forward/`，均不纳入普通 Git 提交。

当前 `Tiingo` 和 `FRED` 已完成最小接入，正式入口均在 `phase0/data_access/connectivity.py`。`phase0/data_sources.py` 仅保留为旧导入兼容入口：

```text
docs/tasks/data-sources/TIINGO_IMPLEMENTATION_TASKS.md
docs/tasks/data-sources/FRED_IMPLEMENTATION_TASKS.md
```

Tiingo 当前还新增了一个最小新闻抓取入口 `fetch_tiingo_news()` 和探测模块 `phase0.intelligence.tiingo_news_probe`，用于验证 `ticker 列表 + 主题标签 + 时间窗口` 三类过滤条件及 token 权限状态；`scripts/tiingo_news_probe.py` 仅保留为兼容旧入口。当前实测结论是：项目所用 token 可访问 Tiingo 日线接口，但访问 `/tiingo/news` 返回 `403 You do not have permission to access the News API`，因此新闻能力暂不可用。

## 本地数据

默认数据库：

```text
data/manual_history/a_share_history.sqlite
data/us_market_history.sqlite
data/hk_market_history.sqlite
```

数据库不进入 Git。目录说明见：

```text
data/manual_history/README.md
```

`a_share_history.sqlite` 的时效保护只限制“当前股票池 / 当日研判”场景：如果本地最新交易日超过配置允许滞后，系统不会用旧快照生成当前股票池，而是返回空并告警。该限制不等于禁用研究主库，历史回测、指定历史区间分析和历史日线读取仍可继续进行。

当前主要表包括：

- `market_daily_bars`: A 股日线，含前复权/不复权数据。
- `market_stocks`: 股票元数据与横截面字段。
- `market_financial_factors`: 季度财务因子表，当前配置默认维护最近 32 个季度。
- `trading_calendar`: 交易日历。
- `delisted_stocks`: 退市股票列表。
- `market_indices`: 指数元数据。
- `market_index_bars`: 指数日线。
- `market_data_source_runs`: 数据源增量更新审计记录。

`us_market_history.sqlite` 当前用于跨市场 overlay，主要表包括：

- `us_daily_bars`: `^NDX`, `^SOX`, `NVDA`, `KWEB`, `^VIX`, `CNY=X` 的日线数据。
- `us_data_source_runs`: US market 数据源更新审计记录，记录 `source`, `fetched_at`, `latest_trade_date`, `coverage` 和写入行数。

`hk_market_history.sqlite` 当前已启用并完成 30 标的初始观察池批量落库，仍处于独立数据层验证阶段，不挂到策略或报告链路。等港股覆盖率、新鲜度、复权口径和交易日历稳定后，再接入应用。

### 数据目录边界

当前代码已经体现了“`data/` 放长期可复用数据资产，`reports/` 放运行输出和验收记录”的大方向，但 `data/raw_data/` 与 `data/features/` 仍是预留目录，尚未成为正式写入路径。

当前已落地的数据资产主要包括：

- `data/manual_history/a_share_history.sqlite`：A 股本地研究数据库，承载日线、股票元数据、交易日历、退市清单、指数数据和财务因子。
- `data/us_market_history.sqlite`：美股 / ETF / VIX / CNH 跨市场 overlay 本地库。
- `data/hk_market_history.sqlite`：港股观察池历史库，当前用于独立数据层验证，不参与主策略链路。
- `data/universe/`：股票池和横截面快照产物，包括 `local_factor_universe.csv`、`a_share_snapshot.csv` 以及对应说明报告。

当前 `reports/` 主要用于：

- Phase 0 数据源、walk-forward、effectiveness gate、成本敏感性和策略变更报告。
- 账单、盘前观察池、HTML 预览、CSV 导出和归档。
- 报告生成所需的临时缓存，例如 `reports/cache/low_turnover_panel.pkl`。

后续落库边界如下：

- `data/raw_data/`：用于保存接近原始源口径的快照或响应，例如 FRED 序列、Tiingo 日线、Tushare 批量导出和其他外部数据源原始落盘。
- `data/features/`：用于保存已经清洗、对齐并可被策略或日报复用的特征表，例如跨市场映射特征、宏观状态特征、技术/财务组合特征和信号输入表。

当前 FRED 最小缓存已按数据层边界配置到 `data/cache/fred`。若后续需要保留更接近原始源口径的完整响应归档，可进一步迁入或扩展到 `data/raw_data/fred`。HK-A mapping factor 探测实现位于 `phase0.intelligence.hk_a_mapping_factors`，`scripts/export_hk_a_mapping_factors.py` 仅保留为兼容旧入口；`reports/hk_a_mapping_factors` 目前仍按实验输出处理，若未来成为策略稳定输入，应迁移到 `data/features/cross_market/`。

## 常用命令

本项目应独立运行。可以复用或迁移其他项目中的经验，但运行时不应依赖兄弟仓库源码路径或外部项目专属虚拟环境。

安装本项目依赖：

```bash
uv sync
```

### CLI 路由总览

当前推荐统一使用 `phase0.cli` 的 `brief ...` 层级入口。所有带 `--config` 的命令默认值都是 `config.yaml`，在项目根目录执行时通常可以省略。

| 路由 | 用途 | 状态 |
| --- | --- | --- |
| `brief daily` | 当前日报主入口；先更新 A 股历史库，再生成阶段试用观察池页面 | 推荐 |
| `brief watchlist` | 阶段试用观察池入口；当前与 `brief daily` 同执行路径 | 推荐 |
| `brief premarket` | 只导出原始盘前观察池，不更新 A 股历史库 | 推荐 |
| `brief account-bill` | 从 SQLite 导出最新或指定日期的模拟交易账单 HTML | 推荐 |
| `update-history` | 更新 A 股本地日线历史库 | 推荐 |
| `update-us-market-history` | 更新 US market 跨市场历史库 | 推荐 |
| `update-hk-market-history` | 更新港股历史库；当前是否实际启用取决于 `hk_market_history.enabled` | 预留 / 可检查 |
| `update-financials` | 更新 A 股季度财务因子 | 推荐 |
| `run` | 运行 Phase 0 主流程 | 研究入口 |
| `cost-sensitivity` | 运行显式成本敏感性测试 | 研究入口 |
| `bill` | 导出当前主策略低换手回测账单、日资产表和 HTML 预览 | 研究入口 |
| `market-regime` | 导出市场状态分段验证报告 | 研究入口 |
| `oos-report` | 导出连续 OOS 报告 | 研究入口 |
| `execution-gate` | 运行账户级执行仿真 gate | 研究入口 |
| `financial-pti` | 审计财务因子 point-in-time 有效性 | 研究入口 |
| `build-universe` | 构建本地因子股票池 | 维护入口 |
| `import-history` | 完整重建 / 导入 A 股离线历史库 | 维护入口 |
| `import-index-history` | 只重建指数元数据和指数日线表 | 维护入口 |

兼容旧入口仍保留，但后续文档和定时任务应优先使用 `brief ...`：

```bash
./.venv/bin/python -m phase0.cli daily-brief
./.venv/bin/python -m phase0.cli premarket
./.venv/bin/python -m phase0.cli brief daily-brief
```

运行 Phase 0：

```bash
./.venv/bin/python -m phase0.cli run --config config.yaml
```

该命令会自动加载项目根目录 `.env`，因此 `TUSHARE_TOKEN` 放在 `.env` 后不需要手工 `export`。数据源连通性结果写入 `reports/phase0_data_source_report.md`。主测试使用 `walk_forward.slippage: 0.00246`，不会自动运行成本敏感性测试。

成本敏感性测试是单独路径，必须显式指定场景：

```bash
./.venv/bin/python -m phase0.cli cost-sensitivity --config config.yaml \
  --scenario base_research_cost:0.001 \
  --scenario main_personal_execution:0.00246 \
  --scenario stress_slippage_0_003:0.003 \
  --scenario stress_slippage_0_005:0.005
```

也可以显式使用 `config.yaml` 中的 `cost_sensitivity.scenarios`：

```bash
./.venv/bin/python -m phase0.cli cost-sensitivity --config config.yaml --use-config-scenarios
```

导出当前主策略账单、日资产表和 HTML 预览：

```bash
./.venv/bin/python -m phase0.cli bill --config config.yaml
```

账单使用 `phase0.execution` 中的账户级仿真 v2 参数，当前默认包含 `price_mode: next_open`、`lot_size: 100`、`max_participation_rate: 0.05`、涨跌停检查和停牌检查。输出会记录全部成交、部分成交、未成交及原因。

成交价口径中的日期含义需要区分：`close` 表示执行日收盘价，即观察池对应执行日 15:00 附近价格；`next_open` 表示执行日开盘价，即观察池对应执行日 09:30 附近价格；`conservative` 表示执行日开盘价叠加保守缓冲后的估算价格。

按账户级仿真规则重跑 effective gate：

```bash
./.venv/bin/python -m phase0.cli execution-gate --config config.yaml
```

`execution-gate` 是独立于默认 `phase0_effectiveness_report.md` 的“实盘仿真回测”管线。默认读取 `config.yaml` 中的 `live_execution_backtest.default_profile`，再按名称加载 `live_execution_backtest.profiles.<profile>` 的完整参数组合，不在脚本里硬编码 profile 参数。

`research` / `live` profile 只控制执行假设和交易摩擦，例如滑点、佣金、成交价口径、涨跌停 / 停牌检查、整手约束和最大成交参与率；它不选择股票池。历史回测的股票池边界由 `universe.point_in_time_for_backtest` 控制，默认开启：每折按训练窗口结束日只读生成 point-in-time 股票池。当前日报、watchlist 和模拟账户继续使用 `data/universe/local_factor_universe.csv` 这类当前股票池产物。

当前内置两套 profile：

- `research`：策略研究回测，当前使用 `slippage: 0.001`、`commission: 0.00025`、`stamp_duty_sell: 0.0005`、`price_mode: close`，并关闭涨跌停 / 停牌检查和流动性参与率限制。
- `live`：实盘仿真回测，当前使用 `slippage: 0.00246`、`commission: 0.00025`、`stamp_duty_sell: 0.0005`、`price_mode: next_open`、`lot_size: 100`、`max_participation_rate: 0.05`，并开启涨跌停和停牌检查。

显式指定 profile：

```bash
./.venv/bin/python -m phase0.cli execution-gate --config config.yaml --profile research
./.venv/bin/python -m phase0.cli execution-gate --config config.yaml --profile live
```

临时覆盖单项执行参数，用于压力测试或敏感性检查：

```bash
./.venv/bin/python -m phase0.cli execution-gate --config config.yaml \
  --profile live \
  --slippage 0.003 \
  --commission 0.00025 \
  --stamp-duty-sell 0.0005 \
  --price-mode conservative \
  --max-participation-rate 0.03
```

默认输出目录为：

```text
reports/live_execution_backtest/
```

可用 `--output-dir` 为不同 profile 或压力测试生成独立批次目录：

```bash
./.venv/bin/python -m phase0.cli execution-gate --config config.yaml \
  --profile live \
  --output-dir reports/live_execution_backtest/live_profile
```

生成阶段试用简报 pipeline：

```bash
./.venv/bin/python -m phase0.cli brief daily
./.venv/bin/python -m phase0.cli brief watchlist
```

`brief daily` 是当前日报主入口。现阶段完整日报产物尚未独立实现，该入口暂时复用 `brief watchlist` 的阶段试用简报生成代码：先执行 A 股本地历史库增量更新，再导出当前有效主策略的 07:30 盘前观察池；如果历史库插入了新行，会自动刷新低换手策略 panel cache，避免基于旧缓存生成观察池。`brief watchlist` 可直接调用同一阶段试用观察池管线。`--config` 默认值为 `config.yaml`，在项目根目录执行时可以省略。

`brief daily` / `brief watchlist` 的报告按简报日期归档，日期来自观察池中的 `盘前检查时间`，不是系统运行时间。输出路径格式为：

```text
reports/<brief_date>/phase0_premarket_watchlist_<brief_date>.csv
reports/<brief_date>/phase0_watchlist_report_<brief_date>.html
```

`brief watchlist` 会维护模拟账户主账本，SQLite 为主存储：

```text
data/simulated_trading/simulated_accounts.sqlite
```

当前会自动创建并更新四张表：

```text
simulated_accounts       # 模拟账户配置
account_daily_assets     # 每日账户资产、股票资产、现金资产、收益额
account_trades           # 每笔模拟交易，含买卖方向、价格、金额、股数、手数
account_positions        # 每日持仓快照
```

同时保留一份连续模拟仓位 CSV 流水，作为兼容导出：

```text
data/simulated_trading/phase0_daily_brief_ledger.csv
data/simulated_trading/phase0_daily_account_ledger.csv
```

现阶段该流水默认按程序自动生成的目标仓位滚动；后续接入用户模拟交易确认后，可用用户实际成交/持仓状态替代这份自动状态。简报中的 `交易动作`、`当前权重`、`目标权重`、`权重变化` 使用连续模拟口径，`策略信号动作` 保留本次策略模型自身的信号口径。

注意：`brief watchlist` 当前展示的是计划层观察池；模拟账户账单只写入本地日线库已有对应执行日 OHLCV 的已确认日期。`next_open` / `conservative` 使用执行日开盘价附近撮合，`close` 使用执行日收盘价撮合，持仓按执行日收盘价估值。当前账单已接入 100 股整手、现金约束、佣金、卖出印花税、滑点、涨跌停 / 停牌检查和最大成交参与率；未成交 / 部分成交原因的结构化落库仍需后续增强。

单独导出模拟交易账单 HTML：

```bash
./.venv/bin/python -m phase0.cli brief account-bill
./.venv/bin/python -m phase0.cli brief account-bill --date 2026-06-03
```

单独导出 07:30 盘前观察池：

```bash
./.venv/bin/python -m phase0.cli brief premarket
```

观察池会显示交易动作、权重变化、观察理由、成交价口径和执行风险提示。`brief premarket` 不负责更新 A 股本地历史库，日常使用优先跑 `brief daily`。

完整重建离线历史库：

```bash
./.venv/bin/python -m phase0.cli import-history --config config.yaml
```

只重建指数元数据和指数日线表：

```bash
./.venv/bin/python -m phase0.cli import-index-history --config config.yaml
```

构建本地因子股票池：

```bash
./.venv/bin/python -m phase0.cli build-universe --config config.yaml
```

增量更新本地历史库：

```bash
./.venv/bin/python -m phase0.cli update-history --config config.yaml
```

只检查本地历史库新鲜度：

```bash
./.venv/bin/python -m phase0.cli update-history --config config.yaml --check-only
```

更新季度财务因子：

```bash
./.venv/bin/python -m phase0.cli update-financials --config config.yaml
```

更新 US market 跨市场历史库：

```bash
./.venv/bin/python -m phase0.cli update-us-market-history --config config.yaml
```

只检查 US market 跨市场历史库覆盖率：

```bash
./.venv/bin/python -m phase0.cli update-us-market-history --config config.yaml --check-only
```

港股历史库当前已启用但仍处于独立数据层验证阶段，不挂到主策略链路。可用以下命令检查覆盖率与新鲜度：

```bash
./.venv/bin/python -m phase0.cli update-hk-market-history --config config.yaml --check-only
```

安装开发期定时任务：

```bash
bash scripts/install_dev_cron.sh
```

该命令只向系统 cron 安装一个项目入口：

```text
* * * * * bash scripts/run_project_scheduler.sh
```

`scripts/run_project_scheduler.sh` 当前是 wrapper：加载 `.env`、预热维护状态库后调用 `phase0.cli maintain tick`。具体任务由维护编排器判断运行窗口、交易日历、重试状态和健康门禁，当前默认包含：

- 每周一 `03:30`：更新 A 股季度财务因子，日志写入 `logs/financial_factors_update.log`。
- 交易日 `07:20`：运行 `brief watchlist`，生成阶段试用观察池页面 `reports/watchlist_today/index.html`，并同步到 ECS 远端目录 `BRIEF_SYNC_REMOTE_DIR`，日志写入 `logs/daily_brief_pipeline.log`。
- 交易日 `16:20`：更新港股历史库，日志写入 `logs/hk_market_history_update.log`。
- 交易日 `16:30`：更新 A 股本地历史库，日志写入 `logs/manual_history_update.log`。
- 交易日 `17:10`：更新 US market 历史库，日志写入 `logs/us_market_history_update.log`。

调度器本身日志写入：

```text
logs/project_scheduler.log
```

后续新增定时任务时，应优先扩展 `phase0/maintenance_orchestrator.py` 的任务 registry，保持系统 cron 里只有一个项目入口。

## 策略开发

当前策略候选通过 `phase0/strategies/` 注册：

- `legacy_momentum`
- `legacy_momentum_low_turnover_v1`
- `ma_kline_baseline_v1`
- `residual_momentum_reversal_v1`
- `residual_momentum_reversal_v2`
- `quality_growth_price_v1`
- `low_vol_low_turnover_quality_v1`
- `quality_low_turnover_monthly_v1`
- `multifactor_volume_price_filter_v1`
- `core_selection_quality_momentum_v1`
- `theme_exposure_momentum_v1`
- `sleeve_composite_v1`

`strategy-admission` 默认使用 `config.yaml` 中的 `phase0.walk_forward.admission.default_strategy_set` 和
`phase0.walk_forward.admission.strategy_sets` 控制本轮候选集合；临时缩小范围优先用 CLI `--strategies` 覆盖，
避免把临时实验状态写回配置。若长期不希望某个策略参与默认准入，可以在 `strategy_sets` 中注释对应策略行；
该变更是持久设计变更，不会自动恢复。`phase0.walk_forward.strategy_v2.compare_strategies` 仅保留为向后兼容入口。

当前默认准入集合 `baseline_admission_all_v1` 已包含上述 12 个候选。main 上已落盘的全候选 admission 仍需重跑以纳入 `sleeve_composite_v1`；`sleeve_composite_v1` 当前仅有 scoped admission 证据，结论为 `reject`，保持 research-only，不进入 paper review、模拟账户、日报或 watchlist。

策略变更要求：

- 每次修改策略逻辑或参数，必须记录理由、参考信息和验证结果。
- 不以单次高收益作为晋级依据，必须看 `annualized_return_mean`, `sharpe_mean`, `max_drawdown_mean`, `win_rate_mean`, `oos_return_decay_ratio`。
- 对 fold 数过少或 symbol 覆盖过窄的候选，要谨慎解释，不应直接晋级。
- 每次 compare / strategy-admission 代码验证通过后，必须生成带日期、运行背景、命令口径、验证结果、候选结论和下一步动作的策略治理报告。

策略变更日志：

```text
reports/phase0_strategy_change_log.md
```

## Agent 与 MCP

Agent 只做研究辅助与代码审查辅助，不进入主信号链路。

`Harness`、Codex MCP、Agents SDK、DeepSeek MCP 和外部 agent 工作流，只是开发、验证、复核与文档同步工具；它们的可执行性需要随当前仓库状态复核，不应被视作策略准入结果或门禁替代。

Codex 侧 Claude provider 配置放在 `.codex/`，不写入 `.claude/`，避免影响其他以 Claude 为主控模型的 agent 工具。

`Claude_Analyst_agent` 用于量化研究分析、风险提示和样本外稳健性评估：

```bash
bash .codex/run_claude_analyst_agent.sh --dry-run
bash .codex/run_claude_analyst_agent.sh
```

旧命令仍可用，等同于调用 `Claude_Analyst_agent`：

```bash
bash .codex/run_claude_agent.sh
```

`Claude_Code_Reviewer_agent` 用于代码质量审查：

```bash
bash .codex/run_claude_code_reviewer_agent.sh --dry-run
bash .codex/run_claude_code_reviewer_agent.sh
```

配置说明：

```text
.codex/CLAUDE_AGENT_WORKFLOW.md
```

项目内还提供 DeepSeek MCP 辅助工具，用于报告总结、第二意见和策略审查：

```text
refdocs/AGENT_AND_LOCAL_LLM_WORKFLOW.md
scripts/deepseek_agent_mcp.py
```

外部 OpenClaw agent 会话命名约定使用 `provider-role`，例如：

- `cloe-bridge`
- `cloe-research`
- `cloe-risk`
- `cloe-premarket`

Cloe 可作为外部 agent / 调度入口，但只用于研究摘要、消息通道和跨工具编排。当前技术底座是 OpenClaw Gateway：

```text
refdocs/AGENT_AND_LOCAL_LLM_WORKFLOW.md
```

当前 Codex 内推荐通过 `acpx` 调用 Cloe，固定使用 `cloe-bridge` 会话：

```bash
acpx openclaw sessions ensure --name cloe-bridge
acpx openclaw -s cloe-bridge "请审查当前 Phase 0 报告并列出主要风险。"
```

项目封装脚本会自动先确认会话再派发任务：

```bash
scripts/cloe_agent.sh "请检查当前开发计划和周任务清单是否一致。"
scripts/cloe_research_agent.sh "请基于 reports/phase0_effectiveness_report.md 生成研究摘要与风险点。"
scripts/cloe_risk_agent.sh "请从最新回测与执行报告提炼风险告警，按高/中/低分级。"
scripts/cloe_premarket_agent.sh "请基于 phase0_premarket_watchlist.csv 生成盘前要点和情景提示。"
```

MCP 与外部 agent 不得绕过 effectiveness gate、`qfq_asof`、PIT、过拟合诊断、`strategy-admission`、`execution-gate` 或人工 review，不得直接生成交易指令。

## 计划文档

- 主计划：`docs/DEVELOPMENT_PLAN.md`
- 任务索引：`docs/tasks/README.md`
- 架构说明：`docs/PROJECT_ARCHITECTURE_OVERVIEW.md`
- 策略开发标准：`docs/STRATEGY_DEVELOPMENT_GUIDELINES.md`
- 当前统一周执行附件：`docs/tasks/WEEKLY_EXECUTION_CHECKLIST.md`
- 策略候选整理：`docs/tasks/strategy/PHASE0_CANDIDATE_STRATEGIES.md`
- 候选策略解释索引：`docs/strategy_explanations/INDEX.md`
- 策略开发检查清单：`docs/STRATEGY_DEV_CHECKLIST.md`
- FRED 接入任务单：`docs/tasks/data-sources/FRED_IMPLEMENTATION_TASKS.md`
- Tiingo 接入任务单：`docs/tasks/data-sources/TIINGO_IMPLEMENTATION_TASKS.md`
- 有效量化策略研发任务清单：`docs/tasks/strategy/EFFECTIVE_QUANT_STRATEGY_RESEARCH_TASKS.md`
- 数据治理与维护编排器任务单：`docs/tasks/ops/DATA_GOVERNANCE_ORCHESTRATOR_TASKS.md`
- 远期展望：`refdocs/OUTLOOK/`

## 输出文件

- `reports/phase0_data_source_report.md`
- `reports/phase0_walk_forward_report.md`
- `reports/phase0_walk_forward_folds.csv`
- `reports/phase0_walk_forward_candidates.csv`
- `reports/phase0_walk_forward_universe_audit.csv`
- `reports/phase0_cost_sensitivity_report.md`
- `reports/phase0_cost_sensitivity.csv`
- `reports/phase0_effectiveness_report.md`
- `reports/phase0_strategy_change_log.md`
- `reports/strategy_admission*/strategy_admission_report.md`
- `reports/strategy_governance/<date>/strategy_governance_report_*.md`
- `reports/database_health/<date-or-scope>/database_health_report.md`
- `data/universe/local_factor_universe.csv`
- `data/universe/a_share_snapshot.csv`
- `data/universe/local_factor_universe_report.md`

## 重要约束

- 本工具仅供个人研究和自用决策辅助，不对外提供投资建议或商业服务。
- 所有输出属于观察池、风险暴露、信号等级、情景推演和策略验证结果，不构成投资建议。
- 所有策略参数变更必须记录理由、参考信息和验证结果。
- 当前无 selected candidate；任何进入 paper review、模拟账户正式链路或日报主线的候选，必须先通过严格 `qfq_asof`、PIT 股票池、成本后、过拟合、行业集中、因子诊断和 `strategy-admission` 门禁。
- 本地 fallback 不会静默使用过期快照：若本地最新交易日超过配置允许滞后，当前股票池 fallback 返回空并告警。
- 财务因子历史回测必须使用公告日 point-in-time 口径，避免未来函数。
- `yfinance` 和 `AkShare` 仅作为开发/研究辅助或 fallback，长期正式主源按 Tushare / Tiingo / FRED 分层推进。
- Claude / DeepSeek 等 LLM agent 仅做报告阅读、研究摘要、风险提示和第二意见，不直接生成交易信号，不修改策略参数，不跳过 gate，不把工作流执行结果解释为策略准入通过。
