from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from phase0.ai_corpus import (
    AI_CORPUS_DOCUMENT_COLUMNS,
    build_gov_policy_params,
    fetch_national_policy_repository,
    npr,
    parse_gov_policy_content,
    query_ai_corpus_documents,
    upsert_ai_corpus_documents,
)
from phase0.ai_corpus.providers import gov_policy
from phase0.cli_commands.ai_corpus import handle_ai_corpus_command


FIXTURE_DIR = Path("tests/fixtures/ai_corpus/gov_policy")


def _write_config(root: Path) -> Path:
    config_path = root / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "phase0:",
                "  ai_corpus:",
                "    database_path: data/ai_corpus/ai_corpus.sqlite",
                "    raw_archive_dir: data/raw_data/ai_corpus/gov_policy",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return config_path


def test_gov_policy_params_map_org_topic_and_dates() -> None:
    params = build_gov_policy_params(
        org="国务院",
        ptype="科技",
        keyword="人工智能",
        end_date="2025-08-26 17:00:00",
        page=0,
        page_size=20,
    )

    assert params["t"] == "zhengcelibrary_gw"
    assert params["puborg"] == "国务院"
    assert params["subchildtype"] == "2220"
    assert params["q"] == "人工智能"
    assert params["timetype"] == "timezd"
    assert params["maxtime"] == "2025-08-26"

    department = build_gov_policy_params(org="工业和信息化部", keyword="人工智能", collection="department")

    assert department["t"] == "zhengcelibrary_bm"
    assert department["bmfl"] == "工业和信息化部"


def test_npr_fixture_returns_ai_plus_policy_with_content_audit(tmp_path: Path) -> None:
    frame = npr(
        root=tmp_path,
        fixture_dir=Path.cwd() / FIXTURE_DIR,
        raw_archive_dir="raw/gov_policy",
        org="国务院",
        ptype="科技",
        end_date="2025-08-26 17:00:00",
        fields="pubtime,title,pcode,puborg,ptype,url,content_html,raw_path,content_hash,parser_version,as_of_time,published_at,issued_at",
        limit=20,
    )

    assert len(frame) == 1
    row = frame.iloc[0].to_dict()
    assert row["title"] == "国务院关于深入实施“人工智能+”行动的意见"
    assert row["pcode"] == "国发〔2025〕11号"
    assert row["puborg"] == "国务院"
    assert row["ptype"] == "科技、教育\\科技"
    assert row["url"] == "https://www.gov.cn/zhengce/zhengceku/202508/content_7037862.htm"
    assert "UCAP-CONTENT" in row["content_html"]
    assert row["content_hash"]
    assert row["parser_version"] == "gov_policy_v1"
    assert row["published_at"] == "2025-08-26"
    assert row["issued_at"] == "2025-08-20"
    assert row["as_of_time"] != row["published_at"]
    assert (tmp_path / row["raw_path"]).exists()


def test_gov_policy_parser_extracts_metadata_content_and_dates() -> None:
    html = (FIXTURE_DIR / "content_7037862.html").read_text(encoding="utf-8")

    parsed = parse_gov_policy_content(html, url="https://www.gov.cn/zhengce/zhengceku/202508/content_7037862.htm")

    assert parsed["title"] == "国务院关于深入实施“人工智能+”行动的意见"
    assert parsed["published_at"] == "2025-08-26"
    assert parsed["issued_at"] == "2025-08-20"
    assert parsed["pcode"] == "国发〔2025〕11号"
    assert parsed["puborg"] == "国务院"
    assert parsed["ptype"] == "科技、教育\\科技"
    assert "人工智能+" in parsed["raw_text"]
    assert parsed["content_html"].startswith('<div id="UCAP-CONTENT">')


def test_gov_policy_storage_upsert_deduplicates_documents(tmp_path: Path) -> None:
    frame = fetch_national_policy_repository(
        root=tmp_path,
        fixture_dir=Path.cwd() / FIXTURE_DIR,
        raw_archive_dir="raw/gov_policy",
        org="国务院",
        ptype="科技",
        limit=20,
    )
    db_path = tmp_path / "data/ai_corpus/ai_corpus.sqlite"

    first = upsert_ai_corpus_documents(db_path, frame.to_dict(orient="records"))
    second = upsert_ai_corpus_documents(db_path, frame.to_dict(orient="records"))

    assert first >= 1
    assert second >= 1
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM ai_corpus_documents").fetchone()[0]
    assert count == 1
    rows = query_ai_corpus_documents(db_path, provider="gov_policy", keyword="人工智能", limit=10)
    assert len(rows) == 1
    assert rows[0]["document_id"].startswith("gov_policy:")
    assert set(AI_CORPUS_DOCUMENT_COLUMNS).issubset(rows[0].keys())


def test_gov_policy_live_fetch_paginates_and_records_content_failures(monkeypatch, tmp_path: Path) -> None:
    seen_pages: list[str] = []

    def fake_search(*, params, timeout):
        seen_pages.append(params["p"])
        if params["p"] == "0":
            rows = [
                {
                    "title": f"政策{i}",
                    "url": f"https://www.gov.cn/{i}.htm",
                    "puborg": "国务院",
                    "pubtime": "2026-01-01",
                    "id": str(i),
                }
                for i in range(50)
            ]
            rows[2]["url"] = "https://www.gov.cn/two.htm"
            rows[2]["id"] = "two"
            return json.dumps({"data": {"list": rows}}, ensure_ascii=False)
        return '{"data":{"list":[]}}'

    def fake_content(url: str, *, timeout: int):
        if url.endswith("two.htm"):
            raise RuntimeError("fixture failure")
        return (FIXTURE_DIR / "content_7037862.html").read_text(encoding="utf-8")

    monkeypatch.setattr(gov_policy, "_fetch_live_search", fake_search)
    monkeypatch.setattr(gov_policy, "_fetch_live_content", fake_content)

    frame = fetch_national_policy_repository(
        root=tmp_path,
        raw_archive_dir="raw/gov_policy",
        org="国务院",
        limit=51,
        timeout=1,
    )

    assert seen_pages == ["0", "1"]
    assert len(frame) == 50
    failed = frame[frame["source_id"] == "two"].iloc[0].to_dict()
    assert failed["parse_status"] == "failed"
    assert "fixture failure" in failed["raw_text"]


def test_ai_corpus_fetch_cli_uses_fixture_and_writes_database(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    output_csv = tmp_path / "out/policies.csv"

    exit_code = handle_ai_corpus_command(
        argparse.Namespace(
            cmd="ai-corpus",
            ai_corpus_cmd="fetch",
            config=str(config_path),
            provider="gov-policy",
            org="国务院",
            ptype="科技",
            keyword=None,
            start_date=None,
            end_date="2025-08-26 17:00:00",
            limit=20,
            fields="pubtime,title,pcode,puborg,ptype,url",
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
    assert "国务院关于深入实施“人工智能+”行动的意见" in output_csv.read_text(encoding="utf-8-sig")
    db_path = tmp_path / "data/ai_corpus/ai_corpus.sqlite"
    rows = query_ai_corpus_documents(db_path, provider="gov_policy", keyword="人工智能", limit=10)
    assert len(rows) == 1
