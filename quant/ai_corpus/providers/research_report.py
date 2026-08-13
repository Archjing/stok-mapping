"""券商研报元数据 provider（东财公开研报入口）。

严格遵循 AI 语料库「不做清单」：只存研报**元数据 + 授权摘要**（报告名称），
**不下载、不保存 PDF 全文**。``content_html`` / ``raw_text`` 一律留空，
``parse_status`` 固定 ``metadata_only``。

数据源：AkShare ``stock_research_report_em``（东方财富研报中心，公开元数据）。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from quant.ai_corpus.registry import RESEARCH_REPORT_PARSER_VERSION
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

RESEARCH_REPORT_SOURCE = "东方财富研报中心"
DEFAULT_RAW_ARCHIVE_DIR = "data/raw_data/ai_corpus/research_report"


def _date_only(value: Any) -> str:
    text = safe_text(value)
    return text[:10] if text else ""


def _write_raw_text(*, archive_root: Path, stem: str, text: str) -> Path:
    day = datetime.now().date().isoformat()
    path = archive_root / "search" / day.replace("-", "/") / f"{stem}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _read_fixture_frame(fixture_dir: Path) -> pd.DataFrame:
    for candidate in [fixture_dir / "research_reports.csv", fixture_dir / "reports.csv"]:
        if candidate.exists():
            return pd.read_csv(candidate)
    for candidate in [fixture_dir / "research_reports.json", fixture_dir / "reports.json"]:
        if candidate.exists():
            import json

            payload = json.loads(candidate.read_text(encoding="utf-8"))
            rows = payload.get("reports", payload) if isinstance(payload, dict) else payload
            return pd.DataFrame(rows)
    raise FileNotFoundError(f"research_report fixture not found under {fixture_dir}")


def _normalize_symbol(value: Any) -> str:
    """Normalize a stock code that lost leading zeros (CSV int coercion) to 6 digits."""
    text = safe_text(value)
    if not text:
        return ""
    if text.isdigit() and len(text) < 6:
        return text.zfill(6)
    return text


def parse_research_reports(
    frame: pd.DataFrame,
    *,
    raw_path: Path | None = None,
    ingested_at: str | None = None,
) -> list[dict[str, str]]:
    """Parse 东财研报元数据 rows into ai_corpus documents (metadata only)."""
    fetched_at = ingested_at or now_iso()
    documents: list[dict[str, str]] = []
    if frame.empty:
        return documents
    for raw in frame.to_dict(orient="records"):
        title = safe_text(raw.get("报告名称") or raw.get("report_name") or raw.get("title"))
        if not title:
            continue
        symbol = _normalize_symbol(raw.get("股票代码") or raw.get("symbol"))
        broker = safe_text(raw.get("机构") or raw.get("org") or raw.get("broker"))
        rating = safe_text(raw.get("东财评级") or raw.get("rating"))
        industry = safe_text(raw.get("行业") or raw.get("industry"))
        published_at = _date_only(raw.get("日期") or raw.get("date") or raw.get("published_at"))
        pdf_url = safe_text(raw.get("报告PDF链接") or raw.get("pdf_url") or raw.get("url"))

        # 授权摘要 = 报告名称本身；盈利预测入 topics 的 stat: 标签。
        stat_parts = [f"rating={rating}" if rating else "", f"industry={industry}" if industry else ""]
        for year in ("2026", "2027", "2028"):
            eps = raw.get(f"{year}-盈利预测-收益")
            pe = raw.get(f"{year}-盈利预测-市盈率")
            if eps is not None and pd.notna(eps) and safe_text(eps):
                stat_parts.append(f"eps_{year}={safe_text(eps)}")
            if pe is not None and pd.notna(pe) and safe_text(pe):
                stat_parts.append(f"pe_{year}={safe_text(pe)}")
        topics = f"研报\\{'|'.join(p for p in stat_parts if p)}" if stat_parts else "研报"

        content_hash = content_sha256(title)
        source_id = content_sha256(stable_dedupe_key(symbol, title, published_at, broker))[:24]
        dedupe_key = stable_dedupe_key(source_id, symbol, title, broker, published_at, content_hash)
        documents.append({
            "document_id": stable_document_id("research_report", source_id, content_hash),
            "corpus_type": "research_report",
            "event_type": "research_report",
            "provider": "research_report",
            "source": RESEARCH_REPORT_SOURCE,
            "source_id": source_id,
            "published_at": published_at,
            "issued_at": "",
            "ingested_at": fetched_at,
            "as_of_time": fetched_at,
            "title": title,
            "summary": title,  # 授权摘要 = 报告名称
            "content_html": "",  # 不做清单：不存全文
            "raw_text": "",  # 不做清单：不存全文
            "url": pdf_url,
            "org": broker,
            "pcode": "",
            "ptype": "equity_research",
            "symbols": symbol,
            "industries": industry,
            "topics": topics,
            "language": "zh-CN",
            "dedupe_key": dedupe_key,
            "content_hash": content_hash,
            "raw_path": str(raw_path) if raw_path else "",
            "parse_status": "metadata_only",
            "source_confidence": "public_rss_metadata",
            "parser_version": RESEARCH_REPORT_PARSER_VERSION,
        })
    return documents


def fetch_research_reports(
    *,
    keyword: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    symbols: list[str] | None = None,
    fields: list[str] | None = None,
    limit: int = 100,
    root: Path | None = None,
    fixture_dir: str | Path | None = None,
    raw_archive_dir: str | Path = DEFAULT_RAW_ARCHIVE_DIR,
    timeout: int = 20,
    ingested_at: str | None = None,
) -> pd.DataFrame:
    """Fetch broker research-report metadata (东财公开入口).

    只存元数据 + 授权摘要，不下载 PDF 全文。``symbols`` 为空时抓全市场列表，
    否则逐只抓取后合并。
    """
    project_root = root or Path.cwd()
    archive_root = resolve_path(project_root, raw_archive_dir)
    fetched_at = ingested_at or now_iso()

    frames: list[pd.DataFrame] = []
    if fixture_dir:
        frames.append(_read_fixture_frame(resolve_path(project_root, fixture_dir)))
    else:
        import akshare as ak

        for symbol in (symbols or [""]):
            try:
                frame = fetch_with_akshare_retries(
                    lambda s=symbol: ak.stock_research_report_em(symbol=s) if s else ak.stock_research_report_em()
                )
                frames.append(frame)
            except Exception:
                continue

    raw_payload = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if keyword:
        raw_payload = raw_payload[
            raw_payload["报告名称"].astype(str).str.contains(keyword, na=False)
        ] if not raw_payload.empty else raw_payload
    if start_date:
        raw_payload = raw_payload[
            raw_payload["日期"].astype(str) >= start_date
        ] if not raw_payload.empty else raw_payload
    if end_date:
        raw_payload = raw_payload[
            raw_payload["日期"].astype(str) <= end_date
        ] if not raw_payload.empty else raw_payload
    if limit >= 0:
        raw_payload = raw_payload.head(int(limit))

    raw_text = raw_payload.to_json(orient="records", force_ascii=False, date_format="iso")
    raw_path = _write_raw_text(
        archive_root=archive_root,
        stem=f"research_report_{datetime.now().strftime('%Y%m%d')}",
        text=raw_text,
    )
    documents = parse_research_reports(raw_payload, raw_path=raw_path, ingested_at=fetched_at)
    output_rows = select_fields(documents, fields)
    return pd.DataFrame(output_rows, columns=fields or AI_CORPUS_DOCUMENT_COLUMNS)
