from __future__ import annotations

from phase0.ai_corpus.schema import AiCorpusProviderSpec

GOV_POLICY_PARSER_VERSION = "gov_policy_v1"
CCTV_NEWS_PARSER_VERSION = "cctv_news_v1"
CNINFO_PARSER_VERSION = "cninfo_announcement_v1"
US_MARKET_NEWS_PARSER_VERSION = "us_market_news_rss_v1"

PROVIDER_ALIASES = {
    "gov-policy": "gov_policy",
    "gov_cn": "gov_policy",
    "gov.cn": "gov_policy",
    "national-policy-repository": "gov_policy",
    "npr": "gov_policy",
    "cctv-news": "cctv",
    "cctv_news": "cctv",
    "cn-info": "cninfo",
    "cn_info": "cninfo",
    "announcement": "cninfo",
    "announcements": "cninfo",
    "us-market-news": "us_market_news",
    "us_news": "us_market_news",
    "us-news": "us_market_news",
    "market-news": "us_market_news",
    "us-market": "us_market_news",
}

PROVIDER_REGISTRY = {
    "gov_policy": AiCorpusProviderSpec(
        name="gov_policy",
        canonical_name="gov_policy",
        corpus_types=("policy", "regulation"),
        source="中国政府网政策文件库",
        base_url="https://sousuo.www.gov.cn/search-gov/data",
        parser_version=GOV_POLICY_PARSER_VERSION,
        raw_archive_dir="data/raw_data/ai_corpus/gov_policy",
        supported_parameters=(
            "org",
            "ptype",
            "keyword",
            "start_date",
            "end_date",
            "limit",
            "collection",
            "reference_dir",
            "refresh_reference",
            "probe_before_fetch",
        ),
        status="implemented_mvp",
        notes="Supports fixture tests, live gov.cn list/content fetch, reference cache, source probe, and pre-fetch audit gate.",
    ),
    "cctv": AiCorpusProviderSpec(
        name="cctv",
        canonical_name="cctv",
        corpus_types=("cctv_news",),
        source="央视网新闻联播",
        base_url="https://tv.cctv.com/lm/xwlb/day/",
        parser_version=CCTV_NEWS_PARSER_VERSION,
        raw_archive_dir="data/raw_data/ai_corpus/cctv",
        supported_parameters=("date", "start_date", "end_date", "include_segments", "limit"),
        status="implemented_mvp",
        notes="Supports live CCTV day/program/segment fetch and fixture-based parser regression tests.",
    ),
    "cninfo": AiCorpusProviderSpec(
        name="cninfo",
        canonical_name="cninfo",
        corpus_types=("announcement",),
        source="巨潮资讯 / AkShare 公告入口",
        base_url="https://www.cninfo.com.cn/",
        parser_version=CNINFO_PARSER_VERSION,
        raw_archive_dir="data/raw_data/ai_corpus/cninfo",
        supported_parameters=("event_type", "start_date", "end_date", "keyword", "symbols", "limit"),
        status="implemented_mvp",
        notes="Supports AkShare/CNInfo announcement list fetch, risk_events filters, fixture regression, raw archive, and SQLite upsert.",
    ),
    "us_market_news": AiCorpusProviderSpec(
        name="us_market_news",
        canonical_name="us_market_news",
        corpus_types=("us_market_news",),
        source="Public US market RSS feeds",
        base_url="configurable RSS feeds",
        parser_version=US_MARKET_NEWS_PARSER_VERSION,
        raw_archive_dir="data/raw_data/ai_corpus/us_market_news",
        supported_parameters=("keyword", "start_date", "end_date", "limit", "feeds", "keywords"),
        status="implemented_mvp",
        notes="Configurable RSS metadata fetch for US market and semiconductor context; explanation layer only.",
    ),
}


def canonical_provider_name(provider: str | None) -> str:
    raw = (provider or "gov_policy").strip()
    normalized = raw.replace(" ", "_")
    return PROVIDER_ALIASES.get(normalized, normalized)


def get_provider_spec(provider: str | None) -> AiCorpusProviderSpec:
    canonical = canonical_provider_name(provider)
    if canonical not in PROVIDER_REGISTRY:
        raise KeyError(f"unsupported ai corpus provider: {provider}")
    return PROVIDER_REGISTRY[canonical]


def provider_registry_rows() -> list[dict[str, str]]:
    return [
        {
            "name": spec.name,
            "canonical_name": spec.canonical_name,
            "corpus_types": ",".join(spec.corpus_types),
            "source": spec.source,
            "base_url": spec.base_url,
            "parser_version": spec.parser_version,
            "raw_archive_dir": spec.raw_archive_dir,
            "supported_parameters": ",".join(spec.supported_parameters),
            "status": spec.status,
            "notes": spec.notes,
        }
        for spec in PROVIDER_REGISTRY.values()
    ]
