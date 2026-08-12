# Quant CLI 使用说明（当前版本）

适用范围：`python -m quant.cli` 当前已实现命令。

默认配置文件：`config.yaml`。

说明口径：以 [`quant/cli.py`](../quant/cli.py) 实际参数为准。

项目根目录快捷入口：`./runit`。它等价于 `./.venv/bin/python -m quant.cli`。

---

## 1. 快速开始

安装依赖（项目根目录）：

```bash
uv sync
```

查看总帮助：

```bash
./.venv/bin/python -m quant.cli -h
./runit -h
```

最常用的三个命令：

```bash
# 日常简报 pipeline：先更新 A 股历史库，再导出当前主策略观察池
./.venv/bin/python -m quant.cli daily-brief --config config.yaml

# 全量 Quant 主流程
./.venv/bin/python -m quant.cli run --config config.yaml

# 仅更新 A 股本地历史库，用于单独排查数据新鲜度
./.venv/bin/python -m quant.cli update-history --config config.yaml
```

---

## 2. 命令总览

`quant.cli` 当前支持以下子命令：

- `run`
- `cost-sensitivity`
- `bill`
- `market-regime`
- `oos-report`
- `strategy-admission`
- `overfit-diagnostic`
- `financial-pti`
- `factor-effectiveness`
- `intraday-account`
- `db-health`
- `ai-corpus`
- `daily-brief`
- `premarket`
- `execution-gate`
- `build-universe`
- `import-history`
- `import-index-history`
- `update-history`
- `update-us-market-history`
- `update-hk-market-history`
- `update-financials`
- `site`

---

## 3. 命令详解

### 3.1 主流程与策略评估

`run`：执行 Quant 主流程（数据源连通性、质量审计、walk-forward、effectiveness report、账单导出）。

```bash
./.venv/bin/python -m quant.cli run --config config.yaml
```

`cost-sensitivity`：成本敏感性单独运行，不与 `run` 自动绑定。

```bash
# 手动传场景
./.venv/bin/python -m quant.cli cost-sensitivity --config config.yaml \
  --scenario base:0.001 --scenario stress:0.003

# 使用 config.yaml 的 cost_sensitivity.scenarios
./.venv/bin/python -m quant.cli cost-sensitivity --config config.yaml --use-config-scenarios
```

`strategy-admission`：运行统一策略准入报告。默认读取 `config.yaml` 中的
`walk_forward.admission.default_strategy_set` 和 `walk_forward.admission.strategy_sets`；
临时缩小候选范围时优先使用 CLI `--strategies`，不要把一次性实验状态写回配置。
如果确实要长期移除某个候选，可以在 `strategy_sets` 中注释对应策略行；该变更不会自动恢复，
需要手动取消注释或用 `--strategy-set` / `--strategies` 临时覆盖。

```bash
# 使用默认 strategy set
./.venv/bin/python -m quant.cli strategy-admission --config config.yaml \
  --presets baseline_2y_1y_5fold --trace-run

# 诊断耗时：生成 logs/perf/walk_forward_profile_<preset>_<run_id>.json/.csv
./.venv/bin/python -m quant.cli strategy-admission --config config.yaml \
  --presets baseline_2y_1y_5fold --profile

# 使用配置中的专项 strategy set
./.venv/bin/python -m quant.cli strategy-admission --config config.yaml \
  --presets baseline_2y_1y_5fold quality_3y_1y_4fold \
  --strategy-set quality_research_v1 --trace-run

# 临时只跑少数策略；下次不带 --strategies 会回到默认 strategy set
./.venv/bin/python -m quant.cli strategy-admission --config config.yaml \
  --presets baseline_2y_1y_5fold \
  --strategies low_vol_low_turnover_quality_v1 quality_low_turnover_monthly_v1 \
  --trace-run
```

Walk-forward runtime cache 默认只缓存安全边界：同一数据源签名下，admission 多 preset 可复用 symbol 级行情 LRU；
同一训练窗结束日的 point-in-time universe 快照；同一股票池、同一日期窗口、同一 as-of 口径和同一数据源签名下的 fold panel；
同一基准指数区间指标；以及“同一策略 + 同一配置 + 同一 fold 输入”的 prepared panel。prepared panel 不会跨不同策略共享。
profile JSON 会记录 cache manifest，包括数据源 mtime/size、复权口径、cache 开关和命中统计。需要排查缓存影响时可加 `--no-wf-cache`；
启用磁盘缓存后需要重建时可加 `--refresh-wf-cache`。

### 3.2 5 分钟单 ETF 模拟账户

`intraday-account`：按配置重放“外部市场信号 → 下一 A 股交易日 → 单只 ETF 入场 →
T+1 日内退出”的 5 分钟级账户。默认只读，不写模拟账户数据库。

`cross_market_semiconductor_timing_etf_v1` 是可复用的策略 ID。每个账户通过
`strategy_params.target_symbol` 独立指定交易标的，因此可以创建多个账户来分别模拟不同
ETF；账户 ID、现金、持仓、成交、净值和 SQLite 状态彼此隔离。现有账户仍配置为
`SH.512480`。

允许的标的仅限：`SH.512480`、`SH.512760`、`SH.516920`、`SH.516640`、
`SZ.159995`、`SZ.159813`、`SZ.159801`、`SH.588200`。策略会拒绝清单外的代码。
新增账户前必须分别确认该 ETF 的日线和 5 分钟线覆盖，并完成独立回测、walk-forward 与
admission；512480 的历史结果不能外推到其它 ETF。缺失关键分钟数据时命令会以退出码
`2` 结束，且 `--recover-missing` 不会以不完整重放结果写入账户。

以下是账户配置模板，仅供复制后按实际资金、账户名称和已验证标的填写；它不会自动创建或
启用新账户：

```yaml
- account_id: "semiconductor_512760"
  name: "半导体ETF美股情绪映射择时_512760_v1"
  enabled: false
  initial_cash: 100000
  strategy_id: "cross_market_semiconductor_timing_etf_v1"
  strategy_params:
    target_symbol: "SH.512760"
  execution_model: "single_etf_intraday"
  intraday_data_path: "data/etf_history.sqlite"
  ledger_path: "data/simulated_trading/phase0_daily_account_ledger_512760.csv"
  database_path: "data/simulated_trading/simulated_accounts.sqlite"
  price_tick: 0.001
  lot_size: 100
  commission: 0.00025
  min_commission: 5.0
  slippage: 0.0001
  stamp_duty_sell: 0.0
```

```bash
# 固定 as-of 的可复现 dry-run
./.venv/bin/python -m quant.cli intraday-account \
  --account-id semiconductor_timing \
  --as-of 2026-08-11 \
  --json

# 盘后以完整 5 分钟线核验当日实时结果；只有当日产物缺失或不完整时才补写
./.venv/bin/python -m quant.cli intraday-account \
  --account-id semiconductor_timing \
  --as-of 2026-08-11 \
  --recover-missing
```

执行口径：

- 强信号按交易日开盘价成交；弱信号使用限价单，未触及即撤单。
- T+1 使用 5 分钟 OHLC 完成 bar 做追踪止损；当前 bar 的 high 不能反向触发同一 bar 的 low。
- 跳空跌破止损线时按 bar 开盘价成交，不按不可获得的止损价成交。
- 未触发止损时要求存在配置的 `14:55` bar，并按该 bar 收盘价退出。
- 缺失关键 5 分钟数据时返回退出码 `2`，且 `--recover-missing` 拒绝用不完整重放结果恢复状态。
- 样本末日刚入场且未来 T+1 尚未发生时，状态为 `open_position_pending_exit`，不属于数据缺失。

盘后核验与恢复：

- 不带 `--recover-missing` 时，命令只重放和输出核验结果，不修改账户数据库。
- 带 `--recover-missing` 时，命令只处理 `--as-of` 指定交易日；当天资产、成交或订单产物缺失／不完整时，才补写该日专用账户表，不清空历史台账。
- 当天已有完整实时产物且与重放一致时，结果为 `verified`，不写库。
- 当天已有产物但与完整分钟线重放不一致时，结果为 `mismatch` 并以退出码 `2` 结束；命令不会静默覆盖实时账本，必须先审计差异。
- 恢复会按完整分钟线重新执行原有规则；弱信号限价单全天未触及时保持“收盘撤单”，不会事后按开盘价补造买入成交。
- 当天 ETF 日线尚未落库时，恢复会读取同日开盘快照和已采集的 5 分钟线，并把已完成的美国收盘信号映射到该 A 股会话；这只用于当日执行和台账恢复，不会伪造或回填 ETF 日线记录。

边界：该命令是盘后确定性重放、核验与缺失恢复工具，不是盘中实时行情订阅器、订单调度器或券商交易接口。实时链路应在开盘与盘中持续生成台账和订单；盘后重放仅在该链路中断、行情采集失败或当日产物缺失时用于恢复和复核。

### 3.3 AI 语料库命令

`ai-corpus`：抓取、入库、查询和导出本地 AI 语料库文档。当前用于政策法规、CCTV 新闻联播公开文稿、后续公告 / 央行报告 / 研报元数据等文本材料的可追溯归档；不直接生成交易信号，不直接接入主 ranker。

当前 provider 状态：

```bash
./runit ai-corpus registry --config config.yaml
```

当前输出含义：

- `gov_policy`：`implemented_mvp`，支持 gov.cn 政策库 fixture、live fetch、reference cache、source probe 和 pre-fetch audit gate。
- `cctv`：`implemented_mvp`，支持央视网新闻联播日期页、完整节目页和分段页 live fetch；fixture 仅用于离线回归测试。
- `cninfo`：`implemented_mvp`，支持 AkShare / 巨潮资讯公告列表抓取、fixture 回归、事件类型过滤、raw archive、SQLite upsert 和晚间调度任务；当前只承诺列表级事件线索，不抓公告 PDF / 全文。

默认本地 SQLite 库路径：

```text
data/ai_corpus/ai_corpus.sqlite
```

默认表名：

```text
ai_corpus_documents
```

注意：默认库只有在第一次不带 `--database-path` 执行 `ai-corpus fetch` 后才会创建。验收或实验命令若使用 `/tmp/...sqlite` 覆盖路径，不会生成默认库。

gov.cn 政策库示例：

```bash
# fixture-first 验收：创建默认 data/ai_corpus/ai_corpus.sqlite
./runit ai-corpus fetch --config config.yaml \
  --provider gov-policy \
  --org 国务院 \
  --ptype 科技 \
  --end-date '2025-08-26 17:00:00' \
  --fixture-dir tests/fixtures/ai_corpus/gov_policy \
  --limit 20

# live 抓取：不传 --fixture-dir 时访问 gov.cn；需要网络可用
./runit ai-corpus fetch --config config.yaml \
  --provider gov-policy \
  --org 国务院 \
  --ptype 科技 \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --limit 100

# 生产门禁：先写 source probe JSON，probe 失败时不执行 fetch
./runit ai-corpus fetch --config config.yaml \
  --provider gov-policy \
  --org 国务院 \
  --ptype 科技 \
  --keyword 人工智能 \
  --limit 20 \
  --min-rows 1 \
  --timeout 20 \
  --refresh-reference \
  --probe-before-fetch \
  --min-probe-content-chars 200 \
  --probe-output-json 'reports/phase0/ai_corpus/probes/gov_policy_probe_%Y%m%dT%H%M%S.json'
```

日期区间口径：

- `--start-date` / `--end-date` 是上游发布时间 `published_at` 过滤条件。
- gov.cn provider 如果两个日期都不传，就是不加发布时间过滤，只受 `--limit` 和上游返回顺序影响；这不适合作为可复现的治理任务。
- 只传 `--end-date` 时，表示抓取发布时间不晚于该日期的结果；只传 `--start-date` 时，表示抓取发布时间不早于该日期的结果。
- 创建默认库本身不会自动决定日期区间；日期区间完全由本次 `fetch` 命令参数决定。
- 每日调度器默认任务 `gov_policy_fetch` 会运行上述生产门禁路径：先执行 gov.cn source probe，报告写入 `reports/phase0/ai_corpus/probes/`，再抓取并 upsert 到默认 AI 语料库。
- gov.cn probe 报告包含 `audit.checks[]`，默认检查 reference topic、匹配主题、搜索行数、列表必需字段、发布时间字段、`ztflTree`、正文 HTML 和正文长度；任一 error 会让 `--probe-before-fetch` 阻断生产抓取。
- `gov_policy_fetch` 可通过环境变量覆盖：`GOV_POLICY_TIME`、`GOV_POLICY_ORG`、`GOV_POLICY_PTYPE`、`GOV_POLICY_KEYWORD`、`GOV_POLICY_LIMIT`、`GOV_POLICY_MIN_ROWS`、`GOV_POLICY_TIMEOUT`、`GOV_POLICY_DATABASE_PATH`、`GOV_POLICY_RAW_ARCHIVE_DIR`、`GOV_POLICY_REFERENCE_DIR`、`GOV_POLICY_PROBE_OUTPUT_JSON`、`GOV_POLICY_PROBE_MIN_ROWS`、`GOV_POLICY_PROBE_MIN_TOPICS`、`GOV_POLICY_PROBE_MIN_DEPARTMENTS`、`GOV_POLICY_PROBE_MIN_CONTENT_CHARS`。

CCTV 新闻联播 live 抓取示例：

```bash
# 抓指定日期；不传 --fixture-dir 时访问央视网公开页面
./runit ai-corpus fetch --config config.yaml \
  --provider cctv-news \
  --date 20260703 \
  --limit 100 \
  --min-rows 1

# 不传 --date 时默认抓当天，适合每日调度器使用
./runit ai-corpus fetch --config config.yaml \
  --provider cctv-news \
  --limit 100 \
  --min-rows 1

# 抓时间区间；按闭区间逐日访问 CCTV 日期页并合并入库
./runit ai-corpus fetch --config config.yaml \
  --provider cctv-news \
  --start-date 2026-07-03 \
  --end-date 2026-07-07 \
  --limit 100 \
  --min-rows 1

# 只抓完整节目，不抓分段节目
./runit ai-corpus fetch --config config.yaml \
  --provider cctv-news \
  --date 20260703 \
  --full-program-only
```

CCTV fixture 回归测试示例：

```bash
./runit ai-corpus fetch --config config.yaml \
  --provider cctv-news \
  --date 20260703 \
  --fixture-dir tests/fixtures/ai_corpus/cctv_news \
  --limit 20
```

CNInfo / 巨潮资讯公告列表示例：

```bash
# 生产调度推荐口径：抓取市场风险类公告，再按标题细分为异常波动 / 交易风险提示 / 严重异常波动
./runit ai-corpus fetch --config config.yaml \
  --provider cninfo \
  --event-type risk_events \
  --start-date 2026-07-02 \
  --end-date 2026-07-03 \
  --min-rows 0

# 单独抓取异常波动公告；不传 --fixture-dir 时通过 AkShare 访问巨潮资讯公告列表
./runit ai-corpus fetch --config config.yaml \
  --provider cninfo \
  --event-type abnormal_trading \
  --start-date 2026-07-02 \
  --end-date 2026-07-03 \
  --min-rows 1

# 抓取交易风险提示公告，并过滤可转债适当性、退市风险警示等非目标公告
./runit ai-corpus fetch --config config.yaml \
  --provider cninfo \
  --event-type trading_risk_warning \
  --start-date 2026-07-02 \
  --end-date 2026-07-03 \
  --min-rows 1

# 按股票代码限定范围；多个代码用逗号分隔
./runit ai-corpus fetch --config config.yaml \
  --provider cninfo \
  --event-type earnings_forecast \
  --symbols 300750,600519 \
  --start-date 2026-07-01 \
  --end-date 2026-07-10 \
  --min-rows 1
```

查询本地库：

```bash
# 表格输出
./runit ai-corpus query --config config.yaml --provider gov-policy --keyword 人工智能 --limit 20

# Markdown 输出
./runit ai-corpus query --config config.yaml --corpus-type cctv_news --format markdown --limit 20

# CSV 输出
./runit ai-corpus query --config config.yaml --provider gov-policy --keyword 人工智能 \
  --format csv --output-csv reports/runs/latest/ai_corpus_policy_query.csv
```

导出本地库已有记录：

```bash
./runit ai-corpus export --config config.yaml \
  --provider gov-policy \
  --keyword 人工智能 \
  --output-csv reports/runs/latest/ai_corpus_export.csv
```

常用参数：

- `--provider`：`gov-policy` / `npr` / `cctv-news` 等别名会映射到内部 provider。
- `--event-type`：事件型 provider 的事件过滤口径，当前主要用于 `cninfo`，如 `risk_events`、`abnormal_trading`、`trading_risk_warning`、`severe_abnormal_trading`、`earnings_forecast`。
- `--org`：政策发文机关，如 `国务院`、`工业和信息化部`。
- `--ptype`：政策主题，目前已支持 `科技`、`科技、教育` 的 MVP 映射。
- `--keyword`：关键词过滤。
- `--symbols`：股票代码过滤，当前主要用于 `cninfo`；多个代码用逗号分隔。
- `--date`：日期型 provider 的单日日期，当前主要用于 `cctv-news`，格式 `YYYYMMDD` 或可解析日期。
- `--min-rows`：抓取结果低于该行数时返回失败码；调度器用 `--min-rows 1` 避免“当天页面尚未发布但任务显示成功”。
- `--fields`：抓取后 CSV 输出字段列表，如 `pubtime,title,pcode,puborg,ptype,url`。
- `--fixture-dir`：离线 fixture 验证目录；不传时 `gov-policy` / `cctv-news` 会尝试访问公开 live 来源。
- `--database-path`：覆盖 SQLite 路径，适合验收或实验，不会写默认库。
- `--raw-archive-dir`：覆盖原始响应归档目录。
- `--no-content`：gov.cn 只抓列表，不抓正文页。
- `--full-program-only`：`cctv-news` 只抓新闻联播完整节目行，不抓分段节目。
- `--min-probe-rows` / `--min-probe-topics` / `--min-probe-departments` / `--min-probe-content-chars`：gov.cn probe audit 阈值，生产调度器默认分别为 `1`、`1`、`0`、`200`。
- `--no-require-topic-tree` / `--no-require-content-html`：降低 gov.cn probe audit 严格度；只建议临时排障使用，不建议放入默认调度。

默认调度补充：

- `cninfo_risk_events` 每天 `20:20` 运行，默认等同于 `ai-corpus fetch --provider cninfo --event-type risk_events --limit 200 --min-rows 0`。
- `CNINFO_RISK_EVENTS_TIME`、`CNINFO_RISK_EVENTS_EVENT_TYPE`、`CNINFO_RISK_EVENTS_LIMIT`、`CNINFO_RISK_EVENTS_MIN_ROWS`、`CNINFO_RISK_EVENTS_DATABASE_PATH`、`CNINFO_RISK_EVENTS_RAW_ARCHIVE_DIR` 可覆盖默认调度参数。
- `CNINFO_RISK_EVENTS_MIN_ROWS` 默认是 `0`，因为某天没有异常波动或交易风险提示公告是正常结果；网络、解析或入库异常仍会让任务失败。

边界要求：

- AI 语料库只作为研究情报、政策解释、公告风险提示和后续 RAG-ready 资料层。
- 不允许把政策、新闻、公告或 LLM 摘要直接当作策略信号接入主 ranker。
- 进入回测或策略解释前，必须先通过 `as_of_time`、来源、去重键、正文 hash 和 raw path 审计。

### 3.3 导出类命令

`daily-brief`：日常简报 pipeline。默认先执行 A 股历史库增量更新，再导出当前有效主策略的 07:30 盘前观察池；如果历史库插入了新行，会自动刷新低换手策略 panel cache。

```bash
./.venv/bin/python -m quant.cli daily-brief --config config.yaml
./.venv/bin/python -m quant.cli daily-brief --config config.yaml --skip-update
./.venv/bin/python -m quant.cli daily-brief --config config.yaml --check-only
./.venv/bin/python -m quant.cli daily-brief --config config.yaml --refresh-cache
```

常用口径：

- `--skip-update`：不更新 A 股库，只基于当前本地库重新生成简报。
- `--check-only`：只检查 A 股库新鲜度，不生成简报。
- `--refresh-cache`：即使没有新数据，也强制重建策略 panel cache。

`daily-brief` 输出按简报日期归档，日期取自简报 `盘前检查时间` 的日期部分，不使用系统运行日期：

```text
reports/<brief_date>/phase0_premarket_watchlist_<brief_date>.csv
reports/<brief_date>/phase0_premarket_report_<brief_date>.html
```

连续模拟仓位流水：

```text
data/simulated_trading/phase0_daily_brief_ledger.csv
```

当前阶段，`brief watchlist` 会用当前模拟账户的上一确认持仓与本期策略目标权重生成计划层观察池。为压缩宽表，表格显示短表头：`动作`、`当前权重`、`目标权重`、`权重变化`、`持仓天数` 是模拟账户口径；`信号动作`、`信号持有天数` 是策略研究信号口径。模拟账户可通过 `accounts.simulated[].simulation_start_date` 设置生命周期起点，避免新账户继承更早历史 watchlist。

多模拟账户日常生成：

```bash
./runit brief watchlist --config config.yaml --all-accounts
```

该命令会为 `accounts.simulated` 中所有 `enabled: true` 的模拟账户生成各自的 watchlist、模拟账单和账户级 latest bundle。不同账户可以配置不同 `strategy_id`，控制台和后续发布链路按账户读取各自的产物，不复用默认账户页面。

盘后确认当日模拟账户账单：

```bash
./runit brief confirm-account-bills --config config.yaml --all-accounts
./runit brief confirm-account-bills --config config.yaml --all-accounts --date 2026-07-02
```

`brief confirm-account-bills` 不重新生成观察池；它读取当日已归档的 watchlist CSV，按每个 enabled 账户自己的策略、建仓日和执行价口径重算账户账本。若当天执行价 OHLCV 已入库，则刷新账户级 latest account-bill、默认账户旧版 `/account-bill/` 镜像，并发布 `/quant/` 静态控制台。`brief account-bill` 只负责从 SQLite 导出账单 HTML，不负责重算账本。

`bill`：导出低换手账单与资产曲线文件。

```bash
./.venv/bin/python -m quant.cli bill --config config.yaml
./.venv/bin/python -m quant.cli bill --config config.yaml --refresh-cache
./.venv/bin/python -m quant.cli bill --config config.yaml --no-panel-cache
```

`oos-report`：导出连续 OOS 报告，支持执行参数 profile 和临时覆盖。

```bash
./.venv/bin/python -m quant.cli oos-report --config config.yaml --profile research
./.venv/bin/python -m quant.cli oos-report --config config.yaml --profile live \
  --slippage 0.003 --price-mode conservative --max-participation-rate 0.03
```

`execution-gate`：账户级执行有效性门控报告。

```bash
./.venv/bin/python -m quant.cli execution-gate --config config.yaml --profile live
./.venv/bin/python -m quant.cli execution-gate --config config.yaml --profile research \
  --output-dir reports/live_execution_backtest/research_profile
```

默认 `compare` / `strategy-admission` 会启用 `walk_forward.strategy_v2.account_execution` 诊断，并按 `quant.execution` 中的确定性规则计算账户执行指标。当前规则覆盖 100 股整手、最低佣金、过户费、最小成交金额、T+1 可卖库存、ST 5% 涨跌停、新股上市初期不限价、普通涨跌停、停牌和最大成交参与率。该诊断用于准入复核；主收益曲线仍是策略研究收益口径。

`premarket`：导出 07:30 盘前观察池。

```bash
./.venv/bin/python -m quant.cli premarket --config config.yaml
```

`market-regime`：导出行情分段验证报告。

```bash
./.venv/bin/python -m quant.cli market-regime --config config.yaml
```

### 3.4 静态站点命令

`site`：构建和发布多模拟账户静态控制台。默认本地输出目录为 `reports/static_site/quant/`，远端入口为 `/quant/`。

```bash
# 本地构建，不同步远端
./runit site build --config config.yaml

# 同步已有本地控制台到远端 /quant/
./runit site sync --config config.yaml

# 先构建再同步
./runit site publish --config config.yaml
```

远端同步默认读取：

```bash
QUANT_SITE_SYNC_REMOTE=linuxuser@108.61.182.91
QUANT_SITE_SYNC_REMOTE_DIR=/var/www/share/quant/
QUANT_SITE_SYNC_PASSWORD=your-password
```

将这些值写入未跟踪的 `.env`，不要提交到 Git。地址字段只写 `user@host`，不加 `ssh://` 或 `https://`；若密码含 shell 特殊字符，使用双引号包裹。`QUANT_SITE_SYNC_PASSWORD` 通过临时 `SSH_ASKPASS` 提供给 ssh，不作为命令行参数。

安全边界：`site sync` 只允许远端目录以 `/quant/` 结尾，不会同步到 `/var/www/share/` 根目录；静态站点只包含 HTML/CSS/JSON/CSV，不上传 SQLite。

`financial-pti`：财务因子 point-in-time 校验。

```bash
./.venv/bin/python -m quant.cli financial-pti --config config.yaml
```

### 3.5 数据库导入与更新

`import-history`：从本地压缩包重建 A 股历史库（首次建库或重建）。

```bash
./.venv/bin/python -m quant.cli import-history --config config.yaml
```

`import-index-history`：仅重建指数元数据和指数日线表。

```bash
./.venv/bin/python -m quant.cli import-index-history --config config.yaml
```

`update-history`：A 股历史库增量更新。

```bash
# 实际更新
./.venv/bin/python -m quant.cli update-history --config config.yaml

# 只检查新鲜度，不写库
./.venv/bin/python -m quant.cli update-history --config config.yaml --check-only

# 更新后不自动重建 universe
./.venv/bin/python -m quant.cli update-history --config config.yaml --no-build-universe
```

`update-us-market-history`：US market 本地库增量更新。

```bash
./.venv/bin/python -m quant.cli update-us-market-history --config config.yaml
./.venv/bin/python -m quant.cli update-us-market-history --config config.yaml --check-only
```

配置中的 `instrument_groups` 将标的按业务用途维护。命令会输出每组的最新共同完成交易日、覆盖情况和状态，并把每个标的的抓取窗口、写入行数、异常或空响应记录到 `us_data_source_symbol_runs`。OHLC 不合法的行不会覆盖已存在的有效日线。

`core_signal` 是当前半导体 ETF 映射策略的唯一自动交易输入（`^SOX`、`^VIX`）。其余分组仅用于研究背景和盘前人工观察；它们不会改变下单信号、仓位或执行规则。

`update-hk-market-history`：港股本地库增量更新。

```bash
./.venv/bin/python -m quant.cli update-hk-market-history --config config.yaml
./.venv/bin/python -m quant.cli update-hk-market-history --config config.yaml --check-only
```

`update-financials`：更新 A 股季度财务因子。

```bash
./.venv/bin/python -m quant.cli update-financials --config config.yaml
./.venv/bin/python -m quant.cli update-financials --config config.yaml --periods 16
./.venv/bin/python -m quant.cli update-financials --config config.yaml --no-build-universe
```

`build-universe`：单独构建本地因子股票池。

```bash
./.venv/bin/python -m quant.cli build-universe --config config.yaml
```

---

## 4. 关键输出文件

常见输出路径：

- `reports/phase0_data_source_report.md`
- `reports/phase0_walk_forward_report.md`
- `reports/phase0_effectiveness_report.md`
- `reports/phase0_walk_forward_folds.csv`
- `reports/phase0_walk_forward_candidates.csv`
- `reports/strategy_admission/strategy_admission_report.md`
- `reports/strategy_admission/strategy_admission_window_matrix.csv`
- `reports/strategy_admission/strategy_admission_constraint_review.csv`
- `reports/strategy_admission/strategy_admission_candidate_folds.csv`
- `reports/strategy_admission/overfit_diagnostic/strategy_overfit_diagnostic.csv`
- `reports/phase0_cost_sensitivity_report.md`
- `reports/phase0_cost_sensitivity.csv`
- `reports/phase0_low_turnover_bill.csv`
- `reports/phase0_low_turnover_bill_preview.html`
- `reports/<brief_date>/phase0_premarket_watchlist_<brief_date>.csv`（`daily-brief`）
- `reports/<brief_date>/phase0_premarket_report_<brief_date>.html`（`daily-brief`）
- `reports/phase0_premarket_watchlist.csv`（单独 `premarket`）
- `reports/phase0_premarket_report.html`（单独 `premarket`）
- `data/simulated_trading/phase0_daily_brief_ledger.csv`
- `data/ai_corpus/ai_corpus.sqlite`

本地数据库：

- `data/a_share_history.sqlite`
- `data/us_market_history.sqlite`
- `data/hk_market_history.sqlite`
- `data/ai_corpus/ai_corpus.sqlite`

---

## 5. 当前配置要点（与你现在的状态相关）

- A 股主链路：`Tushare + 本地 SQLite`
- US market：当前仍为 `yfinance` 过渡 provider（Tiingo 已最小接入）
- 港股：当前配置已切到 `tushare_hk` provider，并启用 `hk_market_history`
- 港股落库表：`hk_daily_bars`，含 `hk` 字段（港股行写 `HK`）

---

## 6. 常见问题与排查

### 6.1 `status=stale` 且 `rows=0`

常见原因：

- 数据源接口限频
- token 无权限
- 网络/DNS 不可达
- symbol 列表为空或格式不合法

排查顺序：

1. 先跑 `--check-only` 看覆盖率和最新日期。

2. 再看 `Warning` 里的原始报错。

3. 单独跑对应 provider 的最小抓取脚本（单标的、短区间）。

4. 必要时切换 provider 或缩小 symbols。

### 6.2 OOS/Execution 参数覆盖

`oos-report` 与 `execution-gate` 支持临时参数覆盖：

- `--slippage`
- `--commission`
- `--stamp-duty-sell`
- `--price-mode`
- `--lot-size`
- `--max-participation-rate`
- `--enable-limit-check / --no-enable-limit-check`
- `--enable-suspension-check / --no-enable-suspension-check`

建议优先用 `--profile research|live`，只在压力测试时覆盖单项参数。

---

## 7. 推荐工作流

日常（开发/研究）：

1. `daily-brief`
2. `brief confirm-account-bills`（盘后确认模拟账户账单）
3. `update-financials`（按周）
4. `update-us-market-history`
5. `update-hk-market-history`
6. `run`（策略评估或验收时）
7. `premarket`（仅在需要跳过数据更新、单独重生成观察池时使用）

验收（策略阶段）：

1. `run`
2. `execution-gate --profile live`
3. `oos-report --profile live`
4. `cost-sensitivity --use-config-scenarios`
5. `market-regime`
6. `financial-pti`

---

## 8. 参考源码

- CLI 入口：[quant/cli.py](../quant/cli.py)
- 数据源适配：[quant/data_access/connectivity.py](../quant/data_access/connectivity.py)
- 外部市场 provider 适配：[quant/data_access/providers/external_market.py](../quant/data_access/providers/external_market.py)
- US/HK 历史库更新：[quant/data_governance/external_market_history.py](../quant/data_governance/external_market_history.py)
- A 股增量更新：[quant/data_governance/update_history.py](../quant/data_governance/update_history.py)
