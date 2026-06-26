from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from phase0.data_governance.external_market_history import configure_us_market_history
from phase0.data_access.local_history import configure_local_history, local_history_path
from phase0.data_access.throttle import configure_akshare_throttle
from phase0.universe import _filter_snapshot, _score_snapshot, _select_balanced_universe, load_point_in_time_universe


@dataclass(frozen=True)
class MissingCoreAuditResult:
    symbol_csv_path: Path
    event_csv_path: Path
    report_md_path: Path
    run_log_md_path: Path
    symbol_rows: int
    event_rows: int


def run_missing_core_audit(
    *,
    config: dict[str, Any],
    root: Path,
    config_path: Path | None,
    missing_reasons_path: Path,
    candidate_folds_path: Path,
    output_dir: Path,
    top_symbols: int = 30,
    command: str | None = None,
) -> MissingCoreAuditResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    configure_local_history(config.get("local_history", {}), root)
    configure_us_market_history(config.get("us_market_history", {}), root)
    configure_akshare_throttle(config.get("data_sources", {}).get("akshare", {}))

    missing = _read_required_csv(missing_reasons_path, "strategy_core_reachability_failure_reasons.csv")
    _require_columns(
        missing,
        ["strategy_id", "walk_forward_preset", "fold", "date", "symbol", "benchmark_rank", "benchmark_weight", "failure_reason"],
        missing_reasons_path,
    )
    missing = missing[missing["failure_reason"].astype(str).eq("missing_from_pit_panel")].copy()
    if missing.empty:
        event_df = pd.DataFrame()
        symbol_df = pd.DataFrame()
    else:
        missing["symbol"] = missing["symbol"].astype(str).str.strip()
        missing["date"] = pd.to_datetime(missing["date"], errors="coerce").dt.normalize()
        missing["benchmark_weight"] = pd.to_numeric(missing["benchmark_weight"], errors="coerce").fillna(0.0)
        missing["benchmark_rank"] = pd.to_numeric(missing["benchmark_rank"], errors="coerce")
        symbol_priority = (
            missing.groupby("symbol", as_index=False)
            .agg(
                missing_days=("date", "nunique"),
                missing_folds=("fold", "nunique"),
                avg_rank=("benchmark_rank", "mean"),
                min_rank=("benchmark_rank", "min"),
                avg_weight=("benchmark_weight", "mean"),
                total_missing_weight=("benchmark_weight", "sum"),
            )
            .sort_values(["total_missing_weight", "missing_days"], ascending=[False, False])
        )
        selected_symbols = set(symbol_priority.head(max(1, int(top_symbols)))["symbol"].astype(str).tolist())
        scoped_missing = missing[missing["symbol"].isin(selected_symbols)].copy()
        event_df = _event_audit(
            scoped_missing,
            config=config,
            root=root,
            candidate_folds_path=candidate_folds_path,
        )
        symbol_df = _symbol_summary(event_df, symbol_priority)

    symbol_csv_path = output_dir / "missing_core_symbol_audit.csv"
    event_csv_path = output_dir / "missing_core_event_audit.csv"
    report_md_path = output_dir / "missing_core_audit_report.md"
    run_log_md_path = output_dir / "missing_core_audit_run_log.md"
    symbol_df.to_csv(symbol_csv_path, index=False)
    event_df.to_csv(event_csv_path, index=False)
    _write_report(report_md_path, symbol_df=symbol_df, event_df=event_df, top_symbols=top_symbols)
    _write_run_log(
        run_log_md_path,
        config_path=config_path,
        missing_reasons_path=missing_reasons_path,
        candidate_folds_path=candidate_folds_path,
        output_dir=output_dir,
        command=command,
    )
    return MissingCoreAuditResult(
        symbol_csv_path=symbol_csv_path,
        event_csv_path=event_csv_path,
        report_md_path=report_md_path,
        run_log_md_path=run_log_md_path,
        symbol_rows=len(symbol_df),
        event_rows=len(event_df),
    )


def _event_audit(
    missing: pd.DataFrame,
    *,
    config: dict[str, Any],
    root: Path,
    candidate_folds_path: Path,
) -> pd.DataFrame:
    folds = _read_required_csv(candidate_folds_path, "strategy_admission_candidate_folds.csv")
    _require_columns(
        folds,
        ["strategy_id", "walk_forward_preset", "fold", "train_end", "valid_start", "valid_end"],
        candidate_folds_path,
    )
    folds["fold"] = folds["fold"].astype(int)
    folds["strategy_id"] = folds["strategy_id"].astype(str)
    folds["walk_forward_preset"] = folds["walk_forward_preset"].astype(str)
    fold_rows = folds.drop_duplicates(["strategy_id", "walk_forward_preset", "fold"]).set_index(
        ["strategy_id", "walk_forward_preset", "fold"],
    )
    db_summary = _db_symbol_summary(sorted(missing["symbol"].unique().tolist()), config=config)
    universe_cache: dict[str, dict[str, pd.DataFrame | int]] = {}
    rows: list[dict[str, Any]] = []
    for (strategy_id, preset_name, fold, symbol), group in missing.groupby(
        ["strategy_id", "walk_forward_preset", "fold", "symbol"],
        sort=True,
    ):
        strategy_id = str(strategy_id)
        preset_name = str(preset_name)
        fold = int(fold)
        key = (strategy_id, preset_name, fold)
        fold_row = fold_rows.loc[key] if key in fold_rows.index else pd.Series(dtype=object)
        train_end = _safe_str(fold_row.get("train_end"))
        valid_start = _safe_str(fold_row.get("valid_start"))
        valid_end = _safe_str(fold_row.get("valid_end"))
        universe_info = _universe_membership(
            config=config,
            root=root,
            train_end=train_end,
            symbol=symbol,
            cache=universe_cache,
        )
        db = db_summary.get(symbol, {})
        missing_days = int(group["date"].nunique())
        fold_db = _fold_db_coverage(
            symbol=symbol,
            train_end=train_end,
            valid_start=valid_start,
            valid_end=valid_end,
            missing_dates=group["date"],
            config=config,
        )
        reason = _classify_reason(
            in_snapshot=bool(universe_info.get("in_snapshot")),
            in_filtered=bool(universe_info.get("in_filtered")),
            in_scored=bool(universe_info.get("in_scored")),
            in_selected_before_limit=bool(universe_info.get("in_selected_before_limit")),
            in_universe=bool(universe_info.get("in_universe")),
            missing_days=missing_days,
            snapshot_bfq_rows=int(fold_db.get("snapshot_bfq_rows", 0)),
            snapshot_basic_rows=int(fold_db.get("snapshot_basic_rows", 0)),
            valid_bfq_rows=int(fold_db.get("valid_bfq_rows", 0)),
            valid_adj_factor_rows=int(fold_db.get("valid_adj_factor_rows", 0)),
            missing_dates_present_in_valid_bfq=int(fold_db.get("missing_dates_present_in_valid_bfq", 0)),
            missing_dates_present_in_valid_adj=int(fold_db.get("missing_dates_present_in_valid_adj", 0)),
            db_daily_rows=int(db.get("daily_rows", 0)),
            db_basic_rows=int(db.get("daily_basic_rows", 0)),
            db_adj_rows=int(db.get("adj_factor_rows", 0)),
        )
        rows.append(
            {
                "strategy_id": strategy_id,
                "walk_forward_preset": preset_name,
                "fold": fold,
                "symbol": symbol,
                "name": _safe_str(universe_info.get("name") or db.get("name")),
                "industry": _safe_str(universe_info.get("industry") or db.get("industry")),
                "valid_start": valid_start,
                "valid_end": valid_end,
                "train_end": train_end,
                "missing_days": missing_days,
                "avg_rank": float(pd.to_numeric(group["benchmark_rank"], errors="coerce").mean()),
                "min_rank": float(pd.to_numeric(group["benchmark_rank"], errors="coerce").min()),
                "avg_weight": float(pd.to_numeric(group["benchmark_weight"], errors="coerce").mean()),
                "total_missing_weight": float(pd.to_numeric(group["benchmark_weight"], errors="coerce").sum()),
                "in_pit_snapshot": bool(universe_info.get("in_snapshot")),
                "in_pit_filtered": bool(universe_info.get("in_filtered")),
                "in_pit_scored": bool(universe_info.get("in_scored")),
                "in_pit_selected_before_limit": bool(universe_info.get("in_selected_before_limit")),
                "in_pit_universe": bool(universe_info.get("in_universe")),
                "pit_universe_rank": _safe_float(universe_info.get("universe_rank")),
                "pit_universe_score": _safe_float(universe_info.get("universe_score")),
                "pit_liquidity_rank": _safe_float(universe_info.get("liquidity_rank")),
                "pit_size_rank": _safe_float(universe_info.get("size_rank")),
                "pit_walk_forward_limit": _safe_int(universe_info.get("walk_forward_limit")),
                "snapshot_window_start": _safe_str(fold_db.get("snapshot_window_start")),
                "snapshot_bfq_rows": _safe_int(fold_db.get("snapshot_bfq_rows")),
                "snapshot_qfq_rows": _safe_int(fold_db.get("snapshot_qfq_rows")),
                "snapshot_basic_rows": _safe_int(fold_db.get("snapshot_basic_rows")),
                "valid_bfq_rows": _safe_int(fold_db.get("valid_bfq_rows")),
                "valid_qfq_rows": _safe_int(fold_db.get("valid_qfq_rows")),
                "valid_adj_factor_rows": _safe_int(fold_db.get("valid_adj_factor_rows")),
                "valid_basic_rows": _safe_int(fold_db.get("valid_basic_rows")),
                "missing_dates_present_in_valid_bfq": _safe_int(fold_db.get("missing_dates_present_in_valid_bfq")),
                "missing_dates_present_in_valid_qfq": _safe_int(fold_db.get("missing_dates_present_in_valid_qfq")),
                "missing_dates_present_in_valid_adj": _safe_int(fold_db.get("missing_dates_present_in_valid_adj")),
                "db_stock_metadata": bool(db.get("metadata_rows", 0)),
                "db_daily_rows": int(db.get("daily_rows", 0)),
                "db_daily_min_date": _safe_str(db.get("daily_min_date")),
                "db_daily_max_date": _safe_str(db.get("daily_max_date")),
                "db_daily_basic_rows": int(db.get("daily_basic_rows", 0)),
                "db_adj_factor_rows": int(db.get("adj_factor_rows", 0)),
                "classification": reason,
            }
        )
    return pd.DataFrame(rows)


def _universe_membership(
    *,
    config: dict[str, Any],
    root: Path,
    train_end: str,
    symbol: str,
    cache: dict[str, dict[str, pd.DataFrame | int]] | None = None,
) -> dict[str, Any]:
    if not train_end:
        return {}
    frames = _pit_membership_frames(config=config, root=root, train_end=train_end, cache=cache)
    snapshot = frames["snapshot"].copy()
    filtered = frames["filtered"].copy()
    scored = frames["scored"].copy()
    selected_before_limit = frames["selected_before_limit"].copy()
    universe = frames["universe"].copy()
    out: dict[str, Any] = {
        "in_snapshot": False,
        "in_filtered": False,
        "in_scored": False,
        "in_selected_before_limit": False,
        "in_universe": False,
        "walk_forward_limit": int(frames.get("walk_forward_limit", 0) or 0),
    }
    if not snapshot.empty and "symbol" in snapshot.columns:
        row = snapshot[snapshot["symbol"].astype(str).eq(symbol)]
        out["in_snapshot"] = not row.empty
        if not row.empty:
            out.update(_row_fields(row.iloc[0]))
    if not filtered.empty and "symbol" in filtered.columns:
        row = filtered[filtered["symbol"].astype(str).eq(symbol)]
        out["in_filtered"] = not row.empty
        if not row.empty:
            out.update(_row_fields(row.iloc[0]))
    if not scored.empty and "symbol" in scored.columns:
        row = scored[scored["symbol"].astype(str).eq(symbol)]
        out["in_scored"] = not row.empty
        if not row.empty:
            out.update(_row_fields(row.iloc[0]))
    if not selected_before_limit.empty and "symbol" in selected_before_limit.columns:
        row = selected_before_limit[selected_before_limit["symbol"].astype(str).eq(symbol)]
        out["in_selected_before_limit"] = not row.empty
        if not row.empty:
            out.update(_row_fields(row.iloc[0]))
    if not universe.empty and "symbol" in universe.columns:
        row = universe[universe["symbol"].astype(str).eq(symbol)]
        out["in_universe"] = not row.empty
        if not row.empty:
            out.update(_row_fields(row.iloc[0]))
    return out


def _pit_membership_frames(
    *,
    config: dict[str, Any],
    root: Path,
    train_end: str,
    cache: dict[str, dict[str, pd.DataFrame | int]] | None = None,
) -> dict[str, pd.DataFrame | int]:
    if cache is not None and train_end in cache:
        return cache[train_end]
    pit = load_point_in_time_universe(config, root, train_end)
    snapshot = pit.snapshot.copy()
    if snapshot.empty:
        filtered = snapshot.copy()
        scored = snapshot.copy()
        selected_before_limit = snapshot.copy()
    else:
        filtered = _filter_snapshot(snapshot, config)
        scored = _score_snapshot(filtered) if not filtered.empty else filtered
        selected_before_limit = _select_balanced_universe(scored, config)
        if not selected_before_limit.empty:
            selected_before_limit = selected_before_limit.copy()
            selected_before_limit["universe_rank"] = np.arange(1, len(selected_before_limit) + 1)
    universe_cfg = config.get("universe", {})
    walk_forward_limit = int(universe_cfg.get("walk_forward_limit", universe_cfg.get("target_size", 500)))
    frames: dict[str, pd.DataFrame | int] = {
        "snapshot": snapshot,
        "filtered": filtered,
        "scored": scored,
        "selected_before_limit": selected_before_limit,
        "universe": pit.universe.copy(),
        "walk_forward_limit": walk_forward_limit,
    }
    if cache is not None:
        cache[train_end] = frames
    return frames


def _row_fields(row: pd.Series) -> dict[str, Any]:
    fields = [
        "name",
        "industry",
        "universe_rank",
        "universe_score",
        "liquidity_rank",
        "size_rank",
        "amount",
        "total_mv",
        "pe_ttm",
        "pb",
    ]
    return {field: row.get(field) for field in fields if field in row.index}


def _db_symbol_summary(symbols: list[str], *, config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    db_path = local_history_path()
    if not db_path.exists():
        return {}
    local_cfg = config.get("local_history", {})
    market = str(local_cfg.get("market", "CN"))
    meta_table = _safe_identifier(str(local_cfg.get("meta_table", "market_stocks")))
    daily_table = _safe_identifier(str(local_cfg.get("daily_table", "market_daily_bars")))
    daily_basic_table = _safe_identifier(str(local_cfg.get("daily_basic_table", "market_daily_basic")))
    adj_factor_table = _safe_identifier(str(local_cfg.get("adj_factor_table", "market_adj_factors")))
    out: dict[str, dict[str, Any]] = {}
    with sqlite3.connect(db_path) as conn:
        for symbol in symbols:
            row: dict[str, Any] = {}
            meta = conn.execute(
                f"SELECT COUNT(*), MAX(name), MAX(industry) FROM {meta_table} WHERE market = ? AND symbol = ?",
                (market, symbol),
            ).fetchone()
            row["metadata_rows"] = int(meta[0] or 0)
            row["name"] = meta[1] or ""
            row["industry"] = meta[2] or ""
            for table, prefix in [
                (daily_table, "daily"),
                (daily_basic_table, "daily_basic"),
                (adj_factor_table, "adj_factor"),
            ]:
                try:
                    values = conn.execute(
                        f"SELECT COUNT(*), MIN(date), MAX(date) FROM {table} WHERE market = ? AND symbol = ?",
                        (market, symbol),
                    ).fetchone()
                except sqlite3.Error:
                    values = (0, "", "")
                row[f"{prefix}_rows"] = int(values[0] or 0)
                row[f"{prefix}_min_date"] = values[1] or ""
                row[f"{prefix}_max_date"] = values[2] or ""
            out[symbol] = row
    return out


def _fold_db_coverage(
    *,
    symbol: str,
    train_end: str,
    valid_start: str,
    valid_end: str,
    missing_dates: pd.Series,
    config: dict[str, Any],
) -> dict[str, Any]:
    db_path = local_history_path()
    if not db_path.exists():
        return {}
    local_cfg = config.get("local_history", {})
    universe_cfg = config.get("universe", {})
    market = str(local_cfg.get("market", "CN"))
    daily_table = _safe_identifier(str(local_cfg.get("daily_table", "market_daily_bars")))
    daily_basic_table = _safe_identifier(str(local_cfg.get("daily_basic_table", "market_daily_basic")))
    adj_factor_table = _safe_identifier(str(local_cfg.get("adj_factor_table", "market_adj_factors")))
    train_end_ts = pd.to_datetime(train_end, errors="coerce")
    valid_start_ts = pd.to_datetime(valid_start, errors="coerce")
    valid_end_ts = pd.to_datetime(valid_end, errors="coerce")
    if pd.isna(train_end_ts) or pd.isna(valid_start_ts) or pd.isna(valid_end_ts):
        return {}
    snapshot_days = int(universe_cfg.get("fallback_days", 90))
    snapshot_start = (pd.Timestamp(train_end_ts).date() - timedelta(days=snapshot_days)).isoformat()
    train_end_str = pd.Timestamp(train_end_ts).date().isoformat()
    valid_start_str = pd.Timestamp(valid_start_ts).date().isoformat()
    valid_end_str = pd.Timestamp(valid_end_ts).date().isoformat()
    missing_date_set = {
        pd.Timestamp(value).date().isoformat()
        for value in pd.to_datetime(missing_dates, errors="coerce").dropna().tolist()
    }
    with sqlite3.connect(db_path) as conn:
        snapshot_bfq = _count_table_rows(
            conn,
            table=daily_table,
            market=market,
            symbol=symbol,
            start=snapshot_start,
            end=train_end_str,
            adjust_type="bfq",
        )
        snapshot_qfq = _count_table_rows(
            conn,
            table=daily_table,
            market=market,
            symbol=symbol,
            start=snapshot_start,
            end=train_end_str,
            adjust_type="qfq",
        )
        snapshot_basic = _count_table_rows(
            conn,
            table=daily_basic_table,
            market=market,
            symbol=symbol,
            start=snapshot_start,
            end=train_end_str,
        )
        valid_bfq = _count_table_rows(
            conn,
            table=daily_table,
            market=market,
            symbol=symbol,
            start=valid_start_str,
            end=valid_end_str,
            adjust_type="bfq",
        )
        valid_qfq = _count_table_rows(
            conn,
            table=daily_table,
            market=market,
            symbol=symbol,
            start=valid_start_str,
            end=valid_end_str,
            adjust_type="qfq",
        )
        valid_adj = _count_table_rows(
            conn,
            table=adj_factor_table,
            market=market,
            symbol=symbol,
            start=valid_start_str,
            end=valid_end_str,
        )
        valid_basic = _count_table_rows(
            conn,
            table=daily_basic_table,
            market=market,
            symbol=symbol,
            start=valid_start_str,
            end=valid_end_str,
        )
        missing_bfq = _count_specific_dates(
            conn,
            table=daily_table,
            market=market,
            symbol=symbol,
            dates=missing_date_set,
            adjust_type="bfq",
        )
        missing_qfq = _count_specific_dates(
            conn,
            table=daily_table,
            market=market,
            symbol=symbol,
            dates=missing_date_set,
            adjust_type="qfq",
        )
        missing_adj = _count_specific_dates(
            conn,
            table=adj_factor_table,
            market=market,
            symbol=symbol,
            dates=missing_date_set,
        )
    return {
        "snapshot_window_start": snapshot_start,
        "snapshot_bfq_rows": snapshot_bfq,
        "snapshot_qfq_rows": snapshot_qfq,
        "snapshot_basic_rows": snapshot_basic,
        "valid_bfq_rows": valid_bfq,
        "valid_qfq_rows": valid_qfq,
        "valid_adj_factor_rows": valid_adj,
        "valid_basic_rows": valid_basic,
        "missing_dates_present_in_valid_bfq": missing_bfq,
        "missing_dates_present_in_valid_qfq": missing_qfq,
        "missing_dates_present_in_valid_adj": missing_adj,
    }


def _count_table_rows(
    conn: sqlite3.Connection,
    *,
    table: str,
    market: str,
    symbol: str,
    start: str,
    end: str,
    adjust_type: str | None = None,
) -> int:
    adjust_filter = ""
    params: list[Any] = [market, symbol, start, end]
    if adjust_type and _sqlite_table_has_column(conn, table, "adjust_type"):
        adjust_filter = "AND adjust_type = ?"
        params.append(adjust_type)
    try:
        value = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM {table}
            WHERE market = ?
              AND symbol = ?
              AND date >= ?
              AND date <= ?
              {adjust_filter}
            """,
            tuple(params),
        ).fetchone()
    except sqlite3.Error:
        return 0
    return int(value[0] or 0)


def _count_specific_dates(
    conn: sqlite3.Connection,
    *,
    table: str,
    market: str,
    symbol: str,
    dates: set[str],
    adjust_type: str | None = None,
) -> int:
    if not dates:
        return 0
    placeholders = ",".join(["?"] * len(dates))
    adjust_filter = ""
    params: list[Any] = [market, symbol, *sorted(dates)]
    if adjust_type and _sqlite_table_has_column(conn, table, "adjust_type"):
        adjust_filter = "AND adjust_type = ?"
        params.append(adjust_type)
    try:
        value = conn.execute(
            f"""
            SELECT COUNT(DISTINCT date)
            FROM {table}
            WHERE market = ?
              AND symbol = ?
              AND date IN ({placeholders})
              {adjust_filter}
            """,
            tuple(params),
        ).fetchone()
    except sqlite3.Error:
        return 0
    return int(value[0] or 0)


def _sqlite_table_has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    except sqlite3.Error:
        return False
    return any(str(row[1]) == column for row in rows)


def _safe_identifier(value: str) -> str:
    import re

    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Unsafe SQL identifier: {value}")
    return value


def _symbol_summary(event_df: pd.DataFrame, priority_df: pd.DataFrame) -> pd.DataFrame:
    if event_df.empty:
        return pd.DataFrame()
    grouped = (
        event_df.groupby(["symbol", "name", "industry"], dropna=False)
        .agg(
            missing_folds=("fold", "nunique"),
            missing_days=("missing_days", "sum"),
            avg_rank=("avg_rank", "mean"),
            min_rank=("min_rank", "min"),
            avg_weight=("avg_weight", "mean"),
            total_missing_weight=("total_missing_weight", "sum"),
            in_pit_snapshot_folds=("in_pit_snapshot", "sum"),
            in_pit_filtered_folds=("in_pit_filtered", "sum"),
            in_pit_selected_before_limit_folds=("in_pit_selected_before_limit", "sum"),
            in_pit_universe_folds=("in_pit_universe", "sum"),
            missing_dates_present_in_valid_bfq=("missing_dates_present_in_valid_bfq", "sum"),
            missing_dates_present_in_valid_adj=("missing_dates_present_in_valid_adj", "sum"),
            snapshot_bfq_rows=("snapshot_bfq_rows", "sum"),
            snapshot_basic_rows=("snapshot_basic_rows", "sum"),
            valid_bfq_rows=("valid_bfq_rows", "sum"),
            valid_adj_factor_rows=("valid_adj_factor_rows", "sum"),
            db_daily_rows=("db_daily_rows", "max"),
            db_daily_basic_rows=("db_daily_basic_rows", "max"),
            db_adj_factor_rows=("db_adj_factor_rows", "max"),
        )
        .reset_index()
    )
    classifications = (
        event_df.groupby("symbol")["classification"]
        .agg(lambda values: ",".join(sorted(set(str(value) for value in values))))
        .reset_index()
    )
    out = grouped.merge(classifications, on="symbol", how="left")
    return out.sort_values(["total_missing_weight", "missing_days"], ascending=[False, False]).reset_index(drop=True)


def _classify_reason(
    *,
    in_snapshot: bool,
    in_filtered: bool,
    in_scored: bool,
    in_selected_before_limit: bool,
    in_universe: bool,
    missing_days: int,
    snapshot_bfq_rows: int,
    snapshot_basic_rows: int,
    valid_bfq_rows: int,
    valid_adj_factor_rows: int,
    missing_dates_present_in_valid_bfq: int,
    missing_dates_present_in_valid_adj: int,
    db_daily_rows: int,
    db_basic_rows: int,
    db_adj_rows: int,
) -> str:
    if in_universe:
        if valid_bfq_rows <= 0 or valid_adj_factor_rows <= 0:
            return "universe_member_with_valid_window_data_gap"
        if missing_dates_present_in_valid_bfq >= missing_days and missing_dates_present_in_valid_adj >= missing_days:
            return "universe_member_but_panel_missing"
        return "universe_member_but_panel_missing"
    if in_selected_before_limit:
        return "beyond_walk_forward_limit"
    if in_scored or in_filtered:
        return "ranked_out_or_balanced_out_of_pit_universe"
    if in_snapshot:
        return "filtered_out_before_universe_selection"
    if snapshot_bfq_rows <= 0:
        return "snapshot_window_price_gap"
    if snapshot_basic_rows <= 0:
        return "snapshot_window_basic_gap"
    if db_daily_rows > 0 and db_basic_rows > 0 and db_adj_rows > 0:
        return "available_in_db_but_absent_from_pit_snapshot"
    if db_daily_rows <= 0:
        return "missing_daily_history"
    if db_basic_rows <= 0:
        return "missing_daily_basic"
    if db_adj_rows <= 0:
        return "missing_adjustment_factor"
    return "unknown"


def _write_report(path: Path, *, symbol_df: pd.DataFrame, event_df: pd.DataFrame, top_symbols: int) -> None:
    total_missing_weight = float(event_df["total_missing_weight"].sum()) if "total_missing_weight" in event_df.columns else 0.0
    total_missing_days = int(event_df["missing_days"].sum()) if "missing_days" in event_df.columns else 0
    lines = [
        "# Missing Core Member Audit",
        "",
        f"Generated at: {pd.Timestamp.now().isoformat(timespec='seconds')}",
        "",
        "## Scope",
        "",
        f"- Top symbols audited: `{int(top_symbols)}`",
        f"- Fold-symbol rows audited: `{len(event_df)}`",
        f"- Missing days represented by audited rows: `{total_missing_days}`",
        f"- Sum of missing benchmark weight over audited rows: `{total_missing_weight:.4f}`",
        "- Input reason: `missing_from_pit_panel` from strategy core reachability diagnostic.",
        "- This is a read-only data coverage audit. It does not alter universe construction or strategy admission.",
        "",
        "## Symbol Summary",
        "",
    ]
    if symbol_df.empty:
        lines.append("No missing core symbols to audit.")
    else:
        lines.append(
            _md_table(
                ["symbol", "name", "industry", "folds", "days", "avg_rank", "avg_weight", "classification"],
                [
                    [
                        _safe_str(row.get("symbol")),
                        _safe_str(row.get("name")),
                        _safe_str(row.get("industry")),
                        str(_safe_int(row.get("missing_folds"))),
                        str(_safe_int(row.get("missing_days"))),
                        f"{_safe_float(row.get('avg_rank')):.2f}",
                        f"{_safe_float(row.get('avg_weight')):.4%}",
                        _safe_str(row.get("classification")),
                    ]
                    for _, row in symbol_df.head(int(top_symbols)).iterrows()
                ],
            )
        )
        lines.extend(["", "## Classification Counts", ""])
        counts = event_df["classification"].value_counts().reset_index() if not event_df.empty else pd.DataFrame()
        if not counts.empty:
            counts.columns = ["classification", "fold_symbol_rows"]
            counts = counts.merge(
                event_df.groupby("classification", as_index=False).agg(
                    missing_days=("missing_days", "sum"),
                    missing_weight=("total_missing_weight", "sum"),
                ),
                on="classification",
                how="left",
            )
            lines.append(
                _md_table(
                    ["classification", "fold_symbol_rows", "missing_days", "missing_weight"],
                    [
                        [
                            _safe_str(row["classification"]),
                            str(_safe_int(row["fold_symbol_rows"])),
                            str(_safe_int(row["missing_days"])),
                            f"{_safe_float(row['missing_weight']):.4f}",
                        ]
                        for _, row in counts.iterrows()
                    ],
                )
            )
        fold_counts = (
            event_df.groupby(["fold", "classification"], as_index=False)
            .agg(missing_days=("missing_days", "sum"), missing_weight=("total_missing_weight", "sum"))
            .sort_values(["fold", "missing_weight"], ascending=[True, False])
        )
        if not fold_counts.empty:
            lines.extend(["", "## Fold Classification Weights", ""])
            lines.append(
                _md_table(
                    ["fold", "classification", "missing_days", "missing_weight"],
                    [
                        [
                            str(_safe_int(row["fold"])),
                            _safe_str(row["classification"]),
                            str(_safe_int(row["missing_days"])),
                            f"{_safe_float(row['missing_weight']):.4f}",
                        ]
                        for _, row in fold_counts.iterrows()
                    ],
                )
            )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_run_log(
    path: Path,
    *,
    config_path: Path | None,
    missing_reasons_path: Path,
    candidate_folds_path: Path,
    output_dir: Path,
    command: str | None,
) -> None:
    lines = [
        "# Missing Core Member Audit Run Log",
        "",
        f"- generated_at: `{pd.Timestamp.now().isoformat(timespec='seconds')}`",
        f"- config_path: `{config_path or ''}`",
        f"- missing_reasons_path: `{missing_reasons_path}`",
        f"- candidate_folds_path: `{candidate_folds_path}`",
        f"- output_dir: `{output_dir}`",
        f"- command: `{command or ''}`",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _read_required_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    return pd.read_csv(path)


def _require_columns(df: pd.DataFrame, columns: list[str], path: Path) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"{path} missing required columns: {', '.join(missing)}")


def _safe_str(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value)


def _safe_int(value: Any) -> int:
    if value is None or pd.isna(value):
        return 0
    return int(value)


def _safe_float(value: Any) -> float:
    if value is None or pd.isna(value):
        return 0.0
    return float(value)


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(item) for item in row) + " |")
    return "\n".join(lines)
