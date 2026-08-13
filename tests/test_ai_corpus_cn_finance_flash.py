from __future__ import annotations

import sqlite3
from pathlib import Path

from quant.ai_corpus import fetch_ai_corpus, query_ai_corpus_documents, upsert_ai_corpus_documents
from quant.ai_corpus.registry import canonical_provider_name, get_provider_spec


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures/ai_corpus/cn_finance_flash"


def test_cls_telegraph_fixture_normalizes_rows(tmp_path: Path) -> None:
    frame = fetch_ai_corpus(
        provider="cls-telegraph",
        root=tmp_path,
        fixture_dir=FIXTURE_DIR,
        limit=10,
    )

    assert len(frame) == 3
    row = frame.iloc[0].to_dict()
    assert row["provider"] == "cls_telegraph"
    assert row["corpus_type"] == "market_flash"
    assert row["source"] == "财联社电报"
    assert row["published_at"]
    assert row["raw_text"]
    assert row["topics"]  # subjects 应映射为 topics
    assert row["language"] == "zh-CN"
    assert row["parse_status"] == "full_text"
    assert Path(row["raw_path"]).exists()


def test_sina_7x24_fixture_normalizes_and_extracts_symbols(tmp_path: Path) -> None:
    frame = fetch_ai_corpus(
        provider="sina",
        root=tmp_path,
        fixture_dir=FIXTURE_DIR,
        limit=50,
    )

    assert len(frame) >= 1
    row = frame.iloc[0].to_dict()
    assert row["provider"] == "sina_7x24"
    assert row["source"] == "新浪财经 7x24"
    assert row["published_at"]
    assert row["raw_text"]
    # 部分快讯 ext 里有 stocks，符号应被抽到 symbols 列
    assert row["language"] == "zh-CN"


def test_wallstcn_lives_fixture_normalizes_rows(tmp_path: Path) -> None:
    frame = fetch_ai_corpus(
        provider="wallstcn",
        root=tmp_path,
        fixture_dir=FIXTURE_DIR,
        limit=20,
    )

    assert len(frame) == 5
    row = frame.iloc[0].to_dict()
    assert row["provider"] == "wallstcn_lives"
    assert row["source"] == "华尔街见闻实时快讯"
    assert row["raw_text"]
    assert row["published_at"]


def test_cn_finance_flash_upsert_is_idempotent(tmp_path: Path) -> None:
    frame = fetch_ai_corpus(
        provider="cls",
        root=tmp_path,
        fixture_dir=FIXTURE_DIR,
        limit=10,
    )
    db_path = tmp_path / "ai_corpus.sqlite"
    first = upsert_ai_corpus_documents(db_path, frame.to_dict(orient="records"))
    second = upsert_ai_corpus_documents(db_path, frame.to_dict(orient="records"))
    rows = query_ai_corpus_documents(db_path, provider="cls_telegraph", limit=20)

    assert first == 3
    assert second >= 3
    assert len(rows) == 3
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM ai_corpus_documents").fetchone()[0] == 3


def test_cn_finance_flash_registry_aliases() -> None:
    assert canonical_provider_name("cls") == "cls_telegraph"
    assert canonical_provider_name("cailianpress-telegraph") == "cls_telegraph"
    assert canonical_provider_name("sina-7x24") == "sina_7x24"
    assert canonical_provider_name("wallstreetcn") == "wallstcn_lives"
    assert get_provider_spec("cls-telegraph").status == "implemented_mvp"
    assert get_provider_spec("sina").corpus_types == ("market_flash",)
    assert get_provider_spec("wallstcn").source == "华尔街见闻实时快讯"
