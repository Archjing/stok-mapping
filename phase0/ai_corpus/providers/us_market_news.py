from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import feedparser
import pandas as pd

from phase0.ai_corpus.registry import US_MARKET_NEWS_PARSER_VERSION
from phase0.ai_corpus.schema import (
    content_sha256,
    now_iso,
    resolve_path,
    safe_text,
    select_fields,
    stable_dedupe_key,
    stable_document_id,
)

US_MARKET_NEWS_SOURCE = "US market RSS"
DEFAULT_RAW_ARCHIVE_DIR = "data/raw_data/ai_corpus/us_market_news"
DEFAULT_KEYWORDS = (
    "semiconductor",
    "semiconductors",
    "chip",
    "chips",
    "SOX",
    "VIX",
    "Nasdaq",
    "Federal Reserve",
    "interest rate",
    "NVIDIA",
    "NVDA",
    "AMD",
    "Intel",
    "TSMC",
    "Taiwan Semiconductor",
)
DEFAULT_FEEDS = (
    {
        "name": "cnbc_markets",
        "source": "CNBC Markets",
        "url": "https://www.cnbc.com/id/10000664/device/rss/rss.html",
        "topics": ["us_market"],
        "language": "en-US",
    },
    {
        "name": "cnbc_technology",
        "source": "CNBC Technology",
        "url": "https://www.cnbc.com/id/19854910/device/rss/rss.html",
        "topics": ["technology", "semiconductor"],
        "language": "en-US",
    },
)


def _safe_stem(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z_.-]+", "_", safe_text(value)).strip("._")[:100] or "feed"


def _archive_path(*, archive_root: Path, ingested_at: str, feed_name: str) -> Path:
    stamp = safe_text(ingested_at) or now_iso()
    day = stamp[:10] or datetime.now(timezone.utc).date().isoformat()
    year, month, date_part = day.split("-")
    clock = re.sub(r"[^0-9]", "", stamp[11:])[:12] or "run"
    return archive_root / "rss" / year / month / date_part / f"{_safe_stem(feed_name)}_{clock}.xml"


def _write_raw(*, archive_root: Path, ingested_at: str, feed_name: str, payload: bytes) -> Path:
    path = _archive_path(archive_root=archive_root, ingested_at=ingested_at, feed_name=feed_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def _published_at(entry: Any) -> str:
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if parsed:
        return datetime(*parsed[:6], tzinfo=timezone.utc).isoformat()
    raw = safe_text(getattr(entry, "published", "") or getattr(entry, "updated", ""))
    if not raw:
        return ""
    timestamp = pd.to_datetime(raw, errors="coerce", utc=True)
    return "" if pd.isna(timestamp) else timestamp.isoformat()


def _entry_text(entry: Any) -> str:
    parts = [
        safe_text(getattr(entry, "title", "")),
        safe_text(getattr(entry, "summary", "")),
        safe_text(getattr(entry, "description", "")),
    ]
    tags = getattr(entry, "tags", []) or []
    parts.extend(safe_text(tag.get("term", "") if isinstance(tag, dict) else getattr(tag, "term", "")) for tag in tags)
    return " ".join(part for part in parts if part)


def _matches_keywords(text: str, keywords: list[str]) -> list[str]:
    lowered = text.casefold()
    return [keyword for keyword in keywords if safe_text(keyword).casefold() in lowered]


def _feed_config(provider_config: dict[str, Any] | None) -> tuple[list[dict[str, Any]], list[str]]:
    config = provider_config or {}
    feeds = config.get("feeds") or list(DEFAULT_FEEDS)
    keywords = config.get("keywords")
    if keywords is None:
        keywords = list(DEFAULT_KEYWORDS)
    return [feed for feed in feeds if isinstance(feed, dict) and safe_text(feed.get("url"))], [str(item) for item in keywords]


def _fixture_payload(fixture_root: Path, feed: dict[str, Any]) -> bytes:
    name = _safe_stem(str(feed.get("name") or urlparse(str(feed["url"])).netloc))
    candidates = [fixture_root / f"{name}.xml", fixture_root / "feed.xml"]
    for candidate in candidates:
        if candidate.exists():
            return candidate.read_bytes()
    raise FileNotFoundError(f"US market news fixture not found; expected one of: {', '.join(str(p) for p in candidates)}")


def _document_from_entry(
    entry: Any,
    *,
    feed: dict[str, Any],
    matched_keywords: list[str],
    ingested_at: str,
    raw_path: Path,
) -> dict[str, str]:
    title = safe_text(getattr(entry, "title", ""))
    summary = safe_text(getattr(entry, "summary", "") or getattr(entry, "description", ""))
    url = safe_text(getattr(entry, "link", ""))
    published_at = _published_at(entry)
    source_id = safe_text(getattr(entry, "id", "") or getattr(entry, "guid", "") or url or title)
    content_hash = content_sha256("|".join([title, summary, url]))
    configured_topics = [safe_text(item) for item in (feed.get("topics") or []) if safe_text(item)]
    topics = configured_topics + [f"keyword:{item}" for item in matched_keywords]
    industries = ["semiconductor"] if any("chip" in item.casefold() or "semiconductor" in item.casefold() for item in matched_keywords) else []
    return {
        "document_id": stable_document_id("us_market_news", source_id, content_hash),
        "corpus_type": "us_market_news",
        "event_type": "market_news",
        "provider": "us_market_news",
        "source": safe_text(feed.get("source") or feed.get("name") or US_MARKET_NEWS_SOURCE),
        "source_id": source_id,
        "published_at": published_at,
        "issued_at": "",
        "ingested_at": ingested_at,
        "as_of_time": ingested_at,
        "title": title,
        "summary": summary,
        "content_html": "",
        "raw_text": summary,
        "url": url,
        "org": safe_text(feed.get("source") or feed.get("name")),
        "pcode": "",
        "ptype": "",
        "symbols": "",
        "industries": "\\".join(industries),
        "topics": "\\".join(topics),
        "language": safe_text(feed.get("language") or "en-US"),
        "dedupe_key": stable_dedupe_key("us_market_news", source_id, url, title, published_at),
        "content_hash": content_hash,
        "raw_path": str(raw_path),
        "parse_status": "metadata_only" if summary else "title_only",
        "source_confidence": "public_rss_metadata",
        "parser_version": US_MARKET_NEWS_PARSER_VERSION,
    }


def fetch_us_market_news(
    *,
    root: Path | None = None,
    provider_config: dict[str, Any] | None = None,
    keyword: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    fields: list[str] | None = None,
    limit: int = 100,
    fixture_dir: str | Path | None = None,
    raw_archive_dir: str | Path = DEFAULT_RAW_ARCHIVE_DIR,
    timeout: int = 20,
    include_content: bool = True,
    ingested_at: str | None = None,
) -> pd.DataFrame:
    del include_content  # RSS provider intentionally stores metadata only.
    project_root = root or Path.cwd()
    archive_root = resolve_path(project_root, raw_archive_dir)
    fetched_at = ingested_at or now_iso()
    feeds, configured_keywords = _feed_config(provider_config)
    keywords = [safe_text(keyword)] if safe_text(keyword) else configured_keywords
    fixture_root = resolve_path(project_root, fixture_dir) if fixture_dir else None
    rows: list[dict[str, str]] = []
    for feed in feeds:
        feed_name = safe_text(feed.get("name") or feed.get("source") or feed.get("url"))
        if fixture_root:
            payload = _fixture_payload(fixture_root, feed)
        else:
            import requests

            response = requests.get(
                str(feed["url"]),
                timeout=timeout,
                headers={"User-Agent": "stok-mapping/ai-corpus-us-market-news"},
            )
            response.raise_for_status()
            payload = response.content
        raw_path = _write_raw(archive_root=archive_root, ingested_at=fetched_at, feed_name=feed_name, payload=payload)
        parsed = feedparser.parse(payload)
        if getattr(parsed, "bozo", 0) and not getattr(parsed, "entries", []):
            raise ValueError(f"failed to parse RSS feed {feed_name}: {getattr(parsed, 'bozo_exception', 'unknown error')}")
        for entry in getattr(parsed, "entries", []) or []:
            published_at = _published_at(entry)
            published_day = published_at[:10] if published_at else ""
            if start_date and published_day and published_day < str(start_date)[:10]:
                continue
            if end_date and published_day and published_day > str(end_date)[:10]:
                continue
            matched = _matches_keywords(_entry_text(entry), keywords)
            if keywords and not matched:
                continue
            rows.append(
                _document_from_entry(
                    entry,
                    feed=feed,
                    matched_keywords=matched,
                    ingested_at=fetched_at,
                    raw_path=raw_path,
                )
            )
    rows.sort(key=lambda row: row.get("published_at", ""), reverse=True)
    rows = rows[: max(0, int(limit))]
    frame = pd.DataFrame(rows)
    if fields:
        return pd.DataFrame(select_fields(rows, fields))
    return frame


def load_feed_config_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
