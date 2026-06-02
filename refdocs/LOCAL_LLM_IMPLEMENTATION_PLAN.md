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
