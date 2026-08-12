# 历史项目拆解任务清单

> 本目录于 2026-08-12 归档。它记录当时的任务拆分、执行附件和专项工作，不再维护，也不能据此判断当前待办或完成状态。
> 当前总体计划：[`DEVELOPMENT_PLAN.md`](../../DEVELOPMENT_PLAN.md)；当前工程规则：[`docs/README.md`](../../README.md)。

## T0.1 任务目录结构

| 层级编号 | 目录 / 文件 | 作用 |
| --- | --- | --- |
| `T0` | [`WEEKLY_EXECUTION_CHECKLIST.md`](./WEEKLY_EXECUTION_CHECKLIST.md) | 周任务执行总清单，承接总体计划的近期执行节奏 |
| `T1` | [`data-sources/`](./data-sources/) | 数据源升级任务：FRED、Tiingo、新闻源等 |
| `T2` | [`strategy/`](./strategy/) | 策略候选、策略积木工程化计划、过拟合诊断和有效策略研发任务 |
| `T3` | [`cross-market/`](./cross-market/) | 跨市场映射与港股/A 股候选任务 |
| `T4` | [`account/`](./account/) | 账户级仿真、真实账户对账和交易计划辅助相关任务 |
| `T5` | [`research/`](./research/) | 论文、策略摘要和研究支持资料 |
| `T6` | [`ops/`](./ops/) | 统一调度器、后台 pipeline、数据治理编排、任务重试和运行状态管理 |

## T0.2 当前项目基线

| 层级编号 | 基线项 | 当前状态 |
| --- | --- | --- |
| `B1` | 兼容基线 | 旧 `qfq_current` 研究样本：`legacy_momentum_low_turnover_v1` |
| `B2` | Phase 0 gate | 严格 `qfq_asof` 口径未通过；当前仅确认工程链路可用 |
| `B3` | 主线定位 | A 股本土因子为主，跨市场信号只做风险/情绪 overlay |
| `B4` | 产品边界 | 个人自用量化研究、盘前研判与交易计划辅助，不自动下单 |
| `B5` | 下一主线 | T5.2 RAG-ready 情报基础与策略池 admission 治理并行：先让研究情报可持续检索、复核和转任务，再用严格 `qfq_asof` admission 重建合格候选 |

## T0.3 子任务索引

| 层级编号 | 子任务 | 文档 |
| --- | --- | --- |
| `T1.1` | FRED 宏观 / 利率 / VIX 数据源 | [`data-sources/FRED_IMPLEMENTATION_TASKS.md`](./data-sources/FRED_IMPLEMENTATION_TASKS.md) |
| `T1.2` | Tiingo 美股个股 / ETF 主源 | [`data-sources/TIINGO_IMPLEMENTATION_TASKS.md`](./data-sources/TIINGO_IMPLEMENTATION_TASKS.md) |
| `T1.3` | 新闻源独立模块 | [`data-sources/NEWS_SOURCE_IMPLEMENTATION_TASKS.md`](./data-sources/NEWS_SOURCE_IMPLEMENTATION_TASKS.md) |
| `T1.4` | A 股历史 as-of 前复权与复权因子治理 | [`data-sources/ASOF_PRICE_ADJUSTMENT_GOVERNANCE_TASKS.md`](./data-sources/ASOF_PRICE_ADJUSTMENT_GOVERNANCE_TASKS.md) |
| `T1.6` | `a_share_history.sqlite` 主库定义与 README 重整 | [`data-sources/MANUAL_HISTORY_README_REALIGNMENT_TASKS.md`](./data-sources/MANUAL_HISTORY_README_REALIGNMENT_TASKS.md) |
| `T1.7` | AI 语料库（政策法规 / CCTV / 公告 / 央行报告 / 研报元数据） | [`data-sources/AI_CORPUS_IMPLEMENTATION_TASKS.md`](./data-sources/AI_CORPUS_IMPLEMENTATION_TASKS.md) |
| `T2.1` | Phase 0 候选策略池 | [`strategy/PHASE0_CANDIDATE_STRATEGIES.md`](./strategy/PHASE0_CANDIDATE_STRATEGIES.md) |
| `T2.3` | 策略积木工程化计划 | [`strategy/STRATEGY_BLOCKS_PLAN.md`](./strategy/STRATEGY_BLOCKS_PLAN.md) |
| `T2.4` | 策略过拟合诊断工具 | [`strategy/STRATEGY_OVERFITTING_DIAGNOSTIC_TOOL.md`](./strategy/STRATEGY_OVERFITTING_DIAGNOSTIC_TOOL.md) |
| `T2.5-T2.11` | 有效量化策略研发任务清单 | [`strategy/EFFECTIVE_QUANT_STRATEGY_RESEARCH_TASKS.md`](./strategy/EFFECTIVE_QUANT_STRATEGY_RESEARCH_TASKS.md) |
| `T2.14` | 盘中行情信号择时买卖专项探索 | [`strategy/INTRADAY_SIGNAL_TIMING_EXPLORATION.md`](./strategy/INTRADAY_SIGNAL_TIMING_EXPLORATION.md) |
| `T3.1` | 港股映射 A 股候选策略 | [`cross-market/HK_A_SHARE_MAPPING_STRATEGIES.md`](./cross-market/HK_A_SHARE_MAPPING_STRATEGIES.md) |
| `T4.1` | 真实账户对账 CSV 预留格式 | [`account/ACCOUNT_RECONCILIATION_CSV_SCHEMA.md`](./account/ACCOUNT_RECONCILIATION_CSV_SCHEMA.md) |
| `T5.1` | 中文 A 股量化策略论文提炼 | [`research/STRATEGY_SUMMARY.md`](./research/STRATEGY_SUMMARY.md) |
| `T5.2` | 投资策略情报搜集、评估、维护、提炼与解读模块 | [`任务定义`](./research/STRATEGY_INTELLIGENCE_WORKFLOW_TASKS.md) / [`工作流说明`](./research/STRATEGY_INTELLIGENCE_WORKFLOW.md) |
| `T6.1` | 统一调度器与后台 Pipeline | [`ops/SCHEDULER_PIPELINE_TASKS.md`](./ops/SCHEDULER_PIPELINE_TASKS.md) |
| `T6.2` | 数据库健康检查与数据质量门禁 | [`WEEKLY_EXECUTION_CHECKLIST.md`](./WEEKLY_EXECUTION_CHECKLIST.md#W217数据库健康检查与数据质量门禁t62) |
| `T6.3` | 数据治理与维护编排器 | [`ops/DATA_GOVERNANCE_ORCHESTRATOR_TASKS.md`](./ops/DATA_GOVERNANCE_ORCHESTRATOR_TASKS.md) |
| `T6.4` | Report Dashboard Astro 静态报表门户 | [`ops/REPORT_DASHBOARD_ASTRO_TASKS.md`](./ops/REPORT_DASHBOARD_ASTRO_TASKS.md) |
| `T6.5` | Report Output Path Standardization | [`../superpowers/plans/2026-06-23-report-output-path-standardization.md`](../superpowers/plans/2026-06-23-report-output-path-standardization.md) |
| `T6.6` | Daily Brief 独立内容模型与页面设计 | [`ops/DAILY_BRIEF_CONTENT_MODEL_TASKS.md`](./ops/DAILY_BRIEF_CONTENT_MODEL_TASKS.md) |
| `T6.7` | 多模拟账户静态控制台 | [`ops/MULTI_ACCOUNT_STATIC_CONSOLE_TASKS.md`](./ops/MULTI_ACCOUNT_STATIC_CONSOLE_TASKS.md) |

## T0.4 维护规则

- 新增任务必须先判断是否属于父级总体计划当前主线。
- 所有任务项使用稳定层级编号，例如 `T1.1.2`、`T2.3.4`。
- 父级总体计划只写阶段、优先级和引用，不堆叠完整任务细节。
- 周任务清单只记录近期执行节奏，专项细节放入对应子任务文档。
