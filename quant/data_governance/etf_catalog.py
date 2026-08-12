from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import requests

from quant.config import load_config
from quant.data_access.providers.tushare import (
    TushareAPIError,
    TushareConfig,
    TusharePermissionError,
    TushareTokenError,
    fetch_tushare_etf_basic,
    tushare_config,
)
from quant.data_governance.etf_store import (
    ensure_etf_schema,
    insert_tracking_observations,
    upsert_etf_catalog,
)


@dataclass(frozen=True)
class ETFCatalogSyncResult:
    status: str
    snapshot_id: str
    active_rows: int
    delisted_rows: int
    error_kind: str | None
    error_message: str | None


class StaleETFCatalogError(RuntimeError):
    """No completed catalog snapshot satisfies the configured freshness bound."""


def _mapping(value: object, *, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} configuration must be a mapping")
    return value


def _iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat()


def _error_kind(exc: Exception) -> str:
    if isinstance(exc, TusharePermissionError):
        return "permission_denied"
    if isinstance(exc, TushareTokenError):
        return "token_error"
    if isinstance(exc, TushareAPIError):
        return "api_error"
    if isinstance(exc, requests.RequestException):
        return "network_error"
    if isinstance(exc, (KeyError, ValueError, TypeError)):
        return "data_validation"
    return "unexpected_error"


def sync_etf_catalog(
    db_path: Path,
    *,
    provider_cfg: TushareConfig,
    now: datetime | None = None,
) -> ETFCatalogSyncResult:
    started = now or datetime.now()
    snapshot_id = uuid.uuid4().hex
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        ensure_etf_schema(conn)
        conn.execute(
            "INSERT INTO etf_catalog_sync_runs(snapshot_id,status,active_result,delisted_result,started_at) VALUES (?,'running','not_run','not_run',?)",
            (snapshot_id, _iso(started)),
        )
        conn.commit()
    try:
        active = fetch_tushare_etf_basic(list_status="L", cfg=provider_cfg)
        delisted = fetch_tushare_etf_basic(list_status="D", cfg=provider_cfg)
        finished = now or datetime.now()
        active_result = "empty" if active.empty else "ok"
        delisted_result = "empty" if delisted.empty else "ok"
        with sqlite3.connect(db_path) as conn:
            ensure_etf_schema(conn)
            with conn:
                active_rows = upsert_etf_catalog(conn, active, snapshot_id=snapshot_id, fetched_at=_iso(finished))
                delisted_rows = upsert_etf_catalog(conn, delisted, snapshot_id=snapshot_id, fetched_at=_iso(finished))
                insert_tracking_observations(conn, active, snapshot_id=snapshot_id, observed_at=_iso(finished))
                insert_tracking_observations(conn, delisted, snapshot_id=snapshot_id, observed_at=_iso(finished))
                conn.execute(
                    "UPDATE etf_catalog_sync_runs SET status='ok',active_result=?,delisted_result=?,active_rows=?,delisted_rows=?,finished_at=?,last_error=NULL WHERE snapshot_id=?",
                    (active_result, delisted_result, active_rows, delisted_rows, _iso(finished), snapshot_id),
                )
        return ETFCatalogSyncResult("ok", snapshot_id, active_rows, delisted_rows, None, None)
    except Exception as exc:
        message = str(exc)[:1000]
        with sqlite3.connect(db_path) as conn:
            ensure_etf_schema(conn)
            with conn:
                conn.execute("DELETE FROM market_etf_tracking_mappings WHERE catalog_snapshot_id=?", (snapshot_id,))
                conn.execute("DELETE FROM market_etfs WHERE catalog_snapshot_id=?", (snapshot_id,))
                conn.execute(
                    "UPDATE etf_catalog_sync_runs SET status='failed',finished_at=?,last_error=? WHERE snapshot_id=?",
                    (_iso(now or datetime.now()), message, snapshot_id),
                )
        return ETFCatalogSyncResult("failed", snapshot_id, 0, 0, _error_kind(exc), message)


def sync_etf_catalog_from_config(config_path: Path) -> ETFCatalogSyncResult:
    """Resolve the dedicated ETF store and Tushare settings from config."""
    config_path = Path(config_path).resolve()
    quant_cfg = load_config(config_path)
    history_cfg = _mapping(quant_cfg.get("etf_history"), name="quant.etf_history")
    data_sources_cfg = _mapping(quant_cfg.get("data_sources", {}), name="quant.data_sources")
    provider_raw = _mapping(data_sources_cfg.get("tushare", {}), name="quant.data_sources.tushare")
    db_path = Path(str(history_cfg.get("path", "data/etf_history.sqlite")))
    if not db_path.is_absolute():
        db_path = config_path.parent / db_path
    return sync_etf_catalog(db_path, provider_cfg=tushare_config(provider_raw))


def latest_completed_catalog_snapshot(
    conn: sqlite3.Connection,
    *,
    max_age_days: int,
    now: datetime | None = None,
) -> str:
    if max_age_days < 0:
        raise ValueError("max_age_days must be non-negative")
    row = conn.execute(
        "SELECT snapshot_id,finished_at FROM etf_catalog_sync_runs WHERE status='ok' AND finished_at IS NOT NULL ORDER BY finished_at DESC LIMIT 1"
    ).fetchone()
    if row is None:
        raise StaleETFCatalogError("no completed ETF catalog snapshot")
    finished = datetime.fromisoformat(row[1])
    current = now or datetime.now()
    if current - finished > timedelta(days=max_age_days):
        raise StaleETFCatalogError(f"latest ETF catalog snapshot is older than {max_age_days} days")
    return str(row[0])
