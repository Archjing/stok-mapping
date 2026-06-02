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
