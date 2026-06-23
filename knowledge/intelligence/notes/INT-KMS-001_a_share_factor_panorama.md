# 情报解读：A股个股行情影响因子全景图

## 元信息

- Intelligence ID: `INT-KMS-001`
- Source Type: `manual_note`
- Source Path or URL: `/home/zj/workspace/KMS/My_logseq/pages/A股个股行情影响因子全景图.md`
- Published At:
- Collected At: `2026-06-23`
- Market Scope: A 股个股 / 全市场
- Topic Tags: `multifactor;macro;industry;style;fund-flow;text-event`
- Strategy Tags: `factor-taxonomy;market-regime;data-source-mapping;text-event-layer`

## Abstract

这份 Logseq 页面把 A 股个股行情影响因子整理为“宏观制度、行业主题、公司价值、风格风险、资金交易、信息事件”六域模型。它同时给出了 Tushare 与外部数据源映射、覆盖缺口和自建指标方案，适合作为本项目补齐市场环境、板块轮动、资金流和文本事件层的蓝图。该材料不是已验证交易策略，而是策略研究与数据建设的分类框架。对当前质量低换手策略而言，它最适合用于解释弱样本外区间、规划外部因子诊断模块和识别数据缺口。

## 核心观点

- 个股行情不能只由财务质量、低波和低换手解释，还受到宏观制度、行业主题、风格风险、资金交易和信息事件共同影响。
- 外部市场、政策、行业轮动、资金流和新闻公告应先作为诊断和解释层，经过时点有效性和样本外验证后才可进入策略信号。
- Tushare 可以覆盖大量 A 股行情、财务、估值、公告、资金、概念、宏观和部分海外市场数据，但行业经营、政策强度、产业链位置、舆情热度和一致预期仍需要外部源或自建指标。
- 文档中的数据源映射可直接服务 `market_regime_data`、`market_regime_features`、`text_event_features` 和 strategy admission 诊断扩展。

## 对 stok-mapping 的启发

- 支撑当前“市场环境与外部信息研究模块”计划，将质量低换手策略的失败归因从单纯收益指标扩展到风格、板块、资金和事件维度。
- 为 `T1.3` 新闻源与文本事件层提供事件类型边界，包括公告、研报、重大新闻、政策、产业主题和风险事件。
- 为 `T2.5` 因子有效性诊断提供统一分类框架，避免把宏观、行业、风格、资金和事件因子混在同一层比较。
- 为 `T2.10` 市场环境覆盖层提供第一版候选指标清单，但不绕过回测、时点有效性、过拟合诊断和准入门禁。
- 已与 marklogseq HTML 结构化接口手册整合为项目知识资产：`knowledge/intelligence/wiki/a_share_factor_data_interface_knowledge_asset.md`。
- 机器可读接口索引：`knowledge/intelligence/wiki/a_share_factor_data_interface_index.csv`。

## 数据可用性

- 当前已有数据：A 股日线、财务指标、估值、行业字段、部分跨市场行情、策略准入报告、情报采集器和 Tushare 数据工作流。
- 缺失数据：行业经营与供需、产业链图谱、政策强度、公告/新闻事件分类、舆情热度、一致预期、研报评级变化、部分资金结构数据。
- 数据接入难度：`partial`

## 策略转化判断

- 推荐动作：`use_as_market_regime_and_data_gap_blueprint`
- 可转化为：`data task / diagnostic / overlay / explanation`
- 关联任务：`T1.3;T2.5;T2.10;T5.2`

## 风险与反证

- 未来函数风险：政策、新闻、公告、财报和事件数据必须区分发布时间、抓取时间和策略可见时间。
- 幸存者偏差风险：行业、主题、概念和股票池成员必须按历史时点处理，不能只用当前成分。
- 过拟合风险：六域因子非常宽，若一次性全部入模，容易做出只解释历史的复杂系统。
- 市场迁移风险：板块轮动、政策主题和资金偏好具有阶段性，不能静态外推。
- 授权与数据维护风险：外部新闻、研报、政策库、舆情和一致预期数据存在权限、稳定性和维护成本问题。

## 结论

- Status: `screened`
- Next Action: 先转为市场环境诊断和数据缺口任务，不直接生成交易信号；优先服务质量低换手双策略的弱样本外区间归因。
