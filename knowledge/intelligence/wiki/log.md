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

## 2026-06-23 ingest | Logseq A股个股行情影响因子全景图

- Source: `/home/zj/workspace/KMS/My_logseq/pages/A股个股行情影响因子全景图.md`
- Candidate CSV: `data/intelligence/inbox/a_share_factor_panorama_candidates_2026-06-23.csv`
- Import report: `reports/intelligence/intelligence_import_local_report_2026-06-23_a_share_factor_panorama.md`
- Created: `knowledge/intelligence/notes/INT-KMS-001_a_share_factor_panorama.md`
- Updated: `knowledge/intelligence/strategy_intelligence_ledger.csv`
- Updated: `knowledge/intelligence/rag_manifest.csv`
- Updated: `knowledge/intelligence/wiki/index.md`
- Notes: Logseq pages path is an accepted intelligence source, but `config.yaml` keeps `logseq_pages` disabled by default to avoid bulk-importing the whole personal graph.
- Open question: 是否为 Logseq 情报采集器增加 `include_globs` / `exclude_globs`，支持只扫描指定知识页而不是全量 `pages/`。

## 2026-06-23 ingest | marklogseq 数据接口结构化知识资产

- Source HTML: `/home/zj/workspace/brainstorm/modules/marklogseq/html-site/index.html`
- Linked intelligence: `INT-KMS-001`
- Created: `knowledge/intelligence/wiki/a_share_factor_data_interface_knowledge_asset.md`
- Created: `knowledge/intelligence/wiki/a_share_factor_data_interface_index.csv`
- Updated: `knowledge/intelligence/notes/INT-KMS-001_a_share_factor_panorama.md`
- Updated: `knowledge/intelligence/rag_manifest.csv`
- Updated: `knowledge/intelligence/wiki/index.md`
- Parsed categories: 11
- Parsed navigation interfaces: 70
- Parsed content pages: 71
- Notes: 该资产把 Logseq 六域因子框架与 marklogseq HTML 接口手册整合为项目可用的数据接口地图；它用于数据接入和诊断规划，不作为策略有效性证据。
