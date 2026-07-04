from __future__ import annotations

import argparse
from pathlib import Path

from phase0.ai_corpus import (
    fetch_cctv_news,
    parse_cctv_content_page,
    parse_cctv_day_page,
    query_ai_corpus_documents,
)
from phase0.cli_commands.ai_corpus import handle_ai_corpus_command


FIXTURE_DIR = Path("tests/fixtures/ai_corpus/cctv_news")


def _write_config(root: Path) -> Path:
    config_path = root / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "phase0:",
                "  ai_corpus:",
                "    database_path: data/ai_corpus/ai_corpus.sqlite",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return config_path


def test_parse_cctv_day_page_extracts_full_program_and_segment() -> None:
    html = (FIXTURE_DIR / "day_20260703.html").read_text(encoding="utf-8")

    rows = parse_cctv_day_page(html, date="20260703")

    assert len(rows) == 2
    assert rows[0]["source_id"] == "VIDEcTNEq7lYlINRUm5tZqrU260703"
    assert rows[0]["title"] == "《新闻联播》 20260703 19:00"
    assert rows[0]["published_at"] == "2026-07-03"
    assert rows[0]["duration"] == "00:30:02"
    assert rows[0]["item_type"] == "full_program"
    assert rows[1]["item_type"] == "segment"
    assert "晋升上将军衔仪式" in rows[1]["title"]


def test_parse_cctv_content_page_extracts_metadata_and_content() -> None:
    html = (FIXTURE_DIR / "VIDEZQQue6pdTmCNLV8OhN4c260703.html").read_text(encoding="utf-8")

    parsed = parse_cctv_content_page(
        html,
        url="https://tv.cctv.com/2026/07/03/VIDEZQQue6pdTmCNLV8OhN4c260703.shtml",
    )

    assert parsed["source_id"] == "VIDEZQQue6pdTmCNLV8OhN4c260703"
    assert "晋升上将军衔仪式" in parsed["title"]
    assert "content_area" in parsed["content_html"]
    assert "央视网消息" in parsed["raw_text"]
    assert parsed["guid"] == "6feca9a704944cfbbb7b4ec3e9773458"


def test_fetch_cctv_news_fixture_outputs_full_and_segment_documents(tmp_path: Path) -> None:
    frame = fetch_cctv_news(
        root=tmp_path,
        date="20260703",
        include_segments=True,
        fixture_dir=Path.cwd() / FIXTURE_DIR,
        raw_archive_dir="raw/cctv",
        limit=20,
    )

    assert len(frame) == 2
    full = frame[frame["event_type"] == "cctv_news_full"].iloc[0].to_dict()
    segment = frame[frame["event_type"] == "cctv_news_segment"].iloc[0].to_dict()
    assert full["title"] == "《新闻联播》 20260703 19:00"
    assert full["provider"] == "cctv"
    assert full["corpus_type"] == "cctv_news"
    assert full["published_at"] == "2026-07-03"
    assert full["parser_version"] == "cctv_news_v1"
    assert full["parse_status"] == "ok"
    assert "video_brief" in full["content_html"]
    assert "晋升上将军衔仪式" in segment["title"]
    assert "content_area" in segment["content_html"]
    assert (tmp_path / segment["raw_path"]).exists()


def test_fetch_cctv_news_fixture_can_exclude_segments(tmp_path: Path) -> None:
    frame = fetch_cctv_news(
        root=tmp_path,
        date="20260703",
        include_segments=False,
        fixture_dir=Path.cwd() / FIXTURE_DIR,
        raw_archive_dir="raw/cctv",
        limit=20,
    )

    assert len(frame) == 1
    assert frame.iloc[0]["event_type"] == "cctv_news_full"


def test_ai_corpus_fetch_cli_accepts_cctv_fixture_provider(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    output_csv = tmp_path / "out/cctv.csv"

    exit_code = handle_ai_corpus_command(
        argparse.Namespace(
            cmd="ai-corpus",
            ai_corpus_cmd="fetch",
            config=str(config_path),
            provider="cctv-news",
            org=None,
            ptype=None,
            keyword=None,
            start_date=None,
            end_date="20260703",
            limit=20,
            fields="published_at,title,event_type,provider,source_id,url",
            fixture_dir=str(Path.cwd() / FIXTURE_DIR),
            database_path=None,
            raw_archive_dir=None,
            output_csv=str(output_csv),
            no_content=False,
        ),
        parser=argparse.ArgumentParser(),
    )

    assert exit_code == 0
    assert output_csv.read_bytes().startswith(b"\xef\xbb\xbf")
    csv_text = output_csv.read_text(encoding="utf-8-sig")
    assert "《新闻联播》 20260703 19:00" in csv_text
    assert "cctv_news_segment" in csv_text
    rows = query_ai_corpus_documents(tmp_path / "data/ai_corpus/ai_corpus.sqlite", provider="cctv", limit=10)
    assert len(rows) == 2
    assert {row["event_type"] for row in rows} == {"cctv_news_full", "cctv_news_segment"}
