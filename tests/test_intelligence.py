from __future__ import annotations

import csv
from pathlib import Path

from phase0.config import load_config
from phase0.intelligence import LEDGER_COLUMNS, _write_candidates, review_intelligence_candidates, validate_intelligence_ledger


def _write_config(root: Path) -> Path:
    config_path = root / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "phase0:",
                "  intelligence:",
                "    ledger: knowledge/intelligence/strategy_intelligence_ledger.csv",
                "    rag_manifest: knowledge/intelligence/rag_manifest.csv",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return config_path


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def _ledger_row(**overrides: str) -> dict[str, str]:
    row = {
        "intelligence_id": "INT-001",
        "title": "Demo strategy intelligence",
        "source_type": "paper",
        "source_path_or_url": "refdocs/papers/demo.md",
        "published_at": "2026-06-01",
        "collected_at": "2026-06-02",
        "market_scope": "a_share",
        "topic_tags": "factor-selection",
        "strategy_tags": "factor-model",
        "evidence_type": "local_markdown",
        "quality_score": "4",
        "novelty_score": "3",
        "actionability_score": "4",
        "data_availability": "ready",
        "bias_risk": "overfit",
        "recommended_action": "screen",
        "status": "evaluated",
        "linked_strategy_task": "T5.2",
        "reviewed_at": "2026-06-03",
    }
    row.update(overrides)
    return row


def _manifest_row(**overrides: str) -> dict[str, str]:
    row = {
        "corpus_id": "RAG-INT-001-NOTE",
        "path": "knowledge/intelligence/notes/INT-001.md",
        "doc_type": "note",
        "trust_level": "curated",
        "intelligence_id": "INT-001",
        "source_path_or_url": "refdocs/papers/demo.md",
        "tags": "a_share;T5.2",
        "linked_tasks": "T5.2",
        "status": "evaluated",
        "last_reviewed": "2026-06-03",
    }
    row.update(overrides)
    return row


def test_intelligence_validate_checks_rag_manifest_success(tmp_path) -> None:
    config_path = _write_config(tmp_path)
    (tmp_path / "refdocs/papers").mkdir(parents=True)
    (tmp_path / "refdocs/papers/demo.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "knowledge/intelligence/notes").mkdir(parents=True)
    (tmp_path / "knowledge/intelligence/notes/INT-001.md").write_text("# INT-001\n", encoding="utf-8")
    _write_csv(
        tmp_path / "knowledge/intelligence/strategy_intelligence_ledger.csv",
        LEDGER_COLUMNS,
        [_ledger_row()],
    )
    _write_csv(
        tmp_path / "knowledge/intelligence/rag_manifest.csv",
        [
            "corpus_id",
            "path",
            "doc_type",
            "trust_level",
            "intelligence_id",
            "source_path_or_url",
            "tags",
            "linked_tasks",
            "status",
            "last_reviewed",
        ],
        [_manifest_row()],
    )

    result = validate_intelligence_ledger(
        config_path,
        output_report=tmp_path / "reports/intelligence/validate.md",
    )

    assert result.status == "ok"
    assert result.error_count == 0
    assert result.warning_count == 0
    assert result.row_count == 1
    assert "- Manifest Rows: 1" in result.report_md.read_text(encoding="utf-8")


def test_intelligence_validate_flags_bad_rag_manifest(tmp_path) -> None:
    config_path = _write_config(tmp_path)
    (tmp_path / "refdocs/papers").mkdir(parents=True)
    (tmp_path / "refdocs/papers/demo.md").write_text("# Demo\n", encoding="utf-8")
    _write_csv(
        tmp_path / "knowledge/intelligence/strategy_intelligence_ledger.csv",
        LEDGER_COLUMNS,
        [_ledger_row()],
    )
    _write_csv(
        tmp_path / "knowledge/intelligence/rag_manifest.csv",
        [
            "corpus_id",
            "path",
            "doc_type",
            "trust_level",
            "intelligence_id",
            "source_path_or_url",
            "tags",
            "linked_tasks",
            "status",
            "last_reviewed",
        ],
        [
            _manifest_row(
                path="knowledge/intelligence/notes/missing.md",
                intelligence_id="INT-MISSING",
            )
        ],
    )

    result = validate_intelligence_ledger(
        config_path,
        output_report=tmp_path / "reports/intelligence/validate.md",
    )

    assert result.status == "error"
    assert "RAG-INT-001-NOTE: corpus path missing: knowledge/intelligence/notes/missing.md" in result.errors
    assert "RAG-INT-001-NOTE: intelligence_id not found in ledger: INT-MISSING" in result.errors


def test_default_intelligence_config_enables_online_sources() -> None:
    cfg = load_config(Path("config.yaml"))
    sources = {source["name"]: source for source in cfg["intelligence"]["sources"]}

    assert sources["local_papers"]["enabled"] is True
    for name in ["arxiv_quant_finance", "openalex_quant_strategy", "crossref_quant_strategy", "rss_quantocracy"]:
        assert sources[name]["enabled"] is True


def test_candidate_csv_is_excel_friendly_utf8_sig(tmp_path) -> None:
    output_csv = tmp_path / "candidates.csv"

    _write_candidates([_ledger_row(title="中文策略情报")], output_csv)

    assert output_csv.read_bytes().startswith(b"\xef\xbb\xbf")
    assert "中文策略情报" in output_csv.read_text(encoding="utf-8-sig")


def test_review_candidates_writes_suggestions_without_updating_ledger(tmp_path) -> None:
    config_path = _write_config(tmp_path)
    source_path = tmp_path / "refdocs/papers/demo.md"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(
        "# 基于双重选择LASSO模型的我国股市定价因子边际有效性研究\n\n"
        "本文讨论 A 股 factor selection, LASSO, ROE, PE and turnover factors.\n",
        encoding="utf-8",
    )
    candidates_csv = tmp_path / "data/intelligence/inbox/candidates.csv"
    _write_candidates(
        [
            _ledger_row(
                source_path_or_url="refdocs/papers/demo.md",
                topic_tags="multifactor",
                strategy_tags="factor-model",
                evidence_type="local_markdown",
            )
        ],
        candidates_csv,
    )
    ledger_path = tmp_path / "knowledge/intelligence/strategy_intelligence_ledger.csv"
    _write_csv(ledger_path, LEDGER_COLUMNS, [_ledger_row()])
    before_ledger = ledger_path.read_text(encoding="utf-8")

    result = review_intelligence_candidates(
        config_path,
        candidates_csv=candidates_csv,
        output_csv=tmp_path / "data/intelligence/inbox/review.csv",
        output_report=tmp_path / "reports/intelligence/review.md",
    )

    assert result.status == "ok"
    assert result.row_count == 1
    assert ledger_path.read_text(encoding="utf-8") == before_ledger
    assert result.review_csv.read_bytes().startswith(b"\xef\xbb\xbf")
    review_rows = list(csv.DictReader(result.review_csv.open(encoding="utf-8-sig")))
    assert review_rows[0]["suggested_actionability_score"] == "4"
    assert review_rows[0]["suggested_data_availability"] == "ready"
    assert review_rows[0]["suggested_recommended_action"] == "create_strategy_task"
    assert "factor-style idea" in review_rows[0]["review_rationale"]
    assert "Ledger updated: no" in result.report_md.read_text(encoding="utf-8")
