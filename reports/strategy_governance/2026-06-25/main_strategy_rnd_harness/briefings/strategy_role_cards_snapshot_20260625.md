# 策略角色卡快照（2026-06-25）

## 口径

本快照用于把当前策略研发形成的策略角色、阶段性断言和后续动作说清楚，避免把实验对象误认为正式候选。

证据来源：

- 主配置：`config.yaml` 的 `baseline_admission_all_v1`
- 策略治理文档：`docs/tasks/strategy/PHASE0_CANDIDATE_STRATEGIES.md`
- 已落盘 admission / failure attribution / holdings exposure / CSI300 attribution 报告

当前总判断：

- 正式全局候选池仍是 `baseline_admission_all_v1` 的 12 个策略。
- 当前没有通过严格 admission 的 selected candidate。
- 后续新增策略分为“实验备选”和“归因拆分对象”；归因拆分对象不能进入策略池。
- 当前主线重点不是继续堆候选数量，而是补齐强沪深300/强市场环境下可用策略角色。

## 正式 12 个候选策略

| 策略 | 角色卡 | 阶段性断言 | 当前动作 |
| --- | --- | --- | --- |
| `legacy_momentum` | 历史动量 baseline / 失败样本 | 严格 `qfq_asof`、PIT、成本后口径下收益和 Sharpe 明显不合格，且换手过高。 | 只保留回归对照，不进入实盘链路。 |
| `legacy_momentum_low_turnover_v1` | 兼容 baseline / 动量 sleeve 输入 | 旧 `qfq_current` 结果只能作历史参考；严格 admission 未通过。 | 保留为兼容参考和失败对照。 |
| `ma_kline_baseline_v1` | 透明规则地板策略 | 简单均线/K线规则在当前严格口径下表现很弱。 | 用作“复杂策略是否真有增益”的下限对照。 |
| `residual_momentum_reversal_v1` | 高换手价格行为失败样本 | 价格反转/残差动量首版收益、Sharpe、换手均不合格。 | 降级归档，不做小参数调优。 |
| `residual_momentum_reversal_v2` | 高换手价格行为失败样本 | 二版没有解决收益质量和高换手问题。 | 降级归档，不做小参数调优。 |
| `quality_growth_price_v1` | 质量成长早期候选 | 质量成长信号尚未稳定转化为收益。 | 保留为质量因子诊断输入。 |
| `low_vol_low_turnover_quality_v1` | 质量/低波低换手诊断资产 | 最近折有改善，但质量 bucket 和长期折稳定性不足。 | 暂停参数微调，只作质量线诊断样本。 |
| `quality_low_turnover_monthly_v1` | 低频质量对照候选 | 低频和低换手有研究价值，但 admission 仍未通过。 | 保留为质量线对照，不输出信号。 |
| `multifactor_volume_price_filter_v1` | 多因子量价失败样本 | 因子堆叠没有证明稳定收益，且换手和成本压力较高。 | 保留为诊断，不继续堆参数。 |
| `core_selection_quality_momentum_v1` | 质量 + 动量复合候选 | 复合后未证明降低 churn 或提高稳定性。 | 保留为组合构造对照。 |
| `theme_exposure_momentum_v1` | 主题暴露候选 / regime 线索 | 缺少充分 as-of 主题/行业轮动数据支撑。 | 暂作研究线索，不作主 ranker。 |
| `sleeve_composite_v1` | 组合诊断候选 | 原构造日度重排、高换手、行业集中和收益质量均未过关。 | research-only；不再微调原权重。 |

## 后添加的实验备选策略

| 策略 | 角色卡 | 阶段性断言 | 当前动作 |
| --- | --- | --- | --- |
| `quality_low_turnover_regime_gate_v1` | 小市场状态过滤 / 质量线实验备选 | admission 为 `reject`；regime gate 未解决质量线长期稳定性，还带来换手和 overfit 风险。 | 停止作为当前主线。 |
| `sleeve_composite_low_churn_v1` | 低 churn 组合构造实验备选 | 低 churn 机制能降低换手并改善部分指标，但仍未通过 admission，overfit 风险仍高。 | 保留“降低 churn 有价值”的工程经验，不输出信号。 |
| `price_volume_low_turnover_v1` | 防守 / 选择性 research-only 候选 | 弱基准或风险压力环境下有研究价值；强沪深300环境下不适合承担参与角色。 | 可作为防守样本继续研究；未进入 paper review、模拟、日报或 watchlist。 |
| `strong_index_participation_v1` | 强沪深300参与型首版实验备选 | scoped admission 为 `reject`；主要问题是强指数阶段长期低参与或空仓。 | 保留失败样本，不继续小参数调优。 |
| `strong_index_participation_dynamic_trigger_v1` | 强指数动态触发实验备选 | 动态触发改善部分参与度，但带来高换手和不稳定。 | 保留 I18 对照，不继续微调触发器。 |
| `strong_market_liquid_breadth_participation_v1` | 强市场宽篮子参与实验备选 | 换手比前两版更好，但收益质量、正收益折比例和行业审计仍未达标。 | 保留 I20 对照，不作为当前候选。 |
| `strong_market_effective_participation_v1` | 强市场有效参与实验备选 | 未达到强市场折最低仓位、沪深300权重覆盖和 Top20 覆盖要求。 | 首版停止，研发转向核心权重可达性。 |
| `strong_market_core_participation_v1` | 强市场核心成分参与实验备选 | 核心候选池可达性改善，但实际参与持续性不足，换手仍高。 | 保留 I46 失败样本。 |
| `strong_market_stable_core_base_v1` | 强市场稳定核心底仓实验备选 | 稳定底仓显著提高参与度、降低换手，但收益、Sharpe、正收益折、行业偏离和 overfit 仍未过关。 | 继续做跑输沪深300归因；不进入正式链路。 |

## 只用于归因的拆分对象

| 对象 | 正确身份 | 阶段性断言 | 禁止动作 |
| --- | --- | --- | --- |
| `strong_market_stable_core_only_v1` | I48/I49 归因变体 | 用来判断 I47 改善是否主要来自稳定核心底仓。它不是新增候选策略。 | 不进入正式候选池、paper review、模拟、日报或 watchlist。 |
| `strong_market_stable_satellite_only_v1` | I48/I49 归因变体 | 用来判断卫星增强是否有稳定贡献；当前证据显示没有稳定贡献。 | 不进入正式候选池、paper review、模拟、日报或 watchlist。 |
| `core+satellite` | I48 拆分实验标签 | 只是 `strong_market_stable_core_base_v1` 在拆分实验里的对照名称，不是新策略 id。 | 不作为独立候选登记。 |

## 当前研发焦点

1. 策略池缺口仍在“强沪深300/强市场环境下的相对优势策略”。
2. `strong_market_stable_core_base_v1` 证明稳定核心底仓方向有价值，但还没有证明能跑赢强沪深300。
3. 下一步应解释稳定核心底仓为什么跑输沪深300：核心权重贴近度、行业主动偏离、Top20 权重漏配和强市场触发持续性。
4. 不应把 `core-only` / `satellite-only` 当作候选策略池扩容。
