# T6.3｜数据治理与维护编排器专项开发计划

> 父级任务域：`T6` 运维调度与后台任务。  
> 目标形态：把当前 shell 调度器演进为本地优先、可审计、可恢复的数据治理控制平面。  
> 当前状态：专项计划已建立，尚未开始代码实现。  
> 推荐架构模式：`Control Plane + Command Registry + State Machine + Policy Gate + Supervisor`。

---

## T6.3.1 架构定位

### T6.3.1.1 要解决的问题

当前项目已经具备：

- `scripts/run_project_scheduler.sh` 统一 cron 入口
- `db-health` 只读健康检查与退出码门禁
- `backfill-tushare-history` / `backfill-tushare-financials` 回填与审计报告
- source audit、运行日志、调度 stamp 和简单锁

但这些能力仍分散在 shell、CLI、报告文件和任务表中，缺少一个统一的维护编排器来回答：

- 哪个任务应该在什么窗口运行？
- 为什么某个任务被跳过、阻断或失败？
- 失败后是否应该重试？
- 长 backfill 当前有哪些 shard 正在跑？
- 手动中断后如何只恢复未完成 shard？
- 哪些报告是本次运行产物，哪些是历史汇总账本？

### T6.3.1.2 与 System Orchestrator 的关系

维护编排器不应演进成单体超级编排器。项目长期应采用：

```text
System Orchestrator（总体编排器）
    ├── Maintenance Orchestrator（数据治理与维护）
    ├── Research Orchestrator（策略研究与实验）
    ├── Delivery Orchestrator（日报 / 报告 / 观察池交付）
    ├── Account Orchestrator（模拟账户与复盘）
    └── Focus Orchestrator（关注个股分析）
```

总体编排器只做统一入口和跨域协调：

- [ ] 统一任务注册和 workflow registry。
- [ ] 统一 run id、状态查询、日志和报告索引。
- [ ] 统一 TUI / 桌面 UI 后端接口。
- [ ] 统一危险操作边界，例如停止长任务、覆盖数据、触发远端同步。
- [ ] 汇总“今天系统状态如何”，但不承载具体业务规则。

领域子编排器负责各自状态机：

| 编排器 | 职责 | 典型命令 |
| --- | --- | --- |
| `Maintenance` | 数据更新、backfill、`db-health`、source audit、调度 | `maintain tick/status/run/stop/resume` |
| `Research` | 因子诊断、回测、策略准入、过拟合诊断 | `research run/status/compare/admission` |
| `Delivery` | daily brief、watchlist、报告归档、ECS 同步 | `deliver daily/watchlist/status` |
| `Account` | 模拟账单、持仓、成交、真实账户 CSV 对账 | `account sync/report/reconcile` |
| `Focus` | 关注个股分析、单股报告、单股可视化看板 | `focus add/refresh/report/dashboard/tui` |

推荐总体入口：

```bash
./.venv/bin/python -m phase0.cli system status --config config.yaml
./.venv/bin/python -m phase0.cli system run --config config.yaml --workflow daily
./.venv/bin/python -m phase0.cli system tui --config config.yaml
```

演进原则：

- [ ] `System Orchestrator = thin shell + registry + shared state`。
- [ ] 各领域子编排器拥有自己的业务状态机，不把所有逻辑塞进一个模块。
- [ ] 第一阶段先实现 `Maintenance Orchestrator`，再补 `system status` 汇总入口。
- [ ] TUI / 桌面 UI 连接总体编排器，不直接散连每个业务模块。

### T6.3.1.3 架构边界

- [ ] 编排器只做调度、门禁、状态、重试、监督和审计，不重写业务数据生产逻辑。
- [ ] 现有 `update-history`、`update-financials`、`backfill-*`、`brief`、`db-health` 继续作为 data plane。
- [ ] 第一版不引入 Airflow、Celery、Redis、systemd service、Kubernetes 或外部队列。
- [ ] 第一版继续使用本机 cron 作为 tick 触发器，但 cron 只调用 Python 编排器。
- [ ] 状态落到本地 SQLite，便于审计、恢复和后续报告。

---

## T6.3.2 推荐架构模式

### T6.3.2.1 Control Plane / Data Plane

- [ ] Control Plane：新增维护编排器，负责决策和状态。
- [ ] Data Plane：保留现有 CLI 与业务模块，负责真实数据读取、写入、报告生成。
- [ ] 编排器通过命令适配器调用现有 CLI，避免第一阶段大范围重构。

### T6.3.2.2 Command Registry

- [ ] 每个维护任务定义为一个 command spec。
- [ ] command spec 至少包含任务名、命令、时间窗口、交易日历、依赖、前置健康检查、后置健康检查、重试策略、超时和产物规则。
- [ ] 首批任务映射当前统一调度器已有任务：
  - [ ] `daily_brief`
  - [ ] `a_share_history`
  - [ ] `hk_market_history`
  - [ ] `us_market_history`
  - [ ] `financial_factors`

### T6.3.2.3 State Machine

任务状态统一为：

```text
pending -> running -> succeeded
pending -> skipped
pending -> blocked
running -> failed
running -> cancelled
failed -> pending
blocked -> pending
cancelled -> pending
```

- [ ] `skipped` 必须记录跳过原因，例如未到窗口、非交易日、依赖未满足、当天已完成。
- [ ] `blocked` 表示门禁或依赖不允许继续运行，例如 `db-health` error。
- [ ] `failed` 表示任务实际启动后退出失败。
- [ ] `cancelled` 表示用户或编排器主动中断。

### T6.3.2.4 Policy Gate

- [ ] 运行前统一执行交易日历、锁、状态、依赖、失败次数和 `db-health` 检查。
- [ ] 运行后统一记录 exit code、报告路径、error summary 和关键结论。
- [ ] 调度任务默认使用 `db-health --scope scheduler --fail-on warning`。
- [ ] A 股研究与数据任务默认使用 `db-health --scope cn --fail-on error` 或 `financial/error`。

### T6.3.2.5 Supervisor

- [ ] 长任务使用子进程组运行，记录 pid、command、start time 和 shard。
- [ ] `stop` 能中断一个 run 的全部 shard。
- [ ] `resume` 只重启未完成、失败或中断的 shard。
- [ ] 分片限速由全局额度分配，Tushare 200/min 档位默认三 shard，每 shard 66-67/min。

### T6.3.2.6 Append-only Audit Ledger

- [ ] 编排器运行事件只追加，不覆盖。
- [ ] backfill 详细报告继续按 `reports/YYYY-MM-DD/` 输出。
- [ ] backfill 汇总报告继续每次追加 1 行关键结论。
- [ ] 编排器只登记报告路径与结论，不复制或改写报告内容。

---

## T6.3.3 数据模型设计

### T6.3.3.1 状态库

建议新增：

```text
data/maintenance/maintenance.sqlite
```

### T6.3.3.2 首批表

- [ ] `maintenance_runs`
  - `run_id`
  - `task_name`
  - `planned_date`
  - `schedule_window`
  - `status`
  - `attempt`
  - `started_at`
  - `finished_at`
  - `exit_code`
  - `pid`
  - `command`
  - `health_scope`
  - `health_status`
  - `error_summary`
  - `key_conclusion`

- [ ] `maintenance_events`
  - `event_id`
  - `run_id`
  - `task_name`
  - `event_at`
  - `event_type`
  - `message`
  - `severity`

- [ ] `maintenance_artifacts`
  - `artifact_id`
  - `run_id`
  - `task_name`
  - `artifact_type`
  - `path`
  - `created_at`

- [ ] `maintenance_locks`
  - `task_name`
  - `run_id`
  - `pid`
  - `locked_at`
  - `expires_at`

- [ ] `maintenance_shards`
  - `shard_id`
  - `run_id`
  - `task_name`
  - `shard_index`
  - `shard_count`
  - `status`
  - `pid`
  - `started_at`
  - `finished_at`
  - `exit_code`
  - `processed`
  - `failed`
  - `artifact_path`

---

## T6.3.4 CLI 设计

### T6.3.4.1 统一入口

建议新增 `phase0.cli maintain` 子命令组：

```bash
./.venv/bin/python -m phase0.cli maintain tick --config config.yaml
./.venv/bin/python -m phase0.cli maintain status --config config.yaml
./.venv/bin/python -m phase0.cli maintain run --config config.yaml --task a_share_history
./.venv/bin/python -m phase0.cli maintain stop --config config.yaml --task tushare_financial_backfill
./.venv/bin/python -m phase0.cli maintain resume --config config.yaml --task tushare_financial_backfill
```

### T6.3.4.2 子命令职责

- [ ] `maintain tick`：由 cron 每分钟调用，判断本分钟哪些任务该运行。
- [ ] `maintain status`：展示最近成功、最近失败、当前运行、阻断原因和报告路径。
- [ ] `maintain run --task <name>`：手动触发单个任务，仍执行门禁与锁。
- [ ] `maintain stop --run-id|--task`：中断当前运行任务或长任务全部 shard。
- [ ] `maintain resume --run-id|--task`：恢复可续跑任务，只重启未完成 shard。

### T6.3.4.3 配置入口

建议在 `config.yaml` 新增：

```yaml
maintenance_orchestrator:
  enabled: true
  state_db: data/maintenance/maintenance.sqlite
  default_timezone: Asia/Shanghai
  tasks: []
```

第一版可先在代码中提供内置默认 registry，再逐步迁移到配置文件，降低一次性配置风险。

---

## T6.3.5 分阶段开发任务

### T6.3.5.1 P0：专项文档和任务建模

- [x] 创建本专项任务单。
- [x] 更新主计划、架构文档和任务索引。
- [x] 明确第一版只做本地 Python 编排器，不引入外部任务系统。
- [x] 明确现有 CLI 继续作为 data plane。

验收标准：

- [x] 主计划可定位到 `T6.3`。
- [x] 架构文档能说明编排器在交付与运维层的位置。
- [x] 后续实现者不需要重新决定架构模式。

### T6.3.5.2 P1：状态库与 dry-run tick

- [ ] 新增 `phase0/maintenance_orchestrator.py`。
- [ ] 新增状态库初始化逻辑。
- [ ] 新增内置任务 registry，覆盖当前 shell 调度任务。
- [ ] 实现 `maintain tick --dry-run`，只输出将运行、跳过和阻断原因。
- [ ] 实现 `maintain status`，读取状态库展示最近运行。

验收标准：

- [ ] 不改现有 cron 行为也能 dry-run 出与 shell 调度一致的任务判断。
- [ ] 每个跳过原因可追溯。
- [ ] `maintenance.sqlite` schema 可重复初始化。

### T6.3.5.3 P2：短任务编排上线

- [ ] 实现真实 `maintain tick`。
- [ ] 把 `scripts/run_project_scheduler.sh` 降级为 wrapper，加载 `.env` 后调用 `maintain tick`。
- [ ] 接入运行窗口、重试次数、重试间隔和状态锁。
- [ ] 成功后写入 `maintenance_runs`，兼容保留现有 `logs/scheduler/*.last`。

验收标准：

- [ ] `daily_brief`、`a_share_history`、`hk_market_history`、`us_market_history`、`financial_factors` 能由编排器驱动。
- [ ] 失败任务在时间窗口内重试。
- [ ] 同一任务不会重复并发启动。
- [ ] `db-health` 阻断时状态为 `blocked`，不是 `failed`。

### T6.3.5.4 P3：长 backfill 分片监督

- [x] 为 `backfill-tushare-financials` 定义 orchestrated run spec。
- [x] 支持 3 shard 自动启动，默认每 shard `66-67` requests/min。
- [x] 支持 `stop` 中断所有 shard。
- [x] 支持 `resume` 只重启未完成、失败或中断 shard。
- [x] 将每个 shard 的 pid、命令、日志路径和状态写入 `maintenance_shards`。
- [ ] 补持续 supervisor，使后台 shard 退出码可从 `exited_unknown` 精确更新为成功或失败。

验收标准：

- [x] `maintain run --task tushare_financial_backfill` 能启动 3 个独立子进程。
- [x] `maintain stop --task tushare_financial_backfill` 能停止全部 shard。
- [x] 某个 shard 失败后，`maintain resume` 只重启该 shard。
- [x] 汇总状态能同时展示总 run 和每个 shard。

### T6.3.5.5 P4：治理报告与观察面板

- [ ] 新增 `reports/maintenance/maintenance_status_YYYY-MM-DD.md`。
- [ ] 输出当日任务状态、失败原因、跳过原因、健康门禁结果、报告路径。
- [ ] 后续可接入 ECS 同步或通知，但第一版不默认启用。

验收标准：

- [ ] 运维报告能回答“今天哪些数据更新成功、哪些失败、为什么”。
- [ ] 报告包含可点击或可定位的本地报告路径。
- [ ] 不复制 backfill 详细报告内容，只引用路径和结论。

---

## T6.3.6 风险与取舍

### T6.3.6.1 主要风险

- [ ] 编排器过早直接调用内部函数，可能扩大重构范围。
- [ ] 长任务多进程并发会触发 Tushare 限流或 SQLite 写锁。
- [ ] 状态库与旧 `.last` stamp 并存期间可能出现口径不一致。
- [ ] 过度门禁可能阻断低风险报告任务。

### T6.3.6.2 控制策略

- [ ] 第一版通过 CLI 适配器调用现有命令。
- [ ] 长任务默认总请求速率不超过 Tushare 配额，并保留配置下调空间。
- [ ] `db-health` scope 和 `fail-on` 按任务配置，不使用全局单一阻断标准。
- [ ] 迁移期保留旧日志和 stamp，只把 SQLite 作为新事实来源。

---

## T6.3.7 验收清单

- [ ] 编排器能替代 shell 内部调度判断。
- [ ] 每个任务都有可解释状态：未到时间、非交易日、已成功、运行中、阻断、失败、取消。
- [ ] 所有运行都有 run id、命令、退出码、日志路径和报告路径。
- [ ] `maintain status` 能用于日常运维巡检。
- [ ] `db-health` 前置门禁统一由编排器执行。
- [ ] 长 backfill 能统一启动、停止、恢复和查看 shard 状态。
- [ ] 现有业务命令、报告路径和数据表不被破坏。
- [ ] 编排器异常退出时不会留下永久锁。
