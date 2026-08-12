from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

import quant.ai_corpus.api as ai_corpus_api
import quant.cli_commands.ai_corpus as ai_corpus_cli
from quant.ai_corpus import (
    AI_CORPUS_DOCUMENT_COLUMNS,
    audit_gov_policy_probe_report,
    build_gov_policy_params,
    fetch_ai_corpus,
    fetch_national_policy_repository,
    load_gov_policy_references,
    npr,
    parse_gov_policy_department_reference,
    parse_gov_policy_content,
    probe_gov_policy_source,
    query_ai_corpus_documents,
    upsert_ai_corpus_documents,
)
from quant.ai_corpus.providers import gov_policy
from quant.cli_commands.ai_corpus import handle_ai_corpus_command


FIXTURE_DIR = Path("tests/fixtures/ai_corpus/gov_policy")


DEPARTMENT_REFERENCE_JSON = json.dumps(
    {
        "data": [
            {"id": "3268", "name": "科学技术部"},
            {"id": "3273", "name": "工业和信息化部"},
        ]
    },
    ensure_ascii=False,
)


TOPIC_REFERENCE_JSON = json.dumps(
    {
        "searchVO": {
            "ztflTree": [
                {
                    "id": "1088",
                    "name": "科技、教育",
                    "children": [
                        {"id": "2220", "name": "科技"},
                        {"id": "2221", "name": "教育"},
                    ],
                }
            ]
        }
    },
    ensure_ascii=False,
)


def _write_config(root: Path) -> Path:
    config_path = root / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "quant:",
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


def test_gov_policy_reference_parsers_map_departments_and_topics() -> None:
    departments = parse_gov_policy_department_reference(DEPARTMENT_REFERENCE_JSON)
    topics = gov_policy.parse_gov_policy_topic_reference(TOPIC_REFERENCE_JSON)

    assert departments == ["工业和信息化部", "科学技术部"]
    assert topics["科技、教育"]["childtype"] == "1088"
    assert topics["科技"]["subchildtype"] == "2220"
    assert topics["科技"]["ptype_label"] == "科技、教育\\科技"


def test_gov_policy_params_validate_department_when_reference_available() -> None:
    params = build_gov_policy_params(
        org="工业和信息化部",
        keyword="人工智能",
        department_names={"工业和信息化部"},
    )

    assert params["t"] == "zhengcelibrary_bm"
    assert params["bmfl"] == "工业和信息化部"
    with pytest.raises(ValueError, match="unsupported gov.cn department org"):
        build_gov_policy_params(org="不存在的部门", department_names={"工业和信息化部"})


def test_load_gov_policy_references_fetches_and_caches(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    def fake_request(url: str, *, params=None, timeout: int):
        calls.append(url)
        assert timeout == 9
        return DEPARTMENT_REFERENCE_JSON

    def fake_search(*, params, timeout: int):
        calls.append("topic")
        assert timeout == 9
        return TOPIC_REFERENCE_JSON

    monkeypatch.setattr(gov_policy, "_request_gov_policy_text", fake_request)
    monkeypatch.setattr(gov_policy, "_fetch_live_search", fake_search)

    departments, topics = load_gov_policy_references(
        root=tmp_path,
        reference_dir="refs/gov_policy",
        timeout=9,
        ingested_at="2026-07-08T00:00:00+08:00",
    )

    assert calls == [gov_policy.GOV_DEPARTMENT_URL, "topic"]
    assert departments == {"工业和信息化部", "科学技术部"}
    assert topics["科技"]["subchildtype"] == "2220"
    assert (tmp_path / "refs/gov_policy/departments.json").exists()
    assert (tmp_path / "refs/gov_policy/topics.json").exists()

    calls.clear()
    cached_departments, cached_topics = load_gov_policy_references(
        root=tmp_path,
        reference_dir="refs/gov_policy",
        timeout=9,
    )
    assert calls == []
    assert cached_departments == departments
    assert cached_topics["科技"]["subchildtype"] == "2220"


def test_gov_policy_params_reject_reverse_date_range() -> None:
    with pytest.raises(ValueError, match="start_date must be <= end_date"):
        build_gov_policy_params(start_date="2026-01-02", end_date="2026-01-01")


def test_gov_policy_live_request_retries_transient_status(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class FakeResponse:
        def __init__(self, *, status_code: int, text: str, url: str) -> None:
            self.status_code = status_code
            self.text = text
            self.url = url
            self.encoding = None
            self.apparent_encoding = "utf-8"

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise gov_policy.requests.HTTPError(f"HTTP {self.status_code}")

    def fake_get(url: str, *, params, timeout, headers):
        calls.append({"url": url, "params": params, "timeout": timeout, "headers": headers})
        if len(calls) == 1:
            return FakeResponse(status_code=503, text="", url=url)
        return FakeResponse(status_code=200, text='{"data":{"list":[]}}', url=url)

    monkeypatch.setattr(gov_policy.requests, "get", fake_get)
    monkeypatch.setattr(gov_policy.time, "sleep", lambda _: None)

    text = gov_policy._fetch_live_search(params={"p": "0"}, timeout=7)

    assert text == '{"data":{"list":[]}}'
    assert len(calls) == 2
    assert calls[0]["timeout"] == 7
    assert calls[0]["headers"]["Referer"].startswith("https://sousuo.www.gov.cn/")


def test_gov_policy_response_decodes_utf8_meta_before_response_text() -> None:
    class FakeResponse:
        status_code = 200
        url = "https://www.gov.cn/example.htm"
        encoding = "ISO-8859-1"
        apparent_encoding = "ISO-8859-1"
        headers = {}
        content = (
            '<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8" /></head>'
            "<body>中华人民共和国国务院</body></html>"
        ).encode("utf-8")
        text = content.decode("ISO-8859-1")

    decoded = gov_policy._decode_gov_policy_response(FakeResponse())

    assert "中华人民共和国国务院" in decoded
    assert "ä¸" not in decoded


def test_fetch_ai_corpus_passes_timeout_to_gov_policy(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_fetch_national_policy_repository(**kwargs):
        captured.update(kwargs)
        return pd.DataFrame()

    monkeypatch.setattr(ai_corpus_api, "fetch_national_policy_repository", fake_fetch_national_policy_repository)

    fetch_ai_corpus(provider="gov-policy", root=tmp_path, keyword="人工智能", limit=1, timeout=3)

    assert captured["timeout"] == 3


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


def test_gov_policy_live_list_cleans_markup_and_dot_dates(monkeypatch, tmp_path: Path) -> None:
    def fake_search(*, params, timeout):
        rows = [
            {
                "title": "国务院关于深入实施“<em>人工智能</em>+”行动的意见",
                "url": "https://www.gov.cn/zhengce/zhengceku/202508/content_7037862.htm",
                "puborg": "国务院",
                "pubtime": "2025.08.26",
                "summary": "加快推进<em>人工智能</em>发展",
                "id": "7037862",
            }
        ]
        return json.dumps({"data": {"list": rows}}, ensure_ascii=False)

    monkeypatch.setattr(gov_policy, "_fetch_live_search", fake_search)

    frame = fetch_national_policy_repository(
        root=tmp_path,
        raw_archive_dir="raw/gov_policy",
        include_content=False,
        limit=1,
        timeout=1,
    )

    row = frame.iloc[0].to_dict()
    assert row["published_at"] == "2025-08-26"
    assert row["title"] == "国务院关于深入实施“人工智能+”行动的意见"
    assert row["summary"] == "加快推进人工智能发展"


def test_gov_policy_live_fetch_uses_dynamic_topic_label(monkeypatch, tmp_path: Path) -> None:
    def fake_references(**kwargs):
        return {"国务院"}, {"产业": {"subchildtype": "9999", "ptype_label": "产业发展\\产业"}}

    def fake_search(*, params, timeout):
        assert params["subchildtype"] == "9999"
        rows = [
            {
                "title": "关于促进产业人工智能应用的意见",
                "url": "https://www.gov.cn/zhengce/content_9000000.htm",
                "puborg": "国务院",
                "pubtime": "2026-01-01",
                "summary": "人工智能应用",
                "id": "9000000",
            }
        ]
        return json.dumps({"data": {"list": rows}}, ensure_ascii=False)

    monkeypatch.setattr(gov_policy, "load_gov_policy_references", fake_references)
    monkeypatch.setattr(gov_policy, "_fetch_live_search", fake_search)

    frame = fetch_national_policy_repository(
        root=tmp_path,
        raw_archive_dir="raw/gov_policy",
        org="国务院",
        ptype="产业",
        include_content=False,
        limit=1,
        timeout=1,
    )

    row = frame.iloc[0].to_dict()
    assert row["ptype"] == "产业发展\\产业"
    assert row["topics"] == "产业发展\\产业"


def test_probe_gov_policy_source_reports_reference_search_and_content(monkeypatch, tmp_path: Path) -> None:
    def fake_references(**kwargs):
        return {"国务院"}, {"科技": {"subchildtype": "2220", "ptype_label": "科技、教育\\科技"}}

    def fake_search(*, params, timeout):
        assert params["subchildtype"] == "2220"
        rows = [
            {
                "title": "国务院关于深入实施“<em>人工智能</em>+”行动的意见",
                "url": "https://www.gov.cn/zhengce/zhengceku/202508/content_7037862.htm",
                "puborg": "国务院",
                "pubtime": "2025.08.26",
                "pcode": "国发〔2025〕11号",
                "id": "7037862",
            }
        ]
        return json.dumps(
            {
                "code": 200,
                "searchVO": {
                    "ztflTree": [
                        {
                            "id": "1088",
                            "name": "科技、教育",
                            "children": [{"id": "2220", "name": "科技"}],
                        }
                    ],
                    "catMap": {"gongwen": {"listVO": rows}},
                },
            },
            ensure_ascii=False,
        )

    def fake_content(url: str, *, timeout: int):
        return (FIXTURE_DIR / "content_7037862.html").read_text(encoding="utf-8")

    monkeypatch.setattr(gov_policy, "load_gov_policy_references", fake_references)
    monkeypatch.setattr(gov_policy, "_fetch_live_search", fake_search)
    monkeypatch.setattr(gov_policy, "_fetch_live_content", fake_content)

    report = probe_gov_policy_source(
        root=tmp_path,
        reference_dir="refs/gov_policy",
        timeout=1,
        min_content_raw_text_length=20,
    )

    assert report["ok"] is True
    assert report["reference"]["effective_topic_count"] == 1
    assert report["reference"]["matched_topic"]["subchildtype"] == "2220"
    assert report["search"]["row_count"] == 1
    assert report["search"]["has_topic_tree"] is True
    assert report["search"]["sample_titles"] == ["国务院关于深入实施“人工智能+”行动的意见"]
    assert report["content"]["ok"] is True
    assert report["content"]["published_at"] == "2025-08-26"
    assert report["audit"]["ok"] is True
    assert {item["name"] for item in report["audit"]["checks"]} >= {
        "search_required_fields",
        "search_date_field",
        "content_html_present",
    }
    assert report["errors"] == []


def test_audit_gov_policy_probe_report_flags_structure_drift() -> None:
    report = {
        "query": {"ptype": "科技"},
        "reference": {
            "effective_topic_count": 1,
            "effective_department_count": 0,
            "matched_topic": {"subchildtype": "2220"},
        },
        "search": {
            "ok": True,
            "row_count": 1,
            "has_topic_tree": False,
            "topic_tree_count": 0,
            "field_keys": ["title"],
            "response_keys": ["searchVO"],
        },
        "content": {"ok": True, "content_html_present": False, "raw_text_length": 10},
    }

    audit = audit_gov_policy_probe_report(report, min_content_raw_text_length=200)

    failed = {item["name"]: item["status"] for item in audit["checks"] if item["status"] == "error"}
    assert audit["ok"] is False
    assert failed["search_required_fields"] == "error"
    assert failed["search_date_field"] == "error"
    assert failed["search_topic_tree"] == "error"
    assert failed["content_html_present"] == "error"
    assert failed["content_raw_text_length"] == "error"


def test_ai_corpus_probe_cli_writes_json_report(monkeypatch, tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    output_json = tmp_path / "probe/gov_policy.json"
    captured: dict[str, object] = {}

    def fake_probe_gov_policy_source(**kwargs):
        captured.update(kwargs)
        return {
            "provider": "gov_policy",
            "ok": True,
            "search": {"row_count": 1},
            "content": {"ok": True},
            "errors": [],
        }

    monkeypatch.setattr(ai_corpus_cli, "probe_gov_policy_source", fake_probe_gov_policy_source)

    exit_code = handle_ai_corpus_command(
        argparse.Namespace(
            cmd="ai-corpus",
            ai_corpus_cmd="probe",
            config=str(config_path),
            provider="gov-policy",
            collection="department",
            org="国务院",
            ptype="科技",
            keyword="人工智能",
            start_date=None,
            end_date=None,
            reference_dir=None,
            refresh_reference=False,
            timeout=1,
            no_content=False,
            output_json=str(output_json),
            min_probe_rows=2,
            min_probe_topics=3,
            min_probe_departments=4,
            min_probe_content_chars=5,
            require_topic_tree=False,
            require_content_html=False,
        ),
        parser=argparse.ArgumentParser(),
    )

    assert exit_code == 0
    assert captured["collection"] == "department"
    assert captured["timeout"] == 1
    assert captured["min_rows"] == 2
    assert captured["min_topic_count"] == 3
    assert captured["min_department_count"] == 4
    assert captured["min_content_raw_text_length"] == 5
    assert captured["require_topic_tree"] is False
    assert captured["require_content_html"] is False
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["search"]["row_count"] == 1


def test_ai_corpus_fetch_cli_probe_before_fetch_blocks_failed_probe(monkeypatch, tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    output_json = tmp_path / "probe/failed.json"
    fetch_called = False

    def fake_probe_gov_policy_source(**kwargs):
        return {
            "provider": "gov_policy",
            "ok": False,
            "search": {"row_count": 0},
            "content": {"ok": False},
            "errors": ["no search rows available for content probe"],
        }

    def fake_fetch_ai_corpus(**kwargs):
        nonlocal fetch_called
        fetch_called = True
        return pd.DataFrame()

    monkeypatch.setattr(ai_corpus_cli, "probe_gov_policy_source", fake_probe_gov_policy_source)
    monkeypatch.setattr(ai_corpus_cli, "fetch_ai_corpus", fake_fetch_ai_corpus)

    exit_code = handle_ai_corpus_command(
        argparse.Namespace(
            cmd="ai-corpus",
            ai_corpus_cmd="fetch",
            config=str(config_path),
            provider="gov-policy",
            org="国务院",
            ptype="科技",
            keyword="人工智能",
            date=None,
            start_date=None,
            end_date=None,
            limit=20,
            min_rows=1,
            timeout=1,
            fields=None,
            fixture_dir=None,
            database_path=None,
            raw_archive_dir=None,
            reference_dir=None,
            refresh_reference=True,
            output_csv=None,
            no_content=False,
            full_program_only=False,
            probe_before_fetch=True,
            probe_output_json=str(output_json),
            probe_no_content=False,
        ),
        parser=argparse.ArgumentParser(),
    )

    assert exit_code == 2
    assert fetch_called is False
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert payload["errors"] == ["no search rows available for content probe"]


def test_ai_corpus_fetch_cli_probe_before_fetch_blocks_audit_failure(monkeypatch, tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    output_json = tmp_path / "probe/audit_failed.json"
    fetch_called = False

    def fake_probe_gov_policy_source(**kwargs):
        return {
            "provider": "gov_policy",
            "ok": True,
            "search": {"row_count": 1},
            "content": {"ok": True},
            "audit": {
                "ok": False,
                "error_count": 1,
                "warning_count": 0,
                "checks": [{"name": "search_required_fields", "status": "error"}],
            },
            "errors": [],
        }

    def fake_fetch_ai_corpus(**kwargs):
        nonlocal fetch_called
        fetch_called = True
        return pd.DataFrame()

    monkeypatch.setattr(ai_corpus_cli, "probe_gov_policy_source", fake_probe_gov_policy_source)
    monkeypatch.setattr(ai_corpus_cli, "fetch_ai_corpus", fake_fetch_ai_corpus)

    exit_code = handle_ai_corpus_command(
        argparse.Namespace(
            cmd="ai-corpus",
            ai_corpus_cmd="fetch",
            config=str(config_path),
            provider="gov-policy",
            org="国务院",
            ptype="科技",
            keyword="人工智能",
            date=None,
            start_date=None,
            end_date=None,
            limit=20,
            min_rows=1,
            timeout=1,
            fields=None,
            fixture_dir=None,
            database_path=None,
            raw_archive_dir=None,
            reference_dir=None,
            refresh_reference=True,
            output_csv=None,
            no_content=False,
            full_program_only=False,
            probe_before_fetch=True,
            probe_output_json=str(output_json),
            probe_no_content=False,
            min_probe_rows=1,
            min_probe_topics=1,
            min_probe_departments=0,
            min_probe_content_chars=200,
            require_topic_tree=True,
            require_content_html=True,
        ),
        parser=argparse.ArgumentParser(),
    )

    assert exit_code == 2
    assert fetch_called is False
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["audit"]["ok"] is False


def test_ai_corpus_fetch_cli_probe_before_fetch_avoids_double_reference_refresh(monkeypatch, tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    captured_fetch: dict[str, object] = {}

    def fake_probe_gov_policy_source(**kwargs):
        return {
            "provider": "gov_policy",
            "ok": True,
            "search": {"row_count": 1},
            "content": {"ok": True},
            "errors": [],
        }

    def fake_fetch_ai_corpus(**kwargs):
        captured_fetch.update(kwargs)
        return pd.DataFrame([{"published_at": "2025-08-26", "title": "ok"}])

    monkeypatch.setattr(ai_corpus_cli, "probe_gov_policy_source", fake_probe_gov_policy_source)
    monkeypatch.setattr(ai_corpus_cli, "fetch_ai_corpus", fake_fetch_ai_corpus)
    monkeypatch.setattr(ai_corpus_cli, "upsert_ai_corpus_documents", lambda db_path, rows: 1)

    exit_code = handle_ai_corpus_command(
        argparse.Namespace(
            cmd="ai-corpus",
            ai_corpus_cmd="fetch",
            config=str(config_path),
            provider="gov-policy",
            org="国务院",
            ptype="科技",
            keyword="人工智能",
            date=None,
            start_date=None,
            end_date=None,
            limit=20,
            min_rows=1,
            timeout=1,
            fields=None,
            fixture_dir=None,
            database_path=None,
            raw_archive_dir=None,
            reference_dir="refs/gov_policy",
            refresh_reference=True,
            output_csv=None,
            no_content=False,
            full_program_only=False,
            probe_before_fetch=True,
            probe_output_json=str(tmp_path / "probe/ok.json"),
            probe_no_content=False,
        ),
        parser=argparse.ArgumentParser(),
    )

    assert exit_code == 0
    assert captured_fetch["reference_dir"] == "refs/gov_policy"
    assert captured_fetch["refresh_reference"] is False


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
