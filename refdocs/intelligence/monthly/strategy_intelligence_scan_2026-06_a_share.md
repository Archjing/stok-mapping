# A 股策略情报月度扫描｜2026-06

生成日期：2026-06-10  
扫描窗口：2026-05-11 到 2026-06-10。  
扫描范围：A 股相关；优先近 30 天发表、修订或可形成当前研发输入的公开量化研究。  
输出定位：候选情报，不等同于策略有效性证据；进入正式台账前仍需人工复核、评分和偏差风险补充。

## Abstract

本次只收集 A 股相关策略情报，重点关注能服务当前 `stok-mapping` 策略研发主线的材料：市场状态识别、低波/低换手/质量策略的 regime 解释、A 股投资者行为 proxy、短线量价因子库与严格 walk-forward 验证。检索结果显示，近 30 天内公开且直接与 A 股量化策略相关的高质量资料数量有限；本次宁缺毋滥，筛出 3 条候选情报。核心结论是：当前项目不应继续盲目微调单一低换手质量策略，而应优先建设 regime 诊断、投资者行为 proxy 和短线量价因子复核框架。

## 筛选结论

| ID | 情报 | A 股相关性 | 推荐动作 | 优先级 |
| --- | --- | --- | --- | --- |
| ASHARE-INT-20260610-001 | CSI300 高频 regime、波动预测与收益预测 | 直接使用沪深 300 高频数据 | 转入 T2.9/T2.11 的 regime 诊断与波动 gating 研究 | 高 |
| ASHARE-INT-20260610-002 | 中美投资者信息扩散与超额联动 | 使用 4,533 只中国股票，强调散户驱动扩散 | 转入投资者行为 proxy 与行业/股票联动解释研究 | 中高 |
| ASHARE-INT-20260610-003 | Alpha191 A 股短线量价因子的跨市场验证 | 因子源自 A 股短线交易信号库 | 转入 A 股 Alpha191 因子本地复核，不直接照搬结论 | 中 |

## 1. CSI300 高频 regime、波动预测与收益预测

- 标题：Volatility Forecasting and Return Prediction under Market Regimes: Evidence from High-Frequency Chinese Equity Data
- 作者：Xinyue Fang, Robert Ślepaczuk
- 发布时间：2026-06-08
- 来源：https://arxiv.org/abs/2606.09478
- 研究对象：2005-2023 年沪深 300 指数高频数据

### 核心观点

该研究把 regime-aware 波动预测与机器学习收益预测结合：先用带 regime 的 HARQ 与 Markov-switching GJR-GARCH 捕捉长记忆、非对称和结构性市场状态，再把波动预测、regime 指标和收益相关变量送入 XGBoost，并用严格 walk-forward OOS 评估。其结论对本项目很关键：无条件收益预测弱，且主要集中在低波动 regime；简单预测交易策略计入真实成本后通常失败，但波动缩放、低波 gating、阈值校准和换手控制有助于改善防御型表现。

### 对本项目的可验证假设

- 低换手/质量策略的收益改善可能来自特定低波 regime，而不是稳定 alpha。
- 当前 T2.7 “最后一折拉高”应优先解释为 regime 依赖候选证据。
- admission 报告可加入 regime split：低波、正常、高波阶段分别统计年化、Sharpe、回撤、换手和正收益折比例。
- 波动缩放可能比直接调高质量/低换手权重更符合 KISS。

### 所需数据

- 本地 `market_daily_bars`、指数 `market_index_bars`、交易日历。
- 若后续做高频版本，需要分钟级或更高频沪深 300 数据；V1 可以先用日频 realized volatility proxy。

### 风险

- 高频研究结论不能直接迁移到日频个股组合。
- XGBoost 收益预测容易过拟合；本项目 V1 应先做 regime 分层诊断，而不是直接引入复杂模型。
- 需要明确成本、换手和阈值校准，否则容易产生“统计预测强、交易结果弱”的错觉。

### 建议落地

- 进入 `T2.9`：把 `regime_failure` 做成归因标签。
- 进入 `T2.11` 候选：波动 gating / volatility scaling overlay。
- 不进入当前实盘模拟候选。

## 2. 中美投资者信息扩散与超额联动

- 标题：The effect of investor-driven information diffusion on excess comovement: Evidence from retail and institutional investors in China and the United States
- 作者：Fei Ren, Miao-Miao Yi, Zhang-Hangjian Chen, Xiang Gao
- arXiv 提交时间：2026-05-09
- 期刊信息：Journal of International Financial Markets, Institutions and Money 106 (2026) 102258
- 来源：https://arxiv.org/abs/2605.08726
- 研究对象：4,533 只中国股票与 4,517 只美国股票，2010-2022

### 核心观点

该研究关注不同投资者群体驱动的信息扩散如何影响股票间超额联动。结论显示，在中国市场，散户驱动的信息扩散对超额联动影响更强；存在快扩散股票领先慢扩散股票的 lead-lag 关系；中国市场中散户驱动扩散对超额联动具有较强且持续的预测能力。

### 对本项目的可验证假设

- A 股市场信号不能只看公司基本面，散户行为 proxy 可能解释短期联动和行业扩散。
- 可把“关注度/成交活跃/换手突变/同概念扩散”做成解释层，不直接作为买入信号。
- 当前低换手策略若在某些阶段失效，可能与高扩散、高联动、高情绪阶段相关。
- 行业集中度约束应同时看行业静态分类和扩散网络暴露。

### 所需数据

- 日频成交额、换手率、波动率、涨跌停、行业/概念分类。
- 可选 proxy：同主题股票同步上涨比例、成交额扩散、热门概念覆盖、公告/新闻事件扩散。
- 若要复现论文级别，需要投资者类型交易数据；本项目大概率只能做匿名聚合 proxy。

### 风险

- 真实个人/机构账户级行为数据不可得，本项目只能做 proxy。
- 信息扩散 proxy 容易和动量、流动性、行业拥挤混淆。
- 不能把“散户扩散强”直接解释成 alpha，先做解释和风险提示更稳妥。

### 建议落地

- 进入关注个股分析工具：增加“扩散/联动/拥挤”解释项。
- 进入 `T2.9`：把行业集中与 regime 依赖结合分析。
- 进入 `T1.3/T2.11`：为文本事件和市场行为 proxy 预留字段。

## 3. Alpha191 A 股短线量价因子的跨市场验证

- 标题：Cross-Market Alpha: Testing Short-Term Trading Factors in the U.S. Market via Double-Selection LASSO
- 作者：Jin Du, Alexander Walter, Maxim Ulrich
- 首次提交：2026-01-10
- 近 30 天内修订：2026-05-21
- 来源：https://arxiv.org/abs/2601.06499
- 研究对象：源自中国 A 股市场的 Alpha191 短线量价/微观结构信号，并在美股 S&P 500 上做跨市场验证

### 核心观点

该研究从 A 股零售主导、政策敏感、高频活跃交易结构中产生的 Alpha191 短线交易信号出发，使用 double-selection LASSO 控制大量基本面因子后，筛选部分非冗余价格成交量与微观结构信号。对本项目最有用的不是“美股也有效”的结论，而是“短线量价行为 footprint 可以和慢变量基本面形成双周期框架”。

### 对本项目的可验证假设

- 当前质量/低换手策略只用慢变量，可能缺少短线行为确认层。
- 可先从 Alpha191 中挑选低复杂度、日频可复现、无未来函数的少数因子，作为质量策略的二阶段过滤或风险提示。
- 不应一次性引入 191 个因子；V1 只选 5-10 个可解释的量价因子做候选。

### 所需数据

- 日频 OHLCV、成交额、换手率、复权因子。
- 严格 qfq_asof 或 raw/bfq 口径审计，避免复权污染。
- 因子计算时必须确认 rolling window 不含未来数据。

### 风险

- Alpha191 因子数量多，若直接暴力搜索，过拟合风险极高。
- 部分因子可能依赖高质量分钟数据或复杂微观结构字段，本项目日频 V1 不一定能复现。
- 跨市场验证不是 A 股本地有效性证明，必须重新在本地库做 PIT / 成本后 walk-forward。

### 建议落地

- 进入 `T2.10` sleeve/rerank 的前置研究：慢变量质量 + 短线行为确认。
- 进入 `T2.5` 因子有效性诊断扩展：新增 Alpha191 子集候选。
- 暂不进入主策略代码，先做因子库和诊断。

## 本次不纳入的材料类型

- 仅泛泛讨论“AI 炒股”“量化私募”的新闻，不具备可复现策略假设。
- 只面向美股、港股或全球资产且没有 A 股来源/验证/迁移价值的资料。
- 无发布时间、无原始链接、只有转载摘要的材料。
- 需要付费研报全文才能复查关键结论的材料。

## 对当前策略研发的直接影响

1. `T2.7` 当前不应继续盲目调参，优先用 `T2.9` 解释失败来源。
2. `regime_failure` 应成为策略失败归因的正式标签，尤其用于解释最后一折拉高。
3. A 股散户行为 proxy 值得进入解释层和风险层，但不应直接变成买卖信号。
4. Alpha191 类短线因子可以补足慢变量质量策略，但必须小样本、低复杂度、强审计地引入。
5. 下一步最小开发建议：先实现 T2.9，再把报告中的 regime / diffusion / Alpha191 分别转成候选任务。

## 候选入库建议

| ID | 推荐状态 | 建议关联任务 |
| --- | --- | --- |
| ASHARE-INT-20260610-001 | screened | T2.9;T2.11 |
| ASHARE-INT-20260610-002 | collected | T1.3;T2.9;关注个股分析工具 |
| ASHARE-INT-20260610-003 | collected | T2.5;T2.10 |

## 参考来源

- arXiv: Volatility Forecasting and Return Prediction under Market Regimes: Evidence from High-Frequency Chinese Equity Data, https://arxiv.org/abs/2606.09478
- arXiv: The effect of investor-driven information diffusion on excess comovement: Evidence from retail and institutional investors in China and the United States, https://arxiv.org/abs/2605.08726
- arXiv: Cross-Market Alpha: Testing Short-Term Trading Factors in the U.S. Market via Double-Selection LASSO, https://arxiv.org/abs/2601.06499
