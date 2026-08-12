from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from phase0.ai_corpus import fetch_ai_corpus, query_ai_corpus_documents, upsert_ai_corpus_documents
from phase0.ai_corpus.registry import canonical_provider_name, get_provider_spec
from phase0.cli_commands.ai_corpus import handle_ai_corpus_command, register_ai_corpus_commands


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures/ai_corpus/us_market_news"


def test_us_market_news_fixture_filters_and_normalizes_rows(tmp_path: Path) -> None:
    frame = fetch_ai_corpus(
        provider="us-market-news",
        root=tmp_path,
        fixture_dir=FIXTURE_DIR,
        provider_config={
            "feeds": [
                {
                    "name": "cnbc_markets",
                    "source": "CNBC Markets",
                    "url": "https://example.test/cnbc_markets.xml",
                    "topics": ["us_market"],
                    "language": "en-US",
                }
            ],
            "keywords": ["SOX", "semiconductor", "chip"],
        },
        limit=20,
    )

    assert len(frame) == 1
    row = frame.iloc[0].to_dict()
    assert row["provider"] == "us_market_news"
    assert row["source"] == "CNBC Markets"
    assert row["published_at"].startswith("2026-08-11T21:00:00")
    assert row["url"] == "https://example.test/news/sox-1"
    assert "keyword:SOX" in row["topics"]
    assert Path(row["raw_path"]).exists()
    assert row["parse_status"] == "metadata_only"


def test_us_market_news_upsert_is_idempotent(tmp_path: Path) -> None:
    frame = fetch_ai_corpus(
        provider="us_news",
        root=tmp_path,
        fixture_dir=FIXTURE_DIR,
        provider_config={
            "feeds": [{"name": "cnbc_markets", "url": "https://example.test/cnbc_markets.xml"}],
            "keywords": ["SOX"],
        },
        limit=20,
    )
    db_path = tmp_path / "ai_corpus.sqlite"
    first = upsert_ai_corpus_documents(db_path, frame.to_dict(orient="records"))
    second = upsert_ai_corpus_documents(db_path, frame.to_dict(orient="records"))
    rows = query_ai_corpus_documents(db_path, provider="us_market_news", limit=20)

    assert first == 1
    # SQLite's upsert reports the conflict update as a change, while the row
    # count remains stable; idempotence is verified by the single stored row.
    assert second >= 1
    assert len(rows) == 1
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM ai_corpus_documents").fetchone()[0] == 1


def test_us_market_news_registry_alias_and_cli_route(tmp_path: Path) -> None:
    assert canonical_provider_name("market-news") == "us_market_news"
    assert get_provider_spec("us-news").status == "implemented_mvp"

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "phase0:\n"
        "  ai_corpus:\n"
        "    database_path: data/ai_corpus/ai_corpus.sqlite\n"
        "    us_market_news:\n"
        "      raw_archive_dir: data/raw_data/ai_corpus/us_market_news\n"
        "      feeds:\n"
        "        - name: cnbc_markets\n"
        "          source: CNBC Markets\n"
        "          url: https://example.test/cnbc_markets.xml\n"
        "      keywords: [SOX]\n",
        encoding="utf-8",
    )
    parser = argparse.ArgumentParser()
    register_ai_corpus_commands(parser.add_subparsers(dest="command"))
    args = parser.parse_args(
        [
            "ai-corpus",
            "fetch",
            "--config",
            str(config_path),
            "--provider",
            "us-market-news",
            "--fixture-dir",
            str(FIXTURE_DIR),
            "--min-rows",
            "1",
        ]
    )

    assert handle_ai_corpus_command(args, parser=parser) == 0
    assert (tmp_path / "data/ai_corpus/ai_corpus.sqlite").exists()


def test_us_market_news_is_registered_before_premarket_brief() -> None:
    from phase0.maintenance_orchestrator import _default_registry

    specs = _default_registry(Path("config.yaml"))
    by_name = {item.name: item for item in specs}
    names = [item.name for item in specs]
    task = by_name["us_market_news"]

    assert names.index("us_market_news") < names.index("daily_brief")
    assert task.schedule_value == "06:30"
    assert task.market_calendar == "all"
    assert task.command[task.command.index("--provider") + 1] == "us-market-news"
