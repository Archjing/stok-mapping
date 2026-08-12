from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from phase0.data_access.connectivity import (
    fetch_hk_daily,
    fetch_tiingo_daily,
    fetch_tushare_hk_daily,
    fetch_yahoo_chart_daily,
    fetch_yf_daily,
)


def to_yfinance_symbol(symbol: str) -> str:
    raw = str(symbol).strip().upper()
    if raw.startswith("HK."):
        code = raw.split(".", 1)[1]
        if code.isdigit():
            code = str(int(code)).zfill(4)
        return f"{code}.HK"
    return raw


def fetch_external_market_daily(symbol: str, settings: Any) -> pd.DataFrame:
    provider = str(settings.provider)
    years = int(settings.years)
    if provider == "yfinance":
        yf_symbol = to_yfinance_symbol(symbol)
        start = getattr(settings, "fetch_start_date", None)
        if start is not None and not isinstance(start, date):
            raise TypeError("fetch_start_date must be a date when provided")
        # yfinance's download flow currently hits Yahoo's crumb/session rate
        # limit before ordinary Chart API requests do.  Use the direct Yahoo
        # endpoint first, retaining yfinance only as a same-source fallback.
        try:
            frame = fetch_yahoo_chart_daily(yf_symbol, years=years, start=start)
        except Exception:
            frame = pd.DataFrame()
        if not frame.empty:
            return frame
        return fetch_yf_daily(yf_symbol, years=years)
    if provider == "tiingo":
        return fetch_tiingo_daily(symbol, years=years)
    if provider in {"akshare_hk", "akshare-hk"}:
        return fetch_hk_daily(symbol, years=years, adjust="qfq")
    if provider in {"tushare_hk", "tushare-hk"}:
        return fetch_tushare_hk_daily(symbol, years=years)
    raise ValueError(f"Unsupported market history provider: {provider}")
