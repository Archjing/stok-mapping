# Wiki Ingest Log

## 2026-06-09 ingest | 中文 A 股量化策略情报

- Created: `a_share_quant_strategy_intelligence_cn.md`
- Updated: `index.md`
- Source scope: `INT-CN-001` to `INT-CN-010`, `STRATEGY_SUMMARY.md`, `cn_INDEX.md`
- Notes: 当前精炼页仅提炼已归档中文策略情报，不新增外部情报，不改正式情报台账。
- Open question: 哪些中文策略假设值得优先转为 T2.5-T2.10 实验任务，仍需结合数据覆盖和准入口径判断。

## 2026-06-23 ingest | T5.2 RAG-ready Strategy Intelligence Foundation

- Created: `knowledge/intelligence/notes/INT-CN-005_ml_asset_characteristics_portfolio.md`
- Created: `knowledge/intelligence/notes/INT-CN-007_lasso_pricing_factors_china.md`
- Created: `knowledge/intelligence/notes/INT-CN-008_analyst_text_quant_strategy.md`
- Created: `knowledge/intelligence/strategy_translations/INT-CN-007_factor_effectiveness_strategy_task.md`
- Created: `knowledge/intelligence/rag_corpus_spec.md`
- Created: `knowledge/intelligence/rag_manifest.csv`
- Created: `knowledge/intelligence/monthly/README.md`
- Created: `knowledge/intelligence/monthly/index.md`
- Updated: `index.md`
- Source scope: `INT-CN-005`, `INT-CN-007`, `INT-CN-008`, existing June 2026 A-share monthly scan.
- Notes: 本次只建立 RAG-ready Markdown / CSV 语料边界，不引入向量库、SQLite、知识图谱或自动交易信号。
- Open question: 后续是否把 `factor_effectiveness_redundancy_diagnostic_v1` 纳入 T2.5 只读诊断工具，需等待全 12 候选 qfq_asof admission 复跑结果。
