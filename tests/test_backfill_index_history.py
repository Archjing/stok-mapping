from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest

from phase0.data_access import local_history
from phase0.data_governance.backfills import index_history


@pytest.fixture(autouse=True)
def restore_local_history_configuration() -> Iterator[None]:
    original_config = vars(local_history._settings).copy()
    try:
        yield
    finally:
        local_history.configure_local_history(original_config)


def test_index_ts_code_mapping() -> None:
    assert index_history.index_ts_code("SH.000001") == "000001.SH"
    assert index_history.index_ts_code("SZ.399001") == "399001.SZ"
    assert index_history.index_ts_code("CSI.000300") == "000300.SH"
    assert index_history.index_ts_code("CSI.399707") == "399707.SZ"


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "history.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE market_index_bars (
                market TEXT, symbol TEXT, date TEXT, frequency TEXT,
                open REAL, high REAL, low REAL, close REAL,
                volume REAL, amount REAL, advances REAL, declines REAL,
                name TEXT, source TEXT
            )
            """
        )
        # Pre-existing stale window for one index, to be replaced by backfill.
        conn.execute(
            "INSERT INTO market_index_bars VALUES ('CN','SH.000001','2016-05-03','daily',1,2,0.5,1.5,1,1,1,1,'上证指数','index_daily_kline')",
        )
        # Second index Tushare does not carry; must land in missing_symbols.
        conn.execute(
            "INSERT INTO market_index_bars VALUES ('CN','CSI.930050','2016-05-03','daily',1,2,0.5,1.5,1,1,1,1,'中证全指','index_daily_kline')",
        )
        conn.execute(
            """
            CREATE TABLE market_indices (
                market TEXT, symbol TEXT, raw_symbol TEXT, name TEXT,
                exchange TEXT, publisher TEXT, category TEXT,
                base_date TEXT, base_point REAL, list_date TEXT, source TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO market_indices VALUES ('CN','SH.000001','000001','上证指数','SSE','上交所','',NULL,NULL,NULL,'')",
        )
        conn.execute(
            "INSERT INTO market_indices VALUES ('CN','CSI.930050','930050','中证全指','SSE','中证','',NULL,NULL,NULL,'')",
        )
    return db_path


def _write_config(tmp_path: Path, db_path: Path) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
phase0:
  local_history:
    path: "{db_path}"
  data_sources:
    tushare:
      enabled: true
      token_env: "TUSHARE_TOKEN"
"""
    )
    return config_path


def test_backfill_index_history_fetches_and_replaces_window(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = _make_db(tmp_path)
    config_path = _write_config(tmp_path, db_path)
    monkeypatch.setenv("TUSHARE_TOKEN", "fake-token")

    def fake_fetch(local_symbol, *, ts_code, start_date, end_date, cfg, name=""):
        assert start_date == "2016-01-01"
        assert end_date == "2016-01-31"
        if local_symbol == "CSI.930050":
            return pd.DataFrame(
                columns=[
                    "market", "symbol", "date", "frequency", "open", "high", "low", "close",
                    "volume", "amount", "advances", "declines", "name", "source",
                ]
            )
        return pd.DataFrame(
            [
                {
                    "market": "CN",
                    "symbol": local_symbol,
                    "date": "2016-01-04",
                    "frequency": "daily",
                    "open": 3000.0,
                    "high": 3100.0,
                    "low": 2990.0,
                    "close": 3050.0,
                    "volume": 1e7,
                    "amount": 2e11,
                    "advances": None,
                    "declines": None,
                    "name": name,
                    "source": "tushare.index_daily",
                }
            ]
        )

    monkeypatch.setattr(index_history, "fetch_tushare_index_daily", fake_fetch)
    result = index_history.backfill_index_history_from_config(
        config_path, start_date="2016-01-01", end_date="2016-01-31"
    )

    assert result.status == "ok"
    assert result.target_symbols == 2
    assert result.fetched_symbols == 1
    assert result.empty_symbols == 1
    assert result.missing_symbols == ["CSI.930050"]
    assert result.inserted_rows == 1

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT symbol, date, close, name, source FROM market_index_bars ORDER BY symbol, date"
        ).fetchall()
        # The stale 2016-05-03 row for SH.000001 sits outside the backfill window and is
        # preserved; the window row 2016-01-04 was fetched and inserted. CSI.930050 has no
        # Tushare data so its existing row is left untouched.
        assert rows == [
            ("CSI.930050", "2016-05-03", 1.5, "中证全指", "index_daily_kline"),
            ("SH.000001", "2016-01-04", 3050.0, "上证指数", "tushare.index_daily"),
            ("SH.000001", "2016-05-03", 1.5, "上证指数", "index_daily_kline"),
        ]


def test_backfill_index_history_requires_token(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = _make_db(tmp_path)
    config_path = _write_config(tmp_path, db_path)
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    result = index_history.backfill_index_history_from_config(
        config_path, start_date="2016-01-01", end_date="2016-01-31"
    )
    assert result.status == "missing_tushare_token"
    assert result.fetched_symbols == 0
