# stok-mapping

A 股本土因子为主、跨市场风险/情绪 overlay 为辅的量化研究与盘前研判工具。

当前阶段重点是 Phase 0/1：验证数据源、构建离线 fallback 数据库、扩展股票池、做 walk-forward 回测，并为每天 `07:30` 的盘前研判日报做数据底座。

## 当前状态

- 已接入 `yfinance` / `akshare` 数据源连通性检查和数据质量审计。
- 已实现 Phase 0 walk-forward 回测框架和候选策略对比输出。
- 已创建本地离线历史库 `data/manual_history/a_share_history.sqlite`，用于在线抓取失败时的回测与股票池 fallback。
- 已导入 A 股前复权/不复权日线、股票列表、交易日历、退市清单、指数元数据和指数日线。
- 已增加开发期每日增量更新任务，维护 `a_share_history.sqlite` 最近交易日滞后不超过 1 天。
- 已接入季度财务因子表，覆盖 ROE、营收/利润增速、现金流质量和资产负债率。
- 已增加 AkShare 请求节流/重试机制，降低反爬和频繁请求导致的失败率。
- 已将运行时间线调整为：`16:00` A 股收盘数据采集，`06:00` 美股收盘数据采集，`07:30` 盘前研报邮件投递。

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

当前导入结果：

- `market_daily_bars`: qfq `10,462,485` 行 / `5,760` 只，bfq `10,462,385` 行 / `5,748` 只，日期 `2016-05-03` 至 `2026-05-28`。
- `market_stocks`: `5,524` 行。
- `market_financial_factors`: 季度财务因子表，通过 `update-financials` 更新。
- `trading_calendar`: `13,162` 行，覆盖 `1990-12-19` 至 `2026-12-31`。
- `delisted_stocks`: `324` 行。
- `market_indices`: `997` 行。
- `market_index_bars`: `1,876,918` 行 / `995` 个指数，日期 `2016-05-03` 至 `2026-05-28`。
- 关键指数 `SH.000001` 已验证可读，`2016-05-03` 至 `2026-05-28` 共 `2,445` 行。

## 常用命令

本项目必须能够独立运行。可以复用或迁移其他项目中的可用代码与依赖选型，但运行时不应依赖 `stok-quant` 仓库、其源码路径或其虚拟环境。

建议先在本项目目录下安装独立环境与依赖：

```bash
uv sync
```

之后使用本项目自己的虚拟环境执行命令：

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

更新季度财务因子：

```bash
./.venv/bin/python -m phase0.cli update-financials --config config.yaml
```

只检查本地历史库新鲜度：

```bash
./.venv/bin/python -m phase0.cli update-history --config config.yaml --check-only
```

开发期每日定时更新任务：

```bash
bash scripts/install_dev_cron.sh
```

该 cron 任务默认安装两条开发期任务：

- 交易日 `16:30` 运行 `scripts/update_manual_history_daily.sh`，日志写入 `logs/manual_history_update.log`。
- 每周一 `03:30` 运行 `scripts/update_financial_factors_weekly.sh`，日志写入 `logs/financial_factors_update.log`。

日线增量更新会先检查库中最新交易日、覆盖率和交易日历；若已满足 `max_staleness_days=1` 与 `min_latest_coverage=0.80`，不会重复抓取。若在配置的 `min_run_time=16:00` 之前运行，不会把盘中实时快照写成日线收盘数据。

`update-history` 还会刷新 `market_stocks` 中的横截面字段：`market_cap`, `pe_ratio`, `pb_ratio`, `turnover_rate`。该元数据刷新与日线写入分离：即使早于 `16:00`，也允许用全市场快照回填横截面字段；只有日线收盘写入受 `min_run_time` 保护。当前主源为 AkShare 东方财富快照，断连时会尝试新浪原始快照备用源。

`update-financials` 使用东方财富数据中心季度接口写入 `market_financial_factors`。当前字段包括 `roe`, `revenue_growth`, `profit_growth`, `operating_cash_flow_to_net_profit`, `debt_to_asset`。这些字段会并入本地股票池 snapshot，供后续质量/价值因子回测使用；当前不会改变 `universe_score`，避免未验证基本面参数直接影响选股结果。现金流质量暂定义为经营活动现金流净额 / 归母净利润；负债率优先使用东方财富 `DEBT_ASSET_RATIO`，缺失时用总负债 / 总资产计算。

财务因子的当前用途是“最新横截面基本面字段”。用于历史回测前必须进一步按公告日做 point-in-time 校验，因为财务接口可能返回后续更正公告日期，不能直接假设报告期末即可使用。

财务因子定时任务放在每周一 `03:30`，理由是财报数据低频、周末公告可被覆盖，同时避开 `16:30` 日线增量、`06:00` 美股收盘采集和 `07:30` 盘前研报生成。脚本使用 `nice`/`ionice` 降低资源优先级，用锁文件避免重复运行，并设置 `120m` 超时保护，避免异常卡住影响后续盘前任务。

## Agent 协同

Codex 侧 Claude provider 配置放在 `.codex/`，不写入 `.claude/`，避免影响其他以 Claude 为主控模型的 agent 工具。

只生成 prompt 预览：

```bash
bash .codex/run_claude_agent.sh --dry-run
```

调用 Claude API 生成研究摘要：

```bash
bash .codex/run_claude_agent.sh
```

配置说明见：

```text
.codex/CLAUDE_AGENT_WORKFLOW.md
```

## 计划文档

- 主计划：`DEVELOPMENT_PLAN.md`
- 当前统一周执行附件：`refdocs/todo/WEEKLY_EXECUTION_CHECKLIST.md`
- 策略候选整理：`refdocs/todo/PHASE0_CANDIDATE_STRATEGIES.md`
- FRED 接入任务单：`refdocs/todo/FRED_IMPLEMENTATION_TASKS.md`
- Tiingo 接入任务单：`refdocs/todo/TIINGO_IMPLEMENTATION_TASKS.md`

## 输出文件

- `reports/phase0_data_source_report.md`
- `reports/phase0_walk_forward_report.md`
- `reports/phase0_walk_forward_folds.csv`
- `reports/phase0_walk_forward_candidates.csv`
- `reports/phase0_effectiveness_report.md`
- `data/universe/local_factor_universe.csv`
- `data/universe/local_factor_universe_report.md`

## 重要约束

- 本工具仅供个人研究和自用决策辅助，不对外提供投资建议或商业服务。
- 所有策略参数变更必须记录理由、参考信息和验证结果。
- 本地 fallback 不会静默使用过期快照：若本地最新交易日超过配置允许滞后，当前股票池 fallback 返回空并告警。
- `yfinance` 和 `akshare` 定位为开发/研究数据源，后续生产化需保留 Tushare Pro / Wind / 聚宽 / Polygon 等适配层。
- Claude agent 仅做报告阅读、研究摘要和风险提示；不得直接生成交易指令、擅自修改策略参数或跳过 effectiveness gate。
