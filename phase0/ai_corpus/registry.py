from __future__ import annotations

from phase0.ai_corpus.schema import AiCorpusProviderSpec

GOV_POLICY_PARSER_VERSION = "gov_policy_v1"

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
        supported_parameters=("org", "ptype", "keyword", "start_date", "end_date", "limit", "collection"),
        status="implemented_mvp",
        notes="Supports fixture-first tests and live gov.cn list/content fetch when network is available.",
    ),
    "cctv": AiCorpusProviderSpec(
        name="cctv",
        canonical_name="cctv",
        corpus_types=("cctv_news",),
        source="央视网新闻联播",
        base_url="https://tv.cctv.com/lm/xwlb/day/",
        parser_version="planned",
        raw_archive_dir="data/raw_data/ai_corpus/cctv",
        supported_parameters=("date", "start_date", "end_date", "include_segments"),
        status="planned_fixture_only",
        notes="W2.31 only reserves the provider plan; production fetch is not implemented yet.",
    ),
    "cninfo": AiCorpusProviderSpec(
        name="cninfo",
        canonical_name="cninfo",
        corpus_types=("announcement",),
        source="巨潮资讯 / AkShare 公告入口",
        base_url="https://www.cninfo.com.cn/",
        parser_version="planned",
        raw_archive_dir="data/raw_data/ai_corpus/cninfo",
        supported_parameters=("event_type", "start_date", "end_date", "keyword"),
        status="planned_only",
        notes="W2.31 keeps abnormal-trading/risk-warning announcement work scoped as a later provider.",
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
