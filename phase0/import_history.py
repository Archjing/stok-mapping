from __future__ import annotations

import io
import re
import os
import sqlite3
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from phase0.local_history import normalize_cn_symbol


@dataclass
class ImportResult:
    db_path: Path
    start_date: str
    qfq_files: int
    bfq_files: int
    qfq_rows: int
    bfq_rows: int
    symbols: int
    stock_meta_rows: int
    calendar_rows: int
    delisted_rows: int
    index_files: int
    index_rows: int
    index_meta_rows: int


@dataclass
class IndexImportResult:
    db_path: Path
    start_date: str
    index_files: int
    index_rows: int
    index_meta_rows: int


def _read_csv_from_zip(zf: zipfile.ZipFile, name: str) -> pd.DataFrame:
    raw = zf.read(name)
    return pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig")


def _parse_date_series(series: pd.Series) -> pd.Series:
    raw = series.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    raw = raw.replace({"nan": "", "NaN": "", "None": "", "NaT": ""})
    digits = raw.str.fullmatch(r"\d{8}", na=False)
    out = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    if digits.any():
        out.loc[digits] = pd.to_datetime(raw.loc[digits], format="%Y%m%d", errors="coerce")
    if (~digits).any():
        out.loc[~digits] = pd.to_datetime(raw.loc[~digits], errors="coerce")
    return out.dt.strftime("%Y-%m-%d").fillna("")


def _normalize_daily_frame(
    df: pd.DataFrame,
    adjust_type: str,
    start_date: str,
    fallback_symbol: str = "",
) -> pd.DataFrame:
    rename = {
        "日期": "date",
        "股票代码": "raw_symbol",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
        "振幅": "amplitude",
        "涨跌幅": "change_pct",
        "涨跌额": "change_amount",
        "换手率": "turnover_rate",
    }
    out = df.rename(columns=rename)
    needed = ["date", "raw_symbol", "open", "close", "high", "low", "volume", "amount"]
    missing = [col for col in needed if col not in out.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")
    out["date"] = _parse_date_series(out["date"])
    out = out[out["date"] >= start_date].copy()
    if out.empty:
        return out
    out["symbol"] = out["raw_symbol"].map(normalize_cn_symbol)
    if fallback_symbol:
        out.loc[out["symbol"] == "", "symbol"] = fallback_symbol
    out = out[out["symbol"] != ""]
    out["market"] = "CN"
    out["adjust_type"] = adjust_type
    for col in ["open", "high", "low", "close", "volume", "amount", "amplitude", "change_pct", "change_amount", "turnover_rate"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    out["adjusted_close"] = out["close"]
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
    return out[[col for col in keep if col in out.columns]].dropna(subset=["date", "symbol", "open", "close"])


def _infer_symbol_from_name(name: str) -> str:
    match = re.search(r"(\d{6})", Path(name).name)
    if not match:
        return ""
    return normalize_cn_symbol(match.group(1))


def _iter_daily_frames(zip_path: Path, adjust_type: str, start_date: str) -> Iterable[pd.DataFrame]:
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".csv"):
                continue
            try:
                df = _read_csv_from_zip(zf, name)
                frame = _normalize_daily_frame(df, adjust_type, start_date, _infer_symbol_from_name(name))
            except Exception:
                continue
            if frame.empty:
                continue
            yield frame


def _write_frames(conn: sqlite3.Connection, frames: Iterable[pd.DataFrame], table: str, chunk_size: int) -> tuple[int, int]:
    rows = 0
    files = 0
    buffer: list[pd.DataFrame] = []
    for frame in frames:
        files += 1
        rows += len(frame)
        buffer.append(frame)
        if sum(len(item) for item in buffer) >= chunk_size:
            pd.concat(buffer, ignore_index=True).to_sql(table, conn, if_exists="append", index=False)
            buffer = []
    if buffer:
        pd.concat(buffer, ignore_index=True).to_sql(table, conn, if_exists="append", index=False)
    return files, rows


def _create_index_tables(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS market_indices")
    conn.execute("DROP TABLE IF EXISTS market_index_bars")
    conn.execute(
        """
        CREATE TABLE market_indices (
            market TEXT,
            symbol TEXT,
            raw_symbol TEXT,
            name TEXT,
            exchange TEXT,
            publisher TEXT,
            category TEXT,
            base_date TEXT,
            base_point REAL,
            list_date TEXT,
            source TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE market_index_bars (
            market TEXT,
            symbol TEXT,
            date TEXT,
            frequency TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            amount REAL,
            advances REAL,
            declines REAL,
            name TEXT,
            source TEXT
        )
        """
    )


def _import_index_tables(
    conn: sqlite3.Connection,
    *,
    index_list_csv: Path | None,
    csi_index_list_csv: Path | None,
    index_daily_zip: Path | None,
    csi_index_daily_zip: Path | None,
    start_date: str,
    chunk_size: int,
) -> tuple[int, int, int]:
    _create_index_tables(conn)
    general_indices = _normalize_index_list(index_list_csv, source="index_list")
    csi_indices = _normalize_index_list(csi_index_list_csv, source="csi_index_list")
    index_sources = [frame for frame in [general_indices, csi_indices] if not frame.empty]
    index_meta = (
        pd.concat(index_sources, ignore_index=True).drop_duplicates("symbol")
        if index_sources
        else pd.DataFrame()
    )
    if not index_meta.empty:
        index_meta.to_sql("market_indices", conn, if_exists="append", index=False)
    general_lookup = _index_symbol_lookup(general_indices)
    csi_lookup = _index_symbol_lookup(csi_indices)

    def index_frame_iter() -> Iterable[pd.DataFrame]:
        yield from _iter_index_daily_frames(
            index_daily_zip,
            start_date=start_date,
            source="index_daily_kline",
            lookup=general_lookup,
        )
        yield from _iter_index_daily_frames(
            csi_index_daily_zip,
            start_date=start_date,
            source="csi_index_daily_kline",
            lookup=csi_lookup,
            fallback_market="CSI",
        )

    index_files, index_rows = _write_frames(conn, index_frame_iter(), "market_index_bars", chunk_size)
    conn.execute("CREATE INDEX idx_indices_symbol ON market_indices(symbol)")
    conn.execute("CREATE INDEX idx_index_bars_symbol_date ON market_index_bars(symbol, date, frequency)")
    index_meta_rows = int(pd.read_sql_query("SELECT COUNT(*) AS n FROM market_indices", conn)["n"].iloc[0])
    return index_files, index_rows, index_meta_rows


def _normalize_stock_list(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    code_col = "TS代码" if "TS代码" in df.columns else "股票代码"
    out = pd.DataFrame(
        {
            "market": "CN",
            "symbol": df[code_col].map(normalize_cn_symbol),
            "raw_symbol": df.get("TS代码", df.get("股票代码", "")),
            "name": df.get("股票名称", ""),
            "exchange": df.get("交易所代码", ""),
            "board": df.get("市场类型", ""),
            "sector": "",
            "industry": df.get("所属行业", ""),
            "area": df.get("地域", ""),
            "country": "CN",
            "currency": df.get("交易货币", "CNY"),
            "list_status": df.get("上市状态", ""),
            "list_date": _parse_date_series(df.get("上市日期", pd.Series(dtype=object))),
            "delist_date": _parse_date_series(df.get("退市日期", pd.Series(dtype=object))),
            "is_hs_connect": df.get("沪深港通标的", ""),
            "controller": df.get("实控人名称", ""),
            "controller_type": df.get("实控人企业性质", ""),
            "market_cap": None,
            "pe_ratio": None,
            "pb_ratio": None,
            "turnover_rate": None,
        }
    )
    out = out[out["symbol"] != ""].drop_duplicates("symbol")
    return out


def _normalize_trading_calendar(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    out = pd.DataFrame(
        {
            "exchange": df.get("交易所", ""),
            "date": _parse_date_series(df.get("日期", pd.Series(dtype=object))),
            "is_open": df.get("是否交易", "").astype(str).eq("交易").astype(int),
            "previous_trade_date": _parse_date_series(df.get("上一个交易日", pd.Series(dtype=object))),
        }
    )
    return out[out["date"] != ""].drop_duplicates(["exchange", "date"])


def _normalize_delisted_stocks(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    code_col = "TS代码" if "TS代码" in df.columns else "股票代码"
    out = pd.DataFrame(
        {
            "market": "CN",
            "symbol": df[code_col].map(normalize_cn_symbol),
            "raw_symbol": df.get("TS代码", df.get("股票代码", "")),
            "name": df.get("股票名称", ""),
            "industry": df.get("所属行业", ""),
            "exchange": df.get("交易所代码", ""),
            "board": df.get("市场类型", ""),
            "list_status": df.get("上市状态", ""),
            "list_date": _parse_date_series(df.get("上市日期", pd.Series(dtype=object))),
            "delist_date": _parse_date_series(df.get("退市日期", pd.Series(dtype=object))),
        }
    )
    return out[out["symbol"] != ""].drop_duplicates("symbol")


def _normalize_index_symbol(value: Any, fallback_market: str = "") -> str:
    raw = str(value).strip().upper()
    if not raw or raw == "NAN":
        return ""
    raw = raw.replace("_日", "").replace("_周", "").replace("_月", "")
    market = fallback_market.upper()
    match = re.search(r"(\d{6})\.(SH|SZ|CSI|SSE|SZSE)", raw)
    if match:
        market = match.group(2)
        if market == "SSE":
            market = "SH"
        elif market == "SZSE":
            market = "SZ"
        return f"{market}.{match.group(1)}"
    match_text = re.search(r"([A-Z0-9]{5,10})\.(CSI)", raw)
    if match_text:
        return f"{match_text.group(2)}.{match_text.group(1)}"
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 6:
        return f"{market}.{raw}" if market == "CSI" and re.fullmatch(r"[A-Z0-9]{5,10}", raw) else ""
    code = digits[-6:]
    if market in {"SSE", "SH"}:
        return f"SH.{code}"
    if market in {"SZSE", "SZ"}:
        return f"SZ.{code}"
    if market == "CSI":
        return f"CSI.{code}"
    if code.startswith(("0", "8", "9")):
        return f"SH.{code}"
    if code.startswith(("3", "4")):
        return f"SZ.{code}"
    return f"IDX.{code}"


def _normalize_index_list(csv_path: Path | None, *, source: str) -> pd.DataFrame:
    if csv_path is None or not csv_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    if "ts_code" in df.columns:
        code = df["ts_code"]
        market = df.get("market", "")
        name = df.get("name", "")
        publisher = df.get("publisher", "")
        category = df.get("category", "")
        base_date = df.get("base_date", pd.Series(dtype=object))
        base_point = df.get("base_point", "")
        list_date = df.get("list_date", pd.Series(dtype=object))
    else:
        code = df.get("指数代码", pd.Series(dtype=object))
        market = df.get("市场", "")
        name = df.get("指数简称", "")
        publisher = df.get("发布方", "")
        category = df.get("指数类别", "")
        base_date = df.get("基期", pd.Series(dtype=object))
        base_point = df.get("基点", "")
        list_date = df.get("发布日期", pd.Series(dtype=object))
    out = pd.DataFrame(
        {
            "market": "CN",
            "symbol": [
                _normalize_index_symbol(raw_code, str(raw_market))
                for raw_code, raw_market in zip(code, market if isinstance(market, pd.Series) else pd.Series([market] * len(df)))
            ],
            "raw_symbol": code,
            "name": name,
            "exchange": market,
            "publisher": publisher,
            "category": category,
            "base_date": _parse_date_series(base_date),
            "base_point": pd.to_numeric(base_point, errors="coerce"),
            "list_date": _parse_date_series(list_date),
            "source": source,
        }
    )
    return out[out["symbol"] != ""].drop_duplicates("symbol")


def _index_symbol_lookup(*frames: pd.DataFrame) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for frame in frames:
        if frame.empty:
            continue
        for _, row in frame.iterrows():
            raw = str(row.get("raw_symbol", "")).strip().upper()
            symbol = str(row.get("symbol", ""))
            digits = re.sub(r"\D", "", raw)
            if len(digits) >= 6 and symbol:
                lookup[digits[-6:]] = symbol
                lookup[raw] = symbol
    return lookup


def _infer_index_symbol_from_name(name: str, lookup: dict[str, str], fallback_market: str = "") -> str:
    stem = Path(name).stem.upper()
    if stem in lookup:
        return lookup[stem]
    match_full = re.search(r"(\d{6}\.(?:SH|SZ|CSI))", stem)
    if match_full:
        return _normalize_index_symbol(match_full.group(1), fallback_market)
    match = re.search(r"(\d{6})", stem)
    if match and match.group(1) in lookup:
        return lookup[match.group(1)]
    if match:
        return _normalize_index_symbol(match.group(1), fallback_market)
    return ""


def _normalize_index_daily_frame(
    df: pd.DataFrame,
    *,
    start_date: str,
    fallback_symbol: str,
    source: str,
) -> pd.DataFrame:
    rename = {
        "日期": "date",
        "代码": "raw_symbol",
        "名称": "name",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "开盘价": "open",
        "收盘价": "close",
        "最高价": "high",
        "最低价": "low",
        "成交量": "volume",
        "成交额": "amount",
        "上涨家数": "advances",
        "下跌家数": "declines",
    }
    out = df.rename(columns=rename)
    needed = ["date", "open", "close", "high", "low"]
    missing = [col for col in needed if col not in out.columns]
    if missing:
        raise ValueError(f"missing index columns: {missing}")
    out["date"] = _parse_date_series(out["date"])
    out = out[out["date"] >= start_date].copy()
    if out.empty:
        return out
    raw_symbol = out["raw_symbol"] if "raw_symbol" in out.columns else pd.Series("", index=out.index)
    out["symbol"] = raw_symbol.map(_normalize_index_symbol)
    if fallback_symbol:
        out.loc[out["symbol"] == "", "symbol"] = fallback_symbol
    out = out[out["symbol"] != ""]
    out["market"] = "CN"
    out["frequency"] = "daily"
    out["source"] = source
    if "name" not in out.columns:
        out["name"] = ""
    for col in ["open", "high", "low", "close", "volume", "amount", "advances", "declines"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    keep = [
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
    return out[[col for col in keep if col in out.columns]].dropna(subset=["date", "symbol", "open", "close"])


def _iter_index_daily_frames(
    zip_path: Path | None,
    *,
    start_date: str,
    source: str,
    lookup: dict[str, str],
    fallback_market: str = "",
) -> Iterable[pd.DataFrame]:
    if zip_path is None or not zip_path.exists():
        return
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".csv"):
                continue
            try:
                df = _read_csv_from_zip(zf, name)
                frame = _normalize_index_daily_frame(
                    df,
                    start_date=start_date,
                    fallback_symbol=_infer_index_symbol_from_name(name, lookup, fallback_market),
                    source=source,
                )
            except Exception:
                continue
            if not frame.empty:
                yield frame


def import_manual_history(
    *,
    qfq_zip: Path,
    bfq_zip: Path | None,
    stock_list_csv: Path | None,
    trading_calendar_csv: Path | None,
    delisted_stock_csv: Path | None,
    index_list_csv: Path | None,
    csi_index_list_csv: Path | None,
    index_daily_zip: Path | None,
    csi_index_daily_zip: Path | None,
    db_path: Path,
    years: int = 10,
    chunk_size: int = 250_000,
) -> ImportResult:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    start = date.today() - timedelta(days=365 * years + 30)
    start_date = start.isoformat()

    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE IF EXISTS market_daily_bars")
        conn.execute("DROP TABLE IF EXISTS market_stocks")
        conn.execute("DROP TABLE IF EXISTS trading_calendar")
        conn.execute("DROP TABLE IF EXISTS delisted_stocks")
        conn.execute(
            """
            CREATE TABLE market_daily_bars (
                market TEXT NOT NULL,
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                adjust_type TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                amount REAL,
                adjusted_close REAL,
                change_pct REAL,
                change_amount REAL,
                amplitude REAL,
                turnover_rate REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE market_stocks (
                market TEXT NOT NULL,
                symbol TEXT NOT NULL,
                raw_symbol TEXT,
                name TEXT,
                exchange TEXT,
                board TEXT,
                sector TEXT,
                industry TEXT,
                area TEXT,
                country TEXT,
                currency TEXT,
                list_status TEXT,
                list_date TEXT,
                delist_date TEXT,
                is_hs_connect TEXT,
                controller TEXT,
                controller_type TEXT,
                market_cap REAL,
                pe_ratio REAL,
                pb_ratio REAL,
                turnover_rate REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE trading_calendar (
                exchange TEXT,
                date TEXT,
                is_open INTEGER,
                previous_trade_date TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE delisted_stocks (
                market TEXT,
                symbol TEXT,
                raw_symbol TEXT,
                name TEXT,
                industry TEXT,
                exchange TEXT,
                board TEXT,
                list_status TEXT,
                list_date TEXT,
                delist_date TEXT
            )
            """
        )
        qfq_files, qfq_rows = _write_frames(conn, _iter_daily_frames(qfq_zip, "qfq", start_date), "market_daily_bars", chunk_size)
        bfq_files = 0
        bfq_rows = 0
        if bfq_zip is not None and bfq_zip.exists():
            bfq_files, bfq_rows = _write_frames(conn, _iter_daily_frames(bfq_zip, "bfq", start_date), "market_daily_bars", chunk_size)
        stock_meta = _normalize_stock_list(stock_list_csv) if stock_list_csv is not None else pd.DataFrame()
        delisted = _normalize_delisted_stocks(delisted_stock_csv) if delisted_stock_csv is not None else pd.DataFrame()
        if not stock_meta.empty:
            stock_meta.to_sql("market_stocks", conn, if_exists="append", index=False)
        else:
            conn.execute(
                """
                INSERT INTO market_stocks (
                    market, symbol, raw_symbol, name, exchange, board, sector, industry, area, country,
                    currency, list_status, list_date, delist_date, is_hs_connect, controller,
                    controller_type, market_cap, pe_ratio, pb_ratio, turnover_rate
                )
                SELECT 'CN', symbol, symbol, '', '', '', '', '', '', 'CN',
                       'CNY', '', '', '', '', '', '', NULL, NULL, NULL, AVG(turnover_rate)
                FROM market_daily_bars
                WHERE adjust_type = 'qfq'
                GROUP BY symbol
                """
            )
        if not delisted.empty:
            delisted.to_sql("delisted_stocks", conn, if_exists="append", index=False)
            delisted_symbols = set(delisted["symbol"])
            conn.executemany(
                "UPDATE market_stocks SET list_status = '退市' WHERE symbol = ?",
                [(symbol,) for symbol in delisted_symbols],
            )
        calendar = _normalize_trading_calendar(trading_calendar_csv) if trading_calendar_csv is not None else pd.DataFrame()
        if not calendar.empty:
            calendar.to_sql("trading_calendar", conn, if_exists="append", index=False)

        index_files, index_rows, index_meta_rows = _import_index_tables(
            conn,
            index_list_csv=index_list_csv,
            csi_index_list_csv=csi_index_list_csv,
            index_daily_zip=index_daily_zip,
            csi_index_daily_zip=csi_index_daily_zip,
            start_date=start_date,
            chunk_size=chunk_size,
        )

        conn.execute("CREATE INDEX idx_daily_symbol_date_adj ON market_daily_bars(symbol, date, adjust_type)")
        conn.execute("CREATE INDEX idx_daily_market_adj ON market_daily_bars(market, adjust_type)")
        conn.execute("CREATE INDEX idx_stocks_symbol ON market_stocks(symbol)")
        conn.execute("CREATE INDEX idx_calendar_exchange_date ON trading_calendar(exchange, date)")
        conn.execute("CREATE INDEX idx_delisted_symbol ON delisted_stocks(symbol)")
        symbols = int(pd.read_sql_query("SELECT COUNT(DISTINCT symbol) AS n FROM market_daily_bars WHERE adjust_type = 'qfq'", conn)["n"].iloc[0])
        stock_meta_rows = int(pd.read_sql_query("SELECT COUNT(*) AS n FROM market_stocks", conn)["n"].iloc[0])
        calendar_rows = int(pd.read_sql_query("SELECT COUNT(*) AS n FROM trading_calendar", conn)["n"].iloc[0])
        delisted_rows = int(pd.read_sql_query("SELECT COUNT(*) AS n FROM delisted_stocks", conn)["n"].iloc[0])
        conn.commit()

    return ImportResult(
        db_path=db_path,
        start_date=start_date,
        qfq_files=qfq_files,
        bfq_files=bfq_files,
        qfq_rows=qfq_rows,
        bfq_rows=bfq_rows,
        symbols=symbols,
        stock_meta_rows=stock_meta_rows,
        calendar_rows=calendar_rows,
        delisted_rows=delisted_rows,
        index_files=index_files,
        index_rows=index_rows,
        index_meta_rows=index_meta_rows,
    )


def _resolve_config_path(value: str | Path | None, *, root: Path) -> Path:
    if value is None or str(value).strip() == "":
        raise ValueError("manual_history_import path is not configured")
    expanded = os.path.expandvars(str(value))
    if "$" in expanded:
        raise ValueError(f"manual_history_import path contains unresolved environment variable: {value}")
    path = Path(expanded).expanduser()
    return path if path.is_absolute() else root / path


def import_from_config(cfg: dict[str, Any], root: Path) -> ImportResult:
    raw = cfg.get("manual_history_import", {})
    qfq_zip = _resolve_config_path(raw.get("qfq_zip"), root=root)
    bfq_zip = _resolve_config_path(raw.get("bfq_zip"), root=root)
    stock_list_csv = _resolve_config_path(raw.get("stock_list_csv"), root=root)
    trading_calendar_csv = _resolve_config_path(raw.get("trading_calendar_csv"), root=root)
    delisted_stock_csv = _resolve_config_path(raw.get("delisted_stock_csv"), root=root)
    index_list_csv = _resolve_config_path(raw.get("index_list_csv"), root=root)
    csi_index_list_csv = _resolve_config_path(raw.get("csi_index_list_csv"), root=root)
    index_daily_zip = _resolve_config_path(raw.get("index_daily_zip"), root=root)
    csi_index_daily_zip = _resolve_config_path(raw.get("csi_index_daily_zip"), root=root)
    local_history = cfg.get("local_history", {})
    db_path = Path(raw.get("output_db", local_history.get("path", "data/manual_history/a_share_history.sqlite")))
    if not db_path.is_absolute():
        db_path = root / db_path
    return import_manual_history(
        qfq_zip=qfq_zip,
        bfq_zip=bfq_zip,
        stock_list_csv=stock_list_csv,
        trading_calendar_csv=trading_calendar_csv,
        delisted_stock_csv=delisted_stock_csv,
        index_list_csv=index_list_csv,
        csi_index_list_csv=csi_index_list_csv,
        index_daily_zip=index_daily_zip,
        csi_index_daily_zip=csi_index_daily_zip,
        db_path=db_path,
        years=int(raw.get("years", 10)),
        chunk_size=int(raw.get("chunk_size", 250_000)),
    )


def import_index_history_from_config(cfg: dict[str, Any], root: Path) -> IndexImportResult:
    raw = cfg.get("manual_history_import", {})
    index_list_csv = _resolve_config_path(raw.get("index_list_csv"), root=root)
    csi_index_list_csv = _resolve_config_path(raw.get("csi_index_list_csv"), root=root)
    index_daily_zip = _resolve_config_path(raw.get("index_daily_zip"), root=root)
    csi_index_daily_zip = _resolve_config_path(raw.get("csi_index_daily_zip"), root=root)
    local_history = cfg.get("local_history", {})
    db_path = Path(raw.get("output_db", local_history.get("path", "data/manual_history/a_share_history.sqlite")))
    if not db_path.is_absolute():
        db_path = root / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    start = date.today() - timedelta(days=365 * int(raw.get("years", 10)) + 30)
    start_date = start.isoformat()
    with sqlite3.connect(db_path) as conn:
        index_files, index_rows, index_meta_rows = _import_index_tables(
            conn,
            index_list_csv=index_list_csv,
            csi_index_list_csv=csi_index_list_csv,
            index_daily_zip=index_daily_zip,
            csi_index_daily_zip=csi_index_daily_zip,
            start_date=start_date,
            chunk_size=int(raw.get("chunk_size", 250_000)),
        )
        conn.commit()
    return IndexImportResult(
        db_path=db_path,
        start_date=start_date,
        index_files=index_files,
        index_rows=index_rows,
        index_meta_rows=index_meta_rows,
    )
