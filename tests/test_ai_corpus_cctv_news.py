from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

import phase0.cli_commands.ai_corpus as ai_corpus_cli
import phase0.ai_corpus.providers.cctv_news as cctv_news_provider
from phase0.ai_corpus import (
    fetch_ai_corpus,
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


def test_parse_cctv_content_page_prefers_nonempty_video_brief_over_empty_content_area() -> None:
    html = """
    <html>
      <head>
        <meta property="og:title" content="《新闻联播》 20260703 19:00">
        <meta name="description" content="meta summary">
      </head>
      <body>
        <div id="content_area"></div>
        <div class="video_brief">节目概要正文</div>
      </body>
    </html>
    """

    parsed = parse_cctv_content_page(html, url="https://tv.cctv.com/example.shtml")

    assert "video_brief" in parsed["content_html"]
    assert parsed["raw_text"] == "节目概要正文"


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


def test_fetch_cctv_news_live_fetches_day_and_content(monkeypatch, tmp_path: Path) -> None:
    day_html = (FIXTURE_DIR / "day_20260703.html").read_text(encoding="utf-8")
    full_html = (FIXTURE_DIR / "VIDEcTNEq7lYlINRUm5tZqrU260703.html").read_text(encoding="utf-8")
    segment_html = (FIXTURE_DIR / "VIDEZQQue6pdTmCNLV8OhN4c260703.html").read_text(encoding="utf-8")
    seen_urls: list[str] = []

    def fake_fetch_live_text(url: str, *, timeout: int) -> str:
        seen_urls.append(url)
        if url.endswith("/day/20260703.shtml"):
            return day_html
        if url.endswith("VIDEcTNEq7lYlINRUm5tZqrU260703.shtml"):
            return full_html
        if url.endswith("VIDEZQQue6pdTmCNLV8OhN4c260703.shtml"):
            return segment_html
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(cctv_news_provider, "_fetch_live_text", fake_fetch_live_text)

    frame = fetch_cctv_news(
        root=tmp_path,
        date="20260703",
        include_segments=True,
        raw_archive_dir="raw/cctv",
        limit=20,
    )

    assert len(frame) == 2
    assert seen_urls[0] == "https://tv.cctv.com/lm/xwlb/day/20260703.shtml"
    assert {row["event_type"] for row in frame.to_dict(orient="records")} == {"cctv_news_full", "cctv_news_segment"}
    assert all((tmp_path / raw_path).exists() for raw_path in frame["raw_path"])


def test_fetch_cctv_news_live_marks_content_failures(monkeypatch, tmp_path: Path) -> None:
    day_html = (FIXTURE_DIR / "day_20260703.html").read_text(encoding="utf-8")

    def fake_fetch_live_text(url: str, *, timeout: int) -> str:
        if url.endswith("/day/20260703.shtml"):
            return day_html
        raise RuntimeError("fixture failure")

    monkeypatch.setattr(cctv_news_provider, "_fetch_live_text", fake_fetch_live_text)

    frame = fetch_cctv_news(
        root=tmp_path,
        date="20260703",
        include_segments=False,
        raw_archive_dir="raw/cctv",
        limit=1,
    )

    assert len(frame) == 1
    row = frame.iloc[0].to_dict()
    assert row["parse_status"] == "failed"
    assert "fixture failure" in row["raw_text"]
    assert (tmp_path / row["raw_path"]).exists()


def test_fetch_ai_corpus_cctv_accepts_date_range(monkeypatch, tmp_path: Path) -> None:
    seen_dates: list[str] = []

    def fake_fetch_cctv_news(**kwargs):
        seen_dates.append(kwargs["date"])
        return pd.DataFrame(
            [
                {
                    "document_id": f"doc-{kwargs['date']}",
                    "provider": "cctv",
                    "corpus_type": "cctv_news",
                    "event_type": "cctv_news_full",
                    "published_at": f"{kwargs['date'][:4]}-{kwargs['date'][4:6]}-{kwargs['date'][6:8]}",
                    "title": f"《新闻联播》 {kwargs['date']} 19:00",
                }
            ]
        )

    monkeypatch.setattr("phase0.ai_corpus.api.fetch_cctv_news", fake_fetch_cctv_news)

    frame = fetch_ai_corpus(
        provider="cctv-news",
        root=tmp_path,
        start_date="2026-07-03",
        end_date="20260705",
        limit=10,
    )

    assert seen_dates == ["20260703", "20260704", "20260705"]
    assert list(frame["published_at"]) == ["2026-07-03", "2026-07-04", "2026-07-05"]


def test_fetch_live_text_prefers_apparent_utf8_when_server_defaults_latin1(monkeypatch) -> None:
    class FakeResponse:
        encoding = "ISO-8859-1"
        apparent_encoding = "utf-8"
        content = "新闻联播".encode("utf-8")

        def raise_for_status(self) -> None:
            return None

        @property
        def text(self) -> str:
            return self.content.decode(self.encoding)

    def fake_get(url: str, **kwargs) -> FakeResponse:
        return FakeResponse()

    monkeypatch.setattr(cctv_news_provider.requests, "get", fake_get)

    assert cctv_news_provider._fetch_live_text("https://tv.cctv.com/example.shtml", timeout=1) == "新闻联播"


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
            date=None,
            start_date=None,
            end_date="20260703",
            limit=20,
            min_rows=0,
            fields="published_at,title,event_type,provider,source_id,url",
            fixture_dir=str(Path.cwd() / FIXTURE_DIR),
            database_path=None,
            raw_archive_dir=None,
            output_csv=str(output_csv),
            no_content=False,
            full_program_only=False,
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


def test_ai_corpus_fetch_cli_accepts_cctv_live_provider_without_fixture(monkeypatch, tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    output_csv = tmp_path / "out/cctv_live.csv"
    captured: dict[str, object] = {}

    def fake_fetch_ai_corpus(**kwargs):
        captured.update(kwargs)
        return pd.DataFrame(
            [
                {
                    "document_id": "doc-1",
                    "corpus_type": "cctv_news",
                    "event_type": "cctv_news_full",
                    "provider": "cctv",
                    "source": "央视网新闻联播",
                    "source_id": "VIDE1",
                    "published_at": "2026-07-03",
                    "issued_at": "",
                    "ingested_at": "2026-07-04T00:00:00",
                    "as_of_time": "2026-07-04T00:00:00",
                    "title": "《新闻联播》 20260703 19:00",
                    "summary": "",
                    "content_html": "<p>content</p>",
                    "raw_text": "content",
                    "url": "https://tv.cctv.com/example.shtml",
                    "org": "央视网",
                    "pcode": "",
                    "ptype": "新闻联播\\完整版",
                    "symbols": "",
                    "industries": "",
                    "topics": "新闻联播\\完整版",
                    "language": "zh-CN",
                    "dedupe_key": "doc-1",
                    "content_hash": "hash-1",
                    "raw_path": "raw/cctv/content.html",
                    "parse_status": "ok",
                    "source_confidence": "official_public_source",
                    "parser_version": "cctv_news_v1",
                }
            ]
        )

    monkeypatch.setattr(ai_corpus_cli, "fetch_ai_corpus", fake_fetch_ai_corpus)

    exit_code = handle_ai_corpus_command(
        argparse.Namespace(
            cmd="ai-corpus",
            ai_corpus_cmd="fetch",
            config=str(config_path),
            provider="cctv-news",
            org=None,
            ptype=None,
            keyword=None,
            date="20260703",
            start_date=None,
            end_date=None,
            limit=20,
            min_rows=1,
            fields="published_at,title,event_type,provider,source_id,url",
            fixture_dir=None,
            database_path=None,
            raw_archive_dir=None,
            output_csv=str(output_csv),
            no_content=False,
            full_program_only=True,
        ),
        parser=argparse.ArgumentParser(),
    )

    assert exit_code == 0
    assert captured["provider"] == "cctv"
    assert captured["start_date"] == "20260703"
    assert captured["end_date"] == "20260703"
    assert captured["include_segments"] is False
    assert "《新闻联播》 20260703 19:00" in output_csv.read_text(encoding="utf-8-sig")


def test_ai_corpus_fetch_cli_fails_when_cctv_rows_below_minimum(monkeypatch, tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)

    def fake_fetch_ai_corpus(**kwargs):
        return pd.DataFrame()

    monkeypatch.setattr(ai_corpus_cli, "fetch_ai_corpus", fake_fetch_ai_corpus)

    exit_code = handle_ai_corpus_command(
        argparse.Namespace(
            cmd="ai-corpus",
            ai_corpus_cmd="fetch",
            config=str(config_path),
            provider="cctv-news",
            org=None,
            ptype=None,
            keyword=None,
            date="20260703",
            start_date=None,
            end_date=None,
            limit=20,
            min_rows=1,
            fields=None,
            fixture_dir=None,
            database_path=None,
            raw_archive_dir=None,
            output_csv=None,
            no_content=False,
            full_program_only=False,
        ),
        parser=argparse.ArgumentParser(),
    )

    assert exit_code == 2
    assert not (tmp_path / "data/ai_corpus/ai_corpus.sqlite").exists()
