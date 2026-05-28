from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import pandas as pd
import yfinance as yf

from phase0.env import prepare_imports

prepare_imports()

from backend.markets.cn import CNMarketSource  # noqa: E402
from backend.markets.hk import HKMarketSource  # noqa: E402


@dataclass
class ConnectivityResult:
    source: str
    target: str
    ok: bool
    rows: int
    latest_date: str
    error: str = ""


def _safe_latest_date(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    col = "date" if "date" in df.columns else None
    if col:
        return str(pd.to_datetime(df[col]).max().date())
    if isinstance(df.index, pd.DatetimeIndex):
        return str(df.index.max().date())
    return ""


def fetch_yf_daily(symbol: str, years: int) -> pd.DataFrame:
    end = date.today()
    start = end - timedelta(days=365 * years + 20)
    df = yf.download(
        symbol,
        start=start.isoformat(),
        end=end.isoformat(),
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        # yfinance may return MultiIndex columns even for single ticker.
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    df = df.reset_index().rename(
        columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adjusted_close",
            "Volume": "volume",
        }
    )
    keep = ["date", "open", "high", "low", "close", "adjusted_close", "volume"]
    return df[[c for c in keep if c in df.columns]].copy()


def check_connectivity(cfg: dict[str, Any], years: int) -> list[ConnectivityResult]:
    results: list[ConnectivityResult] = []
    ycfg = cfg.get("yfinance", {})
    for sym in ycfg.get("us_indices", []) + ycfg.get("us_equities", []) + ycfg.get("cnh_proxy", []):
        try:
            df = fetch_yf_daily(sym, years=years)
            err = ""
            if df.empty:
                err = "empty_or_rate_limited"
            results.append(
                ConnectivityResult(
                    source="yfinance",
                    target=sym,
                    ok=not df.empty,
                    rows=len(df),
                    latest_date=_safe_latest_date(df),
                    error=err,
                )
            )
        except Exception as exc:
            results.append(
                ConnectivityResult(
                    source="yfinance",
                    target=sym,
                    ok=False,
                    rows=0,
                    latest_date="",
                    error=str(exc),
                )
            )

    cns = CNMarketSource()
    for sym in cfg.get("akshare", {}).get("cn_symbols", []):
        try:
            end = date.today()
            start = end - timedelta(days=365 * years + 20)
            df = cns.get_daily_data(sym, start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), adjust="qfq")
            results.append(
                ConnectivityResult(
                    source="akshare-cn",
                    target=sym,
                    ok=not df.empty,
                    rows=len(df),
                    latest_date=_safe_latest_date(df),
                )
            )
        except Exception as exc:
            results.append(
                ConnectivityResult(
                    source="akshare-cn",
                    target=sym,
                    ok=False,
                    rows=0,
                    latest_date="",
                    error=str(exc),
                )
            )

    hks = HKMarketSource()
    for sym in cfg.get("akshare", {}).get("hk_symbols", []):
        try:
            end = date.today()
            start = end - timedelta(days=365 * years + 20)
            df = hks.get_daily_data(sym, start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), adjust="qfq")
            results.append(
                ConnectivityResult(
                    source="akshare-hk",
                    target=sym,
                    ok=not df.empty,
                    rows=len(df),
                    latest_date=_safe_latest_date(df),
                )
            )
        except Exception as exc:
            results.append(
                ConnectivityResult(
                    source="akshare-hk",
                    target=sym,
                    ok=False,
                    rows=0,
                    latest_date="",
                    error=str(exc),
                )
            )

    return results
