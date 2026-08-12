"""Semiconductor supply-chain hard data from Chinese financial media reprints.

TSMC monthly revenue and Korea semiconductor exports are published by their
official sources (TSMC IR, Korea Customs Service) roughly 10 days / 1 day
after each reported month.  Both official sites are unreachable from this
network (Cloudflare 403 / DNS failure), so this provider parses the regular
Chinese financial-media reprints instead:

  - TSMC monthly revenue: reprints of the official release, e.g. title
    "创新高！台积电7月营收3231.66亿元新台币：同比增长25.8%"
  - Korea semiconductor exports: reprints of Korea Customs Service data,
    e.g. "韩国7月半导体出口额同比增长31.2%，连续四个月创新高", body carries
    the USD billion figure.

Source URLs are supplied explicitly (``source_urls``): the monthly search is
done by the caller (agent / cron) via web search; this provider fetches and
parses the located pages.  All documents are tagged
``source_confidence=media_reprint_of_official_disclosure`` to distinguish
them from first-party SIA releases.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from phase0.ai_corpus.registry import SEMI_SUPPLY_CHAIN_PARSER_VERSION
from phase0.ai_corpus.schema import (
    content_sha256,
    now_iso,
    resolve_path,
    safe_text,
    select_fields,
    stable_dedupe_key,
    stable_document_id,
)

DEFAULT_RAW_ARCHIVE_DIR = "data/raw_data/ai_corpus/semi_supply_chain"

# TSMC: "台积电7月营收3231.66亿元新台币：同比增长25.8%"
_TSMC_TITLE = re.compile(
    r"台积电(?P<month>\d{1,2})月营收(?P<revenue>[\d,\.]+)亿(?:元)?新台币[：:]\s*同比增长(?P<yoy>[\d\.]+)%"
)
# Korea: "韩国7月半导体出口额同比增长31.2%"
_KOREA_TITLE = re.compile(
    r"韩国(?P<month>\d{1,2})月半导体出口(?:额)?(?:同比)?增长(?P<yoy>[\d\.]+)%"
)
_KOREA_BODY_USD = re.compile(
    r"(?:半导体出口(?:额|金额)?(?:达|为|约)?\s*)(?P<usd>[\d,\.]+)\s*(?:亿美元|亿美元)",
    re.IGNORECASE,
)
_MONTH_CN = {
    "1": "01", "2": "02", "3": "03", "4": "04", "5": "05", "6": "06",
    "7": "07", "8": "08", "9": "09", "10": "10", "11": "11", "12": "12",
}
# Report year: infer from the article's publication year (reprints appear
# within ~2 days of the official release in the following month).
_KOREA_USD_FALLBACK = re.compile(r"半导体出口(?:额|金额)[^0-9]{0,20}([\d,\.]+)\s*亿")


def _safe_stem(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z_.-]+", "_", safe_text(value)).strip("._")[:100] or "page"


def _archive_path(*, archive_root: Path, ingested_at: str, slug: str) -> Path:
    stamp = safe_text(ingested_at) or now_iso()
    day = stamp[:10] or datetime.now(timezone.utc).date().isoformat()
    year, month, date_part = day.split("-")
    clock = re.sub(r"[^0-9]", "", stamp[11:])[:12] or "run"
    return archive_root / "html" / year / month / date_part / f"{_safe_stem(slug)}_{clock}.html"


def _write_raw(*, archive_root: Path, ingested_at: str, slug: str, payload: bytes) -> Path:
    path = _archive_path(archive_root=archive_root, ingested_at=ingested_at, slug=slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def _http_get(url: str, timeout: int) -> bytes:
    response = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": "stok-mapping/ai-corpus-semi-supply-chain"},
    )
    response.raise_for_status()
    return response.content


def _html_to_text(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.S | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;?", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _report_year(html: str, reported_month: str) -> str:
    """Infer the reported year from page metadata or publication date.

    Reprints are published in the calendar month following the reported
    month.  Use the page's published date when present; otherwise fall back
    to the current year.
    """
    for pattern in (
        r'"datePublished"\s*:\s*"(\d{4})-',
        r'published_time"\s*content="(\d{4})-',
        r'"pubDate"\s*:\s*"(\d{4})-',
    ):
        match = re.search(pattern, html)
        if match:
            return match.group(1)
    return str(datetime.now(timezone.utc).year)


def _parse_tsmc(html: str, title: str) -> dict[str, str]:
    text = _html_to_text(html)
    match = _TSMC_TITLE.search(title) or _TSMC_TITLE.search(text)
    if not match:
        return {}
    month = _MONTH_CN.get(match.group("month"), match.group("month").zfill(2))
    year = _report_year(html, month)
    revenue_ntd_million = match.group("revenue").replace(",", "")  # 亿元 → 百万? no: 亿元 = 100 million NTD
    return {
        "report_period": f"{year}-{month}",
        "period_kind": "month",
        "revenue_ntd_billion": str(round(float(revenue_ntd_million) / 10.0, 2)),  # 亿元 → 十亿
        "yoy_pct": match.group("yoy"),
        "text": text,
    }


def _parse_korea(html: str, title: str) -> dict[str, str]:
    text = _html_to_text(html)
    title_match = _KOREA_TITLE.search(title)
    if not title_match:
        return {}
    month = _MONTH_CN.get(title_match.group("month"), title_match.group("month").zfill(2))
    year = _report_year(html, month)
    usd_match = _KOREA_BODY_USD.search(text)
    exports_usd_billion = usd_match.group("usd").replace(",", "") if usd_match else ""
    return {
        "report_period": f"{year}-{month}",
        "period_kind": "month",
        "exports_usd_billion": exports_usd_billion,
        "yoy_pct": title_match.group("yoy"),
        "text": text,
    }


def _document_from_parse(
    *,
    corpus_type: str,
    url: str,
    parsed: dict[str, str],
    ingested_at: str,
    raw_path: Path,
    stat_fields: list[str],
) -> dict[str, str]:
    title = safe_text(parsed.get("title"))
    text = safe_text(parsed.get("text"))
    content_hash = content_sha256("|".join([title, url]))
    structured = " ".join(
        part
        for part in [
            f"period={parsed.get('report_period')}" if parsed.get("report_period") else "",
            *[
                f"{field}={parsed.get(field)}" if parsed.get(field) else ""
                for field in stat_fields
            ],
            f"yoy_pct={parsed.get('yoy_pct')}" if parsed.get("yoy_pct") else "",
        ]
        if part
    )
    topics = [
        "semiconductor-cycle",
        "industry-statistics",
        "supply-chain",
        f"report:{parsed.get('period_kind') or 'unknown'}",
    ]
    if structured:
        topics.append(f"stat:{structured}")
    return {
        "document_id": stable_document_id(corpus_type, url, content_hash),
        "corpus_type": corpus_type,
        "event_type": "industry_sales_report",
        "provider": "semi_supply_chain",
        "source": safe_text(parsed.get("source")),
        "source_id": url,
        "published_at": safe_text(parsed.get("published_at")),
        "issued_at": "",
        "ingested_at": ingested_at,
        "as_of_time": ingested_at,
        "title": title,
        "summary": text[:2000],
        "content_html": "",
        "raw_text": text,
        "url": url,
        "org": safe_text(parsed.get("org")),
        "pcode": safe_text(parsed.get("report_period")),
        "ptype": safe_text(parsed.get("period_kind")),
        "symbols": "",
        "industries": "semiconductor",
        "topics": "\\".join(topics),
        "language": "zh-CN",
        "dedupe_key": stable_dedupe_key(corpus_type, url, url, title, safe_text(parsed.get("published_at"))),
        "content_hash": content_hash,
        "raw_path": str(raw_path),
        "parse_status": "content_extracted",
        "source_confidence": "media_reprint_of_official_disclosure",
        "parser_version": SEMI_SUPPLY_CHAIN_PARSER_VERSION,
    }


def _page_meta(html: str) -> dict[str, str]:
    title_match = re.search(r"<title>([^<]*)</title>", html, re.I)
    title = title_match.group(1).split(" - ")[0].split(" | ")[0].strip() if title_match else ""
    date_match = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html) or re.search(
        r'published_time"\s*content="([^"]+)"', html
    )
    source = ""
    source_match = re.search(r'"source"\s*:\s*"([^"]+)"', html)
    if source_match:
        source = source_match.group(1)
    return {
        "title": title,
        "published_at": date_match.group(1) if date_match else "",
        "source": source,
        "org": source or "Chinese financial media",
    }


def _parse_page(*, corpus_type: str, html: str, url: str, ingested_at: str, raw_path: Path) -> dict[str, str]:
    meta = _page_meta(html)
    if corpus_type == "tsmc_monthly_revenue":
        parsed = _parse_tsmc(html, meta["title"])
        stat_fields = ["revenue_ntd_billion"]
    elif corpus_type == "korea_semi_exports":
        parsed = _parse_korea(html, meta["title"])
        stat_fields = ["exports_usd_billion"]
    else:
        return {}
    if not parsed or not parsed.get("report_period"):
        return {}
    parsed.update(meta)
    if not parsed.get("published_at"):
        # Reprint pages often lack machine-readable publish dates. Fall back
        # to the 1st of the month after the reported period (official release
        # cadence); deterministic across runs so dedupe keys stay stable.
        year, month = parsed["report_period"].split("-")
        next_month = int(month) + 1
        if next_month > 12:
            year, next_month = str(int(year) + 1), 1
        parsed["published_at"] = f"{year}-{next_month:02d}-01"
    return _document_from_parse(
        corpus_type=corpus_type,
        url=url,
        parsed=parsed,
        ingested_at=ingested_at,
        raw_path=raw_path,
        stat_fields=stat_fields,
    )


def fetch_semiconductor_supply_chain(
    *,
    root: Path | None = None,
    provider_config: dict[str, Any] | None = None,
    keyword: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    fields: list[str] | None = None,
    limit: int = 20,
    fixture_dir: str | Path | None = None,
    raw_archive_dir: str | Path = DEFAULT_RAW_ARCHIVE_DIR,
    timeout: int = 20,
    include_content: bool = True,
    ingested_at: str | None = None,
    source_urls: list[str] | None = None,
) -> pd.DataFrame:
    """Fetch and parse semiconductor supply-chain reprint pages.

    ``source_urls`` is the primary input: the caller locates the monthly
    reprints (web search) and passes the URLs here.  In fixture mode, all
    HTML files in ``fixture_dir`` are parsed; the URL is rebuilt from the
    filename prefix.
    """
    project_root = root or Path.cwd()
    archive_root = resolve_path(project_root, raw_archive_dir)
    fetched_at = ingested_at or now_iso()
    config = provider_config or {}
    rows: list[dict[str, str]] = []
    fixture_root = resolve_path(project_root, fixture_dir) if fixture_dir else None

    if fixture_root:
        pages = sorted(fixture_root.glob("*.html"))
        if not pages:
            raise FileNotFoundError(f"semiconductor supply chain fixture not found in {fixture_root}")
        for page in pages[: max(0, int(limit))]:
            corpus_type = (
                "tsmc_monthly_revenue" if page.stem.startswith("tsmc") else "korea_semi_exports"
            )
            payload = page.read_bytes()
            url = f"https://example.test/semi-supply-chain/{page.stem}"
            raw_path = _write_raw(archive_root=archive_root, ingested_at=fetched_at, slug=page.stem, payload=payload)
            document = _parse_page(
                corpus_type=corpus_type,
                html=payload.decode("utf-8", errors="ignore"),
                url=url,
                ingested_at=fetched_at,
                raw_path=raw_path,
            )
            if document:
                rows.append(document)
        return pd.DataFrame(select_fields(rows, fields)) if fields else pd.DataFrame(rows)

    urls = [safe_text(item) for item in (source_urls or config.get("source_urls") or []) if safe_text(item)]
    for url in list(dict.fromkeys(urls))[: max(0, int(limit))]:
        try:
            payload = _http_get(url, timeout)
        except Exception:
            continue
        decoded = payload.decode("utf-8", errors="ignore")
        meta = _page_meta(decoded)
        combined = f"{meta.get('title', '')} {url}".casefold()
        if "台积电" in combined or "tsmc" in combined:
            corpus_type = "tsmc_monthly_revenue"
        else:
            corpus_type = "korea_semi_exports"
        slug = url.rstrip("/").split("/")[-1] or "page"
        raw_path = _write_raw(archive_root=archive_root, ingested_at=fetched_at, slug=slug, payload=payload)
        document = _parse_page(
            corpus_type=corpus_type,
            html=decoded,
            url=url,
            ingested_at=fetched_at,
            raw_path=raw_path,
        )
        if document:
            published_day = document.get("published_at", "")[:10]
            if start_date and published_day and published_day < str(start_date)[:10]:
                continue
            if end_date and published_day and published_day > str(end_date)[:10]:
                continue
            if keyword and keyword.casefold() not in document.get("raw_text", "").casefold():
                continue
            rows.append(document)

    rows.sort(key=lambda row: row.get("published_at", ""), reverse=True)
    if fields:
        return pd.DataFrame(select_fields(rows, fields))
    return pd.DataFrame(rows)
