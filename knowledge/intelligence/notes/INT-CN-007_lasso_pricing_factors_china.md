# 情报解读：基于双重选择 LASSO 模型的我国股市定价因子边际有效性研究

## 元信息

- Intelligence ID: `INT-CN-007`
- Source Type: `paper`
- Source Path or URL: `refdocs/papers/cn/markdown/cn07_lasso_pricing_factors_china.md`
- Published At: `2024`
- Collected At: `2026-06-07`
- Market Scope: 我国股市 / A 股
- Topic Tags: `lasso;factor-pricing`
- Strategy Tags: `factor-selection;redundancy-control`

## 归档完整性

- PDF SHA-256: `c5f8857db2a727bcfcdada9157bb7cbd108184214f9190ab26206af2aba9f32c`
- Markdown SHA-256: `10242db07cc796be9cb58ee5cd59eda33117627e76859364908fcf4c43617580`
- Markdown 行尾口径：LF；仅规范化 PDF 转写遗留的混合行尾，不改写论文正文或研究结论。

## Abstract

这篇论文用双重选择 LASSO 从中国股市 85 个定价因子中识别候选因子的边际有效性。研究强调，判断因子有效性时不能只看风险溢价，还要看随机贴现因子载荷，并通过“横截面 LASSO -> 逐步 LASSO -> 筛选后 OLS”的流程控制遗漏变量和冗余因子。论文发现 2014 年后提出的 15 个候选因子中有 7 个具有边际有效性，且在多种稳健性检验下基本保持。对本项目而言，它最适合作为因子库治理、候选策略筛选和冗余控制的方法论依据。

## 核心观点

- 高维因子库中同时存在有效因子、冗余因子和无效因子，直接堆叠因子会造成多重共线、误设和过拟合。
- DS-LASSO 通过两轮选择降低遗漏变量风险，比单一 LASSO、PCA、逐步回归等方法更适合做边际有效性筛选。
- 论文识别的边际有效因子包括低 Beta、盈利、投资、管理费用、预期投资增长和隔夜收益等方向。
- 因子有效性具有时变特征，不能把历史显著性静态外推到当前市场。

## 对 stok-mapping 的启发

- 本文不应被转化为单一交易策略，而应转化为 `T2.5` 因子有效性诊断和 admission 前置筛选工具。
- 当前 12 个候选策略的全量准入复核，应增加“因子冗余、与 legacy baseline 的相关性、最近折贡献、参数邻域稳定性”的解释维度。
- RAG 检索中应把本文归类为“因子动物园治理 / 边际有效性 / 冗余控制 / overfit diagnostic”，服务策略池完善和准入报告解释。
- 对新因子，应要求先证明其在当前已存在本土主因子之外仍有边际贡献，再进入候选策略池。

## 数据可用性

- 当前已有数据：A 股日线、股票池、基础财务因子、walk-forward folds、strategy-admission 输出、overfit diagnostic。
- 缺失数据：完整 85 因子库、论文中使用的所有分析师/波动/特征组合因子和 SDF 载荷估计模块。
- 数据接入难度：`ready` 用于治理思想；`partial` 用于完整 DS-LASSO 复刻。

## 策略转化判断

- 推荐动作：`use_for_factor_effectiveness_design`
- 可转化为：`data task / diagnostic / admission precheck / explanation`
- 关联任务：`T2.5;T2.8;T5.2`

## 风险与反证

- 未来函数风险：因子发现时间、财务披露可见性和训练窗口必须严格分离。
- 幸存者偏差风险：因子库和样本组合必须按历史可得股票池构建。
- 过拟合风险：LASSO 选择本身仍依赖样本划分、正则化参数和候选集合，不能替代样本外 admission。
- 市场迁移风险：论文发现的有效因子可能随发表、拥挤和制度环境变化衰减。
- 授权与数据维护风险：完整因子库依赖商业数据字段，本项目当前不应承诺完全复刻。

## 结论

- Status: `evaluated`
- Next Action: 建立“因子边际有效性诊断”任务草案，先作为策略池治理和 RAG 解释层，不直接生成交易信号。
