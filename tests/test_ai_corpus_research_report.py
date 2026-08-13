"""Tests for the broker research-report metadata provider."""
from __future__ import annotations

from pathlib import Path

from quant.ai_corpus.providers.research_report import (
    fetch_research_reports,
    parse_research_reports,
)


FIXTURE_DIR = Path("tests/fixtures/ai_corpus/research_report")


def test_parse_research_reports_extracts_metadata() -> None:
    import pandas as pd

    frame = pd.read_csv(FIXTURE_DIR / "research_reports.csv")
    rows = parse_research_reports(frame)
    assert len(rows) >= 1
    first = rows[0]
    assert first["provider"] == "research_report"
    assert first["corpus_type"] == "research_report"
    assert first["symbols"] == "000001"
    assert first["org"]  # 券商机构非空
    assert first["published_at"]  # 日期非空
    assert first["parse_status"] == "metadata_only"
    # 盈利预测进入 topics 的 stat: 标签
    assert "rating=" in first["topics"]


def test_parse_research_reports_never_stores_full_text() -> None:
    """Hard constraint: no unauthorized full text — content_html/raw_text empty."""
    import pandas as pd

    frame = pd.read_csv(FIXTURE_DIR / "research_reports.csv")
    rows = parse_research_reports(frame)
    for row in rows:
        assert row["content_html"] == ""
        assert row["raw_text"] == ""


def test_fetch_research_reports_fixture(tmp_path: Path) -> None:
    frame = fetch_research_reports(
        root=tmp_path,
        fixture_dir=Path.cwd() / FIXTURE_DIR,
        raw_archive_dir="raw/research_report",
        limit=10,
    )
    assert not frame.empty
    assert set(frame["provider"]) == {"research_report"}
    assert (frame["parse_status"] == "metadata_only").all()
    assert (frame["raw_text"] == "").all()
    assert (frame["content_html"] == "").all()
