from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import pandas as pd
import requests

from phase0.local_history import normalize_cn_symbol


TUSHARE_API_URL = "http://api.tushare.pro"


@dataclass
class TushareConfig:
    enabled: bool = False
    token_env: str = "TUSHARE_TOKEN"
    api_url: str = TUSHARE_API_URL
    request_delay: float = 0.25
    max_retries: int = 3
    retry_backoff: float = 2.0
    min_coverage: float = 0.80


def tushare_config(raw: dict[str, Any] | None) -> TushareConfig:
    cfg = raw or {}
    return TushareConfig(
        enabled=bool(cfg.get("enabled", False)),
        token_env=str(cfg.get("token_env", "TUSHARE_TOKEN")),
        api_url=str(cfg.get("api_url", TUSHARE_API_URL)),
        request_delay=float(cfg.get("request_delay", 0.25)),
        max_retries=int(cfg.get("max_retries", 3)),
        retry_backoff=float(cfg.get("retry_backoff", 2.0)),
        min_coverage=float(cfg.get("min_coverage", 0.80)),
    )


def _token(cfg: TushareConfig) -> str:
    return os.environ.get(cfg.token_env, "").strip()


def tushare_available(cfg: TushareConfig) -> bool:
    return bool(cfg.enabled and _token(cfg))


def token_env_is_set(cfg: TushareConfig) -> bool:
    return bool(_token(cfg))


def _call(api_name: str, *, params: dict[str, Any], fields: list[str], cfg: TushareConfig) -> pd.DataFrame:
    token = _token(cfg)
    if not token:
        raise RuntimeError(f"Tushare token is not set in environment variable {cfg.token_env}")

    payload = {
        "api_name": api_name,
        "token": token,
        "params": params,
        "fields": ",".join(fields),
    }
    last_error: Exception | None = None
    for attempt in range(max(1, cfg.max_retries)):
        try:
            response = requests.post(cfg.api_url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            if data.get("code") != 0:
                raise RuntimeError(f"Tushare {api_name} failed: code={data.get('code')}, msg={data.get('msg')}")
            items = data.get("data", {}).get("items", [])
            columns = data.get("data", {}).get("fields", fields)
            return pd.DataFrame(items, columns=columns)
        except Exception as exc:
            last_error = exc
            if attempt + 1 < max(1, cfg.max_retries):
                time.sleep(cfg.retry_backoff * (attempt + 1))
    raise RuntimeError(str(last_error) if last_error else f"Tushare {api_name} failed")


def _parse_trade_date(value: date | str) -> str:
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    return str(value).replace("-", "")[:8]


def _normalize_daily(raw: pd.DataFrame, *, trade_date: date, adjust_types: list[str], adj_factor: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    out = raw.copy()
    out["symbol"] = out["ts_code"].map(normalize_cn_symbol)
    out["date"] = pd.to_datetime(out["trade_date"], format="%Y%m%d", errors="coerce").dt.strftime("%Y-%m-%d")
    for col in ["open", "high", "low", "close", "vol", "amount", "pct_chg", "change"]:
        out[col] = pd.to_numeric(out.get(col), errors="coerce")
    out = out.dropna(subset=["symbol", "date", "open", "high", "low", "close"])
    out = out[out["symbol"] != ""].copy()
    if out.empty:
        return out

    factor = adj_factor.copy()
    if not factor.empty:
        factor["symbol"] = factor["ts_code"].map(normalize_cn_symbol)
        factor["adj_factor"] = pd.to_numeric(factor["adj_factor"], errors="coerce")
        out = out.merge(factor[["symbol", "adj_factor"]], on="symbol", how="left")
    else:
        out["adj_factor"] = pd.NA

    frames: list[pd.DataFrame] = []
    keep = [
        "market",
        "symbol",
        "date",
        "adjust_type",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "adjusted_close",
        "change_pct",
        "change_amount",
        "amplitude",
        "turnover_rate",
    ]
    base = pd.DataFrame(
        {
            "market": "CN",
            "symbol": out["symbol"],
            "date": out["date"],
            "open": out["open"],
            "high": out["high"],
            "low": out["low"],
            "close": out["close"],
            "volume": out["vol"],
            "amount": out["amount"] * 1000.0,
            "adjusted_close": out["close"],
            "change_pct": out["pct_chg"],
            "change_amount": out["change"],
            "amplitude": ((out["high"] - out["low"]) / out["close"].replace(0, pd.NA) * 100.0),
            "turnover_rate": pd.NA,
            "_adj_factor": out["adj_factor"],
        }
    )
    for adjust_type in adjust_types:
        frame = base.copy()
        frame["adjust_type"] = adjust_type
        if adjust_type == "qfq" and frame["_adj_factor"].notna().any():
            # QFQ relative to the trade-date factor. For a one-day incremental row,
            # today's unadjusted OHLC equals today's forward-adjusted OHLC.
            frame["adjusted_close"] = frame["close"]
        frames.append(frame[[col for col in keep if col in frame.columns]])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=keep)


def _normalize_daily_basic(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    out = raw.copy()
    out["symbol"] = out["ts_code"].map(normalize_cn_symbol)
    for col in ["total_mv", "circ_mv", "pe_ttm", "pb", "turnover_rate"]:
        out[col] = pd.to_numeric(out.get(col), errors="coerce")
    return pd.DataFrame(
        {
            "market": "CN",
            "symbol": out["symbol"],
            "market_cap": out["total_mv"] * 10_000.0,
            "circ_mv": out["circ_mv"] * 10_000.0,
            "pe_ratio": out["pe_ttm"],
            "pb_ratio": out["pb"],
            "turnover_rate": out["turnover_rate"],
        }
    ).dropna(subset=["symbol"])


def fetch_tushare_trade_date(
    trade_date: date,
    *,
    adjust_types: list[str],
    cfg: TushareConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    trade_date_text = _parse_trade_date(trade_date)
    daily = _call(
        "daily",
        params={"trade_date": trade_date_text},
        fields=["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"],
        cfg=cfg,
    )
    time.sleep(max(0.0, cfg.request_delay))
    basic = _call(
        "daily_basic",
        params={"trade_date": trade_date_text},
        fields=["ts_code", "trade_date", "turnover_rate", "pe_ttm", "pb", "total_mv", "circ_mv"],
        cfg=cfg,
    )
    time.sleep(max(0.0, cfg.request_delay))
    factors = _call(
        "adj_factor",
        params={"trade_date": trade_date_text},
        fields=["ts_code", "trade_date", "adj_factor"],
        cfg=cfg,
    )

    rows = _normalize_daily(daily, trade_date=trade_date, adjust_types=adjust_types, adj_factor=factors)
    meta = _normalize_daily_basic(basic)
    if not rows.empty and not meta.empty:
        rows = rows.merge(meta[["symbol", "turnover_rate"]], on="symbol", how="left", suffixes=("", "_basic"))
        rows["turnover_rate"] = rows["turnover_rate_basic"].combine_first(rows["turnover_rate"])
        rows = rows.drop(columns=["turnover_rate_basic"])
    rows.attrs["source"] = "tushare.daily+daily_basic+adj_factor"
    meta.attrs["source"] = "tushare.daily_basic"
    return rows, meta


def fetch_tushare_smoke(cfg: TushareConfig, *, days: int = 10) -> pd.DataFrame:
    today = date.today()
    start = today - timedelta(days=max(1, int(days)))
    return _call(
        "trade_cal",
        params={
            "exchange": "SSE",
            "start_date": start.strftime("%Y%m%d"),
            "end_date": today.strftime("%Y%m%d"),
        },
        fields=["exchange", "cal_date", "is_open", "pretrade_date"],
        cfg=cfg,
    )
