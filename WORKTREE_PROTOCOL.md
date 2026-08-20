# Worktree 工作协议

## 目的

本项目使用 `git worktree` 把不同性质的工作隔离到独立工作区：研究/实验的临时产物不得污染版本管理，`main` 作为全局合流点保持干净，只承载明确的代码、配置、规则与文档变更。本协议定义每种 worktree 允许改动的路径边界。创建任何 worktree 前先读本文件。

## 三类工作区

| 工作区 | 用途 | 允许改动 |
| --- | --- | --- |
| `main`（主工作区） | 全局合流点 | 所有代码、配置、规则、文档 |
| 代码集成 worktree | 单个子系统的代码开发（web、quant 集成等） | 该子系统源码与配套配置；验证后合并回 `main` |
| 研究/实验 worktree | 回测、实验、研究报告 | 只产生本地运行资产与该研究自己的产物；不改源码 |

## 路径允许矩阵

| 路径 | 代码集成 worktree | 研究/实验 worktree |
| --- | --- | --- |
| `quant/` `scripts/` `tests/` `web/` | ✅ 本子系统可改 | ❌ 禁止，改动须提级为 `main` 任务 |
| `config.yaml` `pyproject.toml` `uv.lock` `restart_web.sh` | ✅ 明确授权的集成任务可改 | ❌ 禁止 |
| `AGENTS.md` `CLAUDE.md` `WORKTREE_PROTOCOL.md` | ✅ 全局规则可改 | ❌ 禁止 |
| `docs/` `refdocs/` `knowledge/` | ⚠️ 全局文档，只在 `main` 改 | ⚠️ 只读；要改走 `main` |
| `experiments/<harness>/configs/` | ✅ | ⚠️ 只允许新增/修改该研究分支对应实验自己的配置；不得改动共享或存量配置 |
| `reports/` `logs/` `data/` `memory/` `experiments/*/outputs\|logs\|data` | ✅ 本地资产自由读写 | ✅ 本地资产自由读写（gitignore，不入 git） |

注：`data/` 下个别 git 跟踪的文件（如 `data/cache/fred/` 部分 CSV、`data/intelligence/inbox/`）属于 `main` 入库数据，任何 worktree 都不得改动；数据入版只走 `main`。

## 核心工作流：研究 → 提级 → 同步

1. 研究/实验 worktree 中做研究，产物落在本地资产区（`reports/`、`logs/`、`data/` 等）。
2. 发现必须改源码或主配置时，**立即停止研究分支操作**，把需求提级为独立 `main` 任务。
3. 在 `main`（或专门的代码集成 worktree）完成代码改动，验证并提交到 `main`。
4. 研究分支 `git merge main` 同步最新代码后继续研究。

## 入版边界

- `reports/`、`logs/`、SQLite 数据库默认是本地运行资产，不随远端同步。需要入版的治理/审计报告由 `main` 工作区按 `.gitignore` 的 `.gitkeep` 机制显式落盘。
- 研究分支只提交"该研究自己的产物"（研究笔记、实验配置）。绝不把日志、数据库、运行产物提交到研究分支。

## 回退与清理

- 研究完成或作废后，归档结论到 `reports/`，`git worktree remove` 清理研究 worktree，删除对应分支。
- 若研究分支已含应保留的产物，先合并/转移后再清理。
