from __future__ import annotations

from importlib import import_module

import pytest

import quant.intelligence as intelligence
from quant.intelligence.schema import IntelligenceValidationResult, LEDGER_COLUMNS


@pytest.mark.parametrize(
    ("module_name", "symbol_pairs"),
    [
        (
            "quant.intelligence.collection",
            [
                ("collect_intelligence", "collect_intelligence"),
                ("import_local_intelligence", "import_local_intelligence"),
                ("_candidate_id", "_candidate_id"),
                ("_candidate_row", "_candidate_row"),
                ("_topic_tags_from_text", "_topic_tags_from_text"),
                ("_strategy_tags_from_topics", "_strategy_tags_from_topics"),
                ("_dedupe_rows", "_dedupe_rows"),
                ("_write_collect_report", "_write_collect_report"),
                ("_title_from_markdown", "_title_from_markdown"),
                ("_relative_source", "_relative_source"),
                ("_rows_from_local_file", "_rows_from_local_file"),
                ("_collect_local_dir", "_collect_local_dir"),
                ("_fetch_rss", "_fetch_rss"),
                ("_fetch_arxiv", "_fetch_arxiv"),
                ("_fetch_openalex", "_fetch_openalex"),
                ("_fetch_crossref", "_fetch_crossref"),
            ],
        ),
        (
            "quant.intelligence.candidates",
            [
                ("_write_candidates", "write_candidates"),
                ("_write_review_csv", "write_review_csv"),
                ("_read_candidate_rows", "read_candidate_rows"),
            ],
        ),
        (
            "quant.intelligence.review",
            [
                ("review_intelligence_candidates", "review_intelligence_candidates"),
                ("_source_excerpt", "_source_excerpt"),
                ("_contains_any", "_contains_any"),
                ("_review_suggestion", "_review_suggestion"),
                ("_write_review_report", "_write_review_report"),
            ],
        ),
        (
            "quant.intelligence.validation",
            [
                ("validate_intelligence_ledger", "validate_intelligence_ledger"),
                ("_read_ledger", "_read_ledger"),
                ("_read_csv_rows", "_read_csv_rows"),
                ("_local_path_exists", "_local_path_exists"),
                ("_validate_rag_manifest", "_validate_rag_manifest"),
            ],
        ),
    ],
)
def test_intelligence_package_root_exports_alias_split_modules(
    module_name: str,
    symbol_pairs: list[tuple[str, str]],
) -> None:
    split_module = import_module(module_name)

    for root_symbol, split_symbol in symbol_pairs:
        assert getattr(intelligence, root_symbol) is getattr(split_module, split_symbol)


def test_intelligence_validation_schema_exports_remain_compatible() -> None:
    assert intelligence.IntelligenceValidationResult is IntelligenceValidationResult
    assert intelligence.LEDGER_COLUMNS is LEDGER_COLUMNS
