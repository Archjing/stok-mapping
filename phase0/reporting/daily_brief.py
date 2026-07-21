from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, DecimalException
from datetime import date, datetime
import math
from typing import Any, Mapping


DAILY_BRIEF_SECTION_ORDER = [
    "metadata",
    "data_freshness",
    "account_summary",
    "market_context",
    "strategy_status",
    "portfolio_plan",
    "watchlist_digest",
    "risk_checks",
    "artifacts",
    "disclaimer",
]

DAILY_BRIEF_DISCLAIMER = (
    "本简报仅用于个人量化研究、盘前复核和模拟账户跟踪，不构成投资建议；"
    "未确认账单不推导收益，未通过 strategy-admission 的策略仅按 research-only 边界展示。"
)

NO_ADMISSION_PASS_MESSAGE = (
    "当前没有通过正式 strategy-admission 的候选策略；日报只能展示研究状态、观察池和风险解释，"
    "不能包装为正式可执行策略。"
)


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None or (isinstance(value, str) and value == ""):
        return None
    try:
        return Decimal(str(value))
    except (DecimalException, OverflowError, TypeError, ValueError):
        return None


def _validated_confirmed_asset_fields(snapshot: Mapping[str, Any]) -> tuple[float, float, float]:
    asset_values: dict[str, Decimal] = {}
    for field_name in ("total_asset", "cash_asset", "stock_asset"):
        raw_value = snapshot.get(field_name)
        parsed_value = _optional_decimal(raw_value)
        if isinstance(raw_value, bool) or parsed_value is None:
            raise ValueError(f"Confirmed bill snapshot has incomplete or non-numeric {field_name}.")
        try:
            if not parsed_value.is_finite():
                raise ValueError(f"Confirmed bill snapshot has non-finite {field_name}.")
            if parsed_value < 0:
                raise ValueError(f"Confirmed bill snapshot has negative {field_name}.")
        except (DecimalException, OverflowError, TypeError, ValueError) as exc:
            if isinstance(exc, ValueError):
                raise
            raise ValueError(f"Confirmed bill snapshot has invalid {field_name}.") from exc
        asset_values[field_name] = parsed_value

    total_asset = asset_values["total_asset"]
    cash_asset = asset_values["cash_asset"]
    stock_asset = asset_values["stock_asset"]
    try:
        difference = total_asset - cash_asset - stock_asset
        if abs(difference) > Decimal("0.01"):
            raise ValueError(
                "Confirmed bill snapshot asset fields are inconsistent: "
                f"total_asset={total_asset}, cash_asset={cash_asset}, stock_asset={stock_asset}, "
                f"difference={difference}; total_asset must equal cash_asset + stock_asset within 0.01."
            )
    except (DecimalException, OverflowError, TypeError, ValueError) as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError(
            "Confirmed bill snapshot has values outside the supported range: "
            f"total_asset={total_asset}, cash_asset={cash_asset}, stock_asset={stock_asset}."
        ) from exc

    effective_assets: dict[str, float] = {}
    for field_name, decimal_value in asset_values.items():
        try:
            float_value = float(decimal_value)
            if not math.isfinite(float_value):
                raise ValueError
            if decimal_value != 0 and float_value == 0.0:
                raise ValueError
        except (DecimalException, OverflowError, TypeError, ValueError) as exc:
            raise ValueError(
                "Confirmed bill snapshot has a non-finite or unrepresentable "
                f"{field_name}={decimal_value}."
            ) from exc
        effective_assets[field_name] = float_value
    return (
        effective_assets["total_asset"],
        effective_assets["cash_asset"],
        effective_assets["stock_asset"],
    )


def _date_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _format_money(value: float) -> str:
    return f"{value:,.2f}"


def _format_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


@dataclass(frozen=True)
class DailyBriefMetadata:
    brief_date: str
    signal_date: str = ""
    generated_at: str = ""
    is_trading_day: bool | None = None
    trading_calendar_source: str = ""
    run_profile: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DataFreshnessItem:
    name: str
    status: str
    latest_date: str = ""
    source: str = ""
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AccountSummary:
    account_id: str
    account_name: str
    total_asset: float
    cash_asset: float
    stock_asset: float
    exposure: float
    current_return: float | None = None
    bill_date: str = ""
    bill_status: str = "unconfirmed_or_missing"

    @property
    def total_asset_display(self) -> str:
        return _format_money(self.total_asset)

    @property
    def cash_asset_display(self) -> str:
        return _format_money(self.cash_asset)

    @property
    def stock_asset_display(self) -> str:
        return _format_money(self.stock_asset)

    @property
    def exposure_display(self) -> str:
        return _format_pct(self.exposure)

    @property
    def current_return_display(self) -> str:
        return "暂无" if self.current_return is None else _format_pct(self.current_return)

    def span_items(self) -> list[dict[str, str]]:
        return [
            {"key": "total_asset", "label": "总资产（元）", "value": self.total_asset_display},
            {"key": "cash_asset", "label": "可用资金（元）", "value": self.cash_asset_display},
            {"key": "stock_asset", "label": "持仓市值（元）", "value": self.stock_asset_display},
            {"key": "exposure", "label": "当前仓位（%）", "value": self.exposure_display},
            {"key": "current_return", "label": "当前收益率（%）", "value": self.current_return_display},
        ]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["spans"] = self.span_items()
        return data


@dataclass(frozen=True)
class MarketContext:
    status: str = "not_available"
    summary: str = "市场环境数据尚未接入正式 daily brief。"
    latest_cn_trade_date: str = ""
    cross_market_status: str = "not_available"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StrategyStatus:
    status: str = "research_only"
    strategy_set: str = ""
    admission_action: str = "not_admitted"
    has_admission_pass: bool = False
    summary: str = NO_ADMISSION_PASS_MESSAGE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PortfolioPlan:
    status: str = "not_ready"
    stance: str = "仅观察"
    target_exposure: float | None = None
    current_exposure: float | None = None
    blocking_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WatchlistDigest:
    status: str = "not_available"
    signal_date: str = ""
    action_counts: dict[str, int] = field(default_factory=dict)
    highlights: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RiskCheck:
    name: str
    status: str
    message: str = ""
    severity: str = "info"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ArtifactLink:
    key: str
    label: str
    path: str
    status: str = "available"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DailyBriefSection:
    key: str
    title: str
    status: str = "not_available"
    summary: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    artifact_keys: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DailyBriefDocument:
    metadata: DailyBriefMetadata
    data_freshness: list[DataFreshnessItem] = field(default_factory=list)
    account_summary: AccountSummary | None = None
    market_context: MarketContext = field(default_factory=MarketContext)
    strategy_status: StrategyStatus = field(default_factory=StrategyStatus)
    portfolio_plan: PortfolioPlan = field(default_factory=PortfolioPlan)
    watchlist_digest: WatchlistDigest = field(default_factory=WatchlistDigest)
    risk_checks: list[RiskCheck] = field(default_factory=list)
    artifacts: list[ArtifactLink] = field(default_factory=list)
    disclaimer: str = DAILY_BRIEF_DISCLAIMER
    sections: list[DailyBriefSection] = field(default_factory=list)

    def ordered_sections(self) -> list[DailyBriefSection]:
        by_key = {section.key: section for section in self.sections}
        generated = default_daily_brief_sections(self)
        by_key.update({section.key: by_key.get(section.key, section) for section in generated})
        return [by_key[key] for key in DAILY_BRIEF_SECTION_ORDER if key in by_key]

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "data_freshness": [item.to_dict() for item in self.data_freshness],
            "account_summary": self.account_summary.to_dict() if self.account_summary is not None else None,
            "market_context": self.market_context.to_dict(),
            "strategy_status": self.strategy_status.to_dict(),
            "portfolio_plan": self.portfolio_plan.to_dict(),
            "watchlist_digest": self.watchlist_digest.to_dict(),
            "risk_checks": [item.to_dict() for item in self.risk_checks],
            "artifacts": [item.to_dict() for item in self.artifacts],
            "disclaimer": self.disclaimer,
            "sections": [section.to_dict() for section in self.ordered_sections()],
        }


def build_account_summary(
    snapshot: Mapping[str, Any] | None,
    *,
    account_id: str = "",
    account_name: str = "",
    initial_cash: float = 1_000_000.0,
    bill_confirmed: bool = False,
    bill_date: str = "",
) -> AccountSummary:
    snapshot = snapshot or {}
    if bill_confirmed:
        effective_total, effective_cash, effective_stock = _validated_confirmed_asset_fields(snapshot)
    else:
        effective_total = float(initial_cash)
        effective_cash = float(initial_cash)
        effective_stock = 0.0
    exposure = effective_stock / effective_total if effective_total else 0.0
    current_return = (effective_total - float(initial_cash)) / float(initial_cash) if bill_confirmed and initial_cash else None
    return AccountSummary(
        account_id=str(snapshot.get("account_id") or account_id),
        account_name=str(account_name or snapshot.get("name") or ""),
        total_asset=float(effective_total),
        cash_asset=float(effective_cash),
        stock_asset=float(effective_stock),
        exposure=float(exposure),
        current_return=current_return,
        bill_date=str(snapshot.get("brief_date") or bill_date or ""),
        bill_status="confirmed" if bill_confirmed else "unconfirmed_or_missing",
    )


def default_daily_brief_sections(document: DailyBriefDocument) -> list[DailyBriefSection]:
    account_payload = document.account_summary.to_dict() if document.account_summary is not None else {}
    return [
        DailyBriefSection("metadata", "顶部状态栏", "available", payload=document.metadata.to_dict()),
        DailyBriefSection(
            "data_freshness",
            "数据新鲜度",
            "available" if document.data_freshness else "not_available",
            payload={"items": [item.to_dict() for item in document.data_freshness]},
        ),
        DailyBriefSection("account_summary", "账户与风险摘要", "available", payload=account_payload),
        DailyBriefSection(
            "market_context",
            "市场环境",
            document.market_context.status,
            document.market_context.summary,
            document.market_context.to_dict(),
        ),
        DailyBriefSection(
            "strategy_status",
            "策略与门禁状态",
            document.strategy_status.status,
            document.strategy_status.summary,
            document.strategy_status.to_dict(),
        ),
        DailyBriefSection(
            "portfolio_plan",
            "组合计划",
            document.portfolio_plan.status,
            document.portfolio_plan.stance,
            document.portfolio_plan.to_dict(),
        ),
        DailyBriefSection(
            "watchlist_digest",
            "观察池摘要",
            document.watchlist_digest.status,
            payload=document.watchlist_digest.to_dict(),
        ),
        DailyBriefSection(
            "risk_checks",
            "风险、阻断与人工检查",
            "available" if document.risk_checks else "not_available",
            payload={"items": [item.to_dict() for item in document.risk_checks]},
        ),
        DailyBriefSection(
            "artifacts",
            "证据与产物链接",
            "available" if document.artifacts else "not_available",
            payload={"items": [item.to_dict() for item in document.artifacts]},
        ),
        DailyBriefSection("disclaimer", "边界说明", "available", document.disclaimer, {"text": document.disclaimer}),
    ]


def build_empty_daily_brief_document(
    *,
    brief_date: Any,
    signal_date: Any = "",
    generated_at: Any = "",
    account_id: str = "",
    account_name: str = "",
    initial_cash: float = 1_000_000.0,
) -> DailyBriefDocument:
    metadata = DailyBriefMetadata(
        brief_date=_date_text(brief_date),
        signal_date=_date_text(signal_date),
        generated_at=_date_text(generated_at),
    )
    account_summary = build_account_summary(
        {},
        account_id=account_id,
        account_name=account_name,
        initial_cash=initial_cash,
        bill_confirmed=False,
    )
    return DailyBriefDocument(
        metadata=metadata,
        account_summary=account_summary,
        risk_checks=[
            RiskCheck(
                name="正式日报生成",
                status="not_ready",
                message="Daily Brief renderer 尚未接入；当前模型用于冻结内容契约和缺数据口径。",
                severity="warning",
            )
        ],
    )
