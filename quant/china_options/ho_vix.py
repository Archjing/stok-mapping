from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Iterable, Mapping


MINUTES_PER_YEAR = 365 * 24 * 60


class InsufficientOptionDataError(ValueError):
    """Raised when a chain cannot support an auditable volatility value."""


@dataclass(frozen=True)
class OptionQuote:
    trade_date: date
    expiry_date: date
    contract: str
    option_type: str
    strike: float
    bid: float | None
    ask: float | None
    last_price: float | None = None

    @property
    def mid(self) -> float | None:
        if self.bid is None or self.ask is None or self.bid < 0 or self.ask <= 0 or self.ask < self.bid:
            return None
        return (self.bid + self.ask) / 2.0


@dataclass(frozen=True)
class TermVarianceResult:
    expiry_date: date
    minutes_to_expiry: float
    variance: float
    forward: float
    k0: float
    quote_count: int
    used_strikes: tuple[float, ...]
    quality_flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Ho30IndexResult:
    value: float
    target_minutes: float
    near: TermVarianceResult
    next: TermVarianceResult
    quality_flags: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["near"]["expiry_date"] = self.near.expiry_date.isoformat()
        payload["next"]["expiry_date"] = self.next.expiry_date.isoformat()
        return payload


def _positive_otm_quotes(
    strikes: list[float],
    quotes: Mapping[float, OptionQuote],
    *,
    descending: bool,
) -> dict[float, float]:
    selected: dict[float, float] = {}
    zero_bid_count = 0
    for strike in sorted(strikes, reverse=descending):
        quote = quotes.get(strike)
        if quote is None or quote.mid is None:
            continue
        if quote.bid is None or quote.bid <= 0:
            zero_bid_count += 1
            if zero_bid_count >= 2:
                break
            continue
        zero_bid_count = 0
        selected[strike] = quote.mid
    return selected


def calculate_term_variance(
    quotes: Iterable[OptionQuote],
    *,
    valuation_at: datetime,
    settlement_at: datetime,
    risk_free_rate: float,
) -> TermVarianceResult:
    rows = list(quotes)
    if settlement_at <= valuation_at:
        raise InsufficientOptionDataError("option term has already expired")
    minutes = (settlement_at - valuation_at).total_seconds() / 60.0
    time_years = minutes / MINUTES_PER_YEAR

    calls = {float(q.strike): q for q in rows if q.option_type.upper() == "C" and q.mid is not None}
    puts = {float(q.strike): q for q in rows if q.option_type.upper() == "P" and q.mid is not None}
    paired = sorted(set(calls) & set(puts))
    if len(paired) < 2:
        raise InsufficientOptionDataError("term requires paired call and put quotes")

    forward_strike = min(paired, key=lambda strike: abs(calls[strike].mid - puts[strike].mid))
    forward = forward_strike + math.exp(risk_free_rate * time_years) * (
        calls[forward_strike].mid - puts[forward_strike].mid
    )
    eligible_k0 = [strike for strike in paired if strike <= forward]
    if not eligible_k0:
        raise InsufficientOptionDataError("forward is below the quoted strike range")
    k0 = max(eligible_k0)

    selected: dict[float, float] = {
        k0: (calls[k0].mid + puts[k0].mid) / 2.0,
    }
    selected.update(_positive_otm_quotes([k for k in puts if k < k0], puts, descending=True))
    selected.update(_positive_otm_quotes([k for k in calls if k > k0], calls, descending=False))
    used_strikes = sorted(selected)
    if len(used_strikes) < 3:
        raise InsufficientOptionDataError("term has fewer than three usable strikes")

    contribution = 0.0
    for index, strike in enumerate(used_strikes):
        if index == 0:
            delta_k = used_strikes[1] - strike
        elif index == len(used_strikes) - 1:
            delta_k = strike - used_strikes[index - 1]
        else:
            delta_k = (used_strikes[index + 1] - used_strikes[index - 1]) / 2.0
        contribution += delta_k / (strike * strike) * math.exp(risk_free_rate * time_years) * selected[strike]

    variance = 2.0 / time_years * contribution - 1.0 / time_years * (forward / k0 - 1.0) ** 2
    if not math.isfinite(variance) or variance <= 0:
        raise InsufficientOptionDataError("term variance is non-positive")
    return TermVarianceResult(
        expiry_date=settlement_at.date(),
        minutes_to_expiry=minutes,
        variance=variance,
        forward=forward,
        k0=k0,
        quote_count=len(used_strikes),
        used_strikes=tuple(used_strikes),
    )


def calculate_30_day_index(
    quotes: Iterable[OptionQuote],
    *,
    valuation_at: datetime,
    settlement_times: Mapping[date, datetime],
    risk_free_rate: float,
    target_days: int = 30,
) -> Ho30IndexResult:
    grouped: dict[date, list[OptionQuote]] = {}
    for quote in quotes:
        grouped.setdefault(quote.expiry_date, []).append(quote)

    valid_terms: list[TermVarianceResult] = []
    quality_flags: list[str] = []
    for expiry, term_quotes in sorted(grouped.items()):
        settlement_at = settlement_times.get(expiry)
        if settlement_at is None or settlement_at <= valuation_at:
            continue
        try:
            valid_terms.append(
                calculate_term_variance(
                    term_quotes,
                    valuation_at=valuation_at,
                    settlement_at=settlement_at,
                    risk_free_rate=risk_free_rate,
                )
            )
        except InsufficientOptionDataError as exc:
            quality_flags.append(f"ignored_term:{expiry.isoformat()}:{exc}")

    target_minutes = float(target_days * 24 * 60)
    near_candidates = [term for term in valid_terms if term.minutes_to_expiry <= target_minutes]
    next_candidates = [term for term in valid_terms if term.minutes_to_expiry > target_minutes]
    if not near_candidates or not next_candidates:
        raise InsufficientOptionDataError("two valid terms bracketing 30 days are required")
    near = max(near_candidates, key=lambda term: term.minutes_to_expiry)
    next_term = min(next_candidates, key=lambda term: term.minutes_to_expiry)

    n1, n2, n30 = near.minutes_to_expiry, next_term.minutes_to_expiry, target_minutes
    time_weighted_variance = (
        near.variance * (n2 - n30) / (n2 - n1) * (n1 / MINUTES_PER_YEAR)
        + next_term.variance * (n30 - n1) / (n2 - n1) * (n2 / MINUTES_PER_YEAR)
    ) * MINUTES_PER_YEAR / n30
    if not math.isfinite(time_weighted_variance) or time_weighted_variance <= 0:
        raise InsufficientOptionDataError("30-day interpolated variance is non-positive")
    return Ho30IndexResult(
        value=100.0 * math.sqrt(time_weighted_variance),
        target_minutes=target_minutes,
        near=near,
        next=next_term,
        quality_flags=tuple(quality_flags),
    )
