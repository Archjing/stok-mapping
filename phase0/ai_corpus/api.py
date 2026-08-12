from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from phase0.ai_corpus.providers.cctv_news import fetch_cctv_news
from phase0.ai_corpus.providers.cninfo import fetch_cninfo_announcements
from phase0.ai_corpus.providers.gov_policy import (
    DEFAULT_REFERENCE_DIR,
    fetch_national_policy_repository,
    npr,
)
from phase0.ai_corpus.providers.us_market_news import fetch_us_market_news
from phase0.ai_corpus.registry import canonical_provider_name, get_provider_spec
from phase0.ai_corpus.storage import query_ai_corpus_documents


def _parse_cctv_date(value: str) -> datetime:
    text = str(value).strip()
    if not text:
        raise ValueError("cctv news date is required")
    if len(text) >= 10 and text[4] in {"-", "/"}:
        return datetime.strptime(text[:10].replace("/", "-"), "%Y-%m-%d")
    if len(text) >= 8 and text[:8].isdigit():
        return datetime.strptime(text[:8], "%Y%m%d")
    raise ValueError(f"invalid cctv news date: {value}")


def _iter_cctv_dates(*, start_date: str | None, end_date: str | None) -> list[str]:
    if not start_date and not end_date:
        return [datetime.now().date().strftime("%Y%m%d")]
    start = _parse_cctv_date(start_date or end_date or "")
    end = _parse_cctv_date(end_date or start_date or "")
    if start > end:
        raise ValueError(f"cctv news start_date must be <= end_date: {start_date} > {end_date}")
    days: list[str] = []
    current = start
    while current <= end:
        days.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)
    return days


def fetch_ai_corpus(
    *,
    provider: str | None = None,
    corpus_type: str | None = None,
    event_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    org: str | None = None,
    ptype: str | None = None,
    symbols: list[str] | None = None,
    topics: list[str] | None = None,
    keyword: str | None = None,
    include_content: bool = True,
    include_segments: bool = True,
    fields: list[str] | None = None,
    limit: int = 500,
    root: Path | None = None,
    fixture_dir: str | Path | None = None,
    raw_archive_dir: str | Path | None = None,
    reference_dir: str | Path | None = None,
    refresh_reference: bool = False,
    database_path: str | Path | None = None,
    timeout: int = 20,
    provider_config: dict | None = None,
) -> pd.DataFrame:
    canonical = canonical_provider_name(provider)
    spec = get_provider_spec(canonical)
    if spec.status not in {"implemented_mvp", "fixture_mvp"}:
        raise NotImplementedError(f"ai corpus provider is not implemented for production fetch yet: {canonical}")
    if spec.status == "fixture_mvp" and not fixture_dir:
        raise NotImplementedError(f"ai corpus provider requires fixture_dir for validation: {canonical}")
    if symbols and canonical != "cninfo":
        raise NotImplementedError("symbol filtering is reserved for later market_text_events bridging")
    if topics and not ptype:
        ptype = topics[0]
    if canonical == "gov_policy":
        return fetch_national_policy_repository(
            root=root,
            org=org,
            start_date=start_date,
            end_date=end_date,
            ptype=ptype,
            keyword=keyword,
            collection="all" if not corpus_type else corpus_type,
            fields=fields,
            limit=limit,
            include_content=include_content,
            fixture_dir=fixture_dir,
            raw_archive_dir=raw_archive_dir or spec.raw_archive_dir,
            reference_dir=reference_dir or DEFAULT_REFERENCE_DIR,
            refresh_reference=refresh_reference,
            timeout=timeout,
        )
    if canonical == "cctv":
        frames: list[pd.DataFrame] = []
        remaining = max(0, int(limit))
        for date_value in _iter_cctv_dates(start_date=start_date, end_date=end_date):
            if remaining == 0:
                break
            frame = fetch_cctv_news(
                root=root,
                date=date_value,
                include_segments=include_segments,
                fields=fields,
                limit=remaining,
                fixture_dir=fixture_dir,
                raw_archive_dir=raw_archive_dir or spec.raw_archive_dir,
                timeout=timeout,
            )
            frames.append(frame)
            remaining -= len(frame)
        if not frames:
            return pd.DataFrame(columns=fields)
        return pd.concat(frames, ignore_index=True)
    if canonical == "cninfo":
        return fetch_cninfo_announcements(
            root=root,
            event_type=event_type or corpus_type,
            start_date=start_date,
            end_date=end_date,
            keyword=keyword,
            symbols=symbols,
            fields=fields,
            limit=limit,
            fixture_dir=fixture_dir,
            raw_archive_dir=raw_archive_dir or spec.raw_archive_dir,
        )
    if canonical == "us_market_news":
        return fetch_us_market_news(
            root=root,
            provider_config=provider_config,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            fields=fields,
            limit=limit,
            fixture_dir=fixture_dir,
            raw_archive_dir=raw_archive_dir or spec.raw_archive_dir,
            timeout=timeout,
            include_content=include_content,
        )
    if database_path:
        rows = query_ai_corpus_documents(
            Path(database_path),
            provider=canonical,
            corpus_type=corpus_type,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        return pd.DataFrame(rows)
    raise NotImplementedError(f"unsupported ai corpus provider: {canonical}")
