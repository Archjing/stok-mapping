# TUI 可行性评估笔记

日期：2026-06-09

## 结论

将本项目开发成一个在终端里运行的 TUI 软件，做一个“可用的项目 TUI”难度不大；做一个“覆盖全系统、体验优秀、可长期维护的研究工作台 TUI”则是中等偏大的工程。

当前项目很适合做 TUI，因为已经具备较好的命令化和结构化输出基础。

## 当前基础

- CLI 已比较完整：`db-health`、`maintain status/run/stop/resume/supervise`、`strategy-admission`、`factor-effectiveness`、backfill 等都能命令化。
- 数据状态有 SQLite、Markdown 报告和 CSV 报表。
- 维护编排器 V1 已有状态库、run id、shard 状态、日志路径和报告路径。
- 策略准入报告已经结构化输出 CSV / Markdown。

因此，TUI 第一版不需要重写核心业务，应作为“壳层 / 控制台 / 状态面板”。

## 难度分层

| 范围 | 难度 | 预估 |
| --- | --- | --- |
| 只读状态面板：数据库健康、维护任务、最近报告 | 低 | 1-2 天 |
| 可操作 TUI：运行 db-health、查看日志、启动/停止 backfill | 中 | 3-5 天 |
| 策略研究 TUI：选择 preset、跑 admission、浏览结果矩阵 | 中 | 5-8 天 |
| 全系统 TUI：维护、数据、策略、报告、关注个股、账户、情报统一入口 | 中高 | 2-4 周 |
| 接近 Notion / Obsidian 体验的桌面级交互 | 高 | 1-2 月以上 |

## 推荐路线

第一阶段不要做“全系统 TUI”。

推荐先做 `System Orchestrator TUI V1`：

- `Status`：显示 db-health、maintenance status、最新策略报告。
- `Maintenance`：查看 shard、日志、run id，支持 stop/resume。
- `Strategy`：选择 strategy-set / preset，生成 admission 命令，不一定立刻后台跑。
- `Reports`：列出最新 Markdown / CSV 报告路径，支持终端内预览摘要。
- `Guardrails`：高风险操作二次确认，例如 stop、resume、大规模 backfill。

## 主要风险

- 长任务交互复杂：backfill 多进程、日志刷新、中断恢复需要清晰状态机。
- TUI 不应绕过 CLI：否则会形成两套业务入口，维护成本上升。
- 终端展示复杂表格有限：策略矩阵和报告可以摘要展示，详细分析仍打开 Markdown / HTML。
- 键盘交互要克制：先保证清晰、稳定，不追求炫技。

## 判断

值得做，但应定位为“本地运维与研究控制台”，不是一开始就做完整桌面应用。

第一版可以较快落地，并且与现有架构兼容。
