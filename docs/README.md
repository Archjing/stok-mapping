# 文档索引

`docs/` 只保留当前维护所需的事实源、操作说明和策略说明。历史任务分解、一次性研发计划和过期评估已移至 [archive/](archive/)，不再作为当前项目状态的依据。

## 长期维护的主文档

| 文档 | 用途 | 更新时机 |
| --- | --- | --- |
| [PROJECT_ARCHITECTURE_OVERVIEW.md](PROJECT_ARCHITECTURE_OVERVIEW.md) | 系统边界、模块职责、数据流、运维与架构债务 | 模块、数据流或运行边界变化时 |
| [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) | 已完成能力、当前优先级、验收门槛和下一阶段 | 计划状态或研发优先级变化时 |
| [CODING_STYLE_RULES.md](CODING_STYLE_RULES.md) | Python、数据治理、策略、配置、测试和文档规范 | 形成稳定工程约束时 |
| [PHASE0_CLI_USER_GUIDE.md](PHASE0_CLI_USER_GUIDE.md) | 当前 CLI 的操作手册 | 命令、参数或运行行为变化时 |
| [STRATEGY_DEVELOPMENT_GUIDELINES.md](STRATEGY_DEVELOPMENT_GUIDELINES.md) | 策略研发、回测、admission 与模拟账户准则 | 策略治理规则变化时 |

## 策略说明与研究接口

- [策略说明索引](strategy_explanations/INDEX.md)：已注册策略的可读说明；其结果仍须以实际回测与 admission 产物为准。
- [数据资产说明](../data/README.md)：本地 SQLite、数据源、价格口径和审计边界。
- [参考资料索引](../refdocs/README.md)：论文、外部资料和历史会话上下文，不是当前工程事实源。

## 归档规则

- 不再维护的设计草案、任务清单和阶段性评估进入 `archive/`；Git 历史保留其可追溯性。
- 新的长期规则优先更新上表五份主文档，而不是新增平行的“总体计划”或“架构说明”。
- 新的短期研发拆解可放入 issue、PR 描述或临时计划；完成后将结论回写到架构或开发计划，并归档临时材料。
