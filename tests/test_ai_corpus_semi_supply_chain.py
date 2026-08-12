from __future__ import annotations

from pathlib import Path

from phase0.ai_corpus import fetch_ai_corpus, upsert_ai_corpus_documents
from phase0.ai_corpus.registry import canonical_provider_name, get_provider_spec


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures/ai_corpus/semi_supply_chain"


def test_fixture_fetch_parses_both_corpus_types(tmp_path: Path) -> None:
    frame = fetch_ai_corpus(
        provider="semi-supply-chain",
        root=tmp_path,
        fixture_dir=FIXTURE_DIR,
        limit=10,
    )

    assert len(frame) == 2
    tsmc = frame[frame["corpus_type"] == "tsmc_monthly_revenue"].iloc[0].to_dict()
    korea = frame[frame["corpus_type"] == "korea_semi_exports"].iloc[0].to_dict()

    # TSMC reprint: revenue and YoY extracted from title
    assert tsmc["pcode"] == "2026-07"
    assert tsmc["ptype"] == "month"
    assert "revenue_ntd_billion=323.17" in tsmc["topics"]
    assert "yoy_pct=25.8" in tsmc["topics"]
    assert tsmc["source_confidence"] == "media_reprint_of_official_disclosure"
    assert tsmc["industries"] == "semiconductor"
    assert tsmc["language"] == "zh-CN"

    # Korea reprint: YoY extracted; USD figure parsed when present in body
    assert korea["pcode"] == "2026-07"
    assert "yoy_pct=31.2" in korea["topics"]
    assert korea["corpus_type"] == "korea_semi_exports"
    assert Path(korea["raw_path"]).exists()


def test_fixture_upsert_is_idempotent(tmp_path: Path) -> None:
    from phase0.ai_corpus import query_ai_corpus_documents

    frame = fetch_ai_corpus(
        provider="tsmc",
        root=tmp_path,
        fixture_dir=FIXTURE_DIR,
        limit=10,
    )
    db_path = tmp_path / "ai_corpus.sqlite"
    first = upsert_ai_corpus_documents(db_path, frame.to_dict(orient="records"))
    second = upsert_ai_corpus_documents(db_path, frame.to_dict(orient="records"))
    rows = query_ai_corpus_documents(db_path, provider="semi_supply_chain", limit=20)

    assert first == 2
    assert second >= 1  # SQLite upsert counts conflict updates; row count is stable
    assert len(rows) == 2


def test_registry_alias_and_spec() -> None:
    assert canonical_provider_name("tsmc-revenue") == "semi_supply_chain"
    assert canonical_provider_name("korea-exports") == "semi_supply_chain"
    spec = get_provider_spec("semi_supply_chain")
    assert spec.status == "implemented_mvp"
    assert spec.corpus_types == ("tsmc_monthly_revenue", "korea_semi_exports")
