# deepseekAgentMcp

项目内本地 MCP server，负责把 DeepSeek 在线模型包装成标准工具，供 Claude 在 `stok-mapping` 项目里调用。

## 文件位置

- Server 脚本：`scripts/deepseek_agent_mcp.py`
- 项目 MCP 配置：`.mcp.json`

## 环境变量

通过 `.claude/settings.local.json` 注入：

- `DEEPSEEK_BASE_URL`
- `DEEPSEEK_API_KEY`
- 可选：`DEEPSEEK_MODEL`
- 可选：`DEEPSEEK_TIMEOUT`

## 当前暴露的工具

### 1. `deepseek_second_opinion`
用于对报告、候选策略、研究结论给“第二意见”。

输入：
- `context`
- `question`

返回 JSON：
- `summary`
- `risks`
- `contradictions`
- `next_actions`

### 2. `deepseek_report_summarize`
用于把 Markdown 报告压缩成结构化摘要。

输入：
- `report_text`
- `focus`（可选）

返回 JSON：
- `summary`
- `key_metrics`
- `risk_flags`
- `next_actions`

### 3. `deepseek_strategy_review`
用于审查某个候选策略。

输入：
- `candidate_name`
- `metrics`
- `logic`
- `constraints`（可选）

返回 JSON：
- `candidate`
- `summary`
- `strengths`
- `weaknesses`
- `gate_risks`
- `next_actions`

### 4. `deepseek_signal_explain`
用于把单只标的/观察池候选转成研究语言说明。

输入：
- `symbol`
- `context`

返回 JSON：
- `symbol`
- `summary`
- `risk_flags`
- `invalid_conditions`
- `note`

## 设计边界

这个 MCP server 只负责：
- 总结
- 审查
- 解释
- 第二意见

它**不负责**：
- 直接生成交易指令
- 直接替代 `phase0.cli`
- 直接作为正式批处理回测链路

## 当前推荐用法

### 场景 A：报告总结
- 读取 `reports/phase0_walk_forward_report.md`
- 调 `deepseek_report_summarize`
- 输出压缩版盘前摘要

### 场景 B：候选策略审查
- 把候选策略名称、指标、逻辑描述传给 `deepseek_strategy_review`
- 获取风险点和下一步建议

### 场景 C：第二意见
- 当 Claude 本地主代理已经给出结论后
- 调 `deepseek_second_opinion`
- 让 DeepSeek 从反方角度补充矛盾与风险

## 注意事项

- 本地会话重启后，Claude 才会重新读取 `.mcp.json`
- 若 `DEEPSEEK_API_KEY` 未配置，server 工具调用会报配置错误
- 输出默认要求中文且不出现直接交易指令措辞
