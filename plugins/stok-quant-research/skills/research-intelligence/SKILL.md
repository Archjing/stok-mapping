---
name: research-intelligence
description: Use for Stok Mapping investment strategy intelligence collection, monthly 30-day quant strategy scans, source ingestion, paper/news/report evaluation, research note drafting, and Logseq/refdocs archiving.
---

# Research Intelligence

Use this skill when the task concerns investment strategy intelligence collection, source search, paper ingestion, news/source mapping, research notes, or knowledge-base archiving.

## Scope

- Preserve source URLs and distinguish external facts from project interpretation.
- Keep raw notes, source records and repeatable research ledgers in `refdocs/` or `knowledge/`.
- Put stable strategy-governance conclusions in `docs/STRATEGY_DEVELOPMENT_GUIDELINES.md` or `docs/DEVELOPMENT_PLAN.md`; do not create a parallel permanent task tree.
- Prefer structured ledgers for repeatable intelligence tracking.
- Do not mix unverifiable market rumors with validated strategy design evidence.

## Key Files

- `docs/STRATEGY_DEVELOPMENT_GUIDELINES.md`
- `docs/DEVELOPMENT_PLAN.md`
- `refdocs/intelligence/README.md`
- `refdocs/intelligence/strategy_intelligence_ledger.csv`
- `refdocs/intelligence/monthly/strategy_intelligence_scan_YYYY-MM.md`
- `refdocs/intelligence/templates/intelligence_note_template.md`
- `refdocs/intelligence/templates/strategy_translation_template.md`
- `refdocs/papers/`

## Related Local Skills

- `/home/zj/workspace/skills/article-ingest`
- `/home/zj/workspace/skills/wiki-ingest`
- `/home/zj/workspace/skills/clean-content-fetch`
- `/home/zj/workspace/skills/logseq`
- `/home/zj/workspace/skills/zettelkasten-cn`
- `/home/zj/workspace/skills/multi-search-engine`

## Review Rules

- For strategy translation, end with testable factor hypotheses, required data fields, leakage risks, and validation windows.
- For news data source work, record upstream source mapping and legal/robots/licensing uncertainty.
- For notes copied to Logseq, keep a project copy under `refdocs/` as the source of record.

## Monthly Scan Workflow

Use this workflow for repeated "near 30 days" or "monthly strategy intelligence scan" tasks.

1. Define the scan window explicitly, using exact dates such as `2026-05-09` to `2026-06-09`.
2. Search recent sources in priority order: papers/preprints, exchange/index/data-provider official materials, institutional quant research, high-quality quant blogs, then news only as supporting context.
3. Keep only items with a source URL, publication date, and a clear reason they matter to Stok Mapping.
4. Write the scan report to `refdocs/intelligence/monthly/strategy_intelligence_scan_YYYY-MM.md`.
5. For each high-value item, record: publication date, source URL, core idea, testable strategy hypothesis, required data, implementation cost, leakage/overfit/data-bias/licensing risks, and recommended action.
6. Recommended actions are `archive_only`, `screen_later`, `create_strategy_task`, or `create_data_task`.
7. Put candidates into `data/intelligence/inbox/` or the monthly report first; write to `refdocs/intelligence/strategy_intelligence_ledger.csv` only after manual scoring and bias-risk review.

Hard boundaries:

- Do not scrape paid research report full text.
- Do not treat marketing material, news headlines, or blog claims as strategy effectiveness evidence.
- Do not turn intelligence directly into trading signals.
- Do not bypass the T5.2 score, bias-risk, and strategy-translation gates.
