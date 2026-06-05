# 本项目 AI 能力探索与规划评估

> 日期：2026-06-05  
> 性质：短报告原文归档  
> 状态：参考资料，不直接落入开发计划

---

当前项目对 AI 的探索已经有清晰边界：**AI 只做研究辅助、解释、审查、摘要、工具编排入口，不进入主信号链路，不生成交易指令。**

**已落地能力**
- DeepSeek MCP：用于报告总结、第二意见、策略审查、信号解释。见 [deepseek_agent_mcp.py](/home/zj/workspace/stok-mapping/scripts/deepseek_agent_mcp.py)
- Cloe / OpenClaw：用于外部 agent 调度、研究摘要、风险提示、盘前观察池解释。见 [AGENT_AND_LOCAL_LLM_WORKFLOW.md](/home/zj/workspace/stok-mapping/refdocs/AGENT_AND_LOCAL_LLM_WORKFLOW.md)
- 项目技能：已有 `tushare` 自然语言数据研究 skill、策略实验解读 skill。见 [.agents/skills](/home/zj/workspace/stok-mapping/.agents/skills)
- README 已明确边界：Agent 不进入主信号链路，不绕过 gate，不生成交易指令。见 [README.md](/home/zj/workspace/stok-mapping/README.md)

**已有规划**
- 本地 LLM：规划以 `Qwen3 + vLLM` 做主研究代理，DeepSeek 做审查器。
- 多代理分工：研究代理、工程代理、风险审查器。
- 工具接入：只暴露有限工具，如读报告、读配置、运行受控 CLI、比较候选策略。
- 输出协议：要求结构化 JSON/Markdown，带风险、证据、下一步，不允许自由发挥荐股。
- Tushare MCP：定位为少量补查和解释增强，不替代正式批处理。

**评估**
方向是正确的。项目没有走“LLM 直接选股/调仓”的高风险路线，而是把 AI 放在解释层、审查层和交互层，这符合量化系统的可验证性要求。

主要优势：
- 边界清楚：AI 不进 alpha 主链路。
- 可审计：正式结论仍来自 CLI、SQLite、报告和 gate。
- 适配当前形态：项目已经有大量 Markdown/CSV/HTML 报告，适合 AI 摘要和问答。
- 适合未来 TUI / 桌面 UI：AI 可作为 command assistant、报告解释器、风险秘书。

主要不足：
- AI 工具还偏“旁路辅助”，没有统一接入 `System Orchestrator`。
- 没有标准化 AI 输入包，例如固定的 report bundle / context bundle。
- 没有 AI 输出落库或审计表，复盘能力弱。
- 本地 LLM 规划较完整，但还没看到真正生产化接入。
- 目前 AI 对数据质量、PIT、未来函数风险的约束主要靠 prompt 和文档，不如代码门禁可靠。

**建议路线**
1. 先做 `AI Context Bundle`：把一次分析需要的报告、数据日期、策略版本、gate 状态打包成固定 JSON。
2. 再做 `ai-review` CLI：只读输入包，输出结构化审查报告。
3. 接入 `System Orchestrator`：AI 只通过统一编排器拿状态和报告。
4. 最后进 TUI：AI 做报告解释、风险摘要、命令建议，不直接执行危险动作。

一句话判断：**AI 方向值得继续，但应保持“可审计研究助手”定位，不升级成“交易决策者”。**
