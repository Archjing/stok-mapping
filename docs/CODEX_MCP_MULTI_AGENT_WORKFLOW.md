# `stok-mapping` Codex MCP 多 Agent 开发团队工作流

目标：把 `/home/zj/workspace/codex-mcp-server-demo` 中的 Codex MCP + Agents SDK team 用到 `stok-mapping`，形成可复查、可验证、可持续推进的量化研发工作流。

本工作流不替代 `AGENTS.md`、`CLAUDE.md`、`docs/DEVELOPMENT_PLAN.md` 和 `docs/STRATEGY_DEVELOPMENT_GUIDELINES.md`。这些文件仍是项目主线规则。本工作流只定义如何用多 Agent 团队执行项目任务。

---

## 1. 适用边界

适合使用 Codex MCP team 的任务：

- 策略开发：候选策略立项、实现、walk-forward、gate、报告归档。
- 数据治理：本地 SQLite 覆盖率、数据新鲜度、PIT 约束、数据源 fallback 检查。
- 报告链路：`brief daily`、`brief watchlist`、账单、OOS、execution gate、HTML 输出修复。
- 工程维护：CLI 路由、测试补齐、调度器、维护编排器、文档同步。
- 代码审查：行为回归、数据口径漂移、未来函数、成本口径、边界条件、测试缺口。

不适合直接交给 Codex MCP team 的任务：

- 自动下单、券商接口执行、实盘资金操作。
- 绕过 effectiveness gate 生成交易结论。
- 让 LLM 直接决定买卖、仓位或清仓。
- 未经用户明确确认的大规模重构、删除数据、重建长期数据库。
- 把 `yfinance`、新闻或文本事件直接升为主 ranker。

---

## 2. 启动方式

在 `codex-mcp-server-demo` 中运行 team，并把 workspace 指向 `stok-mapping`：

```bash
cd /home/zj/workspace/codex-mcp-server-demo
CODEX_MCP_CWD=/home/zj/workspace/stok-mapping \
CODEX_MCP_MODEL=gpt-5.4 \
CODEX_MCP_SANDBOX=workspace-write \
CODEX_MCP_APPROVAL_POLICY=never \
python3 main.py "在 stok-mapping 中执行：<任务描述>"
```

先做 MCP 连接 smoke test：

```bash
cd /home/zj/workspace/codex-mcp-server-demo
CODEX_MCP_CWD=/home/zj/workspace/stok-mapping python3 smoke_test.py
```

期望输出包含：

```text
codex_mcp_server=ready
workspace=/home/zj/workspace/stok-mapping
tools=codex,codex-reply
```

推荐把常用启动命令写成 shell alias，但不要把 `.env` 的 key 或 token 写入文档。

---

## 3. 团队角色

当前 `codex_team.py` 中的默认角色：

- `Team Lead`：入口 agent，负责路由任务，决定是否交给 Planner、Implementer 或 Reviewer。
- `Planner`：只做计划，不改文件。用于目标不清、范围较大、需要拆任务树的场景。
- `Codex Implementer`：通过 Codex MCP 调用 `codex` / `codex-reply` 做 repo 内检查和实现。
- `Reviewer`：通过 Codex MCP 做验证、diff 审查、测试风险和数据口径审查。

`stok-mapping` 任务中的角色使用建议：

- `Planner` 对应项目技术负责人 / 研究负责人：先确认任务是否符合当前 `DEVELOPMENT_PLAN.md` 主线。
- `Codex Implementer` 对应实现工程师：只在明确任务、边界、验收标准后改代码。
- `Reviewer` 对应量化审查 + 代码审查：重点看未来函数、PIT、成本口径、样本治理、报告一致性。

---

## 4. 标准工作流

每个非简单任务按 6 步走。

### Step 1：任务准入

先让 team 检查任务是否符合项目当前主线：

```text
请在 stok-mapping 中先做任务准入判断：
1. 读取 AGENTS.md、CLAUDE.md、README.md、docs/DEVELOPMENT_PLAN.md、docs/STRATEGY_DEVELOPMENT_GUIDELINES.md。
2. 判断下面任务是否属于当前主线，是否会违反项目边界。
3. 输出目标、范围、不做什么、验收标准和建议执行顺序。

任务：<任务描述>
```

准入必须回答：

- 是否符合“本土主因子 + 跨市场 overlay”的主线。
- 是否涉及自动交易或投资建议边界。
- 是否需要数据源 token、联网、长时间任务或重建数据库。
- 是否需要先做只读 smoke test。

### Step 2：上下文读取

Implementer 开始前必须读取最小上下文：

- `AGENTS.md`
- `CLAUDE.md`
- `README.md`
- `docs/DEVELOPMENT_PLAN.md`
- 与任务直接相关的源码、配置、报告或测试。

不要默认全仓库扫描。优先用 `rg`、目标文件读取和现有报告。

### Step 3：实现计划

对代码任务，Planner 或 Implementer 应先输出短计划：

```text
请为这个 stok-mapping 任务生成最小实现计划：
- 目标
- 需要修改的模块
- 不修改的边界
- 数据口径风险
- 验证命令
- 回退办法

任务：<任务描述>
```

计划必须保持小步推进。除非用户明确要求，不做无关重构。

### Step 4：实现

Implementer 调用 Codex MCP 时，默认传入：

```json
{
  "cwd": "/home/zj/workspace/stok-mapping",
  "sandbox": "workspace-write",
  "approval-policy": "never",
  "model": "gpt-5.4"
}
```

实现要求：

- 只修改与任务相关的文件。
- 不提交密钥、token、本地数据库。
- 不删除报告或数据资产，除非用户明确要求。
- 保持 CLI 和报告路径兼容。
- 新策略必须走 `phase0/strategies/` 注册表结构。

### Step 5：验证

验证根据任务风险分层。

文档任务：

```bash
rg -n "<关键标题或命令>" docs README.md AGENTS.md CLAUDE.md
```

轻量代码任务：

```bash
./.venv/bin/python -m pytest
```

CLI / 报告链路任务，优先跑最小相关入口：

```bash
./.venv/bin/python -m phase0.cli brief premarket
./.venv/bin/python -m phase0.cli brief watchlist
./.venv/bin/python -m phase0.cli execution-gate --config config.yaml
```

数据治理任务：

```bash
./.venv/bin/python -m phase0.cli db-health --config config.yaml
./.venv/bin/python -m phase0.cli financial-pti --config config.yaml
```

策略开发任务必须遵守 `docs/STRATEGY_DEVELOPMENT_GUIDELINES.md`：

```bash
./.venv/bin/python -m phase0.cli run --config config.yaml
./.venv/bin/python -m phase0.cli cost-sensitivity --config config.yaml --use-config-scenarios
./.venv/bin/python -m phase0.cli oos-report --config config.yaml
./.venv/bin/python -m phase0.cli overfit-diagnostic --config config.yaml
```

如果验证命令太慢或需要外部数据源，必须说明没有执行的原因和残余风险。

### Step 6：Review 与归档

Reviewer 最后做审查：

```text
请在 stok-mapping 中审查刚才的变更：
1. 找 bug、行为回归、未来函数、PIT 破坏、成本口径不一致、报告不一致和测试缺口。
2. 按严重程度列出问题，带文件路径。
3. 如果没有发现问题，明确说明剩余风险。
```

完成后同步必要文档：

- 任务主线变化：更新 `docs/DEVELOPMENT_PLAN.md`。
- 策略候选变化：更新策略说明和 change log。
- CLI / 报告行为变化：更新 `README.md` 或对应 `docs/*.md`。
- 新工具或工作流变化：更新本文件。

---

## 5. 常用任务模板

### 5.1 策略候选开发

```bash
cd /home/zj/workspace/codex-mcp-server-demo
CODEX_MCP_CWD=/home/zj/workspace/stok-mapping python3 main.py "
在 stok-mapping 中开发一个策略候选。
先读取 AGENTS.md、CLAUDE.md、docs/DEVELOPMENT_PLAN.md 和 docs/STRATEGY_DEVELOPMENT_GUIDELINES.md。
任务：<策略想法>
要求：
1. 先判断是否符合当前主线。
2. 给出最小可解释 baseline。
3. 若实现，放入 phase0/strategies/ 并走注册表。
4. 先做 smoke test，再建议 walk-forward/gate。
5. 不输出投资建议或自动下单指令。
"
```

### 5.2 数据治理修复

```bash
cd /home/zj/workspace/codex-mcp-server-demo
CODEX_MCP_CWD=/home/zj/workspace/stok-mapping python3 main.py "
在 stok-mapping 中处理数据治理任务。
任务：<数据问题>
要求：
1. 先只读检查 config.yaml、数据访问模块和现有 reports。
2. 明确是否影响 PIT、新鲜度、覆盖率或 fallback。
3. 实现最小修复。
4. 给出 db-health / financial-pti / 相关 CLI 验证命令。
"
```

### 5.3 报告链路修复

```bash
cd /home/zj/workspace/codex-mcp-server-demo
CODEX_MCP_CWD=/home/zj/workspace/stok-mapping python3 main.py "
在 stok-mapping 中修复报告链路。
任务：<报告问题>
要求：
1. 找到生成该报告的 CLI 和源码。
2. 保持 Markdown/CSV/HTML 口径一致。
3. 不改变策略计算逻辑，除非问题根因在计算层。
4. 运行最小报告生成命令或说明无法运行的原因。
"
```

### 5.4 代码审查

```bash
cd /home/zj/workspace/codex-mcp-server-demo
CODEX_MCP_CWD=/home/zj/workspace/stok-mapping python3 main.py "
请作为 Reviewer 审查 stok-mapping 当前改动。
重点检查：
1. 未来函数和 point-in-time 破坏。
2. 成本、滑点、成交价和整手约束口径。
3. report / gate / bill / brief 输出是否一致。
4. 数据源 fallback 是否会静默改变结果。
5. 缺失测试和慢验证风险。
"
```

---

## 6. Gate 与禁止事项

策略相关任务必须经过：

```text
Operational smoke test -> Strategy smoke test -> walk-forward -> gate -> OOS -> overfit diagnostic -> report archive
```

禁止：

- 只凭单次回测或单折结果晋级策略。
- 用 `qfq_current` 结果冒充严格 point-in-time 结论。
- 成本敏感性没跑就声称适合实盘。
- 让 LLM 生成买卖指令。
- 未经确认修改真实账户、券商接口或实盘执行配置。
- 把报告格式修复和策略计算改动混在一个不可审查的大变更里。

---

## 7. 推荐运行节奏

日常小任务：

```text
Team Lead -> Implementer -> Reviewer
```

策略或架构任务：

```text
Team Lead -> Planner -> Implementer -> Reviewer -> Planner 复盘
```

数据源或调度任务：

```text
Team Lead -> Planner -> Implementer -> Reviewer
```

如果 Codex MCP tool 超时：

1. 先确认 `python3 smoke_test.py` 是否仍能列出 `codex,codex-reply`。
2. 检查 `.env` 的 `OPENAI_BASE_URL` 和网关状态。
3. 把任务拆小，先让 Codex 只读检查，再执行修改。
4. 必要时提高 `CODEX_MCP_TIMEOUT_SECONDS`。

---

## 8. 最小验收标准

一次 multi-agent 开发任务完成时，最终输出至少包含：

- 做了什么。
- 改了哪些关键文件。
- 跑了哪些验证命令。
- 验证结果。
- 没跑的验证和原因。
- 剩余风险。
- 下一步最值得做什么。
