# 跨市场量化研判与选股系统 · 开发计划书

> 项目名称：stok-mapping  
> 创建日期：2026-05-28  
> 最后修订：2026-06-01（实盘仿真 profile、OOS profile 与 HTML 报表体验收口）
> 状态：**Phase 0 已通过；账户级仿真与报表链路已收口，当前进入 Phase 1 / Week 2 准备**
> 法律声明：本工具定位为**量化研究与风险提示工具**，所有输出属于观察池、信号等级、风险暴露、情景推演和策略验证结果，不构成任何形式的投资建议、荐股或交易指令。使用者应独立判断并承担全部交易风险。  
> **边界声明：本系统仅供个人研究和自用决策辅助，不对外提供投资建议或商业服务。**

---

## 当前项目状态摘要

### 当前阶段

项目已完成一轮 **Phase 0 正式验证**，当前进入 **通过后的收口阶段**：

- Phase 0 基础设施已验证可用
- 本地历史库、股票池、walk-forward、候选比较链路已落地
- 策略层已拆为 `phase0/strategies/` 注册表结构
- 候选样本治理已固化，当前 compare 已统一为 portfolio 口径
- 当前 selected candidate 已切换为 `legacy_momentum_low_turnover_v1`
- 主测试默认成本口径已切换为 `slippage = 0.00246`，用于更贴近普通个人实盘执行假设
- 成本敏感性测试已从 `phase0 run` 中拆出，必须通过单独 CLI 显式指定场景再运行
- 连续 OOS 资金曲线与沪深300基准对比报表已生成，已纠正 walk-forward 分折重置带来的阅读偏差
- 账单导出已接入正式 CLI / report 链路，`phase0 run` 会同步生成账单、日资产表和 HTML 预览
- 账户级账单已补齐 A 股 `100` 股整手成交、现金约束、卖出回款和交易成本字段
- 账户级仿真 v2 已补齐 `execution.price_mode`、涨跌停、停牌、流动性参与率、未成交原因和真实账户 CSV 对账预留
- `execution-gate` 与 `oos-report` 已支持 `research` / `live` profile，标准参数组合统一由 `config.yaml` 管理，脚本不再内置 profile 默认数值
- 行情分段验证已生成 HTML / CSV 报告，用于区分顺风行情、震荡和回撤阶段表现
- 财务因子 PTI 校验已生成独立报告，当前结论为 `PASS`
- `07:30` 盘前观察池已接入 CLI，按最近交易日信号输出持仓、候选、权重和观察理由
- HTML 报表体验已统一：标题右侧显示生成时间，宽表按 `96vw` 横向滚动，长表按 `70vh` 纵向滚动，表头固定
- 当前主阻塞点不再是 Sharpe 门槛，而是**把通过策略转入更长期的稳定性验证、数据源升级和日常研判自动化**

### 当前主线

> **A 股本土因子为主，跨市场信号仅做风险/情绪 overlay。**

跨市场映射仍然重要，但当前不再作为主选股 ranker，而是用于：

- 隔夜情绪解释
- 风险缩放
- 开盘情景推演
- 盘中情绪验证

### 当前选中候选与门槛状态

根据 `reports/phase0_effectiveness_report.md`（生成时间：2026-05-31 18:59:23，主测试 `slippage = 0.00246`）：

- 当前 selected candidate：`legacy_momentum_low_turnover_v1`
- 当前总 verdict：`PASS`
- 样本治理状态：`selected_candidate_eligible = True`
- 样本覆盖：`4` 个 portfolio fold
- 关键变化：低换手改造后，Sharpe、回撤、胜率和样本外衰减全部过线

当前 gate 结果：

| 指标 | 当前值 | 门槛 | 状态 |
|------|--------|------|------|
| `selected_candidate_eligible` | `True` | `True` | PASS |
| `annualized_return_mean` | `0.1331` | `> 0` | PASS |
| `sharpe_mean` | `1.0083` | `> 0.5` | PASS |
| `max_drawdown_mean` | `-0.1042` | `> -0.25` | PASS |
| `win_rate_mean` | `0.5110` | `> 0.45` | PASS |
| `oos_return_decay_ratio` | `-2.4116` | `< 0.30` | PASS |

解释：

- 所有候选已统一为 `portfolio` 口径，避免 symbol-scope 与 portfolio-scope 混排。
- 回测窗口已扩大到 7 年，使 portfolio 候选均达到 `4` 个 fold 的最低治理门槛。
- `legacy_momentum_low_turnover_v1` 已替代旧 `legacy_momentum` 成为当前主候选。
- 低换手、宽持有区间、较慢调仓与换手惩罚显著降低了年化换手：`13.48 -> 1.50`。
- 在 `base_research_cost`、`main_personal_execution`、`stress_slippage_0_003`、`stress_slippage_0_005` 等场景下，低换手候选仍是主要有效候选；但成本敏感性属于单独验证路径，不再混入每次主测试。

### 当前工作重心

当前阶段最优先的是：

1. 固化 `legacy_momentum_low_turnover_v1` 的解释链路，保持 report / gate / bill / 变更日志口径一致。
2. 维护账单、资产轨迹、买卖原因和策略参数的标准 CLI / report 链路。
3. 维护账户级仿真 v2，并在后续真实账户复盘时接入本地持仓 / 成交回报 CSV 对账。
4. 维护 `research` / `live` profile 的参数治理，确保策略研究口径和实盘仿真口径分离。
5. 基于已通过的财务因子 PTI 校验，谨慎恢复质量成长 / 多因子后续验证。
6. 将盘前观察池接入定时任务和日报摘要，形成可复盘的日常研判记录。
7. 按 Week 2 顺序先推进 FRED 宏观 / 利率 / VIX 数据源，再推进 Tiingo 美股个股 / ETF 主源。

当前**不是**优先做的事：

- 再盲目堆叠新的主候选策略
- 扩展跨市场主 ranker
- 让 LLM 直接参与交易决策
- 把账户级仿真结果误解为实盘可自动下单

### 通过后四步执行顺序

这是当前 Phase 0 通过后的正式开发顺序，后续任务默认按这条线推进：

| 优先级 | 任务 | 现在做它的理由 | 完成标准 |
|------|------|------|------|
| `P0` | 将账单导出纳入正式 `CLI / report` 链路 | 当前账单、日资产表和 HTML 预览需要固化为标准产物，后续验证、归档和日报才能共用同一口径。 | 已完成。`phase0 run` 与 `phase0 bill` 可稳定生成账单、日资产表和 HTML 预览。 |
| `P0` | 增加 A 股整手成交、现金约束和账户级撮合细节 | 当前回测更偏目标权重层，距离真实 A 股账户执行还有差距；不补这层，账单的实盘参考价值有限。 | 已完成。账单体现 `100` 股整手、买入受现金限制、卖出回笼现金，以及现金/持仓/总资产联动。 |
| `P1` | 账户级仿真 v2：A 股真实交易约束增强 | 当前账单已完成账户级 v1，但仍缺次日开盘/保守成交价、涨跌停、停牌、流动性和未成交记录。 | 已完成。账单能展示全部成交、部分成交、未成交及原因；盘前观察池显示执行风险提示；真实账户 CSV 对账格式已预留。 |
| `P1` | 区分策略研究与实盘仿真 profile | 同一策略在研究口径和接近实盘口径下参数不同，混用会导致报告不可比较。 | 已完成。`execution-gate` 与 `oos-report` 支持 `--profile research/live`，并从 `config.yaml` 读取参数组合。 |
| `P1` | 统一 HTML 报表展示规范 | 报表需要适合人工复核，长表和宽表必须可读、可滚动、可定位生成时间。 | 已完成。所有现有 HTML 与生成脚本已补生成时间、横纵滚动和固定表头。 |
| `P1` | 完成财务因子公告日 point-in-time 校验方案 | 后续质量成长、多因子扩展都依赖财务字段，必须先封住未来函数争议。 | 已完成。`reports/phase0_financial_pti_report.html` 当前结论为 `PASS`。 |
| `P1` | 将当前 selected strategy 接入 `07:30` 盘前日报 / 观察池输出 | 策略通过后，需要进入日常使用链路，而不是只停留在回测报告。 | 已完成。`phase0 premarket` 输出候选、权重、理由和 HTML 报告。 |

补充约束：

- 在上述四步完成前，不把 residual / multifactor 等备选策略重新拉回主线。
- `FRED` / `Tiingo` 数据源升级继续保留，但优先级低于当前通过策略的收口工作。

---

## 一、背景依据摘要

本项目的研究框架来自三类信息源：

### 1.1 跨市场映射研究结论

外部研究与项目内 Phase 0 结果共同表明：

- 美股对 A 股的影响更多体现在**隔夜开盘与短时情绪传导**
- 板块映射强于大盘映射
- VIX、KWEB、CNH、SOX、NVDA 等指标更适合做风险与情绪解释
- 月线级别跨市场相关性并不稳定，不能天然充当长期主选股因子
- 本项目已有候选回测显示，直接把跨市场信号作为主 ranker 效果弱于本土主因子路径

### 1.2 量化策略方法论结论

量化交易方法论给出的关键启发：

- 简单策略优于过度复杂策略（KISS）
- 因子应是可解释收益差异的变量，而不是事后拟合标签
- 策略评价应以年化、夏普、最大回撤、胜率、换手和样本外衰减综合判断
- 单次高收益不能代替稳定性验证
- LLM 更适合做摘要、整理、研究辅助和反方审查，而不是直接决定交易信号

### 1.3 论文与研究报告依据

以下内容是本项目功能设计与策略扩展的重要理论依据：

- `refdocs/papers/cn/cn_INDEX.md` 索引的中文 A 股论文资料
- `refdocs/papers/en/INDEX.md` 索引的英文/国际论文资料
- `refdocs/todo/PHASE0_CANDIDATE_STRATEGIES.md`
- `reports/phase0_strategy_change_log.md`
- `reports/phase0_walk_forward_report.md`
- `reports/phase0_effectiveness_report.md`

这些资料用于：

- 选择可落地的候选策略方向
- 约束架构扩展顺序
- 判断哪些 ML / 多因子 / 量价 / 文本思路值得优先进入产品
- 记录每次策略参数和逻辑调整的理由

### 1.4 当前交叉结论

结合文献、项目内回测和数据可用性，当前最重要的结论是：

> **跨市场映射适合作为 overlay，不适合作为当前阶段主 ranker。**

因此项目主线已经调整为：

> **本土主因子选股 + 跨市场风险缩放 / 情绪解释 + 严格 effectiveness gate 治理。**

---

## 二、系统定位

本项目是一个：

> **A 股本土因子为主、跨市场风险/情绪 overlay 为辅的量化研究与盘前研判工具。**

它不是通用量化平台，也不是自动交易系统。

### 当前目标

输入多市场数据后，输出：

- A 股盘前情景推演
- 观察池
- 风险暴露说明
- 失效条件
- 候选策略对比结论
- 策略有效性验证报告

### 输出边界

所有输出统一使用以下研究语言：

- 观察池
- 风险暴露
- 信号等级
- 情景推演
- 失效条件
- 策略验证结果

明确禁止：

- 强买入
- 清仓
- 满仓
- 荐股
- 自动下单指令
- LLM 直接生成交易信号

### 输入 / 输出全景

```text
输入层                      分析引擎层                         输出层
────────────────────────────────────────────────────────────────────────────
美股/ETF/宏观 → 跨市场风险/情绪 overlay ─┐
港股/A50/CNH  → 盘前与盘中情绪验证       ├→ 观察池 / 风险暴露 / 情景推演
A股日线/财务  → 本土主因子引擎           ├→ 候选策略 / 组合候选 / 信号等级
政策/研报/财报 → LLM 摘要与解释辅助      ┘
```

---

## 三、当前有效的引擎分工

### 引擎 #1：隔夜情绪传导

作用：

- 解释隔夜开盘方向
- 识别 risk-off / risk-on
- 作为风险缩放层，而非主排序层

核心输入：

- 纳指 / SOX
- NVDA / KWEB
- VIX
- CNH / CNY 代理
- A50 / 港股情绪代理

当前状态：

- 当前跨市场 overlay 已先落库到 `data/us_market_history.sqlite`，策略运行读取本地 `us_daily_bars`，不再运行时临时抓取 yfinance。
- US market 当前 provider 仍为 `yfinance`，但定位是过渡数据源；后续美股个股/ETF 计划接入 `Tiingo`，宏观/利率/VIX 计划接入 `FRED`。
- 港股库 `data/hk_market_history.sqlite` 仅保留结构和 CLI，当前 `enabled: false`，等港股数据源接入并通过覆盖率/新鲜度验证后再挂到应用。
- 港股映射 A 股候选策略已记录到 `refdocs/todo/HK_A_SHARE_MAPPING_STRATEGIES.md`，后续补全代码；当前先做数据层验证，不并入 Phase 0 主线。

### 引擎 #2：本土主因子选股

作用：

- 作为当前主策略验证核心
- 决定候选池与排序主逻辑
- 生成可进入观察池的 A 股候选

当前已注册候选：

- `legacy_momentum`
- `ma_kline_baseline_v1`
- `residual_momentum_reversal_v1`
- `residual_momentum_reversal_v2`
- `quality_growth_price_v1`
- `multifactor_volume_price_filter_v1`

当前重点：

- `quality_growth_price_v1` 需要扩大 fold/symbol 覆盖验证。
- `legacy_momentum` 仍需作为 baseline 保留。
- 新候选不能仅凭少量 fold 的高分晋级。

### 引擎 #3：港股领先指标

作用：

- 盘中外资情绪代理
- 替代已停发的北向实时成交细节
- 做盘中确认，不作为主选股核心

当前状态：

- 仍处于设计/辅助输入阶段。
- 不影响 Phase 0 当前主线。

### 引擎 #4：解释层 / Agent 辅助层

作用：

- 把策略报告和数据质量报告转为可读摘要
- 提醒风险、矛盾、样本不足和下一步验证
- 为盘前日报提供文案草稿

当前接入：

- `.codex/` 下 Claude provider 脚本
- `deepseekAgentMcp` 用于第二意见、报告总结和策略审查

边界：

- 不直接生成交易指令
- 不修改策略参数
- 不跳过 effectiveness gate

---

## 四、多因子研究框架

### 4.1 当前因子优先级

```text
单只标的研究评分 = 本土主因子分数 × 跨市场风险缩放 × 可成交性约束
```

当前本土主因子优先，跨市场只做 overlay。

### 4.1.1 本土价格行为因子（当前第一优先级）

- 残差动量
- 短周期反转
- 低波
- 趋势确认
- 量价强弱
- 均线偏离
- K 线行为特征
- 成交额放量 / 缩量过滤
- 跳空与上影线过热过滤

### 4.1.2 本土基本面因子（已接入，但历史使用仍需谨慎）

当前已接入季度财务字段：

- `roe`
- `revenue_growth`
- `profit_growth`
- `operating_cash_flow_to_net_profit`
- `debt_to_asset`

当前用途：

- 最新横截面筛选
- 质量/成长/价格复合候选策略
- 股票池 snapshot 辅助解释

当前限制：

- 在进入正式历史回测前，必须先完成公告日 point-in-time 校验。
- 不能直接把报告期末数据视为历史上当日可用数据。
- `quality_growth_price_v1` 的当前好结果必须先通过样本覆盖和时间线审查。

### 4.1.3 行业 / 主题轮动因子（后续）

适合 A 股结构，但需先补：

- 更稳定的行业分类
- 行业层回测框架
- 行业中性化与拥挤度分析
- 行业权重上限对策略表现的影响评估

### 4.1.4 跨市场风险 overlay

只做：

- 风险缩放
- 情绪解释
- 开盘情景推演
- 盘中确认

**不做主 ranker。**

### 4.1.5 机器学习能力（中期扩展）

本项目未来需要具备机器学习分析能力，但应建立在当前应用导向主线之上，而不是一开始全面学术化重构。

建议中期按以下顺序引入：

1. 多因子 + 规则过滤
2. 多因子 + sklearn 基线模型（SVM / Logistic / Lasso / Ridge）
3. 滚动评估与预测记录
4. 简单组合权重生成

也就是说：

> 机器学习能力要服务于“更快形成可用产品”，而不是先把系统变成纯研究平台再考虑应用输出。

### 4.1.6 新闻 / 文本摘要因子（辅助）

LLM 仅负责：

- 政策/财报/研报摘要
- 报告压缩
- 策略审查第二意见
- 解释层文案整理

LLM 不直接生成评分与交易信号。

### 4.2 信号等级体系（研究输出，非交易指令）

| 信号等级 | 含义 | 当前用途 |
|---------|------|---------|
| L1-高关注 | 条件最强，进入核心观察池 | 盘前研判 |
| L2-关注 | 条件成立但有追高/拥挤风险 | 盘前研判 |
| L3-中性 | 无明确信号 | 观望 |
| L4-谨慎 | 风险偏空或映射不利 | 降暴露 |
| L5-避险 | 极端风险情景 | 只观察 |

### 4.3 风险预算体系

不采用凯利公式。当前统一采用风险预算约束：

- 单票暴露上限
- 单行业暴露上限
- 总暴露上限
- 波动率过滤
- 回撤熔断
- 连续失败降级
- 样本覆盖不足降级

### 4.4 可成交性模型

在任何信号输出前都必须检查：

- 停牌
- 涨跌停
- T+1
- 流动性
- 冲击成本
- 开盘追价风险
- 行业集中度

---

## 五、数据源策略（已确认并采纳）

本项目正式采用以下数据源层级：

### 5.1 国内股票

- **主数据源**：Tushare
- **fallback**：AkShare / 新浪快照 / 本地离线库
- **本地底座**：`data/manual_history/a_share_history.sqlite`

当前状态：

- Tushare 已作为 A 股主源接入增量更新链路。
- `phase0 run` 已在启动时执行 `manual_history_update` 预检查：本地库新鲜则直接复用 SQLite，本地库落后时优先 Tushare 补齐。
- 本地库承担回测和股票池底座，避免 walk-forward 逐只在线抓取导致结果不可复现。
- `reports/phase0_data_source_report.md` 已纳入 Tushare smoke test 和 manual-history pre-run update 状态。
- AkShare 当前易受远端断连影响，但仍保留为开发/研究辅助源。

### 5.2 美股个股与 ETF

- **计划主源**：Tiingo
- **fallback**：yfinance
- **当前过渡库**：`data/us_market_history.sqlite`

当前状态：

- Tiingo 尚未接入代码。
- 当前跨市场标的已先由 `yfinance` 增量写入 US market 本地 SQLite，策略读取落库数据，避免每次评估时临时在线抓取。
- 接入任务单见：`refdocs/todo/TIINGO_IMPLEMENTATION_TASKS.md`

### 5.3 港股

- **当前状态**：预留 `data/hk_market_history.sqlite`、`hk_daily_bars`、`hk_data_source_runs` 和 CLI 命令
- **应用挂载状态**：未挂载，`hk_market_history.enabled: false`
- **候选策略记录**：`refdocs/todo/HK_A_SHARE_MAPPING_STRATEGIES.md`

当前说明：

- 港股数据源进入可生产状态前，不参与策略、报告或质量审计。
- 后续启用前必须先完成覆盖率、新鲜度、复权口径和交易日历校验。
- 港股映射 A 股策略后续按“先数据验证、再解释力测试、最后回测接入”的顺序推进。

### 5.4 宏观 / 利率 / VIX

- **计划主源**：FRED
- **fallback**：yfinance

当前状态：

- FRED 尚未接入代码。
- 接入任务单见：`refdocs/todo/FRED_IMPLEMENTATION_TASKS.md`

### 5.5 yfinance 的定位

`yfinance` 继续保留，但口径已经明确：

> **yfinance 仅作为 fallback，不再作为长期正式主源。**

现阶段例外是 `us_market_history.sqlite` 的过渡期更新仍使用 `yfinance` provider；策略读取的是本地库，不直接依赖运行时在线请求。等 Tiingo/FRED 接入后，再把对应标的迁移到正式主源。

### 5.6 当前意义

这个策略保留了旧版计划中“数据源升级”的应用导向思路：

- 不一次性推翻现有链路
- 先保证可用
- 再逐步把更正式的数据源接入主链路
- 每个源单独记录覆盖率、最新日期、拉取时间和失败原因

---

## 六、每日运行时间线

当前建议运行线：

- `16:00` A 股收盘数据采集窗口
- `16:30` 开发期本地历史库增量刷新
- 每周一 `03:30` 财务因子刷新
- `06:00` 美股收盘数据采集窗口
- `07:30` 盘前研判日报生成/投递
- `09:15 / 09:25` 集合竞价修正（可选，后续阶段）

### 当前说明

- `16:30` 的日线更新已是开发期默认操作点。
- 日线写入受 `manual_history_update.min_run_time` 保护，避免盘中快照被误写成收盘日线。
- 财务因子更新已独立为低频任务。
- 港股、CNH、A50 主要作为开盘前后风险和情绪解释层输入。

---

## 七、技术栈（当前版本）

### 7.1 当前实际选型

| 层次 | 技术 | 当前状态 |
|------|------|---------|
| 语言 | Python 3.12+ | 已用 |
| 包管理 | uv / pyproject.toml | 已用 |
| A股主数据链路 | Tushare + 本地 SQLite fallback | 已采纳主方向 |
| 开发/研究辅助源 | AkShare / yfinance | 已用，长期降级为 fallback |
| US market 跨市场库 | yfinance -> `us_market_history.sqlite` | 过渡期已接入 |
| 美股 / ETF 后续主源 | Tiingo | 计划接入，未来替换过渡 provider |
| 港股历史库 | `hk_market_history.sqlite` | 结构预留，暂不挂应用 |
| 宏观 / 利率 / VIX 后续主源 | FRED | 计划接入 |
| 数据存储 | SQLite | 已用 |
| 回测框架 | pandas + walk-forward | 已用 |
| 策略插件 | `phase0/strategies/` registry | 已用 |
| 调度 | cron / shell scripts | 已用 |
| LLM | Claude provider / DeepSeek MCP | 仅研究辅助 |
| 前端 / PWA | React / PWA / Tauri | 后续阶段 |

### 7.2 当前设计原则

- 优先做“可运行、可验证、可输出”的产品能力。
- 项目必须能独立运行，不依赖兄弟仓库源码路径或外部项目专属虚拟环境。
- 机器学习能力在中期引入，但不能破坏当前应用导向。
- 数据源升级按主源 / fallback 分层推进，不做一次性硬切。
- 策略候选必须通过统一 gate，不允许人工绕过。

---

## 八、分阶段开发计划（恢复原模板并按当前状态更新）

### 当前已完成的基础能力

以下内容已基本落地：

- 本地 A 股历史库 `a_share_history.sqlite`
- 指数元数据与指数日线库
- 股票列表、交易日历、退市清单
- `phase0.cli` 主命令集
- walk-forward 回测框架
- 候选策略 compare 输出
- `phase0/strategies/` 策略注册表
- 本地股票池构建链路
- 每日增量更新脚本
- 每周财务因子更新脚本
- 季度财务因子表接入
- Claude provider 与 DeepSeek MCP 研究辅助链路
- Tiingo / FRED 接入任务单

### Phase 0：基础验证结论（已收口）

**目标：验证数据、股票池、候选策略、walk-forward、compare、effectiveness gate 和报告链路能否闭环运行。**

#### Phase 0 结论

Phase 0 已完成基础闭环验证：

- 数据链路、股票池、策略注册表、compare、walk-forward、effectiveness gate 和报告输出均可运行。
- 候选样本治理已固化：低样本组合候选不会再因 raw score 高而直接晋级。
- 当前 selected candidate 为 `legacy_momentum_low_turnover_v1`，样本治理通过。
- 当前总 verdict 为 `PASS`，因此 Phase 0 结论是 **基础设施完成、主策略通过、可进入下一阶段收口**。

#### 当前通过结果

最新 gate 中：

- `legacy_momentum_low_turnover_v1`：`annualized_return_mean = 0.1331`
- `legacy_momentum_low_turnover_v1`：`sharpe_mean = 1.0083`
- `legacy_momentum_low_turnover_v1`：`max_drawdown_mean = -0.1042`
- `legacy_momentum_low_turnover_v1`：`win_rate_mean = 0.5110`
- `legacy_momentum_low_turnover_v1`：`turnover_annual_mean = 1.50`
- 主测试成本口径：`slippage = 0.00246`，`commission = 0.00025`，`stamp_duty_sell = 0.0005`

因此当前真实缺口变为：

1. 把账单导出从独立脚本进一步沉淀为标准 CLI / report 链路。
2. 在账户仿真层补齐 A 股整手成交、现金约束和更贴近实盘的执行假设。
3. 完成财务因子公告日 point-in-time 校验，避免后续扩展时引入未来函数争议。

#### 当前核心任务

1. 保留 `legacy_momentum_low_turnover_v1` 作为当前正式 portfolio baseline。
2. 将账单导出、资产日表、HTML 预览和买卖原因说明纳入标准研究产物。
3. 为 Phase 1 的盘前研判和模拟交易补齐账户级执行约束。
4. 在变更日志和主计划中沉淀本轮晋级结论。

#### 当前候选方向

- `legacy_momentum_low_turnover_v1`：当前主候选与正式 baseline
- `legacy_momentum`：保留为旧 baseline，用于衡量低换手改造收益
- residual / multifactor / quality-growth：保留为后续备选，不再占据当前主线

#### 当前验收口径

- `annualized_return_mean > 0`
- `sharpe_mean > 0.5`
- `max_drawdown_mean > -0.25`
- `win_rate_mean > 0.45`
- `oos_return_decay_ratio < 0.30`
- 样本治理要求：symbol-scope 候选至少 `20` 个 fold 与 `20` 个 symbol；portfolio-scope 候选至少 `4` 个 portfolio fold

这套验收标准不是在找“历史上最赚钱的策略”，而是在找：

> **有正收益、风险可控、表现较稳、样本外还能成立，并且不是由少量样本偶然支撑的策略。**

### Phase 1：形成可用的盘前研判产品（已具备进入条件）

当前可以开始进入：

- 稳定观察池输出
- `07:30` 日报流水线强化
- 更稳定的本土主策略正式化
- 跨市场 overlay 与盘前解释层完善
- 主源与 fallback 的长期运行治理

### Phase 1.5：引入机器学习增强，但保持产品导向

该阶段不是做学术平台，而是做**能提升产品可用性的 ML 增强**：

- 接入 sklearn 基线模型
- 用 ML 做辅助排序或过滤
- 记录预测与实际结果
- 用更稳的方式提升选股与观察池质量

### Phase 2：数据源升级与产品扩展

此阶段重点：

- FRED 接入宏观 / 利率 / VIX 主链路
- Tiingo 接入美股个股 / ETF 主链路
- yfinance 退化为 fallback
- 强化盘前日报与解释层
- 逐步评估 Dashboard / PWA / 桌面端

### Phase 3：组合与账户仿真增强（后续）

以下内容保留为中后期路线图：

- 组合权重分配
- 简化组合风险约束
- 账户级仿真
- 更系统的模型评估记录

注意：

> 这些能力未来可以引入，但不应挤占当前“先做出可应用产品”的主线。

---

## 九、安全与合规

### 9.1 密钥与环境变量

- `.env` 不入库
- `.codex/claude_agent.local.json` 不入库
- `.claude/settings.local.json` 不入库
- `.mcp.json` 不入库
- Token / SMTP / API Key 不硬编码
- 生产环境采用 secret 注入

### 9.2 操作审计

- 信号/报告/调度执行写入日志
- 数据源更新写入 `market_data_source_runs`
- 策略变更写入 `reports/phase0_strategy_change_log.md`
- 关键步骤保留版本信息
- 日志保留不少于 90 天

### 9.3 LLM 使用边界

LLM 允许：

- 摘要提取
- 报告润色
- 研究辅助
- 因子构思辅助
- 第二意见和反方审查

当前接入形态：

- Codex 侧 Claude provider 配置统一放在 `.codex/`
- DeepSeek MCP 作为 Claude/外部 agent 的研究辅助工具
- OpenClaw Gateway 可作为外部 agent / 调度入口，用于研究摘要、消息通道和跨工具编排；接入说明见 `refdocs/OPENCLAW_GATEWAY_AGENT.md`
- 不把 LLM 放入主信号层

LLM 禁止：

- 直接生成交易信号
- 修改因子权重
- 输出交易指令
- 跳过 effectiveness gate

---

## 十、期货数据在研判中的角色

当前只作为：

- 盘前情绪信号
- 外资预期代理
- 风险解释输入

不用于：

- 直接对冲执行
- 主策略排序
- 自动下单

---

## 十一、项目目录结构（当前视角）

当前重点目录：

```text
stok-mapping/
├── CLAUDE.md
├── DEVELOPMENT_PLAN.md
├── README.md
├── config.yaml
├── pyproject.toml
├── phase0/
│   ├── cli.py
│   ├── data_sources.py
│   ├── local_history.py
│   ├── update_history.py
│   ├── universe.py
│   ├── walk_forward.py
│   └── strategies/
├── reports/
├── refdocs/
│   ├── papers/
│   ├── todo/
│   └── OUTLOOK/
├── data/
├── scripts/
├── .codex/
└── logs/
```

未来计划中的更大规模分层结构可以保留为中长期目标，但当前不应为了“架构好看”而牺牲快速形成可用产品的速度。

---

## 十二、部署方案

### 当前建议

- 开发/研究阶段：WSL / 本机运行
- 统一命令入口：`phase0.cli`
- Python 环境：项目内 `.venv`
- 调度：本地 cron + shell script
- 后续如需部署：Docker Compose 统一打包

### 当前已落地调度

- 交易日 `16:30`：`scripts/update_manual_history_daily.sh`
- 每周一 `03:30`：`scripts/update_financial_factors_weekly.sh`

---

## 十三、关键决策记录（当前有效）

| 决策项 | 当前选择 | 原因 |
|--------|---------|------|
| 产品定位 | 量化研究与风险提示工具 | 避免误导为自动交易系统 |
| 当前主线 | 本土因子主导，跨市场 overlay | 回测与文献共同支持 |
| 当前领先候选 | `legacy_momentum_low_turnover_v1` | 当前 Phase 0 selected candidate，effectiveness gate 已通过 |
| 当前 baseline | `legacy_momentum_low_turnover_v1` | 低换手 portfolio baseline，便于后续模拟账单和账户仿真 |
| 跨市场映射 | 仅做 overlay | 直接做 ranker 效果弱 |
| 国内股票主源 | Tushare | 已正式采纳 |
| 国内 fallback 基座 | 本地 SQLite / AkShare / 新浪 | 最稳、可控、可补位 |
| US market 过渡库 | `us_market_history.sqlite` | 当前已替代运行时 yfinance 临时抓取 |
| 美股/ETF 主源方向 | Tiingo | 比 yfinance 更适合长期主链路 |
| 港股库 | `hk_market_history.sqlite` | 当前预留，生产化后再挂应用 |
| 宏观/利率/VIX 主源方向 | FRED | 更适合正式主链路 |
| yfinance | 仅 fallback | 保留低摩擦备用价值 |
| 财务因子 | 已接入，但历史回测前需 PTI 校验 | 防未来函数 |
| LLM | 仅研究辅助，不直接产出交易信号 | 保持可解释和可控 |
| 当前优先事项 | 完成策略收口、账户仿真约束与 PTI 校验 | 当前 gate 已通过，下一步是把策略变成稳定的研究与模拟产物 |

---

## 十四、当前一周执行摘要

> 当前统一周执行附件见：`refdocs/todo/WEEKLY_EXECUTION_CHECKLIST.md`

### 本周目标

围绕 A 股本土主因子完成一轮低换手改造验证，正式确认新候选替代旧 baseline，并补齐账单导出与解释性产物。

### 本周已完成

- `legacy_momentum` 已从 symbol-scope 改为 portfolio-scope baseline。
- 回测窗口已从 `5` 年扩大到 `7` 年，portfolio 候选均达到 `4` 个 fold。
- 财务因子历史已扩展到 `32` 个季度，覆盖 `2018-06-30` 至 `2026-03-31`。
- 已新增成本敏感性报告，输出 current / low-slippage / zero-cost 三档。
- 主测试已改为默认 `slippage = 0.00246`，成本敏感性测试已改为单独 CLI 路径，需显式指定场景运行。
- 已修复财务因子 point-in-time merge 的 datetime dtype 边界问题。
- 已新增 `legacy_momentum_low_turnover_v1`，并通过完整 Phase 0 gate。
- 已生成低换手策略账单 CSV、资产日表和 HTML 预览。
- 已将低换手策略连续 OOS 报表改为内嵌 CSS 的 HTML 文件。
- 已为账单导出脚本增加行情面板缓存，减少重复生成账单时的行情加载和对齐成本。
- 已在通过策略和回测关键代码块补充中文注释。
- 已完成账户级仿真 v2，覆盖成交价口径、整手、现金、涨跌停、停牌、流动性参与率、未成交原因和真实账户 CSV 对账预留。
- 已将 `execution-gate` 与 `oos-report` 做成 profile 化管线，支持 `research` / `live` 两类参数组合。
- 已统一 HTML 报表展示规范：生成时间、横向滚动、纵向滚动、固定表头。

### 本周候选方向

1. **低换手 legacy momentum 改造并正式替代旧 baseline**
2. **账单 / 资产轨迹 / 买卖原因导出标准化**
3. **账户级仿真与实盘约束补齐**
4. **公告日 point-in-time 校验与日报接入**

### 推荐实施顺序

从治理风险看：

1. 样本覆盖门槛与 portfolio 口径已完成，继续保持为强制治理。
2. 当前先围绕 `legacy_momentum_low_turnover_v1` 做解释链路和账户仿真收口。
3. residual / multifactor-volume-price 暂时降为备选，等主线收口后再继续精修。

### 本周成功标准

- compare mode 不再混用 symbol-scope 与 portfolio-scope 结果
- 至少一个 portfolio 候选在足够 fold 覆盖下通过 gate
- `sharpe_mean > 0.5`
- `max_drawdown_mean > -0.25`
- `win_rate_mean > 0.45`
- current-cost 与 low-slippage 场景差距可解释，且不是完全依赖零成本才有效
- 变更日志有清晰晋级或失败原因

---

## 十五、下一步行动

### 当前最高优先级

- [x] 为候选选择加入最低 fold 数 / symbol 覆盖 / 样本支持约束
- [x] 重跑 Phase 0，确认低样本 `quality_growth_price_v1` 不再直接晋级
- [x] 扩展 portfolio 候选的有效 fold 覆盖
- [x] 保持 compare / report / gate / change log 同口径输出
- [x] 加入成本敏感性报告，区分信号无效和成本吞噬
- [x] 将主测试默认滑点更新为 `0.00246`
- [x] 将成本敏感性测试拆成显式 CLI 路径，避免每次主测试自动跑压力场景
- [x] 将财务因子历史扩展到 32 个季度
- [x] 修复财务因子 point-in-time merge 的 datetime dtype 边界问题
- [x] 优先修复 Sharpe 缺口
- [x] 设计低换手 / 延长持有 / slippage-aware 参数选择方案
- [x] 跑完整 Phase 0，正式确认 `legacy_momentum_low_turnover_v1` 替代 `legacy_momentum`
- [x] 生成低换手策略账单 CSV、资产日表与 HTML 预览
- [x] 为账单导出脚本增加行情面板缓存与 `--refresh-cache` / `--no-panel-cache` 控制
- [x] 在通过策略和回测代码补充中文注释
- [x] 在财务因子历史回测前完成公告日 point-in-time 校验方案设计
- [x] 将账单导出纳入标准 CLI / report 链路
- [x] 增加 A 股整手成交、现金约束和账户级撮合细节
- [x] 将当前 selected strategy 接入 `07:30` 盘前日报 / 观察池输出
- [x] 补连续样本外资金曲线验证，消除 walk-forward 分折重置造成的误读
- [x] 生成“连续 OOS 资金曲线 + 基准对比 + 各 fold 收益分解”HTML 报表
- [x] 补行情分段验证，区分顺风行情、震荡行情和回撤阶段的表现
- [x] 推进账户级仿真 v2：成交价口径、涨跌停、停牌、流动性、未成交原因和真实账户对账预留
- [x] 将 `execution-gate` 参数 profile 化，区分策略研究与实盘仿真回测
- [x] 将 `oos-report` 参数 profile 化，保持与 `execution-gate` 相同的 `research` / `live` 逻辑
- [x] 统一 HTML 报表展示体验：生成时间、横纵滚动、固定表头

### 条件满足后再推进

- [x] 将 Tushare 纳入 Phase 0 数据源 smoke test 与 pre-run update 链路
- [x] 新增 `us_market_history.sqlite`，让当前跨市场 overlay 从落库数据读取
- [x] 预留 `hk_market_history.sqlite`，但在港股数据源生产化前不挂应用
- [ ] 完成 Tushare 主源长期稳定性验证与源审计闭环
- [ ] 执行统一周执行附件中的数据源升级计划
- [ ] 优先引入 FRED 作为宏观 / 利率 / VIX 主源
- [ ] 再引入 Tiingo 作为美股个股 / ETF 主源
- [ ] 保留 `yfinance` 作为 fallback，不做一次性全替换
- [ ] 强化 `07:30` 盘前日报自动生成链路，并形成每日可复盘归档
- [ ] 精修映射标的池与行业层分析
- [ ] 补全港股映射 A 股候选策略代码，前置条件是港股历史数据源质量验证通过
- [ ] 在不破坏当前应用导向的前提下，引入 sklearn 基线模型辅助策略研究

---

## 附：核心参考文件

- `README.md`
- `CLAUDE.md`
- `config.yaml`
- `refdocs/PROJECT_ARCHITECTURE_OVERVIEW.md`
- `reports/phase0_effectiveness_report.md`
- `reports/phase0_walk_forward_report.md`
- `reports/phase0_strategy_change_log.md`
- `data/universe/local_factor_universe_report.md`
