from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

from phase0.ai_corpus.registry import CCTV_NEWS_PARSER_VERSION
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

CCTV_SOURCE = "央视网新闻联播"
CCTV_DAY_URL_TEMPLATE = "https://tv.cctv.com/lm/xwlb/day/{date}.shtml"
DEFAULT_RAW_ARCHIVE_DIR = "data/raw_data/ai_corpus/cctv"
DEFAULT_USER_AGENT = "stok-mapping-ai-corpus/1.0"


def _date_only(value: str | None) -> str:
    text = safe_text(value)
    if not text:
        return ""
    if re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    match = re.search(r"\d{4}-\d{1,2}-\d{1,2}", text.replace("/", "-"))
    if match:
        year, month, day = [int(part) for part in match.group(0).split("-")]
        return f"{year:04d}-{month:02d}-{day:02d}"
    return text


def _compact_date(value: str | None) -> str:
    date_value = _date_only(value)
    return date_value.replace("-", "") if date_value else ""


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


def _fixture_day_path(fixture_dir: Path, date: str) -> Path:
    compact = _compact_date(date)
    for candidate in [
        fixture_dir / f"day_{compact}.html",
        fixture_dir / f"{compact}.html",
        fixture_dir / "day.html",
    ]:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"cctv day fixture not found for {compact} under {fixture_dir}")


def _content_fixture_path(fixture_dir: Path, item: dict[str, str]) -> Path:
    stems = [safe_text(item.get("source_id")), Path(urlparse(safe_text(item.get("url"))).path).stem]
    for stem in [value for value in stems if value]:
        for suffix in (".html", ".htm"):
            path = fixture_dir / f"{stem}{suffix}"
            if path.exists():
                return path
    raise FileNotFoundError(f"cctv content fixture not found for {safe_text(item.get('source_id')) or safe_text(item.get('url'))}")


def _fetch_live_text(url: str, *, timeout: int) -> str:
    response = requests.get(url, timeout=timeout, headers={"User-Agent": DEFAULT_USER_AGENT})
    response.raise_for_status()
    encoding = response.encoding or ""
    if not encoding or encoding.lower() in {"iso-8859-1", "latin-1"}:
        encoding = response.apparent_encoding or "utf-8"
    response.encoding = encoding
    return response.text


def _meta_tags(soup: BeautifulSoup) -> dict[str, str]:
    tags: dict[str, str] = {}
    for meta in soup.find_all("meta"):
        key = safe_text(meta.get("name") or meta.get("property")).lower()
        value = safe_text(meta.get("content"))
        if key and value:
            tags[key] = value
    return tags


def parse_cctv_day_page(html_text: str, *, date: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(f"<html><body>{html_text}</body></html>", "html.parser")
    items: list[dict[str, str]] = []
    for node in soup.find_all("li"):
        link = node.find("a", href=True)
        if not link:
            continue
        url = safe_text(link.get("href"))
        title = safe_text(link.get("title") or link.get("alt") or link.get_text(" ", strip=True))
        source_id = Path(urlparse(url).path).stem
        duration_node = node.find("span")
        badge = node.find("i")
        badge_class = " ".join(badge.get("class", [])) if badge else ""
        is_full_program = "《新闻联播》" in title or "sql0" in badge_class
        items.append(
            {
                "source_id": source_id,
                "title": title,
                "url": url,
                "published_at": _date_only(date),
                "duration": safe_text(duration_node.get_text(" ", strip=True) if duration_node else ""),
                "item_type": "full_program" if is_full_program else "segment",
            }
        )
    return items


def parse_cctv_content_page(html_text: str, *, url: str = "") -> dict[str, str]:
    soup = BeautifulSoup(html_text, "html.parser")
    meta = _meta_tags(soup)
    title = safe_text(meta.get("og:title") or (soup.title.get_text(" ", strip=True) if soup.title else ""))
    description = safe_text(meta.get("description") or meta.get("og:description"))
    content_candidates = [soup.find(id="content_area"), soup.find(class_="video_brief")]
    content_node = next(
        (node for node in content_candidates if node and safe_text(node.get_text(" ", strip=True))),
        None,
    )
    if content_node:
        content_html = str(content_node).strip()
        raw_text = content_node.get_text("\n", strip=True)
    elif description:
        content_html = f"<p>{description}</p>"
        raw_text = description
    else:
        content_html = ""
        raw_text = soup.get_text("\n", strip=True)
    guid_match = re.search(r'var\s+guid\s*=\s*"([^"]+)"', html_text)
    return {
        "source_id": safe_text(meta.get("contentid") or Path(urlparse(url).path).stem),
        "title": title,
        "summary": description,
        "content_html": content_html,
        "raw_text": raw_text,
        "guid": safe_text(guid_match.group(1) if guid_match else ""),
        "url": url,
    }


def _document_from_cctv_item(
    item: dict[str, str],
    *,
    content: dict[str, str],
    ingested_at: str,
    raw_path: Path,
) -> dict[str, str]:
    source_id = safe_text(content.get("source_id") or item.get("source_id"))
    title = safe_text(content.get("title") or item.get("title"))
    content_html = safe_text(content.get("content_html"))
    raw_text = safe_text(content.get("raw_text") or content.get("summary"))
    content_hash = content_sha256(content_html or raw_text or title)
    item_type = safe_text(item.get("item_type")) or "segment"
    event_type = "cctv_news_full" if item_type == "full_program" else "cctv_news_segment"
    topic = "新闻联播\\完整版" if event_type == "cctv_news_full" else "新闻联播\\分段"
    published_at = _date_only(item.get("published_at"))
    dedupe_key = stable_dedupe_key(source_id, item.get("url", ""), title, published_at, content_hash)
    return {
        "document_id": stable_document_id("cctv", source_id, content_hash),
        "corpus_type": "cctv_news",
        "event_type": event_type,
        "provider": "cctv",
        "source": CCTV_SOURCE,
        "source_id": source_id,
        "published_at": published_at,
        "issued_at": "",
        "ingested_at": ingested_at,
        "as_of_time": ingested_at,
        "title": title,
        "summary": safe_text(content.get("summary")),
        "content_html": content_html,
        "raw_text": raw_text,
        "url": safe_text(item.get("url") or content.get("url")),
        "org": "央视网",
        "pcode": "",
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
        "parser_version": CCTV_NEWS_PARSER_VERSION,
    }


def fetch_cctv_news(
    *,
    date: str,
    include_segments: bool = True,
    fields: list[str] | None = None,
    limit: int = 100,
    root: Path | None = None,
    fixture_dir: str | Path | None = None,
    raw_archive_dir: str | Path = DEFAULT_RAW_ARCHIVE_DIR,
    timeout: int = 20,
    ingested_at: str | None = None,
) -> pd.DataFrame:
    project_root = root or Path.cwd()
    archive_root = resolve_path(project_root, raw_archive_dir)
    fetched_at = ingested_at or now_iso()
    compact = _compact_date(date)
    if not compact:
        raise ValueError("cctv news date is required, for example 20260703")

    if fixture_dir:
        fixture_root = resolve_path(project_root, fixture_dir)
        day_path = _fixture_day_path(fixture_root, compact)
        day_text = day_path.read_text(encoding="utf-8")
        day_raw_path = _write_raw_text(
            archive_root=archive_root,
            kind="day",
            ingested_at=fetched_at,
            stem=day_path.stem,
            suffix="html",
            text=day_text,
        )
    else:
        day_url = CCTV_DAY_URL_TEMPLATE.format(date=compact)
        day_text = _fetch_live_text(day_url, timeout=timeout)
        day_raw_path = _write_raw_text(
            archive_root=archive_root,
            kind="day",
            ingested_at=fetched_at,
            stem=f"day_{compact}",
            suffix="html",
            text=day_text,
        )
    items = parse_cctv_day_page(day_text, date=date)
    if not include_segments:
        items = [item for item in items if item.get("item_type") == "full_program"]

    documents: list[dict[str, str]] = []
    for item in items[:limit]:
        raw_path = day_raw_path
        try:
            if fixture_dir:
                fixture_root = resolve_path(project_root, fixture_dir)
                content_path = _content_fixture_path(fixture_root, item)
                content_text = content_path.read_text(encoding="utf-8")
                raw_path = _write_raw_text(
                    archive_root=archive_root,
                    kind="content",
                    ingested_at=fetched_at,
                    stem=content_path.stem,
                    suffix="html",
                    text=content_text,
                )
            else:
                content_text = _fetch_live_text(safe_text(item.get("url")), timeout=timeout)
                raw_path = _write_raw_text(
                    archive_root=archive_root,
                    kind="content",
                    ingested_at=fetched_at,
                    stem=safe_text(item.get("source_id")) or Path(urlparse(safe_text(item.get("url"))).path).stem,
                    suffix="html",
                    text=content_text,
                )
            content = parse_cctv_content_page(content_text, url=safe_text(item.get("url")))
        except Exception as exc:
            content = {
                "source_id": safe_text(item.get("source_id")),
                "title": safe_text(item.get("title")),
                "url": safe_text(item.get("url")),
                "raw_text": f"content fetch/parse failed: {type(exc).__name__}: {exc}",
                "parse_status": "failed",
            }
        documents.append(_document_from_cctv_item(item, content=content, ingested_at=fetched_at, raw_path=raw_path))

    output_rows = select_fields(documents, fields)
    return pd.DataFrame(output_rows, columns=fields or AI_CORPUS_DOCUMENT_COLUMNS)
