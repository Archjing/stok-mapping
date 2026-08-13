"""PBOC 货币政策执行报告 provider.

抓取中国人民银行官网「货币政策执行报告」列表页（
`/zhengcehuobisi/125207/125227/125957/index.html`），定位各季度报告详情页，
抽取发布时间（``PubDate`` meta）、正文（``td.content``）、PDF 链接。

首期只做列表 + 详情页文本抽取；PDF 全文文本抽取（pymupdf）在 ``include_content=True``
且 PDF 可下载时尽力而为，失败降级为 ``parse_status=partial``。
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import pandas as pd
import requests

from quant.ai_corpus.registry import PBOC_PARSER_VERSION
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

PBOC_SOURCE = "中国人民银行"
PBOC_LIST_URL = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125227/125957/index.html"
PBOC_BASE = "https://www.pbc.gov.cn"
DEFAULT_RAW_ARCHIVE_DIR = "data/raw_data/ai_corpus/pboc"

# 报告标题必须包含「货币政策执行报告」，排除《简介》等导航条目。
REPORT_TITLE_RE = re.compile(r"(\d{4})年(第[一二三四]季度)?\s*中国货币政策执行报告")
QUARTER_MAP = {"一": "Q1", "二": "Q2", "三": "Q3", "四": "Q4"}


def _date_only(value: str) -> str:
    text = safe_text(value)
    if not text:
        return ""
    match = re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", text)
    if match:
        year, month, day = [int(p) for p in match.group(0).replace("/", "-").split("-")]
        return f"{year:04d}-{month:02d}-{day:02d}"
    return text[:10]


def _report_period(title: str) -> str:
    """Extract report period from title, e.g. ``2026年第二季度`` → ``2026Q2``."""
    match = re.search(r"(\d{4})年(第([一二三四])季度)?", title)
    if not match:
        return ""
    year = match.group(1)
    quarter = match.group(3)
    if quarter and quarter in QUARTER_MAP:
        return f"{year}{QUARTER_MAP[quarter]}"
    return year


def _parse_listing_links(html_text: str) -> list[tuple[str, str]]:
    """Return [(title, url), ...] for report detail pages from the listing HTML."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_text, "html.parser")
    results: list[tuple[str, str]] = []
    for a in soup.find_all("a", href=True):
        title = safe_text(a.get("title") or a.get_text("", strip=True))
        if not REPORT_TITLE_RE.search(title):
            continue
        href = a["href"].strip()
        if not href or href.endswith("/index.html") and not _is_detail_href(href):
            # skip the "2026年货币政策执行报告" year-level folder pages
            if _is_year_folder(title, href):
                continue
        url = urljoin(PBOC_BASE, href)
        results.append((title, url))
    # de-dupe by url while keeping order
    seen: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for title, url in results:
        if url not in seen:
            seen.add(url)
            deduped.append((title, url))
    return deduped


def _is_year_folder(title: str, href: str) -> bool:
    # Year folders have titles like "2026年货币政策执行报告" (no 季度).
    return bool(re.search(r"(\d{4})年货币政策执行报告$", title))


def _is_detail_href(href: str) -> bool:
    # Detail pages live under a deep numeric path; folder pages are one level.
    return bool(re.search(r"/\d{13,}/index\.html$", href)) or bool(
        re.search(r"/[0-9a-f]{32}/index\.html$", href)
    )


def parse_pboc_report_page(
    html_text: str,
    *,
    url: str = "",
    raw_path: Path | None = None,
    ingested_at: str | None = None,
    pdf_text: str = "",
) -> dict[str, str]:
    """Parse a single report detail page into an ai_corpus document row."""
    from bs4 import BeautifulSoup

    fetched_at = ingested_at or now_iso()
    soup = BeautifulSoup(html_text, "html.parser")
    title = safe_text(soup.find("meta", attrs={"name": "ArticleTitle"}).get("content")
                      if soup.find("meta", attrs={"name": "ArticleTitle"}) else "")
    if not title:
        t = soup.find("title")
        title = safe_text(t.get_text("", strip=True) if t else "")
    pub_date = safe_text(soup.find("meta", attrs={"name": "PubDate"}).get("content")
                         if soup.find("meta", attrs={"name": "PubDate"}) else "")
    published_at = _date_only(pub_date)

    content_cell = soup.find("td", class_="content")
    paragraphs = []
    pdf_url = ""
    if content_cell:
        for p in content_cell.find_all("p"):
            text = safe_text(p.get_text(" ", strip=True))
            if text:
                paragraphs.append(text)
        for a in content_cell.find_all("a", href=True):
            if a["href"].endswith(".pdf"):
                pdf_url = urljoin(url, a["href"]) if url else a["href"]
                break
    raw_text = "\n".join(paragraphs)
    if pdf_text:
        raw_text = f"{raw_text}\n\n[PDF 正文]\n{pdf_text}".strip()

    period = _report_period(title)
    content_hash = content_sha256(raw_text or title)
    source_id = content_sha256(url or title)[:24]
    dedupe_key = stable_dedupe_key(source_id, url, title, published_at, content_hash)
    parse_status = "content_extracted" if raw_text else "partial"
    return {
        "document_id": stable_document_id("pboc", source_id, content_hash),
        "corpus_type": "pboc_report",
        "event_type": "pboc_report",
        "provider": "pboc",
        "source": PBOC_SOURCE,
        "source_id": source_id,
        "published_at": published_at,
        "issued_at": "",
        "ingested_at": fetched_at,
        "as_of_time": fetched_at,
        "title": title,
        "summary": "",
        "content_html": "",
        "raw_text": raw_text,
        "url": url or pdf_url,
        "org": PBOC_SOURCE,
        "pcode": period,
        "ptype": "quarter" if "Q" in period else "annual",
        "symbols": "",
        "industries": "",
        "topics": f"货币政策\\{period}",
        "language": "zh-CN",
        "dedupe_key": dedupe_key,
        "content_hash": content_hash,
        "raw_path": str(raw_path) if raw_path else "",
        "parse_status": parse_status,
        "source_confidence": "official_central_bank",
        "parser_version": PBOC_PARSER_VERSION,
    }


def _write_raw_text(*, archive_root: Path, stem: str, text: str) -> Path:
    day = datetime.now().date().isoformat()
    path = archive_root / "html" / day.replace("-", "/") / f"{stem}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _read_fixture(fixture_dir: Path, name: str) -> str:
    candidate = fixture_dir / name
    if not candidate.exists():
        raise FileNotFoundError(f"pboc fixture not found: {candidate}")
    return candidate.read_text(encoding="utf-8")


def _extract_pdf_text(pdf_url: str, timeout: int) -> str:
    """Best-effort PDF text extraction via pymupdf; empty string on failure."""
    try:
        import fitz  # pymupdf
    except ImportError:
        return ""
    try:
        resp = requests.get(pdf_url, timeout=timeout)
        resp.raise_for_status()
        with fitz.open(stream=resp.content, filetype="pdf") as doc:
            return "\n".join(page.get_text() for page in doc)
    except Exception:
        return ""


def fetch_pboc_reports(
    *,
    root: Path | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    keyword: str | None = None,
    fields: list[str] | None = None,
    limit: int = 100,
    include_content: bool = True,
    fixture_dir: str | Path | None = None,
    raw_archive_dir: str | Path = DEFAULT_RAW_ARCHIVE_DIR,
    timeout: int = 20,
    ingested_at: str | None = None,
) -> pd.DataFrame:
    """Fetch PBOC monetary-policy implementation reports.

    fixture 模式：解析 ``fixture_dir/pboc_report_list.html`` 列表 + 各报告详情页
    （``pboc_report_*.html``），不碰网络。
    live 模式：抓列表页 → 过滤目标日期范围 → 逐篇抓详情页 → 抽取正文。
    """
    project_root = root or Path.cwd()
    archive_root = resolve_path(project_root, raw_archive_dir)
    fetched_at = ingested_at or now_iso()

    if fixture_dir:
        fixture_root = resolve_path(project_root, fixture_dir)
        listing_html = _read_fixture(fixture_root, "pboc_report_list.html")
        links = _parse_listing_links(listing_html)
        detail_fixtures = sorted(p.name for p in fixture_root.glob("pboc_report_*.html"))
        documents: list[dict[str, str]] = []
        for title, url in links:
            # match fixture by quarter/year embedded in title where possible
            period = _report_period(title)
            fixture_name = None
            for name in detail_fixtures:
                if period and period in name:
                    fixture_name = name
                    break
            if fixture_name is None and detail_fixtures:
                fixture_name = detail_fixtures[0]
            if fixture_name is None:
                continue
            html = _read_fixture(fixture_root, fixture_name)
            raw_path = _write_raw_text(archive_root=archive_root, stem=fixture_name[:-5], text=html)
            documents.append(parse_pboc_report_page(
                html, url=url, raw_path=raw_path, ingested_at=fetched_at,
            ))
    else:
        resp = requests.get(PBOC_LIST_URL, timeout=timeout)
        resp.raise_for_status()
        listing_html = resp.content.decode("utf-8", errors="replace")
        raw_path = _write_raw_text(archive_root=archive_root, stem="pboc_report_list", text=listing_html)
        links = _parse_listing_links(listing_html)
        documents = []
        for title, url in links:
            try:
                detail = requests.get(url, timeout=timeout)
                detail.raise_for_status()
                html = detail.content.decode("utf-8", errors="replace")
            except requests.RequestException:
                continue
            raw = _write_raw_text(
                archive_root=archive_root,
                stem=content_sha256(url)[:12],
                text=html,
            )
            pdf_text = ""
            doc = parse_pboc_report_page(html, url=url, raw_path=raw, ingested_at=fetched_at)
            if include_content and doc["parse_status"] == "content_extracted":
                pdf_url = doc["url"] if doc["url"].endswith(".pdf") else ""
                if pdf_url:
                    pdf_text = _extract_pdf_text(pdf_url, timeout)
                    if pdf_text:
                        doc = parse_pboc_report_page(
                            html, url=url, raw_path=raw, ingested_at=fetched_at, pdf_text=pdf_text,
                        )
            documents.append(doc)

    # filter by date range
    if start_date:
        documents = [d for d in documents if d["published_at"] >= start_date]
    if end_date:
        documents = [d for d in documents if d["published_at"] <= end_date]
    if keyword:
        documents = [d for d in documents if keyword in d["title"] or keyword in d["raw_text"]]
    if limit >= 0:
        documents = documents[: int(limit)]

    output_rows = select_fields(documents, fields)
    return pd.DataFrame(output_rows, columns=fields or AI_CORPUS_DOCUMENT_COLUMNS)
