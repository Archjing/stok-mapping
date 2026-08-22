# stok-mapping 动态网站 — 设计与开发计划

> 版本：v0.1（草案）
> 日期：2026-08-13
> 状态：待评审。本文档在"策略验证优先于平台化"的主线约束下，规划把现有 `quant` CLI 能力 API 化，并在保留现有静态站点视觉（Belafonte Day/Night）的基础上，演进为一个可交互的量化研究控制台。
> 关联文档：[DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md)（唯一事实源）、[PROJECT_ARCHITECTURE_OVERVIEW.md](PROJECT_ARCHITECTURE_OVERVIEW.md)（架构细节）。

---

## 0. TL;DR

- **定位**：本地优先的"研究控制台"。它把 `./runit` 下已经能跑的命令变成可点击、可填参、可看进度的 Web 界面，**不改写策略口径、不新增下单能力、不碰券商**。它服务于"让策略验证更快、更可观测"，而不是把系统变成面向外部的 SaaS。
- **技术栈**：后端 FastAPI（复用现有 `quant` 纯 Python 函数，包一层 API，不迁移核心逻辑）；前端 Vite + React + TypeScript + Tailwind，用 CSS 变量 1:1 复刻现有 `quant/reporting/static/style.css` 的 Belafonte 主题；异步任务用本地进程池 + SQLite 任务表，不引入 Redis。
- **关键取舍**：先做"读"（看账户、看回测、看情报、看报告），后做"写"（建账户、跑回测、调参数），最后做"实时"（盘中刷新、WebSocket 推送）。写操作全部走**任务队列**，因为一次 walk-forward 或回填是分钟级长任务，HTTP 请求不能同步等待。
- **分三阶段**：M1 只读控制台（1–2 周）→ M2 交互式研究/回测/账户管理（2–4 周）→ M3 盘中实时与观测（按需）。

---

## 1. 目标与范围

### 1.1 要解决的问题

现有交付方式是"命令行 + 静态站点"。命令行对策略研究者可用，但存在三个摩擦点：

1. **参数散落**：跑一次 `strategy-admission` 要记住 `--presets`、`--strategy-set`、`--strategies` 等参数；调参试错成本高。
2. **结果不可比、不可追溯**：报告落在 `reports/` 各子目录，跨 run 的横向对比要人工拼表。
3. **状态不可见**：长任务（回填、walk-forward）进度只体现在日志里；调度任务（`maintain tick`）状态藏在 SQLite。

### 1.2 目标（本计划范围内）

1. **研究控制台**：策略注册/注销、参数化跑 walk-forward 回测、admission、过拟合诊断，结果入库并可在页面横向对比。
2. **账户与模拟**：查看/创建/启停模拟账户，触发盘后账本核验与恢复，查看台账与账单。
3. **情报分析**：情报采集（`intelligence collect`）、候选审查、AI 语料查询、新闻观察。
4. **行情浏览**：提供本地优先、只读的 A 股 / 美股行情看板，用于研究与盘前观察；支持单标的 K 线、A 股多标的归一化对照与代码/名称搜索，不承担交易执行职责。
5. **盘前交付**：复用并实时刷新现有观察池/简报/研究型对照报告页面，取代"每晚 build + rsync"的静态快照。
6. **系统观测**：调度任务状态、数据健康、回填审计一览。

### 1.3 明确不在范围内（本期不做）

- 不接入券商、不自动下单、不做任何真实交易。
- 不新增策略类型或改变任何策略口径（这是"策略验证"主线的事，与平台无关）。
- 不做多用户、权限、租户。单机本地工具，用户就是本机研究员。
- 不做云部署 / 容器编排 / 横向扩展。
- `phase0 → quant` 重命名已完成（`quant` 是唯一应用命名空间）。Web 层统一 import `quant.*`；`phase0.cli` 仅保留为临时兼容转发入口。

### 1.4 成功标准（Meta）

- 任何在 Web 上做的事，都能在 CLI 里找到等价的、可复现的命令；反之亦然——Web 只暴露"已验证的 CLI 能力"，不发明新能力。
- 站点的数据口径与 `config.yaml`、`DEVELOPMENT_PLAN.md` 完全一致（尤其 `qfq_asof` / 执行价格 / 密钥只从 `.env` 读）。

---

## 2. 现状盘点（可复用的资产）

### 2.1 视觉资产

- 静态站点在 `reports/static_site/quant/`，主题 CSS 源文件在 `quant/reporting/static/style.css`（499 行）。
- 主题名 **Belafonte Day / Belafonte Night**（源自 Jan T. Sott 的 macOS Terminal 配色）。
  - Light：暖羊皮纸底 `#fffaed`，卡片 `#ded8c8`，正文 `#45373c`，强调 `#426a79`。
  - Dark：深酒红底 `#20111b`，正文 `#b88f55`。
  - 通过 `[data-theme="dark"]` 覆盖 CSS 变量，前端用 `localStorage`（key `belafonte-theme`）记忆。
- 字体：中文 `LXGW WenKai Mono` / `Noto Sans Mono SC`，标题 `PingFang SC / Microsoft YaHei`，等宽 `JetBrains Mono`。
- 组件语言：`.summary` 指标卡、`.quick-card` 快捷入口、`.report-table`（sticky 表头、buy/sell/hold 行配色）、`.brief-hero`、`.brief-card`、`.theme-bar` + `themeToggle`。
- 涨红跌绿是项目明确口径（`PROJECT_ARCHITECTURE_OVERVIEW.md`："上涨使用红色、下跌使用绿色"）；表格 `buy/sell/hold` 行则用 `--focus-row` / `--red-row` 区分语义。前端必须沿用这套色语义，不随图表库默认色。
- **结论**：这些设计 token 可以直接搬进前端设计系统（见 §6）。

### 2.2 后端能力（全部在 `quant/`，纯 Python，无任何 web 框架）

| 领域 | 模块 | 可 API 化的能力 |
| --- | --- | --- |
| 数据治理 | `quant/data_governance/*` | `update-history`、`update-us/hk-market-history`、`backfill-etf-history`、`resolve-etf-universe`、`db-health`、审计 |
| 策略研究 | `quant/walk_forward.py`、`quant/research/*`、`quant/strategies/*` | walk-forward 回测、compare、factor-effectiveness、overfit-diagnostic、execution-gate、admission、failure-attribution |
| 策略注册 | `quant/strategies/registry.py` | `available_strategies()` 枚举 32 个已注册策略（分布在 `strategies/` 下，部分文件定义多个变体） |
| 模拟执行 | `quant/execution/*` | `accounts.py`（日频目标权重）、`single_etf_intraday.py`（5 分钟 ETF）、`strategy_ledger.py` |
| 账户 | `quant/execution/accounts.py` + `config.yaml: accounts` | 账户配置、台账、账单、`intraday-account --recover-missing` |
| 情报 | `quant/intelligence/*` | `collect`、`import-local`、`review-candidates`、`validate`；`ai_corpus` 查询 |
| 交付 | `quant/reporting/*` | 观察池、简报、对照图、`quant_static_site.py` 的 build/publish |
| 运维 | `quant/maintenance_orchestrator.py` | `maintain tick/status/run/stop/resume/supervise` |

关键结论：**核心业务逻辑都是"输入 config + 参数 → 产出文件/报告/DB 行"的纯函数，没有全局可变状态**。这意味着 API 层可以做得很薄——大部分端点只是"把 HTTP 参数翻译成函数调用，把返回值序列化成 JSON"。

### 2.3 依赖与运行环境

- Python `>=3.12`，依赖 `tushare/akshare/yfinance/pandas/numpy/jinja2/matplotlib/rich/feedparser/requests/pyyaml`。
- 虚拟环境里已有 `starlette`/`uvicorn`/`pydantic`（作为 `mcp` 的传递依赖），但**`fastapi` 尚未安装，且三者均未在 `pyproject.toml` 声明**；开工时需 `uv add fastapi uvicorn[standard]`（pydantic 已随 FastAPI 可用）。
- 项目用 `uv` 管理（`uv.lock`、`[project.scripts]`），新增依赖走 `uv add`。

---

## 3. 关键设计决策

### D1. 单体 FastAPI 应用 + 薄 API 层，不重写核心逻辑

后端是一个 FastAPI app，直接 import `quant.*` 的函数。理由：

- 核心逻辑已经在 CLI 里验证过，重写只会引入口径漂移。
- FastAPI 的 Pydantic 模型可以用来做参数校验，把 CLI 的 argparse 约束搬到 HTTP 层。

**纪律**：API 层只做"参数翻译、调用、序列化、权限/并发控制"，不得包含策略逻辑。任何"Web 上新增的能力"必须先落成 CLI 命令 + 测试，再暴露 API（保证可复现、可回归）。

### D2. 写操作用"任务队列"，读操作同步返回

一次 `strategy-admission` 是分钟级长任务，不能挂在 HTTP 连接上。方案：

- 用本地进程池（`concurrent.futures.ProcessPoolExecutor`，因为 pandas 重计算应脱离 GIL 且需要进程隔离）执行长任务。
- 任务状态存进一个新的 SQLite 表 `web_jobs`（或复用现有 `logs/` 下机制，见 D5），前端轮询或通过 SSE/WebSocket 订阅进度。
- 进度上报：现有 `walk_forward` 已有 `TraceCallback` / `_emit_trace` 机制，可以作为进度推送的天然钩子。

**明确不做**：不引入 Celery/Redis/RabbitMQ。单机工具不需要分布式队列，SQLite + 进程池足够，且避免"多一份基础设施要运维"的债务。

### D3. 进程模型：单一 worker 进程 + 持久调度

- 一个 uvicorn 进程常驻，负责 HTTP + 进程池。
- **长任务并发上限**：CPU 密集任务（walk-forward/admission）并发上限设为 `max(1, cpu_count-1)`，防止拖垮本机。
- **与现有 cron 的关系**：现有 `scripts/run_project_scheduler.sh` → `quant.cli maintain tick` 的调度链路**保持不变**。Web 的任务队列是"用户主动触发的任务"，调度链是"系统定时任务"，两者读写同一套 DB 与报告目录，通过文件锁（现有 `maintain` 已有锁机制）避免冲突。

### D4. 数据一致性：单一事实源仍是 `config.yaml` + SQLite + `reports/`

- Web 不另建"配置数据库"。账户、策略参数仍以 `config.yaml` 为事实源，Web 的"改参数"其实是"生成一个新的 run 配置"（见 §5 领域模型），不直接改写 `config.yaml` 主文件（或只在明确的"账户管理"子集里写入，且先备份）。
- 回测/报告结果继续写 `reports/`，Web 通过读取报告产物或新的 run 索引表来展示，避免把报告内容复制进另一份 DB。

### D5. 新增一张"运行索引"表，不破坏现有目录

现有 `reports/runs/`、`reports/archive/` 是按报告类型组织的历史产物。为了支持"跨 run 横向对比"，新增一个轻量索引库：

- 表 `run_index`：`run_id, kind(admission|walk_forward|backtest|recover|...), params_json, config_hash, status, started_at, finished_at, artifacts_json, exit_code, error`。
- 只存元数据与产物路径，**不复制报告正文**；正文仍从 `reports/` 文件读。
- 这样"结果可追溯、可对比"的目标达成，同时不改变现有报告目录结构。

### D6. 认证：本地单用户，最小防御

- 默认 `127.0.0.1` 绑定 + 一个 `WEB_TOKEN`（从 `.env` 读，无则随机生成并打印）。所有写端点要求 `Authorization: Bearer <token>`。
- 原因：系统能触发数据回填、跑回测、`rsync publish`，即便本机也应对非预期访问设最低限度的门槛。**密钥仍只从 `.env` 读，永不进代码/config/文档**。

### D7. 静态站点与动态站点的关系

- 短期：动态站点**复用**静态站点的 HTML 片段作为"只读报告视图"（报告本身就是生成的 HTML），前端用 iframe 或直接路由嵌入，减少重复工作。
- 长期：`quant_static_site.py` 的 build 产出降级为"离线备份/发布快照"，动态站点成为主界面；`site publish` 的 rsync 保留给外部只读分享场景。
- 视觉上两者共享同一份设计 token，保证迁移后用户无感。

---

## 4. 技术栈选型

### 4.1 后端

| 组件 | 选择 | 理由 |
| --- | --- | --- |
| Web 框架 | **FastAPI** | 与现有 `quant` 纯函数无缝集成；Pydantic 校验参数；自动 OpenAPI 文档；异步友好（SSE/WS 简单） |
| 服务 | **uvicorn[standard]** | FastAPI 官方配套；已作为传递依赖存在 |
| 任务执行 | `ProcessPoolExecutor`（标准库） | 无新依赖，进程隔离保护内存与 GIL |
| 任务状态 | SQLite（新增 `web_jobs` 表） | 与项目 SQLite-first 一致 |
| 参数校验 | Pydantic v2（FastAPI 自带） | 与 argparse 约束对应 |
| 进度推送 | **SSE**（首选）/ WebSocket（后续） | SSE 单向、实现简单，够用 |

> 备选评估：Flask 更轻但异步/校验弱；Django 过重（自带 ORM/Admin 我们用不上且与 SQLite-first 手写 SQL 风格冲突）。选 FastAPI 是"用最少的新东西换最强的类型/文档能力"。

### 4.2 前端

| 组件 | 选择 | 理由 |
| --- | --- | --- |
| 构建 | **Vite** | 快、生态成熟 |
| 框架 | **React 18 + TypeScript** | 状态密集（任务进度、表格、表单），React 生态最全 |
| 样式 | **Tailwind CSS + CSS 变量** | 用 CSS 变量把 Belafonte 主题 1:1 映射成 design token，Tailwind 负责布局/组件；避免"另起一套视觉" |
| 图表 | **ECharts**（中文生态、K 线/多序列支持好）或 **Lightweight Charts**（TradingView 开源，专为金融时序） | 对照图、资金曲线、净值曲线用；ECharts 优先（与中文报告一致），K 线场景可引入 Lightweight Charts |
| 表格 | TanStack Table（虚拟滚动，报告表格行数大） | 现有报告表格动辄上千行 |
| 数据请求 | TanStack Query | 轮询任务进度、缓存只读数据 |
| 状态 | Zustand | 轻量，够用 |
| 路由 | React Router | 标准 |

> 前端全部构建为静态资源，由 FastAPI 在 `/` 提供（生产），开发期 Vite dev server 代理到 `127.0.0.1:8010`。单一仓库（monorepo 单目录）结构，见 §6。
> **端口约定**：后端统一用 **8010**（`uvicorn web.app.main:app --port 8010`）；**8000 被本机模型服务（oMLX，`http://172.16.10.254:8000`）占用，严禁使用**。前端 dev：`web/ui`=5173（代理 `/api`→8010）、`web/index-chart`=5180。

### 4.3 为什么不选

- **不做 SSR/Next.js**：这是本地工具，无 SEO 需求，CSR + API 最简单。
- **不用 Streamlit/Gradio**：它们适合快速原型，但做不到"复刻 Belafonte 视觉 + 精确的交互控制 + 与现有 Python 模块的清晰边界"。
- **不引入独立数据库服务器（Postgres）**：SQLite-first 是项目既定风格，单机场景够用。

---

## 5. 领域模型（核心概念）

### 5.1 已有实体（映射现有代码）

- `Strategy`（策略）：`strategy_id`（如 `legacy_momentum_low_turnover_v1`）、`display_name`、`category`、`panel_scope`、`execution_model`、`supports_*` 标志。来源 `strategies/registry.py` + `config.yaml: strategy_reports`。
- `StrategySet` / `Preset`：admission 的 `strategy_set`（如 `baseline_admission_all_v1`）与 walk-forward `presets`（如 `baseline_2y_1y_5fold`）。
- `Account`（模拟账户）：`account_id`、`name`、`initial_cash`、`strategy_id`、`execution_model`、`execution_price_mode`、成本参数、`enabled`。来源 `config.yaml: accounts.simulated` + `execution/accounts.py`。
- `Run`（回测运行）：一次 walk-forward / admission / compare 的产物。**本计划新增 `run_index` 表持久化其元数据。**
- `Job`（任务）：一次异步执行（回测、回填、恢复）。新增实体。
- `IntelligenceCandidate` / `Corpus`：情报候选与 AI 语料。已有 `intelligence/schema.py`、`ai_corpus`。
- `Ledger`（台账）、`Bill`（账单）、`Watchlist`（观察池）：已有产物。

### 5.2 新增实体

- `Job`：`job_id, kind, payload_json, status(pending|running|succeeded|failed|cancelled), progress, log_path, created_at, started_at, finished_at, exit_code, error`。
- `RunIndex`：`run_id, job_id?, kind, strategy_ids, params_json, config_hash, benchmark, status, metrics_json, artifacts_json, created_at`。

### 5.3 关系

```text
config.yaml（事实源）
  ├─ accounts ──────────── Account（配置）
  ├─ strategy_reports ──── Strategy（元数据）
  └─ walk_forward ──────── Preset / StrategySet / gate

User 触发 Job ──(执行)──> Run ──(产出)──> reports/…（报告、CSV、HTML）
                          └──(写入)──> run_index 行
Job ──(进度)──> web_jobs 表 ──(SSE)──> 前端
```

---

## 6. 系统架构

### 6.1 进程与目录

```text
stok-mapping/
├─ quant/                     # 现有核心（不动）
├─ web/                        # 新增
│  ├─ app/
│  │  ├─ main.py               # FastAPI app 工厂
│  │  ├─ api/                  # 路由层（薄）
│  │  │  ├─ strategies.py
│  │  │  ├─ runs.py
│  │  │  ├─ accounts.py
│  │  │  ├─ intelligence.py
│  │  │  ├─ reports.py
│  │  │  ├─ system.py
│  │  │  └─ jobs.py
│  │  ├─ schemas.py            # Pydantic 模型
│  │  ├─ jobs.py               # 任务队列（进程池 + SQLite）
│  │  ├─ run_index.py          # 运行索引
│  │  ├─ auth.py               # 简单 token
│  │  └─ adapters.py           # CLI 参数 ↔ 函数调用的翻译
│  └─ ui/                      # 前端（Vite + React + TS）
│     ├─ src/
│     │  ├─ theme/             # Belafonte design tokens
│     │  ├─ pages/             # 页面
│     │  ├─ components/        # summary/quick-card/report-table 等
│     │  └─ api/               # TanStack Query hooks
│     └─ package.json
├─ data/
│  └─ web_jobs.sqlite          # 新增（任务 + run_index）
├─ config.yaml                 # 事实源（不变）
└─ reports/                    # 产物（不变）
```

### 6.2 请求流（读）

```text
Browser ──GET /api/accounts──> FastAPI ──import quant──> 读 config/SQLite/报告
         <──JSON─────────────            <──纯函数返回──
```

### 6.3 请求流（写 / 长任务）

```text
Browser ──POST /api/runs──> FastAPI 校验→入队(web_jobs)→返回 202 {job_id}
Worker（进程池）──运行 quant 函数──> 写 reports/ + run_index + 进度
Browser ──GET /api/jobs/{id}（或 SSE）──> 轮询进度/结果
```

### 6.4 并发与锁

- 复用现有 `maintain` 的文件锁与 `logs/` 状态机制，防止 Web 触发的回填与 cron 触发的回填并发写同一 DB。
- 所有写 DB 的操作经过同一 `data_governance` 模块，保持其内部已有的幂等/可恢复语义。

---

## 7. API 设计（REST 概要）

> 完整 OpenAPI 由 FastAPI 自动生成。这里只列关键资源与语义，确保与 CLI 一一对应。

### 7.1 策略与研究

| 方法 | 路径 | 说明 | 对应 CLI |
| --- | --- | --- | --- |
| GET | `/api/strategies` | 列出可用策略（含元数据） | `strategies/registry` |
| GET | `/api/strategies/{id}` | 单策略详情 + 支持的报告类型 | — |
| GET | `/api/presets` | walk-forward presets 与 admission strategy_sets | `strategy-admission --presets` 描述 |
| POST | `/api/runs/walk-forward` | 发起一次回测/compare | `run` / `pipeline_run` |
| POST | `/api/runs/admission` | 发起 admission | `strategy-admission` |
| POST | `/api/runs/diagnostic` | overfit / execution-gate / failure-attribution | `overfit-diagnostic` 等 |
| GET | `/api/runs` | 运行索引（可过滤 kind/strategy/状态，支持对比） | 新增 `run_index` |
| GET | `/api/runs/{id}` | 单 run 指标 + 产物链接 | — |
| GET | `/api/runs/{id}/artifacts/*` | 读报告产物（HTML/CSV/MD） | — |

### 7.2 账户与模拟

| 方法 | 路径 | 说明 | 对应 CLI |
| --- | --- | --- | --- |
| GET | `/api/accounts` | 账户列表（含最新总资产/仓位） | `config.yaml: accounts` |
| GET | `/api/accounts/{id}` | 账户详情 + 台账/账单入口 | `intraday-account`（只读） |
| POST | `/api/accounts` | 创建模拟账户（写 config.yaml，先备份） | 手工编辑 config |
| POST | `/api/accounts/{id}/disable` | 注销/停用账户 | 编辑 config |
| POST | `/api/accounts/{id}/recover` | 盘后核验/恢复（只读重放语义不变） | `intraday-account --recover-missing` |
| GET | `/api/accounts/{id}/ledger` | 台账 | `reports/…/ledger` |

> 账户创建/注销是最敏感的写操作之一，M2 才做，且限制字段子集、强制确认。

### 7.3 情报与语料

| 方法 | 路径 | 说明 | 对应 CLI |
| --- | --- | --- | --- |
| POST | `/api/intelligence/collect` | 采集情报候选 | `intelligence collect` |
| GET | `/api/intelligence/candidates` | 候选列表 + 审查建议 | `intelligence review-candidates` |
| POST | `/api/intelligence/candidates/{id}/import` | 入库 | `intelligence import-local` |
| GET | `/api/corpus/query` | AI 语料检索（新闻等） | `ai-corpus query` |

### 7.4 系统与观测

| 方法 | 路径 | 说明 | 对应 CLI |
| --- | --- | --- | --- |
| GET | `/api/system/status` | 调度状态、数据健康摘要 | `system status` / `maintain status` |
| POST | `/api/maintain/tick` | 触发一次维护 tick | `maintain tick` |
| GET | `/api/jobs` / `/api/jobs/{id}` | 任务列表/详情/进度 | 新增 |
| GET | `/api/jobs/{id}/events` | SSE 进度流 | 新增 |

### 7.5 报告与页面

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/reports/watchlist` | 各账户盘前观察池数据 |
| GET | `/api/reports/brief` | 每日简报数据 |
| GET | `/api/reports/comparison/{slug}` | 对照图数据（SOX/VIX vs ETF） |
| GET | `/report/{path}` | 直接提供已生成的静态 HTML（只读视图，iframe 嵌入） |

---

## 8. 前端设计（页面地图 + 视觉映射）

### 8.1 布局骨架

沿用现有站点的 `.theme-bar`（左上返回链接 + 右上 Belafonte 主题切换）+ `.page`（max-width 1340px 居中）。新增左侧导航（桌面）用于领域切换：

```text
┌───────────────────────────────────────────────┐
│ theme-bar: 返回 │ 主题切换(Belafonte Day/Night) │
├──────────┬────────────────────────────────────┤
│ 研究      │                                  │
│ 账户      │         当前页内容                 │
│ 情报      │                                  │
│ 观测      │                                  │
└──────────┴────────────────────────────────────┘
```

导航项：**研究**（策略 / 回测 / 准入 / 对比）、**账户**（账户 / 台账 / 盘前）、**情报**（候选 / 语料 / 新闻）、**观测**（任务 / 调度 / 数据健康）。

### 8.2 页面清单

1. **控制台首页** `/`：核心入口 quick-cards（对应现有 index.html 的 BRIEF/RESEARCH/账户入口）+ 数据健康摘要 + 最近任务。
2. **策略列表** `/strategies`：32 个策略卡片（display_name、category、panel_scope、执行模型、支持的报告）。
3. **策略详情** `/strategies/:id`：元数据 + 该策略的历史 run 列表 + "发起回测"入口。
4. **回测运行器** `/runs/new`：表单（preset / strategy-set / strategies / 成本缩放 / trace 开关）→ 提交后跳任务详情。
5. **任务详情** `/jobs/:id`：SSE 实时进度、日志尾随、完成后产物链接。复用现有 `walk_forward` 的 `TraceCallback` 输出。
6. **运行对比** `/runs`：按 kind/策略过滤的 run 表，多选横向对比关键指标（年化/夏普/回撤/OOS 一致性/换手），用 ECharts 画净值曲线叠加。
7. **准入报告视图** `/runs/:id`：展示 admission 的 window matrix / constraint review / governance 报告（嵌入现有 MD/HTML 产物或结构化渲染）。
8. **账户列表** `/accounts`：复用现有账户总览表（账户 ID/名称/最新账单日/总资产/仓位/入口）。
9. **账户详情** `/accounts/:id`：summary 指标卡 + 台账 + 账单 + 观察池 + 快捷入口（对应现有账户页）。
10. **盘前观察池** `/accounts/:id/watchlist`：SOX/VIX 信号卡 + 研究背景表 + 新闻表（对应现有 watchlist 页，改为 API 实时）。
11. **对照图** `/research/comparison/:slug`：SOX/VIX vs 512480 对照图（ECharts，复用 `market_comparison_chart` 数据）。
12. **情报候选** `/intelligence`：候选 inbox 表 + 审查建议 + 入库/忽略操作。
13. **语料检索** `/intelligence/corpus`：关键词检索新闻/论文语料。
14. **系统观测** `/system`：`maintain status`、数据健康、回填审计、调度任务状态。

### 8.3 Belafonte 主题 → 前端 Design Token

把 `style.css` 的 CSS 变量直接映射为 Tailwind 主题（`tailwind.config` 扩展颜色）：

```text
--bg / --bg-card / --border / --text / --text-dim / --text-muted
--accent / --accent-bg / --accent-text
--focus-text / --focus-strong / --focus-row
--red-text / --red-row / --amber
--header-bg / --header-fg
```

- 组件映射：`.summary div` → `MetricCard`；`.quick-card` → `QuickCard`；`.report-table` → `ReportTable`（sticky 表头 + `buy/sell/hold` 行语义）；`.brief-hero`/`.brief-card` → `BriefHero`/`BriefCard`。
- 涨红跌绿：数字组件统一 `positive→红(#be100e light) / negative→绿`（严格遵循现有语义，不随图表库默认色）。
- 主题切换：`data-theme` 挂在 `<html>`，`localStorage key = belafonte-theme`，与现有站点完全一致。

---

## 9. 分阶段实施计划

> 每阶段结束都要求"可运行 + 有测试 + 有 CLI 等价命令"，避免"Web 上能点但 CLI 复现不了"的漂移。

### M1 — 只读控制台（目标：把静态站点"活"起来）

范围：

1. 搭 FastAPI 骨架 + 认证 + `/api/strategies`、`/api/accounts`、`/api/system/status`、`/api/reports/*`。
2. 前端骨架：主题 token 落地、布局、导航、控制台首页、账户列表/详情、盘前观察池、对照图（读 API）。
3. 报告只读视图：`/report/{path}` 提供现有 HTML。

验收：

- 打开 `http://127.0.0.1:8010` 能看到与现有静态站点视觉一致的账户总览、账户详情、观察池、对照图。（端口约定：8000 预留给本机模型服务 oMLX，后端统一 8010。）
- 所有页面数据来自 API，`GET` 端点有对应 pytest；`maintain status`、账户数据与 CLI 输出一致。
- 不引入任何写端点。

### M2 — 交互式研究与账户管理（目标：替代大部分 CLI 试错）

范围：

1. 任务队列（`web_jobs` + 进程池）+ `run_index`。
2. 写端点：walk-forward、admission、diagnostic；账户创建/停用；`intraday-account recover`。
3. 前端：回测运行器、任务详情（SSE 进度）、运行对比、准入报告视图、情报候选/语料。
4. 参数校验：把 argparse 约束搬到 Pydantic，写端返回明确校验错误。

验收：

- 在 Web 发起一次 `strategy-admission`，能在任务详情看到进度、完成后看到与 CLI 一致的报告产物；`run_index` 有记录，可与另一 run 对比。
- 账户创建/停用会先备份 `config.yaml`，写入的字段与 CLI 手改等价；错误输入被拒绝。
- 情报采集/审查流程可在 Web 完成，且与 `intelligence` CLI 产物一致。

### M3 — 盘中实时与观测增强（按需，不阻塞主线）

范围：

1. SSE/WebSocket 推送任务进度、盘中账户状态刷新。
2. 调度状态可视化、回填审计仪表盘。
3. 视需要把 `site publish` 做成"一键发布"按钮（仍走 `.env` 密码、仍只发 HTML/CSS/JSON/CSV）。

验收：

- 盘中观察池/账户页在数据更新后自动刷新，无需手动 rebuild。
- 观测页能定位一次失败回填的原因与恢复入口。

---

## 10. 风险与待决事项

| 风险 / 待决 | 影响 | 缓解 / 决策点 |
| --- | --- | --- |
| Web 触发的回填与 cron 并发写 DB | 数据损坏 | 复用现有文件锁；Web 写任务与 cron 任务走同一锁域；M2 前做并发测试 |
| 长任务占满 CPU 拖慢本机 | 研究员本机变卡 | 进程池并发上限 `cpu_count-1`；提供取消；低优先级 nice |
| `config.yaml` 被 Web 改写失控 | 事实源被污染 | 账户写操作限制字段子集 + 强制备份 + 记录 config_hash |
| 报告产物目录结构与 `run_index` 不同步 | 对比错乱 | `run_index` 只存产物路径，正文从文件读；每次 run 结束做一次一致性校验 |
| 前端复刻视觉走样 | 与静态站点不一致 | 用同一份 CSS 变量源；抽 `theme/` 单一 token 文件；视觉验收对照截图 |
| 密钥/密码泄漏到 Web | 安全 | 密钥仍只从 `.env` 读；Bearer token 保护写端点；`publish` 按钮后端用 `SSH_ASKPASS`，前端不碰密码 |
| 进度推送的钩子不够细 | 任务详情"假死" | 复用 `walk_forward.TraceCallback`；不足则在 CLI 层补 trace 点（同时惠及 CLI） |
| `quant` 命名空间后续演进（如移除 `phase0.cli` 兼容转发） | Web import 路径变更 | Web 层全部 import 集中在 `adapters.py`，改动只在一处 |

**建议在开工前与项目主人确认的点**：

1. 是否接受"Web 账户管理写 `config.yaml`"？还是账户管理保持 CLI-only、Web 只读？（本计划默认 M2 做受控写。）
2. 前端图表库选 ECharts 还是 TradingView Lightweight Charts？（对照图/净值曲线，视觉风格有差异。）
3. 是否需要暴露到局域网（非 127.0.0.1）？这决定认证强度的投入。

---

## 11. 与主线的边界声明（重要）

本计划是**平台化**工作。按 [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md)，当前主线的 P0 是"证明策略在真实约束下成立"（逐 ETF 准入、修复 US 信号源、组合策略重建）。因此：

- 本网站开发**不得阻塞或取代**策略验证工作；M1/M2 以"复用已验证 CLI 能力"为原则，不新增策略、不改口径。
- 若两者资源冲突，优先保障 P0 策略验证；本计划可按里程碑插入推进。
- 网站本身是"让验证更快、更可观测"的工具，其最终价值取决于策略验证是否更快收敛——而不是页面数量。
