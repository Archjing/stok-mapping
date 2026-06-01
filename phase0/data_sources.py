from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import os
from typing import Any

import akshare as ak
import pandas as pd
import requests
import yfinance as yf

from phase0.local_history import normalize_cn_symbol
from phase0.throttle import configure_akshare_throttle, fetch_with_akshare_retries
from phase0.tushare_source import fetch_tushare_smoke, token_env_is_set, tushare_config


DEFAULT_FRED_SERIES: dict[str, str] = {
    "gdp": "GDP",
    "cpi": "CPIAUCSL",
    "fedfunds": "FEDFUNDS",
    "fedfunds_daily": "DFF",
    "vix": "VIXCLS",
}


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


def fetch_fred_series(
    series_id: str,
    years: int | None = None,
    start: date | None = None,
    end: date | None = None,
    api_key_env: str = "FRED_API_KEY",
) -> pd.DataFrame:
    if not series_id:
        return pd.DataFrame(columns=["date", "value"])
    if end is None:
        end = date.today()
    if start is None:
        if years is None:
            years = 10
        start = end - timedelta(days=365 * years + 20)
    params: dict[str, str] = {
        "series_id": str(series_id),
        "observation_start": start.isoformat(),
        "observation_end": end.isoformat(),
        "file_type": "json",
    }
    api_key = os.getenv(api_key_env, "").strip()
    if api_key:
        params["api_key"] = api_key
    resp = requests.get(
        "https://api.stlouisfed.org/fred/series/observations",
        params=params,
        timeout=20,
    )
    resp.raise_for_status()
    payload = resp.json()
    observations = payload.get("observations", [])
    if not observations:
        return pd.DataFrame(columns=["date", "value"])
    out = pd.DataFrame(observations)
    if "date" not in out.columns or "value" not in out.columns:
        return pd.DataFrame(columns=["date", "value"])
    out = out[["date", "value"]].copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    out = out.dropna(subset=["date", "value"]).sort_values("date")
    return out.reset_index(drop=True)


def fetch_cn_daily(symbol: str, years: int, adjust: str = "qfq") -> pd.DataFrame:
    end = date.today()
    start = end - timedelta(days=365 * years + 20)
    normalized = normalize_cn_symbol(symbol)
    code = normalized.split(".", 1)[1] if "." in normalized else str(symbol)
    df = fetch_with_akshare_retries(
        lambda: ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust=adjust,
        )
    )
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.rename(
        columns={
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
            "涨跌幅": "change_pct",
            "涨跌额": "change_amount",
            "换手率": "turnover_rate",
        }
    ).copy()
    out["date"] = pd.to_datetime(out["date"])
    out["symbol"] = normalized
    if "adjusted_close" not in out.columns:
        out["adjusted_close"] = out.get("close")
    keep = [
        "date",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "adjusted_close",
        "volume",
        "amount",
        "change_pct",
        "change_amount",
        "turnover_rate",
    ]
    return out[[c for c in keep if c in out.columns]].copy()


def fetch_hk_daily(symbol: str, years: int, adjust: str = "qfq") -> pd.DataFrame:
    end = date.today()
    start = end - timedelta(days=365 * years + 20)
    raw = str(symbol).strip().upper()
    code = raw.split(".", 1)[1] if "." in raw else raw
    code = code.zfill(5)
    df = fetch_with_akshare_retries(
        lambda: ak.stock_hk_hist(
            symbol=code,
            period="daily",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust=adjust,
        )
    )
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.rename(
        columns={
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
            "涨跌幅": "change_pct",
            "涨跌额": "change_amount",
        }
    ).copy()
    out["date"] = pd.to_datetime(out["date"])
    out["symbol"] = f"HK.{code}"
    if "adjusted_close" not in out.columns:
        out["adjusted_close"] = out.get("close")
    keep = [
        "date",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "adjusted_close",
        "volume",
        "amount",
        "change_pct",
        "change_amount",
    ]
    return out[[c for c in keep if c in out.columns]].copy()


def check_connectivity(cfg: dict[str, Any], years: int) -> list[ConnectivityResult]:
    results: list[ConnectivityResult] = []
    configure_akshare_throttle(cfg.get("akshare", {}))
    fcfg = cfg.get("fred", {})
    if bool(fcfg.get("enabled", False)):
        series_cfg = fcfg.get("series", {})
        api_key_env = str(fcfg.get("api_key_env", "FRED_API_KEY"))
        series_ids: list[str] = []
        if isinstance(series_cfg, dict):
            for default_key in DEFAULT_FRED_SERIES.keys():
                sid = str(series_cfg.get(default_key, DEFAULT_FRED_SERIES[default_key])).strip()
                if sid:
                    series_ids.append(sid)
        else:
            series_ids = list(DEFAULT_FRED_SERIES.values())
        seen: set[str] = set()
        for series_id in series_ids:
            if series_id in seen:
                continue
            seen.add(series_id)
            try:
                df = fetch_fred_series(series_id, years=years, api_key_env=api_key_env)
                err = ""
                if df.empty:
                    err = "empty_or_no_valid_values"
                results.append(
                    ConnectivityResult(
                        source="fred",
                        target=series_id,
                        ok=not df.empty,
                        rows=len(df),
                        latest_date=_safe_latest_date(df),
                        error=err,
                    )
                )
            except Exception as exc:
                results.append(
                    ConnectivityResult(
                        source="fred",
                        target=series_id,
                        ok=False,
                        rows=0,
                        latest_date="",
                        error=str(exc),
                    )
                )

    tcfg = tushare_config(cfg.get("tushare", {}))
    if tcfg.enabled:
        if not token_env_is_set(tcfg):
            results.append(
                ConnectivityResult(
                    source="tushare",
                    target="trade_cal",
                    ok=False,
                    rows=0,
                    latest_date="",
                    error=f"missing_token_env:{tcfg.token_env}",
                )
            )
        else:
            try:
                df = fetch_tushare_smoke(tcfg)
                latest = ""
                if not df.empty and "cal_date" in df.columns:
                    latest = str(pd.to_datetime(df["cal_date"], format="%Y%m%d", errors="coerce").max().date())
                results.append(
                    ConnectivityResult(
                        source="tushare",
                        target="trade_cal",
                        ok=not df.empty,
                        rows=len(df),
                        latest_date=latest,
                        error="" if not df.empty else "empty",
                    )
                )
            except Exception as exc:
                results.append(
                    ConnectivityResult(
                        source="tushare",
                        target="trade_cal",
                        ok=False,
                        rows=0,
                        latest_date="",
                        error=str(exc),
                    )
                )

    ycfg = cfg.get("yfinance", {})
    yf_targets = (
        ycfg.get("us_indices", [])
        + ycfg.get("us_equities", [])
        + ycfg.get("thematic_etfs", [])
        + ycfg.get("cnh_proxy", [])
    )
    for sym in yf_targets:
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

    for sym in cfg.get("akshare", {}).get("cn_symbols", []):
        try:
            df = fetch_cn_daily(sym, years=years, adjust="qfq")
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

    for sym in cfg.get("akshare", {}).get("hk_symbols", []):
        try:
            df = fetch_hk_daily(sym, years=years, adjust="qfq")
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
