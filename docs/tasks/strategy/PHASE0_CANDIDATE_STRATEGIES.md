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
- 当前重点研发集合：低波、低换手、质量主线与 `sleeve_composite_v1` 降换手重构
- 当前禁止动作：不凭 compare 排名、旧 `qfq_current` 结果或单次 scoped admission 相对最优结论进入模拟账户或日报

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
| `low_vol_low_turnover_quality_v1` | 当前 active research 主线 | 优先失败归因、组合构造修正和行业集中复核 | 通过全量 admission，且核心失败项明显改善 |
| `quality_low_turnover_monthly_v1` | 低频质量对照候选 | 优先复核最后一折 regime 依赖、参数稳定性和行业集中 | 通过双 preset admission，且不是单折驱动 |
| `multifactor_volume_price_filter_v1` | 多因子量价失败样本 | 保留为诊断，不继续堆叠参数 | 需先证明低换手和因子域覆盖改善 |
| `core_selection_quality_momentum_v1` | 质量 + 动量复合候选 | 保留为组合构造对照 | 需证明复合后降低而非放大 churn |
| `theme_exposure_momentum_v1` | 主题暴露候选 / 失败样本 | 保留研究，不作为主 ranker | 需先补齐主题/行业轮动 as-of 数据 |
| `sleeve_composite_v1` | research-only 组合诊断候选 | 优先降换手、降 churn、降行业集中，再 scoped admission | 当前 scoped admission 为 `reject`；二次研发后仍需全量 admission |

## T2.1.3 当前优先级

### P0：当前必须优先处理

1. **全候选 admission 治理报告补齐**

   - 覆盖 `baseline_admission_all_v1` 的 12 个候选。
   - 报告必须标注运行日期、数据口径、preset、策略集合、是否 scoped、是否 research-only。
   - 报告必须输出 action：`reject`、`retest`、`research_only` 或 `admission_pass_candidate`。

2. **低波低换手质量主线失败归因**

   - 重点策略：`low_vol_low_turnover_quality_v1`、`quality_low_turnover_monthly_v1`。
   - 优先解释质量暴露为何没有稳定转化为收益。
   - 重点复核正收益折比例、参数漂移、最后一折 regime 依赖、行业集中和换手。

3. **`sleeve_composite_v1` 降换手重构**

   - 当前 scoped admission 为 `reject`，不能进入正式链路。
   - 下一轮不直接调收益权重，先处理持仓保留、risk overlay churn、行业集中和 turnover。
   - 二次研发后必须重新 scoped admission，再决定是否进入全量 admission。

4. **T2.13 因子域元数据接入策略诊断**

   - 把六域因子传导框架先用于失败归因和 admission 报告解释。
   - 不把因子域矩阵直接转成策略权重。
   - 用于区分策略失效、因子域缺失、市场环境未覆盖和外部事件未建模。

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

## T2.1.4 开发任务清单

### 已完成

- [x] 将策略层拆为 `phase0/strategies/` 注册表结构。
- [x] 建立 `baseline_admission_all_v1` 作为全局 admission 策略集合。
- [x] 完成 `low_vol_low_turnover_quality_v1` 和 `quality_low_turnover_monthly_v1` 的初始研发与 admission 复核。
- [x] 完成 `sleeve_composite_v1` 规则型组合 V1，并明确为 research-only。
- [x] 完成 `sleeve_composite_v1` scoped admission，结论为 `reject`。
- [x] 完成行业集中度 100% universe 专项实验，结论为 research-only，主线不放宽策略层行业审计。
- [x] 建立策略失败归因诊断模块 V1，用于解释 reject / retest / research-only。

### 下一步

- [ ] 重跑 main 全候选 admission，覆盖 `baseline_admission_all_v1` 12 个候选并纳入 `sleeve_composite_v1`。
- [ ] 为全候选 admission 生成策略池治理报告，输出策略状态、主要失败原因、研究边界和下一步动作。
- [ ] 对 `low_vol_low_turnover_quality_v1` 做 paired compare / admission，重点验证行业集中、质量暴露和参数稳定性修正是否有效。
- [ ] 对 `quality_low_turnover_monthly_v1` 做最后一折 regime 依赖复核，避免用单折转好解释长期有效。
- [ ] 对 `sleeve_composite_v1` 设计降换手方案，先降低 turnover / churn / industry concentration，再做二次 scoped admission。
- [ ] 将 T2.13 因子域、影响通道和外部市场环境字段接入失败归因报告设计，不进入主策略权重。
- [ ] 明确每个候选的状态枚举：`active_research`、`baseline`、`failure_sample`、`research_only`、`deferred`、`admission_pass_candidate`。

## T2.1.5 不做清单

- [x] 不把旧 `qfq_current` selected candidate 解释为当前可用策略。
- [x] 不因为 admission 过严就降低门槛。
- [x] 不用单次 compare 相对最优替代 admission。
- [x] 不把 `sleeve_composite_v1` scoped admission 的相对表现解释为正式候选。
- [x] 不继续堆叠高换手价格行为策略参数。
- [x] 不在没有 as-of 数据和覆盖率诊断前启动文本、主题、政策或新闻因子回测。
- [x] 不把 LLM / 知识图谱输出直接转成交易信号。

## T2.1.6 简短结论

T2.1 当前不是“挑一个马上上线的策略”，而是“把策略池治理成可复查的研究资产”。

短期唯一合理主线是：

1. 用 `baseline_admission_all_v1` 统一治理 12 个候选。
2. 优先修正低波、低换手、质量策略的失败原因。
3. 把 `sleeve_composite_v1` 保持为 research-only，先降换手和行业集中。
4. 用 T2.13 的因子传导框架增强归因和报告解释，而不是绕过 admission 生成新信号。
