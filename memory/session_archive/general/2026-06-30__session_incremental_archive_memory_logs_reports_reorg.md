# 2026-06-30 会话增量归档：memory / logs / reports 目录治理

## 范围

- 本轮按用户要求，依据前一轮简报交付和模拟账户账单同步成果，更新项目文档，并整理会话记录存档位置。
- 重点是目录边界和可维护性，不改变策略逻辑、数据源逻辑或账户撮合逻辑。

## 关键决策

- `reports/` 只保留程序报告和可展示/可复盘的业务产物：Markdown、HTML、CSV、dashboard 可索引报告和 curated strategy governance report。
- `logs/` 只保留机器运行日志、调度状态、锁文件和 pipeline stdout/stderr。
- `memory/` 作为人工项目记忆目录，存放会话增量归档、关键决策、专题判断和历史开发计划快照。
- 旧规则中把会话归档放到 `reports/strategy_governance/.../session_archive/` 是错误边界，已迁移到 `memory/session_archive/`。

## 迁移结果

- 策略研发 Harness 会话归档迁移到：
  - `memory/session_archive/strategy_governance/`
- 通用会话、专题判断和原始会话片段迁移到：
  - `memory/session_archive/general/`
- 开发计划历史快照迁移到：
  - `memory/development_plan_history/`
- `logs/` 下 Markdown/TXT 仅保留：
  - `logs/README.md`
- `reports/**/session_archive/` 已清空，不再作为会话归档位置。

## 文档更新

- 新增 `memory/README.md`，定义 memory / logs / reports 的职责边界。
- 重写 `logs/README.md`，明确 logs 只存机器运行日志和调度状态。
- 更新 `reports/README.md`，明确 reports 不存会话归档。
- 更新 `docs/CODEX_MCP_MULTI_AGENT_WORKFLOW.md`，将上下文压缩前会话归档路径改为 `memory/session_archive/<topic>/`。
- 更新 `README.md`、`docs/DEVELOPMENT_PLAN.md`、`docs/PROJECT_ARCHITECTURE_OVERVIEW.md`、周任务清单和调度任务文档，补充：
  - `share.spidermanread.men/brief/`
  - `share.spidermanread.men/account-bill/`
  - account-bill latest 镜像与远端同步
  - memory / logs / reports 目录边界
- 更新 `.gitignore`，允许版本化 `memory/**/*.md`、`memory/**/*.txt` 和 `logs/README.md`，继续忽略机器运行日志。

## 验证

- `./.venv/bin/python -m pytest tests/test_cli_delivery_commands.py -q`
  - 结果：`6 passed, 1 warning`
- 搜索确认：
  - `reports/**/session_archive` 无剩余文件。
  - `logs/` 下 Markdown/TXT 只剩 `logs/README.md`。
  - `memory/session_archive` 有 34 份会话/专题记忆。
  - `memory/development_plan_history` 有 24 份历史计划快照。

## 未完成事项

- 当前工作树仍有较多与本轮无关的运行产物、数据库和历史 reports 脏状态，未在本轮清理或提交。
- `docs/PYTHON_ARCHITECTURE_CONSOLIDATION_PLAN.md` 中仍可能有历史语境下的旧部署术语，但不属于当前运行规则；本轮只修正当前可误导的 watchlist mirror 表述。
