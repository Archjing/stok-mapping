from __future__ import annotations

from pathlib import Path

from quant.ai_corpus import fetch_ai_corpus, upsert_ai_corpus_documents
from quant.ai_corpus.registry import canonical_provider_name, get_provider_spec
from quant.ai_corpus.providers.sia_sales import _parse_release


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures/ai_corpus/sia_sales"


def test_parse_release_extracts_structured_sales_fields() -> None:
    html = (FIXTURE_DIR / "global-semiconductor-sales-increase-9-2-month-to-month-in-may.html").read_text(
        encoding="utf-8"
    )
    parsed = _parse_release(html)

    assert parsed["title"].startswith("Global Semiconductor Sales Increase 9.2%")
    assert parsed["published_at"].startswith("2026-07-06")
    assert parsed["report_period"] == "2026-May"
    assert parsed["period_kind"] == "month"
    assert parsed["sales_usd_billion"] == "120.6"
    assert parsed["mom_pct"] == "9.2"
    assert parsed["yoy_pct"] == "104.1"


def test_fixture_fetch_normalizes_documents(tmp_path: Path) -> None:
    frame = fetch_ai_corpus(
        provider="sia",
        root=tmp_path,
        fixture_dir=FIXTURE_DIR,
        limit=5,
    )

    assert len(frame) == 1
    row = frame.iloc[0].to_dict()
    assert row["provider"] == "sia_sales"
    assert row["corpus_type"] == "sia_sales_news"
    assert row["event_type"] == "industry_sales_report"
    assert row["pcode"] == "2026-May"
    assert row["ptype"] == "month"
    assert row["industries"] == "semiconductor"
    assert "semiconductor-cycle" in row["topics"]
    assert row["parse_status"] == "content_extracted"
    assert row["url"].startswith("https://www.semiconductors.org/")
    assert Path(row["raw_path"]).exists()


def test_fixture_upsert_is_idempotent(tmp_path: Path) -> None:
    from quant.ai_corpus import query_ai_corpus_documents

    frame = fetch_ai_corpus(
        provider="sia-sales",
        root=tmp_path,
        fixture_dir=FIXTURE_DIR,
        limit=5,
    )
    db_path = tmp_path / "ai_corpus.sqlite"
    first = upsert_ai_corpus_documents(db_path, frame.to_dict(orient="records"))
    second = upsert_ai_corpus_documents(db_path, frame.to_dict(orient="records"))
    rows = query_ai_corpus_documents(db_path, provider="sia_sales", limit=20)

    assert first == 1
    # SQLite's upsert reports the conflict update as a change, while the row
    # count remains stable; idempotence is verified by the single stored row.
    assert second >= 1
    assert len(rows) == 1


def test_registry_alias_and_spec() -> None:
    assert canonical_provider_name("sia") == "sia_sales"
    assert canonical_provider_name("sia-sales-news") == "sia_sales"
    spec = get_provider_spec("sia_sales")
    assert spec.status == "implemented_mvp"
    assert spec.corpus_types == ("sia_sales_news",)
