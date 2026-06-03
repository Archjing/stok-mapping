# Claude Agent Workflow

目标：把 Claude 作为 `stok-mapping` 的外部辅助 agent，而不是主策略引擎。

当前拆分为两个角色：

- `Claude_Analyst_agent`：量化研究分析助理，负责研究摘要、风险提示、样本外稳健性评估和验证建议。
- `Claude_Code_Reviewer_agent`：编程专家与代码质量审查助理，负责审查 bug、行为回归风险、数据一致性、边界条件和测试缺口。

## 配置位置

所有 Codex 侧 Claude provider 配置放在 `.codex/`：

- `.codex/claude_agent_config.json`: 旧版兼容配置，语义等同于 `Claude_Analyst_agent`。
- `.codex/claude_analyst_agent_config.json`: `Claude_Analyst_agent` 角色配置。
- `.codex/claude_code_reviewer_agent_config.json`: `Claude_Code_Reviewer_agent` 角色配置。
- `.codex/claude_agent.local.json`: 本地密钥/覆盖配置，已加入 `.gitignore`。
- `.codex/claude_agent.py`: 通用 Claude 调用器。
- `.codex/run_claude_agent.sh`: 旧版兼容入口，转发到 `Claude_Analyst_agent`。
- `.codex/run_claude_analyst_agent.sh`: 固定使用当前项目 Python 环境调用 `Claude_Analyst_agent`。
- `.codex/run_claude_code_reviewer_agent.sh`: 固定使用当前项目 Python 环境调用 `Claude_Code_Reviewer_agent`。
- `.codex/mcp.example.json`: MCP 配置模板，不影响项目根目录 `.mcp.json`。

## 本地 API 配置

默认读取 Claude 全局配置：

```text
~/.claude/settings.json
```

脚本会读取其中的 `env` 字段，例如：

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://sgp.tokensea.top",
    "ANTHROPIC_AUTH_TOKEN": "...",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-opus-4-8[1M]"
  }
}
```

`ANTHROPIC_BASE_URL` 是 API 基础地址，脚本会自动补齐 `/v1/messages`。`ANTHROPIC_AUTH_TOKEN` 使用 `Authorization: Bearer ...` 认证头。默认 Opus 模型从 `ANTHROPIC_DEFAULT_OPUS_MODEL` 读取；若该变量不存在，则回退到 agent config 中的 `model`。

项目根目录 `.env` 仍可作为项目级补充配置：

```bash
ANTHROPIC_BASE_URL=https://sgp.tokensea.top
ANTHROPIC_AUTH_TOKEN=sk-...
```

`.codex/claude_agent.local.json` 只建议用于本地非密钥覆盖配置，不建议写入 token。

默认输出语言为简体中文；即使上下文文件包含英文，Claude agent 也应使用中文总结和解释，除非用户明确要求其他语言。

## 常用命令

### Claude_Analyst_agent

只生成 prompt 预览，不请求外部 API：

```bash
bash .codex/run_claude_analyst_agent.sh --dry-run
```

调用 Claude API 生成研究摘要：

```bash
bash .codex/run_claude_analyst_agent.sh
```

指定任务：

```bash
bash .codex/run_claude_analyst_agent.sh \
  --task "基于当前报告生成 07:30 盘前研究摘要，重点说明风险、失效条件和下一步验证。"
```

指定上下文文件：

```bash
bash .codex/run_claude_analyst_agent.sh \
  --include reports/phase0_effectiveness_report.md \
  --include reports/phase0_walk_forward_report.md
```

旧命令 `bash .codex/run_claude_agent.sh` 保留，等同于调用 `Claude_Analyst_agent`。

### Claude_Code_Reviewer_agent

只生成 prompt 预览：

```bash
bash .codex/run_claude_code_reviewer_agent.sh --dry-run
```

调用 Claude API 做代码质量审查：

```bash
bash .codex/run_claude_code_reviewer_agent.sh
```

指定审查任务和文件：

```bash
bash .codex/run_claude_code_reviewer_agent.sh \
  --task "审查 brief watchlist 与 simulated account 相关代码，重点找数据口径不一致和账单生成风险。" \
  --include phase0/cli.py \
  --include phase0/accounts.py \
  --include phase0/reporting.py
```

## 权限边界

Claude agent 当前只允许：

- 阅读已落库报告和配置。
- 总结研究结论。
- 提醒数据质量风险。
- 提出待验证问题。
- 审查用户显式提供的项目代码上下文。

Claude agent 当前不允许：

- 直接生成买卖指令。
- 擅自修改策略参数。
- 跳过 effectiveness gate。
- 连接券商接口或自动下单。
- 直接修改项目文件。

## MCP 协同

MCP 适合给外部 agent 暴露只读数据源、报告读取器或低风险工具。当前建议把 MCP 配置模板放在 `.codex/mcp.example.json`，避免把 Claude Code、Codex 和其他 agent 工具的项目级配置混在一起。

涉及写库、跑重任务、改配置和下单的能力应继续走人工确认。
