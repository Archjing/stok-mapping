# 2026-06-08 Session 增量知识归档

归档日期：2026-06-08  
定位：在 `2026-06-04` 与 `2026-06-06` 已有归档基础上，补充本次会话新增的知识性内容。  
范围：保留策略研发、架构演示、机器学习能力规划、技能选择与安装等可复用内容；明确排除本次会话中关于 `MCP` 与 `Activepieces` 的讨论。  

导航：[`refdocs 索引`](../README.md)

---

## 2026-06-08 增量归档：解释类 / 研判计划类问答

> 来源 session：`/home/zj/.codex/sessions/2026/06/07/rollout-2026-06-07T00-00-00-019e9da9-a15d-7e80-a590-d59326901cab.jsonl`
> 完整归档规则：命中解释、解读、回答、详解、是非判断、研判、考虑、计划、为什么、是什么、如何、怎么、哪个；以及调研、检索、文献搜索、资料排序、数据源/API/权限/费用评估等主题型研究。
> 其他内容：未命中原文归档规则的会话内容、项目开发文档更新内容已压缩摘要归档。
> 上次已归档时间戳：`2026-06-06`

### 👤 User / 用户
$machine-learning 能为本项目做什么？

### 🤖 Assistant / 助手
`machine-learning` 对本项目最有价值的方向，不是马上上深度模型选股，而是把现有“因子研究 + 策略准入 + 数据治理”升级成更强的研究工具链。

**最适合做的事**
1. **因子有效性建模**
   - 用 ML 判断哪些因子在不同市场阶段有效。
   - 输入：低波、低换手、质量、估值、动量、反转、行业、流动性、宏观/跨市场 overlay。
   - 输出：因子权重、因子失效预警、市场状态下的因子适用性。

2. **二阶段 rerank**
   - 现有策略先筛出候选股票。
   - ML 不直接全市场选股，而是在候选池里二次排序。
   - 好处：降低过拟合和交易成本，保留规则策略可解释性。
   - 适合模型：Logistic / Lasso / Elastic Net / XGBoost / LightGBM。

3. **策略准入增强**
   - 对 walk-forward fold 结果做稳定性分类。
   - 识别“只在少数窗口有效”的策略。
   - 预测策略进入未来样本后失效概率。
   - 服务 `strategy-admission`，不是替代它。

4. **市场状态识别**
   - 识别趋势、震荡、风险偏好、流动性收缩、拥挤交易等 regime。
   - 用于风险缩放、暂停策略、降低仓位，而不是直接下单。
   - 可结合 FRED、VIX、港股、美股、A 股宽基、成交额、换手率。

5. **异常检测与数据质量**
   - 检测异常 OHLC、异常成交额、财务字段异常、覆盖率突变。
   - 这对 `db-health` 很有价值。
   - ML 在这里的 ROI 可能高于直接预测收益。

6. **研究情报分类**
   - 自动给论文、新闻、公告、研报打标签。
   - 提取策略假设、因子、数据需求、风险点。
   - 服务“投资策略情报工作流模块”。

**不建议现在做的事**
- 不建议直接训练深度学习模型预测个股涨跌。
- 不建议让 LLM 或神经网络直接生成买卖信号。
- 不建议在 `qfq_asof`、PIT、财务因子覆盖和策略准入还没完全闭环前，把 ML 作为主 ranker。
- 不建议先上 JAX/深度学习，当前项目更适合从可解释的传统 ML 开始。

**推荐落地顺序**
1. `ML-0`：建立 ML 数据集生成器，严格保证 `as_of_date`、PIT 股票池、`qfq_asof`、财务公告日。
2. `ML-1`：做二阶段 rerank MVP，只在已有策略候选池内排序。
3. `ML-2`：把 ML 结果接入 `strategy-admission`，作为辅助诊断，不作为准入唯一依据。
4. `ML-3`：做市场 regime 识别，用于仓位缩放和风险解释。
5. `ML-4`：再考虑 XGBoost/LightGBM，最后才考虑深度学习或 JAX 加速。

**我的判断**
当前最值得做的是：`ML 数据集生成器 + 二阶段 rerank MVP + strategy-admission 辅助诊断`。  
这条线收益高、风险可控，并且符合本项目“可审计、可复现、先治理再预测”的架构方向。

### 👤 User / 用户
$skill-installer 搜索适合本项目的数据分析工具

### 🤖 Assistant / 助手
用 `skill-installer` 查到的 curated skills 里，真正适合本项目“数据分析/量化研究”的候选不多。

**最推荐安装**
1. `jupyter-notebook`
   - 用途：适合做因子诊断、数据覆盖率分析、策略回测结果探索、图表原型。
   - 适配本项目：很高。
   - 建议：安装。

2. `pdf`
   - 用途：读取/处理论文、研报、审计 PDF。
   - 适配本项目：中高，适合 `refdocs/papers/` 和研究情报模块。
   - 建议：可安装。

3. `playwright`
   - 用途：网页抓取、网页报告验证、HTML 报告截图、可视化 UI 自动检查。
   - 适配本项目：中高，尤其适合后续本地 UI / 报告系统。
   - 建议：可安装，但不是纯数据分析。

4. `screenshot`
   - 用途：截取网页/报告视图。
   - 适配本项目：中，适合报告验收和 UI 归档。
   - 建议：可选。

**研究文档/知识管理相关**
5. `notion-research-documentation`
   - 用途：研究资料整理、文档化。
   - 适配本项目：中，项目已有 `docs/`、`refdocs/`、Logseq/KMS 流程，未必需要 Notion。
   - 建议：除非你打算接 Notion，否则不优先。

6. `notion-knowledge-capture`
   - 用途：知识捕获。
   - 适配本项目：中低，和现有本地 Markdown/Logseq 路线可能重复。
   - 建议：暂不优先。

**当前结论**
最小安装组合建议：

```text
jupyter-notebook
pdf
playwright
```

如果只装一个：`jupyter-notebook`。

实验技能列表查询失败，原因是远端 `skills/.experimental` 路径不存在或不可用。当前 curated 列表里没有专门的 `pandas`、`duckdb`、`sqlite-analysis`、`quant-research` 类技能。

如果你确认，我可以继续安装：

```bash
jupyter-notebook
pdf
playwright
```

### 👤 User / 用户
系统里已经安装过jupyter-notebook

### 🤖 Assistant / 助手
是的，当前系统里可能已经有 Jupyter 环境，但 `skill-installer` 查的是 **Codex skill 是否安装**，不是系统 Python 包或可执行程序。

刚才列表显示：

```text
jupyter-notebook installed: false
```

含义是：Codex 的 `jupyter-notebook` 技能尚未安装。

建议区分：

- 系统已安装 Jupyter：你可以自己运行 notebook。
- Codex 未安装 `jupyter-notebook` skill：我还没有专门的 notebook 操作流程/规范技能。

如果只是本项目数据分析，系统已有 Jupyter 就够用；不一定需要再装 skill。  
更值得补的是 `pdf` 和 `playwright`。

## 其他会话内容压缩摘要

- 新增 Slidev 架构演示稿目录 `docs/slides/project-architecture/`，包含 `slides.md` 和 `README.md`。演示稿基于 `docs/PROJECT_ARCHITECTURE_OVERVIEW.md` 与 `docs/DEVELOPMENT_PLAN.md` 提炼，覆盖系统定位、分层架构、端到端数据流、数据质量门禁、策略研究流、策略治理门禁、账户仿真、维护编排器、System Orchestrator、本地桌面 UI 预留、关注个股分析工具、关键数据口径、失败模式、架构债务与演进路线。风格采用 Slidev 标准 Markdown + Mermaid 图 +内联样式，不改动 `package.json`，避免新增 Node 依赖和 lockfile 变更。
- 为 Slidev 演示稿单独创建提交：`245524a Add Slidev architecture presentation`。该提交只包含 `docs/slides/project-architecture/README.md` 与 `docs/slides/project-architecture/slides.md`，未把 `data/maintenance/maintenance.sqlite` 和 `logs/project_scheduler.log` 两个运行态文件纳入提交。
- 执行 Git 同步时，先用 `git pull --rebase --autostash` 处理本地运行态脏文件，再完成 `git push`。最终远端 `main` 推送到 `245524a`，本地仍保留未提交的运行态改动：`data/maintenance/maintenance.sqlite` 与 `logs/project_scheduler.log`。
- 使用 `skill-installer` 安装了 Codex 的 `jupyter-notebook` 技能，安装路径为：

```text
/home/zj/.codex/skills/jupyter-notebook
```

  该安装不影响系统已有 Jupyter，只是为 Codex 增加 notebook 工作流能力。安装后需要重启 Codex 才能在后续会话中生效。
- 本次归档明确排除会话后半段关于 `MCP`、`Activepieces`、OAuth/Bearer token、客户端兼容性与登录排障的全部讨论，不写入本文件。
