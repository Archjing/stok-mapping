from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from quant.ai_corpus.schema import (
    content_sha256,
    now_iso,
    resolve_path,
    safe_text,
    select_fields,
    stable_dedupe_key,
    stable_document_id,
)

# 中文财经快讯源：财联社电报、新浪 7x24、华尔街见闻实时。
# 三者都是公开 JSON 接口，无需 API Key；字段归一化到 ai_corpus_documents。
# 时区统一为 Asia/Shanghai (UTC+8)，与项目 default_timezone 一致。

CN_TZ = timezone(timedelta(hours=8))
UA = "stok-mapping/ai-corpus-cn-finance-flash"

CLS_TELEGRAPH_URL = "https://www.cls.cn/api/cache"
CLS_TELEGRAPH_SOURCE = "财联社电报"
DEFAULT_RAW_ARCHIVE_DIR = "data/raw_data/ai_corpus/cn_finance_flash"

SINA_7X24_URL = "https://zhibo.sina.com.cn/api/zhibo/feed"
SINA_7X24_SOURCE = "新浪财经 7x24"
SINA_7X24_PAGE_SIZE = 100

WALLSTCN_LIVES_URL = "https://api-one.wallstcn.com/apiv1/content/lives"
WALLSTCN_LIVES_SOURCE = "华尔街见闻实时快讯"


def _safe_stem(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z_.-]+", "_", safe_text(value)).strip("._")[:100] or "feed"


def _archive_path(*, archive_root: Path, ingested_at: str, source: str) -> Path:
    stamp = safe_text(ingested_at) or now_iso()
    day = stamp[:10] or datetime.now(CN_TZ).date().isoformat()
    year, month, date_part = day.split("-")
    clock = re.sub(r"[^0-9]", "", stamp[11:])[:12] or "run"
    return archive_root / "flash" / year / month / date_part / f"{_safe_stem(source)}_{clock}.json"


def _write_raw(*, archive_root: Path, ingested_at: str, source: str, payload: bytes) -> Path:
    path = _archive_path(archive_root=archive_root, ingested_at=ingested_at, source=source)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def _http_get_json(url: str, *, params: dict[str, Any], headers: dict[str, str], timeout: int) -> dict[str, Any]:
    import requests

    response = requests.get(url, params=params, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _parse_cn_time(value: Any) -> str:
    text = safe_text(value)
    if not text:
        return ""
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        try:
            return datetime.fromtimestamp(int(value), tz=CN_TZ).isoformat()
        except (OverflowError, OSError, ValueError):
            return ""
    timestamp = pd.to_datetime(text, errors="coerce")
    if pd.isna(timestamp):
        return ""
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(CN_TZ)
    return timestamp.isoformat()


def _base_document(
    *,
    provider: str,
    source: str,
    source_id: str,
    published_at: str,
    title: str,
    raw_text: str,
    url: str,
    topics: list[str],
    symbols: list[str],
    ingested_at: str,
    raw_path: Path,
    parser_version: str,
    parse_status: str,
) -> dict[str, str]:
    content_hash = content_sha256("|".join([title, raw_text, url]))
    topics_clean = [safe_text(item) for item in topics if safe_text(item)]
    symbols_clean = [safe_text(item) for item in symbols if safe_text(item)]
    return {
        "document_id": stable_document_id(provider, source_id, content_hash),
        "corpus_type": "market_flash",
        "event_type": "market_news",
        "provider": provider,
        "source": source,
        "source_id": source_id,
        "published_at": published_at,
        "issued_at": "",
        "ingested_at": ingested_at,
        "as_of_time": ingested_at,
        "title": title,
        "summary": "",
        "content_html": "",
        "raw_text": raw_text,
        "url": url,
        "org": source,
        "pcode": "",
        "ptype": "",
        "symbols": ";".join(symbols_clean),
        "industries": "",
        "topics": "\\".join(topics_clean),
        "language": "zh-CN",
        "dedupe_key": stable_dedupe_key(provider, source_id, url, title, published_at),
        "content_hash": content_hash,
        "raw_path": str(raw_path),
        "parse_status": parse_status,
        "source_confidence": "public_json_feed",
        "parser_version": parser_version,
    }


# ---------------------------------------------------------------------------
# 财联社电报
# ---------------------------------------------------------------------------


def _cls_document_from_item(item: dict[str, Any], *, ingested_at: str, raw_path: Path, parser_version: str) -> dict[str, str]:
    title = safe_text(item.get("title")) or safe_text(item.get("brief"))
    raw_text = safe_text(item.get("content")) or safe_text(item.get("brief")) or title
    published_at = _parse_cn_time(item.get("ctime"))
    source_id = safe_text(item.get("id"))
    url = f"https://www.cls.cn/detail/{source_id}" if source_id else ""
    subjects = item.get("subjects") or []
    topics = [safe_text(subject.get("subject_name")) for subject in subjects if isinstance(subject, dict)]
    stocks = item.get("stock_list") or []
    symbols = [safe_text(stock.get("symbol") or stock.get("code")) for stock in stocks if isinstance(stock, dict)]
    parse_status = "full_text" if raw_text else "title_only"
    return _base_document(
        provider="cls_telegraph",
        source=CLS_TELEGRAPH_SOURCE,
        source_id=source_id,
        published_at=published_at,
        title=title,
        raw_text=raw_text,
        url=url,
        topics=topics,
        symbols=symbols,
        ingested_at=ingested_at,
        raw_path=raw_path,
        parser_version=parser_version,
        parse_status=parse_status,
    )


def fetch_cls_telegraph(
    *,
    root: Path | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    fields: list[str] | None = None,
    limit: int = 20,
    fixture_dir: str | Path | None = None,
    raw_archive_dir: str | Path = DEFAULT_RAW_ARCHIVE_DIR,
    timeout: int = 20,
    parser_version: str = "cls_telegraph_v1",
) -> pd.DataFrame:
    project_root = root or Path.cwd()
    archive_root = resolve_path(project_root, raw_archive_dir)
    fetched_at = now_iso()
    fixture_root = resolve_path(project_root, fixture_dir) if fixture_dir else None
    if fixture_root:
        candidates = [fixture_root / "cls_telegraph.json", fixture_root / "telegraph.json"]
        payload = next((c.read_bytes() for c in candidates if c.exists()), None)
        if payload is None:
            raise FileNotFoundError(f"cls telegraph fixture not found under {fixture_root}")
        data = json.loads(payload.decode("utf-8"))
    else:
        data = _http_get_json(
            CLS_TELEGRAPH_URL,
            params={"app": "CailianpressWeb", "name": "telegraph", "os": "web", "sv": "8.7.9"},
            headers={"User-Agent": UA, "Referer": "https://www.cls.cn/telegraph"},
            timeout=timeout,
        )
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    raw_path = _write_raw(archive_root=archive_root, ingested_at=fetched_at, source="cls_telegraph", payload=payload)
    roll = (data.get("data") or {}).get("roll_data") or (data.get("data") or {}).get("telegraph") or []
    rows: list[dict[str, str]] = []
    for item in roll:
        if not isinstance(item, dict):
            continue
        published_at = _parse_cn_time(item.get("ctime"))
        published_day = published_at[:10] if published_at else ""
        if start_date and published_day and published_day < str(start_date)[:10]:
            continue
        if end_date and published_day and published_day > str(end_date)[:10]:
            continue
        rows.append(_cls_document_from_item(item, ingested_at=fetched_at, raw_path=raw_path, parser_version=parser_version))
    rows.sort(key=lambda row: row.get("published_at", ""), reverse=True)
    rows = rows[: max(0, int(limit))]
    if fields:
        return pd.DataFrame(select_fields(rows, fields))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 新浪财经 7x24（支持 page_size + 翻页）
# ---------------------------------------------------------------------------


def _sina_symbols_from_ext(ext: Any) -> list[str]:
    if not ext:
        return []
    try:
        parsed = json.loads(ext) if isinstance(ext, str) else ext
    except json.JSONDecodeError:
        return []
    stocks = parsed.get("stocks") if isinstance(parsed, dict) else None
    if not isinstance(stocks, list):
        return []
    symbols = []
    for stock in stocks:
        if not isinstance(stock, dict):
            continue
        symbol = safe_text(stock.get("symbol"))
        key = safe_text(stock.get("key"))
        symbols.append(f"{symbol}:{key}" if key else symbol)
    return symbols


def _sina_document_from_item(item: dict[str, Any], *, ingested_at: str, raw_path: Path, parser_version: str) -> dict[str, str]:
    raw_text = safe_text(item.get("rich_text")) or safe_text(item.get("content"))
    title = raw_text[:80] if raw_text else ""
    published_at = _parse_cn_time(item.get("create_time"))
    source_id = safe_text(item.get("id"))
    url = ""
    tags = item.get("tag") or []
    topics = [safe_text(tag.get("name")) for tag in tags if isinstance(tag, dict)]
    symbols = _sina_symbols_from_ext(item.get("ext"))
    parse_status = "full_text" if raw_text else "title_only"
    return _base_document(
        provider="sina_7x24",
        source=SINA_7X24_SOURCE,
        source_id=source_id,
        published_at=published_at,
        title=title,
        raw_text=raw_text,
        url=url,
        topics=topics,
        symbols=symbols,
        ingested_at=ingested_at,
        raw_path=raw_path,
        parser_version=parser_version,
        parse_status=parse_status,
    )


def fetch_sina_7x24(
    *,
    root: Path | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    fields: list[str] | None = None,
    limit: int = 100,
    fixture_dir: str | Path | None = None,
    raw_archive_dir: str | Path = DEFAULT_RAW_ARCHIVE_DIR,
    timeout: int = 20,
    parser_version: str = "sina_7x24_v1",
) -> pd.DataFrame:
    project_root = root or Path.cwd()
    archive_root = resolve_path(project_root, raw_archive_dir)
    fetched_at = now_iso()
    fixture_root = resolve_path(project_root, fixture_dir) if fixture_dir else None
    if fixture_root:
        candidates = [fixture_root / "sina_7x24.json", fixture_root / "sina.json"]
        payload = next((c.read_bytes() for c in candidates if c.exists()), None)
        if payload is None:
            raise FileNotFoundError(f"sina 7x24 fixture not found under {fixture_root}")
        data = json.loads(payload.decode("utf-8"))
        items = ((data.get("result") or {}).get("data") or {}).get("feed", {}).get("list", [])
        raw_path = _write_raw(archive_root=archive_root, ingested_at=fetched_at, source="sina_7x24", payload=payload)
        rows = [_sina_document_from_item(item, ingested_at=fetched_at, raw_path=raw_path, parser_version=parser_version) for item in items if isinstance(item, dict)]
        rows.sort(key=lambda row: row.get("published_at", ""), reverse=True)
        rows = rows[: max(0, int(limit))]
        if fields:
            return pd.DataFrame(select_fields(rows, fields))
        return pd.DataFrame(rows)

    remaining = max(0, int(limit))
    page = 1
    seen_ids: set[str] = set()
    rows: list[dict[str, str]] = []
    # page_size 必须固定，否则新浪接口按 page*page_size 算偏移会导致翻页重叠。
    page_size = SINA_7X24_PAGE_SIZE
    while remaining > 0:
        data = _http_get_json(
            SINA_7X24_URL,
            params={"page": page, "page_size": page_size, "zhibo_id": 152, "tag_id": 0, "type": 0},
            headers={"User-Agent": UA, "Referer": "https://finance.sina.com.cn/7x24/"},
            timeout=timeout,
        )
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        raw_path = _write_raw(archive_root=archive_root, ingested_at=fetched_at, source=f"sina_7x24_p{page}", payload=payload)
        items = ((data.get("result") or {}).get("data") or {}).get("feed", {}).get("list", [])
        if not items:
            break
        new_rows = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            source_id = safe_text(item.get("id"))
            if source_id in seen_ids:
                continue
            seen_ids.add(source_id)
            published_at = _parse_cn_time(item.get("create_time"))
            published_day = published_at[:10] if published_at else ""
            if start_date and published_day and published_day < str(start_date)[:10]:
                continue
            if end_date and published_day and published_day > str(end_date)[:10]:
                continue
            rows.append(_sina_document_from_item(item, ingested_at=fetched_at, raw_path=raw_path, parser_version=parser_version))
            new_rows += 1
            remaining -= 1
            if remaining <= 0:
                break
        if new_rows == 0:
            break
        page += 1
    rows.sort(key=lambda row: row.get("published_at", ""), reverse=True)
    rows = rows[: max(0, int(limit))]
    if fields:
        return pd.DataFrame(select_fields(rows, fields))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 华尔街见闻实时快讯
# ---------------------------------------------------------------------------


def _wallstcn_document_from_item(item: dict[str, Any], *, ingested_at: str, raw_path: Path, parser_version: str) -> dict[str, str]:
    raw_text = safe_text(item.get("content_text")) or safe_text(item.get("content"))
    title = raw_text[:80] if raw_text else ""
    published_at = _parse_cn_time(item.get("display_time"))
    source_id = safe_text(item.get("uri") or item.get("id"))
    url = source_id if source_id.startswith("http") else f"https://wallstreetcn.com/livenews/{source_id}" if source_id else ""
    important = bool(item.get("is_important"))
    topics = ["important"] if important else []
    parse_status = "full_text" if raw_text else "title_only"
    return _base_document(
        provider="wallstcn_lives",
        source=WALLSTCN_LIVES_SOURCE,
        source_id=source_id,
        published_at=published_at,
        title=title,
        raw_text=raw_text,
        url=url,
        topics=topics,
        symbols=[],
        ingested_at=ingested_at,
        raw_path=raw_path,
        parser_version=parser_version,
        parse_status=parse_status,
    )


def fetch_wallstcn_lives(
    *,
    root: Path | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    fields: list[str] | None = None,
    limit: int = 100,
    fixture_dir: str | Path | None = None,
    raw_archive_dir: str | Path = DEFAULT_RAW_ARCHIVE_DIR,
    timeout: int = 20,
    parser_version: str = "wallstcn_lives_v1",
) -> pd.DataFrame:
    project_root = root or Path.cwd()
    archive_root = resolve_path(project_root, raw_archive_dir)
    fetched_at = now_iso()
    fixture_root = resolve_path(project_root, fixture_dir) if fixture_dir else None
    if fixture_root:
        candidates = [fixture_root / "wallstcn_lives.json", fixture_root / "wallstcn.json"]
        payload = next((c.read_bytes() for c in candidates if c.exists()), None)
        if payload is None:
            raise FileNotFoundError(f"wallstcn lives fixture not found under {fixture_root}")
        data = json.loads(payload.decode("utf-8"))
    else:
        data = _http_get_json(
            WALLSTCN_LIVES_URL,
            params={"channel": "global-channel", "limit": max(0, int(limit))},
            headers={"User-Agent": UA, "Referer": "https://wallstreetcn.com/", "Origin": "https://wallstreetcn.com"},
            timeout=timeout,
        )
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    raw_path = _write_raw(archive_root=archive_root, ingested_at=fetched_at, source="wallstcn_lives", payload=payload)
    items = (data.get("data") or {}).get("items") or []
    rows: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        published_at = _parse_cn_time(item.get("display_time"))
        published_day = published_at[:10] if published_at else ""
        if start_date and published_day and published_day < str(start_date)[:10]:
            continue
        if end_date and published_day and published_day > str(end_date)[:10]:
            continue
        rows.append(_wallstcn_document_from_item(item, ingested_at=fetched_at, raw_path=raw_path, parser_version=parser_version))
    rows.sort(key=lambda row: row.get("published_at", ""), reverse=True)
    rows = rows[: max(0, int(limit))]
    if fields:
        return pd.DataFrame(select_fields(rows, fields))
    return pd.DataFrame(rows)
