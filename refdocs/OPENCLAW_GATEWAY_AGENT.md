# Cloe Agent 接入说明

> 目标：把 Cloe 作为外部 agent / 调度入口，用于研究摘要、资料检索、报告审查和消息通道集成。  
> 技术底座：Cloe 当前通过 OpenClaw Gateway 与 `acpx openclaw` 调用。  
> 边界：不进入主信号链路，不直接生成交易指令，不绕过 `phase0` effectiveness gate。

## 一、当前本机状态

- OpenClaw CLI 已安装：`OpenClaw 2026.5.26`
- Gateway 配置：
  - `gateway.mode = local`
  - `gateway.port = 18789`
  - `gateway.bind = loopback`
- 当前环境中 systemd user 不可用，因此不建议先用后台服务方式启动。
- 推荐当前项目使用前台 loopback 方式，避免把 Gateway 暴露到局域网。

## 二、推荐启动方式

前台启动本地 Gateway：

```bash
openclaw gateway run --bind loopback --port 18789
```

如果已有旧进程占用端口，可手工确认后再使用：

```bash
openclaw gateway run --bind loopback --port 18789 --force
```

检查状态：

```bash
openclaw gateway status
openclaw gateway health
```

Dashboard：

```text
http://127.0.0.1:18789/
```

## 三、直接运行 agent 回合

不依赖后台 Gateway，使用本地 embedded agent：

```bash
openclaw agent --local --message "Summarize reports/phase0_strategy_change_log.md and list next actions."
```

通过 Gateway 跑 agent：

```bash
openclaw agent --agent stok-mapping --message "Review current Phase 0 report and identify risk flags."
```

## 四、Codex 内通过 acpx 调用 Cloe

当前推荐用 `acpx` 管理 Cloe 会话。会话名统一使用：

```text
cloe-bridge
```

确认或创建会话：

```bash
acpx openclaw sessions ensure --name cloe-bridge
```

注意：上面这条命令只负责确认会话存在，不会真正派发任务。真正让 Cloe 工作时使用：

```bash
acpx openclaw -s cloe-bridge "请审查 reports/phase0_effectiveness_report.md，并列出主要风险。"
```

项目内提供了封装脚本，会自动先 `ensure` 再发送任务：

```bash
scripts/cloe_agent.sh "请审查 README.md 里的 Agent 与 MCP 说明是否清晰。"
```

可选环境变量：

```bash
CLOE_ACPX_SESSION=cloe-bridge
CLOE_ACPX_TIMEOUT=900
CLOE_ACPX_FORMAT=text
```

在 Codex 会话中，可以直接要求：

```text
调用 Cloe：请检查当前开发计划和周任务清单是否一致。
```

Codex 侧应优先通过 `scripts/cloe_agent.sh` 调用，保持会话、工作目录和输出格式一致。`scripts/openclaw_agent.sh` 仅作为旧命令兼容入口保留。

## 五、与本项目的职责边界

Cloe 可以做：

- 报告摘要
- 第二意见
- 文献/资料检索后的归纳
- 任务清单整理
- 盘前观察池文本解释
- 外部消息通道转发

Cloe 不可以做：

- 直接生成交易指令
- 自动下单
- 绕过 `phase0.cli run`、`execution-gate` 或 `oos-report`
- 修改策略参数后不跑 gate
- 把未经验证的港股 / FRED / Tiingo 数据直接接进主策略

## 六、与现有 MCP 的关系

当前项目已有：

- `.mcp.json`
- `scripts/deepseek_agent_mcp.py`
- `refdocs/DEEPSEEK_AGENT_MCP.md`

OpenClaw Gateway 不替代这些 MCP 工具。推荐分工：

| 工具 | 用途 |
|---|---|
| DeepSeek MCP | 报告总结、策略审查、第二意见 |
| Tushare MCP | A 股数据查询与辅助研究 |
| OpenClaw Gateway | 外部 agent 调度、消息通道、跨工具编排 |

## 七、安全要求

- 默认只用 `loopback`。
- 不使用 `lan` / `tailnet` / `funnel`，除非明确需要远程访问并已配置认证。
- 如需开放给其他设备，必须启用 token 或 password：

```bash
openclaw gateway run --bind loopback --auth token --token "$OPENCLAW_GATEWAY_TOKEN"
```

- token 放在本地 shell 或 `.env`，不得写入 Git。
- `.mcp.json`、`.claude/settings.local.json`、`.codex/*.local.json` 不入库。

## 八、后续任务

- [ ] 确认是否需要为 `stok-mapping` 建专用 OpenClaw agent id
- [ ] 如果需要消息通道，再配置 Telegram / Feishu / WeChat 等 channel
- [ ] 将盘前日报生成结果通过 OpenClaw agent 做文本摘要
- [ ] 将摘要发送到指定消息通道，但仍保持“研究辅助，不构成交易建议”的边界
