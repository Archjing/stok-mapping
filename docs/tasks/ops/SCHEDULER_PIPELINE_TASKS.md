# T6.1｜统一调度器与后台 Pipeline 任务清单

> 父级任务域：`T6` 运维调度与后台任务。  
> 当前目标：用一个系统 cron 入口驱动项目内统一调度器，由项目脚本负责多市场数据获取、日报生成、失败重试、交易日历判断、日志和锁。

## T6.1.1 当前已完成基线

- [x] 新增统一项目调度器：`scripts/run_project_scheduler.sh`
- [x] 将系统 crontab 收敛为一个项目入口：`* * * * * bash scripts/run_project_scheduler.sh`
- [x] `scripts/run_project_scheduler.sh` 已降级为 wrapper：加载 `.env`、预热 `maintenance.sqlite` schema 后调用 `phase0.cli maintain tick`
- [x] 接入 `brief watchlist` 阶段试用观察池 pipeline
- [x] 接入 A 股本地历史库更新：`phase0.cli update-history`
- [x] 接入港股历史库更新：`phase0.cli update-hk-market-history`
- [x] 接入 US market 历史库更新：`phase0.cli update-us-market-history`
- [x] 接入 A 股季度财务因子更新：`phase0.cli update-financials`
- [x] 为每个任务提供独立日志文件
- [x] 为每个任务提供简单锁目录，避免同一任务并发重复启动
- [x] 成功后写入每日 stamp，避免同一任务同一天重复执行
- [x] `07:20` 任务已切换到 `phase0.cli brief watchlist`
- [x] 阶段试用观察池已固定生成 `reports/watchlist_today/index.html`
- [x] 阶段试用观察池已内置 ECS rsync 同步，远端默认 `BRIEF_SYNC_REMOTE_DIR=/brief/`
- [x] `scripts/run_daily_brief_pipeline.sh` 已改为兼容调用 `brief watchlist`
- [x] 当前 `brief` 命令路由已整理为 `brief daily`、`brief watchlist`、`brief premarket`、`brief account-bill`

## T6.1.2 已知问题：交易日判断仍过于粗糙

### T6.1.2.1 当前实现

- [x] 当前调度入口已由 shell weekday 判断迁移到 `maintain tick`。
- [x] A 股任务已读取 `data/manual_history/a_share_history.sqlite` 的 `trading_calendar` 表。
- [x] HK / US 任务当前使用 weekday fallback，并在 `maintain tick` 输出中明确记录 fallback reason。

### T6.1.2.2 风险

- [x] A 股法定节假日、春节、国庆等休市日触发风险已由本地 `trading_calendar` 降低。
- [ ] 港股休市日与 A 股不同，当前没有独立判断。
- [ ] 美股休市日与 A 股 / 港股不同，当前没有独立判断。
- [ ] 港股 / 美股周六补交易、特殊休市、半日市等场景仍依赖 fallback，无法完全正确处理。

### T6.1.2.3 后续开发项

- [x] `T6.1.2.3.1` 为 A 股任务读取 `data/manual_history/a_share_history.sqlite` 的 `trading_calendar` 表。
- [ ] `T6.1.2.3.2` 为港股任务接入港股交易日历或以数据源最新交易日判断。
- [ ] `T6.1.2.3.3` 为 US market 任务接入美股交易日历或以数据源最新交易日判断。
- [x] `T6.1.2.3.4` 将 `brief watchlist` / `brief daily` 的触发条件与 A 股下一个盘前检查日绑定。
- [x] `T6.1.2.3.5` 在日志里记录任务跳过原因：非交易日、已完成、锁占用、未到时间窗口。

## T6.1.3 已知问题：失败重试策略仍不完整

### T6.1.3.1 当前实现

- [x] 当前任务成功后写入 `logs/scheduler/<task_name>.last`，当天不再执行。
- [x] 当前任务失败后不会写成功 stamp。
- [x] 当前触发条件已从单点精确分钟迁移为 `maintain tick` 的 schedule + retry window。
- [x] 失败任务可在 retry window 内按重试间隔继续尝试，不再只依赖精确分钟触发。

### T6.1.3.2 风险

- [x] 网络短暂异常导致当天任务缺失的风险已由 retry window 和 state 文件降低。
- [x] 数据源限频、DNS、代理短时失败后可在窗口内重试。
- [ ] 日报任务如果多次失败或超过窗口，仍可能错过 `07:30` 前的简报产出。
- [ ] 多市场数据更新如果某个时间点失败，后续策略可能继续使用旧数据。

### T6.1.3.3 后续开发项

- [x] `T6.1.3.3.1` 为每个任务配置运行窗口，例如 `07:20-07:40`、`16:20-17:00`。
- [x] `T6.1.3.3.2` 为每个任务配置最大重试次数，例如 `3` 次。
- [x] `T6.1.3.3.3` 为每个任务配置重试间隔，例如 `5` 分钟。
- [x] `T6.1.3.3.4` 将失败次数、最后失败时间、最后错误摘要写入 `logs/scheduler/<task_name>.state`。
- [x] `T6.1.3.3.5` 成功后清理失败状态并写入成功 stamp。
- [x] `T6.1.3.3.6` 超过最大重试次数后写入明确告警日志。

## T6.1.4 后续扩展方向

- [ ] `T6.1.4.1` 将任务配置从 shell hardcode 迁移到 `config.yaml` 或独立 `scheduler.yaml`。
- [x] `T6.1.4.2` 增加状态查询入口；当前实现为 `phase0.cli maintain status`，展示最近运行、失败次数、最后日志路径。
- [x] `T6.1.4.3` 增加手动触发入口；当前实现为 `phase0.cli maintain run --task tushare_financial_backfill`，短任务仍由 `maintain tick` 驱动。
- [ ] `T6.1.4.4` 为 OpenClaw / Cloe 增加日报完成后的摘要通知入口。
- [ ] `T6.1.4.5` 为未来新闻源、宏观源、策略重评估、模拟账户结算预留任务槽。
