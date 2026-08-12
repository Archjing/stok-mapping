from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import pandas as pd
import requests

from quant.data_access.local_history import normalize_cn_symbol
from quant.data_access.symbols import from_tushare_symbol, normalize_etf_symbol, to_tushare_symbol


TUSHARE_API_URL = "http://api.tushare.pro"

ETF_CATALOG_COLUMNS = [
    "symbol", "ts_code", "name", "short_name", "exchange", "list_status",
    "setup_date", "list_date", "delist_date", "etf_type", "management_name",
    "custodian_name", "management_fee", "index_code_raw",
    "tracking_index_symbol", "tracking_index_name", "source",
]
ETF_DAILY_COLUMNS = [
    "symbol", "ts_code", "date", "price_mode", "open", "high", "low", "close",
    "pre_close", "change_amount", "change_pct", "volume", "amount", "source",
]
ETF_FACTOR_COLUMNS = ["symbol", "ts_code", "date", "adj_factor", "source"]


class TushareAPIError(RuntimeError):
    def __init__(self, api_name: str, code: object, message: str):
        super().__init__(f"Tushare {api_name} failed: code={code}, msg={message}")
        self.api_name = api_name
        self.code = code
        self.message = message


class TusharePermissionError(TushareAPIError):
    """The token is valid but the endpoint or fields are not authorized."""


class TushareTokenError(TushareAPIError):
    """The configured token is missing, invalid, or rejected."""


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
        raise TushareTokenError(api_name, None, f"token is not set in environment variable {cfg.token_env}")

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
            code = data.get("code")
            message = str(data.get("msg") or "unknown error")
            if code != 0:
                lowered = message.lower()
                if "permission" in lowered or "权限" in message:
                    raise TusharePermissionError(api_name, code, message)
                if "token" in lowered:
                    raise TushareTokenError(api_name, code, message)
                raise TushareAPIError(api_name, code, message)
            response_data = data.get("data") or {}
            items = response_data.get("items", [])
            columns = response_data.get("fields", fields)
            return pd.DataFrame(items, columns=columns)
        except TushareAPIError:
            raise
        except Exception as exc:
            last_error = exc
            if attempt + 1 < max(1, cfg.max_retries):
                time.sleep(cfg.retry_backoff * (attempt + 1))
    raise RuntimeError(str(last_error) if last_error else f"Tushare {api_name} failed")


def _iso_date(value: object) -> str | None:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    parsed = pd.to_datetime(str(value), format="%Y%m%d", errors="coerce")
    return None if pd.isna(parsed) else parsed.strftime("%Y-%m-%d")


def fetch_tushare_etf_basic(*, list_status: str, cfg: TushareConfig) -> pd.DataFrame:
    fields = [
        "ts_code", "csname", "extname", "cname", "index_code", "index_name",
        "setup_date", "list_date", "delist_date", "list_status", "exchange",
        "mgt_name", "custod_name", "mgt_fee", "etf_type",
    ]
    raw = _call("etf_basic", params={"list_status": list_status}, fields=fields, cfg=cfg)
    if raw.empty:
        return pd.DataFrame(columns=ETF_CATALOG_COLUMNS)
    out = pd.DataFrame(index=raw.index)
    out["symbol"] = raw["ts_code"].map(from_tushare_symbol)
    out["ts_code"] = raw["ts_code"].astype(str).str.upper()
    out["name"] = raw.get("cname", raw.get("extname"))
    out["short_name"] = raw.get("csname")
    out["exchange"] = raw.get("exchange")
    out["list_status"] = raw.get("list_status")
    out["setup_date"] = raw.get("setup_date", pd.Series(index=raw.index, dtype=object)).map(_iso_date)
    out["list_date"] = raw.get("list_date", pd.Series(index=raw.index, dtype=object)).map(_iso_date)
    out["delist_date"] = raw.get("delist_date", pd.Series(index=raw.index, dtype=object)).map(_iso_date)
    out["etf_type"] = raw.get("etf_type")
    out["management_name"] = raw.get("mgt_name")
    out["custodian_name"] = raw.get("custod_name")
    out["management_fee"] = pd.to_numeric(raw.get("mgt_fee"), errors="coerce")
    out["index_code_raw"] = raw.get("index_code")
    out["tracking_index_symbol"] = raw.get("index_code", pd.Series(index=raw.index, dtype=object)).map(from_tushare_symbol)
    out["tracking_index_name"] = raw.get("index_name")
    out["source"] = "tushare.etf_basic"
    return out[ETF_CATALOG_COLUMNS].reset_index(drop=True)


def fetch_tushare_etf_daily(
    symbol: str,
    *,
    start_date: date | str,
    end_date: date | str,
    cfg: TushareConfig,
) -> pd.DataFrame:
    local = normalize_etf_symbol(symbol)
    ts_code = to_tushare_symbol(local)
    fields = ["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"]
    raw = _call("fund_daily", params={"ts_code": ts_code, "start_date": _parse_trade_date(start_date), "end_date": _parse_trade_date(end_date)}, fields=fields, cfg=cfg)
    if raw.empty:
        return pd.DataFrame(columns=ETF_DAILY_COLUMNS)
    out = pd.DataFrame(index=raw.index)
    out["symbol"] = raw["ts_code"].map(from_tushare_symbol)
    out["ts_code"] = raw["ts_code"].astype(str).str.upper()
    out["date"] = pd.to_datetime(raw["trade_date"], format="%Y%m%d", errors="coerce").dt.strftime("%Y-%m-%d")
    out["price_mode"] = "raw"
    for target, source in (("open", "open"), ("high", "high"), ("low", "low"), ("close", "close"), ("pre_close", "pre_close"), ("change_amount", "change"), ("change_pct", "pct_chg")):
        out[target] = pd.to_numeric(raw.get(source), errors="coerce")
    out["volume"] = pd.to_numeric(raw.get("vol"), errors="coerce") * 100.0
    out["amount"] = pd.to_numeric(raw.get("amount"), errors="coerce") * 1000.0
    out["source"] = "tushare.fund_daily"
    return out[ETF_DAILY_COLUMNS].reset_index(drop=True)


def fetch_tushare_etf_adj_factors(
    symbol: str,
    *,
    start_date: date | str,
    end_date: date | str,
    cfg: TushareConfig,
) -> pd.DataFrame:
    local = normalize_etf_symbol(symbol)
    ts_code = to_tushare_symbol(local)
    fields = ["ts_code", "trade_date", "adj_factor"]
    raw = _call("fund_adj", params={"ts_code": ts_code, "start_date": _parse_trade_date(start_date), "end_date": _parse_trade_date(end_date)}, fields=fields, cfg=cfg)
    if raw.empty:
        return pd.DataFrame(columns=ETF_FACTOR_COLUMNS)
    out = pd.DataFrame(index=raw.index)
    out["symbol"] = raw["ts_code"].map(from_tushare_symbol)
    out["ts_code"] = raw["ts_code"].astype(str).str.upper()
    out["date"] = pd.to_datetime(raw["trade_date"], format="%Y%m%d", errors="coerce").dt.strftime("%Y-%m-%d")
    out["adj_factor"] = pd.to_numeric(raw.get("adj_factor"), errors="coerce")
    out["source"] = "tushare.fund_adj"
    return out[ETF_FACTOR_COLUMNS].reset_index(drop=True)


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
    out["trade_date"] = pd.to_datetime(out["trade_date"], format="%Y%m%d", errors="coerce").dt.strftime("%Y-%m-%d")
    for col in ["total_mv", "circ_mv", "pe_ttm", "pb", "turnover_rate"]:
        out[col] = pd.to_numeric(out.get(col), errors="coerce")
    return pd.DataFrame(
        {
            "market": "CN",
            "symbol": out["symbol"],
            "date": out["trade_date"],
            "market_cap": out["total_mv"] * 10_000.0,
            "circ_mv": out["circ_mv"] * 10_000.0,
            "pe_ratio": out["pe_ttm"],
            "pb_ratio": out["pb"],
            "turnover_rate": out["turnover_rate"],
        }
    ).dropna(subset=["symbol", "date"])


def fetch_tushare_daily_basic_trade_date(trade_date: date | str, *, cfg: TushareConfig) -> pd.DataFrame:
    trade_date_text = _parse_trade_date(trade_date)
    raw = _call(
        "daily_basic",
        params={"trade_date": trade_date_text},
        fields=["ts_code", "trade_date", "turnover_rate", "pe_ttm", "pb", "total_mv", "circ_mv"],
        cfg=cfg,
    )
    out = _normalize_daily_basic(raw)
    out.attrs["source"] = "tushare.daily_basic"
    return out


def normalize_adj_factors(raw: pd.DataFrame, *, source: str = "tushare.adj_factor") -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=["market", "symbol", "date", "adj_factor", "source"])
    out = raw.copy()
    out["symbol"] = out["ts_code"].map(normalize_cn_symbol)
    out["date"] = pd.to_datetime(out["trade_date"], format="%Y%m%d", errors="coerce").dt.strftime("%Y-%m-%d")
    out["adj_factor"] = pd.to_numeric(out.get("adj_factor"), errors="coerce")
    out = out.dropna(subset=["symbol", "date", "adj_factor"])
    out = out[out["symbol"] != ""].copy()
    out["market"] = "CN"
    out["source"] = source
    return out[["market", "symbol", "date", "adj_factor", "source"]]


def fetch_tushare_adj_factor_trade_date(trade_date: date, *, cfg: TushareConfig) -> pd.DataFrame:
    trade_date_text = _parse_trade_date(trade_date)
    raw = _call(
        "adj_factor",
        params={"trade_date": trade_date_text},
        fields=["ts_code", "trade_date", "adj_factor"],
        cfg=cfg,
    )
    return normalize_adj_factors(raw)


def fetch_tushare_adj_factor_symbol(
    symbol: str,
    *,
    start_date: date | str,
    end_date: date | str,
    cfg: TushareConfig,
) -> pd.DataFrame:
    code = normalize_cn_symbol(symbol)
    if not code:
        return pd.DataFrame(columns=["market", "symbol", "date", "adj_factor", "source"])
    market, digits = code.split(".")
    ts_code = f"{digits}.{market}"
    raw = _call(
        "adj_factor",
        params={
            "ts_code": ts_code,
            "start_date": _parse_trade_date(start_date),
            "end_date": _parse_trade_date(end_date),
        },
        fields=["ts_code", "trade_date", "adj_factor"],
        cfg=cfg,
    )
    return normalize_adj_factors(raw)


INDEX_DAILY_COLUMNS = [
    "market",
    "symbol",
    "date",
    "frequency",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "advances",
    "declines",
    "name",
    "source",
]


def fetch_tushare_index_daily(
    local_symbol: str,
    *,
    ts_code: str,
    start_date: date | str,
    end_date: date | str,
    cfg: TushareConfig,
    name: str = "",
) -> pd.DataFrame:
    """Fetch daily bars for one index via Tushare index_daily.

    ``local_symbol`` keeps the database's own symbol form (e.g. ``SH.000001``)
    while ``ts_code`` is the Tushare code (e.g. ``000001.SH``).  Index bars are
    stored in ``market_index_bars`` with the same column layout the zip import
    uses; Tushare does not provide advances/declines so those stay NULL.
    """
    raw = _call(
        "index_daily",
        params={
            "ts_code": ts_code,
            "start_date": _parse_trade_date(start_date),
            "end_date": _parse_trade_date(end_date),
        },
        fields=["ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount"],
        cfg=cfg,
    )
    if raw.empty:
        return pd.DataFrame(columns=INDEX_DAILY_COLUMNS)
    out = raw.copy()
    out["symbol"] = local_symbol
    out["date"] = pd.to_datetime(out["trade_date"], format="%Y%m%d", errors="coerce").dt.strftime("%Y-%m-%d")
    for col in ["open", "high", "low", "close", "vol", "amount"]:
        out[col] = pd.to_numeric(out.get(col), errors="coerce")
    out = out.dropna(subset=["date", "open", "high", "low", "close"]).copy()
    out["market"] = "CN"
    out["frequency"] = "daily"
    out["volume"] = out["vol"]
    # Tushare amounts are in thousands of yuan; the manual history tables store yuan.
    out["amount"] = out["amount"] * 1000.0
    out["advances"] = None
    out["declines"] = None
    out["name"] = name
    out["source"] = "tushare.index_daily"
    return out.loc[:, INDEX_DAILY_COLUMNS].copy()


def normalize_dividend(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    out = raw.copy()
    out["symbol"] = out["ts_code"].map(normalize_cn_symbol)
    date_fields = ["record_date", "ex_date", "pay_date", "div_listdate", "imp_ann_date", "base_date", "ann_date"]
    for col in date_fields:
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], format="%Y%m%d", errors="coerce").dt.strftime("%Y-%m-%d")
    numeric_fields = [
        "stk_div",
        "stk_bo_rate",
        "stk_co_rate",
        "cash_div",
        "cash_div_tax",
        "base_share",
    ]
    for col in numeric_fields:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out[out["symbol"] != ""].copy()
    out["market"] = "CN"
    keep = [
        "market",
        "symbol",
        "ann_date",
        "div_proc",
        "stk_div",
        "stk_bo_rate",
        "stk_co_rate",
        "cash_div",
        "cash_div_tax",
        "record_date",
        "ex_date",
        "pay_date",
        "div_listdate",
        "imp_ann_date",
        "base_date",
        "base_share",
    ]
    return out[[col for col in keep if col in out.columns]].drop_duplicates()


def fetch_tushare_dividend(
    *,
    start_date: date | str,
    end_date: date | str,
    cfg: TushareConfig,
) -> pd.DataFrame:
    raw = _call(
        "dividend",
        params={
            "ann_date": "",
            "start_date": _parse_trade_date(start_date),
            "end_date": _parse_trade_date(end_date),
        },
        fields=[
            "ts_code",
            "ann_date",
            "div_proc",
            "stk_div",
            "stk_bo_rate",
            "stk_co_rate",
            "cash_div",
            "cash_div_tax",
            "record_date",
            "ex_date",
            "pay_date",
            "div_listdate",
            "imp_ann_date",
            "base_date",
            "base_share",
        ],
        cfg=cfg,
    )
    return normalize_dividend(raw)


def normalize_tushare_financial_factors(
    *,
    income: pd.DataFrame,
    cashflow: pd.DataFrame,
    balancesheet: pd.DataFrame,
    fina_indicator: pd.DataFrame,
    source: str = "tushare.income/cashflow/balancesheet/fina_indicator",
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []

    def numeric_series(frame: pd.DataFrame, column: str) -> pd.Series:
        if column in frame.columns:
            return pd.to_numeric(frame[column], errors="coerce")
        return pd.Series(pd.NA, index=frame.index, dtype="Float64")

    if income is not None and not income.empty:
        inc = income.copy()
        inc["symbol"] = inc["ts_code"].map(normalize_cn_symbol)
        inc["report_date"] = pd.to_datetime(inc.get("end_date"), format="%Y%m%d", errors="coerce").dt.strftime("%Y-%m-%d")
        inc["announce_date"] = pd.to_datetime(inc.get("ann_date"), format="%Y%m%d", errors="coerce").dt.strftime("%Y-%m-%d")
        for col in ["revenue", "n_income_attr_p"]:
            inc[col] = pd.to_numeric(inc.get(col), errors="coerce")
        frames.append(
            inc[["symbol", "report_date", "announce_date", "revenue", "n_income_attr_p"]].rename(
                columns={"n_income_attr_p": "net_profit"}
            )
        )

    out = frames[0] if frames else pd.DataFrame(columns=["symbol", "report_date"])
    if cashflow is not None and not cashflow.empty:
        cf = cashflow.copy()
        cf["symbol"] = cf["ts_code"].map(normalize_cn_symbol)
        cf["report_date"] = pd.to_datetime(cf.get("end_date"), format="%Y%m%d", errors="coerce").dt.strftime("%Y-%m-%d")
        cf["operating_cash_flow"] = pd.to_numeric(cf.get("n_cashflow_act"), errors="coerce")
        out = out.merge(cf[["symbol", "report_date", "operating_cash_flow"]], on=["symbol", "report_date"], how="outer")

    if balancesheet is not None and not balancesheet.empty:
        bs = balancesheet.copy()
        bs["symbol"] = bs["ts_code"].map(normalize_cn_symbol)
        bs["report_date"] = pd.to_datetime(bs.get("end_date"), format="%Y%m%d", errors="coerce").dt.strftime("%Y-%m-%d")
        for col in ["total_assets", "total_liab", "total_hldr_eqy_exc_min_int"]:
            bs[col] = pd.to_numeric(bs.get(col), errors="coerce")
        bs["debt_to_asset"] = bs["total_liab"] / bs["total_assets"].replace(0, pd.NA) * 100.0
        out = out.merge(
            bs[["symbol", "report_date", "debt_to_asset", "total_assets", "total_liab", "total_hldr_eqy_exc_min_int"]].rename(
                columns={"total_liab": "total_liabilities", "total_hldr_eqy_exc_min_int": "total_equity"}
            ),
            on=["symbol", "report_date"],
            how="outer",
        )

    if fina_indicator is not None and not fina_indicator.empty:
        fi = fina_indicator.copy()
        fi["symbol"] = fi["ts_code"].map(normalize_cn_symbol)
        fi["report_date"] = pd.to_datetime(fi.get("end_date"), format="%Y%m%d", errors="coerce").dt.strftime("%Y-%m-%d")
        fi["announce_date_fina"] = pd.to_datetime(fi.get("ann_date"), format="%Y%m%d", errors="coerce").dt.strftime("%Y-%m-%d")
        for col in ["roe", "tr_yoy", "netprofit_yoy", "debt_to_assets"]:
            fi[col] = pd.to_numeric(fi.get(col), errors="coerce")
        out = out.merge(
            fi[["symbol", "report_date", "announce_date_fina", "roe", "tr_yoy", "netprofit_yoy", "debt_to_assets"]],
            on=["symbol", "report_date"],
            how="outer",
        )

    if out.empty:
        return pd.DataFrame()
    out["symbol"] = out["symbol"].map(normalize_cn_symbol)
    out = out[out["symbol"] != ""].copy()
    out["market"] = "CN"
    out["announce_date"] = out.get("announce_date", pd.Series(index=out.index, dtype=object)).combine_first(
        out.get("announce_date_fina", pd.Series(index=out.index, dtype=object))
    )
    out["roe"] = numeric_series(out, "roe")
    out["revenue_growth"] = numeric_series(out, "tr_yoy")
    out["profit_growth"] = numeric_series(out, "netprofit_yoy")
    out["debt_to_asset"] = numeric_series(out, "debt_to_asset").combine_first(numeric_series(out, "debt_to_assets"))
    net_profit = numeric_series(out, "net_profit")
    operating_cash_flow = numeric_series(out, "operating_cash_flow")
    out["operating_cash_flow_to_net_profit"] = operating_cash_flow / net_profit.replace(0, pd.NA)
    out["fiscal_year"] = pd.to_datetime(out["report_date"], errors="coerce").dt.year
    out["fiscal_quarter"] = pd.to_datetime(out["report_date"], errors="coerce").dt.quarter
    out["source"] = source
    out["updated_at"] = pd.Timestamp.now().isoformat(timespec="seconds")
    keep = [
        "market",
        "symbol",
        "report_date",
        "fiscal_year",
        "fiscal_quarter",
        "announce_date",
        "roe",
        "revenue",
        "revenue_growth",
        "net_profit",
        "profit_growth",
        "operating_cash_flow",
        "operating_cash_flow_to_net_profit",
        "debt_to_asset",
        "total_assets",
        "total_liabilities",
        "total_equity",
        "source",
        "updated_at",
    ]
    for col in keep:
        if col not in out.columns:
            out[col] = pd.NA
    return out[keep].dropna(subset=["symbol", "report_date"]).drop_duplicates(["market", "symbol", "report_date"])


def _to_tushare_code(symbol: str) -> str:
    code = normalize_cn_symbol(symbol)
    if not code or "." not in code:
        return ""
    market, digits = code.split(".", 1)
    return f"{digits}.{market}"


def fetch_tushare_financial_period(
    period: date | str,
    *,
    cfg: TushareConfig,
    ts_code: str = "",
    interfaces: set[str] | None = None,
) -> pd.DataFrame:
    period_text = _parse_trade_date(period)
    code = _to_tushare_code(ts_code) if ts_code else ""
    common_params = {"period": period_text}
    if code:
        common_params["ts_code"] = code
    requested = interfaces or {"income", "cashflow", "balancesheet", "fina_indicator"}
    unknown = requested - {"income", "cashflow", "balancesheet", "fina_indicator"}
    if unknown:
        raise ValueError(f"unknown Tushare financial interfaces: {', '.join(sorted(unknown))}")

    income = pd.DataFrame()
    cashflow = pd.DataFrame()
    balancesheet = pd.DataFrame()
    fina_indicator = pd.DataFrame()
    if "income" in requested:
        income = _call(
            "income",
            params=common_params,
            fields=["ts_code", "ann_date", "end_date", "revenue", "n_income_attr_p"],
            cfg=cfg,
        )
        time.sleep(max(0.0, cfg.request_delay))
    if "cashflow" in requested:
        cashflow = _call(
            "cashflow",
            params=common_params,
            fields=["ts_code", "ann_date", "end_date", "n_cashflow_act"],
            cfg=cfg,
        )
        time.sleep(max(0.0, cfg.request_delay))
    if "balancesheet" in requested:
        balancesheet = _call(
            "balancesheet",
            params=common_params,
            fields=["ts_code", "ann_date", "end_date", "total_assets", "total_liab", "total_hldr_eqy_exc_min_int"],
            cfg=cfg,
        )
        time.sleep(max(0.0, cfg.request_delay))
    if "fina_indicator" in requested:
        fina_indicator = _call(
            "fina_indicator",
            params=common_params,
            fields=["ts_code", "ann_date", "end_date", "roe", "tr_yoy", "netprofit_yoy", "debt_to_assets"],
            cfg=cfg,
        )
    return normalize_tushare_financial_factors(
        income=income,
        cashflow=cashflow,
        balancesheet=balancesheet,
        fina_indicator=fina_indicator,
    )


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
