# T2.1｜Phase 0 候选策略池治理清单

父级计划：[`DEVELOPMENT_PLAN.md`](../../DEVELOPMENT_PLAN.md)
架构约束：[`PROJECT_ARCHITECTURE_OVERVIEW.md`](../../PROJECT_ARCHITECTURE_OVERVIEW.md)
任务索引：[`docs/tasks/README.md`](../README.md)

## T2.1.0 当前结论

Phase 0 的基础工程闭环已经完成，但策略池当前没有严格 `qfq_asof` / PIT / 成本后 / admission 口径下可进入 paper review、模拟账户、日报或 watchlist 正式链路的合格候选。

当前 T2.1 的职责不再是继续扩大候选数量，而是把候选池改为可治理、可复核、可降级的策略研究清单：

- 当前 selected candidate：无
- 当前正式 baseline：无严格准入合格 baseline
- 当前兼容 baseline：`legacy_momentum_low_turnover_v1`，仅作旧 `qfq_current` 口径兼容参考、动量 sleeve 输入和失败对照样本
- 当前全局准入集合：`baseline_admission_all_v1`，包含 12 个候选策略
- 当前重点研发集合：`price_volume_low_turnover_v1` 防守 / 选择性角色治理；`sleeve_composite_v1` 低换手改造已验证为 research-only 经验，不作为当前主动调参主线
- 当前治理工具新增：`strategy-role-card`，用于把 admission、失败归因、市场状态、持仓暴露和反事实实验汇总成可复查的策略角色卡
- 当前角色卡批量验证结论：只有 `price_volume_low_turnover_v1` 暂时支持“防守 / 选择性研究样本”标签；质量线和低换手 sleeve 只能作为诊断样本
- 当前角色卡 manifest 结论：已生成角色卡的三条候选在正式流程中均为 `no_eligible_strategy`
- 当前新增策略池角色结论：`price_volume_low_turnover_v1` 只能作为防守 / 选择性研究候选；`strong_index_participation_v1`、`strong_index_participation_dynamic_trigger_v1` 和 `strong_market_liquid_breadth_participation_v1` 三个强沪深300参与型 research-only 版本均为 `reject`；强市场参与型角色仍无合格候选
- 当前强市场候选归因结论：I35 已对 I15/I18/I20 补齐真实日度持仓级 CSI300 权重归因，确认主要失败模式是强指数阶段低参与度和低沪深300权重覆盖；下一步不继续微调这三条候选，而是预注册新的强市场有效参与假设
- 当前新候选设计：I36 已预注册 `strong_market_effective_participation_v1`，要求强市场折同时验证最低仓位、最低沪深300权重覆盖和前20权重股覆盖；下一轮若实现，必须在 scoped admission 后立刻跑 holdings exposure 与 CSI300 attribution
- 当前新候选验证结论：I37 已实现并验证 `strong_market_effective_participation_v1`，并在 I38 前修正单股权重上限口径后复跑；admission 仍为 `reject`，第 5 折强相关窗口平均实盘暴露仅 `10.29%`、持有沪深300权重 `2.13%`、前20覆盖 `2.79%`，远低于 I36 预设底线，首版停止
- 当前强市场可达性诊断结论：I38 已完成强市场候选池可达性诊断；第 5 折强市场日平均可买候选只覆盖沪深300约 `9.05%` 权重，当前 panel 可见权重前20股票只覆盖约 `3.93%`，说明当前强市场参与型路线的主要瓶颈在候选生成和核心权重可达性，而不是继续微调组合权重器
- 当前强市场下一步设计：I39 已完成候选生成层重设计，下一轮不直接写新交易策略，先做 `strategy-core-reachability-diagnostic` 只读诊断，验证 T-1 CSI300 核心权重和完整基准 Top20 经过 PIT、流动性、行业和基础风险过滤后是否仍可达
- 当前强市场核心可达性结论：I40 已完成完整基准核心权重只读诊断；五折 as-of 覆盖均为 `100%`，平均可达核心权重约 `53%` 到 `58%`，完整 Top20 可达约 `31%` 到 `34%`。这说明本地 PIT 数据不是主要障碍，I37 失败主要来自过窄 alpha / hard filters 把核心权重从约 `55%` 砍到约 `9%`
- 当前 Top 权重缺口结论：I44 已完成 `csi300_core_seed_panel` 只读实验，并修正 I39/I43 的 Top20 门槛口径。Top20 绝对权重是沪深300当期集中度，不应固定要求超过 `35%`；可达性应看覆盖率。显式保留 as-of 可见的沪深300核心成分后，五折均为 `pass`：平均核心可达权重 `59.45%`，平均核心覆盖率 `99.28%`，平均 Top20 覆盖率 `99.95%`。下一步可以预注册新的强市场核心参与候选，但不能把 I44 解释为交易策略通过或固定买沪深300前20只。
- 当前强市场新候选设计：I45 已预注册 `strong_market_core_participation_v1`。新候选基于 I44 的 core seed panel，不复制沪深300、不固定买前20只；先保证核心股进入候选池，再用趋势、流动性、风险和行业约束决定实际持仓。下一步 I46 可做最小实现，并必须跑 scoped admission、holdings exposure、CSI300 attribution 和 failure attribution。
- 当前强市场稳定底仓结论：I47 已实现 `strong_market_stable_core_base_v1`，把强市场参与机制拆成稳定核心底仓和小比例 alpha 卫星。结论仍为 `reject`，但它把平均实盘暴露从 I46 的约 `3.93%` 提高到约 `36.58%`，把 Top20 覆盖率从约 `3.66%` 提高到约 `58.16%`，并把平均年化换手从 `4.08` 降到 `0.68`。这说明稳定底仓机制有效，但收益、Sharpe、正收益折、行业偏离和 overfit 仍未过关。
- 当前强市场稳定底仓拆分结论：I48 已完成 `core-only` / `core+satellite` / `satellite-only` 拆分归因。短窗口 `baseline_2y_1y_5fold` 仅作为策略横向比较；长窗口 `quality_3y_1y_4fold` 和 `quality_4y_1y` 用于稳定性复核。结论是 I47 的改善主要来自稳定核心底仓，不来自卫星增强；卫星增强在短窗口里有少数阶段性交易，但长窗口下基本没有稳定贡献。`core-only` / `satellite-only` 是 attribution-only 归因变体，`core+satellite` 只是 I47 `strong_market_stable_core_base_v1` 的归因对照口径；三者均不得作为新增正式候选进入 `baseline_admission_all_v1`、paper review、模拟账户、日报或 watchlist。
- 当前强市场 benchmark-aware 设计：I50 已预注册 `strong_market_benchmark_aware_core_v1`。新候选不复制沪深300、不固定买前20只，而是把强基准阶段的最低实盘仓位、持有沪深300权重、Top20 覆盖和行业主动偏离写成显式验收指标。下一步 I51 若实现，必须先跑 scoped admission、holdings exposure、CSI300 attribution、failure attribution 和长窗口稳定性检查。
- 当前新增专项探索：盘中行情信号择时买卖已立项为 `T2.14`，仅作为后续数据与验证框架探索，不属于当前已研究候选策略
- 当前禁止动作：不凭 compare 排名、旧 `qfq_current` 结果或单次 scoped admission 相对最优结论进入模拟账户或日报

策略池治理服务于两个北极星目标：

1. 找到至少一个适合当前市场环境、能够指导个人实盘操作决策、并在成本后具备较可观盈利潜力的合格量化策略。
2. 形成覆盖不同市场环境和市场风格的量化策略池，并沉淀一套可复查、可执行、可迭代的策略选择方法论。

因此，策略池不是候选堆积。每个 active research 或 admission pass 候选都必须逐步补齐市场环境标签、风格标签、相对基准表现、失败模式、换手和执行约束说明，最终能够支持“当前市场该选用、降权、停用或观察哪类量化策略”的方法论判断。

旧 `qfq_current` 兼容指标只能作为历史参考：

| 指标 | `legacy_momentum_low_turnover_v1` 旧兼容结果 | 当前解释 |
| --- | ---: | --- |
| `annualized_return_mean` | `0.1331` | 兼容参考，不代表严格准入 |
| `sharpe_mean` | `1.0083` | 兼容参考，不代表严格准入 |
| `max_drawdown_mean` | `-0.1042` | 兼容参考，不代表严格准入 |
| `win_rate_mean` | `0.5110` | 兼容参考，不代表严格准入 |
| `turnover_annual_mean` | `1.50` | 兼容参考，不代表严格准入 |

## T2.1.1 策略池治理边界

### 必须遵守

- 历史回测默认使用 `qfq_asof`，`qfq_current` 只允许作为兼容对照。
- 历史股票池必须使用每折 point-in-time universe。
- 交易成本必须包含当前主测试口径：`slippage = 0.00246`、`commission = 0.00025`、`stamp_duty_sell = 0.0005`。
- 任何候选进入 paper review、模拟账户、日报或 watchlist 正式链路前，必须通过 `strategy-admission`。
- compare 只能给出相对排序和研究线索，不能替代 admission。
- research-only 策略可以参与 compare / scoped admission / 失败归因，但不能输出为交易信号。
- 行业集中度 100% universe 实验只作为分支研究证据；主线仍保留 universe 分散约束与策略层行业审计。
- T2.13 因子传导图只作为本体、特征注册和失败归因元数据，不直接给策略权重。
- 策略池入池治理必须记录策略适用的市场状态、市场风格、相对优势基准、主要失败模式和启用 / 降权 / 停用条件。
- 策略池角色标签只表示研究治理角色，不表示资金分配权重、买卖建议或实盘启用权限。
- 如果某个市场环境没有通过 admission 的对应角色候选，策略选择方法论必须输出“暂无合格策略”，不能临时拼接 research-only 候选。
- 强沪深300跑输不能直接等同于“应当提高仓位”。I11 反事实显示，把 `price_volume_low_turnover_v1` 的最低暴露简单抬到 `65%` 会恶化收益、Sharpe 和回撤。

### 当前 admission 门槛

| 维度 | 当前门槛 |
| --- | --- |
| 收益 | `annualized_return_mean > 0` |
| 风险收益 | `sharpe_mean > 0.5` |
| 回撤 | `max_drawdown_mean > -0.25` |
| 正收益折比例 | `positive_fold_ratio >= 0.75` |
| 换手 | `turnover_annual_mean <= 3.0`，`turnover_annual_max <= 5.0` |
| 过拟合 | `overfit_risk <= medium` |
| 参数 | 要求参数稳定性检查 |
| 行业 | 要求行业集中度检查 |
| 因子 | 要求因子诊断 |
| 市场环境 | 要求记录适用 / 不适用市场状态与风格标签 |
| 策略选择方法论 | 要求输出市场环境识别、策略适配、启用、降权、停用和复盘更新条件 |
| 价格口径 | 要求 `qfq_asof` |
| 样本治理 | symbol-scope 至少 `20` 个 fold 与 `20` 个 symbol；portfolio-scope 至少 `4` 个 portfolio fold |

## T2.1.2 当前策略集合

配置层当前以 `baseline_admission_all_v1` 作为全局治理集合，包含 12 个策略：

| 策略 | 当前角色 | 当前动作 | 进入正式链路条件 |
| --- | --- | --- | --- |
| `legacy_momentum` | 历史 baseline / 失败样本 | 保留对照，不再优化为主线 | 仅作回归对照，不直接进入 |
| `legacy_momentum_low_turnover_v1` | 兼容 baseline / 动量 sleeve 输入 | 保留为研究样本与解释链路兼容输入 | 必须重新通过严格 admission；当前未通过 |
| `ma_kline_baseline_v1` | 透明规则 baseline / 失败样本 | 保留地板策略，用于判断复杂策略是否真有增益 | 必须重新通过严格 admission；当前不作为主线 |
| `residual_momentum_reversal_v1` | 高换手价格行为失败样本 | 降级，不继续作为当前主线 | 除非新增低换手重构证据，否则不重启 |
| `residual_momentum_reversal_v2` | 高换手价格行为失败样本 | 降级，不继续作为当前主线 | 除非新增低换手重构证据，否则不重启 |
| `quality_growth_price_v1` | 质量成长早期候选 | 保留为质量因子诊断输入 | 必须证明质量暴露可稳定转化为收益 |
| `low_vol_low_turnover_quality_v1` | 质量因子诊断资产 | I25 同折归因显示质量线只在最近一折明显胜出，质量 bucket 不稳定；停止当前构造的小参数微调 | 只有新预注册质量假设且 bucket 单调性稳定后才重启 |
| `quality_low_turnover_monthly_v1` | 低频质量对照候选 | 作为质量线对照样本，避免用最近单折变好解释长期有效 | 通过双 preset admission，且不是单折驱动 |
| `multifactor_volume_price_filter_v1` | 多因子量价失败样本 | 保留为诊断，不继续堆叠参数 | 需先证明低换手和因子域覆盖改善 |
| `core_selection_quality_momentum_v1` | 质量 + 动量复合候选 | 保留为组合构造对照 | 需证明复合后降低而非放大 churn |
| `theme_exposure_momentum_v1` | 主题暴露候选 / 失败样本 | 保留研究，不作为主 ranker | 需先补齐主题/行业轮动 as-of 数据 |
| `sleeve_composite_v1` | research-only 组合诊断候选 | I26 确认每日重排导致低持仓保留和高换手；同时收益、Sharpe、回撤、正收益折比例、行业集中和 overfit 均未过关；不再微调原策略权重 | 当前 scoped admission 为 `reject`；若继续，只能新建低 churn 候选并重新 scoped admission |
| `sleeve_composite_low_churn_v1` | 低 churn 组合构造研究候选 | I27 证明低 churn 机制能显著降低换手并改善收益；I28 显示旧折亏损不是单一股票、单一行业或市场压力可充分解释，质量桶贡献也不稳定 | 只能 research-only；不继续用当前证据调小参数，不能进入 paper review、模拟、日报或 watchlist |
| `price_volume_low_turnover_v1` | 防守 / 选择性 research-only 候选 | I29 已形成研究适配 / 降权 / 停用规则：弱基准或风险压力环境下可作为研究样本，强沪深300环境下不强行承担参与角色 | 需重新进入主配置与全量 admission；当前不允许 paper review、模拟、日报、watchlist 或实盘辅助 |
| `strong_index_participation_v1` | 强沪深300参与型 research-only 首版候选 | 保留为失败归因样本；先查为什么长期空仓，不现场调参 | I15 scoped admission 为 `reject`；当前不允许 paper review、模拟、日报或 watchlist |
| `strong_index_participation_dynamic_trigger_v1` | 强沪深300参与型 timing-only 失败样本 | 保留为 I18 对照；不继续微调动态触发器 | I18 scoped admission 为 `reject`；动态触发改善参与度但引入最大换手超标，当前不允许 paper review、模拟、日报或 watchlist |
| `strong_market_liquid_breadth_participation_v1` | 强市场宽篮子参与型失败样本 | 保留为 I20 对照；不继续局部参数调优 | I20 scoped admission 为 `reject`；换手改善但收益质量、正收益折比例和行业审计仍未达标，当前不允许 paper review、模拟、日报或 watchlist |

## T2.1.3 策略池角色与选择方法论

当前策略研发目标已经从“找一个万能策略”调整为“形成覆盖不同市场环境和市场风格的策略池，并沉淀策略选择方法论”。

策略池角色按以下口径治理：

| 角色 | 含义 | 当前状态 |
| --- | --- | --- |
| `core_candidate` | 已通过严格 gate，可进入 paper-review eligibility 检查的核心候选 | 当前为空 |
| `satellite_alpha_candidate` | 有局部 alpha 迹象，但不能作为主策略 | `price_volume_low_turnover_v1`、质量低换手候选仍是 research-only |
| `diversifier_candidate` | 未来可能改善组合曲线或风格分散，但仍需 admission | 质量低换手候选与 `sleeve_composite_v1` 只保留研究价值 |
| `regime_detector_candidate` | 用于理解市场状态，不直接输出组合 | 主题/行业方向仍缺 as-of 数据 |
| `failure_diagnostic` | 用来解释失败模式和改进方向 | 多数旧候选当前属于此类 |
| `rejected_overlay` | 已被反证的覆盖层或约束方案 | I11 `min_exposure=0.65` 覆盖层 |
| `research_archive` | 保留历史参考，不输出信号 | 旧动量、高换手和多因子失败样本 |

I10/I11 对 `price_volume_low_turnover_v1` 的最新约束：

| 证据 | 结论 | 边界 |
| --- | --- | --- |
| I10 日度持仓暴露诊断 | 强沪深300跑输切片平均 live exposure 约 `44.17%`，平均第一大行业占比约 `14.56%`，最大第一大行业占比 `20.00%` | 更像低参与度，不像行业拥挤；但不能证明低配沪深300成分股 |
| I11 最低暴露反事实 | `min_exposure=0.65` 后 combined 年化 `6.32% -> 3.80%`，Sharpe `0.60 -> 0.34`，最大回撤 `-9.53% -> -14.94%` | 简单最低仓位覆盖不应落成默认规则 |

当前选择方法：

1. 先判断市场状态：弱基准 / 风险压力、强沪深300 / 风险偏好、混合或不清晰。
2. 再匹配策略角色：防守 / 选择性、强指数参与、均衡核心、组合分散。
3. 只允许通过 admission 的候选进入后续 paper-review eligibility 检查。
4. 若对应角色没有 admission pass 候选，输出“暂无合格策略”，继续研发该角色缺口。
5. research-only 角色可以用于解释、比较和下一轮研发，不得输出买卖、模拟、日报或 watchlist 信号。

## T2.1.4 当前优先级

### P0：当前必须优先处理

1. **全候选 admission 治理表持续维护**

   - I22 已建立当前基线治理表，覆盖 `baseline_admission_all_v1` 的 12 个候选、`price_volume_low_turnover_v1`、I15/I18/I20 强市场失败样本和 I11 最低仓位反事实。
   - 后续每轮 compare / admission 后继续维护运行日期、数据口径、preset、策略集合、是否 scoped、是否 research-only。
   - 后续报告仍必须输出 action：`reject`、`retest`、`research_only` 或 `admission_pass_candidate`。

2. **`price_volume_low_turnover_v1` 防守 / 选择性角色治理**

   - I25 已确认质量线当前不适合作为主线继续小参数微调。
   - 价量线仍是当前最有研究价值的防守 / 选择性资产，但不能强行承担强沪深300参与角色。
   - I29 已明确它的研究适配 / 降权 / 停用条件和失败复盘口径：弱基准或风险压力环境下可作为研究比较样本；强沪深300或广谱风险偏好环境下必须降权其角色适配，正式工作流仍输出“暂无合格策略”。
   - I30 已把这种角色卡格式抽象成 `strategy-role-card` 生成器，先对 `price_volume_low_turnover_v1` 生成 6 条研究治理规则。
   - I31 已把角色卡生成器套到质量线和 sleeve 线，并修正过度乐观标签：只有 `price_volume_low_turnover_v1` 保留防守 / 选择性研究样本标签。
   - I32 已生成角色卡 manifest，确认已生成卡片的三条候选正式流程均为 `no_eligible_strategy`。
   - 下一步应先重新把该候选纳入当前全量 admission 刷新，或继续把角色卡扩展到全部候选池。

3. **`sleeve_composite_v1` 降换手重构**

   - 当前 scoped admission 为 `reject`，不能进入正式链路。
   - I26 已确认当前版本平均每日只保留约 `47%` 到 `51%` 的上一日持仓，10 只股票里每天约卖出 / 买入 5 只。
   - I26 同时确认高 churn 不是唯一阻断；收益、Sharpe、回撤、正收益折比例、行业集中和 overfit 仍是硬失败项。
   - I27 已新建 `sleeve_composite_low_churn_v1`，把持仓保留率从约 `48%` 提高到约 `96%`，把 baseline 年化换手从 `33.23` 降到 `3.06`。
   - I27 仍为 `reject`：baseline Sharpe `0.1914`、回撤 `-25.67%`、正收益折比例 `0.60`、overfit `high`。
   - I28 已解释低 churn 后第 1、2 折仍然亏的边界：旧折亏损分散在多只股票和多个行业，市场压力有影响但不是充分解释，质量桶贡献不稳定。
   - 当前不再把 sleeve 路线作为主动小参数调优主线；低 churn 构造保留为组合工程经验。

4. **T2.13 因子域元数据接入策略诊断**

   - 把六域因子传导框架先用于失败归因和 admission 报告解释。
   - 不把因子域矩阵直接转成策略权重。
   - 用于区分策略失效、因子域缺失、市场环境未覆盖和外部事件未建模。

5. **策略池角色表与强指数参与候选缺口**

   - 维护 `iter_12__strategy_pool_role_scorecard` 产物作为当前策略选择方法论证据。
   - 把 `price_volume_low_turnover_v1` 保持为防守 / 选择性 research-only 候选。
   - 单独设计强沪深300行情参与型候选，不用简单最低仓位覆盖修补现有候选。
   - I13 已确认本地有 `SH.000300` 指数日线和市场状态诊断能力，但没有 CSI300 成分/权重表；强指数参与候选只能先做指数趋势/收益/波动/回撤口径，不能声称成分复制或主动权重归因。
   - I15 已实现 `strong_index_participation_v1` research-only 首版并完成 scoped admission，结论为 `reject`：前四折基本空仓，第五折有交易但跑输强沪深300；下一步应先做失败归因，不应现场调松阈值。
   - I16 已完成空仓 / 过滤漏斗诊断：个股硬过滤平均仍有 `6` 到 `10` 只候选，主要断点是强指数状态稀疏和固定 20 日调仓错过短窗口；第 5 折有交易但平均只有 `5` 只持仓，仍跑输强沪深300。
   - I17 已完成下一假设预注册设计：下一轮只测试动态触发检查点，即在保留 I15 强指数定义和个股过滤的前提下，允许 D-1 可见强指数状态从 false 变 true 时额外检查一次候选；不先调松强指数阈值或 admission gate。
   - I18 已实现并验证 `strong_index_participation_dynamic_trigger_v1`：第 1 折和第 5 折参与度改善，但 admission 仍为 `reject`；正收益折比例只有 `0.40`，Sharpe `0.1516`，最大年化换手 `5.7273` 超过门槛，第 5 折仍跑输强沪深300。
   - I19 已完成新假设设计：停止继续微调 I18 的触发器，转向 `strong_market_liquid_breadth_participation_v1`，用 T-1 可见沪深300强趋势状态和本地已有 PIT 股票数据，测试“强市场里买更流动、更有趋势参与度、行业不过度拥挤的一篮子股票”是否比 I15/I18 更合理。
   - I20 已实现并验证 `strong_market_liquid_breadth_participation_v1`：换手显著改善，年化换手最大值降到 `2.7491`，但 admission 仍为 `reject`；正收益折比例只有 `0.20`，Sharpe `0.0743`，第 5 折仍跑输强沪深300，行业审计仍有失败窗口。
   - I21 已完成策略池优先级复盘：暂停强市场参与型局部调参；下一步优先做全候选治理刷新、`price_volume_low_turnover_v1` 角色治理，以及 CSI300 成分/权重 as-of 数据层 spike。
   - I22 已完成全候选治理刷新：建立 17 行候选治理表，覆盖 12 个全量 admission 候选、`price_volume_low_turnover_v1`、I15/I18/I20 强市场失败样本和 I11 最低仓位反事实；确认当前无 paper-review eligible 策略，强市场参与型角色仍为空。
   - I23 已实现 `index-asof-audit` 只读数据能力审计：本地 CSI300 元数据、指数行情和交易日覆盖可用，但缺少 point-in-time 成分表和权重表；因此当前不能做成分级低配/超配、主动权重或权重股遗漏归因。
   - I24 已完成低换手质量线失败图谱：行业集中不再是 I2-I4 后的主阻断项，真正阻断是 2021-2024 多个 baseline 验证折收益弱；质量线仍只能 research-only。
   - I25 已完成 I4 质量线与 I7 价量线同折归因：质量线在 baseline 折 1-4 都弱于价量线，只在最新第 5 折明显更强；质量 bucket 不稳定，当前质量构造降级为诊断资产。
   - I26 已完成 `sleeve_composite_v1` 换手 / churn 诊断：年化换手 `25.93` 到 `44.96`，平均每日持仓保留率约 `47%` 到 `51%`，当前不应继续微调原策略权重。
   - I27 已实现并验证 `sleeve_composite_low_churn_v1`：低 churn 构造显著改善换手和持仓稳定性，但 admission 仍为 `reject`，不能进入正式链路。
   - I28 已完成 `sleeve_composite_low_churn_v1` 旧折亏损归因：旧折亏损不是单一股票或单一行业问题，也不能只用市场压力解释；继续调小参数的过拟合风险较高。
   - I29 已完成 `price_volume_low_turnover_v1` 防守 / 选择性角色规则：当前支持 research-only 的研究适配、降权和停用边界，但不支持启用为交易策略。
   - I30 已新增 `strategy-role-card` 生成器，开始把每轮策略结论转为更固定、更平实的角色卡格式。
   - I31 已验证角色卡批量生成，并修正弱市标签规则，防止把 `reject` 或弱市表现不足的候选误标为防守样本。
   - I32 已生成当前角色卡 manifest：`price_volume_low_turnover_v1` 是唯一防守 / 选择性研究样本，质量线和低换手 sleeve 均为诊断样本。
   - I33 已补齐 CSI300 成分 / 权重 as-of 表，`index-asof-audit` 已可证明本地权重数据可用。
   - I34 已新增 `strategy-csi300-attribution` 只读归因命令，并对 I10 价量线持仓样本完成强沪深300跑输拆解：强指数阶段主要问题是仓位参与不足和高权重成分覆盖极低，不支持把该候选改造成强沪深300参与型策略。
   - I35 已把 `strategy-csi300-attribution` 套到 I15/I18/I20 三个强市场失败候选：I15 第 5 折平均仓位 `8.26%`、持有沪深300权重 `0.93%`；I20 第 5 折平均仓位 `13.55%`、持有沪深300权重 `1.68%`；I18 第 4 折空仓，第 5 折虽有 `27.09%` 平均仓位但持有沪深300权重只有 `3.54%`。结论是继续微调触发器或宽篮子参数的 ROI 低，下一步应预注册新的强市场有效参与假设。
   - I36 已预注册 `strong_market_effective_participation_v1`：新候选不再只问“是否触发强指数状态”，而要求强市场折平均 live exposure、held benchmark weight 和 top20 coverage 同时达到最低研究阈值；若下一轮实现后无法达到这些参与度阈值，应直接停止，不继续小参数调优。
   - I37 已实现 `strong_market_effective_participation_v1` 最小版本并完成 scoped admission 与持仓级归因；I38 前修正 `_scale_to_budget`，避免候选 cap 不足时把剩余额度补给最高权重个股并突破 `max_symbol_weight`，随后复跑产物。修正后 admission 仍为 `reject`，年化收益均值 `-3.47%`，Sharpe `-0.46`，最差回撤 `-17.11%`，最大年化换手 `14.01`；第 5 折强相关窗口平均实盘暴露仅 `10.29%`，持有沪深300权重 `2.13%`，top20 覆盖 `2.79%`。首版没有达成“有效参与”定义。
   - I38 已完成强市场候选池可达性诊断：第 5 折强市场日平均可买候选数约 `16.49`，但可买沪深300权重只有 `9.05%`，当前 panel 可见权重前20股票可买权重只有 `3.93%`；fold 2/3/4 没有强市场触发。结论是当前强市场参与路线同时受强市场 gate 稀少和核心权重可达性不足限制，下一步应重构候选生成层，而不是继续调组合权重参数。
   - I39 已完成强市场候选生成层重设计：下一步先做从 T-1 CSI300 core weights 出发的只读可达性诊断，验收强市场日可达沪深300权重是否达到 `50%`、完整基准 Top20 可达权重是否达到 `35%`；未达标前不实现新的交易策略。
   - I40 已实现并运行 `strategy-core-reachability-diagnostic`：完整基准核心权重只读诊断显示，五折 as-of 权重覆盖均为 `100%`，平均可达核心权重约 `53%` 到 `58%`，完整 Top20 可达约 `31%` 到 `34%`；不可达原因主要是少量核心成分不在当前 PIT panel，而不是价格、成交额、amount_ratio20 或行业字段失败。下一步应重写强市场过滤层，把 alpha 从硬过滤改成排序，不再先砍掉核心权重。
   - I41 已完成 CSI300 Top 权重缺口分析：Top20 缺口主要集中在少数 `missing_from_pit_panel` 成分，如 `SH.601328`、`SH.601816`、`SH.600900`、`SH.600919`、`SH.600030`。下一步应先做缺失核心成分审计，确认这些股票被排除的具体规则或数据原因，再决定是否调整 universe / PIT panel 构造。
   - I42 已完成缺失核心成分审计并新增 `strategy-missing-core-audit` 命令：Top30 缺失股票中，`beyond_walk_forward_limit` 占审计缺失权重约 `94.7%`，说明主因是当前 `walk_forward_limit = 120` 回测 panel 太窄，而不是全局数据库缺行。下一步应先做强市场专项 panel / universe 治理实验，暂缓直接实现新的强市场交易策略。
   - I43 已完成强市场 panel 上限实验：`walk_forward_limit=200/300` 明显改善核心权重可达性，平均可达核心权重最高到 `58.55%`。I44 随后确认，原 `Top20 >= 35%` 绝对权重门槛不合理，因为 Top20 自身权重会随年份变化；改用 Top20 覆盖率后，CSI300 core seed panel 五折均通过可达性诊断。下一步应预注册新的强市场核心参与候选，验证“能看见核心股”能否转化成“真实持仓能有效参与强市场”。
   - I45 已预注册 `strong_market_core_participation_v1`：它不是指数复制，也不是固定买沪深300前20只；它把 I44 的可达性结果转为下一策略候选的候选池和组合构造边界。若 I46 实现，必须验证强市场平均仓位、持有沪深300权重、Top20 持仓覆盖、换手、回撤和 admission。
   - I46 已实现 `strong_market_core_participation_v1` 并完成 scoped admission、failure attribution、market context、holdings exposure 和 CSI300 attribution。结论仍为 `reject`：年化收益均值 `-3.30%`，Sharpe `-0.43`，正收益折比例 `0%`，正超额折比例 `60%`，平均年化换手 `4.08`，最大年化换手 `16.04`，overfit risk `high`。本轮已修正核心逻辑：趋势、流动性、风险、行业约束不再作为沪深300核心股硬筛选器，而是作为排序、降权和审计依据。失败主因从“核心股不可达”推进为“强行情参与触发太窄、全折平均仓位和沪深300权重覆盖不足”。
   - I47 已实现 `strong_market_stable_core_base_v1` 并完成 scoped admission、failure attribution、market context、holdings exposure 和 CSI300 attribution。结论仍为 `reject`：年化收益均值 `-1.74%`，Sharpe `-0.34`，正收益折比例 `40%`，正超额折比例 `40%`，平均年化换手 `0.68`，最大年化换手 `1.85`，overfit risk `high`。本轮证明稳定核心底仓能显著改善参与度和换手，但仍跑不赢强沪深300环境，且行业偏离更明显。
   - I48 已实现 `strong_market_stable_core_only_v1` 和 `strong_market_stable_satellite_only_v1` 两个 attribution-only 归因变体，并复核 `strong_market_stable_core_base_v1`。短窗口 `baseline_2y_1y_5fold` 下三者均为 `reject`；长窗口下 `core-only` 与 `core+satellite` 仅为 `research_only`，`satellite-only` 为 `reject`。结论是短窗口只适合横向比较，不能单独支撑稳定性判断；I47 的主要有效部分是稳定核心底仓，卫星增强不应继续小参数调优。`core+satellite` 不是新策略 id，而是 I47 base 在拆分实验中的对照标签。

### P1：有前置条件后再处理

1. **质量因子组合构造重写**

   - 前置条件：T2.9 失败归因能明确收益、参数、行业或数据缺口。
   - 目标：降低行业集中，降低换手，增强 fold 稳定性。

2. **主题/行业轮动数据层补齐**

   - 前置条件：有 point-in-time 行业、主题或板块轮动数据。
   - 目标：解释 `theme_exposure_momentum_v1` 与质量策略在不同市场风格下的表现断裂。

3. **文本事件与 PEAD 沙盒**

   - 前置条件：T2.11 文本事件数据层具备 as-of 时间线、覆盖率和去重规则。
   - 目标：仅作为过滤、解释或候选假设，不直接进入主 ranker。

### P2：延后研究

1. **SVM / 轻量 ML-AC**

   - 延后原因：当前不是缺少模型复杂度，而是策略暴露、换手、参数稳定性和 regime 覆盖不足。
   - 重启条件：已有稳定因子注册表、足够样本、严格 OOS 评估和模型过拟合审计。

2. **网络因子**

   - 延后原因：需要股票网络、行业/主题共振矩阵和较高计算/解释成本。
   - 重启条件：T2.13 因子本体和行业/主题 as-of 数据层可用。

3. **融资融券 / LSTM 双边策略**

   - 延后原因：当前项目仍是普通 A 股单边研究框架，融资融券执行、保证金和做空约束未工程化。
   - 重启条件：账户与执行仿真层支持融资融券约束，且产品边界重新确认。

## T2.1.5 开发任务清单

### 已完成

- [x] 将策略层拆为 `phase0/strategies/` 注册表结构。
- [x] 建立 `baseline_admission_all_v1` 作为全局 admission 策略集合。
- [x] 完成 `low_vol_low_turnover_quality_v1` 和 `quality_low_turnover_monthly_v1` 的初始研发与 admission 复核。
- [x] 完成 `sleeve_composite_v1` 规则型组合 V1，并明确为 research-only。
- [x] 完成 `sleeve_composite_v1` scoped admission，结论为 `reject`。
- [x] 完成行业集中度 100% universe 专项实验，结论为 research-only，主线不放宽策略层行业审计。
- [x] 建立策略失败归因诊断模块 V1，用于解释 reject / retest / research-only。
- [x] 建立 I10 日度持仓暴露诊断，用于解释强沪深300环境下的低参与度问题。
- [x] 完成 I11 最低暴露覆盖反事实，结论为简单加仓覆盖会恶化表现，不落成默认规则。
- [x] 建立 I12 策略池角色表与策略选择方法论，明确当前无 admitted core candidate。
- [x] 建立 I13 强沪深300行情参与型候选 research brief，明确数据能力、不可声称项和进入编码前的验收边界。
- [x] 建立 I14 `strong_index_participation_v1` 窄口径候选设计 spec，冻结首版强行情定义、信号族、构造约束和停止条件。
- [x] 实现 I15 `strong_index_participation_v1` research-only 首版策略并完成 scoped admission，结论为 `reject`。
- [x] 完成 I16 `strong_index_participation_v1` 空仓 / 过滤漏斗失败归因，确认主要断点是强指数状态稀疏与固定调仓错过窗口。
- [x] 完成 I17 强指数参与下一假设设计，预注册 `strong_index_participation_dynamic_trigger_v1` 只改变调仓检查时机，不改变强指数阈值、选股过滤、PIT、`qfq_asof` 或 admission gate。
- [x] 实现并验证 I18 `strong_index_participation_dynamic_trigger_v1`，确认动态触发提高参与度但仍未通过 admission，且引入最大换手超标。
- [x] 完成 I19 新强市场参与型假设设计，选定 `strong_market_liquid_breadth_participation_v1` 作为 I20 方向，并明确不使用 CSI300 成分复制、主动权重归因或无 as-of 支撑的行业轮动叙事。
- [x] 实现并验证 I20 `strong_market_liquid_breadth_participation_v1`，确认宽篮子和慢换手能降低执行压力，但不能解决强市场收益质量、正收益折比例和行业审计问题。
- [x] 完成 I21 策略池优先级复盘，明确短期不继续调 I20 参数；下一步应先统一候选状态、沉淀 `price_volume_low_turnover_v1` 角色规则，并把强市场线转为 CSI300 成分/权重 as-of 等数据层任务。
- [x] 完成 I22 全候选治理刷新，建立 17 行候选治理表，覆盖 `baseline_admission_all_v1` 12 个候选、`price_volume_low_turnover_v1`、I15/I18/I20 三个强市场失败样本和 I11 最低仓位覆盖反事实。
- [x] 为 `price_volume_low_turnover_v1` 生成角色治理报告，明确它只能作为防守 / 选择性 research-only 候选，不能强行填补强沪深300参与型角色。
- [x] 设计 CSI300 成分/权重 as-of 数据层 spike，给出来源、字段、as-of 时间、覆盖率、缺失处理和禁止未来函数验收标准。
- [x] 明确每个候选的治理状态、允许用途、禁止用途、主失败原因和证据路径。
- [x] 将强沪深300参与型策略的局部触发器 / `top_n` / 换手参数调优列为暂停动作；下一步优先补 CSI300 成分/权重、行业/主题 as-of、审计后的市场宽度数据。
- [x] 完成 I23 CSI300 as-of 数据能力审计，新增 `index-asof-audit` 命令和测试，确认本地指数行情可用但成分 / 权重 as-of 表缺失。
- [x] 完成 I24 低换手质量线失败图谱，确认行业集中不是剩余主因，baseline 折稳定性才是核心问题。
- [x] 完成 I25 质量线 vs 价量线同折归因，新增 `strategy-fold-attribution` 只读汇总命令，确认当前质量线不宜继续小参数微调。
- [x] 完成 I26 `sleeve_composite_v1` 换手 / churn 诊断，确认原策略每日全量重排导致低持仓保留和年化高换手，不应继续微调原权重。
- [x] 完成 I27 `sleeve_composite_low_churn_v1` research-only 候选和 scoped admission，确认低 churn 修复有效但仍未通过准入。
- [x] 完成 I28 `sleeve_composite_low_churn_v1` 旧折亏损归因，确认旧折失败不是单一持仓、单一行业或市场压力可充分解释。
- [x] 完成 I29 `price_volume_low_turnover_v1` 防守 / 选择性角色规则，明确研究适配、降权、停用和禁止用途。
- [x] 完成 I30 `strategy-role-card` 生成器首版，并对 `price_volume_low_turnover_v1` 生成角色卡。
- [x] 完成 I31 角色卡批量验证，对质量线和低换手 sleeve 生成角色卡，并收紧弱市角色标签。
- [x] 完成 I32 角色卡 manifest，汇总三条已生成卡片候选的当前角色状态。
- [x] 完成 I33 CSI300 成分 / 权重 as-of 数据接入：新增 `backfill-index-asof`，写入 `cn_index_constituents_asof` / `cn_index_weights_asof` 各 `60900` 行，`index-asof-audit` 已从缺表变为 `available`。
- [x] 完成 I34 强沪深300跑输权重归因：新增 `strategy-csi300-attribution`，用 `cn_index_weights_asof` 最近已知权重拆解低参与度、权重股遗漏和行业偏离。
- [x] 完成 I35 强市场候选真实持仓级 CSI300 归因：对 I15/I18/I20 补齐 failure attribution、market context、holdings exposure 和 CSI300 attribution，确认三条候选仍是低参与度 / 低权重覆盖失败样本。
- [x] 完成 I36 `strong_market_effective_participation_v1` 预注册设计，明确强市场候选必须显式验证最低有效参与度和沪深300权重覆盖。
- [x] 完成 I37 `strong_market_effective_participation_v1` 最小实现、scoped admission、持仓暴露和 CSI300 归因，确认首版未达成有效参与定义且 admission 为 `reject`。
- [x] 完成 I38 强市场候选池可达性诊断，确认第 5 折强市场日可买候选覆盖沪深300核心权重不足，强市场参与型路线下一步应重构候选生成层。
- [x] 完成 I39 强市场候选生成层重设计，明确下一轮先做 CSI300 core reachability 只读诊断，不直接实现新交易策略。
- [x] 完成 I40 `strategy-core-reachability-diagnostic` 只读诊断，确认本地 PIT 数据能覆盖大部分 CSI300 核心权重，I37 的主要问题是过滤层过窄。
- [x] 完成 I41 CSI300 Top 权重缺口分析，确认完整 Top20 可达权重未达标主要来自少数核心成分缺失于当前 PIT panel。
- [x] 完成 I42 缺失核心成分审计，确认主要缺口来自 `walk_forward_limit = 120` 截断，而不是本地历史库整体缺行。
- [x] 完成 I43 强市场 panel 上限实验，确认扩大到 `200` / `300` 能减少截断并改善核心权重可达性，但仍不能让完整 Top20 可达权重稳定超过 `35%`。
- [x] 完成 I44 `csi300_core_seed_panel` 只读实验，修正 Top20 绝对权重门槛为覆盖率门槛，并确认显式保留 as-of 可见核心成分后五折可达性均为 `pass`。
- [x] 完成 I45 `strong_market_core_participation_v1` 预注册设计，明确新候选不复制沪深300、不固定买前20只，下一步必须用 admission 和持仓级 CSI300 归因验证真实参与度。
- [x] 完成 I47 `strong_market_stable_core_base_v1` 最小实现和 scoped admission，确认稳定核心底仓显著降低换手并提高沪深300核心覆盖，但首版仍未通过 admission。
- [x] 完成 I48 稳定核心底仓拆分归因：新增 `strong_market_stable_core_only_v1` 和 `strong_market_stable_satellite_only_v1` 作为 attribution-only 诊断变体，并用短窗口横向比较、长窗口稳定性复核确认卫星增强没有稳定贡献；这些变体不进入正式候选策略池。
- [x] 立项 T2.14 盘中行情信号择时买卖专项探索计划，明确它不是当前候选策略，而是后续分钟级数据、执行模型和盘中信号验证框架的探索入口。

### 下一步

- [x] 设计并实现受控的 CSI300 历史成分 / 权重接入任务，要求每条记录有 `asof_time` 或 `effective_date`，并用 `index-asof-audit` 作为验收门禁。
- [x] 基于 `cn_index_constituents_asof` / `cn_index_weights_asof` 设计并实现下一轮强沪深300跑输归因：区分低参与度、行业错配、权重股遗漏和个股选择失败。
- [x] 将 `strategy-csi300-attribution` 套到 I15/I18/I20 三个强市场失败样本的日度持仓上，复核强市场参与型候选到底是空仓、低覆盖、行业偏离还是选股失败。
- [x] 预注册新的强市场有效参与候选：不再只调触发器，而是显式约束最低有效参与度、指数权重覆盖或流动性权重覆盖，并继续保留 PIT / `qfq_asof` / 成本后 admission。
- [x] 实现 `strong_market_effective_participation_v1` 最小版本，跑 scoped admission，并立即用 holdings exposure + CSI300 attribution 验证强市场折参与度是否达标。
- [x] 做强市场候选池可达性诊断：按日统计强指数状态下有多少沪深300成分股同时满足 PIT、流动性、趋势、行业和权重可见性约束，先判断低参与度来自候选池不足还是组合构造器不足。
- [x] 重新设计强市场参与型候选生成层：先保证 CSI300 核心权重可达性，再叠加主动 alpha 过滤，避免把指数参与角色做成过窄主动选股器。
- [x] 实现 `strategy-core-reachability-diagnostic` 只读诊断命令，从 T-1 CSI300 core weights 出发检查 PIT、流动性、行业和基础风险过滤后的核心权重可达性。
- [x] 实现缺失核心成分审计：针对 I41 中高权重缺失股票，逐只追踪其是否被 universe 规则、历史数据、估值字段、上市状态或代码映射排除。
- [x] 设计并运行 I43 强市场专项 panel / universe 治理实验：保留常规 `walk_forward_limit = 120` 对照，新增 research-only `200` / `300` 扩 panel 方案，验证完整 Top20 可达权重能否稳定超过 `35%`。
- [x] 设计并运行 I44 `csi300_core_seed_panel` 只读实验：在常规 PIT universe 外显式保留 as-of 可见的沪深300 Top 权重核心成分，基础过滤只剔除不可交易 / 数据不可用标的；结果证明核心覆盖率和 Top20 覆盖率达标。
- [x] 预注册 I45 `strong_market_core_participation_v1`：基于 I44 的 core seed panel 思路设计新的强市场参与候选，不复制沪深300、不固定买前20只，并保留 PIT、`qfq_asof`、成本、行业约束、持仓暴露和 admission 验证。
- [x] 实现 I46 `strong_market_core_participation_v1` 最小版本，跑 scoped admission，并立即用 holdings exposure + CSI300 attribution + failure attribution 验证强市场折真实参与度是否达标；结论为 `reject`，主因是强行情参与持续性不足。
- [x] 预注册并实现 I47 强市场稳定核心底仓候选：把“最低有效参与仓位”与“主动 alpha 卫星”分层，先验证强市时能否稳定保持核心底仓，再评估选股增强，不继续微调 I46 小参数。
- [x] I49 做稳定核心底仓相对沪深300跑输归因：确认主要问题是强基准阶段参与度和核心权重贴近度不足，并伴随行业主动偏离；不继续围绕卫星增强做小参数调优。
- [x] I50 预注册 `strong_market_benchmark_aware_core_v1`：把强基准阶段 live exposure、持有沪深300权重、Top20 覆盖、Top20 漏配和行业 L1 偏离写成下一候选的显式验收指标。
- [ ] I51 最小实现 `strong_market_benchmark_aware_core_v1`，并运行 scoped admission、holdings exposure、CSI300 attribution、failure attribution 和长窗口稳定性检查。
- [ ] 等数据源治理优先级允许后，按 T2.14 先做分钟级行情数据源可用性 spike，而不是直接实现盘中策略。
- [x] 启动 `sleeve_composite_v1` 降换手、降 churn、降行业集中修复，已完成诊断，结论是不直接修原权重。
- [ ] 对 `quality_low_turnover_monthly_v1` 做最后一折 regime 依赖复核，避免用单折转好解释长期有效。
- [x] 新建 `sleeve_composite_low_churn_v1` research-only 候选，先降低 turnover / churn / industry concentration，再做二次 scoped admission。
- [x] 对 `sleeve_composite_low_churn_v1` 做旧折亏损归因，确认第 1、2 折失败不能靠单一股票、单一行业或市场压力充分解释，避免用最近强折继续过拟合。
- [x] 回到 `price_volume_low_turnover_v1` 防守 / 选择性角色治理，定义研究适配、降权、停用和复盘条件。
- [x] 抽象可复用策略角色卡模板或生成器，统一输出候选的市场环境、相对基准、失败模式、允许用途和禁止用途。
- [x] 将 `strategy-role-card` 应用于质量线和 sleeve 线，检查生成卡片是否足够清楚。
- [x] 生成策略角色卡 manifest，总结当前所有生成卡片的角色、禁止用途和下一步。
- [ ] 或先把 `price_volume_low_turnover_v1` 纳入当前全量 admission 刷新，再用新结果更新角色卡。
- [ ] 将 T2.13 因子域、影响通道和外部市场环境字段接入失败归因报告设计，不进入主策略权重。

## T2.1.6 不做清单

- [x] 不把旧 `qfq_current` selected candidate 解释为当前可用策略。
- [x] 不因为 admission 过严就降低门槛。
- [x] 不用单次 compare 相对最优替代 admission。
- [x] 不把 `sleeve_composite_v1` scoped admission 的相对表现解释为正式候选。
- [x] 不继续堆叠高换手价格行为策略参数。
- [x] 不在没有 as-of 数据和覆盖率诊断前启动文本、主题、政策或新闻因子回测。
- [x] 不把 LLM / 知识图谱输出直接转成交易信号。
- [x] 不把 `price_volume_low_turnover_v1` 简单提高最低仓位后解释为强沪深300参与策略。
- [x] 不把缺少 CSI300 成分/权重表的诊断解释成“已证明低配沪深300成分股”；I33 以后如使用 `cn_index_weights_asof`，必须同时说明权重可见性口径和 research-only 边界。

## T2.1.7 简短结论

T2.1 当前不是“挑一个马上上线的策略”，而是“把策略池治理成可复查的研究资产，并形成策略选择方法论”。

短期唯一合理主线是：

1. 用 `baseline_admission_all_v1` 统一治理 12 个候选。
2. 优先修正低波、低换手、质量策略的失败原因。
3. 把 `sleeve_composite_v1` 和 `sleeve_composite_low_churn_v1` 保持为 research-only；低 churn 构造可复用，但当前 sleeve alpha 不再继续小参数调优。
4. 把 `price_volume_low_turnover_v1` 作为防守 / 选择性研究候选观察，不强行改成强指数参与策略。
5. 单独补强“强沪深300行情参与型”策略角色；当前 I15/I18/I20、I37 `strong_market_effective_participation_v1`、I46 `strong_market_core_participation_v1` 和 I47 `strong_market_stable_core_base_v1` 均为 `reject`。I44 已证明如果显式保留沪深300核心成分，候选池可达性可以过关；I46 证明仅补核心候选池还不够；I47 证明稳定核心底仓可以改善参与度和换手；I48 进一步证明主要贡献来自核心底仓，卫星增强没有稳定贡献；I49 确认剩余问题是核心权重贴近度和行业偏离；I50 已预注册 benchmark-aware 强市场核心候选。下一步若实现 I51，应先验证它是否真正提高强基准阶段实盘仓位、沪深300权重覆盖和 Top20 覆盖，而不是继续调卫星增强参数。
6. 用 T2.13 的因子传导框架增强归因和报告解释，而不是绕过 admission 生成新信号。
