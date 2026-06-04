# 项目拆解任务清单

> 父级总体计划：[`DEVELOPMENT_PLAN.md`](../DEVELOPMENT_PLAN.md)  
> 本目录只管理拆分后的任务清单、执行附件、专项任务单和研究支持清单。项目定位、阶段边界和优先级以父级总体计划为准。

## T0.1 任务目录结构

| 层级编号 | 目录 / 文件 | 作用 |
| --- | --- | --- |
| `T0` | [`WEEKLY_EXECUTION_CHECKLIST.md`](./WEEKLY_EXECUTION_CHECKLIST.md) | 周任务执行总清单，承接总体计划的近期执行节奏 |
| `T1` | [`data-sources/`](./data-sources/) | 数据源升级任务：FRED、Tiingo、新闻源等 |
| `T2` | [`strategy/`](./strategy/) | 策略候选、策略开发检查清单、策略积木工程化计划 |
| `T3` | [`cross-market/`](./cross-market/) | 跨市场映射与港股/A 股候选任务 |
| `T4` | [`account/`](./account/) | 账户级仿真、真实账户对账和交易计划辅助相关任务 |
| `T5` | [`research/`](./research/) | 论文、策略摘要和研究支持资料 |
| `T6` | [`ops/`](./ops/) | 统一调度器、后台 pipeline、任务重试和运行状态管理 |

## T0.2 当前项目基线

| 层级编号 | 基线项 | 当前状态 |
| --- | --- | --- |
| `B1` | 主策略基线 | `legacy_momentum_low_turnover_v1` |
| `B2` | Phase 0 gate | `PASS` |
| `B3` | 主线定位 | A 股本土因子为主，跨市场信号只做风险/情绪 overlay |
| `B4` | 产品边界 | 个人自用量化研究、盘前研判与交易计划辅助，不自动下单 |
| `B5` | 下一主线 | `Signal & Rebalance Engine`：可交易信号、调仓建议单、模拟订单、阻断原因 |

## T0.3 子任务索引

| 层级编号 | 子任务 | 文档 |
| --- | --- | --- |
| `T1.1` | FRED 宏观 / 利率 / VIX 数据源 | [`data-sources/FRED_IMPLEMENTATION_TASKS.md`](./data-sources/FRED_IMPLEMENTATION_TASKS.md) |
| `T1.2` | Tiingo 美股个股 / ETF 主源 | [`data-sources/TIINGO_IMPLEMENTATION_TASKS.md`](./data-sources/TIINGO_IMPLEMENTATION_TASKS.md) |
| `T1.3` | 新闻源独立模块 | [`data-sources/NEWS_SOURCE_IMPLEMENTATION_TASKS.md`](./data-sources/NEWS_SOURCE_IMPLEMENTATION_TASKS.md) |
| `T1.4` | A 股历史 as-of 前复权与复权因子治理 | [`data-sources/ASOF_PRICE_ADJUSTMENT_GOVERNANCE_TASKS.md`](./data-sources/ASOF_PRICE_ADJUSTMENT_GOVERNANCE_TASKS.md) |
| `T2.1` | Phase 0 候选策略池 | [`strategy/PHASE0_CANDIDATE_STRATEGIES.md`](./strategy/PHASE0_CANDIDATE_STRATEGIES.md) |
| `T2.2` | 策略开发任务单模板 | [`strategy/STRATEGY_DEV_CHECKLIST.md`](./strategy/STRATEGY_DEV_CHECKLIST.md) |
| `T2.3` | 策略积木工程化计划 | [`strategy/STRATEGY_BLOCKS_PLAN.md`](./strategy/STRATEGY_BLOCKS_PLAN.md) |
| `T2.4` | 策略过拟合诊断工具 | [`strategy/STRATEGY_OVERFITTING_DIAGNOSTIC_TOOL.md`](./strategy/STRATEGY_OVERFITTING_DIAGNOSTIC_TOOL.md) |
| `T2.5-T2.10` | 有效量化策略研发任务清单 | [`strategy/EFFECTIVE_QUANT_STRATEGY_RESEARCH_TASKS.md`](./strategy/EFFECTIVE_QUANT_STRATEGY_RESEARCH_TASKS.md) |
| `T3.1` | 港股映射 A 股候选策略 | [`cross-market/HK_A_SHARE_MAPPING_STRATEGIES.md`](./cross-market/HK_A_SHARE_MAPPING_STRATEGIES.md) |
| `T4.1` | 真实账户对账 CSV 预留格式 | [`account/ACCOUNT_RECONCILIATION_CSV_SCHEMA.md`](./account/ACCOUNT_RECONCILIATION_CSV_SCHEMA.md) |
| `T5.1` | 中文 A 股量化策略论文提炼 | [`research/STRATEGY_SUMMARY.md`](./research/STRATEGY_SUMMARY.md) |
| `T6.1` | 统一调度器与后台 Pipeline | [`ops/SCHEDULER_PIPELINE_TASKS.md`](./ops/SCHEDULER_PIPELINE_TASKS.md) |

## T0.4 维护规则

- 新增任务必须先判断是否属于父级总体计划当前主线。
- 所有任务项使用稳定层级编号，例如 `T1.1.2`、`T2.3.4`。
- 父级总体计划只写阶段、优先级和引用，不堆叠完整任务细节。
- 周任务清单只记录近期执行节奏，专项细节放入对应子任务文档。
