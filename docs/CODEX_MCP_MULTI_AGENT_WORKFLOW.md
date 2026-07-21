# `stok-mapping` Codex MCP 多 Agent 开发团队工作流

目标：把 `/home/zj/workspace/codex-harness-runner` 中的 Codex MCP + Agents SDK team 用到 `stok-mapping`，形成可复查、可验证、可持续推进的量化研发工作流。

本工作流不替代 `AGENTS.md`、`CLAUDE.md`、`docs/DEVELOPMENT_PLAN.md` 和 `docs/STRATEGY_DEVELOPMENT_GUIDELINES.md`。这些文件仍是项目主线规则。本工作流只定义如何用多 Agent 团队执行项目任务。

状态冲突时，以 `docs/DEVELOPMENT_PLAN.md` 为准。Codex MCP、Agents SDK、Harness 与其他 agent workflow 仅代表开发/验证/复核能力，不代表任何策略已经通过准入、可以进入实盘模拟或可以绕过人工 review。

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
- 把 workflow 跑通、报告生成成功或 agent review 通过，解释为策略准入通过。
- 让 LLM 直接决定买卖、仓位或清仓。
- 未经用户明确确认的大规模重构、删除数据、重建长期数据库。
- 把 `yfinance`、新闻或文本事件直接升为主 ranker。

---

## 2. 启动方式

在 `codex-harness-runner` 中运行 team，并把 workspace 指向 `stok-mapping`：

```bash
cd /home/zj/workspace/codex-harness-runner
CODEX_MCP_CWD=/home/zj/workspace/stok-mapping \
CODEX_MCP_MODEL=gpt-5.4 \
CODEX_MCP_SANDBOX=workspace-write \
CODEX_MCP_APPROVAL_POLICY=never \
python3 main.py "在 stok-mapping 中执行：<任务描述>"
```

先做 MCP 连接 smoke test：

```bash
cd /home/zj/workspace/codex-harness-runner
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
- `Quant Research Expert`：股票量化投资研究专家，负责策略假设、因子证据、回测口径、`qfq_asof` / PIT、成本、过拟合、行业集中、Tushare 数据口径和 admission 边界审查。
- `Codex Implementer`：通过 Codex MCP 调用 `codex` / `codex-reply` 做 repo 内检查和实现。
- `Reviewer`：通过 Codex MCP 做验证、diff 审查、测试风险和数据口径审查。

`stok-mapping` 任务中的角色使用建议：

- `Planner` 对应项目技术负责人 / 研究负责人：先确认任务是否符合当前 `DEVELOPMENT_PLAN.md` 主线。
- `Quant Research Expert` 对应股票量化投资专家：做研究第二意见和策略治理审查。遇到量化策略、回测、组合构造或风险指标任务，必须使用或显式套用 `quant-analyst` skill；遇到 A 股数据源、Tushare 字段、权限、覆盖率和源审计问题，必须使用或显式套用 `tushare` skill；解释策略实验、回测结果或 admission 结论时，必须使用或显式套用“策略实验解读”skill。
- `Codex Implementer` 对应实现工程师：只在明确任务、边界、验收标准后改代码。
- `Reviewer` 对应量化审查 + 代码审查：重点看未来函数、PIT、成本口径、样本治理、报告一致性。

`Quant Research Expert` 不提供投资建议，不生成买卖指令，不替代 `strategy-admission`、`execution-gate` 或人工 review。若 Harness 环境无法直接调用 Codex skills，该角色必须在输出中说明适用的 skill，并按项目上下文中的对应规则执行分析。

---

## 4. 标准工作流

每个非简单任务按 7 步走。

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

### Step 7：用户可读简报与会话归档

每轮 Harness 结束后，除了工程日志、CSV、Markdown 研究报告，还必须给用户一份“看得懂、能决策”的简报。简报不是替代原始报告，而是把原始报告翻译成清楚的结论、证据和下一步。

默认产物：

- 路径：`reports/strategy_governance/YYYY-MM-DD/<initiative>/briefings/`
- 格式：Markdown，文件名建议 `iter_NN__<topic>_brief.md`
- 模板：`docs/templates/HARNESS_ITERATION_BRIEF_TEMPLATE.md`

上下文压缩前还必须做一次会话增量归档。归档不是逐字堆聊天记录，而是保留项目后续复盘真正需要的内容：

- 路径：`memory/session_archive/<topic>/`
- 文件名建议：`YYYY-MM-DD__session_incremental_archive_<topic_or_iter>.md`
- 归档内容：用户新增标准、关键决策、执行命令、变更文件、生成报告、测试结果、未完成事项和下一步。
- 如果出现策略解释、方案研判、数据源评估、架构边界或开发标准，应保留原意和关键表述。
- 噪音内容、重复状态更新和大段工具输出只做摘要，不原样归档。
- 若上下文窗口余量紧张，优先写归档，再继续长任务或等待子 Agent。
- `reports/` 只存程序报告和 curated governance report；`logs/` 只存机器运行日志和调度状态，不再放人工会话归档。

简报必须包含：

1. **一句话结论**：用平实中文说明本轮到底发现了什么。
2. **本轮做了什么**：只写和用户决策相关的动作，不堆内部过程。
3. **关键数字表**：把收益、超额、折数、通过/拒绝、风险项写成表格。
4. **图示**：至少给出一个 Mermaid 流程图、因果图、对比图或可读表格；必要时升级为 HTML / PPTX / 动画。
5. **能做和不能做**：明确是否改变 admission、是否允许 paper review、是否仍是 research-only。
6. **下一步**：写成可执行动作，不写抽象口号。
7. **原始证据索引**：列出 CSV、报告、命令日志路径，方便回查。
8. **会话归档索引**：列出本轮增量归档路径，便于上下文压缩后恢复。

表达要求：

- 先说人话，再给证据，最后给下一步。
- 数字必须解释含义。例如“超额 -6.35%”要说明是“策略赚钱，但没跑赢强沪深300”。
- 不用只在工程内部才容易理解的缩写；如果必须使用，第一次出现时解释。
- 不把 research-only 结果写成可交易结论。
- 工程细节放到附录或证据索引，不放在主结论里。

格式分层：

| 等级 | 使用场景 | 产物 |
| ---- | -------- | ---- |
| A | 默认每轮 Harness | Markdown 简报，含表格和 Mermaid 图 |
| B | 多轮阶段复盘、用户需要展示 | HTML slide deck 或静态网页 |
| C | 重要决策会、复杂策略演示 | PPTX / GIF / 短动画，可参考 `~/workspace/brainstorm/modules/` 中的展示工具 |

`~/workspace/brainstorm/modules/` 中的模块只能作为参考资料或原型来源，不能直接照搬为本项目依赖。尤其是 `marklogseq` 这类仍在孵化中的模块，使用时必须遵守：

- 先读 README 和相关源码，确认能力边界和局限。
- 只借鉴明确有用的函数、类、数据结构或展示思路。
- 移植前按 `stok-mapping` 的目录、测试、报告和数据口径重新封装。
- 不把未成熟模块加入正式运行链路，除非经过本项目内测试和文档验收。

---

## 5. 常用任务模板

### 5.1 策略候选开发

```bash
cd /home/zj/workspace/codex-harness-runner
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
cd /home/zj/workspace/codex-harness-runner
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
cd /home/zj/workspace/codex-harness-runner
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
cd /home/zj/workspace/codex-harness-runner
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

如果直接在 `stok-mapping` 中运行 Agents SDK heredoc、README 示例或临时脚本，必须先核对仓库实际文件是否存在，再决定是否可以照文档执行。

当前仓库不存在 `scripts/agents_sdk_bootstrap.py` 和 `scripts/agents_sdk_readme_smoke.py`，因此不能按依赖这些脚本的说明直接执行。遇到这类说明时，以仓库当前可见文件、`pyproject.toml`、锁文件和实际环境配置为准，不要假设文档中提到的辅助脚本已经落库。

如需做 smoke test，应优先使用仓库中已存在的最小验证方式，例如：

- 先确认依赖环境可以导入目标 SDK 或模块。
- 再用仓库中真实存在的入口、命令或最小 heredoc 进行验证。
- 如果某个 README 或外部示例要求额外 bootstrap/辅助脚本，而仓库内没有对应文件，则应把该命令视为可选外部示例，而不是项目内可直接执行步骤。

---

## 8. 最小验收标准

一次 multi-agent 开发任务完成时，最终输出至少包含：

- 用户可读简报路径。
- 一句话结论。
- 做了什么。
- 改了哪些关键文件。
- 跑了哪些验证命令。
- 验证结果。
- 没跑的验证和原因。
- 剩余风险。
- 下一步最值得做什么。
