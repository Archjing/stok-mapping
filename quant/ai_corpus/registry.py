from __future__ import annotations

from quant.ai_corpus.schema import AiCorpusProviderSpec

GOV_POLICY_PARSER_VERSION = "gov_policy_v1"
CCTV_NEWS_PARSER_VERSION = "cctv_news_v1"
CNINFO_PARSER_VERSION = "cninfo_announcement_v1"
US_MARKET_NEWS_PARSER_VERSION = "us_market_news_rss_v1"
SIA_SALES_PARSER_VERSION = "sia_sales_html_v1"
PBOC_PARSER_VERSION = "pboc_report_v1"
RESEARCH_REPORT_PARSER_VERSION = "research_report_metadata_v1"
SIA_NEWS_LISTING = "https://www.semiconductors.org/news-events/latest-news/"
PBOC_LIST_URL = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125227/125957/index.html"
SEMI_SUPPLY_CHAIN_PARSER_VERSION = "semi_supply_chain_reprint_v1"
CLS_TELEGRAPH_PARSER_VERSION = "cls_telegraph_v1"
SINA_7X24_PARSER_VERSION = "sina_7x24_v1"
WALLSTCN_LIVES_PARSER_VERSION = "wallstcn_lives_v1"

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
    "sia": "sia_sales",
    "sia-sales": "sia_sales",
    "sia_news": "sia_sales",
    "sia-news": "sia_sales",
    "sia-sales-news": "sia_sales",
    "sia_sales_news": "sia_sales",
    "semiconductor-sales": "sia_sales",
    "semi-supply-chain": "semi_supply_chain",
    "semi_supply_chain": "semi_supply_chain",
    "tsmc-revenue": "semi_supply_chain",
    "korea-exports": "semi_supply_chain",
    "tsmc": "semi_supply_chain",
    "pboc": "pboc",
    "pboc-report": "pboc",
    "pboc_report": "pboc",
    "monetary-policy": "pboc",
    "research-report": "research_report",
    "research_report": "research_report",
    "broker-report": "research_report",
    "broker_report": "research_report",
    "cls": "cls_telegraph",
    "cls-telegraph": "cls_telegraph",
    "cls_telegraph": "cls_telegraph",
    "cailianpress": "cls_telegraph",
    "cailianpress-telegraph": "cls_telegraph",
    "sina-7x24": "sina_7x24",
    "sina_7x24": "sina_7x24",
    "sina": "sina_7x24",
    "wallstcn": "wallstcn_lives",
    "wallstcn-lives": "wallstcn_lives",
    "wallstcn_lives": "wallstcn_lives",
    "wallstreetcn": "wallstcn_lives",
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
    "sia_sales": AiCorpusProviderSpec(
        name="sia_sales",
        canonical_name="sia_sales",
        corpus_types=("sia_sales_news",),
        source="SIA semiconductors.org global semiconductor sales press releases",
        base_url=SIA_NEWS_LISTING,
        parser_version=SIA_SALES_PARSER_VERSION,
        raw_archive_dir="data/raw_data/ai_corpus/sia_sales",
        supported_parameters=("keyword", "start_date", "end_date", "limit", "pages"),
        status="implemented_mvp",
        notes="Monthly WSTS/SIA global semiconductor sales releases; parses sales, MoM, YoY, report period.",
    ),
    "semi_supply_chain": AiCorpusProviderSpec(
        name="semi_supply_chain",
        canonical_name="semi_supply_chain",
        corpus_types=("tsmc_monthly_revenue", "korea_semi_exports"),
        source="Chinese financial media reprints of TSMC monthly revenue and Korea semiconductor exports",
        base_url="explicit source URLs (caller locates reprints via web search)",
        parser_version=SEMI_SUPPLY_CHAIN_PARSER_VERSION,
        raw_archive_dir="data/raw_data/ai_corpus/semi_supply_chain",
        supported_parameters=("keyword", "start_date", "end_date", "limit", "source_urls"),
        status="implemented_mvp",
        notes="Official TSMC/Korea sites are unreachable (Cloudflare/DNS); parses regular media reprints, tagged media_reprint_of_official_disclosure.",
    ),
    "pboc": AiCorpusProviderSpec(
        name="pboc",
        canonical_name="pboc",
        corpus_types=("pboc_report",),
        source="中国人民银行货币政策司",
        base_url=PBOC_LIST_URL,
        parser_version=PBOC_PARSER_VERSION,
        raw_archive_dir="data/raw_data/ai_corpus/pboc",
        supported_parameters=("start_date", "end_date", "keyword", "limit", "include_content"),
        status="implemented_mvp",
        notes="PBOC monetary-policy implementation reports; list + detail-page text extraction, optional PDF text via pymupdf.",
    ),
    "research_report": AiCorpusProviderSpec(
        name="research_report",
        canonical_name="research_report",
        corpus_types=("research_report",),
        source="东方财富研报中心（AkShare stock_research_report_em）",
        base_url="https://data.eastmoney.com/report/",
        parser_version=RESEARCH_REPORT_PARSER_VERSION,
        raw_archive_dir="data/raw_data/ai_corpus/research_report",
        supported_parameters=("keyword", "start_date", "end_date", "limit", "symbols"),
        status="implemented_mvp",
        notes="Metadata + authorized summaries only; never stores unauthorized full text (content_html/raw_text left empty). Source is Eastmoney research center via AkShare stock_research_report_em.",
    ),
    "cls_telegraph": AiCorpusProviderSpec(
        name="cls_telegraph",
        canonical_name="cls_telegraph",
        corpus_types=("market_flash",),
        source="财联社电报",
        base_url="https://www.cls.cn/api/cache",
        parser_version=CLS_TELEGRAPH_PARSER_VERSION,
        raw_archive_dir="data/raw_data/ai_corpus/cn_finance_flash",
        supported_parameters=("start_date", "end_date", "limit"),
        status="implemented_mvp",
        notes="Public CLS telegraph cache endpoint (no API key). Returns latest ~20 rows per call; endpoint ignores paging params.",
    ),
    "sina_7x24": AiCorpusProviderSpec(
        name="sina_7x24",
        canonical_name="sina_7x24",
        corpus_types=("market_flash",),
        source="新浪财经 7x24 全球实时快讯",
        base_url="https://zhibo.sina.com.cn/api/zhibo/feed",
        parser_version=SINA_7X24_PARSER_VERSION,
        raw_archive_dir="data/raw_data/ai_corpus/cn_finance_flash",
        supported_parameters=("start_date", "end_date", "limit"),
        status="implemented_mvp",
        notes="Public Sina 7x24 feed API. Supports true pagination via page/page_size (max 100/page); limit controls total rows fetched.",
    ),
    "wallstcn_lives": AiCorpusProviderSpec(
        name="wallstcn_lives",
        canonical_name="wallstcn_lives",
        corpus_types=("market_flash",),
        source="华尔街见闻实时快讯",
        base_url="https://api-one.wallstcn.com/apiv1/content/lives",
        parser_version=WALLSTCN_LIVES_PARSER_VERSION,
        raw_archive_dir="data/raw_data/ai_corpus/cn_finance_flash",
        supported_parameters=("start_date", "end_date", "limit"),
        status="implemented_mvp",
        notes="Public WallstreetCN lives API (channel=global-channel). Returns up to limit rows per call.",
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
