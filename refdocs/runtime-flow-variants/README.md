# 项目最终运行形态图 · 样式版本

上级说明：

- [`refdocs/PROJECT_FINAL_RUNTIME_FLOW.md`](../PROJECT_FINAL_RUNTIME_FLOW.md)

本目录新增三种参考样式版本：

| 版本 | 参考方向 | 文件 |
| --- | --- | --- |
| 01 | Canva Architecture Diagram：演示型分层架构蓝图 | `01-canva-architecture/runtime-flow-canva.svg` |
| 02 | Miro Architecture Workflow：白板式泳道流程图 | `02-miro-workflow/runtime-flow-miro.svg` |
| 05 | FinFlow Finance Dashboard：金融驾驶舱式运行看板 | `05-finflow-dashboard/runtime-flow-finflow.svg` |

## 状态图例

- 绿色：已完成 / 已验证。
- 琥珀色：最小接入、过渡状态或仍需补齐稳定闭环。
- 灰色虚线：尚未启动或待开发。

## 表达口径

三版都遵循同一项目边界：

- A 股本土因子是主选股与主验证链路。
- FRED、Tiingo、美股/ETF、港股、A50、CNH 等跨市场输入只做风险/情绪 overlay。
- LLM/Agent 只做摘要、审查、消息通道和跨工具编排，不进入主信号层。
- 所有输出是观察池、风险暴露、情景推演和模拟验证，不构成交易指令。
