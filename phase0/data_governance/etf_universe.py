from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from phase0.config import load_config
from phase0.data_access.symbols import from_tushare_symbol, normalize_etf_symbol, to_tushare_symbol
from phase0.data_governance.etf_catalog import latest_completed_catalog_snapshot
from phase0.data_governance.etf_store import ensure_etf_schema


@dataclass(frozen=True)
class ETFManifestMember:
    universe_name: str
    sector: str
    symbol: str
    ts_code: str
    requested_start: date
    requested_end: date
    effective_start: date
    effective_end: date
    expected_tracking_index: str | None
    resolved_tracking_index: str | None
    mapping_assertion_status: str


@dataclass(frozen=True)
class ETFUniverseManifest:
    universe_name: str
    requested_sectors: tuple[str, ...]
    requested_start: date
    requested_end: date
    config_digest: str
    catalog_snapshot_id: str
    members: tuple[ETFManifestMember, ...]
    manifest_source: str = "catalog"


class ETFUniverseError(RuntimeError):
    """The requested ETF acquisition universe is invalid or non-reproducible."""


def _history_cfg(phase0_cfg: dict[str, object]) -> dict[str, object]:
    value = phase0_cfg.get("etf_history")
    if not isinstance(value, dict):
        raise ETFUniverseError("phase0.etf_history configuration is required")
    return value


def _universe_cfg(phase0_cfg: dict[str, object], universe_name: str) -> dict[str, object]:
    history = _history_cfg(phase0_cfg)
    universes = history.get("universes")
    if not isinstance(universes, dict) or universe_name not in universes or not isinstance(universes[universe_name], dict):
        raise ETFUniverseError(f"unknown ETF universe: {universe_name}")
    return universes[universe_name]


def history_config_digest(
    phase0_cfg: dict[str, object],
    universe_name: str,
    requested_sectors: list[str] | tuple[str, ...] | None = None,
) -> str:
    history = _history_cfg(phase0_cfg)
    universe = _universe_cfg(phase0_cfg, universe_name)
    settings = {key: value for key, value in history.items() if key not in {"path", "report_dir", "universes", "enabled"}}
    payload = {"universe_name": universe_name, "universe": universe, "settings": settings, "requested_sectors": sorted(requested_sectors) if requested_sectors is not None else None}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _tracking_symbol(value: object) -> str | None:
    raw = str(value or "").strip().upper()
    if not raw:
        return None
    if re.fullmatch(r"[A-Z]+\.\d{6}", raw):
        return raw
    converted = from_tushare_symbol(raw)
    if converted:
        return converted
    raise ETFUniverseError(f"invalid tracking index symbol: {value}")


def resolve_etf_universe(
    conn: sqlite3.Connection,
    *,
    phase0_cfg: dict[str, object],
    universe_name: str,
    requested_sectors: list[str] | None,
    start_date: date,
    end_date: date,
    now: datetime | None = None,
) -> ETFUniverseManifest:
    if start_date > end_date:
        raise ETFUniverseError("start_date must be on or before end_date")
    history = _history_cfg(phase0_cfg)
    universe = _universe_cfg(phase0_cfg, universe_name)
    if not set(universe).issubset({"sectors", "manifest_source"}):
        raise ETFUniverseError("ETF universe keys must be sectors and optional manifest_source")
    manifest_source = str(universe.get("manifest_source", "catalog"))
    if manifest_source not in {"catalog", "manual_config"}:
        raise ETFUniverseError("ETF manifest_source must be catalog or manual_config")
    if universe_name == "single_etf" and manifest_source != "manual_config":
        raise ETFUniverseError("single_etf must use manifest_source manual_config")
    sectors_value = universe.get("sectors")
    if not isinstance(sectors_value, dict) or not sectors_value:
        raise ETFUniverseError("ETF universe sectors must be a non-empty mapping")
    all_sector_names = sorted(str(name) for name in sectors_value)
    if requested_sectors is None:
        selected = all_sector_names
    else:
        selected = [str(name) for name in requested_sectors]
        if len(selected) != len(set(selected)):
            raise ETFUniverseError("repeated sector selector")
        unknown = sorted(set(selected) - set(all_sector_names))
        if unknown:
            raise ETFUniverseError(f"unknown sector selector: {','.join(unknown)}")
        selected = sorted(selected)

    seen: dict[str, str] = {}
    parsed: dict[str, list[dict[str, object]]] = {}
    for sector in all_sector_names:
        entries = sectors_value.get(sector)
        if not isinstance(entries, list):
            raise ETFUniverseError(f"sector {sector} must be a list")
        parsed[sector] = []
        for entry in entries:
            allowed_keys = (
                {"symbol", "expected_tracking_index"}
                if manifest_source == "catalog"
                else {"symbol", "ts_code", "listed_from"}
            )
            if not isinstance(entry, dict) or not set(entry).issubset(allowed_keys) or "symbol" not in entry:
                if manifest_source == "catalog":
                    raise ETFUniverseError("ETF selector keys must be symbol and optional expected_tracking_index")
                raise ETFUniverseError("manual ETF selector keys must be symbol, ts_code, and listed_from")
            try:
                symbol = normalize_etf_symbol(entry["symbol"])
            except ValueError as exc:
                raise ETFUniverseError(str(exc)) from exc
            if symbol in seen:
                raise ETFUniverseError(f"ETF symbol {symbol} appears in multiple sectors: {seen[symbol]},{sector}")
            seen[symbol] = sector
            if manifest_source == "catalog":
                parsed[sector].append({"symbol": symbol, "expected": _tracking_symbol(entry.get("expected_tracking_index"))})
            else:
                ts_code = str(entry.get("ts_code") or "").strip().upper()
                if to_tushare_symbol(symbol) != ts_code:
                    raise ETFUniverseError(f"manual ETF symbol exchange mismatch: {symbol} versus {ts_code or '<missing>'}")
                try:
                    listed_from = date.fromisoformat(str(entry.get("listed_from") or ""))
                except ValueError as exc:
                    raise ETFUniverseError(f"manual ETF listed_from must be an ISO date for {symbol}") from exc
                parsed[sector].append({"symbol": symbol, "ts_code": ts_code, "listed_from": listed_from})

    if manifest_source == "manual_config" and len(seen) != 1:
        raise ETFUniverseError("manual_config ETF universe must declare exactly one ETF")
    if manifest_source == "catalog":
        try:
            snapshot = latest_completed_catalog_snapshot(conn, max_age_days=int(history.get("catalog_max_age_days", 7)), now=now)
        except RuntimeError as exc:
            raise ETFUniverseError(str(exc)) from exc
    else:
        snapshot = f"manual-config:{history_config_digest(phase0_cfg, universe_name, tuple(selected))}"
    members: list[ETFManifestMember] = []
    for sector in selected:
        for entry in sorted(parsed[sector], key=lambda value: str(value["symbol"])):
            symbol = str(entry["symbol"])
            if manifest_source == "catalog":
                row = conn.execute(
                    "SELECT ts_code,list_status,list_date,delist_date FROM market_etfs WHERE catalog_snapshot_id=? AND symbol=?",
                    (snapshot, symbol),
                ).fetchone()
                if row is None:
                    raise ETFUniverseError(f"configured ETF symbol missing from catalog: {symbol}")
                ts_code, list_status, listed_text, delisted_text = row
                if to_tushare_symbol(symbol) != ts_code:
                    raise ETFUniverseError(f"ETF symbol exchange mismatch: {symbol} versus {ts_code}")
                mapping = conn.execute(
                    "SELECT tracking_index_symbol FROM market_etf_tracking_mappings WHERE catalog_snapshot_id=? AND symbol=? AND mapping_kind='provider_observation' ORDER BY observed_at DESC LIMIT 1",
                    (snapshot, symbol),
                ).fetchone()
                resolved = _tracking_symbol(mapping[0]) if mapping and mapping[0] else None
                expected = entry["expected"]
                if expected is not None and expected != resolved:
                    raise ETFUniverseError(f"tracking index mismatch for {symbol}: expected {expected}, resolved {resolved}")
                listed = date.fromisoformat(str(listed_text))
                if list_status == "D" and not delisted_text:
                    raise ETFUniverseError(f"delisted ETF {symbol} has no reliable delist_date")
                lifecycle_end = date.fromisoformat(str(delisted_text)) if delisted_text else end_date
                mapping_status = "matched" if expected is not None else "not_configured"
            else:
                ts_code = str(entry["ts_code"])
                listed = entry["listed_from"]
                if not isinstance(listed, date):
                    raise ETFUniverseError(f"manual ETF listed_from is invalid for {symbol}")
                lifecycle_end = end_date
                expected = None
                resolved = None
                mapping_status = "not_applicable_manual_config"
            effective_start = max(start_date, listed)
            effective_end = min(end_date, lifecycle_end)
            if effective_start > effective_end:
                continue
            members.append(ETFManifestMember(
                universe_name, sector, symbol, str(ts_code), start_date, end_date,
                effective_start, effective_end, expected, resolved,
                mapping_status,
            ))
    if not members:
        raise ETFUniverseError("ETF universe has no lifecycle overlap with requested dates")
    members.sort(key=lambda item: (item.sector, item.symbol))
    requested_tuple = tuple(selected)
    return ETFUniverseManifest(
        universe_name, requested_tuple, start_date, end_date,
        history_config_digest(phase0_cfg, universe_name, requested_tuple), snapshot, tuple(members), manifest_source,
    )


def resolve_etf_universe_from_config(
    config_path: Path,
    *,
    universe_name: str,
    requested_sectors: list[str] | None,
    start_date: str,
    end_date: str,
) -> ETFUniverseManifest:
    """Resolve a named ETF universe against the configured catalog store."""
    config_path = Path(config_path).resolve()
    phase0_cfg = load_config(config_path)
    history_cfg = _history_cfg(phase0_cfg)
    try:
        requested_start = date.fromisoformat(start_date)
        requested_end = date.fromisoformat(end_date)
    except ValueError as exc:
        raise ETFUniverseError("start_date and end_date must be ISO dates") from exc
    db_path = Path(str(history_cfg.get("path", "data/etf_history.sqlite")))
    if not db_path.is_absolute():
        db_path = config_path.parent / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        ensure_etf_schema(conn)
        return resolve_etf_universe(
            conn,
            phase0_cfg=phase0_cfg,
            universe_name=universe_name,
            requested_sectors=requested_sectors,
            start_date=requested_start,
            end_date=requested_end,
        )
