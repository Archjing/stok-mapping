# 2024-2026 量化投资策略 · 高影响力论文索引

> 归档日期: 2026-05-29
> 来源: SSRN Top Downloads Q1 2025 / KDD/WWW/AAAI/NeurIPS 顶会 / arXiv / Journal of Empirical Finance
> 筛选标准: 引用量/下载量/顶会接收/与 stok-mapping 项目相关性

---

## 一、因子建模与资产定价（最高相关）

### 1. Artificial Intelligence Asset Pricing Models ⭐⭐⭐⭐⭐
- **作者**: Bryan T. Kelly, Boris Kuznetsov, Semyon Malamud, Teng Andrea Xu
- **来源**: SSRN Top Downloaded Q1 2025
- **链接**: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5089371
- **关键词**: AI-driven asset pricing, machine learning factor models, return prediction
- **价值**: 直接用 AI 方法建模资产定价因子，与我们的多因子打分模型直接相关

### 2. Learning Universal Multi-level Market Irrationality Factors to Improve Stock Return Forecasting ⭐⭐⭐⭐⭐
- **来源**: KDD 2025
- **论文**: https://arxiv.org/pdf/2502.04737
- **代码**: https://github.com/lIcIIl/UMI
- **关键词**: market irrationality factors, stock return forecasting, multi-level factors
- **价值**: KDD 2025 顶会，从市场非理性角度挖掘通用因子，与我们的映射情绪因子互补

### 3. Factor Correlation and the Cross Section of Asset Returns: A Correlation-Robust Machine Learning Approach ⭐⭐⭐⭐
- **作者**: Chuanping Sun
- **来源**: Journal of Empirical Finance, 2024, Vol.77
- **链接**: https://www.sciencedirect.com/science/article/pii/S092753982400032X
- **关键词**: factor correlation, cross-sectional returns, robust estimation, high-dimensional factor models
- **价值**: 因子共线性问题的前沿解决方案，直接回应我们计划书中的 VIF 检查需求

### 4. HRFT: Mining High-Frequency Risk Factor Collections End-to-End via Transformer ⭐⭐⭐⭐
- **来源**: WWW 2025
- **论文**: https://dl.acm.org/doi/pdf/10.1145/3701716.3715235
- **代码**: https://github.com/wencyxu/IRF-LLM-accepted-at-WWW25-
- **关键词**: risk factors, transformer, high-frequency, end-to-end mining
- **价值**: Transformer 自动挖掘高频风险因子，适合 Phase 3 增强因子库

### 5. FactorGCL: A Hypergraph-Based Factor Model with Temporal Residual Contrastive Learning ⭐⭐⭐
- **来源**: arXiv 2025
- **论文**: https://arxiv.org/abs/2502.05218
- **关键词**: hypergraph, factor model, contrastive learning, stock returns
- **价值**: 超图 + 对比学习捕捉股票间的非线性关系

---

## 二、股票预测与 Transformer 架构

### 6. MASTER: Market-Guided Stock Transformer for Stock Price Forecasting ⭐⭐⭐⭐⭐
- **来源**: AAAI 2024
- **论文**: https://arxiv.org/abs/2312.15235
- **代码**: https://github.com/SJTU-Quant/MASTER
- **关键词**: stock transformer, market-guided, price forecasting
- **价值**: AAAI 顶会，市场引导的 Transformer 架构，SJTU-Quant 团队出品

### 7. StockMixer: A Simple yet Strong MLP-based Architecture for Stock Price Forecasting ⭐⭐⭐⭐
- **来源**: AAAI 2024
- **论文+代码**: https://github.com/SJTU-Quant/StockMixer
- **关键词**: MLP, stock forecasting, simple architecture
- **价值**: 用简单 MLP 打平复杂 Transformer，KISS 原则的完美例证

### 8. Multi-period Learning for Financial Time Series Forecasting ⭐⭐⭐
- **来源**: KDD 2025
- **论文**: https://dl.acm.org/doi/pdf/10.1145/3690624.3709422
- **代码**: https://github.com/Meteor-Stars/MLF
- **关键词**: multi-period, financial time series, forecasting

---

## 三、强化学习与交易策略

### 9. MacroHFT: Memory Augmented Context-aware Reinforcement Learning On High Frequency Trading ⭐⭐⭐⭐
- **来源**: KDD 2024
- **论文**: https://arxiv.org/pdf/2406.14537
- **代码**: https://github.com/ZONG0004/MacroHFT
- **关键词**: reinforcement learning, high-frequency trading, memory augmented
- **价值**: RL + 宏观上下文感知，高频交易场景

### 10. ROIDICE: Offline Return on Investment Maximization for Efficient Decision Making ⭐⭐⭐
- **来源**: NeurIPS 2024
- **论文**: https://openreview.net/pdf?id=6Kg26g1quR
- **代码**: https://github.com/ku-dmlab/ROIDICE
- **关键词**: offline RL, return maximization, portfolio optimization
- **价值**: NeurIPS 顶会，离线强化学习做投资组合优化

---

## 四、LLM 与 NLP 在金融中的应用

### 11. FinReport: Explainable Stock Earnings Forecasting via News Factor Analyzing Model ⭐⭐⭐⭐
- **来源**: WWW 2024
- **论文**: https://arxiv.org/pdf/2403.02647
- **代码**: https://github.com/frinkleko/FinReport
- **关键词**: explainable, earnings forecasting, news factor, LLM
- **价值**: 财报预测+可解释性，直接指导我们的 LLM 摘要模块设计

### 12. Learning to Generate Explainable Stock Predictions using Self-Reflective Large Language Models ⭐⭐⭐⭐
- **来源**: WWW 2024
- **论文**: https://arxiv.org/abs/2402.03659
- **代码**: https://github.com/koa-fin/sep
- **关键词**: self-reflective LLM, explainable stock prediction
- **价值**: LLM 自反思机制生成可解释的股票预测

### 13. The Natural Language of Finance ⭐⭐⭐
- **作者**: Gerard Hoberg, Asaf Manela
- **来源**: SSRN Top Downloaded Q1 2025
- **链接**: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5119322
- **关键词**: NLP, financial text, language model
- **价值**: 金融文本 NLP 的前沿研究

---

## 五、组合优化与风险管理

### 14. A Global Optimal Portfolio for m-Sparse Sharpe Ratio Maximization ⭐⭐⭐⭐
- **来源**: NeurIPS 2024
- **论文**: https://arxiv.org/abs/2410.21100
- **代码**: https://github.com/linyizun2024/mSSRM
- **关键词**: sparse portfolio, Sharpe ratio, global optimal
- **价值**: NeurIPS 顶会，稀疏组合优化，直接改进我们的风险预算体系

### 15. FinRL: A Deep Reinforcement Learning Library for Automated Stock Trading in Quantitative Finance ⭐⭐⭐⭐⭐
- **来源**: SSRN Top Downloaded Q1 2025 (持续高下载)
- **论文**: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3737859
- **代码**: https://github.com/AI4Finance-Foundation/FinRL
- **关键词**: deep RL, automated trading, open-source library
- **价值**: FinRL 是量化交易 RL 的事实标准库，长期高引

---

## 六、跨市场与投资者情绪

### 16. Investor Sentiment and Optimizing Traditional Quantitative Investments ⭐⭐⭐⭐
- **来源**: ScienceDirect, 2025
- **论文**: https://www.sciencedirect.com/science/article/pii/S1059056025003909
- **关键词**: investor sentiment, quantitative investment, forum posts
- **价值**: 从论坛帖子提取情绪因子优化量化策略，与我们的情绪面因子直接相关

### 17. Exploring Efficient Quantitative Trading Strategies: Momentum, SMAs, and Machine Learning ⭐⭐⭐
- **来源**: ResearchGate, 2024
- **论文**: https://www.researchgate.net/publication/380931011
- **关键词**: momentum, SMA crossover, machine learning, comparison
- **价值**: 动量/SMA/ML 策略的系统对比

---

## 七、数据集与基准

### 18. FNSPID: A Comprehensive Financial News Dataset in Time Series ⭐⭐⭐⭐
- **来源**: KDD 2024
- **论文**: https://arxiv.org/abs/2402.06698
- **代码**: https://github.com/Zdong104/FNSPID_Financial_News_Dataset
- **关键词**: financial news dataset, time series, benchmark
- **价值**: KDD 顶会金融新闻数据集，可用于训练新闻情绪模块

---

## 对 stok-mapping 项目的优先级建议

| 优先级 | 论文 | 直接应用 |
|--------|------|---------|
| 🔴 立即研读 | #1 AI Asset Pricing / #2 Universal Irrationality Factors | 因子建模方法论 |
| 🔴 立即研读 | #3 Factor Correlation Robust ML | 因子共线性处理方案 |
| 🟡 Phase 2-3 | #6 MASTER / #7 StockMixer | 预测模型架构参考 |
| 🟡 Phase 3 | #11 FinReport / #12 Explainable LLM | LLM 摘要模块设计 |
| 🟢 Phase 4+ | #14 Sparse Portfolio / #15 FinRL | 组合优化/RL 增强 |
