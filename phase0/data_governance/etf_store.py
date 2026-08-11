from __future__ import annotations

import sqlite3
from typing import Iterable

import pandas as pd


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS etf_catalog_sync_runs (
 snapshot_id TEXT PRIMARY KEY, status TEXT NOT NULL CHECK(status IN ('running','ok','failed')),
 active_result TEXT NOT NULL, delisted_result TEXT NOT NULL, active_rows INTEGER NOT NULL DEFAULT 0,
 delisted_rows INTEGER NOT NULL DEFAULT 0, started_at TEXT NOT NULL, finished_at TEXT, last_error TEXT
);
CREATE TABLE IF NOT EXISTS market_etfs (
 catalog_snapshot_id TEXT NOT NULL, symbol TEXT NOT NULL, ts_code TEXT NOT NULL, name TEXT, short_name TEXT,
 exchange TEXT NOT NULL, list_status TEXT NOT NULL, setup_date TEXT, list_date TEXT NOT NULL, delist_date TEXT,
 etf_type TEXT, management_name TEXT, custodian_name TEXT, management_fee REAL, source TEXT NOT NULL,
 fetched_at TEXT NOT NULL, PRIMARY KEY(catalog_snapshot_id,symbol), UNIQUE(catalog_snapshot_id,ts_code)
);
CREATE TABLE IF NOT EXISTS market_etf_tracking_mappings (
 catalog_snapshot_id TEXT NOT NULL, symbol TEXT NOT NULL, index_code_raw TEXT, tracking_index_symbol TEXT,
 tracking_index_name TEXT, mapping_kind TEXT NOT NULL CHECK(mapping_kind IN ('provider_observation','config_override')),
 source TEXT NOT NULL, observed_at TEXT NOT NULL, effective_from TEXT, effective_to TEXT,
 is_point_in_time INTEGER NOT NULL CHECK(is_point_in_time IN (0,1)),
 PRIMARY KEY(catalog_snapshot_id,symbol,mapping_kind,observed_at)
);
CREATE TABLE IF NOT EXISTS market_etf_daily_bars (
 symbol TEXT NOT NULL, date TEXT NOT NULL, open REAL NOT NULL, high REAL NOT NULL, low REAL NOT NULL,
 close REAL NOT NULL, pre_close REAL, change_amount REAL, change_pct REAL, volume REAL, amount REAL,
 source TEXT NOT NULL, fetched_at TEXT NOT NULL, PRIMARY KEY(symbol,date)
);
CREATE TABLE IF NOT EXISTS market_etf_adj_factors (
 symbol TEXT NOT NULL, date TEXT NOT NULL, adj_factor REAL NOT NULL, source TEXT NOT NULL,
 fetched_at TEXT NOT NULL, PRIMARY KEY(symbol,date)
);
CREATE TABLE IF NOT EXISTS etf_backfill_runs (
 run_id TEXT PRIMARY KEY, universe_name TEXT NOT NULL, requested_sectors_json TEXT NOT NULL,
 requested_start TEXT NOT NULL, requested_end TEXT NOT NULL, config_digest TEXT NOT NULL,
 catalog_snapshot_id TEXT NOT NULL, manifest_source TEXT NOT NULL DEFAULT 'catalog', status TEXT NOT NULL CHECK(status IN ('planned','running','ok','partial','failed')),
 audit_status TEXT NOT NULL DEFAULT 'not_run' CHECK(audit_status IN ('not_run','pass','blocking','error')),
 target_tasks INTEGER NOT NULL DEFAULT 0, succeeded_tasks INTEGER NOT NULL DEFAULT 0,
 empty_tasks INTEGER NOT NULL DEFAULT 0, failed_tasks INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT, audited_at TEXT, last_error TEXT
);
CREATE TABLE IF NOT EXISTS etf_backfill_manifest_members (
 run_id TEXT NOT NULL, universe_name TEXT NOT NULL, catalog_snapshot_id TEXT NOT NULL, sector TEXT NOT NULL,
 symbol TEXT NOT NULL, ts_code TEXT NOT NULL, requested_start TEXT NOT NULL, requested_end TEXT NOT NULL,
 effective_start TEXT NOT NULL, effective_end TEXT NOT NULL, expected_tracking_index TEXT,
 resolved_tracking_index TEXT, mapping_assertion_status TEXT NOT NULL, PRIMARY KEY(run_id,sector,symbol)
);
CREATE TABLE IF NOT EXISTS etf_backfill_tasks (
 run_id TEXT NOT NULL, sector TEXT NOT NULL, symbol TEXT NOT NULL, ts_code TEXT NOT NULL,
 dataset TEXT NOT NULL CHECK(dataset IN ('daily','adj_factor')), chunk_start TEXT NOT NULL, chunk_end TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','running','succeeded','empty','failed')),
 attempt_count INTEGER NOT NULL DEFAULT 0, fetched_rows INTEGER NOT NULL DEFAULT 0,
 inserted_rows INTEGER NOT NULL DEFAULT 0, last_error TEXT, started_at TEXT, updated_at TEXT NOT NULL,
 finished_at TEXT, PRIMARY KEY(run_id,sector,symbol,dataset,chunk_start,chunk_end)
);
CREATE INDEX IF NOT EXISTS idx_etf_catalog_status ON etf_catalog_sync_runs(status,finished_at);
CREATE INDEX IF NOT EXISTS idx_market_etfs_snapshot_status ON market_etfs(catalog_snapshot_id,list_status);
CREATE INDEX IF NOT EXISTS idx_etf_daily_date ON market_etf_daily_bars(date);
CREATE INDEX IF NOT EXISTS idx_etf_factor_date ON market_etf_adj_factors(date);
CREATE INDEX IF NOT EXISTS idx_etf_tasks_run_status ON etf_backfill_tasks(run_id,status);
CREATE INDEX IF NOT EXISTS idx_etf_manifest_run_sector ON etf_backfill_manifest_members(run_id,sector);
"""


def ensure_etf_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(etf_backfill_runs)")}
    if "manifest_source" not in columns:
        conn.execute("ALTER TABLE etf_backfill_runs ADD COLUMN manifest_source TEXT NOT NULL DEFAULT 'catalog'")


def _value(value: object) -> object:
    return None if value is None or (not isinstance(value, (list, dict, tuple)) and pd.isna(value)) else value


def _records(frame: pd.DataFrame, key: tuple[str, ...]) -> list[dict[str, object]]:
    logical: dict[tuple[object, ...], dict[str, object]] = {}
    for row in frame.to_dict("records"):
        clean = {name: _value(value) for name, value in row.items()}
        logical[tuple(clean.get(name) for name in key)] = clean
    return list(logical.values())


def upsert_etf_catalog(conn: sqlite3.Connection, frame: pd.DataFrame, *, snapshot_id: str, fetched_at: str) -> int:
    rows = _records(frame, ("symbol",))
    sql = """INSERT INTO market_etfs(catalog_snapshot_id,symbol,ts_code,name,short_name,exchange,list_status,setup_date,list_date,delist_date,etf_type,management_name,custodian_name,management_fee,source,fetched_at)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(catalog_snapshot_id,symbol) DO UPDATE SET
    ts_code=excluded.ts_code,name=excluded.name,short_name=excluded.short_name,exchange=excluded.exchange,
    list_status=excluded.list_status,setup_date=excluded.setup_date,list_date=excluded.list_date,
    delist_date=excluded.delist_date,etf_type=excluded.etf_type,management_name=excluded.management_name,
    custodian_name=excluded.custodian_name,management_fee=excluded.management_fee,source=excluded.source,fetched_at=excluded.fetched_at"""
    conn.executemany(sql, [(snapshot_id, r.get("symbol"), r.get("ts_code"), r.get("name"), r.get("short_name"), r.get("exchange"), r.get("list_status"), r.get("setup_date"), r.get("list_date"), r.get("delist_date"), r.get("etf_type"), r.get("management_name"), r.get("custodian_name"), r.get("management_fee"), r.get("source"), fetched_at) for r in rows])
    return len(rows)


def insert_tracking_observations(conn: sqlite3.Connection, frame: pd.DataFrame, *, snapshot_id: str, observed_at: str) -> int:
    rows = _records(frame, ("symbol",))
    sql = """INSERT INTO market_etf_tracking_mappings(catalog_snapshot_id,symbol,index_code_raw,tracking_index_symbol,tracking_index_name,mapping_kind,source,observed_at,effective_from,effective_to,is_point_in_time)
    VALUES(?,?,?,?,?,'provider_observation',?,?,NULL,NULL,0)
    ON CONFLICT(catalog_snapshot_id,symbol,mapping_kind,observed_at) DO UPDATE SET index_code_raw=excluded.index_code_raw,tracking_index_symbol=excluded.tracking_index_symbol,tracking_index_name=excluded.tracking_index_name,source=excluded.source"""
    conn.executemany(sql, [(snapshot_id, r.get("symbol"), r.get("index_code_raw"), r.get("tracking_index_symbol") or None, r.get("tracking_index_name"), r.get("source"), observed_at) for r in rows])
    return len(rows)


def upsert_etf_daily_bars(conn: sqlite3.Connection, frame: pd.DataFrame, *, fetched_at: str) -> int:
    rows = _records(frame, ("symbol", "date"))
    sql = """INSERT INTO market_etf_daily_bars(symbol,date,open,high,low,close,pre_close,change_amount,change_pct,volume,amount,source,fetched_at)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(symbol,date) DO UPDATE SET open=excluded.open,high=excluded.high,low=excluded.low,close=excluded.close,pre_close=excluded.pre_close,change_amount=excluded.change_amount,change_pct=excluded.change_pct,volume=excluded.volume,amount=excluded.amount,source=excluded.source,fetched_at=excluded.fetched_at"""
    conn.executemany(sql, [(r.get("symbol"), r.get("date"), r.get("open"), r.get("high"), r.get("low"), r.get("close"), r.get("pre_close"), r.get("change_amount"), r.get("change_pct"), r.get("volume"), r.get("amount"), r.get("source"), fetched_at) for r in rows])
    return len(rows)


def upsert_etf_adj_factors(conn: sqlite3.Connection, frame: pd.DataFrame, *, fetched_at: str) -> int:
    rows = _records(frame, ("symbol", "date"))
    sql = """INSERT INTO market_etf_adj_factors(symbol,date,adj_factor,source,fetched_at) VALUES(?,?,?,?,?)
    ON CONFLICT(symbol,date) DO UPDATE SET adj_factor=excluded.adj_factor,source=excluded.source,fetched_at=excluded.fetched_at"""
    conn.executemany(sql, [(r.get("symbol"), r.get("date"), r.get("adj_factor"), r.get("source"), fetched_at) for r in rows])
    return len(rows)


def _dedupe_dict_rows(rows: Iterable[dict[str, object]], key: tuple[str, ...]) -> list[dict[str, object]]:
    unique: dict[tuple[object, ...], dict[str, object]] = {}
    for row in rows:
        unique[tuple(row.get(name) for name in key)] = row
    return list(unique.values())


def insert_manifest_members(conn: sqlite3.Connection, rows: list[dict[str, object]]) -> int:
    rows = _dedupe_dict_rows(rows, ("run_id", "sector", "symbol"))
    cols = ("run_id", "universe_name", "catalog_snapshot_id", "sector", "symbol", "ts_code", "requested_start", "requested_end", "effective_start", "effective_end", "expected_tracking_index", "resolved_tracking_index", "mapping_assertion_status")
    conn.executemany(f"INSERT INTO etf_backfill_manifest_members({','.join(cols)}) VALUES({','.join('?' for _ in cols)})", [tuple(row.get(col) for col in cols) for row in rows])
    return len(rows)


def insert_backfill_tasks(conn: sqlite3.Connection, rows: list[dict[str, object]]) -> int:
    rows = _dedupe_dict_rows(rows, ("run_id", "sector", "symbol", "dataset", "chunk_start", "chunk_end"))
    cols = ("run_id", "sector", "symbol", "ts_code", "dataset", "chunk_start", "chunk_end", "status", "attempt_count", "fetched_rows", "inserted_rows", "last_error", "started_at", "updated_at", "finished_at")
    conn.executemany(f"INSERT INTO etf_backfill_tasks({','.join(cols)}) VALUES({','.join('?' for _ in cols)})", [tuple(row.get(col, 0 if col in {"attempt_count", "fetched_rows", "inserted_rows"} else None) for col in cols) for row in rows])
    return len(rows)


def refresh_run_counts(conn: sqlite3.Connection, run_id: str) -> dict[str, int]:
    grouped = dict(conn.execute("SELECT status,COUNT(*) FROM etf_backfill_tasks WHERE run_id=? GROUP BY status", (run_id,)).fetchall())
    counts = {
        "target_tasks": sum(grouped.values()),
        "succeeded_tasks": grouped.get("succeeded", 0),
        "empty_tasks": grouped.get("empty", 0),
        "failed_tasks": grouped.get("failed", 0),
    }
    conn.execute("UPDATE etf_backfill_runs SET target_tasks=?,succeeded_tasks=?,empty_tasks=?,failed_tasks=? WHERE run_id=?", (*counts.values(), run_id))
    return counts
