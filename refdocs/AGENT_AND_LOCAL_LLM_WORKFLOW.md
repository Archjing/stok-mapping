# Agent、MCP 与本地 LLM 工作流汇编

本文件合并 OpenClaw/Cloe、DeepSeek MCP、本地 LLM 选型与部署接入方案。下方各节保留原文件正文，便于追溯。

## 合并来源

- `refdocs/OPENCLAW_GATEWAY_AGENT.md`
- `refdocs/DEEPSEEK_AGENT_MCP.md`
- `refdocs/LOCAL_LLM_RECOMMENDATION.md`
- `refdocs/LOCAL_LLM_IMPLEMENTATION_PLAN.md`

---

## 原文件：`refdocs/OPENCLAW_GATEWAY_AGENT.md`

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

### 四点五、新增 `cloe-research` 配置档（provider-role）

推荐外部 agent 命名约定使用 `provider-role`，例如：

- `cloe-bridge`
- `cloe-research`
- `cloe-risk`
- `cloe-premarket`

项目内已提供 `cloe-research` 封装脚本：

```bash
scripts/cloe_research_agent.sh "请审查 reports/phase0_effectiveness_report.md，输出风险点和验证建议。"
```

默认会话名：`cloe-research`。  
可选环境变量：

```bash
CLOE_RESEARCH_ACPX_SESSION=cloe-research
CLOE_RESEARCH_ACPX_TIMEOUT=600
CLOE_RESEARCH_ACPX_FORMAT=text
```

兼容回退：如果没有设置 `CLOE_RESEARCH_*`，脚本会回退到 `CLOE_ACPX_*` / `OPENCLAW_ACPX_*`。

### 四点六、新增 `cloe-risk` 配置档

用于风险告警和问题清单提炼：

```bash
scripts/cloe_risk_agent.sh "请审查 execution-gate 与 OOS 报告，按高/中/低列出风险点。"
```

默认会话名：`cloe-risk`。  
可选环境变量：

```bash
CLOE_RISK_ACPX_SESSION=cloe-risk
CLOE_RISK_ACPX_TIMEOUT=600
CLOE_RISK_ACPX_FORMAT=text
```

### 四点七、新增 `cloe-premarket` 配置档

用于盘前观察池解读和开盘情景提示：

```bash
scripts/cloe_premarket_agent.sh "请基于 phase0_premarket_watchlist.csv 输出盘前关注点和情景推演。"
```

默认会话名：`cloe-premarket`。  
可选环境变量：

```bash
CLOE_PREMARKET_ACPX_SESSION=cloe-premarket
CLOE_PREMARKET_ACPX_TIMEOUT=600
CLOE_PREMARKET_ACPX_FORMAT=text
```

以上两个脚本同样支持回退到 `CLOE_ACPX_*` / `OPENCLAW_ACPX_*`。

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
- `refdocs/AGENT_AND_LOCAL_LLM_WORKFLOW.md`

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

---

## 原文件：`refdocs/DEEPSEEK_AGENT_MCP.md`

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

---

## 原文件：`refdocs/LOCAL_LLM_RECOMMENDATION.md`

# 本地部署 LLM 选型结论

## 结论

如果只选一个本地可部署、最适合当前 `stok-mapping` 项目场景的开源/开放权重模型，**首选仍然是 Qwen3**。

在补充检索 **Hugging Face 模型卡** 之后，结论进一步细化为：

1. **主模型首选：Qwen/Qwen3-32B**
2. **显存不足时：Qwen3 14B / 8B**
3. **工程/代码代理优先补位：Qwen/Qwen3-Coder-30B-A3B-Instruct**
4. **作为第二意见/审查器：deepseek-ai/DeepSeek-R1-0528**
5. **国际多语言备选：mistralai/Magistral-Small-2506**
6. **可分析但不适合做主 Agent：google/gemma-3-27b-it**
7. **不建议作为第一选择：Llama 4**

简化判断：

- **主研判代理：Qwen3-32B**
- **本地工程副驾驶：Qwen3-Coder-30B-A3B-Instruct**
- **推理审查器：DeepSeek-R1-0528**
- **国际备选：Magistral-Small-2506**

---

## 为什么首选 Qwen3

### 1. 中文场景最贴合
本项目核心是：
- A 股
- 中文研报/中文日报
- 中文规则与盘前分析
- 中文代码注释与研究输出

Qwen3 在中文理解、中文写作、中英混合任务上更适合这个场景。

### 2. 更适合工具调用与 Agent 工作流
这个项目真正需要的不是普通聊天模型，而是能：
- 读取 `reports/*.md`
- 调用 `phase0.cli`
- 解析回测输出
- 生成结构化研判结论
- 协助修改代码与参数

Qwen 官方对 **function calling / tool use / Qwen-Agent** 的支持更完整，更适合做“本地研究代理”。

### 3. 本地部署路径成熟
Qwen3 官方与 Hugging Face 模型卡共同显示，可配合：
- `vLLM`
- `SGLang`
- `Ollama`
- `llama.cpp`
- `LM Studio`
- `Transformers`

可以先快速验证，再升级为 OpenAI-compatible 的本地服务。

### 4. 工具调用与 Agent 证据最明确
补充查看 Hugging Face 模型卡后，Qwen3-32B 明确强调：
- **agent capabilities**
- **tool use / external tools**
- 推荐搭配 **Qwen-Agent**
- 支持 thinking / non-thinking 两种工作模式

对于你这种“本地工具链 + 日报生成 + 研判代理”的任务，这类信号比一般 benchmark 更关键。

### 5. 金融分析 + 代码辅助更平衡
你的项目既要做：
- 中文金融分析
- A 股盘前研判
- Python/CLI 工具链开发

Qwen3 在“中文分析 + 工具调用 + 编码辅助”这三方面的综合平衡最好。

---

## 关键现实提醒

当前项目最缺的不是“更聪明的 LLM”，而是“更强、可验证的 alpha 引擎”。

根据当前项目输出：

- `sharpe_mean = 0.3358`，未通过 `> 0.5`
- `max_drawdown_mean = -0.3074`，未通过 `> -0.25`
- 当前 Effectiveness Gate 总体仍为 `FAIL`

这意味着：

- **LLM 可以帮你解释、组织、筛查、总结、复盘**
- **但不能凭空把一个尚未过回测门槛的策略变成稳定套利系统**

因此更合理的定位是：

> **让 LLM 做研究代理 + 风控秘书 + 盘前研判助手**
>
> 而不是让它直接替你做交易决策。

---

## 推荐使用方式

### 方案 A：单模型主代理
**Qwen3 32B** 负责：
- 盘前日报生成
- 读取 `phase0` 报告并总结
- 输出观察池、风险点、情景推演
- 协助比较候选策略
- 帮助改代码、调参数、补文档

### 方案 B：双模型结构
如果资源允许，推荐：

- **主代理：Qwen3 32B**
- **工程代理：Qwen3-Coder-30B-A3B-Instruct**
- **审查器：DeepSeek-R1-0528**

分工：

#### Qwen3 负责
- 调工具
- 读报告
- 生成盘前研判
- 产出结构化结论

#### Qwen3-Coder 负责
- 读 repo
- 改 `phase0` 工具链
- 写 glue code / agent integration
- 帮你接本地 CLI、报告解析和自动化流程

#### DeepSeek-R1-0528 负责
- 复核主代理输出
- 专门找逻辑漏洞
- 质疑过拟合、样本偏差、回测失真

这个结构比“单模型直接拍板交易”更稳妥。

---

## 资源条件下的部署建议

### 如果你有 48GB+ 显存
推荐：
- **Qwen3 32B + vLLM / SGLang**

适合作为：
- 本地主研究代理
- OpenAI-compatible 工具调用服务

### 如果你只有 24GB 左右显存
推荐：
- **Qwen3 14B**
- 或者把 **Qwen3-Coder-30B-A3B-Instruct** 作为工程助手、主分析仍由更小 Qwen 承担

适合作为：
- 盘前摘要
- 报告阅读与总结
- 结构化输出
- 轻量代码辅助

### 如果你想做“双模型审查”
推荐：
- 主：**Qwen3 32B**
- 工程：**Qwen3-Coder-30B-A3B-Instruct**
- 审：**DeepSeek-R1-0528** 或其轻量蒸馏版

### 如果你想考虑非中文系国际备选
推荐优先级：
- **Magistral-Small-2506**：多语言且模型卡明确包含中文，适合作为国际备选
- **Gemma-3-27b-it**：多语言强，但模型卡未明确原生工具调用能力
- **Llama 4**：官方支持语言不含中文，不适合作为你的第一选择

---

## 这个项目里，LLM 最应该承担的 5 件事

1. **读取 `phase0` 回测报告并生成中文摘要**
2. **基于规则和报告生成盘前研判日报**
3. **比较候选策略并建议下一轮实验方向**
4. **输出结构化 JSON / Markdown 结论**
   - `watchlist`
   - `risk_flags`
   - `invalid_conditions`
   - `why_not_trade`
5. **辅助改代码与参数，不直接替代交易引擎**

---

## 不建议让 LLM 直接承担的事

1. 直接决定买卖
2. 直接决定仓位
3. 用自然语言“感觉”选股
4. 在策略未过回测 gate 前驱动自动交易

---

## 最终一句话结论

> **最适合当前 `stok-mapping` 项目本地部署的模型：Qwen3。**
>
> 推荐结构是：**Qwen3 做主研究代理，DeepSeek-R1-0528 做审查器**。
>
> LLM 的职责应当是“分析、解释、复盘、辅助研究”，而不是在当前阶段直接替代策略引擎做交易决策。

---

## 原文件：`refdocs/LOCAL_LLM_IMPLEMENTATION_PLAN.md`

# 本地 LLM 部署与接入 `stok-mapping` 实施方案

目标：在本地部署一个可控的 LLM/Agent 系统，让它**使用 `stok-mapping` 已开发的工具**完成盘前阅读、看盘分析、研究总结、候选策略比较与观察池生成。

> **边界声明**：本方案定位为**研究代理 / 风控秘书 / 盘前研判助手**。它不能替代策略引擎，也不应在当前阶段直接自动下单。

---

## 1. 你现在最适合的目标形态

不是做“让 LLM 直接替你交易”的自动交易体，而是做一个：

- **读报告**：读 `reports/*.md`
- **调工具**：调 `phase0.cli`
- **做解释**：解释当前候选策略为何胜出或失败
- **做比较**：比较不同候选策略和参数
- **出研判**：生成盘前观察池、风险提示、失效条件
- **帮开发**：辅助你扩展 `phase0` 策略模块

### 正确定位

```text
本地历史库/报告/回测结果 → 策略引擎给出可验证信号 → LLM 做解释与组织 → 你人工决策
```

### 不建议定位

```text
原始市场数据 → LLM 直接猜股票和仓位 → 自动交易
```

---

## 2. 推荐模型结构

## 2.1 单模型最简方案

### 主模型
- **Qwen/Qwen3-32B**

### 用途
- 盘前研判主代理
- 报告阅读与总结
- 工具调用与结构化输出
- 候选策略比较

### 适合条件
- 你有较强 GPU 资源
- 你想优先把完整链路跑通

---

## 2.2 推荐双模型方案

### 主代理
- **Qwen/Qwen3-32B**

### 工程代理
- **Qwen/Qwen3-Coder-30B-A3B-Instruct**

### 审查器
- **DeepSeek-R1-0528**（或轻量蒸馏版）

### 分工

#### Qwen3-32B
负责：
- 调工具
- 读 `phase0` 报告
- 生成盘前日报
- 输出结构化结论

#### Qwen3-Coder
负责：
- 读 repo
- 改 `phase0` 代码
- 写 glue code
- 生成 Agent 集成脚本

#### DeepSeek-R1-0528
负责：
- 复核主代理结论
- 找逻辑漏洞
- 质疑过拟合、样本偏差、回测失真

---

## 2.3 国际备选

如果你想做额外对照：

- **Magistral-Small-2506**：最值得试的国际多语言备选
- **Gemma-3-27b-it**：分析可用，但工具调用信号不强
- **Llama 4**：不适合作为当前项目第一选择

---

## 3. 按硬件条件选模型

## 3.1 你有 48GB+ 显存

### 推荐
- `Qwen/Qwen3-32B`
- `Qwen/Qwen3-Coder-30B-A3B-Instruct`

### 服务方式
- **首选：vLLM**
- 备选：**SGLang**

### 适合做
- 主盘前研判代理
- 本地 OpenAI-compatible API
- 多工具调用
- 长报告解析

---

## 3.2 你有 24GB 左右显存

### 推荐
- `Qwen3 14B`
- 工程辅助可单独尝试更轻量 coder / quant 版

### 服务方式
- `vLLM` 或 `Ollama`
- 若更重视部署简便：`Ollama`

### 适合做
- 报告总结
- 观察池生成
- 结构化 JSON 输出
- 轻量代码辅助

---

## 3.3 你只有消费级本地机器 / Mac / CPU 偏多

### 推荐
- 量化版 / GGUF 版 Qwen
- `llama.cpp` / `Ollama` / `LM Studio`

### 用途
- 不建议做主实时代理
- 适合做离线阅读器、摘要器、复盘助手

---

## 4. 本地部署选型建议

## 4.1 首选：vLLM

适合：
- 你要 OpenAI-compatible 接口
- 要和 Agent/脚本集成
- 要服务多个工具调用请求

### 优点
- API 兼容度高
- 适合脚本化调用
- 方便接 Agent 框架

---

## 4.2 备选：SGLang

适合：
- 你更重视 agent/tool parser
- 想更强控制推理与工具流

### 优点
- 对 agent 工作流友好
- 部分模型的 tool parser 支持明确

---

## 4.3 最简：Ollama

适合：
- 快速本地验证
- 单机单用户
- 不急着做复杂 Agent 编排

### 优点
- 部署快
- 命令简单
- 适合先验证模型风格

### 不足
- 做复杂多工具编排时不如 vLLM/SGLang 灵活

---

## 5. 建议的最小部署命令

## 5.1 Qwen3-32B with vLLM

```bash
pip install -U vllm
vllm serve Qwen/Qwen3-32B
```

如果你需要更明确的 reasoning 模式支持，可按模型卡建议增加参数。

---

## 5.2 Qwen3-Coder with vLLM

```bash
pip install -U vllm
vllm serve Qwen/Qwen3-Coder-30B-A3B-Instruct
```

---

## 5.3 Qwen3-32B with SGLang

```bash
pip install -U sglang
python3 -m sglang.launch_server \
  --model-path Qwen/Qwen3-32B \
  --host 0.0.0.0 \
  --port 30000
```

---

## 5.4 Ollama 快速验证（如果有对应模型包）

```bash
ollama run qwen3
```

> 说明：Ollama 适合“先看模型风格”，不适合你最终要做的完整研究代理主链路。

---

## 6. 建议的 Agent 架构

## 6.1 最小可用架构

```text
┌──────────────────────────────────────┐
│ Local LLM Service (Qwen3 via vLLM)   │
│ OpenAI-compatible API                │
└──────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────┐
│ Research Agent                       │
│ - 读报告                             │
│ - 调 phase0.cli                      │
│ - 汇总结构化结论                     │
└──────────────────────────────────────┘
        │                │
        │                ├── Tool: run_phase0
        │                ├── Tool: build_universe
        │                ├── Tool: read_reports
        │                ├── Tool: read_config
        │                └── Tool: compare_candidates
        ▼
┌──────────────────────────────────────┐
│ Output                               │
│ - watchlist                          │
│ - risk flags                         │
│ - invalid conditions                 │
│ - summary markdown/json              │
└──────────────────────────────────────┘
```

---

## 6.2 推荐的三代理架构

```text
Qwen3 主代理
  ├─ 负责盘前分析
  ├─ 负责调用工具
  └─ 生成结构化日报

Qwen3-Coder 工程代理
  ├─ 负责修改/扩展 phase0 代码
  ├─ 负责生成集成脚本
  └─ 负责维护自动化任务

DeepSeek 审查器
  ├─ 复核盘前结论
  ├─ 质疑数据外推
  └─ 提醒回测与实盘偏差
```

---

## 7. 建议接给 LLM 的本地工具

你这个项目不需要给模型开放整个 shell 世界，建议只暴露**有限工具集**。

## 7.1 第一批必须工具

### Tool 1: `read_report`
读取：
- `reports/phase0_walk_forward_report.md`
- `reports/phase0_effectiveness_report.md`
- `reports/phase0_data_source_report.md`
- `data/universe/local_factor_universe_report.md`

### Tool 2: `run_phase0`
相当于：

```bash
./.venv/bin/python -m phase0.cli run --config config.yaml
```

### Tool 3: `build_universe`

```bash
./.venv/bin/python -m phase0.cli build-universe --config config.yaml
```

### Tool 4: `update_history_check`

```bash
./.venv/bin/python -m phase0.cli update-history --config config.yaml --check-only
```

### Tool 5: `read_config`
读取 `config.yaml`

### Tool 6: `compare_candidates`
读取并比较：
- `reports/phase0_walk_forward_candidates.csv`
- `reports/phase0_walk_forward_report.md`

---

## 7.2 第二批增强工具

### Tool 7: `update_financials`

```bash
./.venv/bin/python -m phase0.cli update-financials --config config.yaml
```

### Tool 8: `read_universe_snapshot`
读取：
- `data/universe/local_factor_universe.csv`

### Tool 9: `generate_daily_brief`
把结构化结论渲染成每日 Markdown 报告

---

## 8. LLM 的输入输出协议建议

## 8.1 输入不要太自由

不要直接让模型“随便看看然后给建议”。

建议固定输入模板：

```json
{
  "date": "2026-05-29",
  "project": "stok-mapping",
  "task": "pre_market_brief",
  "reports": [
    "reports/phase0_walk_forward_report.md",
    "reports/phase0_effectiveness_report.md"
  ],
  "config": "config.yaml",
  "constraints": {
    "no_trade_instruction": true,
    "output_language": "zh-CN",
    "focus": ["watchlist", "risk_flags", "invalid_conditions"]
  }
}
```

---

## 8.2 输出必须结构化

建议模型输出：

```json
{
  "summary": "...",
  "watchlist": [
    {
      "symbol": "SZ.300750",
      "reason": "...",
      "risk_level": "medium",
      "invalid_condition": "..."
    }
  ],
  "risk_flags": [
    "当前主策略夏普仍未过 gate",
    "最大回撤偏大，不能直接自动交易"
  ],
  "next_actions": [
    "继续比较 residual_momentum 与 legacy_momentum",
    "优先验证量价二次筛选"
  ]
}
```

然后再渲染为 Markdown 日报。

---

## 9. 适合你的每日运行流程

## 9.1 建议的每日节奏

### 06:00 之后
- 更新隔夜美股与跨市场数据
- 读取当前 `phase0` 报告

### 07:00–07:20
Research Agent 调工具：
- `update_history_check`
- `read_report`
- `read_config`
- `compare_candidates`

### 07:20–07:30
生成：
- 盘前摘要
- 观察池
- 风险标记
- 当前策略失效条件

### 07:30
把结果写入：
- `reports/daily_pre_market_brief.md`
- 或邮件/PWA 推送的中间文件

---

## 9.2 推荐生成的日报内容

```text
1. 今日一句话结论
2. 当前主策略状态
3. 候选策略比较摘要
4. 今日观察池
5. 风险提示
6. 哪些情况下不应交易
7. 建议优先验证的下一步实验
```

---

## 10. 不要让它直接做的事情

以下能力当前不要开放给 Agent：

- 自动下单
- 直接连接券商接口
- 自动改生产配置
- 自动决定仓位
- 自动跳过 Effectiveness Gate
- 自动修改历史回测结果

---

## 11. 你最应该先做的 3 个落地步骤

### Step 1：先把主模型服务跑起来
建议先上：
- `Qwen/Qwen3-32B` + `vLLM`

目标：
- 先能通过 API 回答问题
- 先能读报告并总结

### Step 2：只接最小工具集
先只接：
- `read_report`
- `read_config`
- `compare_candidates`
- `update_history_check`

目标：
- 先做日报助手
- 不直接改代码，不直接跑重任务

### Step 3：再接 `phase0.cli`
再逐步接：
- `run_phase0`
- `build_universe`
- `update_financials`

目标：
- 让模型具备“研究助理”能力
- 但仍保留人工审批

---

## 12. 适合当前项目的最终落地建议

### 最稳方案
- **主代理：Qwen/Qwen3-32B**
- 服务：**vLLM**
- 角色：**日报生成 + 报告阅读 + 研判整理**

### 最实用扩展
- 增加 **Qwen/Qwen3-Coder-30B-A3B-Instruct**
- 角色：**工程副驾驶 / 自动化脚本与工具集成**

### 最稳妥审查
- 增加 **DeepSeek-R1-0528**（或轻量蒸馏版）
- 角色：**策略与结论审查器**

---

## 13. 一句话实施结论

> 先用 **Qwen3-32B + vLLM** 把“读报告 → 调有限工具 → 生成盘前研判”跑通；
> 再用 **Qwen3-Coder** 帮你扩展工具链；
> 最后再考虑用 **DeepSeek** 做审查器。
>
> 在当前阶段，LLM 应该接入 `stok-mapping` 做**研究代理**，而不是替代策略引擎做自动交易。

---
