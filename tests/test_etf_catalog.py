from __future__ import annotations

import sqlite3
from datetime import datetime

import pandas as pd
import pytest

from quant.data_access.providers.tushare import ETF_CATALOG_COLUMNS, TushareConfig, TusharePermissionError
from quant.data_governance import etf_catalog as catalog
from quant.data_governance.etf_catalog import StaleETFCatalogError
from quant.data_governance.etf_store import ensure_etf_schema


def _catalog_frame(ts_code: str, list_status: str) -> pd.DataFrame:
    suffix = ts_code.split(".")[1]
    code = ts_code.split(".")[0]
    return pd.DataFrame([{
        "symbol": f"{suffix}.{code}", "ts_code": ts_code, "name": "ETF", "short_name": "ETF",
        "exchange": suffix, "list_status": list_status, "setup_date": "2012-05-04",
        "list_date": "2012-05-28", "delist_date": "2020-12-31" if list_status == "D" else None,
        "etf_type": "股票型", "management_name": "m", "custodian_name": "c", "management_fee": .5,
        "index_code_raw": "000300.SH", "tracking_index_symbol": "SH.000300",
        "tracking_index_name": "沪深300", "source": "tushare.etf_basic",
    }], columns=ETF_CATALOG_COLUMNS)


def test_catalog_snapshot_is_published_only_after_active_and_delisted_calls_succeed(tmp_path, monkeypatch):
    frames = {"L": _catalog_frame("510300.SH", "L"), "D": _catalog_frame("510050.SH", "D")}
    monkeypatch.setattr(catalog, "fetch_tushare_etf_basic", lambda *, list_status, cfg: frames[list_status])
    result = catalog.sync_etf_catalog(tmp_path / "etf.sqlite", provider_cfg=TushareConfig(enabled=True))
    assert result.status == "ok"
    with sqlite3.connect(tmp_path / "etf.sqlite") as conn:
        rows = conn.execute("SELECT symbol,catalog_snapshot_id FROM market_etfs ORDER BY symbol").fetchall()
    assert rows == [("SH.510050", result.snapshot_id), ("SH.510300", result.snapshot_id)]


def test_permission_denied_does_not_publish_partial_snapshot(tmp_path, monkeypatch):
    def fake_fetch(*, list_status, cfg):
        if list_status == "D":
            raise TusharePermissionError("etf_basic", 40203, "permission denied")
        return _catalog_frame("510300.SH", "L")
    monkeypatch.setattr(catalog, "fetch_tushare_etf_basic", fake_fetch)
    result = catalog.sync_etf_catalog(tmp_path / "etf.sqlite", provider_cfg=TushareConfig(enabled=True))
    assert result.status == "failed"
    assert result.error_kind == "permission_denied"
    with sqlite3.connect(tmp_path / "etf.sqlite") as conn:
        assert conn.execute("SELECT COUNT(*) FROM market_etfs WHERE catalog_snapshot_id=?", (result.snapshot_id,)).fetchone()[0] == 0


def test_successful_empty_response_is_distinct_from_permission_failure(tmp_path, monkeypatch):
    frames = {"L": _catalog_frame("510300.SH", "L"), "D": pd.DataFrame(columns=ETF_CATALOG_COLUMNS)}
    monkeypatch.setattr(catalog, "fetch_tushare_etf_basic", lambda *, list_status, cfg: frames[list_status])
    result = catalog.sync_etf_catalog(tmp_path / "etf.sqlite", provider_cfg=TushareConfig(enabled=True))
    assert result.status == "ok"
    with sqlite3.connect(tmp_path / "etf.sqlite") as conn:
        assert conn.execute("SELECT delisted_result FROM etf_catalog_sync_runs WHERE snapshot_id=?", (result.snapshot_id,)).fetchone()[0] == "empty"


def test_latest_catalog_rejects_stale_snapshot():
    with sqlite3.connect(":memory:") as conn:
        ensure_etf_schema(conn)
        conn.execute("INSERT INTO etf_catalog_sync_runs VALUES (?,?,?,?,?,?,?,?,?)", ("old", "ok", "ok", "ok", 1, 1, "2026-08-01T00:00:00", "2026-08-01T00:01:00", None))
        with pytest.raises(StaleETFCatalogError):
            catalog.latest_completed_catalog_snapshot(conn, max_age_days=7, now=datetime(2026, 8, 11))


def test_sync_from_config_resolves_dedicated_store_and_provider_settings(tmp_path, monkeypatch):
    captured: dict[str, object] = {}
    expected = object()
    monkeypatch.setattr(
        catalog,
        "load_config",
        lambda path: {
            "etf_history": {"path": "data/etf.sqlite"},
            "data_sources": {"tushare": {"enabled": True, "token_env": "ETF_TEST_TOKEN"}},
        },
    )

    def fake_sync(db_path, *, provider_cfg):
        captured.update(db_path=db_path, provider_cfg=provider_cfg)
        return expected

    monkeypatch.setattr(catalog, "sync_etf_catalog", fake_sync)
    config_path = tmp_path / "project" / "config.yaml"
    result = catalog.sync_etf_catalog_from_config(config_path)

    assert result is expected
    assert captured["db_path"] == config_path.parent / "data/etf.sqlite"
    assert captured["provider_cfg"].enabled is True
    assert captured["provider_cfg"].token_env == "ETF_TEST_TOKEN"
