from __future__ import annotations

from pathlib import Path

import pandas as pd

from phase0.ai_corpus.providers.gov_policy import fetch_national_policy_repository, npr
from phase0.ai_corpus.registry import canonical_provider_name, get_provider_spec
from phase0.ai_corpus.storage import query_ai_corpus_documents


def fetch_ai_corpus(
    *,
    provider: str | None = None,
    corpus_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    org: str | None = None,
    ptype: str | None = None,
    symbols: list[str] | None = None,
    topics: list[str] | None = None,
    keyword: str | None = None,
    include_content: bool = True,
    fields: list[str] | None = None,
    limit: int = 500,
    root: Path | None = None,
    fixture_dir: str | Path | None = None,
    raw_archive_dir: str | Path = "data/raw_data/ai_corpus/gov_policy",
    database_path: str | Path | None = None,
) -> pd.DataFrame:
    canonical = canonical_provider_name(provider)
    spec = get_provider_spec(canonical)
    if spec.status != "implemented_mvp":
        raise NotImplementedError(f"ai corpus provider is not implemented for production fetch yet: {canonical}")
    if symbols:
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
            raw_archive_dir=raw_archive_dir,
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
