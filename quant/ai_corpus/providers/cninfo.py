from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pandas as pd

from quant.ai_corpus.registry import CNINFO_PARSER_VERSION
from quant.ai_corpus.schema import (
    AI_CORPUS_DOCUMENT_COLUMNS,
    content_sha256,
    now_iso,
    resolve_path,
    safe_text,
    select_fields,
    stable_dedupe_key,
    stable_document_id,
)
from quant.data_access.throttle import fetch_with_akshare_retries

CNINFO_SOURCE = "巨潮资讯"
DEFAULT_RAW_ARCHIVE_DIR = "data/raw_data/ai_corpus/cninfo"

CNINFO_EVENT_CATEGORY_MAP = {
    "announcement": "",
    "risk_events": "风险提示",
    "abnormal_trading": "风险提示",
    "trading_risk_warning": "风险提示",
    "severe_abnormal_trading": "风险提示",
    "earnings_forecast": "业绩预告",
    "major_contract": "日常经营",
    "shareholder_change": "股权变动",
    "share_buyback": "",
    "share_increase": "",
    "share_decrease": "",
    "dividend": "",
}

CNINFO_EVENT_KEYWORDS = {
    "risk_events": ("异常波动", "交易风险提示", "严重异常波动"),
    "abnormal_trading": ("异常波动",),
    "trading_risk_warning": ("交易风险提示", "风险提示"),
    "severe_abnormal_trading": ("严重异常波动",),
    "earnings_forecast": ("业绩预告",),
    "major_contract": ("重大合同", "合同"),
    "shareholder_change": ("股东", "权益变动", "持股变动"),
    "share_buyback": ("回购",),
    "share_increase": ("增持",),
    "share_decrease": ("减持",),
    "dividend": ("分红", "权益分派", "利润分配"),
}

EXCLUDED_RISK_WARNING_KEYWORDS = ("可转债", "适当性", "退市风险警示", "终止上市")


def _date_only(value: Any) -> str:
    text = safe_text(value)
    if not text:
        return ""
    if re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    match = re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", text)
    if match:
        year, month, day = [int(part) for part in match.group(0).replace("/", "-").split("-")]
        return f"{year:04d}-{month:02d}-{day:02d}"
    try:
        parsed = pd.to_datetime(text, errors="raise")
    except Exception:
        return text[:10]
    if pd.isna(parsed):
        return ""
    return parsed.strftime("%Y-%m-%d")


def _compact_date(value: str | None) -> str:
    day = _date_only(value)
    return day.replace("-", "") if day else ""


def _safe_stem(value: str) -> str:
    text = re.sub(r"[^0-9A-Za-z_.-]+", "_", value).strip("._")
    return text[:120] or "raw"


def _archive_path(*, archive_root: Path, ingested_at: str, stem: str, suffix: str) -> Path:
    day = _date_only(ingested_at) or datetime.now().date().isoformat()
    year, month, date_part = day.split("-")
    return archive_root / "search" / year / month / date_part / f"{_safe_stem(stem)}.{suffix}"


def _write_raw_text(*, archive_root: Path, ingested_at: str, stem: str, suffix: str, text: str) -> Path:
    path = _archive_path(archive_root=archive_root, ingested_at=ingested_at, stem=stem, suffix=suffix)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _read_fixture_frame(fixture_dir: Path) -> pd.DataFrame:
    for candidate in [fixture_dir / "cninfo_announcements.csv", fixture_dir / "announcements.csv"]:
        if candidate.exists():
            return pd.read_csv(candidate)
    for candidate in [fixture_dir / "cninfo_announcements.json", fixture_dir / "announcements.json"]:
        if candidate.exists():
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            rows = payload.get("announcements", payload) if isinstance(payload, dict) else payload
            return pd.DataFrame(rows)
    raise FileNotFoundError(f"cninfo announcement fixture not found under {fixture_dir}")


def _fetch_live_frame(
    *,
    symbol: str,
    start_date: str | None,
    end_date: str | None,
    keyword: str,
    category: str,
) -> pd.DataFrame:
    import akshare as ak

    start = _compact_date(start_date) or datetime.now().date().strftime("%Y%m%d")
    end = _compact_date(end_date) or start
    return fetch_with_akshare_retries(
        lambda: ak.stock_zh_a_disclosure_report_cninfo(
            symbol=symbol,
            market="沪深京",
            keyword=keyword,
            category=category,
            start_date=start,
            end_date=end,
        )
    )


def _first_present(row: dict[str, Any], names: list[str]) -> str:
    for name in names:
        value = safe_text(row.get(name))
        if value:
            return value
    return ""


def _source_id_from_url(url: str) -> str:
    query = parse_qs(urlparse(url).query)
    for key in ["announcementId", "announcementid", "id"]:
        values = query.get(key)
        if values:
            return safe_text(values[0])
    match = re.search(r"announcementId=([^&]+)", url)
    return safe_text(match.group(1) if match else "")


def _classify_event_type(title: str, requested_event_type: str) -> str:
    if requested_event_type and requested_event_type not in {"announcement", "risk_events"}:
        return requested_event_type
    if "严重异常波动" in title:
        return "severe_abnormal_trading"
    if "异常波动" in title:
        return "abnormal_trading"
    if "交易风险提示" in title:
        return "trading_risk_warning"
    if "业绩预告" in title:
        return "earnings_forecast"
    return "announcement"


def _passes_event_filter(title: str, event_type: str) -> bool:
    if event_type in {"", "announcement"}:
        return True
    keywords = CNINFO_EVENT_KEYWORDS.get(event_type, ())
    if keywords and not any(keyword in title for keyword in keywords):
        return False
    if event_type == "trading_risk_warning" and any(keyword in title for keyword in EXCLUDED_RISK_WARNING_KEYWORDS):
        return False
    return True


def parse_cninfo_announcements(
    frame: pd.DataFrame,
    *,
    event_type: str = "announcement",
    raw_path: Path | None = None,
    ingested_at: str | None = None,
) -> list[dict[str, str]]:
    fetched_at = ingested_at or now_iso()
    documents: list[dict[str, str]] = []
    if frame.empty:
        return documents
    for raw in frame.to_dict(orient="records"):
        title = _first_present(raw, ["公告标题", "announcementTitle", "title"])
        if not title:
            continue
        classified_event = _classify_event_type(title, event_type)
        if not _passes_event_filter(title, event_type):
            continue
        symbol = _first_present(raw, ["代码", "secCode", "symbol"])
        short_name = _first_present(raw, ["简称", "secName", "name"])
        published_at = _date_only(_first_present(raw, ["公告时间", "announcementTime", "published_at", "date"]))
        url = _first_present(raw, ["公告链接", "url", "adjunctUrl"])
        source_id = _first_present(raw, ["announcementId", "id", "source_id"]) or _source_id_from_url(url)
        if not source_id:
            source_id = content_sha256(stable_dedupe_key(symbol, title, published_at, url))[:24]
        summary = _first_present(raw, ["summary", "摘要"])
        raw_text = "\n".join(part for part in [title, summary] if part)
        content_hash = content_sha256(raw_text or title)
        dedupe_key = stable_dedupe_key(source_id, url, symbol, title, published_at, content_hash)
        documents.append(
            {
                "document_id": stable_document_id("cninfo", source_id, content_hash),
                "corpus_type": "announcement",
                "event_type": classified_event,
                "provider": "cninfo",
                "source": CNINFO_SOURCE,
                "source_id": source_id,
                "published_at": published_at,
                "issued_at": "",
                "ingested_at": fetched_at,
                "as_of_time": fetched_at,
                "title": title,
                "summary": summary,
                "content_html": "",
                "raw_text": raw_text,
                "url": url,
                "org": short_name or CNINFO_SOURCE,
                "pcode": "",
                "ptype": classified_event,
                "symbols": symbol,
                "industries": "",
                "topics": f"公告\\{classified_event}",
                "language": "zh-CN",
                "dedupe_key": dedupe_key,
                "content_hash": content_hash,
                "raw_path": str(raw_path) if raw_path else "",
                "parse_status": "ok" if url else "partial",
                "source_confidence": "official_public_source",
                "parser_version": CNINFO_PARSER_VERSION,
            }
        )
    return documents


def fetch_cninfo_announcements(
    *,
    event_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    keyword: str | None = None,
    symbols: list[str] | None = None,
    fields: list[str] | None = None,
    limit: int = 100,
    root: Path | None = None,
    fixture_dir: str | Path | None = None,
    raw_archive_dir: str | Path = DEFAULT_RAW_ARCHIVE_DIR,
    ingested_at: str | None = None,
) -> pd.DataFrame:
    project_root = root or Path.cwd()
    archive_root = resolve_path(project_root, raw_archive_dir)
    fetched_at = ingested_at or now_iso()
    requested_event = safe_text(event_type) or "announcement"
    category = CNINFO_EVENT_CATEGORY_MAP.get(requested_event, "")
    query_keyword = safe_text(keyword)
    if not query_keyword and requested_event not in {"", "announcement", "risk_events"}:
        query_keyword = (CNINFO_EVENT_KEYWORDS.get(requested_event) or ("",))[0]
    symbol_list = symbols or [""]

    frames: list[pd.DataFrame] = []
    if fixture_dir:
        frame = _read_fixture_frame(resolve_path(project_root, fixture_dir))
        frames.append(frame)
    else:
        for symbol in symbol_list:
            frame = _fetch_live_frame(
                symbol=safe_text(symbol),
                start_date=start_date,
                end_date=end_date,
                keyword=query_keyword,
                category=category,
            )
            frames.append(frame)

    raw_payload = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if limit >= 0:
        raw_payload = raw_payload.head(int(limit))
    raw_text = raw_payload.to_json(orient="records", force_ascii=False, date_format="iso")
    raw_path = _write_raw_text(
        archive_root=archive_root,
        ingested_at=fetched_at,
        stem=f"cninfo_{requested_event}_{_compact_date(start_date) or 'na'}_{_compact_date(end_date) or 'na'}",
        suffix="json",
        text=raw_text,
    )
    documents = parse_cninfo_announcements(
        raw_payload,
        event_type=requested_event,
        raw_path=raw_path,
        ingested_at=fetched_at,
    )
    if limit >= 0:
        documents = documents[: int(limit)]
    output_rows = select_fields(documents, fields)
    return pd.DataFrame(output_rows, columns=fields or AI_CORPUS_DOCUMENT_COLUMNS)
