from __future__ import annotations

import json
import re
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
GOV_POLICY_SOURCE = "中国政府网"
DEFAULT_RAW_ARCHIVE_DIR = "data/raw_data/ai_corpus/gov_policy"
DEFAULT_USER_AGENT = "stok-mapping-ai-corpus/1.0"

TOPIC_NAME_TO_PARAMS = {
    "科技": {"subchildtype": "2220", "ptype_label": "科技、教育\\科技"},
    "科技、教育": {"childtype": "1088", "ptype_label": "科技、教育"},
}


def _date_only(value: str | None) -> str:
    text = safe_text(value)
    if not text:
        return ""
    normalized = text.replace("/", "-").replace("T", " ")
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
        if org_text in {"国务院", "国务院办公厅"}:
            params["t"] = "zhengcelibrary_gw"
            params["puborg"] = org_text
        else:
            params["t"] = "zhengcelibrary_bm"
            params["bmfl"] = org_text
    topic_text = safe_text(ptype)
    if topic_text:
        topic_params = TOPIC_NAME_TO_PARAMS.get(topic_text)
        if not topic_params:
            raise ValueError(f"unsupported gov.cn policy topic mapping: {ptype}")
        for key in ("childtype", "subchildtype"):
            if key in topic_params:
                params[key] = topic_params[key]
    start = _date_only(start_date)
    end = _date_only(end_date)
    if start or end:
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
        title = safe_text(row.get("title"))
        summary = safe_text(row.get("summary"))
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
) -> dict[str, str]:
    url = safe_text(row.get("url") or content.get("url"))
    source_id = safe_text(row.get("id") or row.get("source_id") or content.get("content_id") or Path(urlparse(url).path).stem)
    title = safe_text(row.get("title") or content.get("title"))
    puborg = safe_text(row.get("puborg") or content.get("puborg"))
    published_at = _date_only(row.get("pubtimeStr") or row.get("pubtime") or content.get("published_at"))
    pcode = safe_text(row.get("pcode") or content.get("pcode"))
    topic = safe_text(content.get("ptype") or row.get("ptype") or row.get("childtype"))
    if ptype and ptype in TOPIC_NAME_TO_PARAMS and TOPIC_NAME_TO_PARAMS[ptype].get("ptype_label"):
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
        "summary": safe_text(row.get("summary")),
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


def _fetch_live_search(*, params: dict[str, str], timeout: int) -> str:
    response = requests.get(GOV_SEARCH_URL, params=params, timeout=timeout, headers={"User-Agent": DEFAULT_USER_AGENT})
    response.raise_for_status()
    response.encoding = response.encoding or "utf-8"
    return response.text


def _fetch_live_content(url: str, *, timeout: int) -> str:
    response = requests.get(url, timeout=timeout, headers={"User-Agent": DEFAULT_USER_AGENT})
    response.raise_for_status()
    response.encoding = response.encoding or "utf-8"
    return response.text


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
    timeout: int = 20,
    ingested_at: str | None = None,
) -> pd.DataFrame:
    project_root = root or Path.cwd()
    archive_root = resolve_path(project_root, raw_archive_dir)
    fetched_at = ingested_at or now_iso()
    page_size = min(max(limit, 1), 50)

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
        documents.append(_document_from_policy_row(row, content=content, ingested_at=fetched_at, raw_path=content_raw_path, ptype=ptype))

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
    )
