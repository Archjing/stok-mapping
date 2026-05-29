# Claude Agent Workflow

目标：把 Claude 作为 `stok-mapping` 的外部研究 agent，而不是主策略引擎。

## 配置位置

所有 Codex 侧 Claude provider 配置放在 `.codex/`：

- `.codex/claude_agent_config.json`: 可提交的无密钥 provider 配置。
- `.codex/claude_agent.local.json`: 本地密钥/覆盖配置，已加入 `.gitignore`。
- `.codex/claude_agent.py`: 通过 Anthropic Messages API 调用 Claude。
- `.codex/run_claude_agent.sh`: 固定使用当前项目 Python 环境的包装脚本。
- `.codex/mcp.example.json`: MCP 配置模板，不影响项目根目录 `.mcp.json`。

## 本地密钥配置

推荐继续使用项目根目录 `.env`：

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

也可以使用 `.codex/claude_agent.local.json`：

```json
{
  "env": {
    "ANTHROPIC_API_KEY": "sk-ant-..."
  }
}
```

## 常用命令

只生成 prompt 预览，不请求外部 API：

```bash
bash .codex/run_claude_agent.sh --dry-run
```

调用 Claude API 生成研究摘要：

```bash
bash .codex/run_claude_agent.sh
```

指定任务：

```bash
bash .codex/run_claude_agent.sh \
  --task "基于当前报告生成 07:30 盘前研究摘要，重点说明风险、失效条件和下一步验证。"
```

指定上下文文件：

```bash
bash .codex/run_claude_agent.sh \
  --include reports/phase0_effectiveness_report.md \
  --include reports/phase0_walk_forward_report.md
```

## 权限边界

Claude agent 当前只允许：

- 阅读已落库报告和配置。
- 总结研究结论。
- 提醒数据质量风险。
- 提出待验证问题。

Claude agent 当前不允许：

- 直接生成买卖指令。
- 擅自修改策略参数。
- 跳过 effectiveness gate。
- 连接券商接口或自动下单。

## MCP 协同

MCP 适合给外部 agent 暴露只读数据源、报告读取器或低风险工具。当前建议把 MCP 配置模板放在 `.codex/mcp.example.json`，避免把 Claude Code、Codex 和其他 agent 工具的项目级配置混在一起。

涉及写库、跑重任务、改配置和下单的能力应继续走人工确认。
