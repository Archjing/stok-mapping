# stok-mapping

A 股本土因子为主、跨市场风险/情绪 overlay 为辅的量化研究与盘前研判工具。

本项目不是自动交易系统，也不是通用量化平台。当前目标是形成一条可验证、可复盘、可解释的研究链路：

```text
数据源同步 -> 本地历史库 -> 股票池/特征 -> 候选策略 -> walk-forward/gate -> 报告/观察池
```

核心输出是观察池、风险暴露说明、信号等级、盘前情景推演和候选策略对比结果，不输出自动下单指令。

## 当前状态

- Phase 0 / Phase 0.1 基础设施已基本可用。
- 已创建本地离线历史库 `data/manual_history/a_share_history.sqlite`，用于回测、股票池 fallback 和数据新鲜度保护。
- 已导入 A 股前复权/不复权日线、股票列表、交易日历、退市清单、指数元数据和指数日线。
- 已接入季度财务因子表，覆盖 `roe`, `revenue_growth`, `profit_growth`, `operating_cash_flow_to_net_profit`, `debt_to_asset`。
- 已实现股票池构建、walk-forward 回测、候选策略 compare、effectiveness gate 和报告输出。
- 策略层已拆分为 `phase0/strategies/` 注册表结构，便于新增候选策略。
- 已增加开发期定时任务：交易日 `16:30` 日线增量更新，每周一 `03:30` 财务因子更新。
- 当前主阻塞点不是数据管线，而是主策略仍未稳定通过 effectiveness gate。

最新报告以 `reports/phase0_effectiveness_report.md` 为准。当前最新一次结果显示 selected candidate 为 `quality_growth_price_v1`，但总体 verdict 仍为 `FAIL`，主要失败点是 `win_rate_mean` 未达标。该候选当前样本支持较弱，不能直接视为主策略已晋级。

## 架构层次

当前系统可以理解为 6 层：

- 数据源接入层：`Tushare`, `AkShare`, `yfinance`，后续计划接入 `FRED` 和 `Tiingo`。
- 数据管理层：本地 SQLite 历史库、增量更新、覆盖率检查、新鲜度保护。
- 股票池与特征层：A 股股票池、流动性/市值/行业约束、技术特征、财务因子。
- 策略与信号层：本土主因子策略、跨市场 overlay、解释层。
- 策略评估与治理层：walk-forward、compare mode、effectiveness gate、strategy change log。
- 交付与交互层：Markdown/CSV 报告、Agent 辅助摘要，后续可扩展 Web/PWA/Tauri。

详细架构说明见：

```text
refdocs/PROJECT_ARCHITECTURE_OVERVIEW.md
```

## 数据源策略

当前确认的数据源层级：

- 国内股票主源：`Tushare`
- 国内 fallback：`AkShare` / 新浪快照 / 本地 SQLite 历史库
- 美股个股与 ETF 计划主源：`Tiingo`
- 宏观 / 利率 / VIX 计划主源：`FRED`
- `yfinance`：保留为 fallback，不再作为长期正式主源

当前 `Tiingo` 和 `FRED` 仍是任务单阶段，尚未正式接入 `phase0/data_sources.py`：

```text
refdocs/todo/TIINGO_IMPLEMENTATION_TASKS.md
refdocs/todo/FRED_IMPLEMENTATION_TASKS.md
```

## 本地数据

默认数据库：

```text
data/manual_history/a_share_history.sqlite
```

数据库不进入 Git。目录说明见：

```text
data/manual_history/README.md
```

`a_share_history.sqlite` 的时效保护只限制“当前股票池 / 当日研判”场景：如果本地最新交易日超过配置允许滞后，系统不会用旧快照生成当前股票池，而是返回空并告警。该限制不等于禁用本地库，历史回测、指定历史区间分析和历史日线 fallback 仍可继续读取。

当前主要表包括：

- `market_daily_bars`: A 股日线，含前复权/不复权数据。
- `market_stocks`: 股票元数据与横截面字段。
- `market_financial_factors`: 季度财务因子表。
- `trading_calendar`: 交易日历。
- `delisted_stocks`: 退市股票列表。
- `market_indices`: 指数元数据。
- `market_index_bars`: 指数日线。
- `market_data_source_runs`: 数据源增量更新审计记录。

## 常用命令

本项目应独立运行。可以复用或迁移其他项目中的经验，但运行时不应依赖兄弟仓库源码路径或外部项目专属虚拟环境。

安装本项目依赖：

```bash
uv sync
```

运行 Phase 0：

```bash
./.venv/bin/python -m phase0.cli run --config config.yaml
```

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

安装开发期定时任务：

```bash
bash scripts/install_dev_cron.sh
```

该 cron 任务默认安装两条开发期任务：

- 交易日 `16:30` 运行 `scripts/update_manual_history_daily.sh`，日志写入 `logs/manual_history_update.log`。
- 每周一 `03:30` 运行 `scripts/update_financial_factors_weekly.sh`，日志写入 `logs/financial_factors_update.log`。

## 策略开发

当前策略候选通过 `phase0/strategies/` 注册：

- `legacy_momentum`
- `ma_kline_baseline_v1`
- `residual_momentum_reversal_v1`
- `residual_momentum_reversal_v2`
- `quality_growth_price_v1`
- `multifactor_volume_price_filter_v1`

`config.yaml` 中的 `walk_forward.strategy_v2.compare_strategies` 控制参与 compare 的候选。

策略变更要求：

- 每次修改策略逻辑或参数，必须记录理由、参考信息和验证结果。
- 不以单次高收益作为晋级依据，必须看 `annualized_return_mean`, `sharpe_mean`, `max_drawdown_mean`, `win_rate_mean`, `oos_return_decay_ratio`。
- 对 fold 数过少或 symbol 覆盖过窄的候选，要谨慎解释，不应直接晋级。

策略变更日志：

```text
reports/phase0_strategy_change_log.md
```

## Agent 与 MCP

Agent 只做研究辅助，不进入主信号链路。

Codex 侧 Claude provider 配置放在 `.codex/`，不写入 `.claude/`，避免影响其他以 Claude 为主控模型的 agent 工具。

只生成 prompt 预览：

```bash
bash .codex/run_claude_agent.sh --dry-run
```

调用 Claude API 生成研究摘要：

```bash
bash .codex/run_claude_agent.sh
```

配置说明：

```text
.codex/CLAUDE_AGENT_WORKFLOW.md
```

项目内还提供 DeepSeek MCP 辅助工具，用于报告总结、第二意见和策略审查：

```text
refdocs/DEEPSEEK_AGENT_MCP.md
scripts/deepseek_agent_mcp.py
```

MCP 与外部 agent 不得绕过 effectiveness gate，不得直接生成交易指令。

## 计划文档

- 主计划：`DEVELOPMENT_PLAN.md`
- 架构说明：`refdocs/PROJECT_ARCHITECTURE_OVERVIEW.md`
- 当前统一周执行附件：`refdocs/todo/WEEKLY_EXECUTION_CHECKLIST.md`
- 策略候选整理：`refdocs/todo/PHASE0_CANDIDATE_STRATEGIES.md`
- 策略开发检查清单：`refdocs/todo/STRATEGY_DEV_CHECKLIST.md`
- FRED 接入任务单：`refdocs/todo/FRED_IMPLEMENTATION_TASKS.md`
- Tiingo 接入任务单：`refdocs/todo/TIINGO_IMPLEMENTATION_TASKS.md`
- 远期展望：`refdocs/OUTLOOK/`

## 输出文件

- `reports/phase0_data_source_report.md`
- `reports/phase0_walk_forward_report.md`
- `reports/phase0_walk_forward_folds.csv`
- `reports/phase0_walk_forward_candidates.csv`
- `reports/phase0_effectiveness_report.md`
- `reports/phase0_strategy_change_log.md`
- `data/universe/local_factor_universe.csv`
- `data/universe/a_share_snapshot.csv`
- `data/universe/local_factor_universe_report.md`

## 重要约束

- 本工具仅供个人研究和自用决策辅助，不对外提供投资建议或商业服务。
- 所有输出属于观察池、风险暴露、信号等级、情景推演和策略验证结果，不构成投资建议。
- 所有策略参数变更必须记录理由、参考信息和验证结果。
- 本地 fallback 不会静默使用过期快照：若本地最新交易日超过配置允许滞后，当前股票池 fallback 返回空并告警。
- 财务因子进入正式历史回测前，必须完成公告日 point-in-time 校验，避免未来函数。
- `yfinance` 和 `AkShare` 仅作为开发/研究辅助或 fallback，长期正式主源按 Tushare / Tiingo / FRED 分层推进。
- Claude / DeepSeek 等 LLM agent 仅做报告阅读、研究摘要、风险提示和第二意见，不直接生成交易信号，不修改策略参数，不跳过 gate。
