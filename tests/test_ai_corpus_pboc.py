"""Tests for the PBOC monetary-policy report provider."""
from __future__ import annotations

from pathlib import Path

from quant.ai_corpus.providers.pboc import (
    _parse_listing_links,
    _report_period,
    fetch_pboc_reports,
    parse_pboc_report_page,
)


FIXTURE_DIR = Path("tests/fixtures/ai_corpus/pboc")


def test_report_period_extraction() -> None:
    assert _report_period("2026年第二季度中国货币政策执行报告") == "2026Q2"
    assert _report_period("2025年第四季度中国货币政策执行报告") == "2025Q4"
    assert _report_period("2025年货币政策执行报告") == "2025"


def test_parse_listing_links_finds_report_details() -> None:
    html = (FIXTURE_DIR / "pboc_report_list.html").read_text(encoding="utf-8")
    links = _parse_listing_links(html)
    assert len(links) >= 8  # 2023-2026 reports present
    titles = [t for t, _ in links]
    assert any("2026年第二季度" in t for t in titles)
    # year-level folder pages are excluded
    assert not any(t.endswith("年货币政策执行报告") for t in titles)


def test_parse_pboc_report_page_extracts_fields() -> None:
    html = (FIXTURE_DIR / "pboc_report_2026q2.html").read_text(encoding="utf-8")
    doc = parse_pboc_report_page(html, url="https://www.pbc.gov.cn/x/index.html")
    assert doc["provider"] == "pboc"
    assert doc["corpus_type"] == "pboc_report"
    assert doc["title"] == "2026年第二季度中国货币政策执行报告"
    assert doc["published_at"] == "2026-08-12"
    assert doc["pcode"] == "2026Q2"
    assert doc["ptype"] == "quarter"
    assert doc["parse_status"] == "content_extracted"
    assert "货币政策" in doc["raw_text"]
    assert doc["source_confidence"] == "official_central_bank"


def test_fetch_pboc_reports_fixture(tmp_path: Path) -> None:
    frame = fetch_pboc_reports(
        root=tmp_path,
        fixture_dir=Path.cwd() / FIXTURE_DIR,
        raw_archive_dir="raw/pboc",
        limit=10,
    )
    assert not frame.empty
    assert set(frame["provider"]) == {"pboc"}
    assert (frame["pcode"] != "").all()
    # fixture runs must not hit the network — all rows have a raw_path
    assert (frame["raw_path"] != "").all()


def test_fetch_pboc_reports_filters_by_date(tmp_path: Path) -> None:
    frame = fetch_pboc_reports(
        root=tmp_path,
        fixture_dir=Path.cwd() / FIXTURE_DIR,
        raw_archive_dir="raw/pboc",
        start_date="2026-01-01",
        limit=10,
    )
    assert (frame["published_at"] >= "2026-01-01").all()
