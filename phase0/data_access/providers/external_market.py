from __future__ import annotations

from typing import Any

import pandas as pd

from phase0.data_access.connectivity import fetch_hk_daily, fetch_tiingo_daily, fetch_tushare_hk_daily, fetch_yf_daily


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
        return fetch_yf_daily(to_yfinance_symbol(symbol), years=years)
    if provider == "tiingo":
        return fetch_tiingo_daily(symbol, years=years)
    if provider in {"akshare_hk", "akshare-hk"}:
        return fetch_hk_daily(symbol, years=years, adjust="qfq")
    if provider in {"tushare_hk", "tushare-hk"}:
        return fetch_tushare_hk_daily(symbol, years=years)
    raise ValueError(f"Unsupported market history provider: {provider}")
