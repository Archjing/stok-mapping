from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

from phase0.ai_corpus.registry import GOV_POLICY_PARSER_VERSION
from phase0.ai_corpus.schema import (
    AI_CORPUS_DOCUMENT_COLUMNS,
    content_sha256,
    now_iso,
    resolve_path,
    safe_text,
    select_fields,
    stable_dedupe_key,
    stable_document_id,
)

GOV_SEARCH_URL = "https://sousuo.www.gov.cn/search-gov/data"
GOV_DEPARTMENT_URL = "https://www.gov.cn/zhengce/bmzcfwjg.json"
GOV_POLICY_SOURCE = "中国政府网"
DEFAULT_RAW_ARCHIVE_DIR = "data/raw_data/ai_corpus/gov_policy"
DEFAULT_REFERENCE_DIR = "data/reference/ai_corpus/gov_policy"
DEFAULT_USER_AGENT = "stok-mapping-ai-corpus/1.0"
DEFAULT_HTTP_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 0.5
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
GOV_POLICY_REQUIRED_SEARCH_FIELDS = {"title", "url"}
GOV_POLICY_DATE_SEARCH_FIELDS = {"pubtime", "pubtimeStr"}
DEFAULT_PROBE_MIN_ROWS = 1
DEFAULT_PROBE_MIN_TOPIC_COUNT = 1
DEFAULT_PROBE_MIN_DEPARTMENT_COUNT = 0
DEFAULT_PROBE_MIN_CONTENT_RAW_TEXT_LENGTH = 200

STATE_COUNCIL_ORGS = {"国务院", "国务院办公厅"}
TOPIC_NAME_TO_PARAMS = {
    "科技": {"subchildtype": "2220", "ptype_label": "科技、教育\\科技"},
    "科技、教育": {"childtype": "1088", "ptype_label": "科技、教育"},
}


def _date_only(value: str | None) -> str:
    text = safe_text(value)
    if not text:
        return ""
    normalized = text.replace("/", "-").replace(".", "-").replace("T", " ")
    chinese = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", normalized)
    if chinese:
        return f"{int(chinese.group(1)):04d}-{int(chinese.group(2)):02d}-{int(chinese.group(3)):02d}"
    match = re.search(r"\d{4}-\d{1,2}-\d{1,2}", normalized)
    if match:
        parts = [int(part) for part in match.group(0).split("-")]
        return f"{parts[0]:04d}-{parts[1]:02d}-{parts[2]:02d}"
    if re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text


def _safe_stem(value: str) -> str:
    text = re.sub(r"[^0-9A-Za-z_.-]+", "_", value).strip("._")
    return text[:120] or "raw"


def _clean_html_text(value: Any) -> str:
    text = safe_text(value)
    if "<" in text and ">" in text:
        text = BeautifulSoup(text, "html.parser").get_text("", strip=True)
    return safe_text(text)


def _archive_path(*, archive_root: Path, kind: str, ingested_at: str, stem: str, suffix: str) -> Path:
    day = _date_only(ingested_at) or datetime.now().date().isoformat()
    year, month, date_part = day.split("-")
    return archive_root / kind / year / month / date_part / f"{_safe_stem(stem)}.{suffix}"


def _write_raw_text(*, archive_root: Path, kind: str, ingested_at: str, stem: str, suffix: str, text: str) -> Path:
    path = _archive_path(archive_root=archive_root, kind=kind, ingested_at=ingested_at, stem=stem, suffix=suffix)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_fixture_search(fixture_dir: Path) -> tuple[Path, str]:
    candidates = sorted(fixture_dir.glob("search*.json")) + sorted(fixture_dir.glob("*search*.json"))
    if not candidates:
        raise FileNotFoundError(f"gov policy fixture search JSON not found under {fixture_dir}")
    path = candidates[0]
    return path, path.read_text(encoding="utf-8")


def _content_fixture_path(fixture_dir: Path, row: dict[str, Any]) -> Path:
    source_id = safe_text(row.get("id") or row.get("source_id"))
    url = safe_text(row.get("url"))
    stems = []
    if source_id:
        stems.append(source_id)
    if url:
        stems.append(Path(urlparse(url).path).stem)
    stems.extend(["content_7037862", "content_7068153"])
    for stem in stems:
        for suffix in (".html", ".htm"):
            path = fixture_dir / f"{stem}{suffix}"
            if path.exists():
                return path
    raise FileNotFoundError(f"gov policy content fixture not found for {source_id or url}")


def parse_gov_policy_department_reference(text: str) -> list[str]:
    payload = json.loads(text)
    raw_items = payload.get("data", []) if isinstance(payload, dict) else payload
    if not isinstance(raw_items, list):
        raise ValueError("gov.cn department reference JSON must contain a list under data")
    names = sorted(
        {
            safe_text(item.get("name"))
            for item in raw_items
            if isinstance(item, dict) and safe_text(item.get("name"))
        }
    )
    if not names:
        raise ValueError("gov.cn department reference JSON did not contain any department names")
    return names


def _find_topic_tree(obj: Any) -> list[dict[str, Any]]:
    if isinstance(obj, dict):
        tree = obj.get("ztflTree")
        if isinstance(tree, list):
            return [item for item in tree if isinstance(item, dict)]
        for value in obj.values():
            nested = _find_topic_tree(value)
            if nested:
                return nested
    if isinstance(obj, list):
        for value in obj:
            nested = _find_topic_tree(value)
            if nested:
                return nested
    return []


def _topic_label(parent_name: str, child_name: str) -> str:
    return f"{parent_name}\\{child_name}"


def parse_gov_policy_topic_reference(text: str) -> dict[str, dict[str, str]]:
    payload = json.loads(text)
    topic_tree = _find_topic_tree(payload)
    if not topic_tree:
        raise ValueError("gov.cn search response did not contain searchVO.ztflTree")

    mapping: dict[str, dict[str, str]] = {}
    child_entries: list[tuple[str, str, str]] = []
    child_name_counts: dict[str, int] = {}

    for parent in topic_tree:
        parent_name = safe_text(parent.get("name"))
        parent_id = safe_text(parent.get("id"))
        if not parent_name or not parent_id:
            continue
        mapping[parent_name] = {"childtype": parent_id, "ptype_label": parent_name}
        for child in parent.get("children") or []:
            if not isinstance(child, dict):
                continue
            child_name = safe_text(child.get("name"))
            child_id = safe_text(child.get("id"))
            if not child_name or not child_id:
                continue
            label = _topic_label(parent_name, child_name)
            mapping[label] = {"subchildtype": child_id, "ptype_label": label}
            child_entries.append((child_name, child_id, label))
            child_name_counts[child_name] = child_name_counts.get(child_name, 0) + 1

    for child_name, child_id, label in child_entries:
        if child_name_counts.get(child_name) == 1:
            mapping[child_name] = {"subchildtype": child_id, "ptype_label": label}

    if not mapping:
        raise ValueError("gov.cn topic reference did not contain usable topic ids")
    return mapping


def _read_cached_department_names(reference_root: Path) -> set[str] | None:
    path = reference_root / "departments.json"
    if not path.exists():
        return None
    payload = _load_json(path)
    names = payload.get("department_names", []) if isinstance(payload, dict) else []
    normalized = {safe_text(name) for name in names if safe_text(name)}
    return normalized or None


def _read_cached_topic_params(reference_root: Path) -> dict[str, dict[str, str]] | None:
    path = reference_root / "topics.json"
    if not path.exists():
        return None
    payload = _load_json(path)
    topics = payload.get("topic_params", {}) if isinstance(payload, dict) else {}
    if not isinstance(topics, dict):
        return None
    normalized = {
        safe_text(name): {safe_text(key): safe_text(value) for key, value in params.items()}
        for name, params in topics.items()
        if safe_text(name) and isinstance(params, dict)
    }
    return normalized or None


def load_gov_policy_references(
    *,
    root: Path | None = None,
    reference_dir: str | Path = DEFAULT_REFERENCE_DIR,
    refresh: bool = False,
    timeout: int = 20,
    ingested_at: str | None = None,
) -> tuple[set[str] | None, dict[str, dict[str, str]]]:
    project_root = root or Path.cwd()
    reference_root = resolve_path(project_root, reference_dir)
    fetched_at = ingested_at or now_iso()

    department_names = None if refresh else _read_cached_department_names(reference_root)
    if department_names is None:
        try:
            department_text = _request_gov_policy_text(GOV_DEPARTMENT_URL, timeout=timeout)
            department_names = set(parse_gov_policy_department_reference(department_text))
            _write_json(
                reference_root / "departments.json",
                {
                    "fetched_at": fetched_at,
                    "source_url": GOV_DEPARTMENT_URL,
                    "department_names": sorted(department_names),
                },
            )
        except Exception:
            if refresh:
                raise
            department_names = None

    topic_params = None if refresh else _read_cached_topic_params(reference_root)
    if topic_params is None:
        try:
            topic_text = _fetch_live_search(
                params=build_gov_policy_params(keyword="", collection="all", page=0, page_size=1),
                timeout=timeout,
            )
            topic_params = parse_gov_policy_topic_reference(topic_text)
            _write_json(
                reference_root / "topics.json",
                {
                    "fetched_at": fetched_at,
                    "source_url": GOV_SEARCH_URL,
                    "topic_params": topic_params,
                },
            )
        except Exception:
            if refresh:
                raise
            topic_params = dict(TOPIC_NAME_TO_PARAMS)

    return department_names, topic_params


def build_gov_policy_params(
    *,
    org: str | None = None,
    ptype: str | None = None,
    keyword: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    collection: str = "all",
    page: int = 0,
    page_size: int = 20,
    department_names: set[str] | None = None,
    topic_params: dict[str, dict[str, str]] | None = None,
) -> dict[str, str]:
    params = {
        "q": safe_text(keyword),
        "t": "zhengcelibrary",
        "p": str(page),
        "n": str(page_size),
    }
    collection_map = {
        "all": "zhengcelibrary",
        "state_council": "zhengcelibrary_gw",
        "government": "zhengcelibrary_gw",
        "department": "zhengcelibrary_bm",
        "gazette": "zhengcelibrary_gb",
    }
    params["t"] = collection_map.get(collection, collection)
    org_text = safe_text(org)
    if org_text:
        if org_text in STATE_COUNCIL_ORGS:
            params["t"] = "zhengcelibrary_gw"
            params["puborg"] = org_text
        else:
            if department_names is not None and org_text not in department_names:
                sample = "、".join(sorted(department_names)[:12])
                raise ValueError(f"unsupported gov.cn department org: {org_text}; known examples: {sample}")
            params["t"] = "zhengcelibrary_bm"
            params["bmfl"] = org_text
    topic_text = safe_text(ptype)
    if topic_text:
        topic_reference = topic_params or TOPIC_NAME_TO_PARAMS
        topic_match = topic_reference.get(topic_text)
        if not topic_match:
            sample = "、".join(sorted(topic_reference)[:12])
            suffix = f"; known examples: {sample}" if sample else ""
            raise ValueError(f"unsupported gov.cn policy topic mapping: {ptype}{suffix}")
        for key in ("childtype", "subchildtype"):
            if key in topic_match:
                params[key] = topic_match[key]
    start = _date_only(start_date)
    end = _date_only(end_date)
    if start or end:
        if start and end and start > end:
            raise ValueError(f"gov.cn policy start_date must be <= end_date: {start} > {end}")
        params["timetype"] = "timezd"
        if start:
            params["mintime"] = start
        if end:
            params["maxtime"] = end
    return {key: value for key, value in params.items() if safe_text(value)}


def _looks_like_policy_item(item: Any) -> bool:
    return isinstance(item, dict) and bool(item.get("title")) and bool(item.get("url"))


def _find_policy_items(obj: Any) -> list[dict[str, Any]]:
    if isinstance(obj, list):
        direct = [item for item in obj if _looks_like_policy_item(item)]
        if direct:
            return direct
        for item in obj:
            nested = _find_policy_items(item)
            if nested:
                return nested
    if isinstance(obj, dict):
        for key in ("list", "result", "results", "items", "data", "docs", "searchList"):
            if key in obj:
                nested = _find_policy_items(obj[key])
                if nested:
                    return nested
        for value in obj.values():
            nested = _find_policy_items(value)
            if nested:
                return nested
    return []


def parse_gov_policy_list_response(text: str) -> list[dict[str, Any]]:
    payload = json.loads(text)
    return _find_policy_items(payload)


def _metadata_from_table(soup: BeautifulSoup) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for row in soup.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) < 2:
            continue
        key = cells[0].get_text(" ", strip=True).strip("：:")
        value = cells[1].get_text(" ", strip=True)
        if key and value:
            metadata[key] = value
    for key_node in soup.find_all(["dt", "span"]):
        key_text = key_node.get_text(" ", strip=True).strip("：:")
        if key_text in {"发文机关", "发文字号", "发布日期", "主题分类", "成文日期", "标题", "公文种类", "来源"}:
            next_node = key_node.find_next_sibling(["dd", "span", "p"])
            if next_node:
                metadata[key_text] = next_node.get_text(" ", strip=True)
    return metadata


def parse_gov_policy_content(html_text: str, *, url: str = "") -> dict[str, str]:
    soup = BeautifulSoup(html_text, "html.parser")
    metadata = _metadata_from_table(soup)
    meta_tags: dict[str, str] = {}
    for meta in soup.find_all("meta"):
        name = safe_text(meta.get("name") or meta.get("property")).lower()
        content = safe_text(meta.get("content"))
        if name and content:
            meta_tags[name] = content
    content_node = soup.find(id="UCAP-CONTENT") or soup.find(id="ucap-content") or soup.find(class_="pages_content")
    content_html = str(content_node).strip() if content_node else ""
    raw_text = content_node.get_text("\n", strip=True) if content_node else soup.get_text("\n", strip=True)
    title = metadata.get("标题") or meta_tags.get("article:title") or (soup.title.get_text(" ", strip=True) if soup.title else "")
    return {
        "title": safe_text(title),
        "published_at": _date_only(meta_tags.get("firstpublishedtime") or metadata.get("发布日期")),
        "issued_at": _date_only(metadata.get("成文日期")),
        "pcode": safe_text(metadata.get("发文字号")),
        "puborg": safe_text(metadata.get("发文机关") or metadata.get("来源")),
        "ptype": safe_text(metadata.get("主题分类")),
        "content_html": content_html,
        "raw_text": raw_text,
        "content_id": safe_text(meta_tags.get("contentid")),
        "url": url,
    }


def _filter_fixture_rows(
    rows: list[dict[str, Any]],
    *,
    org: str | None,
    ptype: str | None,
    keyword: str | None,
    start_date: str | None,
    end_date: str | None,
) -> list[dict[str, Any]]:
    org_text = safe_text(org)
    topic_text = safe_text(ptype)
    keyword_text = safe_text(keyword)
    start = _date_only(start_date)
    end = _date_only(end_date)
    filtered = []
    for row in rows:
        title = _clean_html_text(row.get("title"))
        summary = _clean_html_text(row.get("summary"))
        row_org = safe_text(row.get("puborg"))
        row_ptype = safe_text(row.get("ptype") or row.get("childtype"))
        pubtime = _date_only(row.get("pubtime") or row.get("pubtimeStr"))
        if org_text and org_text not in row_org:
            continue
        if topic_text and topic_text not in row_ptype:
            continue
        if keyword_text and keyword_text not in title and keyword_text not in summary:
            continue
        if start and pubtime and pubtime < start:
            continue
        if end and pubtime and pubtime > end:
            continue
        filtered.append(row)
    return filtered


def _document_from_policy_row(
    row: dict[str, Any],
    *,
    content: dict[str, str],
    ingested_at: str,
    raw_path: Path,
    ptype: str | None = None,
    ptype_label: str | None = None,
) -> dict[str, str]:
    url = safe_text(row.get("url") or content.get("url"))
    source_id = safe_text(row.get("id") or row.get("source_id") or content.get("content_id") or Path(urlparse(url).path).stem)
    title = _clean_html_text(row.get("title")) or safe_text(content.get("title"))
    puborg = safe_text(row.get("puborg") or content.get("puborg"))
    published_at = _date_only(row.get("pubtimeStr") or row.get("pubtime") or content.get("published_at"))
    pcode = safe_text(row.get("pcode") or content.get("pcode"))
    topic = safe_text(content.get("ptype") or row.get("ptype") or row.get("childtype"))
    if ptype_label:
        topic = ptype_label
    elif ptype and ptype in TOPIC_NAME_TO_PARAMS and TOPIC_NAME_TO_PARAMS[ptype].get("ptype_label"):
        topic = TOPIC_NAME_TO_PARAMS[ptype]["ptype_label"]
    content_html = content.get("content_html", "")
    raw_text = content.get("raw_text", "")
    content_hash = content_sha256(content_html or raw_text or title)
    dedupe_key = stable_dedupe_key(source_id, url, pcode, title, puborg, published_at, content_hash)
    return {
        "document_id": stable_document_id("gov_policy", source_id, content_hash),
        "corpus_type": "policy",
        "event_type": "policy_document",
        "provider": "gov_policy",
        "source": GOV_POLICY_SOURCE,
        "source_id": source_id,
        "published_at": published_at,
        "issued_at": _date_only(content.get("issued_at")),
        "ingested_at": ingested_at,
        "as_of_time": ingested_at,
        "title": title,
        "summary": _clean_html_text(row.get("summary")),
        "content_html": content_html,
        "raw_text": raw_text,
        "url": url,
        "org": puborg,
        "pcode": pcode,
        "ptype": topic,
        "symbols": "",
        "industries": "",
        "topics": topic,
        "language": "zh-CN",
        "dedupe_key": dedupe_key,
        "content_hash": content_hash,
        "raw_path": str(raw_path),
        "parse_status": safe_text(content.get("parse_status")) or ("ok" if content_html else "partial"),
        "source_confidence": "official_public_source",
        "parser_version": GOV_POLICY_PARSER_VERSION,
    }


def _gov_policy_headers() -> dict[str, str]:
    return {
        "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
        "Referer": "https://sousuo.www.gov.cn/zcwjk/policyDocumentLibrary",
        "User-Agent": DEFAULT_USER_AGENT,
    }


def _charset_from_content_type(value: str | None) -> str:
    match = re.search(r"charset=([0-9A-Za-z_.-]+)", safe_text(value), flags=re.IGNORECASE)
    return match.group(1) if match else ""


def _charset_from_html_meta(content: bytes) -> str:
    head = content[:4096].decode("ascii", errors="ignore")
    match = re.search(r"charset=[\"']?\s*([0-9A-Za-z_.-]+)", head, flags=re.IGNORECASE)
    return match.group(1) if match else ""


def _decode_gov_policy_response(response: requests.Response) -> str:
    content = getattr(response, "content", b"") or b""
    if not content:
        return response.text
    header_encoding = _charset_from_content_type(response.headers.get("content-type") if response.headers else "")
    candidates = [
        _charset_from_html_meta(content),
        header_encoding,
        safe_text(getattr(response, "apparent_encoding", "")),
        safe_text(getattr(response, "encoding", "")),
        "utf-8",
    ]
    seen: set[str] = set()
    for encoding in candidates:
        normalized = safe_text(encoding)
        if not normalized or normalized.lower() in seen:
            continue
        seen.add(normalized.lower())
        try:
            return content.decode(normalized)
        except (LookupError, UnicodeDecodeError):
            continue
    return content.decode("utf-8", errors="replace")


def _request_gov_policy_text(
    url: str,
    *,
    params: dict[str, str] | None = None,
    timeout: int,
) -> str:
    last_error: Exception | None = None
    for attempt in range(1, DEFAULT_HTTP_ATTEMPTS + 1):
        try:
            response = requests.get(
                url,
                params=params,
                timeout=timeout,
                headers=_gov_policy_headers(),
            )
            if response.status_code in RETRYABLE_STATUS_CODES and attempt < DEFAULT_HTTP_ATTEMPTS:
                last_error = requests.HTTPError(f"gov.cn HTTP {response.status_code}: {response.url}")
            else:
                response.raise_for_status()
                return _decode_gov_policy_response(response)
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= DEFAULT_HTTP_ATTEMPTS:
                break
        time.sleep(DEFAULT_RETRY_BACKOFF_SECONDS * attempt)
    raise RuntimeError(f"gov.cn request failed after {DEFAULT_HTTP_ATTEMPTS} attempts: {url}") from last_error


def _fetch_live_search(*, params: dict[str, str], timeout: int) -> str:
    return _request_gov_policy_text(GOV_SEARCH_URL, params=params, timeout=timeout)


def _fetch_live_content(url: str, *, timeout: int) -> str:
    return _request_gov_policy_text(url, timeout=timeout)


def _reference_cache_status(reference_root: Path) -> dict[str, Any]:
    status: dict[str, Any] = {
        "reference_dir": str(reference_root),
        "departments_path": str(reference_root / "departments.json"),
        "topics_path": str(reference_root / "topics.json"),
        "departments_cached": (reference_root / "departments.json").exists(),
        "topics_cached": (reference_root / "topics.json").exists(),
        "department_count": 0,
        "topic_count": 0,
    }
    department_names = _read_cached_department_names(reference_root)
    topic_params = _read_cached_topic_params(reference_root)
    if department_names:
        status["department_count"] = len(department_names)
    if topic_params:
        status["topic_count"] = len(topic_params)
    return status


def _add_audit_check(
    checks: list[dict[str, Any]],
    *,
    name: str,
    ok: bool,
    severity: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    checks.append(
        {
            "name": name,
            "status": "ok" if ok else severity,
            "severity": severity,
            "message": message,
            "details": details or {},
        }
    )


def audit_gov_policy_probe_report(
    report: dict[str, Any],
    *,
    min_rows: int = DEFAULT_PROBE_MIN_ROWS,
    require_topic_tree: bool = True,
    min_topic_count: int = DEFAULT_PROBE_MIN_TOPIC_COUNT,
    min_department_count: int = DEFAULT_PROBE_MIN_DEPARTMENT_COUNT,
    require_content: bool = True,
    require_content_html: bool = True,
    min_content_raw_text_length: int = DEFAULT_PROBE_MIN_CONTENT_RAW_TEXT_LENGTH,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    reference = report.get("reference", {}) if isinstance(report.get("reference"), dict) else {}
    search = report.get("search", {}) if isinstance(report.get("search"), dict) else {}
    content = report.get("content", {}) if isinstance(report.get("content"), dict) else {}
    query = report.get("query", {}) if isinstance(report.get("query"), dict) else {}

    effective_topic_count = int(reference.get("effective_topic_count") or 0)
    _add_audit_check(
        checks,
        name="reference_topic_count",
        ok=effective_topic_count >= min_topic_count,
        severity="error",
        message=f"effective topic count must be >= {min_topic_count}",
        details={"observed": effective_topic_count, "minimum": min_topic_count},
    )
    effective_department_count = int(reference.get("effective_department_count") or 0)
    _add_audit_check(
        checks,
        name="reference_department_count",
        ok=effective_department_count >= min_department_count,
        severity="error",
        message=f"effective department count must be >= {min_department_count}",
        details={"observed": effective_department_count, "minimum": min_department_count},
    )
    if safe_text(query.get("ptype")):
        _add_audit_check(
            checks,
            name="reference_matched_topic",
            ok=bool(reference.get("matched_topic")),
            severity="error",
            message="requested ptype must resolve to an official topic id",
            details={"ptype": safe_text(query.get("ptype")), "matched_topic": reference.get("matched_topic") or {}},
        )

    search_ok = bool(search.get("ok"))
    _add_audit_check(
        checks,
        name="search_response_ok",
        ok=search_ok,
        severity="error",
        message="gov.cn search response must parse successfully",
        details={"response_keys": search.get("response_keys", [])},
    )
    row_count = int(search.get("row_count") or 0)
    _add_audit_check(
        checks,
        name="search_min_rows",
        ok=row_count >= min_rows,
        severity="error",
        message=f"search row count must be >= {min_rows}",
        details={"observed": row_count, "minimum": min_rows},
    )
    field_keys = set(search.get("field_keys") or [])
    missing_required = sorted(GOV_POLICY_REQUIRED_SEARCH_FIELDS - field_keys)
    _add_audit_check(
        checks,
        name="search_required_fields",
        ok=not missing_required,
        severity="error",
        message="search rows must expose title and url",
        details={"missing": missing_required, "field_keys": sorted(field_keys)},
    )
    has_date_field = bool(GOV_POLICY_DATE_SEARCH_FIELDS & field_keys)
    _add_audit_check(
        checks,
        name="search_date_field",
        ok=has_date_field,
        severity="error",
        message="search rows must expose pubtime or pubtimeStr for as-of auditing",
        details={"accepted": sorted(GOV_POLICY_DATE_SEARCH_FIELDS), "field_keys": sorted(field_keys)},
    )
    if require_topic_tree:
        _add_audit_check(
            checks,
            name="search_topic_tree",
            ok=bool(search.get("has_topic_tree")),
            severity="error",
            message="search response must include ztflTree for topic drift auditing",
            details={"topic_tree_count": int(search.get("topic_tree_count") or 0)},
        )

    if require_content:
        _add_audit_check(
            checks,
            name="content_response_ok",
            ok=bool(content.get("ok")),
            severity="error",
            message="sample content page must parse successfully",
            details={"url": safe_text(content.get("url")), "error": safe_text(content.get("error"))},
        )
        if require_content_html:
            _add_audit_check(
                checks,
                name="content_html_present",
                ok=bool(content.get("content_html_present")),
                severity="error",
                message="sample content page must expose content_html",
                details={"url": safe_text(content.get("url"))},
            )
        raw_text_length = int(content.get("raw_text_length") or 0)
        _add_audit_check(
            checks,
            name="content_raw_text_length",
            ok=raw_text_length >= min_content_raw_text_length,
            severity="error",
            message=f"sample content raw_text length must be >= {min_content_raw_text_length}",
            details={"observed": raw_text_length, "minimum": min_content_raw_text_length},
        )
    else:
        _add_audit_check(
            checks,
            name="content_probe",
            ok=True,
            severity="warning",
            message="content probe skipped by caller",
            details={},
        )

    errors = [check for check in checks if check["status"] == "error"]
    warnings = [check for check in checks if check["status"] == "warning"]
    return {
        "ok": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "checks": checks,
    }


def probe_gov_policy_source(
    *,
    root: Path | None = None,
    org: str | None = "国务院",
    ptype: str | None = "科技",
    keyword: str | None = "人工智能",
    start_date: str | None = None,
    end_date: str | None = None,
    collection: str = "all",
    reference_dir: str | Path = DEFAULT_REFERENCE_DIR,
    refresh_reference: bool = False,
    timeout: int = 20,
    content_probe: bool = True,
    min_rows: int = DEFAULT_PROBE_MIN_ROWS,
    require_topic_tree: bool = True,
    min_topic_count: int = DEFAULT_PROBE_MIN_TOPIC_COUNT,
    min_department_count: int = DEFAULT_PROBE_MIN_DEPARTMENT_COUNT,
    require_content_html: bool = True,
    min_content_raw_text_length: int = DEFAULT_PROBE_MIN_CONTENT_RAW_TEXT_LENGTH,
) -> dict[str, Any]:
    project_root = root or Path.cwd()
    reference_root = resolve_path(project_root, reference_dir)
    report: dict[str, Any] = {
        "provider": "gov_policy",
        "parser_version": GOV_POLICY_PARSER_VERSION,
        "probed_at": now_iso(),
        "ok": False,
        "query": {
            "org": safe_text(org),
            "ptype": safe_text(ptype),
            "keyword": safe_text(keyword),
            "start_date": _date_only(start_date),
            "end_date": _date_only(end_date),
            "collection": collection,
        },
        "reference": {},
        "search": {},
        "content": {},
        "errors": [],
    }

    try:
        department_names, topic_params = load_gov_policy_references(
            root=project_root,
            reference_dir=reference_dir,
            refresh=refresh_reference,
            timeout=timeout,
            ingested_at=report["probed_at"],
        )
        report["reference"] = _reference_cache_status(reference_root)
        report["reference"]["department_validation"] = department_names is not None
        report["reference"]["effective_department_count"] = len(department_names or [])
        report["reference"]["effective_topic_count"] = len(topic_params)
        report["reference"]["topic_keys_sample"] = sorted(topic_params)[:12]
        if safe_text(ptype) and safe_text(ptype) in topic_params:
            report["reference"]["matched_topic"] = topic_params[safe_text(ptype)]
        params = build_gov_policy_params(
            org=org,
            ptype=ptype,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            collection=collection,
            page=0,
            page_size=5,
            department_names=department_names,
            topic_params=topic_params,
        )
        report["search"]["params"] = params
        search_text = _fetch_live_search(params=params, timeout=timeout)
        rows = parse_gov_policy_list_response(search_text)
        payload = json.loads(search_text)
        topic_tree = _find_topic_tree(payload)
        report["search"].update(
            {
                "ok": True,
                "row_count": len(rows),
                "has_topic_tree": bool(topic_tree),
                "topic_tree_count": len(topic_tree),
                "sample_titles": [_clean_html_text(row.get("title")) for row in rows[:3]],
                "sample_urls": [safe_text(row.get("url")) for row in rows[:3]],
                "response_keys": sorted(payload.keys()) if isinstance(payload, dict) else [],
                "field_keys": sorted({key for row in rows[:10] for key in row.keys()}),
            }
        )

        if content_probe and rows:
            sample = rows[0]
            url = safe_text(sample.get("url"))
            try:
                content_text = _fetch_live_content(url, timeout=timeout)
                content = parse_gov_policy_content(content_text, url=url)
                report["content"] = {
                    "ok": bool(content.get("content_html") or content.get("raw_text")),
                    "url": url,
                    "title": _clean_html_text(sample.get("title")) or safe_text(content.get("title")),
                    "published_at": _date_only(sample.get("pubtimeStr") or sample.get("pubtime") or content.get("published_at")),
                    "org": safe_text(sample.get("puborg") or content.get("puborg")),
                    "pcode": safe_text(sample.get("pcode") or content.get("pcode")),
                    "content_html_present": bool(content.get("content_html")),
                    "raw_text_length": len(content.get("raw_text", "")),
                }
            except Exception as exc:
                report["content"] = {
                    "ok": False,
                    "url": url,
                    "error": f"{type(exc).__name__}: {exc}",
                }
                report["errors"].append(report["content"]["error"])
        elif content_probe:
            report["content"] = {"ok": False, "error": "no search rows available for content probe"}
            report["errors"].append(report["content"]["error"])
        else:
            report["content"] = {"ok": None, "skipped": True}

        report["ok"] = bool(report["search"].get("ok")) and len(rows) > 0
        if content_probe:
            report["ok"] = report["ok"] and bool(report["content"].get("ok"))
    except Exception as exc:
        report["errors"].append(f"{type(exc).__name__}: {exc}")
    report["audit"] = audit_gov_policy_probe_report(
        report,
        min_rows=min_rows,
        require_topic_tree=require_topic_tree,
        min_topic_count=min_topic_count,
        min_department_count=min_department_count,
        require_content=content_probe,
        require_content_html=require_content_html,
        min_content_raw_text_length=min_content_raw_text_length,
    )
    report["ok"] = bool(report.get("ok")) and bool(report["audit"].get("ok"))
    return report


def fetch_national_policy_repository(
    *,
    root: Path | None = None,
    org: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    ptype: str | None = None,
    keyword: str | None = None,
    collection: str = "all",
    fields: list[str] | None = None,
    limit: int = 500,
    include_content: bool = True,
    fixture_dir: str | Path | None = None,
    raw_archive_dir: str | Path = DEFAULT_RAW_ARCHIVE_DIR,
    reference_dir: str | Path = DEFAULT_REFERENCE_DIR,
    refresh_reference: bool = False,
    timeout: int = 20,
    ingested_at: str | None = None,
) -> pd.DataFrame:
    project_root = root or Path.cwd()
    archive_root = resolve_path(project_root, raw_archive_dir)
    fetched_at = ingested_at or now_iso()
    page_size = min(max(limit, 1), 50)
    topic_params: dict[str, dict[str, str]] | None = None

    if fixture_dir:
        fixture_root = resolve_path(project_root, fixture_dir)
        search_path, search_text = _load_fixture_search(fixture_root)
        search_raw_path = _write_raw_text(
            archive_root=archive_root,
            kind="search",
            ingested_at=fetched_at,
            stem=search_path.stem,
            suffix="json",
            text=search_text,
        )
        rows = _filter_fixture_rows(
            parse_gov_policy_list_response(search_text),
            org=org,
            ptype=ptype,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
        )
    else:
        department_names: set[str] | None = None
        needs_reference = bool(safe_text(ptype)) or (
            bool(safe_text(org)) and safe_text(org) not in STATE_COUNCIL_ORGS
        )
        if needs_reference:
            department_names, topic_params = load_gov_policy_references(
                root=project_root,
                reference_dir=reference_dir,
                refresh=refresh_reference,
                timeout=timeout,
                ingested_at=fetched_at,
            )
        search_raw_path = archive_root / "search"
        rows = []
        page = 0
        while len(rows) < limit:
            params = build_gov_policy_params(
                org=org,
                ptype=ptype,
                keyword=keyword,
                start_date=start_date,
                end_date=end_date,
                collection=collection,
                page=page,
                page_size=page_size,
                department_names=department_names,
                topic_params=topic_params,
            )
            search_text = _fetch_live_search(params=params, timeout=timeout)
            search_raw_path = _write_raw_text(
                archive_root=archive_root,
                kind="search",
                ingested_at=fetched_at,
                stem=f"search_gov_data_p{page}",
                suffix="json",
                text=search_text,
            )
            page_rows = parse_gov_policy_list_response(search_text)
            if not page_rows:
                break
            rows.extend(page_rows)
            if len(page_rows) < page_size:
                break
            page += 1

    ptype_text = safe_text(ptype)
    ptype_label = ""
    if ptype_text and topic_params and ptype_text in topic_params:
        ptype_label = safe_text(topic_params[ptype_text].get("ptype_label"))
    elif ptype_text and ptype_text in TOPIC_NAME_TO_PARAMS:
        ptype_label = safe_text(TOPIC_NAME_TO_PARAMS[ptype_text].get("ptype_label"))

    documents: list[dict[str, str]] = []
    for row in rows[:limit]:
        content: dict[str, str] = {"url": safe_text(row.get("url"))}
        content_raw_path = search_raw_path
        if include_content and safe_text(row.get("url")):
            try:
                if fixture_dir:
                    fixture_root = resolve_path(project_root, fixture_dir)
                    content_fixture = _content_fixture_path(fixture_root, row)
                    content_text = content_fixture.read_text(encoding="utf-8")
                    content_raw_path = _write_raw_text(
                        archive_root=archive_root,
                        kind="content",
                        ingested_at=fetched_at,
                        stem=content_fixture.stem,
                        suffix="html",
                        text=content_text,
                    )
                else:
                    content_text = _fetch_live_content(safe_text(row.get("url")), timeout=timeout)
                    content_raw_path = _write_raw_text(
                        archive_root=archive_root,
                        kind="content",
                        ingested_at=fetched_at,
                        stem=Path(urlparse(safe_text(row.get("url"))).path).stem,
                        suffix="html",
                        text=content_text,
                    )
                content = parse_gov_policy_content(content_text, url=safe_text(row.get("url")))
            except Exception as exc:
                content = {
                    "url": safe_text(row.get("url")),
                    "raw_text": f"content fetch/parse failed: {type(exc).__name__}: {exc}",
                    "parse_status": "failed",
                }
        documents.append(
            _document_from_policy_row(
                row,
                content=content,
                ingested_at=fetched_at,
                raw_path=content_raw_path,
                ptype=ptype,
                ptype_label=ptype_label,
            )
        )

    output_rows = select_fields(documents, fields)
    return pd.DataFrame(output_rows, columns=fields or AI_CORPUS_DOCUMENT_COLUMNS)


def npr(
    *,
    org: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    ptype: str | None = None,
    keyword: str | None = None,
    fields: str | None = None,
    limit: int = 500,
    include_content: bool = True,
    root: Path | None = None,
    fixture_dir: str | Path | None = None,
    raw_archive_dir: str | Path = DEFAULT_RAW_ARCHIVE_DIR,
    reference_dir: str | Path = DEFAULT_REFERENCE_DIR,
    refresh_reference: bool = False,
    timeout: int = 20,
) -> pd.DataFrame:
    field_list = [field.strip() for field in fields.split(",") if field.strip()] if fields else None
    return fetch_national_policy_repository(
        root=root,
        org=org,
        start_date=start_date,
        end_date=end_date,
        ptype=ptype,
        keyword=keyword,
        fields=field_list,
        limit=limit,
        include_content=include_content,
        fixture_dir=fixture_dir,
        raw_archive_dir=raw_archive_dir,
        reference_dir=reference_dir,
        refresh_reference=refresh_reference,
        timeout=timeout,
    )
