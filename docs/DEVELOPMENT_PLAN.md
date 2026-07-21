# 跨市场量化研判与选股系统 · 开发计划书

> 项目名称：stok-mapping  
> 创建日期：2026-05-28  
> 最后修订：2026-07-21（补充多模拟账户静态控制台与账户级交付链路；Daily Brief P0 内容模型完成，P1 renderer 待独立接入）
> 状态：**Phase 0 工程链路可用；严格 qfq_asof / admission 口径下当前无可用于 paper review 或实盘模拟的合格策略，当前目标转为找到至少一个适合当前市场环境、可指导个人实盘操作决策且具备较可观盈利潜力的合格量化策略，并逐步形成覆盖不同市场环境 / 风格的量化策略池与策略选择方法论**
> 法律声明：本工具定位为**个人自用的量化研究、风险提示与交易计划辅助工具**。系统可以基于策略引擎、风控约束和账户仿真生成可交易信号、调仓建议单和模拟订单，但不提供对外投资建议、荐股服务或自动下单指令。使用者应独立判断并承担全部交易风险。  
> **边界声明：本系统仅供个人研究和自用决策辅助，不对外提供投资建议或商业服务。**

---

## 当前项目状态摘要

### 当前阶段

项目已完成一轮 **Phase 0 工程链路验证**，但 `qfq_asof` 严格价格口径复核已经改变策略结论：

- Phase 0 基础设施已验证可用
- 本地历史库、股票池、walk-forward、候选比较链路已落地
- 历史回测已默认启用 point-in-time 股票池：每折按训练窗口结束日只读生成股票池，避免当前股票池污染过去样本
- `T1.4` A 股历史 as-of 前复权与复权因子治理已完成，当前审计结论为 `PASS`
- 已完成 `qfq_current` / `qfq_asof` 差异报告、主策略对照回测和最新版本全候选池 `qfq_asof` compare
- 最新严格结论：当前无可用于实盘模拟的合格 candidate；旧 `qfq_current` 结果只能作为兼容口径参考
- 策略层已拆为 `phase0/strategies/` 注册表结构
- 候选样本治理已固化，当前 compare 已统一为 portfolio 口径
- 当前没有可进入实盘模拟的 selected candidate；`legacy_momentum_low_turnover_v1` 降级为兼容基线和动量 sleeve 研究样本
- 主测试默认成本口径已切换为 `slippage = 0.00246`，用于更贴近普通个人实盘执行假设
- 成本敏感性测试已从 `phase0 run` 中拆出，必须通过单独 CLI 显式指定场景再运行
- 连续 OOS 资金曲线与沪深300基准对比报表已生成，已纠正 walk-forward 分折重置带来的阅读偏差
- 账单导出已接入正式 CLI / report 链路，`phase0 run` 会同步生成账单、日资产表和 HTML 预览
- 账户级账单已补齐 A 股 `100` 股整手成交、现金约束、卖出回款、最低佣金、过户费、最小成交金额、T+1 可卖库存和交易成本字段
- 账户级仿真 v2 已补齐 `execution.price_mode`、ST / 新股特殊涨跌停、普通涨跌停、停牌、流动性参与率、未成交原因和真实账户 CSV 对账预留
- `execution-gate` 与 `oos-report` 已支持 `research` / `live` profile，标准参数组合统一由 `config.yaml` 管理，脚本不再内置 profile 默认数值；profile 控制执行假设，股票池时点边界由 `universe.point_in_time_for_backtest` 单独控制
- 行情分段验证已生成 HTML / CSV 报告，用于区分顺风行情、震荡和回撤阶段表现
- 财务因子 PTI 校验已生成独立报告，当前结论为 `PASS`
- `T2.4` 策略过拟合诊断工具只读 MVP 已落地，当前可基于现有 walk-forward 产物输出 CSV / Markdown 过拟合风险报告
- `T2.1` Phase 0 候选策略池已从“候选扩张/晋级清单”修订为“策略池治理清单”：以 `baseline_admission_all_v1` 统一管理 13 个候选，当前无 `admission_pass_candidate`，候选按 `active_research`、`baseline`、`failure_sample`、`research_only`、`deferred` 等状态治理
- `T2.8` strategy-admission 已成为策略池治理主入口：配置层 `baseline_admission_all_v1` 已包含当前 13 个候选；main 上已落盘的全候选 admission 仍需重跑以纳入 `sleeve_composite_v1` 与 `sleeve_composite_low_churn_v1`，当前 sleeve 证据来自 scoped admission 与后续低 churn 诊断实验。准入口径统一要求 `qfq_asof`、窗口 preset、过拟合、行业集中和因子诊断；账户执行诊断已默认接入 compare/admission 矩阵，execution gate / brief 仍作为独立执行复核入口
- `T2.10.1` 规则型 `sleeve_composite_v1` 已完成 scoped admission 与治理报告，结论为 `reject`；该策略保留为 research-only 诊断候选，不进入 paper review、模拟账户、日报或 watchlist
- 行业集中度 100% universe 专项实验已在分支 `codex/industry-weight-100-universe-experiment` 完成并落盘；main 尚未合入该实验产物。实验结论为 research-only，取消 universe 行业上限未产生可准入策略，主线默认仍保留 universe 层行业分散约束
- `INT-KMS-001` A 股个股行情影响因子全景图已通过情报采集器入库，并与 marklogseq HTML 结构化知识整合为项目可用知识资产；其中“因子传导逻辑图（从定价公式到六域关系矩阵）”被采纳为 `T2.13` 因子本体、特征注册与市场环境归因的理论框架，定位为只读元数据和诊断层，不直接作为 alpha 公式或因果证明
- `T1.5` Tushare 财务因子逐股票历史补齐已完成并验收：2016Q1-2018Q1 目标季度末无 pending/failed，`financial-pti` 复核为 PASS，`factor-effectiveness` 已重跑
- `T6.2` 数据库健康检查只读 MVP 已落地，新增 `phase0.cli db-health`，可输出 CSV / Markdown 报告并按 `--fail-on` 作为调度或 CI 门禁
- `T6.3` 数据治理与维护编排器专项已完成关键收口项：`maintain supervise`、交易日历判断、维护状态 Markdown 报告、backfill 报告索引和只读 `system status` 汇总入口已落地，继续作为统一本地控制平面演进
- Python 架构整理已完成一轮 main 集成：数据源 provider 统一归入 `phase0/data_access/providers/`，数据更新、回填、审计归入 `phase0/data_governance/`，策略研究归入 `phase0/research/`，CLI 只保留路由和参数解析；旧根路径兼容 wrapper 已清理或降级为兼容入口，新代码不得继续依赖旧入口
- 报告目录治理已明确：`reports/` 根目录只保留 `archive/`、`runs/`、`database_health/`、`strategy_admission/`、`phase0/`、`strategy_governance/` 和 `README.md`；常规运行产物、日志和 SQLite 数据库作为本地资产维护，不随远端 Git 同步
- `brief daily` / `brief watchlist` 已成为当前日报与阶段试用观察池主入口，旧 `daily-brief` / `premarket` 入口仅保留兼容
- `07:20` 统一调度器已接入 `brief watchlist`，生成 `reports/watchlist_today/index.html` 并同步到远端 `/brief/`；模拟账户确认账单生成后会镜像到 `reports/account_bill_today/index.html` 并同步到远端 `/account-bill/`
- 多模拟账户静态控制台已新增 `/quant/` 发布链路：`site build/sync/publish` 从所有 enabled 模拟账户读取账户级 latest watchlist、account-bill 和 SQLite 账本，生成 `reports/static_site/quant/`，远端同步只允许落到 `/var/www/spidermanread/quant/`
- Watchlist HTML 产物已从 Python 字符串拼接迁移为 Jinja2 模板渲染，样式拆到独立 `watchlist.css`，视觉与交互按 `/brief/ui-test/` 参考样例对齐；`reports/runs/latest/watchlist/`、`reports/watchlist_today/` 和远端 `/brief/` 均按 HTML + CSS bundle 同步
- 模拟账户已接入 SQLite 主账本 `data/simulated_trading/simulated_accounts.sqlite`，当前按已确认 OHLCV 交易日写入资产、成交和持仓记录
- 正式 `daily brief` 仍需从阶段试用 watchlist 兼容产物中独立出来；已新增 `T6.6` 作为内容模型、页面结构、数据契约和生成代码拆分的专项任务
- 目录治理已明确：`reports/` 存程序产物，`logs/` 存机器运行日志和调度状态，`memory/` 存人工会话归档、关键决策和历史计划快照
- `07:30` 盘前观察池已接入 CLI，按最近交易日信号输出持仓、候选、权重、观察理由、模拟账户快照和风险提示
- HTML 报表体验已统一：标题右侧显示生成时间，宽表按 `96vw` 横向滚动，长表按 `70vh` 纵向滚动，表头固定
- 当前主阻塞点是**在 qfq_asof / PIT 股票池 / 成本后 / admission 口径下，把策略研发收敛到双北极星目标：先找到至少一个适合当前市场环境、可指导个人实盘操作决策且具备较可观盈利潜力的合格策略；同时把候选池沉淀为覆盖不同市场环境 / 市场风格的量化策略池，并形成策略选择方法论**。短期优先路线是复核低波低换手质量主线、拆解行业集中、参数不稳定与相对基准跑输原因、降低组合换手和 churn，而不是继续堆叠高换手价格行为策略

### 策略研发双北极星目标

当前策略研发的目标不是扩充候选数量，也不是寻找历史回测最优曲线，而是同时服务两个北极星目标：

1. **当前市场突破策略**：找到至少一个适合当前市场环境、能够指导个人实盘操作决策、并在成本后具备较可观盈利潜力的量化策略。
2. **策略池与策略选择方法论**：形成一个覆盖不同市场环境和市场风格的量化策略池，并沉淀一套可复查、可执行、可迭代的策略选择方法论，用于回答“当前市场该选用、降权、停用或观察哪类量化策略”。

该目标必须同时满足工程与风控边界：

- 策略必须在 `qfq_asof`、point-in-time 股票池、当前交易成本、walk-forward / admission、过拟合诊断、行业集中和执行可行性约束下成立。
- “较可观盈利”以可复核的年化收益、风险调整收益、回撤、换手、正收益折比例、相对基准表现和模拟 / 实盘偏差复盘综合判断，不承诺未来收益。
- 策略池不是候选堆积；每个入池策略都必须有市场环境标签、风格标签、相对基准表现、失败模式和启用 / 降权 / 停用条件。
- 策略选择方法论至少要覆盖：市场环境识别、市场风格判断、策略适配矩阵、策略优先级、冲突处理、启用 / 降权 / 停用规则，以及事后复盘如何更新方法论。
- 未通过 admission 的候选只能用于 research-only 诊断，不进入 paper review、模拟账户、日报或 watchlist 正式链路。

### 当前主线

> **A 股本土因子为主，跨市场信号仅做风险/情绪 overlay。**

跨市场映射仍然重要，但当前不再作为主选股 ranker，而是用于：

- 隔夜情绪解释
- 风险缩放
- 开盘情景推演
- 盘中情绪验证

### 当前选中候选与门槛状态

根据 `reports/phase0_effectiveness_report.md`（生成时间：2026-05-31 18:59:23，主测试 `slippage = 0.00246`）及后续严格 `qfq_asof` 复核：

- 当前 selected candidate：无
- 当前总 verdict：Phase 0 工程链路可用，但严格策略门禁未通过
- 样本治理状态：旧 `qfq_current` 口径下曾出现 `selected_candidate_eligible = True`，现仅保留为历史兼容参考
- 样本覆盖：`4` 个 portfolio fold
- 关键变化：旧 `qfq_current` 口径下低换手改造曾全部过线；经严格 `qfq_asof` 复核后，`legacy_momentum_low_turnover_v1` 已降级为兼容基线与研究样本

当前 gate 结果：

| 指标 | 当前值 | 门槛 | 状态 |
|------|--------|------|------|
| `selected_candidate_eligible` | 旧 `qfq_current` 为 `True`；当前严格口径不适用 | `True` | 历史兼容参考 |
| `annualized_return_mean` | `0.1331`（旧 `qfq_current`） | `> 0` | 历史兼容参考 |
| `sharpe_mean` | `1.0083`（旧 `qfq_current`） | `> 0.5` | 历史兼容参考 |
| `max_drawdown_mean` | `-0.1042`（旧 `qfq_current`） | `> -0.25` | 历史兼容参考 |
| `win_rate_mean` | `0.5110`（旧 `qfq_current`） | `> 0.45` | 历史兼容参考 |
| `oos_return_decay_ratio` | `-2.4116`（旧 `qfq_current`） | `< 0.30` | 历史兼容参考 |

解释：

- 所有候选已统一为 `portfolio` 口径，避免 symbol-scope 与 portfolio-scope 混排。
- 回测窗口已扩大到 7 年，使 portfolio 候选均达到 `4` 个 fold 的最低治理门槛。
- `legacy_momentum_low_turnover_v1` 曾在旧 `qfq_current` 口径下替代旧 `legacy_momentum` 成为主候选；经严格 `qfq_asof` 复核后已降级为兼容基线。
- 低换手、宽持有区间、较慢调仓与换手惩罚显著降低了年化换手：`13.48 -> 1.50`。
- 在 `base_research_cost`、`main_personal_execution`、`stress_slippage_0_003`、`stress_slippage_0_005` 等场景下，低换手候选仍是主要有效候选；但成本敏感性属于单独验证路径，不再混入每次主测试。

### 当前工作重心

当前阶段最优先的是：

1. 固化 `legacy_momentum_low_turnover_v1` 的解释链路，保持 report / gate / bill / 变更日志口径一致。
2. 维护账单、资产轨迹、买卖原因和策略参数的标准 CLI / report 链路。
3. 维护账户级仿真 v2，并在后续真实账户复盘时接入本地持仓 / 成交回报 CSV 对账。
4. 维护 `research` / `live` profile 的参数治理，确保策略研究口径和实盘仿真口径分离。
5. `T1.5` Tushare 财务因子逐股票历史补齐已完成；后续只保留例行增量维护和非目标 period 任务表清理，不再阻塞策略重建。
6. 将 `T6.2` 数据库健康检查接入调度前置门禁，先用只读报告和 `--fail-on` 控制失败退出，不默认写健康状态表。
7. 推进 `T6.3` 数据治理与维护编排器专项：状态库、真实 tick、wrapper 接管、长 backfill 分片监督、状态报告、报告索引和 `system status` 只读汇总入口已落地；下一步转向 System Orchestrator 的 `run/tui` 边界设计和 TUI/桌面概览入口。
8. 将 `T2.4` 策略过拟合诊断工具继续接入策略治理链路，下一步进入 gate / brief / 模拟账户准入检查。
9. 基于已通过的财务因子 PTI 校验和财务历史回填结果，谨慎恢复质量成长 / 多因子后续验证。
10. 在没有新合格 candidate 前，盘前观察池和账户级仿真只保留兼容基线能力；`Signal & Rebalance Engine` 的正式接入需等待策略通过 admission、行业集中审计和执行诊断后再推进。
11. 维护已接入调度器的阶段试用观察池日报链路，并继续补齐交易日历、失败重试和正式 daily brief 独立产物。
12. 新闻源独立于 Tiingo 日线适配器推进，并演进为统一文本事件数据层；短期先做 provider probe、字段标准化和事件审计，不把新闻直接接入主 ranker。

当前**不是**优先做的事：

- 再盲目堆叠新的主候选策略
- 扩展跨市场主 ranker
- 让 LLM 直接参与交易决策
- 把账户级仿真结果误解为实盘可自动下单
- 绕过策略 gate、风险预算或可成交性检查直接生成调仓动作
- 因为策略已通过 effectiveness gate 就跳过过拟合诊断、参数稳定性和收益集中度检查
- 在未完成 `T1.4` 审计前，把当前全历史前复权 `qfq_current` 结果解释为严格 point-in-time 价格结果
- 因为 universe 层行业限制放宽实验能运行，就同步放宽策略层行业审计阈值或跳过行业集中治理

### 严格门禁通过后的执行顺序

这是待 Phase 0 严格门禁通过后的条件性开发顺序；在出现新的合格 candidate 之前，不预设当前已通过：

| 优先级 | 任务 | 现在做它的理由 | 完成标准 |
|------|------|------|------|
| `P0` | 将账单导出纳入正式 `CLI / report` 链路 | 当前账单、日资产表和 HTML 预览需要固化为标准产物，后续验证、归档和日报才能共用同一口径。 | 已完成。`phase0 run` 与 `phase0 bill` 可稳定生成账单、日资产表和 HTML 预览。 |
| `P0` | 增加 A 股整手成交、现金约束和账户级撮合细节 | 当前回测更偏目标权重层，距离真实 A 股账户执行还有差距；不补这层，账单的实盘参考价值有限。 | 已完成。账单体现 `100` 股整手、买入受现金限制、卖出回笼现金，以及现金/持仓/总资产联动。 |
| `P1` | 账户级仿真 v2：A 股真实交易约束增强 | 当前账单已完成账户级 v1，但仍缺次日开盘/保守成交价、涨跌停、停牌、流动性和未成交记录。 | 已完成。账单能展示全部成交、部分成交、未成交及原因；盘前观察池显示执行风险提示；真实账户 CSV 对账格式已预留。 |
| `P1` | 区分策略研究与实盘仿真 profile | 同一策略在研究口径和接近实盘口径下参数不同，混用会导致报告不可比较。 | 已完成。`execution-gate` 与 `oos-report` 支持 `--profile research/live`，并从 `config.yaml` 读取参数组合。 |
| `P1` | 统一 HTML 报表展示规范 | 报表需要适合人工复核，长表和宽表必须可读、可滚动、可定位生成时间。 | 已完成。所有现有 HTML 与生成脚本已补生成时间、横纵滚动和固定表头。 |
| `P1` | 完成财务因子公告日 point-in-time 校验方案 | 后续质量成长、多因子扩展都依赖财务字段，必须先封住未来函数争议。 | 已完成。`reports/phase0_financial_pti_report.html` 当前结论为 `PASS`。 |
| `P1` | 将未来通过严格门禁的 candidate 接入 `07:30` 盘前日报 / 观察池输出 | 只有在严格 `qfq_asof` 门禁通过后，候选才应进入日常使用链路，而不是只停留在回测报告。 | 当前无 selected candidate；现有 `brief daily` / `brief watchlist` 仅保留旧 `qfq_current` 兼容基线输出能力，待未来重新产生合格 candidate 后再切入正式日常链路。 |
| `P1` | 策略过拟合诊断工具 MVP | gate 通过只能说明当前指标达标，不能说明参数、样本、成本和收益来源稳定。必须把过拟合风险作为策略准入治理项。 | MVP 已完成。`phase0.cli overfit-diagnostic` 可基于现有 walk-forward 产物输出 CSV 和 Markdown 诊断报告；HTML 和流程集成待做。 |
| `P1` | A 股历史 as-of 前复权与复权因子治理 | 当前默认 `qfq_current` 价格可能使用全历史复权因子，需确认价格特征是否受到未来分红送转信息污染。 | 因子治理 MVP 已完成。当前库有 `bfq/qfq/market_adj_factors`，审计为 `PASS`；2026-06-04 已执行 Tushare 历史补全，`market_adj_factors` 覆盖 2016-01-04 到 2026-06-04，`market_daily_basic` 覆盖 2016-01-04 到 2026-06-03。 |

补充约束：

- 在上述四步完成前，不把 residual / multifactor 等备选策略重新拉回主线。
- `FRED` / `Tiingo` 数据源升级继续保留，但优先级低于当前策略重建与准入治理工作。
- 新闻源扩展作为 `T1.3` 独立任务，不归入 Tiingo EOD 接入；后续重点转为公告、研报、新闻、政策和快讯的统一文本事件数据层，不直接生成交易信号。

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
- gate 通过不能替代过拟合诊断；策略还必须检查参数邻域稳定性、fold 稳定性、成本敏感性和收益集中度
- LLM 更适合做摘要、整理、研究辅助和反方审查，而不是直接决定交易信号

### 1.3 论文与研究报告依据

以下内容是本项目功能设计与策略扩展的重要理论依据：

- `refdocs/papers/cn/cn_INDEX.md` 索引的中文 A 股论文资料
- `refdocs/papers/en/INDEX.md` 索引的英文/国际论文资料
- `knowledge/intelligence/strategy_intelligence_ledger.csv` 维护的投资策略情报台账，以及 T5.2 已建立的 RAG-ready Markdown / CSV 语料规范、核心情报 note、情报转任务草案和月度扫描机制
- `knowledge/intelligence/notes/INT-KMS-001_a_share_factor_panorama.md` 与 `knowledge/intelligence/wiki/a_share_factor_data_interface_knowledge_asset.md`：本地 Logseq “A 股个股行情影响因子全景图”和 marklogseq HTML 结构化接口知识资产，用于补齐 A 股因子全景、数据接口索引和后续因子本体设计依据
- `docs/PROJECT_ARCHITECTURE_OVERVIEW.md`：T2.13 因子传导图工程化必须遵循该架构文档中“研究情报层 -> 股票池与特征层 -> 策略治理层 -> 交付与运维层”的分层边界
- `docs/tasks/strategy/PHASE0_CANDIDATE_STRATEGIES.md`
- `reports/phase0_strategy_change_log.md`
- `reports/phase0_walk_forward_report.md`
- `reports/phase0_effectiveness_report.md`

这些资料用于：

- 选择可落地的候选策略方向
- 约束架构扩展顺序
- 判断哪些 ML / 多因子 / 量价 / 文本思路值得优先进入产品
- 记录每次策略参数和逻辑调整的理由
- 维护“情报来源 -> 策略假设 -> 候选任务 -> 实验结果”的可追溯链路
- 每月复核近 30 天新增量化策略情报，筛出可验证策略假设、数据建设需求和反方证据，并同步 RAG manifest / 月扫索引 / wiki ingest log
- 将“因子传导逻辑图”转化为可审计的因子本体、特征注册和市场环境归因元数据，先服务 `factor-effectiveness`、`strategy-admission`、失败归因和报告解释，不直接替代策略回测或准入判断

### 1.4 当前交叉结论

结合文献、项目内回测和数据可用性，当前最重要的结论是：

> **跨市场映射适合作为 overlay，不适合作为当前阶段主 ranker。**

因此项目主线已经调整为：

> **本土主因子选股 + 跨市场风险缩放 / 情绪解释 + 严格 effectiveness gate 治理。**

补充结论：

> **“股价变化 = 未来现金流预期变化 + 折现率/风险溢价变化 + 资金供需变化 + 信息事件冲击 + 交易制度与微观结构放大”可作为项目因子体系的理论分解框架，但不能直接作为交易 alpha、因果证明或准入豁免条件。**

工程含义：

- 该框架用于定义因子域、影响通道、数据来源、可见时间、使用位置和验证状态
- 可先进入研究情报层、股票池与特征层、策略治理层的元数据和诊断报告
- 任何具体因子进入策略主 ranker 前，仍必须通过 as-of 可见性、覆盖率、样本外、成本后和 admission 验证

---

## 二、系统定位

本项目是一个：

> **A 股本土因子为主、跨市场风险/情绪 overlay 为辅的个人量化研究、盘前研判与交易计划辅助工具。**

它不是通用量化平台，也不是自动交易系统。系统允许输出经过规则验证的可交易信号和调仓建议单，但这些输出必须来自策略引擎、风险预算、可成交性模型和账户级仿真，不允许由 LLM 直接生成。

### 当前目标

输入多市场数据后，输出：

- A 股盘前情景推演
- 观察池
- 可交易信号
- 调仓建议单
- 模拟订单和阻断原因
- 风险暴露说明
- 失效条件
- 候选策略对比结论
- 策略有效性验证报告

### 输出边界

所有输出统一使用以下研究与交易计划语言：

- 观察池
- 风险暴露
- 信号等级
- 情景推演
- 失效条件
- 策略验证结果
- 可交易信号
- 目标权重
- 调仓建议单
- 模拟订单
- 阻断原因

明确禁止：

- 强买入
- 清仓
- 满仓
- 荐股
- 自动下单指令
- LLM 直接生成交易信号
- LLM 直接生成调仓建议

### 输入 / 输出全景

```text
输入层                      分析引擎层                         输出层
────────────────────────────────────────────────────────────────────────────
美股/ETF/宏观 → 跨市场风险/情绪 overlay ─┐
港股/A50/CNH  → 盘前与盘中情绪验证       ├→ 观察池 / 风险暴露 / 情景推演
A股日线/财务  → 本土主因子引擎           ├→ 可交易信号 / 调仓建议单 / 模拟订单
当前持仓/现金 → 账户与风控约束           ├→ 候选策略 / 组合候选 / 信号等级
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
- US market 当前 provider 仍为 `yfinance`，但定位是过渡数据源；Tiingo 已完成美股个股 / ETF EOD 最小接入和连通性检查，后续再评估是否接管 `us_market_history` 对应标的；FRED 已完成宏观 / 利率 / VIX 最小接入。
- 港股库 `data/hk_market_history.sqlite` 仅保留结构和 CLI，当前 `enabled: false`，等港股数据源接入并通过覆盖率/新鲜度验证后再挂到应用。
- 港股映射 A 股候选策略已记录到 `docs/tasks/cross-market/HK_A_SHARE_MAPPING_STRATEGIES.md`，后续补全代码；当前先做数据层验证，不并入 Phase 0 主线。

### 引擎 #2：本土主因子选股

作用：

- 作为当前主策略验证核心
- 决定候选池与排序主逻辑
- 生成可进入观察池的 A 股候选

当前配置层候选集合：

- `legacy_momentum`
- `legacy_momentum_low_turnover_v1`
- `ma_kline_baseline_v1`
- `residual_momentum_reversal_v1`
- `residual_momentum_reversal_v2`
- `quality_growth_price_v1`
- `low_vol_low_turnover_quality_v1`
- `quality_low_turnover_monthly_v1`
- `multifactor_volume_price_filter_v1`
- `core_selection_quality_momentum_v1`
- `theme_exposure_momentum_v1`
- `sleeve_composite_v1`
- `sleeve_composite_low_churn_v1`

当前重点：

- 以上 13 个策略已进入 `config.yaml` 的 `compare_strategies` 与 `baseline_admission_all_v1` 配置集合。
- main 上仍需按当前 13 个候选集合重跑全量 admission，并把治理报告落盘到标准报告目录；当前没有通过严格准入的 selected candidate。
- `legacy_momentum` / `legacy_momentum_low_turnover_v1` 仅作为 baseline 或研究样本保留，新候选不能仅凭少量 fold 的高分晋级。

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

### 4.0 因子传导图工程化原则（T2.13）

`INT-KMS-001` 中的“因子传导逻辑图（从定价公式到六域关系矩阵）”被采纳为项目因子体系的工程化理论基础，但其角色是**本体与诊断框架**，不是直接交易公式。

架构位置必须参考 [`docs/PROJECT_ARCHITECTURE_OVERVIEW.md`](PROJECT_ARCHITECTURE_OVERVIEW.md)：

- 研究情报层：保存来源、摘要、六域分类、可验证假设和反方风险
- 股票池与特征层：把可落地字段注册为 factor / feature spec，并记录数据源、频率、覆盖率、as-of 可见性和缺失处理
- 策略治理层：把因子域和影响通道用于 `factor-effectiveness`、`strategy-admission`、失败归因和 regime 解释
- 交付与运维层：只展示已生成的诊断、报告和知识资产，不直接重写策略结论

T2.13 第一版需要统一以下字段口径：

| 字段 | 含义 | 典型取值 |
| --- | --- | --- |
| 因子域 | 因子属于六域矩阵的哪一类 | 宏观制度、行业主题、公司价值、风格风险溢价、资金交易、信息事件 |
| 影响通道 | 因子影响价格的理论路径 | 现金流预期、折现率/风险溢价、资金供需、信息事件、微观结构放大 |
| 数据来源 | 字段来自哪里 | Tushare、本地 SQLite、情报台账、公告新闻、人工 note |
| 可见时间 | 回测时何时可见 | trade_date、announce_date、fetched_at、published_at |
| 使用位置 | 当前允许进入哪一层 | 诊断、筛选、风险 overlay、失败归因、报告解释、候选假设 |
| 验证状态 | 是否已经具备策略证据 | 待采集、覆盖率通过、诊断通过、样本外通过、admission 通过、research-only |

短期不允许：

- 不把六域矩阵直接转成主 ranker 权重
- 不用 LLM 或知识图谱绕过回测、PIT、成本和 admission 门禁
- 不把外部新闻、政策或情绪材料当作已验证因子
- 不在没有字段覆盖率、as-of 可见性和缺失审计前启动策略回测

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

新闻源作为独立数据源模块推进，不归入 Tiingo EOD 日线适配器。当前规划已从单一新闻 provider 扩展为“文本事件数据层”：统一承接公告、研报、新闻、政策、快讯和后续文本摘要事件，服务盘前解释、关注个股分析工具、PEAD 研究和 `T2.11` 文本因子沙盒。

- `Tiingo` 只保留为美股个股 / ETF / ADR 的 EOD 日线源；当前 token 对 `/tiingo/news` 返回 `403 permission_denied:news_api`，不继续扩展 Tiingo News。
- `Alpha Vantage` 作为第一轮低成本新闻源 probe provider，验证 `tickers`、`topics`、`time_from/time_to`、`sort/limit` 和字段结构。
- `Benzinga` 作为后续付费 / 生产级新闻源候选，重点评估 ticker、channel/topic、date range、实时性、成本和授权边界。
- `Finnhub` 仅作为单票 company news 备选，不作为首批主新闻源。
- `AI 语料库（T1.7）` 作为中文文本主线：先以 gov.cn 政策文件库、CCTV 新闻联播公开文字稿、CNInfo 公告、PBOC 报告和授权研报元数据建设自建 provider，不依赖 Tushare 权限；Tushare `research_report` / `anns_d` / `major_news` / `npr` / `cctv_news` 只作为接口形态和可替换 provider 参考。当前 gov.cn、CCTV 和 CNInfo 公告列表已具备 MVP 生产入口。
- 新浪财经、财联社、华尔街见闻、中证网等公开上游只作为替代源候选，接入前必须评估抓取稳定性、授权边界和维护成本。

组合新闻拉取原则：

- 不假设多 ticker 一次传入时 provider 使用 OR 语义。
- 观察池新闻按逐 ticker 请求，再按 `url / title / published_at` 聚合去重。
- 项目内部业务标签需要映射到 provider 固定 topic 枚举。
- 原始响应进入 `data/raw_data/news/<provider>/`，清洗后的文本事件表进入 `data/features/news/`，探测报告进入 `reports/`。
- 文本事件必须保留 `source`、`provider`、`published_at`、`ingested_at`、`as_of_time`、`url`、`dedupe_key` 和 `content_hash`，避免未来函数、重复新闻和来源不可追溯。

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

### 4.3 可交易信号与调仓建议单

可交易信号不是 LLM 文案，也不是自动下单指令。它是策略引擎、risk overlay、风险预算、可成交性模型和账户级仿真共同通过后的结构化交易计划输出。

输入：

- 当前持仓
- 当前现金
- 股票池与策略候选
- 目标权重
- 风险预算
- A 股交易约束
- 跨市场 risk overlay

输出字段至少包括：

- `signal_level`
- `suggested_action`
- `current_weight`
- `target_weight`
- `weight_delta`
- `simulated_order_qty`
- `blocked_reason`
- `risk_notes`
- `invalidation_conditions`

允许动作：

- `新增`
- `加仓`
- `减仓`
- `持有`
- `剔除`
- `阻断`

调仓建议单只表达“按当前模型和约束，系统建议如何形成交易计划”。是否执行、如何执行、是否修改参数，仍由使用者独立判断。

### 4.4 风险预算体系

不采用凯利公式。当前统一采用风险预算约束：

- 单票暴露上限
- 单行业暴露上限
- 总暴露上限
- 波动率过滤
- 回撤熔断
- 连续失败降级
- 样本覆盖不足降级

### 4.5 可成交性模型

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
- **fallback**：AkShare / 新浪快照 / 本地 A 股研究主库
- **本地底座**：`data/manual_history/a_share_history.sqlite`

当前状态：

- Tushare 已作为 A 股主源接入增量更新链路。
- `phase0 run` 已在启动时执行 `manual_history_update` 预检查：本地库新鲜则直接复用 SQLite，本地库落后时优先 Tushare 补齐。
- 本地研究主库承担回测、股票池、PIT 审计和数据治理底座，避免 walk-forward 逐只在线抓取导致结果不可复现。
- `reports/phase0_data_source_report.md` 已纳入 Tushare smoke test 和 manual-history pre-run update 状态。
- AkShare 当前易受远端断连影响，但仍保留为开发/研究辅助源。

### 5.2 美股个股与 ETF

- **计划主源**：Tiingo
- **fallback**：yfinance
- **当前过渡库**：`data/us_market_history.sqlite`

当前状态：

- Tiingo 最小接入已完成：正式入口为 `phase0/data_access/connectivity.py` 中的 `fetch_tiingo_daily`，`check_connectivity` 已覆盖 `NVDA`、`AAPL`、`TSLA`、`KWEB`；`phase0/data_sources.py` 仅保留为兼容旧导入的薄 wrapper。
- 当前跨市场标的已先由 `yfinance` 增量写入 US market 本地 SQLite，策略读取落库数据，避免每次评估时临时在线抓取。
- Tiingo 暂不承接新闻源；新闻源独立任务见 `T1.3`。
- 接入任务单见：`docs/tasks/data-sources/TIINGO_IMPLEMENTATION_TASKS.md`

### 5.3 港股

- **当前状态**：`data/hk_market_history.sqlite` 已启用并完成 30 标的初始观察池批量落库（provider: `yfinance`）
- **应用挂载状态**：数据层已可用，策略主链路仍未挂载（保持独立验证阶段）
- **候选策略记录**：`docs/tasks/cross-market/HK_A_SHARE_MAPPING_STRATEGIES.md`

当前说明：

- 港股库当前已完成数据质量验证与验收报告：`reports/hk_market_history_batch_load_report.md`。
- 最新一次批量结果：覆盖率 `30/30`，最新交易日 `2026-06-01`，累计 `37044` 行。
- 后续启用前必须先完成覆盖率、新鲜度、复权口径和交易日历校验。
- 2026-06-02 Tiingo 实测 `HK.00700`、`HK.09988`、`0700.HK`、`9988.HK` 等格式均返回 `404 Ticker not found`，当前不适合作为港股正式源。
- 港股映射 A 股策略后续按“先数据验证、再解释力测试、最后回测接入”的顺序推进。

### 5.4 宏观 / 利率 / VIX

- **计划主源**：FRED
- **fallback**：yfinance

当前状态：

- FRED 最小接入已完成：正式入口为 `phase0/data_access/connectivity.py` 中的 `fetch_fred_series`，`check_connectivity` 已纳入 `fred` 源检查。
- `config.yaml` 已新增 `data_sources.fred.enabled / api_key_env / series` 配置项。
- 已在非受限网络环境完成首批 5 个序列连通性验收，并写入 `reports/phase0_data_source_report.md`。
- 接入任务单见：`docs/tasks/data-sources/FRED_IMPLEMENTATION_TASKS.md`

### 5.5 yfinance 的定位

`yfinance` 继续保留，但口径已经明确：

> **yfinance 仅作为 fallback，不再作为长期正式主源。**

现阶段例外是 `us_market_history.sqlite` 的过渡期更新仍使用 `yfinance` provider；策略读取的是本地库，不直接依赖运行时在线请求。等 Tiingo/FRED 接入后，再把对应标的迁移到正式主源。

### 5.6 新闻源

- **第一轮 probe provider**：Alpha Vantage `NEWS_SENTIMENT`
- **生产级候选**：Benzinga Newsfeed
- **单票备选**：Finnhub company news
- **不再扩展**：Tiingo News API
- **中文 AI 语料库候选**：gov.cn 政策文件库、CCTV 新闻联播公开文字稿、CNInfo / AkShare 公告、PBOC 货币政策报告、授权券商研报元数据；Tushare 同名接口仅作为兼容形态和可替换 provider 参考。当前前三类已落地 MVP，PBOC / 研报元数据 / 监管规则仍待扩展。

当前状态：

- 已验证 Tiingo News API 当前 token 权限不足，访问 `/tiingo/news` 返回 `403 permission_denied:news_api`。
- Alpha Vantage 只作为低成本可用性验证源，不直接承诺为长期主源。
- Alpha Vantage 多 ticker / 多 topic 过滤不按项目组合 OR 语义假设；组合观察池必须逐 ticker 拉取后聚合去重。
- 后续中文财经新闻看板调查已沉淀到 `refdocs/tushare_news_dashboard_upstream_mapping_note_2026-06-06.md`，用于 provider 选择和公开上游风险评估。
- 自建中文文本事件 API 与国家政策法规库 API 计划已合并为 `T1.7｜AI 语料库`，首期不依赖 Tushare。当前已实现 gov.cn 政策库、CCTV 新闻联播和 CNInfo / AkShare 公告列表 provider。
- 新闻源只服务盘前解释、风险提示、关注个股分析、PEAD 研究和后续文本摘要因子，不进入首批交易建议主线。
- 接入任务单见：`docs/tasks/data-sources/NEWS_SOURCE_IMPLEMENTATION_TASKS.md` 和 `docs/tasks/data-sources/AI_CORPUS_IMPLEMENTATION_TASKS.md`

### 5.7 当前意义

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
| 美股 / ETF 后续主源 | Tiingo | 最小 EOD 接入已完成，未来评估替换过渡 provider |
| 港股历史库 | `hk_market_history.sqlite` | 已完成 30 标的批量落库与验收，暂不挂策略主链路 |
| 宏观 / 利率 / VIX 后续主源 | FRED | 最小接入已完成 |
| 新闻源候选 | Alpha Vantage / Benzinga / Finnhub | 独立模块规划，不接入主 ranker |
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
- 严格 `qfq_asof` 复核与最新全候选 compare 后，当前无可用于实盘模拟的合格 candidate，也没有 selected candidate。
- Phase 0 当前结论应解释为 **基础设施完成、工程链路可用，但策略门禁未通过，不能据此进入实盘模拟**。
- 2026-06-23 `sleeve_composite_v1` scoped admission 结论为 `reject`，主要失败来自负收益、负 Sharpe、高换手、行业集中和 `critical` overfit risk。
- 2026-06-23 行业集中度 100% universe 专项实验在 `codex/industry-weight-100-universe-experiment` 分支完成；取消 universe 层行业上限未产生可准入策略，实验结果仅作 research-only 分支证据，main 尚未合入该实验产物。

#### 当前兼容参考结果

旧 `qfq_current` 兼容口径 gate 中：

- `legacy_momentum_low_turnover_v1`：`annualized_return_mean = 0.1331`
- `legacy_momentum_low_turnover_v1`：`sharpe_mean = 1.0083`
- `legacy_momentum_low_turnover_v1`：`max_drawdown_mean = -0.1042`
- `legacy_momentum_low_turnover_v1`：`win_rate_mean = 0.5110`
- `legacy_momentum_low_turnover_v1`：`turnover_annual_mean = 1.50`
- 主测试成本口径：`slippage = 0.00246`，`commission = 0.00025`，`stamp_duty_sell = 0.0005`

这些结果只能作为兼容参考和研究基线，不能作为当前准入结论。T2.1 当前已经从“继续找一个马上晋级的候选”调整为“把 13 个候选治理为可复查的研究资产”。当前真实缺口变为：

1. 在配置层 13 个候选尚未形成 main 全量 admission 通过记录的前提下，重排策略池优先级，避免继续在高换手价格行为策略上消耗研发资源。
2. 对 `low_vol_low_turnover_quality_v1`、`quality_low_turnover_monthly_v1` 做失败归因复核，重点解释质量暴露为何没有稳定转化为收益。
3. 对 `sleeve_composite_v1` 先降低组合换手、换股 churn 和行业集中，再考虑二次 scoped admission；不直接做收益调参。
4. 保持 universe 层分散约束和策略层 `max_industry_weight = 0.35` 审计分离，避免用放宽研究池约束替代最终组合风险控制。
5. 为每个候选维护状态枚举：`active_research`、`baseline`、`failure_sample`、`research_only`、`deferred` 或 `admission_pass_candidate`。

#### 当前核心任务

1. 以 `baseline_admission_all_v1` 统一治理当前 13 个候选；compare 只产生研究线索，admission 才能产生准入动作。
2. 重跑 main 全候选 admission，纳入 `sleeve_composite_v1` 与 `sleeve_composite_low_churn_v1`，并输出策略池治理报告。
3. 保留 `legacy_momentum_low_turnover_v1` 作为兼容 baseline 与动量 sleeve 研究样本，而非实盘模拟合格候选。
4. 优先完善低波、低换手、质量主线的组合构造和失败归因，控制年化换手、参数漂移和行业集中。
5. 用 T2.13 因子传导框架增强失败归因和 admission 报告解释，但不直接生成策略权重。
6. 在变更日志和主计划中持续沉淀 `qfq_asof` 复核、准入拒绝原因、行业集中实验和候选重建结论。

#### 当前候选方向

- `low_vol_low_turnover_quality_v1`：当前最接近主线方向，但仍未通过 admission；下一步优先做质量暴露、参数稳定性、fold 稳定性和行业集中失败归因
- `quality_low_turnover_monthly_v1`：保留为低频质量对照候选，重点复核最后一折 regime 依赖和参数漂移
- `legacy_momentum_low_turnover_v1`：当前兼容 baseline 与动量 sleeve 研究样本，不是已通过严格门禁的主候选
- `sleeve_composite_v1`：research-only 诊断候选，当前 scoped admission 为 `reject`，二次研发必须先解决换手和组合构造问题
- `quality_growth_price_v1`、`core_selection_quality_momentum_v1`、`multifactor_volume_price_filter_v1`：保留为质量、复合和多因子构造对照，先进入失败归因，不继续堆叠参数
- `ma_kline_baseline_v1`、`legacy_momentum`、高换手 residual、theme exposure：保留为 baseline、失败样本或 deferred 研究线索，不占据当前主线

#### 当前验收口径

- `annualized_return_mean > 0`
- `sharpe_mean > 0.5`
- `max_drawdown_mean > -0.25`
- `win_rate_mean > 0.45`
- `oos_return_decay_ratio < 0.30`
- 样本治理要求：symbol-scope 候选至少 `20` 个 fold 与 `20` 个 symbol；portfolio-scope 候选至少 `4` 个 portfolio fold
- admission 治理要求：默认使用 `qfq_asof`、`baseline_2y_1y_5fold` 起步，并通过收益、Sharpe、回撤、正收益折比例、年化换手、过拟合风险、参数稳定性、行业集中和因子诊断门禁

这套验收标准不是在找“历史上最赚钱的策略”，而是在找：

> **有正收益、风险可控、表现较稳、样本外还能成立，并且不是由少量样本偶然支撑的策略。**

### Phase 1：形成可用的盘前研判产品（链路兼容可用，正式策略接入待准入）

当前产品链路具备兼容输出能力，但在出现新的严格 admission 合格 candidate 前，正式策略接入仍应保持阻断：

- [x] 稳定观察池输出
- [ ] 可交易信号与调仓建议单输出
- [x] `07:30` 日报流水线强化
- [ ] 更稳定的本土主策略正式化
- [ ] 跨市场 overlay 与盘前解释层完善
- [x] 当前持仓 / 现金 / 目标权重到模拟订单的转换链路
- [ ] 主源与 fallback 的长期运行治理

### Phase 1.5：引入机器学习增强，但保持产品导向

该阶段不是做学术平台，而是做**能提升产品可用性的 ML 增强**：

- [ ] 接入 sklearn 基线模型
- [ ] 用 ML 做辅助排序或过滤
- [ ] 记录预测与实际结果
- [ ] 用更稳的方式提升选股与观察池质量

### Phase 2：数据源升级与产品扩展

此阶段重点：

- [x] FRED 接入宏观 / 利率 / VIX 主链路
- [x] Tiingo 接入美股个股 / ETF 主链路
- [x] yfinance 退化为 fallback
- [ ] 强化盘前日报与解释层
- [ ] 逐步评估 Dashboard / PWA / 桌面端

### Phase 3：组合与账户仿真增强（后续）

以下内容保留为中后期路线图：

- [ ] 组合权重分配
- [ ] 简化组合风险约束
- [x] 账户级仿真
- [ ] 更系统的模型评估记录

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
- OpenClaw Gateway 可作为外部 agent / 调度入口，用于研究摘要、消息通道和跨工具编排；接入说明见 `refdocs/AGENT_AND_LOCAL_LLM_WORKFLOW.md`
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
├── AGENTS.md
├── README.md
├── config.yaml
├── pyproject.toml
├── runit
├── phase0/
│   ├── cli.py
│   ├── data_access/
│   │   ├── connectivity.py
│   │   ├── local_history.py
│   │   └── providers/
│   ├── data_governance/
│   │   └── backfills/
│   ├── research/
│   │   ├── admission/
│   │   ├── attribution/
│   │   └── diagnostics/
│   ├── reporting/
│   ├── execution/
│   ├── intelligence/
│   ├── universe.py
│   ├── walk_forward.py
│   └── strategies/
├── docs/
│   ├── tasks/
│   │   ├── data-sources/
│   │   ├── strategy/
│   │   ├── cross-market/
│   │   ├── account/
│   │   ├── research/
│   │   └── ops/
├── data/
├── knowledge/
│   └── intelligence/
├── refdocs/
│   ├── papers/
│   └── OUTLOOK/
├── reports/
│   ├── archive/
│   ├── runs/
│   ├── database_health/
│   ├── strategy_admission/
│   ├── phase0/
│   ├── strategy_governance/
│   └── README.md
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
- 项目短命令：`./runit`，解析为 `./.venv/bin/python -m phase0.cli`
- Python 环境：项目内 `.venv`
- 调度：本地 cron 单入口 + `phase0.cli maintain tick`
- 后续如需部署：Docker Compose 统一打包

### 当前已落地调度

- 系统 cron 只保留一个项目入口：`scripts/run_project_scheduler.sh`
- wrapper 加载 `.env` 后调用 `phase0.cli maintain tick`
- 任务 registry 当前包含：每周一 `03:30` 财务因子更新，交易日 `07:20` 观察池简报，交易日 `16:20` 港股历史更新，交易日 `16:30` A 股历史更新，交易日 `17:10` US market 历史更新
- 维护编排器负责交易日历、运行窗口、重试、状态记录和健康门禁；后续新增定时任务优先扩展 Python registry，不再新增多个 cron 入口

---

## 十三、关键决策记录（当前有效）

| 决策项 | 当前选择 | 原因 |
|--------|---------|------|
| 产品定位 | 量化研究与风险提示工具 | 避免误导为自动交易系统 |
| 当前主线 | 本土因子主导，跨市场 overlay | 回测与文献共同支持 |
| 当前领先候选 | 无 | 严格 `qfq_asof` 复核后当前没有 selected candidate |
| 当前 baseline | `legacy_momentum_low_turnover_v1` | 兼容 baseline 与研究样本，不代表已通过实盘模拟门禁 |
| 跨市场映射 | 仅做 overlay | 直接做 ranker 效果弱 |
| 国内股票主源 | Tushare | 已正式采纳 |
| 国内 fallback 基座 | 本地 SQLite / AkShare / 新浪 | 最稳、可控、可补位 |
| US market 过渡库 | `us_market_history.sqlite` | 当前已替代运行时 yfinance 临时抓取 |
| 美股/ETF 主源方向 | Tiingo | 比 yfinance 更适合长期主链路 |
| 港股库 | `hk_market_history.sqlite` | 已完成 30 标的落库与验收，暂不挂策略主链路 |
| 宏观/利率/VIX 主源方向 | FRED | 更适合正式主链路 |
| yfinance | 仅 fallback | 保留低摩擦备用价值 |
| 财务因子 | 已接入，但历史回测前需 PTI 校验 | 防未来函数 |
| LLM | 仅研究辅助，不直接产出交易信号 | 保持可解释和可控 |
| 当前优先事项 | 重建有效策略、完善准入治理与执行诊断 | 工程链路可用，但当前策略门禁未通过，不能把旧结果解释为可用模拟产物；正式 execution gate / brief 集成仍待完成 |

---

## 十四、当前一周执行摘要

> 当前统一周执行附件见：`docs/tasks/WEEKLY_EXECUTION_CHECKLIST.md`

### 本周目标

~~围绕 A 股本土主因子完成一轮低换手改造验证，正式确认新候选替代旧 baseline，并补齐账单导出与解释性产物。~~

~~围绕 Week 2 数据源升级主线，完成 FRED / Tiingo 最小接入、明确新闻源边界、验证港股历史数据可用性，并把可复用数据资产沉淀到 `data/`，把验收与运行结果沉淀到 `reports/`。~~

当前目标是完善策略池：以 `baseline_admission_all_v1` 为全局准入集合，围绕低波、低换手、质量主线做失败归因和组合构造修正，形成下一轮可验证候选，而不是继续扩大高换手价格行为策略。

### 本周已完成

> 以下删除线条目为前序 Week 1 / Phase 0 收口已完成项，保留作上下文，不再代表当前一周执行重点。

- ~~`legacy_momentum` 已从 symbol-scope 改为 portfolio-scope baseline。~~
- ~~回测窗口已从 `5` 年扩大到 `7` 年，portfolio 候选均达到 `4` 个 fold。~~
- ~~财务因子历史已扩展到 `32` 个季度，覆盖 `2018-06-30` 至 `2026-03-31`。~~
- ~~已新增成本敏感性报告，输出 current / low-slippage / zero-cost 三档。~~
- ~~主测试已改为默认 `slippage = 0.00246`，成本敏感性测试已改为单独 CLI 路径，需显式指定场景运行。~~
- ~~已修复财务因子 point-in-time merge 的 datetime dtype 边界问题。~~
- ~~已新增 `legacy_momentum_low_turnover_v1`，并通过完整 Phase 0 gate。~~
- ~~已生成低换手策略账单 CSV、资产日表和 HTML 预览。~~
- ~~已将低换手策略连续 OOS 报表改为内嵌 CSS 的 HTML 文件。~~
- ~~已为账单导出脚本增加行情面板缓存，减少重复生成账单时的行情加载和对齐成本。~~
- ~~已在通过策略和回测关键代码块补充中文注释。~~
- ~~已完成账户级仿真 v2，覆盖成交价口径、整手、现金、涨跌停、停牌、流动性参与率、未成交原因和真实账户 CSV 对账预留。~~
- ~~已将 `execution-gate` 与 `oos-report` 做成 profile 化管线，支持 `research` / `live` 两类参数组合。~~
- ~~已统一 HTML 报表展示规范：生成时间、横向滚动、纵向滚动、固定表头。~~
- `T1.1` FRED 最小接入已完成：`fetch_fred_series()`、`check_connectivity()`、`config.yaml` 配置和 `.env` key 加载均已验证。
- FRED 首批序列已完成非受限网络验收：`GDP`、`CPIAUCSL`、`FEDFUNDS`、`DFF`、`VIXCLS` 均可返回数据。
- FRED 缓存策略已补齐：缓存目录迁入 `data/cache/fred/`，默认 TTL 为 `24` 小时，报告只保留验收记录。
- `T1.2` Tiingo 最小接入已完成：`fetch_tiingo_daily()` 覆盖 `NVDA`、`AAPL`、`TSLA`、`KWEB`，并保留 `yfinance` fallback。
- Tiingo 港股可用性已实测：`HK.00700`、`HK.09988`、`0700.HK`、`9988.HK` 等格式返回 `404 Ticker not found`，不作为港股正式源。
- Tiingo News API 已探测：当前 token 对 `/tiingo/news` 返回 `403 permission_denied:news_api`，新闻源改为独立模块规划。
- 已新增 Tiingo news probe 最小脚本，用于验证 ticker 列表、主题标签、时间窗口三类过滤能力。
- 已明确新闻源策略：Tiingo 只保留为美股 / ETF / ADR 日线源，新闻模块后续优先 probe Alpha Vantage，生产级候选为 Benzinga。
- 已验证港股历史数据源路径：AkShare 当前环境下不可稳定抓取港股；Tushare 港股接口可用但频率限制过强；yfinance 当前可用于港股历史库 bootstrap。
- `hk_market_history.sqlite` 已启用并完成 30 标的初始港股观察池批量落库，覆盖率 `30/30`，最新交易日 `2026-06-01`，累计 `37044` 行。
- 已生成港股批量落库报告：`reports/hk_market_history_batch_load_report.md`，包含 30 标的覆盖、审计记录、样本行和中文名称 `name_zh`。
- 已新增 `phase0.cli` 当前使用说明：`refdocs/PHASE0_CLI_USER_GUIDE.md`。
- 已同步 `README.md`、`docs/PROJECT_ARCHITECTURE_OVERVIEW.md`、`reports/phase0_strategy_change_log.md`、`docs/tasks/WEEKLY_EXECUTION_CHECKLIST.md` 中的数据源与目录边界说明。
- 已整理当前 `phase0.cli` 命令路由：推荐主入口收敛为 `brief daily`、`brief watchlist`、`brief premarket`、`brief account-bill`，旧 `daily-brief` / `premarket` 保留兼容。
- 已将 `07:20` 调度任务切换为 `brief watchlist`，阶段试用观察池固定输出到 `reports/watchlist_today/index.html`，并由程序内置 rsync 同步到远端 `/brief/`。
- 已将 watchlist 静态页面拆为 `phase0/reporting/templates/watchlist.html` 和 `phase0/reporting/static/watchlist.css`：Python 只准备结构化渲染上下文，CSS 按 `/brief/ui-test/` 参考样例管理 Belafonte Day / Night 主题、大屏断点和表格视觉，主题切换与回到顶部脚本按参考样例内联在 HTML 尾部；生成、latest 镜像和远端同步均复制 HTML + CSS bundle。
- 已固化 watchlist 表格展示口径：`收盘价` 右对齐，其余数值列居中对齐；为压缩宽表，页面表头显示为 `动作`、`当前权重`、`目标权重`、`权重变化`、`持仓天数`，这些列使用当前模拟账户口径，`信号动作`、`信号持有天数` 使用策略研究信号口径；底部术语说明解释短表头的真实含义；顶部账户摘要固定为总资产、可用资金、持仓市值、当前仓位、当前收益率 5 项，无已确认账单时按初始资金和 `暂无` 收益率展示。
- 已为模拟账户账单增加 latest 镜像与远端静态页面：账单 HTML 存在时复制到 `reports/runs/latest/account_bill/index.html` 和 `reports/account_bill_today/index.html`，并同步到远端 `/account-bill/`；无确认账单时安全跳过。
- 已接入模拟账户 SQLite 主账本：自动创建 `simulated_accounts`、`account_daily_assets`、`account_trades`、`account_positions`，并在 watchlist 页面展示最近已确认账单日账户快照；账户配置新增 `simulation_start_date`，用于定义模拟账户生命周期起点，账本重建不会继承更早 watchlist。
- 已修正 watchlist 与正式模拟账单边界：watchlist 为计划层；模拟账单只记录本地日线库已有对应执行日 OHLCV 的已确认交易日。
- 已新增账户设计与账单查询备忘：`refdocs/SIMULATED_ACCOUNT_NOTES.md`，并约定后续“查看账单”默认展开 SQLite 对应表内容。
- 已完成 `sleeve_composite_v1` scoped admission 与治理报告：结论为 `reject`，保留为 research-only 诊断候选。
- 已在实验分支完成 max industry weight 100% universe 专项 compare/admission：配置层 12 个策略在实验分支 admission 中全部 `reject`，实验不改变主线约束与准入结论；main 尚未合入该分支产物。
- 已新增 `phase0.cli system status` 只读汇总入口：复用 Maintenance Orchestrator 状态，输出 maintenance state DB、生成时间、任务状态分布、决策分布和 running shard 数；当前不启动任务、不生成维护 Markdown 报告。

### 本周候选方向

前序候选方向：

1. ~~**低换手 legacy momentum 改造并正式替代旧 baseline**~~
2. ~~**账单 / 资产轨迹 / 买卖原因导出标准化**~~
3. ~~**账户级仿真与实盘约束补齐**~~
4. ~~**公告日 point-in-time 校验与日报接入**~~

当前 Week 2 候选方向：

1. ~~**FRED 宏观 / 利率 / VIX 主源最小化接入**~~
2. ~~**Tiingo 美股个股 / ETF EOD 源最小化接入**~~
3. ~~**新闻源从 Tiingo 中拆出，形成独立 provider 规划**~~
4. ~~**港股历史库从结构预留推进到 30 标的数据层验收**~~

当前策略池候选方向：

1. **T2.1 策略池治理清单收口**：13 个候选统一归入 `active_research`、`baseline`、`failure_sample`、`research_only`、`deferred` 或 `admission_pass_candidate`
2. **全候选 admission 治理报告标准化**：日期、背景、策略集合、preset、数据口径、研究边界和准入动作必须落盘
3. **低波低换手质量主线失败归因与组合构造修正**
4. **低频质量策略参数稳定性和 regime 依赖复核**
5. **`sleeve_composite_v1` 降换手、降 churn、降行业集中后再 scoped admission**
6. **T2.13 因子传导框架接入失败归因和 admission 解释**，但不直接进入主 ranker 权重

### 推荐实施顺序

~~从治理风险看：~~

1. ~~样本覆盖门槛与 portfolio 口径已完成，继续保持为强制治理。~~
2. ~~当前先围绕 `legacy_momentum_low_turnover_v1` 做解释链路和账户仿真收口。~~
3. ~~residual / multifactor-volume-price 暂时降为备选，等主线收口后再继续精修。~~

从当前策略池治理看：

1. 保持 `qfq_asof`、PIT 股票池和成本后口径为 admission 默认，不回退到旧 `qfq_current` 兼容结果。
2. 先完成 T2.1 候选状态治理和 main 全候选 admission 报告，不再让旧 compare 结果承担准入解释。
3. 优先处理低波低换手质量主线，先解释质量暴露、参数稳定性和行业集中失败原因。
4. `sleeve_composite_v1` 不直接调收益参数，先处理换手、持仓保留、risk overlay churn 和行业集中。
5. 行业集中度 100% universe 实验只作为研究归档；主线不放宽策略层行业审计。
6. T2.13 因子传导框架只进入归因、特征注册和报告解释，不绕过 admission。

### 本周成功标准

- ~~compare mode 不再混用 symbol-scope 与 portfolio-scope 结果~~
- ~~至少一个 portfolio 候选在足够 fold 覆盖下通过 gate~~
- ~~`sharpe_mean > 0.5`~~
- ~~`max_drawdown_mean > -0.25`~~
- ~~`win_rate_mean > 0.45`~~
- ~~current-cost 与 low-slippage 场景差距可解释，且不是完全依赖零成本才有效~~
- ~~变更日志有清晰晋级或失败原因~~
- FRED 首批宏观 / 利率 / VIX 序列可通过 connectivity 验收，并有缓存策略。
- Tiingo EOD 最小接口可运行，职责边界和 fallback 关系清晰。
- Tiingo 不承担港股正式源和新闻源的结论已记录到计划与变更日志。
- 港股历史库至少完成 30 标的覆盖、新鲜度、审计记录和报告输出。
- `data/` 与 `reports/` 的职责边界在 README 和架构文档中保持一致。
- 所有数据源变更不破坏当前 Phase 0 策略、账单、gate、premarket 主链路。
- 全候选 strategy-admission 需重跑并覆盖 `baseline_admission_all_v1` 的 13 个候选，结论、拒绝原因和治理报告可追溯。
- 每个候选必须具备明确治理状态：`active_research`、`baseline`、`failure_sample`、`research_only`、`deferred` 或 `admission_pass_candidate`。
- 新一轮策略池改造必须改善至少一个核心失败项：收益、Sharpe、正收益折比例、年化换手、行业集中、参数稳定性或 overfit risk。
- 任何进入 paper review / 模拟账户 / 日报链路的候选必须先通过 admission，而不是仅凭 compare 排名或单次实验相对最优。

---

## 十五、下一步行动

### 任务拆解管理

本文件是项目父级总体计划。所有拆分后的任务清单统一放在 [`docs/tasks/`](tasks/README.md)，父级计划只维护阶段、优先级、主线边界和子任务引用。

当前任务层级：

| 层级编号 | 任务域 | 子任务文档 | 当前状态 |
| --- | --- | --- | --- |
| `T0` | 周任务执行总清单 | [`docs/tasks/WEEKLY_EXECUTION_CHECKLIST.md`](tasks/WEEKLY_EXECUTION_CHECKLIST.md) | 持续执行，仍有未完成项 |
| `T1.1` | FRED 宏观 / 利率 / VIX 数据源 | [`docs/tasks/data-sources/FRED_IMPLEMENTATION_TASKS.md`](tasks/data-sources/FRED_IMPLEMENTATION_TASKS.md) | **已完成** |
| `T1.2` | Tiingo 美股个股 / ETF 主源 | [`docs/tasks/data-sources/TIINGO_IMPLEMENTATION_TASKS.md`](tasks/data-sources/TIINGO_IMPLEMENTATION_TASKS.md) | 基本完成，剩余少量后续增强项 |
| `T1.4` | A 股历史 as-of 前复权与复权因子治理 | [`docs/tasks/data-sources/ASOF_PRICE_ADJUSTMENT_GOVERNANCE_TASKS.md`](tasks/data-sources/ASOF_PRICE_ADJUSTMENT_GOVERNANCE_TASKS.md) | **因子表已补齐，待差异报告与对照回测** |
| `T1.5` | Tushare 财务因子逐股票历史补齐 | [`docs/tasks/WEEKLY_EXECUTION_CHECKLIST.md`](tasks/WEEKLY_EXECUTION_CHECKLIST.md#W216tushare-财务因子逐股票历史补齐t15) | **已完成：2016Q1-2018Q1 目标季度末已补齐并完成 PTI / factor-effectiveness 复核** |
| `T1.6` | `a_share_history.sqlite` 主库定义与 README 重整 | [`docs/tasks/data-sources/MANUAL_HISTORY_README_REALIGNMENT_TASKS.md`](tasks/data-sources/MANUAL_HISTORY_README_REALIGNMENT_TASKS.md) | **已完成：主库定义、维护分工与口径边界已同步到文档** |
| `T1.7` | AI 语料库（政策法规 / CCTV / 公告 / 央行报告 / 研报元数据） | [`docs/tasks/data-sources/AI_CORPUS_IMPLEMENTATION_TASKS.md`](tasks/data-sources/AI_CORPUS_IMPLEMENTATION_TASKS.md) | **gov.cn 政策库、CCTV live 和 CNInfo / AkShare 公告列表 MVP 已落地：schema、provider registry、fixture / parser、raw archive、SQLite upsert / query、`ai-corpus` CLI、gov.cn / CCTV / CNInfo 默认调度基础已完成；PBOC / 研报元数据 / 监管规则仍为后续项** |
| `T2.1` | Phase 0 候选策略池治理清单 | [`docs/tasks/strategy/PHASE0_CANDIDATE_STRATEGIES.md`](tasks/strategy/PHASE0_CANDIDATE_STRATEGIES.md) | **已修订为治理清单：`baseline_admission_all_v1` 统一管理 13 个候选；当前无 admission pass，短期聚焦全候选 admission、低波低换手质量主线失败归因和 sleeve 降换手重构** |
| `T2.3` | 策略积木工程化计划 | [`docs/tasks/strategy/STRATEGY_BLOCKS_PLAN.md`](tasks/strategy/STRATEGY_BLOCKS_PLAN.md) | 主目标已完成，后续按策略扩展维护 |
| `T2.4` | 策略过拟合诊断工具 | [`docs/tasks/strategy/STRATEGY_OVERFITTING_DIAGNOSTIC_TOOL.md`](tasks/strategy/STRATEGY_OVERFITTING_DIAGNOSTIC_TOOL.md) | **只读 MVP 已完成，已进入 strategy-admission 诊断链路，待 gate / brief 集成** |
| `T2.13` | 因子传导图工程化：因子本体、特征注册与市场环境归因 | [`docs/tasks/WEEKLY_EXECUTION_CHECKLIST.md`](tasks/WEEKLY_EXECUTION_CHECKLIST.md) | **计划新增：基于 `INT-KMS-001` 和项目架构文档，把六域传导框架落成只读元数据、诊断与报告解释层；不直接进入交易信号** |
| `T3.1` | 港股映射 A 股候选策略 | [`docs/tasks/cross-market/HK_A_SHARE_MAPPING_STRATEGIES.md`](tasks/cross-market/HK_A_SHARE_MAPPING_STRATEGIES.md) | 数据前置部分完成，策略未代码化 |
| `T4.1` | 真实账户对账 CSV 预留格式 | [`docs/tasks/account/ACCOUNT_RECONCILIATION_CSV_SCHEMA.md`](tasks/account/ACCOUNT_RECONCILIATION_CSV_SCHEMA.md) | **文档型任务已完成** |
| `T5.1` | 中文 A 股量化策略论文提炼 | [`docs/tasks/research/STRATEGY_SUMMARY.md`](tasks/research/STRATEGY_SUMMARY.md) | **文档型任务已完成** |
| `T5.2` | 投资策略情报工作流模块 | [`docs/tasks/research/STRATEGY_INTELLIGENCE_WORKFLOW_TASKS.md`](tasks/research/STRATEGY_INTELLIGENCE_WORKFLOW_TASKS.md) | **RAG-ready foundation 已建立：Markdown + CSV 台账、核心 note、策略转化草案、自动采集器、月度扫描索引和语料 manifest；仍不直接生成交易信号** |
| `T6.1` | 统一调度器与后台 Pipeline | [`docs/tasks/ops/SCHEDULER_PIPELINE_TASKS.md`](tasks/ops/SCHEDULER_PIPELINE_TASKS.md) | 最小统一调度器已接入，交易日历和失败重试仍待增强 |
| `T6.2` | 数据库健康检查与数据质量门禁 | [`docs/tasks/WEEKLY_EXECUTION_CHECKLIST.md`](tasks/WEEKLY_EXECUTION_CHECKLIST.md#W217数据库健康检查与数据质量门禁t62) | **只读 MVP、调度/研究前置门禁与 OHLC sample rows 已完成，后续补覆盖率口径判断** |
| `T6.3` | 数据治理与维护编排器 | [`docs/tasks/ops/DATA_GOVERNANCE_ORCHESTRATOR_TASKS.md`](tasks/ops/DATA_GOVERNANCE_ORCHESTRATOR_TASKS.md) | **P3/P4 关键收口已完成：真实 tick、wrapper 接管、最小重试、3 shard run/stop/resume、supervise、交易日历、Markdown 报告和 backfill 报告索引已落地** |
| `T6.4` | Report Dashboard Astro 静态报表门户 | [`docs/tasks/ops/REPORT_DASHBOARD_ASTRO_TASKS.md`](tasks/ops/REPORT_DASHBOARD_ASTRO_TASKS.md) | **P0 manifest 已落地：`dashboard scan` 可统一扫描 Markdown / HTML / CSV；Astro 页面仍待实现** |
| `T6.5` | Report Output Path Standardization | [`docs/superpowers/plans/2026-06-23-report-output-path-standardization.md`](superpowers/plans/2026-06-23-report-output-path-standardization.md) | **标准 run 路径层已落地，并已迁移 strategy-admission、db-health、factor-effectiveness 默认输出；历史产物保持兼容扫描** |
| `T6.6` | Daily Brief 独立内容模型与页面设计 | [`docs/tasks/ops/DAILY_BRIEF_CONTENT_MODEL_TASKS.md`](tasks/ops/DAILY_BRIEF_CONTENT_MODEL_TASKS.md) | **P0 已完成：DailyBriefDocument / DailyBriefSection、缺失边界与账户摘要口径已固化；P1 独立 HTML renderer 与 CLI 接入待完成** |
| `T6.7` | 多模拟账户静态控制台 | [`docs/tasks/ops/MULTI_ACCOUNT_STATIC_CONSOLE_TASKS.md`](tasks/ops/MULTI_ACCOUNT_STATIC_CONSOLE_TASKS.md) | **第一阶段已实施：`site build/sync/publish` 生成 `/quant/`，每个 enabled 模拟账户有独立观察池、账单和台账入口；逐笔未成交事件表待补** |

### 当前最高优先级

- [x] `T6.3` 当前优先 1：补持续 supervisor，使后台 shard 可基于 pid、日志和 audit 报告保守归类为成功、失败或 unknown
- [x] `T6.3` 当前优先 2：新增 `reports/database_health/maintenance/maintenance_status_YYYY-MM-DD.md`，汇总每日维护状态、失败原因、跳过原因、shard 状态和报告路径
- [x] `T6.3` 当前优先 3：接入交易日历和更细的运行窗口，降低节假日和非交易日误触发
- [x] `T6.3` 当前优先 4：从 backfill audit 中提取报告路径和关键结论，登记到维护状态
- [x] `T6.4` 当前优先：完成只读 manifest MVP 和 `dashboard scan`，生成 `reports/runs/report_dashboard/manifest.json`
- [x] `T6.5` 当前优先：建立 `reports/runs/YYYY-MM-DD/YYYYMMDD_HHMMSS__<command>__<scope>/` 规则并迁移核心默认输出
- [ ] `T6.6` 当前优先：完成 P1 独立 daily brief HTML renderer 与 `brief daily` CLI 接入，保持 `brief watchlist` 观察池页面独立。
- [x] `T6.7` 当前优先：建立多模拟账户静态控制台 `/quant/`，从账户级 latest 产物和模拟账户 SQLite 账本生成控制台、账户页、账单页和台账页
- [x] `T1.7` 当前优先：完成 AI 语料库 schema、provider registry、gov.cn 政策库 fixture / parser MVP，并保持只服务研究情报和解释层，不直接接入主 ranker

- [x] `T1.2` Tiingo 最小接入：在 `phase0/data_access/connectivity.py` 提供 `fetch_tiingo_daily()`，并在 connectivity 中覆盖 `NVDA/AAPL/TSLA/KWEB`
- [x] 完成 Tiingo 与 `yfinance` fallback 的职责边界落地，不做一次性硬切
- [x] 将 FRED/Tiingo 当前接入状态同步到 `reports/phase0_strategy_change_log.md`（按增量记录）
- [x] 强化 `07:30` 阶段试用观察池自动生成链路，形成“每日产出 + 可复盘归档”的最小闭环
- [x] 完成 `brief` 命令路由整理：`brief daily` / `brief watchlist` / `brief premarket` / `brief account-bill`
- [x] 接入模拟账户 SQLite 主账本与最近确认账单快照展示
- [x] 修复历史回测股票池未来函数风险：walk-forward 与历史账单导出默认使用每折 point-in-time 股票池
- [x] 实现 `T2.4` 策略过拟合诊断工具 MVP：基于现有 walk-forward 产物生成策略过拟合风险报告
- [x] 实现 `T1.4` A 股历史 as-of 前复权治理只读审计：确认当前有 `bfq_raw/qfq_current/market_adj_factors`，可构造严格 `qfq_asof`
- [x] 补齐 `market_adj_factors` 历史因子表
- [x] 完成 `T1.6` 文档纠偏：`a_share_history.sqlite` 已明确为 A 股研究主库；`data/manual_history/` 当前视为历史路径名债，不在本阶段做真实目录迁移
- [x] 执行 Tushare 历史数据补全：新增 `backfill-tushare-history`，补齐 2016-01 起 `daily_basic` 与 `adj_factor` 日级字段；验收报告见 `reports/tushare_history_backfill_audit.md`
- [x] 运行 `qfq_current` / `qfq_asof` 差异报告
- [x] 运行主策略 `legacy_momentum_low_turnover_v1` 的 `qfq_current` / `qfq_asof` 对照回测，结论：`qfq_current` 降级为兼容口径参考
- [x] 运行最新版本全候选策略池 `qfq_asof` compare，结论：当前无可用于实盘模拟的合格 candidate
- [x] 制定 `T2.5-T2.11` 有效量化策略研发实施方案与开发任务清单
- [x] 修订 `T2.1` Phase 0 候选策略池文档：从旧候选晋级清单改为策略池治理清单，明确 13 个候选的角色、准入边界、优先级和不做清单
- [x] 实现 `T2.5` 因子有效性诊断报告，先验证低波、低换手、质量、动量、反转和估值因子
- [x] 实现 Tushare 财务回填进度显示：任务选择、处理进度、完成率、速率、耗时和 ETA 可见
- [x] 将 `tushare_financial_backfill_audit.md` 覆盖率展示改为百分数，CSV 保持 0-1 机器口径
- [x] 统一 `backfill-tushare-history` / `backfill-tushare-financials` audit 输出：当次详细报告按日期目录落地，固定汇总表每次仅追加 1 行关键结论
- [x] 实现 `T6.2` 数据库健康检查只读 MVP：`phase0.cli db-health` 可输出 summary/findings/report，并支持 `--fail-on`
- [x] 执行 Tushare 财务因子逐股票历史补齐至 2016Q1-2018Q1 完成，重试 failed 并复核覆盖率
- [x] 将 `db-health --scope scheduler --fail-on warning` 接入每日调度前置检查，失败时阻断对应定时任务
- [x] 将 `db-health --scope cn --fail-on error` 接入 `factor-effectiveness` 前置检查
- [x] 将 `db-health --scope cn --fail-on error` 接入 `run` 前置检查
- [ ] 继续评估哪些其他研究命令需要 `cn/error` 门禁，避免重复或过度阻断
- [x] 实现 `T2.6` `low_vol_low_turnover_quality_v1`
- [x] 实现 `T2.7` `quality_low_turnover_monthly_v1`
- [ ] 实现 `T2.8` 策略准入报告，合并 qfq_asof、因子诊断、过拟合诊断和执行诊断；当前已完成 strategy-admission MVP、全局 admission 配置层、过拟合诊断合并、窗口/约束准入复核、diagnostics suites 设计输入、preset 启动说明、诊断状态可信化和 `baseline_admission_all_v1` 全局策略集合；下一步是把每次 compare/admission 的治理报告模板固化为强制产物，并重跑 main 全候选 13 策略 admission
- [x] 在 `T2.8` 中加入 walk-forward 窗口 preset 与窗口稳健性矩阵：保留 `baseline_2y_1y` 为统一可比口径，并为低频质量策略增加 `quality_3y_1y`、`quality_4y_1y` 复核
- [x] 建立 `T2.8` 回测窗口期配置模块 V1（KISS 收缩版）：先只支持 preset 级 `start_date` / `end_date`、`expected_folds`，新增 `baseline_2y_1y_5fold` 与 `quality_3y_1y_4fold`，解决 T2.7 折数不足和窗口单一问题
- [x] 为窗口配置模块补齐最小报告字段：在 `strategy-admission` 输出 `expected_folds`、`actual_folds`、`window_start`、`window_end`、`fold_generation_warning`
- [x] 新增 `walk_forward.admission` 全局准入配置：`default_strategy_set`、`strategy_sets`、`gate`、`diagnostics.suites`；`strategy-admission` 支持 CLI `--strategy-set` 和 `--strategies` 覆盖
- [x] 将 `strategy-admission` 启动说明改为自然语言输出 preset 训练期、验证期、固定起止日期、预计折数和滚动方式
- [x] 将 `strategy-admission` 报告改为区分 `not_enabled` / `not_available` / `not_applicable` 与真实数值；新增价格口径、账户执行、行业诊断和财务诊断状态字段
- [x] 将 admission 默认价格口径收敛到 `qfq_asof`，非 `qfq_asof` 作为准入阻断原因；完整双口径矩阵仍列为后续任务
- [x] 使用 T2.7 复测 `baseline_2y_1y_5fold` + `quality_3y_1y_4fold`，验证报告能区分折数不足、参数不稳定、收益不达标和组合构造失败
  - 2026-06-10 复测 `quality_low_turnover_monthly_v1`：报告目录 `reports/strategy_admission_t2_7_quality_low_turnover_dual_preset_20260610/`，双 preset 均未通过准入，最终 action 为 `reject`；最后一折拉高已纳入 overfit 诊断，作为行情阶段依赖风险而非单独否定证据。
- [x] 实现 `T2.9` 策略失败归因诊断模块 V1：读取已有 admission / overfit / window matrix / fold 明细产物，不重新回测，把 `reject` / `retest` / `research_only` 拆解为收益、执行、组合构造、因子、参数、regime 和数据质量归因
- [x] 实现 `T2.10.1` 规则型 sleeve 组合 V1：新增 `sleeve_composite_v1`，按 `0.55/0.25/0.20` 输出 defensive quality、low-turnover momentum、risk overlay 和 `final_score`；仅作为 research-only / compare / admission 候选，不进入模拟账户或日报主线
- [x] 实现策略修饰层模块 V1：新增通用 `strategy_v2.constraints`，支持行业约束 `audit/enforce`、PIT 行业暴露审计和 strategy-admission 行业集中度复核
- [x] 完成 `sleeve_composite_v1` scoped admission 治理报告：2026-06-23 运行 `baseline_2y_1y_5fold` 与 `quality_3y_1y_4fold`，最终 action 为 `reject`，保留 research-only 边界
- [ ] 合并或在 main 复核行业集中度 100% universe 专项实验：当前证据位于 `codex/industry-weight-100-universe-experiment` 分支，实验验证取消 universe 层行业上限不会让策略机械失败，但 admission 仍全部拒绝；主线继续保留 universe 分散约束与策略层行业审计
- [ ] 按修订后的 `T2.1` 治理清单为 13 个候选落盘状态枚举：`active_research`、`baseline`、`failure_sample`、`research_only`、`deferred` 或 `admission_pass_candidate`
- [ ] 新增 T2.12 策略池完善专项：以低波低换手质量主线为核心，重构组合构造、换手控制、参数稳定性和行业集中处理；输出 paired compare/admission 与治理报告
- [ ] 新增 T2.13 因子传导图工程化专项：参考 `docs/PROJECT_ARCHITECTURE_OVERVIEW.md`，把 `INT-KMS-001` 六域传导框架落成因子本体、特征注册、市场环境归因和 admission 报告解释元数据
- [ ] T2.13 第一阶段只做只读 schema、知识资产索引和诊断报告字段，不修改策略权重、不接入模拟账户、不进入日报交易信号
- [ ] 后续运行全候选策略池 `qfq_current` / `qfq_asof` 双口径对照回测
- [ ] 精修映射标的池与行业层分析，服务调仓建议和观察池筛选
- [ ] 完成 Tushare 主源长期稳定性验证与源审计闭环；当前日级 `daily_basic` / `adj_factor` 和财务因子 2016Q1-2018Q1 已补齐并有验收报告，后续重点转为增量维护和源稳定性审计
- [x] 完成 Tushare 财务因子逐 `ts_code` 历史补齐任务：2016Q1-2018Q1 目标季度末已清空 pending/failed，并复核 `financial-pti` 与 `factor-effectiveness`
- [ ] 港股数据源质量验证通过后，再推进 `T3.1` 映射策略代码化
- [ ] 完成 `T6.1` 调度器增强：交易日历判断、运行窗口、失败重试次数与状态文件
- [x] 启动 `T6.3` 数据治理与维护编排器：Python control plane 已统一管理内置 task registry、状态机、门禁、重试、审计和长 backfill 分片监督；后续转向 System Orchestrator / TUI 汇总入口
- [ ] 启动 `T6.4` Report Dashboard Astro 静态报表门户：先实现报表 manifest P0，再接入 Astro 本地 Dashboard，默认 `127.0.0.1:4321`
- [ ] 完成 `T6.6` Daily Brief 独立内容模型与页面设计，并据此将 full daily brief 从当前 watchlist 兼容产物中拆出正式生成代码
- [x] 已完成里程碑见：`T0`（周执行清单归档段）、`T1.1`（FRED 最小实现与连通性验收）、`T2.x`（策略主线收口）

### T1.5｜Tushare 财务因子逐股票历史补齐

**目标**：补齐 `market_financial_factors` 中 2016Q1-2018Q1 的全市场财务因子，使质量类因子在更长历史窗口中具备 point-in-time 可用数据。

目标季度：

```text
2016-03-31
2016-06-30
2016-09-30
2016-12-31
2017-03-31
2017-06-30
2017-09-30
2017-12-31
2018-03-31
```

目标字段：

```text
announce_date
roe
revenue
revenue_growth
net_profit
profit_growth
operating_cash_flow
operating_cash_flow_to_net_profit
debt_to_asset
total_assets
total_liabilities
total_equity
source
updated_at
```

请求量估算：当前全市场约 5600 只股票，逐 `ts_code + period` 调 `income`、`cashflow`、`balancesheet`、`fina_indicator` 四个接口，约 `9 * 5600 * 4 = 201,600` 次 Tushare 请求。按 `120 requests/min` 预计约 28 小时；按 `180 requests/min` 预计约 19 小时，但失败/重试风险更高。

工程设计：

- 新增财务回填专用进度表：`tushare_financial_backfill_tasks`
- 每个任务粒度：`period + symbol`
- 任务状态：`pending / fetched / empty / failed`
- 记录 `request_count`、`last_error`、`updated_at`
- 支持断点续跑、重试 failed、分片运行和运行时长上限
- 默认跳过已有有效记录，只有显式传 `--replace-existing` 时才覆盖
- 不允许用空行覆盖已有有效财务记录
- CLI 已增加进度显示：目标任务数、已处理数、完成率、fetched/empty/failed、inserted_rows、rate、elapsed、eta
- 新增字段缺失补录模式：`--missing-fields-only` 使用独立任务表 `tushare_financial_missing_field_tasks`，只为已有行的空字段建任务，并按缺失字段选择最少 Tushare 接口
- 验收 Markdown 报告中的覆盖率按百分数展示，CSV 保持 0-1 机器可读口径

CLI 设计：

```bash
python -m phase0.cli backfill-tushare-financials \
  --config config.yaml \
  --start-period 2016-03-31 \
  --end-period 2018-03-31 \
  --max-requests-per-minute 120 \
  --max-runtime-minutes 180 \
  --shard-index 0 \
  --shard-count 1
```

可选参数：

```text
--period YYYY-MM-DD
--limit-symbols N
--limit-tasks N
--retry-failed
--replace-existing
--missing-fields-only
--missing-fields roe,revenue_growth,profit_growth,operating_cash_flow_to_net_profit,debt_to_asset
--shard-index N
--shard-count N
--max-runtime-minutes N
```

验收报告：

```text
reports/YYYY-MM-DD/tushare_financial_backfill_audit_YYMMDD_<range>.csv
reports/YYYY-MM-DD/tushare_financial_backfill_audit_YYMMDD_<range>.md
reports/tushare_financial_backfill_audit_summary.csv
reports/tushare_financial_backfill_audit_summary.md
reports/YYYY-MM-DD/tushare_history_backfill_audit_YYMMDD_<range>.csv
reports/YYYY-MM-DD/tushare_history_backfill_audit_YYMMDD_<range>.md
reports/tushare_history_backfill_audit_summary.csv
reports/tushare_history_backfill_audit_summary.md
```

验收维度：

```text
period
target_symbols
fetched_symbols
empty_symbols
failed_symbols
roe_coverage
revenue_growth_coverage
profit_growth_coverage
cash_flow_quality_coverage
debt_to_asset_coverage
announce_date_coverage
```

通过标准：

- 2016Q1-2018Q1 每个季度均有任务覆盖
- 每季度 `fetched + empty + failed = target_symbols`
- `failed_symbols` 经重试后低于 1%
- 所有有效记录保留 `announce_date`
- 重新运行 `financial-pti` 后仍为 PASS
- 重新运行 `factor-effectiveness`，确认质量类因子历史覆盖改善后再进入策略重建
- 详细报告可按日期目录和文件名区间检索
- 汇总表每次仅追加 1 行，能追溯历次运行关键结论

验收结果（2026-06-06）：2016Q1-2018Q1 全部 9 个目标季度末已完成回填闭环；每个季度均为 `pending=0`、`failed=0`，仅保留每季 `empty=2` 的请求成功但无有效财务数据任务。`market_financial_factors` 覆盖 `2016-03-31` 到 `2026-03-31` 共 `41` 个报告期、`193,817` 行、`5,611` 只股票；目标季度内 `announce_date` 覆盖 `100%`，`cash_flow_quality` 对应字段覆盖接近满值。`financial-pti` 复核结论为 `PASS`，`factor-effectiveness` 已重跑，`cash_flow_quality` 覆盖率 `0.9959` 并继续列为 `use` 因子。

说明：任务表中曾误生成的非目标 period（如 `2017-07-01`、`2017-08-01` 等）不属于 T1.5 原始季度末验收范围，后续可作为任务表清理项处理，不影响 T1.5 完成判断。

后续增强（2026-06-06）：`backfill-tushare-financials` 已支持字段缺失补录模式。该模式不全量覆盖已有行，而是扫描 `market_financial_factors` 中指定字段为空的既有记录，创建 `period + symbol` 级补录任务，并根据缺失字段只调用必要接口：例如 `roe / revenue_growth / profit_growth` 只需 `fina_indicator`，`operating_cash_flow_to_net_profit` 需要 `income + cashflow`，`debt_to_asset` 需要 `balancesheet + fina_indicator`。

### T1.7｜AI 语料库

**目标**：把政策法规、CCTV 新闻联播文字稿、公告风险提示、央行报告和授权研报元数据统一纳入可追溯的中文 AI 语料库，服务研究情报、事件解释、关注个股时间线和后续 RAG-ready 检索，不直接生成交易信号。

任务文档：[`docs/tasks/data-sources/AI_CORPUS_IMPLEMENTATION_TASKS.md`](tasks/data-sources/AI_CORPUS_IMPLEMENTATION_TASKS.md)

开发顺序：

1. `T1.7.1` 定义 `ai_corpus_documents` schema、provider registry、raw archive 路径和 fixture 规则。
2. `T1.7.2-T1.7.4` 先实现 gov.cn 政策文件库：`/search-gov/data` 列表 provider、正文 parser、机构 / 主题字典缓存和 `npr` 兼容 API。
3. `T1.7.5` 实现 CCTV 新闻联播 live provider，覆盖日期页、完整节目页和分段正文；fixture 保留为 parser 回归测试。
4. `T1.7.6` 实现 CNInfo / AkShare 公告 provider，先聚焦异常波动公告和交易风险提示公告；当前已完成公告列表 MVP，公告详情页正文 / PDF parser 后续增强。
5. `T1.7.7-T1.7.9` 接入本地存储、CLI 查询、`market_text_events` 桥接、PBOC 报告、研报元数据、监管规则和 RAG-ready 索引。

边界：

- 不依赖 Tushare 网站或 Tushare 高权限接口作为首期主源。
- 不抓取、保存或再分发无授权券商研报全文。
- 不用正文发布时间替代本系统 `as_of_time`。
- 不把政策、公告、新闻或 LLM 摘要直接接入主 ranker。

第一版验收：

- `npr(org="国务院", ptype="科技", end_date="2025-08-26 17:00:00")` 能基于 fixture 返回 `国务院关于深入实施“人工智能+”行动的意见`、`国发〔2025〕11号` 和非空 `content_html`。
- `fetch_cctv_news(date="20260703", include_segments=True)` 能抓取央视网公开页面或基于 fixture 返回新闻联播完整节目和分段节目，并抽取标题、URL、`content_id`、正文 HTML、raw path 和 parser version。
- gov.cn 正文 parser 能抽取元数据表、`#UCAP-CONTENT`、正文 hash、raw path 和 parser version。
- `published_at`、`issued_at`、`ingested_at`、`as_of_time` 不混用；回测可见时间以本系统抓取成功时间为准。
- 同一政策文件重复 upsert 不重复入库；去重键覆盖 `source_id / url / pcode + title + puborg + pubtime / content_hash`。
- CCTV 当前为 live MVP；每日编排器默认自然日 `20:45` 抓当天文稿，空结果通过 `--min-rows 1` 触发失败重试。CNInfo 当前为公告列表 MVP；每日编排器默认 `20:20` 抓 `risk_events` 市场风险公告，落库后按标题细分事件类型，但暂不承诺公告详情页全文 / PDF 解析。

### T6.2｜数据库健康检查与数据质量门禁

**目标**：把分散的数据质量检查统一为可调度、可审计、可作为门禁的只读健康检查入口，避免脏数据、缺失数据、future leakage 和调度失败静默进入回测或日报链路。

已完成 MVP：

- 新增 `phase0/db_health.py`
- 新增 CLI：`python -m phase0.cli db-health --config config.yaml`
- 支持 `--scope all|cn|financial|cross_market|scheduler`
- 支持 `--as-of YYYY-MM-DD`
- 支持 `--output-dir`
- 支持 `--fail-on error|warning|never`
- 输出 `database_health_summary.csv`、`database_health_findings.csv`、`database_health_report.md`
- 默认只读数据库，不写健康表

当前检查范围：

- A 股本地库：表结构、最新交易日、覆盖率、滞后、OHLC、非正价格、负成交量/成交额、daily_basic 覆盖、复权因子
- 财务因子：表结构、`announce_date` 覆盖、不可能时间线、核心因子覆盖、Tushare backfill task 状态
- 跨市场：US/HK 数据库、配置标的 freshness、OHLC、source audit
- 调度状态：`logs/scheduler/*.last` 与 source audit 最新运行记录

当前验收（2026-06-05）：

- `scheduler` 范围：PASS
- `cn` 范围：PASS
- `all` 范围：WARNING，`errors=0`、`warnings=6`
- `--fail-on warning` 已验证返回退出码 `2`

下一步：

- `db-health --scope scheduler --fail-on warning` 已接入调度器前置检查
- `db-health --scope cn --fail-on error` 已接入 `factor-effectiveness` 前置检查
- `db-health --scope cn --fail-on error` 已接入 `run` 前置检查
- OHLC 异常样本输出已补齐，当前样本已能直接定位到 `CNY=X` 与 `HK.09633` 的具体异常行
- 继续评估哪些其他研究命令需要 `cn/error` 门禁，避免重复或过度阻断
- `daily_basic.pe_ratio` 覆盖不足已改为诊断项：PE 为空通常代表亏损或 TTM 盈利不可计算，不再作为 daily_basic 硬覆盖率门槛；`market_cap`、`pb_ratio`、`turnover_rate` 仍保留硬覆盖检查

### T6.3｜数据治理与维护编排器

**目标**：把当前 shell 调度器、`db-health` 门禁、任务重试、运行状态、backfill 分片监督和审计报告索引，演进为统一的本地数据治理控制平面。

专项任务单：

- [`docs/tasks/ops/DATA_GOVERNANCE_ORCHESTRATOR_TASKS.md`](tasks/ops/DATA_GOVERNANCE_ORCHESTRATOR_TASKS.md)

推荐架构模式：

- `Control Plane / Data Plane`：编排器只做调度、门禁、状态和监督，现有 CLI 继续负责真实数据生产。
- `Command Registry`：统一声明任务命令、时间窗口、交易日历、依赖、健康门禁、重试和产物规则。
- `State Machine`：任务状态统一为 `pending / running / succeeded / failed / skipped / blocked / cancelled`。
- `Policy Gate`：统一执行交易日历、锁、依赖、失败次数和 `db-health` 检查。
- `Supervisor`：管理长 backfill 子进程、分片、停止和恢复。
- `Append-only Audit Ledger`：运行事件与关键结论只追加，详细报告仍按日期目录输出。

第一阶段交付：

- 新增 `phase0/maintenance_orchestrator.py`
- 新增 `phase0.cli maintain tick/status/supervise/run/stop/resume`
- 新增 `data/maintenance/maintenance.sqlite`
- 已实现 `maintain tick --dry-run`、`maintain status --write-report/--output-md` 与 `maintain supervise`
- 保持 cron 单入口，但逐步把 shell 内部调度逻辑迁移到 Python 编排器
- 后续在维护编排器之上增加轻量 `System Orchestrator`：提供 `system status/run/tui`，统一汇总维护、研究、交付、账户和关注个股分析状态

边界：

- 第一版不引入 Airflow、Celery、Redis、systemd service 或 Kubernetes。
- 第一版先通过现有 CLI 命令数组适配旧任务，不直接重构业务模块。
- backfill 详细报告和 summary audit 继续由现有 backfill 模块生成，编排器只登记路径、状态和关键结论。
- `System Orchestrator` 只做统一入口、registry、状态汇总和 UI 后端接口，不承载所有业务规则。

### T6.4｜Report Dashboard Astro 静态报表门户

**目标**：把 `compare`、`strategy-admission`、`brief`、`maintenance`、`db-health` 等流程生成的 Markdown、HTML、CSV 产物统一登记为 manifest，并由 Astro 生成本地静态 Dashboard。

专项任务单：

- [`docs/tasks/ops/REPORT_DASHBOARD_ASTRO_TASKS.md`](tasks/ops/REPORT_DASHBOARD_ASTRO_TASKS.md)

推荐架构模式：

- `Report Registry`：Python 侧统一登记 run 与 artifact，当前输出 `reports/runs/report_dashboard/manifest.json`。
- `Static Dashboard`：Astro 只消费 manifest，不直接耦合各业务命令。
- `Explicit Register + Scan Fallback`：新流程显式登记，历史产物用扫描兜底。
- `Local-only Preview`：默认绑定 `127.0.0.1:4321`，不作为远程服务暴露。

阶段交付：

- [x] P0 只读 manifest MVP。
- [ ] P1 Astro Dashboard MVP。
- [ ] P2 核心流程自动登记。
- [ ] P3 本地服务体验与 `system status` 展示集成。

### T6.5｜Report Output Path Standardization

**目标**：把后续 Markdown、HTML、CSV 程序产物统一写入不可变 run 目录，并保留历史 `reports/` 产物的只读扫描兼容。

专项计划：

- [`docs/superpowers/plans/2026-06-23-report-output-path-standardization.md`](superpowers/plans/2026-06-23-report-output-path-standardization.md)

当前状态：

- [x] 新增 `phase0/report_paths.py`，提供标准 run、latest、scratch 路径 helper。
- [x] `strategy-admission` 默认输出迁移到 `reports/runs/...`，显式 `--output-dir` 保持旧兼容。
- [x] `db-health` 和 `factor-effectiveness` 默认输出迁移到 `reports/runs/...`，显式输出目录保持旧兼容。
- [x] watchlist latest 新增 `reports/runs/latest/watchlist/index.html` 与 `watchlist.css`，旧 `reports/watchlist_today/index.html` / `watchlist.css` 暂保留为兼容镜像。
- [x] watchlist HTML 生成从 Python 内联字符串迁移到 Jinja2 模板；样式迁移到独立 CSS，Belafonte Day / Night 主题、大屏断点、表格视觉、主题切换脚本和回到顶部按钮按 `/brief/ui-test/` 参考样例对齐，远端同步复制完整 HTML + CSS bundle。
- [x] watchlist 表格区分模拟账户实盘模拟口径和策略研究信号口径：短表头 `持仓天数` 来自 `account_positions` 已确认持仓快照，`信号持有天数` 保留策略内部 `held_days`。
- [x] account-bill latest 新增 `reports/runs/latest/account_bill/index.html` 与 `reports/account_bill_today/index.html`，存在确认账单 HTML 时自动同步远端 `/account-bill/`。
- [x] `dashboard scan` 已识别 `standard_run` 和 legacy categories。
- [ ] 仍未批量迁移历史文件，后续只通过 scanner 兼容读取。

### T6.6｜Daily Brief 独立内容模型与页面设计

**目标**：把正式 daily brief 从当前 `brief watchlist` 兼容页面中拆出，形成独立内容模型、页面信息架构、数据契约和生成代码。Daily brief 是每日盘前决策驾驶舱，watchlist 是其中的观察池组件；两者不能继续等同。

专项任务单：

- [`docs/tasks/ops/DAILY_BRIEF_CONTENT_MODEL_TASKS.md`](tasks/ops/DAILY_BRIEF_CONTENT_MODEL_TASKS.md)

边界：

- daily brief 不绕过 `strategy-admission`、execution gate、数据健康门禁或账户约束生成交易信号。
- 当前无合格 candidate 时，日报必须明确显示“兼容基线 / 研究样本 / 无正式准入策略”的状态，不能把 watchlist 解释为正式推荐。
- 模拟账户收益、持仓和账单只使用已确认 OHLCV 交易日；未生成确认账单时，账户摘要按初始资金和暂无收益率口径展示。

阶段交付：

- [x] P0 内容模型与页面结构：已定义 metadata、data freshness、account summary、market context、strategy status、portfolio plan、watchlist digest、risk checks、artifacts。
- [ ] P1 独立 HTML 页面：新增 `daily_brief` renderer 和 latest 镜像，`brief daily` 输出正式日报，`brief watchlist` 保持观察池页面。
- [ ] P2 数据契约与测试：为缺数据、非交易日、无账单、无合格 candidate、健康门禁异常等场景补测试。
- [ ] P3 Dashboard / 远端同步：将 daily brief artifact 注册到 report manifest，并明确 `/brief/` 指向正式日报还是阶段 watchlist 的迁移窗口。

### 条件满足后再推进

- [x] 将 Tushare 纳入 Phase 0 数据源 smoke test 与 pre-run update 链路
- [x] 新增 `us_market_history.sqlite`，让当前跨市场 overlay 从落库数据读取
- [x] 预留 `hk_market_history.sqlite`，但在港股数据源生产化前不挂应用
- [ ] 完成 Tushare 主源长期稳定性验证与源审计闭环
- [ ] 将 `db-health` 继续接入其他适合的关键研究命令前置门禁，并明确哪些命令不应阻断
- [ ] 执行统一周执行附件中的数据源升级计划
- [x] 优先引入 FRED 作为宏观 / 利率 / VIX 主源（最小实现与连通性验收已完成）
- [x] 再引入 Tiingo 作为美股个股 / ETF 主源（最小实现与连通性验收已完成）
- [x] 保留 `yfinance` 作为 fallback，不做一次性全替换
- [x] 强化 `07:30` 阶段试用观察池自动生成链路，并形成每日可复盘归档的最小闭环
- [ ] 按 `T6.6` 内容模型将正式 daily brief 从当前 watchlist 兼容实现中拆出
- [ ] 精修映射标的池与行业层分析
- [ ] 补全港股映射 A 股候选策略代码，前置条件是港股历史数据源质量验证通过
- [ ] 在规则型 / 因子型信号链路稳定后，再引入 sklearn 基线模型作为研究对照，不进入首批交易建议主线

---

## 附：核心参考文件

- `README.md`
- `CLAUDE.md`
- `config.yaml`
- `docs/PROJECT_ARCHITECTURE_OVERVIEW.md`
- `reports/phase0_effectiveness_report.md`
- `reports/phase0_walk_forward_report.md`
- `reports/phase0_strategy_change_log.md`
- `data/universe/local_factor_universe_report.md`
