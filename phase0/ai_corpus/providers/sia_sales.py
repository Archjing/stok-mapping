"""SIA monthly global semiconductor sales press releases.

SIA (semiconductors.org) publishes one press release per month with the
WSTS-compiled global semiconductor sales figure (3-month moving average).
Release cadence: ~5 weeks after the reported month closes.

The press releases are regular HTML pages (WordPress), not RSS.  We fetch
the "latest news" listing and keep URLs matching the canonical sales-release
slug (``global-semiconductor-sales-...``), then parse each article body for:

  - reported month/quarter (e.g. 2026-05 or 2026Q2)
  - global sales (USD billions)
  - month-over-month change (%)
  - year-over-year change (%)

Structured values are stored via the fixed 30-column corpus schema:
  pcode   -> report period (YYYY-MM or YYYYQn)
  summary -> first content paragraph (the canonical data sentence)
  raw_text-> full article text
  topics  -> semiconductor-cycle / industry-statistics / monthly-report tags
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import pandas as pd
import requests

from phase0.ai_corpus.registry import SIA_SALES_PARSER_VERSION
from phase0.ai_corpus.schema import (
    content_sha256,
    now_iso,
    resolve_path,
    safe_text,
    select_fields,
    stable_dedupe_key,
    stable_document_id,
)

SIA_SALES_SOURCE = "SIA semiconductors.org press releases"
SIA_BASE_URL = "https://www.semiconductors.org/"
SIA_NEWS_LISTING = "https://www.semiconductors.org/news-events/latest-news/"
DEFAULT_RAW_ARCHIVE_DIR = "data/raw_data/ai_corpus/sia_sales"

# Canonical slug for monthly/quarterly sales press releases.
SALES_RELEASE_SLUG = re.compile(r"global-semiconductor-sales-")

# "were $120.6 billion during the month of May 2026, an increase of 9.2%
#  compared to the April 2026 total of $110.5 billion and 104.1% more than
#  the May 2025 total of $59.1 billion."
# Note: split into small patterns because decimals break naive sentence regexes.
_SALES_TOTAL = re.compile(r"were\s+\$(?P<sales>[\d,\.]+)\s+billion", re.IGNORECASE)
_REPORT_MONTH = re.compile(r"month of\s+(?P<month>[A-Za-z]+)\s+(?P<year>\d{4})", re.IGNORECASE)
_REPORT_QUARTER = re.compile(
    r"during the (?P<quarter>first|second|third|fourth) quarter of (?P<year>\d{4})",
    re.IGNORECASE,
)
_QUARTER_SLUG = re.compile(r"from-q(\d)-(\d{4})-to-q(\d)-(\d{4})", re.IGNORECASE)
_QUARTER_TITLE = re.compile(r"from\s*Q(\d)\s*(\d{4})\s*to\s*Q(\d)\s*(\d{4})", re.IGNORECASE)
_QOQ_PCT = re.compile(r"increase of\s+(?P<value>[\d\.]+)%\s+compared to\s+Q(?P<q>\d)", re.IGNORECASE)
_MOM_PCT = re.compile(r"increase of\s+(?P<value>[\d\.]+)%", re.IGNORECASE)
_MOM_DEC = re.compile(r"decrease of\s+(?P<value>[\d\.]+)%", re.IGNORECASE)
_YOY_PCT = re.compile(r"and\s+(?P<value>[\d\.]+)%\s+(?:more|less) than", re.IGNORECASE)

# SIA changed the release template around 2023. Both forms carry two
# percentages; the reference month after "more than" disambiguates them:
#   new form: "increase of X% compared to the {prev-month} total ... and
#              Y% more than the {same-month-last-year} total"  (X=MoM, Y=YoY)
#   old form: "increase of X% over the {same-month-last-year} total ... and
#              Y% more than the {prev-month} total"           (X=YoY, Y=MoM)
_TWO_PCT = re.compile(
    r"increase of\s+(?P<a>[\d\.]+)%\s+(?:compared to|over)\s+the\s+"
    r"(?P<m1>[A-Za-z]+)\s+(?P<y1>\d{4})\s+total[^.]*?"
    r"and\s+(?P<b>[\d\.]+)%\s+(?:more|less) than\s+the\s+"
    r"(?P<m2>[A-Za-z]+)\s+(?P<y2>\d{4})\s+total",
    re.IGNORECASE | re.DOTALL,
)
_MONTH_NUM = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}


def _prev_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _split_mom_yoy(text: str, report_year: str, report_month: str) -> tuple[str, str]:
    """Return (mom_pct, yoy_pct) tolerant of both SIA sentence templates."""
    pair = _TWO_PCT.search(text)
    if pair:
        m1_num = _MONTH_NUM.get(pair.group("m1").casefold())
        m2_num = _MONTH_NUM.get(pair.group("m2").casefold())
        try:
            rep_num = _MONTH_NUM[report_month.casefold()]
            rep_year_num = int(report_year)
        except (KeyError, ValueError):
            return "", ""
        first, second = pair.group("a"), pair.group("b")
        prev_year, prev_num = _prev_month(rep_year_num, rep_num)
        # Whichever reference lands on the previous month is the MoM figure.
        if pair.group("y1") == str(prev_year) and m1_num == prev_num:
            return first, second  # new form: X% compared to prev month
        if pair.group("y2") == str(prev_year) and m2_num == prev_num:
            return second, first  # old form: Y% more than prev month
        # No prev-month reference found; assume the template's default order.
        return first, second
    mom = _MOM_PCT.search(text) or _MOM_DEC.search(text)
    mom_value = mom.group("value") if mom else ""
    if mom_value and _MOM_DEC.search(text):
        mom_value = f"-{mom_value}"
    yoy = _YOY_PCT.search(text)
    return mom_value, (yoy.group("value") if yoy else "")


def _safe_stem(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z_.-]+", "_", safe_text(value)).strip("._")[:100] or "release"


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
        headers={"User-Agent": "stok-mapping/ai-corpus-sia-sales"},
    )
    response.raise_for_status()
    return response.content


def _html_to_text(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.S | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = re.sub(r"\n+", "\n", text)
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def _parse_release(html: str) -> dict[str, str]:
    """Parse one SIA sales press release into structured fields."""
    title_match = re.search(r"<title>([^<]*)</title>", html, re.I)
    title = title_match.group(1).replace(" - Semiconductor Industry Association", "").strip() if title_match else ""

    date_match = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html)
    published_at = date_match.group(1) if date_match else ""

    text = _html_to_text(html)
    # Quarterly releases lead with "were $403.3 billion during the second
    # quarter of 2026, an increase of 35.1% compared to Q1 of 2026"; the
    # monthly sentence (if any) follows. Detect the quarter form first.
    quarter_slug = _QUARTER_SLUG.search(title)
    quarter_title = _QUARTER_TITLE.search(title)
    quarter_sentence = _REPORT_QUARTER.search(text)
    if quarter_sentence or quarter_slug or quarter_title:
        if quarter_slug:
            report_period = f"{quarter_slug.group(4)}Q{quarter_slug.group(3)}"
        elif quarter_title:
            report_period = f"{quarter_title.group(4)}Q{quarter_title.group(3)}"
        else:
            report_period = f"{quarter_sentence.group('year')}Q{quarter_sentence.group('quarter')[0]}"
        period_kind = "quarter"
        # Sales total: prefer the figure tied to the quarter sentence. The
        # quarter regex matches "during the second quarter of ...", which sits
        # AFTER "were $403.3 billion" — walk back to the preceding "were $".
        if quarter_sentence:
            qidx = max(0, text.rfind("were", 0, quarter_sentence.start()))
        else:
            qidx = 0
        window = text[qidx : qidx + 300]
        sales_match = _SALES_TOTAL.search(window) or _SALES_TOTAL.search(text)
        sales = sales_match.group("sales").replace(",", "") if sales_match else ""
        qoq = _QOQ_PCT.search(text)
        mom_value = ""
        yoy_value = ""
        if qoq:
            qoq_value = qoq.group("value")
        else:
            qoq_value = ""
        parsed_extra = {"qoq_pct": qoq_value}
    else:
        sales_match = _SALES_TOTAL.search(text)
        sales = sales_match.group("sales").replace(",", "") if sales_match else ""
        month_match = _REPORT_MONTH.search(text)
        report_month = month_match.group("month") if month_match else ""
        report_year = month_match.group("year") if month_match else ""
        if report_month and report_year:
            report_period = f"{report_year}-{report_month}"
            period_kind = "month"
        else:
            report_period = ""
            period_kind = "unknown"
        mom_value, yoy_value = _split_mom_yoy(text, report_year, report_month)
        parsed_extra = {"qoq_pct": ""}

    return {
        "title": title,
        "published_at": published_at,
        "report_period": report_period,
        "period_kind": period_kind,
        "sales_usd_billion": sales,
        "mom_pct": mom_value,
        "yoy_pct": yoy_value,
        "qoq_pct": parsed_extra["qoq_pct"],
        "text": text,
    }


def _listing_links(html: str) -> list[str]:
    links: list[str] = []
    # Listing pages carry both relative ("/global-...") and absolute
    # ("https://www.semiconductors.org/global-...") hrefs.
    for match in re.finditer(
        r'href="((?:https?://(?:www\.)?semiconductors\.org)?/global-semiconductor-sales-[^"]*)"',
        html,
        re.I,
    ):
        url = urljoin(SIA_BASE_URL, match.group(1))
        if url not in links:
            links.append(url)
    return links


def _document_from_release(
    *,
    url: str,
    parsed: dict[str, str],
    ingested_at: str,
    raw_path: Path,
) -> dict[str, str]:
    title = safe_text(parsed.get("title"))
    text = safe_text(parsed.get("text"))
    summary = text.split("\n")[0][:2000] if text else ""
    source_id = url
    content_hash = content_sha256("|".join([title, url]))
    structured = " ".join(
        part
        for part in [
            f"period={parsed.get('report_period')}" if parsed.get("report_period") else "",
            f"sales_usd_billion={parsed.get('sales_usd_billion')}" if parsed.get("sales_usd_billion") else "",
            f"mom_pct={parsed.get('mom_pct')}" if parsed.get("mom_pct") else "",
            f"yoy_pct={parsed.get('yoy_pct')}" if parsed.get("yoy_pct") else "",
            f"qoq_pct={parsed.get('qoq_pct')}" if parsed.get("qoq_pct") else "",
        ]
        if part
    )
    topics = [
        "semiconductor-cycle",
        "industry-statistics",
        "global-sales",
        f"report:{parsed.get('period_kind') or 'unknown'}",
    ]
    if structured:
        topics.append(f"stat:{structured}")
    return {
        "document_id": stable_document_id("sia_sales", source_id, content_hash),
        "corpus_type": "sia_sales_news",
        "event_type": "industry_sales_report",
        "provider": "sia_sales",
        "source": SIA_SALES_SOURCE,
        "source_id": source_id,
        "published_at": safe_text(parsed.get("published_at")),
        "issued_at": "",
        "ingested_at": ingested_at,
        "as_of_time": ingested_at,
        "title": title,
        "summary": summary,
        "content_html": "",
        "raw_text": text,
        "url": url,
        "org": "SIA / WSTS",
        "pcode": safe_text(parsed.get("report_period")),
        "ptype": safe_text(parsed.get("period_kind")),
        "symbols": "",
        "industries": "semiconductor",
        "topics": "\\".join(topics),
        "language": "en-US",
        "dedupe_key": stable_dedupe_key("sia_sales", source_id, url, title, safe_text(parsed.get("published_at"))),
        "content_hash": content_hash,
        "raw_path": str(raw_path),
        "parse_status": "content_extracted",
        "source_confidence": "official_industry_association",
        "parser_version": SIA_SALES_PARSER_VERSION,
    }


def _month_sequence(start_date: str | None, end_date: str | None) -> list[tuple[int, int]]:
    """Yield (year, month) pairs from start_date to end_date (inclusive)."""
    from datetime import date as _date

    start = _date.fromisoformat(str(start_date)[:10]) if start_date else None
    end = _date.fromisoformat(str(end_date)[:10]) if end_date else None
    if start is None:
        return []
    end = end or _date.today()
    months: list[tuple[int, int]] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append((year, month))
        month += 1
        if month > 12:
            month = 1
            year += 1
        if len(months) > 240:
            break
    return months


def _archive_listing_links(*, project_root: Path, archive_root: Path, fetched_at: str,
                           months: list[tuple[int, int]], listing_url: str, timeout: int) -> list[str]:
    """Collect sales-release links from WordPress monthly archive pages."""
    links: list[str] = []
    for year, month in months:
        archive_url = urljoin(SIA_BASE_URL, f"/{year}/{month:02d}/")
        payload = _http_get(archive_url, timeout)
        _write_raw(archive_root=archive_root, ingested_at=fetched_at, slug=f"archive_{year}_{month:02d}", payload=payload)
        links.extend(_listing_links(payload.decode("utf-8", errors="ignore")))
        time.sleep(0.3)
    return list(dict.fromkeys(links))


def fetch_sia_sales(
    *,
    root: Path | None = None,
    provider_config: dict[str, Any] | None = None,
    keyword: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    fields: list[str] | None = None,
    limit: int = 12,
    fixture_dir: str | Path | None = None,
    raw_archive_dir: str | Path = DEFAULT_RAW_ARCHIVE_DIR,
    timeout: int = 20,
    include_content: bool = True,
    ingested_at: str | None = None,
    pages: int = 1,
) -> pd.DataFrame:
    """Fetch SIA global semiconductor sales press releases.

    Lists the latest-news page (and optional pagination), keeps only the
    canonical sales-release slugs, parses each release body, and returns
    normalized ai-corpus documents.
    """
    project_root = root or Path.cwd()
    archive_root = resolve_path(project_root, raw_archive_dir)
    fetched_at = ingested_at or now_iso()
    config = provider_config or {}
    listing_url = safe_text(config.get("listing_url")) or SIA_NEWS_LISTING
    max_pages = max(1, int(config.get("pages", pages)))

    rows: list[dict[str, str]] = []
    fixture_root = resolve_path(project_root, fixture_dir) if fixture_dir else None

    if fixture_root:
        # Fixture mode: article pages are named by release slug; an optional
        # listing.html provides the links, otherwise every release page is used.
        html_pages = sorted(fixture_root.glob("*.html"))
        if not html_pages:
            raise FileNotFoundError(f"SIA sales fixture not found in {fixture_root}")
        release_pages = [p for p in html_pages if "global-semiconductor-sales" in p.name]
        listing_page = fixture_root / "listing.html"
        links = []
        if listing_page.exists():
            links = _listing_links(listing_page.read_text(encoding="utf-8", errors="ignore"))
        if not links:
            links = [urljoin(SIA_BASE_URL, f"/{page.stem}/") for page in release_pages]
        for link in list(dict.fromkeys(links))[: max(0, int(limit))]:
            slug = link.rstrip("/").split("/")[-1]
            article_path = next(
                (p for p in release_pages if slug.replace("-", "") in p.stem.replace("-", "")),
                None,
            )
            if article_path is None:
                continue
            article_payload = article_path.read_bytes()
            raw_path = _write_raw(archive_root=archive_root, ingested_at=fetched_at, slug=slug, payload=article_payload)
            parsed = _parse_release(article_payload.decode("utf-8", errors="ignore"))
            rows.append(_document_from_release(url=link, parsed=parsed, ingested_at=fetched_at, raw_path=raw_path))
        return pd.DataFrame(select_fields(rows, fields)) if fields else pd.DataFrame(rows)

    # Historical date ranges: use WordPress monthly archive pages (one request
    # per month, precise) instead of digging through listing pagination.
    months = _month_sequence(start_date, end_date)
    use_archive = bool(months)

    if use_archive:
        links = _archive_listing_links(
            project_root=project_root,
            archive_root=archive_root,
            fetched_at=fetched_at,
            months=months,
            listing_url=listing_url,
            timeout=timeout,
        )
    else:
        links = []
        for page_index in range(1, max_pages + 1):
            page_url = listing_url if page_index == 1 else urljoin(SIA_BASE_URL, f"/news-events/latest-news/page/{page_index}/")
            payload = _http_get(page_url, timeout)
            _write_raw(archive_root=archive_root, ingested_at=fetched_at, slug=f"listing_p{page_index}", payload=payload)
            links.extend(_listing_links(payload.decode("utf-8", errors="ignore")))
            time.sleep(0.3)

    rows = []
    for link in list(dict.fromkeys(links))[: max(0, int(limit))]:
        published_day = ""
        try:
            payload = _http_get(link, timeout)
        except Exception:
            continue
        slug = link.rstrip("/").split("/")[-1]
        raw_path = _write_raw(archive_root=archive_root, ingested_at=fetched_at, slug=slug, payload=payload)
        parsed = _parse_release(payload.decode("utf-8", errors="ignore"))
        published_day = safe_text(parsed.get("published_at"))[:10]
        if start_date and published_day and published_day < str(start_date)[:10]:
            continue
        if end_date and published_day and published_day > str(end_date)[:10]:
            continue
        if keyword and keyword.casefold() not in safe_text(parsed.get("text")).casefold():
            continue
        rows.append(_document_from_release(url=link, parsed=parsed, ingested_at=fetched_at, raw_path=raw_path))

    rows.sort(key=lambda row: row.get("published_at", ""), reverse=True)
    if fields:
        return pd.DataFrame(select_fields(rows, fields))
    return pd.DataFrame(rows)
