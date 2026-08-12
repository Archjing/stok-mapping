from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from quant.data_governance.etf_store import (
    ensure_etf_schema,
    insert_backfill_tasks,
    insert_manifest_members,
    insert_tracking_observations,
    refresh_run_counts,
    upsert_etf_adj_factors,
    upsert_etf_catalog,
    upsert_etf_daily_bars,
)


def test_etf_schema_has_unique_raw_data_and_task_keys() -> None:
    with sqlite3.connect(":memory:") as conn:
        ensure_etf_schema(conn)
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {
            "etf_catalog_sync_runs", "market_etfs", "market_etf_tracking_mappings",
            "market_etf_daily_bars", "market_etf_adj_factors", "etf_backfill_runs",
            "etf_backfill_manifest_members", "etf_backfill_tasks",
        } <= tables
        conn.execute("INSERT INTO market_etf_daily_bars(symbol,date,open,high,low,close,source,fetched_at) VALUES ('SH.510300','2026-01-05',4,4.1,3.9,4.05,'test','2026-01-06T00:00:00')")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO market_etf_daily_bars(symbol,date,open,high,low,close,source,fetched_at) VALUES ('SH.510300','2026-01-05',4,4.1,3.9,4.05,'test','2026-01-06T00:00:00')")


def test_etf_schema_does_not_create_stock_tables() -> None:
    with sqlite3.connect(":memory:") as conn:
        ensure_etf_schema(conn)
        names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "market_stocks" not in names
    assert "market_daily_bars" not in names


def test_upserts_are_idempotent_and_update_payloads() -> None:
    catalog = pd.DataFrame([{
        "symbol": "SH.510300", "ts_code": "510300.SH", "name": "old", "short_name": "300ETF",
        "exchange": "SH", "list_status": "L", "setup_date": None, "list_date": "2012-05-28",
        "delist_date": None, "etf_type": "股票型", "management_name": None, "custodian_name": None,
        "management_fee": 0.5, "index_code_raw": "000300.SH", "tracking_index_symbol": "SH.000300",
        "tracking_index_name": "沪深300", "source": "test",
    }])
    daily = pd.DataFrame([{"symbol": "SH.510300", "date": "2026-01-05", "open": 4, "high": 4.1, "low": 3.9, "close": 4.0, "pre_close": 3.9, "change_amount": .1, "change_pct": 2, "volume": 100, "amount": 1000, "source": "test"}])
    factor = pd.DataFrame([{"symbol": "SH.510300", "date": "2026-01-05", "adj_factor": 1.0, "source": "test"}])
    with sqlite3.connect(":memory:") as conn:
        ensure_etf_schema(conn)
        assert upsert_etf_catalog(conn, catalog, snapshot_id="s1", fetched_at="t1") == 1
        catalog.loc[0, "name"] = "new"
        upsert_etf_catalog(conn, catalog, snapshot_id="s1", fetched_at="t2")
        insert_tracking_observations(conn, catalog, snapshot_id="s1", observed_at="t2")
        insert_tracking_observations(conn, catalog, snapshot_id="s1", observed_at="t2")
        upsert_etf_daily_bars(conn, daily, fetched_at="t1")
        daily.loc[0, "close"] = 4.05
        upsert_etf_daily_bars(conn, daily, fetched_at="t2")
        upsert_etf_adj_factors(conn, factor, fetched_at="t1")
        factor.loc[0, "adj_factor"] = 1.1
        upsert_etf_adj_factors(conn, factor, fetched_at="t2")
        assert conn.execute("SELECT name FROM market_etfs").fetchone()[0] == "new"
        assert conn.execute("SELECT COUNT(*) FROM market_etf_tracking_mappings").fetchone()[0] == 1
        assert conn.execute("SELECT close FROM market_etf_daily_bars").fetchone()[0] == 4.05
        assert conn.execute("SELECT adj_factor FROM market_etf_adj_factors").fetchone()[0] == 1.1


def test_manifest_tasks_and_run_counts() -> None:
    with sqlite3.connect(":memory:") as conn:
        ensure_etf_schema(conn)
        conn.execute("INSERT INTO etf_backfill_runs(run_id,universe_name,requested_sectors_json,requested_start,requested_end,config_digest,catalog_snapshot_id,status,created_at) VALUES ('r','u','[\"s\"]','2026-01-01','2026-01-05','d','snap','planned','now')")
        member = {"run_id": "r", "universe_name": "u", "catalog_snapshot_id": "snap", "sector": "s", "symbol": "SH.510300", "ts_code": "510300.SH", "requested_start": "2026-01-01", "requested_end": "2026-01-05", "effective_start": "2026-01-01", "effective_end": "2026-01-05", "expected_tracking_index": None, "resolved_tracking_index": None, "mapping_assertion_status": "not_configured"}
        task = {"run_id": "r", "sector": "s", "symbol": "SH.510300", "ts_code": "510300.SH", "dataset": "daily", "chunk_start": "2026-01-01", "chunk_end": "2026-01-05", "status": "succeeded", "updated_at": "now"}
        assert insert_manifest_members(conn, [member, member]) == 1
        assert insert_backfill_tasks(conn, [task, task]) == 1
        counts = refresh_run_counts(conn, "r")
        assert counts == {"target_tasks": 1, "succeeded_tasks": 1, "empty_tasks": 0, "failed_tasks": 0}
