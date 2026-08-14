from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Callable, Iterable

import pandas as pd


class ChinaOptionsProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class HoQuoteRow:
    trade_date: date
    observed_at: datetime
    market: str
    underlying: str
    expiry_month: str
    expiry_date: date
    contract: str
    option_type: str
    strike: float
    last_price: float | None
    bid: float | None
    ask: float | None
    bid_volume: float | None
    ask_volume: float | None
    volume: float | None
    open_interest: float | None
    source: str = "akshare_sina"


def _number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip().replace(",", "")
    if text in {"", "-", "--", "None", "nan"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def normalize_expiry_month(value: str) -> str:
    month = str(value).strip().lower().replace("ho", "")
    if len(month) != 4 or not month.isdigit():
        raise ChinaOptionsProviderError(f"invalid HO expiry month: {value}")
    return month


def third_friday(year: int, month: int) -> date:
    weeks = calendar.monthcalendar(year, month)
    fridays = [week[calendar.FRIDAY] for week in weeks if week[calendar.FRIDAY]]
    return date(year, month, fridays[2])


def expiry_date_for_month(
    month: str,
    overrides: dict[str, str] | None = None,
    *,
    is_open_date: Callable[[date], bool] | None = None,
) -> date:
    normalized = normalize_expiry_month(month)
    if overrides and normalized in overrides:
        return date.fromisoformat(str(overrides[normalized]))
    expiry = third_friday(2000 + int(normalized[:2]), int(normalized[2:]))
    if is_open_date is None:
        return expiry
    for offset in range(8):
        candidate = expiry + timedelta(days=offset)
        if is_open_date(candidate):
            return candidate
    raise ChinaOptionsProviderError(
        f"no open CN session found within 7 days after HO{normalized} third Friday"
    )


def _column_value(row: pd.Series, candidates: Iterable[str]) -> float | None:
    for name in candidates:
        if name in row.index:
            return _number(row[name])
    return None


def normalize_ho_chain(
    frame: pd.DataFrame,
    *,
    month: str,
    trade_date: date,
    expiry_date: date,
    observed_at: datetime,
) -> list[HoQuoteRow]:
    normalized = normalize_expiry_month(month)
    rows: list[HoQuoteRow] = []
    for _, item in frame.iterrows():
        strike = _number(item.get("行权价"))
        if strike is None or strike <= 0:
            continue
        strike_text = str(int(strike)) if strike.is_integer() else f"{strike:g}"
        for option_type, label in (("C", "看涨合约"), ("P", "看跌合约")):
            rows.append(
                HoQuoteRow(
                    trade_date=trade_date,
                    observed_at=observed_at,
                    market="CFFEX",
                    underlying="HO",
                    expiry_month=normalized,
                    expiry_date=expiry_date,
                    contract=f"HO{normalized}{option_type}{strike_text}",
                    option_type=option_type,
                    strike=strike,
                    last_price=_column_value(item, [f"{label}-最新价"]),
                    bid=_column_value(item, [f"{label}-买价"]),
                    ask=_column_value(item, [f"{label}-卖价"]),
                    bid_volume=_column_value(item, [f"{label}-买量"]),
                    ask_volume=_column_value(item, [f"{label}-卖量"]),
                    volume=_column_value(item, [f"{label}-成交量", f"{label}-成交手数"]),
                    open_interest=_column_value(item, [f"{label}-持仓量"]),
                )
            )
    if not rows:
        raise ChinaOptionsProviderError(f"empty or unrecognized HO chain for {normalized}")
    return rows


class AkshareHoProvider:
    source = "akshare_sina"

    def __init__(self, ak_module: Any | None = None) -> None:
        if ak_module is None:
            try:
                import akshare as ak_module
            except ImportError as exc:
                raise ChinaOptionsProviderError("akshare is required for HO collection") from exc
        self.ak = ak_module

    def list_months(self) -> list[str]:
        try:
            payload = self.ak.option_cffex_sz50_list_sina()
        except Exception as exc:
            raise ChinaOptionsProviderError(f"failed to list HO months: {exc}") from exc
        values = payload.get("上证50指数", []) if isinstance(payload, dict) else payload
        months = sorted({normalize_expiry_month(value) for value in list(values or [])})
        if not months:
            raise ChinaOptionsProviderError("HO month list is empty")
        return months

    def fetch_chain(
        self,
        month: str,
        *,
        trade_date: date,
        expiry_date: date,
        observed_at: datetime,
    ) -> list[HoQuoteRow]:
        normalized = normalize_expiry_month(month)
        try:
            frame = self.ak.option_cffex_sz50_spot_sina(symbol=f"ho{normalized}")
        except Exception as exc:
            raise ChinaOptionsProviderError(f"failed to fetch HO{normalized}: {exc}") from exc
        if frame is None or frame.empty:
            raise ChinaOptionsProviderError(f"HO{normalized} returned no quotes")
        return normalize_ho_chain(
            frame,
            month=normalized,
            trade_date=trade_date,
            expiry_date=expiry_date,
            observed_at=observed_at,
        )

    def fetch_shibor_3m(self) -> float:
        try:
            frame = self.ak.rate_interbank(
                market="上海银行同业拆借市场",
                symbol="Shibor人民币",
                indicator="3月",
            )
        except Exception as exc:
            raise ChinaOptionsProviderError(f"failed to fetch Shibor 3M: {exc}") from exc
        if frame is None or frame.empty or "利率" not in frame:
            raise ChinaOptionsProviderError("Shibor 3M returned no rate")
        rate = _number(frame.iloc[-1]["利率"])
        if rate is None or rate < 0:
            raise ChinaOptionsProviderError("Shibor 3M rate is invalid")
        return rate / 100.0
