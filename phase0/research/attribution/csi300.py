from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


EPS = 1e-12
DEFAULT_CONTEXT_LABEL = "relative_lag_in_strong_benchmark_context"
DEFAULT_BENCHMARK = "SH.000300"
UNKNOWN_INDUSTRY = "UNKNOWN"


@dataclass(frozen=True)
class StrategyCsi300AttributionResult:
    daily_csv_path: Path
    fold_csv_path: Path
    missed_top_csv_path: Path
    industry_csv_path: Path
    report_md_path: Path
    run_log_md_path: Path
    status: str
    daily_rows: int
    fold_rows: int


def run_strategy_csi300_attribution(
    *,
    config: dict[str, Any],
    root: Path,
    holdings_path: Path | None = None,
    daily_exposure_path: Path | None = None,
    candidate_folds_path: Path | None = None,
    market_context_path: Path | None = None,
    output_dir: Path | None = None,
    benchmark_symbol: str | None = None,
    context_label: str = DEFAULT_CONTEXT_LABEL,
    top_n: int = 20,
    weight_date_lag_days: int = 1,
    command: str | None = None,
) -> StrategyCsi300AttributionResult:
    """Attribute strategy lag against CSI300 using point-in-time benchmark weights.

    The diagnostic is research-only. It reads existing daily holdings and local
    CSI300 as-of tables, then uses the latest benchmark weight date before the
    configured lookup cutoff for each holding date.
    """
    if output_dir is None:
        if holdings_path is not None:
            output_dir = holdings_path.parent
        elif candidate_folds_path is not None:
            output_dir = candidate_folds_path.parent
        else:
            raise ValueError("output_dir is required when neither holdings nor candidate_folds is provided")
    output_dir.mkdir(parents=True, exist_ok=True)
    if int(top_n) <= 0:
        raise ValueError("top_n must be positive")
    weight_date_lag_days = max(0, int(weight_date_lag_days))
    symbol = benchmark_symbol or str(config.get("benchmark_symbol", DEFAULT_BENCHMARK))
    db_path = _resolve_local_history_path(config, root)

    daily_csv_path = output_dir / "strategy_csi300_daily_attribution.csv"
    fold_csv_path = output_dir / "strategy_csi300_fold_attribution.csv"
    missed_top_csv_path = output_dir / "strategy_csi300_missed_top_weights.csv"
    industry_csv_path = output_dir / "strategy_csi300_industry_active_weights.csv"
    report_md_path = output_dir / "strategy_csi300_attribution_report.md"
    run_log_md_path = output_dir / "strategy_csi300_attribution_run_log.md"

    if holdings_path is not None:
        holdings = _read_required_csv(holdings_path, "strategy_daily_holdings.csv")
        _require_columns(
            holdings,
            [
                "strategy_id",
                "walk_forward_preset",
                "fold",
                "valid_start",
                "valid_end",
                "market_context_label",
                "date",
                "symbol",
                "industry",
                "live_weight",
                "position_ret",
            ],
            holdings_path,
        )
        holdings = _prepare_holdings(holdings)
    else:
        holdings = _empty_holdings_frame()
    if context_label and context_label != "all":
        holdings = holdings[holdings["market_context_label"].astype(str) == str(context_label)].copy()

    daily_exposure = _read_optional_daily_exposure(daily_exposure_path)
    if daily_exposure is not None and context_label and context_label != "all" and "market_context_label" in daily_exposure.columns:
        daily_exposure = daily_exposure[daily_exposure["market_context_label"].astype(str) == str(context_label)].copy()

    candidate_folds = _read_optional_candidate_folds(candidate_folds_path)
    market_context = _read_optional_market_context(market_context_path)
    date_scaffold = _build_date_scaffold(
        holdings=holdings,
        candidate_folds=candidate_folds,
        market_context=market_context,
        db_path=db_path,
        benchmark_symbol=symbol,
        context_label=context_label,
    )

    if date_scaffold.empty:
        return _write_blocked_outputs(
            daily_csv_path=daily_csv_path,
            fold_csv_path=fold_csv_path,
            missed_top_csv_path=missed_top_csv_path,
            industry_csv_path=industry_csv_path,
            report_md_path=report_md_path,
            run_log_md_path=run_log_md_path,
            status="blocked_no_matching_holdings",
            reason=f"no holdings or candidate-fold dates matched context_label={context_label!r}",
            benchmark_symbol=symbol,
            db_path=db_path,
            holdings_path=holdings_path,
            daily_exposure_path=daily_exposure_path,
            candidate_folds_path=candidate_folds_path,
            market_context_path=market_context_path,
            output_dir=output_dir,
            command=command,
            top_n=top_n,
            weight_date_lag_days=weight_date_lag_days,
            context_label=context_label,
        )

    min_date = pd.to_datetime(date_scaffold["date"]).min().normalize()
    max_date = pd.to_datetime(date_scaffold["date"]).max().normalize()
    try:
        benchmark_weights = _load_benchmark_weights(
            db_path=db_path,
            benchmark_symbol=symbol,
            max_date=max_date,
        )
    except ValueError as exc:
        return _write_blocked_outputs(
            daily_csv_path=daily_csv_path,
            fold_csv_path=fold_csv_path,
            missed_top_csv_path=missed_top_csv_path,
            industry_csv_path=industry_csv_path,
            report_md_path=report_md_path,
            run_log_md_path=run_log_md_path,
            status="blocked_missing_asof_tables",
            reason=str(exc),
            benchmark_symbol=symbol,
            db_path=db_path,
            holdings_path=holdings_path,
            daily_exposure_path=daily_exposure_path,
            candidate_folds_path=candidate_folds_path,
            market_context_path=market_context_path,
            output_dir=output_dir,
            command=command,
            top_n=top_n,
            weight_date_lag_days=weight_date_lag_days,
            context_label=context_label,
        )

    benchmark_weights = benchmark_weights[benchmark_weights["trade_date_dt"] <= max_date].copy()
    if benchmark_weights.empty or benchmark_weights["trade_date_dt"].min() > max_date:
        return _write_blocked_outputs(
            daily_csv_path=daily_csv_path,
            fold_csv_path=fold_csv_path,
            missed_top_csv_path=missed_top_csv_path,
            industry_csv_path=industry_csv_path,
            report_md_path=report_md_path,
            run_log_md_path=run_log_md_path,
            status="blocked_insufficient_asof_history",
            reason=f"no CSI300 as-of weight date covers holdings window {min_date.date()}..{max_date.date()}",
            benchmark_symbol=symbol,
            db_path=db_path,
            holdings_path=holdings_path,
            daily_exposure_path=daily_exposure_path,
            candidate_folds_path=candidate_folds_path,
            market_context_path=market_context_path,
            output_dir=output_dir,
            command=command,
            top_n=top_n,
            weight_date_lag_days=weight_date_lag_days,
            context_label=context_label,
        )

    date_to_weight_date = _asof_weight_date_map(
        date_scaffold["date"],
        benchmark_weights["trade_date_dt"],
        lag_days=weight_date_lag_days,
    )
    exposure_lookup = _daily_exposure_lookup(daily_exposure)
    benchmark_return_lookup = _benchmark_return_lookup(
        db_path=db_path,
        benchmark_symbol=symbol,
        dates=date_scaffold["date"],
    )
    holdings_lookup = _holdings_lookup(holdings)
    daily_rows: list[dict[str, Any]] = []
    missed_rows: list[dict[str, Any]] = []
    industry_rows: list[dict[str, Any]] = []
    group_keys = [
        "strategy_id",
        "walk_forward_preset",
        "fold",
        "valid_start",
        "valid_end",
        "market_context_label",
        "date",
    ]
    weights_by_date = {pd.Timestamp(key): frame.copy() for key, frame in benchmark_weights.groupby("trade_date_dt", sort=False)}
    for _, scaffold_row in date_scaffold.sort_values(["strategy_id", "walk_forward_preset", "fold", "date"]).iterrows():
        row_key = _row_key_from_series(scaffold_row)
        trade_date = pd.Timestamp(row_key["date"]).normalize()
        weight_date = date_to_weight_date.get(trade_date)
        group = holdings_lookup.get(_lookup_key(row_key), _empty_holdings_frame())
        exposure_row = exposure_lookup.get(
            (
                str(row_key["strategy_id"]),
                str(row_key["walk_forward_preset"]),
                int(row_key["fold"]),
                trade_date,
            ),
            scaffold_row.to_dict(),
        )
        if pd.isna(_optional_float(exposure_row.get("benchmark_daily_return"))):
            exposure_row = dict(exposure_row)
            exposure_row["benchmark_daily_return"] = benchmark_return_lookup.get(trade_date, np.nan)
        if weight_date is None or pd.isna(weight_date):
            daily_rows.append(_insufficient_daily_row(row_key, exposure_row, symbol))
            continue

        benchmark = weights_by_date[pd.Timestamp(weight_date)].copy()
        daily, daily_missed, daily_industries = _attribute_one_day(
            row_key=row_key,
            holdings=group,
            benchmark=benchmark,
            benchmark_symbol=symbol,
            benchmark_weight_date=pd.Timestamp(weight_date),
            exposure_row=exposure_row,
            top_n=top_n,
        )
        daily_rows.append(daily)
        missed_rows.extend(daily_missed)
        industry_rows.extend(daily_industries)

    daily_df = pd.DataFrame(daily_rows)
    missed_df = _missed_top_summary(pd.DataFrame(missed_rows))
    industry_df = pd.DataFrame(industry_rows)
    fold_df = _fold_summary(daily_df)

    _format_dates_for_csv(daily_df)
    _format_dates_for_csv(missed_df)
    _format_dates_for_csv(industry_df)
    daily_df.to_csv(daily_csv_path, index=False)
    fold_df.to_csv(fold_csv_path, index=False)
    missed_df.to_csv(missed_top_csv_path, index=False)
    industry_df.to_csv(industry_csv_path, index=False)
    _write_report(
        report_md_path,
        fold_df=fold_df,
        daily_df=daily_df,
        missed_df=missed_df,
        industry_df=industry_df,
        benchmark_symbol=symbol,
        context_label=context_label,
        top_n=top_n,
        db_path=db_path,
        holdings_path=holdings_path,
        daily_exposure_path=daily_exposure_path,
        candidate_folds_path=candidate_folds_path,
        market_context_path=market_context_path,
        weight_date_lag_days=weight_date_lag_days,
    )
    _write_run_log(
        run_log_md_path,
        command=command,
        benchmark_symbol=symbol,
        context_label=context_label,
        top_n=top_n,
        db_path=db_path,
        output_dir=output_dir,
        holdings_path=holdings_path,
        daily_exposure_path=daily_exposure_path,
        candidate_folds_path=candidate_folds_path,
        market_context_path=market_context_path,
        weight_date_lag_days=weight_date_lag_days,
        status="ok",
    )
    return StrategyCsi300AttributionResult(
        daily_csv_path=daily_csv_path,
        fold_csv_path=fold_csv_path,
        missed_top_csv_path=missed_top_csv_path,
        industry_csv_path=industry_csv_path,
        report_md_path=report_md_path,
        run_log_md_path=run_log_md_path,
        status="ok",
        daily_rows=len(daily_df),
        fold_rows=len(fold_df),
    )


def _resolve_local_history_path(config: dict[str, Any], root: Path) -> Path:
    raw = config.get("local_history", {}) or {}
    path = Path(raw.get("path", "data/manual_history/a_share_history.sqlite"))
    return path if path.is_absolute() else root / path


def _read_required_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    return pd.read_csv(path)


def _read_optional_daily_exposure(path: Path | None) -> pd.DataFrame | None:
    if path is None:
        return None
    if not path.exists():
        raise FileNotFoundError(f"strategy_daily_exposure.csv not found: {path}")
    df = pd.read_csv(path)
    _require_columns(
        df,
        ["strategy_id", "walk_forward_preset", "fold", "date"],
        path,
    )
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    return df


def _read_optional_candidate_folds(path: Path | None) -> pd.DataFrame | None:
    if path is None:
        return None
    if not path.exists():
        raise FileNotFoundError(f"strategy_admission_candidate_folds.csv not found: {path}")
    df = pd.read_csv(path)
    _require_columns(
        df,
        ["strategy_id", "walk_forward_preset", "fold", "valid_start", "valid_end"],
        path,
    )
    df["fold"] = pd.to_numeric(df["fold"], errors="coerce").fillna(-1).astype(int)
    return df


def _read_optional_market_context(path: Path | None) -> pd.DataFrame | None:
    if path is None:
        return None
    if not path.exists():
        raise FileNotFoundError(f"strategy_market_context_diagnostic.csv not found: {path}")
    df = pd.read_csv(path)
    _require_columns(
        df,
        ["strategy_id", "walk_forward_preset", "fold", "market_context_label"],
        path,
    )
    df["fold"] = pd.to_numeric(df["fold"], errors="coerce").fillna(-1).astype(int)
    return df


def _require_columns(df: pd.DataFrame, columns: list[str], path: Path) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"{path} missing required columns: {', '.join(missing)}")


def _prepare_holdings(holdings: pd.DataFrame) -> pd.DataFrame:
    out = holdings.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out = out.dropna(subset=["date"]).copy()
    out["symbol"] = out["symbol"].astype(str).str.strip()
    out["industry"] = out["industry"].fillna(UNKNOWN_INDUSTRY).astype(str).replace({"": UNKNOWN_INDUSTRY})
    out["name"] = out["name"].fillna("").astype(str) if "name" in out.columns else ""
    out["live_weight"] = pd.to_numeric(out["live_weight"], errors="coerce").fillna(0.0)
    out["position_ret"] = pd.to_numeric(out["position_ret"], errors="coerce").fillna(0.0)
    out["fold"] = pd.to_numeric(out["fold"], errors="coerce").fillna(-1).astype(int)
    return out


def _empty_holdings_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "strategy_id",
            "walk_forward_preset",
            "fold",
            "valid_start",
            "valid_end",
            "market_context_label",
            "date",
            "symbol",
            "name",
            "industry",
            "live_weight",
            "position_ret",
        ]
    )


def _build_date_scaffold(
    *,
    holdings: pd.DataFrame,
    candidate_folds: pd.DataFrame | None,
    market_context: pd.DataFrame | None,
    db_path: Path,
    benchmark_symbol: str,
    context_label: str,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if not holdings.empty:
        frames.append(
            holdings[
                [
                    "strategy_id",
                    "walk_forward_preset",
                    "fold",
                    "valid_start",
                    "valid_end",
                    "market_context_label",
                    "date",
                ]
            ].drop_duplicates()
        )
    if candidate_folds is not None and not candidate_folds.empty:
        folds = candidate_folds.copy()
        keys = ["strategy_id", "walk_forward_preset", "fold"]
        if market_context is not None and not market_context.empty:
            context_cols = [
                col
                for col in [
                    "strategy_id",
                    "walk_forward_preset",
                    "fold",
                    "market_context_label",
                    "benchmark_return_bucket",
                    "benchmark_trend_bucket",
                ]
                if col in market_context.columns
            ]
            folds = folds.merge(market_context[context_cols].drop_duplicates(keys), on=keys, how="left")
        if "market_context_label" not in folds.columns:
            folds["market_context_label"] = "not_available"
        folds["market_context_label"] = folds["market_context_label"].fillna("not_available")
        if context_label and context_label != "all":
            folds = folds[folds["market_context_label"].astype(str) == str(context_label)].copy()
        frames.append(_fold_daily_scaffold(folds, db_path=db_path, benchmark_symbol=benchmark_symbol))
    if not frames:
        return pd.DataFrame()
    scaffold = pd.concat(frames, ignore_index=True)
    if scaffold.empty:
        return scaffold
    scaffold["date"] = pd.to_datetime(scaffold["date"], errors="coerce").dt.normalize()
    scaffold = scaffold.dropna(subset=["date"]).copy()
    scaffold["fold"] = pd.to_numeric(scaffold["fold"], errors="coerce").fillna(-1).astype(int)
    if context_label and context_label != "all":
        scaffold = scaffold[scaffold["market_context_label"].astype(str) == str(context_label)].copy()
    return scaffold.drop_duplicates(
        ["strategy_id", "walk_forward_preset", "fold", "valid_start", "valid_end", "market_context_label", "date"]
    )


def _fold_daily_scaffold(folds: pd.DataFrame, *, db_path: Path, benchmark_symbol: str) -> pd.DataFrame:
    if folds.empty:
        return pd.DataFrame()
    valid_starts = pd.to_datetime(folds["valid_start"], errors="coerce").dropna()
    valid_ends = pd.to_datetime(folds["valid_end"], errors="coerce").dropna()
    if valid_starts.empty or valid_ends.empty:
        return pd.DataFrame()
    trading_days = _load_benchmark_trading_days(
        db_path=db_path,
        benchmark_symbol=benchmark_symbol,
        start=valid_starts.min().normalize(),
        end=valid_ends.max().normalize(),
    )
    if trading_days.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for _, fold in folds.iterrows():
        start = pd.to_datetime(fold.get("valid_start"), errors="coerce")
        end = pd.to_datetime(fold.get("valid_end"), errors="coerce")
        if pd.isna(start) or pd.isna(end):
            continue
        dates = trading_days[(trading_days >= start.normalize()) & (trading_days <= end.normalize())]
        for trade_date in dates:
            rows.append(
                {
                    "strategy_id": str(fold.get("strategy_id", "")),
                    "walk_forward_preset": str(fold.get("walk_forward_preset", "")),
                    "fold": int(fold.get("fold", -1)),
                    "valid_start": str(fold.get("valid_start", "")),
                    "valid_end": str(fold.get("valid_end", "")),
                    "market_context_label": str(fold.get("market_context_label", "not_available")),
                    "date": pd.Timestamp(trade_date).normalize(),
                }
            )
    return pd.DataFrame(rows)


def _load_benchmark_trading_days(
    *,
    db_path: Path,
    benchmark_symbol: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.Series:
    if not db_path.exists():
        return pd.Series(dtype="datetime64[ns]")
    with sqlite3.connect(db_path) as conn:
        if not _table_exists(conn, "market_index_bars"):
            return pd.Series(dtype="datetime64[ns]")
        columns = _table_columns(conn, "market_index_bars")
        frequency_filter = "AND frequency = 'daily'" if "frequency" in columns else ""
        rows = pd.read_sql_query(
            f"""
            SELECT DISTINCT date
            FROM market_index_bars
            WHERE symbol = ?
              {frequency_filter}
              AND date >= ?
              AND date <= ?
            ORDER BY date
            """,
            conn,
            params=(benchmark_symbol, start.date().isoformat(), end.date().isoformat()),
        )
    if rows.empty:
        return pd.Series(dtype="datetime64[ns]")
    return pd.to_datetime(rows["date"], errors="coerce").dropna().dt.normalize()


def _safe_identifier(value: str) -> str:
    if not value.replace("_", "").isalnum() or value[0].isdigit():
        raise ValueError(f"Unsafe SQL identifier: {value}")
    return value


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?", (table,)).fetchone())


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    safe = _safe_identifier(table)
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({safe})").fetchall()}


def _load_benchmark_weights(*, db_path: Path, benchmark_symbol: str, max_date: pd.Timestamp) -> pd.DataFrame:
    if not db_path.exists():
        raise ValueError(f"local history sqlite not found: {db_path}")
    with sqlite3.connect(db_path) as conn:
        if not _table_exists(conn, "cn_index_weights_asof"):
            raise ValueError("missing table cn_index_weights_asof")
        columns = _table_columns(conn, "cn_index_weights_asof")
        missing = {"index_code", "trade_date", "symbol", "weight"} - columns
        if missing:
            raise ValueError("cn_index_weights_asof missing columns: " + ",".join(sorted(missing)))
        query_cols = ["index_code", "trade_date", "symbol", "weight"]
        for optional in ["effective_date", "asof_time", "source"]:
            if optional in columns:
                query_cols.append(optional)
        safe = _safe_identifier("cn_index_weights_asof")
        df = pd.read_sql_query(
            f"""
            SELECT {", ".join(query_cols)}
            FROM {safe}
            WHERE index_code = ?
              AND trade_date <= ?
            ORDER BY trade_date, weight DESC, symbol
            """,
            conn,
            params=(benchmark_symbol, max_date.date().isoformat()),
        )
        meta = _load_stock_metadata(conn)
    if df.empty:
        raise ValueError(f"cn_index_weights_asof has no rows for {benchmark_symbol} before {max_date.date()}")
    df["trade_date_dt"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.normalize()
    df = df.dropna(subset=["trade_date_dt"]).copy()
    df["symbol"] = df["symbol"].astype(str).str.strip()
    df["benchmark_weight"] = pd.to_numeric(df["weight"], errors="coerce").fillna(0.0)
    sums = df.groupby("trade_date_dt")["benchmark_weight"].transform("sum")
    divisor = np.where(sums > 2.0, 100.0, 1.0)
    df["benchmark_weight"] = df["benchmark_weight"] / divisor
    df = df.merge(meta, on="symbol", how="left")
    df["benchmark_name"] = df["benchmark_name"].fillna("")
    df["benchmark_industry"] = df["benchmark_industry"].fillna(UNKNOWN_INDUSTRY).replace({"": UNKNOWN_INDUSTRY})
    df["benchmark_rank"] = df.groupby("trade_date_dt")["benchmark_weight"].rank(method="first", ascending=False).astype(int)
    return df


def _load_stock_metadata(conn: sqlite3.Connection) -> pd.DataFrame:
    if not _table_exists(conn, "market_stocks"):
        return pd.DataFrame({"symbol": [], "benchmark_name": [], "benchmark_industry": []})
    columns = _table_columns(conn, "market_stocks")
    if "symbol" not in columns:
        return pd.DataFrame({"symbol": [], "benchmark_name": [], "benchmark_industry": []})
    name_expr = "name" if "name" in columns else "''"
    industry_expr = "industry" if "industry" in columns else "''"
    market_filter = "WHERE market = 'CN'" if "market" in columns else ""
    return pd.read_sql_query(
        f"""
        SELECT symbol, {name_expr} AS benchmark_name, {industry_expr} AS benchmark_industry
        FROM market_stocks
        {market_filter}
        """,
        conn,
    )


def _asof_weight_date_map(
    dates: pd.Series,
    weight_dates: pd.Series,
    *,
    lag_days: int = 1,
) -> dict[pd.Timestamp, pd.Timestamp | None]:
    unique_dates = pd.DataFrame({"date": sorted(pd.to_datetime(dates).dropna().dt.normalize().unique())})
    unique_weight_dates = pd.DataFrame({"benchmark_weight_date": sorted(pd.to_datetime(weight_dates).dropna().unique())})
    if unique_dates.empty or unique_weight_dates.empty:
        return {}
    unique_dates["lookup_date"] = unique_dates["date"] - pd.to_timedelta(max(0, int(lag_days)), unit="D")
    merged = pd.merge_asof(
        unique_dates,
        unique_weight_dates,
        left_on="lookup_date",
        right_on="benchmark_weight_date",
        direction="backward",
    )
    return {pd.Timestamp(row["date"]): row["benchmark_weight_date"] for _, row in merged.iterrows()}


def _benchmark_return_lookup(
    *,
    db_path: Path,
    benchmark_symbol: str,
    dates: pd.Series,
) -> dict[pd.Timestamp, float]:
    parsed = pd.to_datetime(dates, errors="coerce").dropna()
    if parsed.empty or not db_path.exists():
        return {}
    with sqlite3.connect(db_path) as conn:
        if not _table_exists(conn, "market_index_bars"):
            return {}
        columns = _table_columns(conn, "market_index_bars")
        frequency_filter = "AND frequency = 'daily'" if "frequency" in columns else ""
        start_date = (parsed.min().normalize() - pd.Timedelta(days=10)).date().isoformat()
        df = pd.read_sql_query(
            f"""
            SELECT date, close
            FROM market_index_bars
            WHERE symbol = ?
              {frequency_filter}
              AND date >= ?
              AND date <= ?
            ORDER BY date
            """,
            conn,
            params=(
                benchmark_symbol,
                start_date,
                parsed.max().date().isoformat(),
            ),
        )
    if df.empty:
        return {}
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["date", "close"]).sort_values("date")
    df["benchmark_daily_return"] = df["close"].pct_change()
    return {pd.Timestamp(row["date"]): _optional_float(row["benchmark_daily_return"]) for _, row in df.iterrows()}


def _holdings_lookup(holdings: pd.DataFrame) -> dict[tuple[str, str, int, pd.Timestamp], pd.DataFrame]:
    if holdings.empty:
        return {}
    out: dict[tuple[str, str, int, pd.Timestamp], pd.DataFrame] = {}
    group_keys = ["strategy_id", "walk_forward_preset", "fold", "date"]
    for key, group in holdings.groupby(group_keys, dropna=False, sort=True):
        strategy_id, preset, fold, date_value = key
        out[(str(strategy_id), str(preset), int(fold), pd.Timestamp(date_value).normalize())] = group.copy()
    return out


def _lookup_key(row_key: dict[str, Any]) -> tuple[str, str, int, pd.Timestamp]:
    return (
        str(row_key.get("strategy_id", "")),
        str(row_key.get("walk_forward_preset", "")),
        int(row_key.get("fold", -1)),
        pd.Timestamp(row_key.get("date")).normalize(),
    )


def _row_key_from_series(row: pd.Series) -> dict[str, Any]:
    return {
        "strategy_id": str(row.get("strategy_id", "")),
        "walk_forward_preset": str(row.get("walk_forward_preset", "")),
        "fold": int(row.get("fold", -1)),
        "valid_start": str(row.get("valid_start", "")),
        "valid_end": str(row.get("valid_end", "")),
        "market_context_label": str(row.get("market_context_label", "not_available")),
        "date": pd.Timestamp(row.get("date")).normalize(),
    }


def _daily_exposure_lookup(daily_exposure: pd.DataFrame | None) -> dict[tuple[str, str, int, pd.Timestamp], dict[str, Any]]:
    if daily_exposure is None or daily_exposure.empty:
        return {}
    lookup: dict[tuple[str, str, int, pd.Timestamp], dict[str, Any]] = {}
    for _, row in daily_exposure.iterrows():
        date = pd.Timestamp(row["date"]).normalize()
        lookup[
            (
                str(row.get("strategy_id", "")),
                str(row.get("walk_forward_preset", "")),
                int(row.get("fold", -1)),
                date,
            )
        ] = row.to_dict()
    return lookup


def _daily_key_dict(keys: list[str], value: Any) -> dict[str, Any]:
    if not isinstance(value, tuple):
        value = (value,)
    out = {key: item for key, item in zip(keys, value)}
    out["date"] = pd.Timestamp(out["date"]).normalize()
    out["fold"] = int(out["fold"])
    return out


def _attribute_one_day(
    *,
    row_key: dict[str, Any],
    holdings: pd.DataFrame,
    benchmark: pd.DataFrame,
    benchmark_symbol: str,
    benchmark_weight_date: pd.Timestamp,
    exposure_row: dict[str, Any],
    top_n: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    live = holdings[holdings["live_weight"] > EPS].copy()
    live_by_symbol = _live_symbol_weights(live)
    live_exposure = float(live_by_symbol["strategy_live_weight"].sum()) if not live_by_symbol.empty else 0.0
    strategy_position_return = float(pd.to_numeric(holdings["position_ret"], errors="coerce").fillna(0.0).sum())

    merged = live_by_symbol.merge(
        benchmark[["symbol", "benchmark_weight", "benchmark_name", "benchmark_industry", "benchmark_rank"]],
        on="symbol",
        how="left",
    )
    in_benchmark_mask = merged["benchmark_weight"].notna()
    strategy_weight_in_benchmark = float(merged.loc[in_benchmark_mask, "strategy_live_weight"].sum()) if not merged.empty else 0.0
    strategy_weight_outside_benchmark = max(live_exposure - strategy_weight_in_benchmark, 0.0)
    benchmark_weight_held = float(merged["benchmark_weight"].fillna(0.0).sum()) if not merged.empty else 0.0
    top = benchmark.sort_values(["benchmark_weight", "symbol"], ascending=[False, True]).head(int(top_n)).copy()
    held_symbols = set(live_by_symbol["symbol"].astype(str).tolist())
    top["held_by_strategy"] = top["symbol"].astype(str).isin(held_symbols)
    top_weight_total = float(top["benchmark_weight"].sum())
    top_weight_held = float(top.loc[top["held_by_strategy"], "benchmark_weight"].sum())
    top_weight_missed = max(top_weight_total - top_weight_held, 0.0)
    top_coverage_ratio = top_weight_held / top_weight_total if top_weight_total > EPS else np.nan
    industry_detail, industry_metrics = _industry_active_weights(
        row_key=row_key,
        live_by_symbol=live_by_symbol,
        benchmark=benchmark,
        live_exposure=live_exposure,
        benchmark_symbol=benchmark_symbol,
        benchmark_weight_date=benchmark_weight_date,
    )
    benchmark_return = _optional_float(exposure_row.get("benchmark_daily_return"))
    strategy_excess_daily_return = (
        strategy_position_return - benchmark_return if not np.isnan(benchmark_return) else np.nan
    )
    daily = {
        **_base_daily_fields(row_key),
        "benchmark_symbol": benchmark_symbol,
        "benchmark_weight_date": benchmark_weight_date,
        "asof_status": "available",
        "benchmark_constituent_count": int(len(benchmark)),
        "benchmark_weight_sum": float(benchmark["benchmark_weight"].sum()),
        "strategy_live_exposure": live_exposure,
        "reported_live_exposure": _optional_float(exposure_row.get("live_exposure")),
        "strategy_live_holding_count": int(len(live_by_symbol)),
        "strategy_position_return": strategy_position_return,
        "benchmark_daily_return": benchmark_return,
        "strategy_excess_daily_return": strategy_excess_daily_return,
        "strategy_weight_in_benchmark": strategy_weight_in_benchmark,
        "strategy_weight_outside_benchmark": strategy_weight_outside_benchmark,
        "benchmark_weight_held_by_strategy": benchmark_weight_held,
        "benchmark_weight_missed_by_strategy": max(1.0 - benchmark_weight_held, 0.0),
        "benchmark_top_n": int(top_n),
        "benchmark_top_n_weight_total": top_weight_total,
        "benchmark_top_n_weight_held": top_weight_held,
        "benchmark_top_n_weight_missed": top_weight_missed,
        "benchmark_top_n_coverage_ratio": top_coverage_ratio,
        "constituent_overlap_count": int(in_benchmark_mask.sum()),
        "outside_benchmark_count": int((~in_benchmark_mask).sum()) if not merged.empty else 0,
        **industry_metrics,
    }
    missed_rows = []
    for _, missed in top[~top["held_by_strategy"]].iterrows():
        missed_rows.append(
            {
                **_base_daily_fields(row_key),
                "benchmark_symbol": benchmark_symbol,
                "benchmark_weight_date": benchmark_weight_date,
                "benchmark_rank": int(missed.get("benchmark_rank", 0)),
                "symbol": str(missed.get("symbol", "")),
                "name": str(missed.get("benchmark_name", "")),
                "industry": str(missed.get("benchmark_industry", UNKNOWN_INDUSTRY) or UNKNOWN_INDUSTRY),
                "benchmark_weight": float(missed.get("benchmark_weight", 0.0)),
                "top_n_parameter": int(top_n),
            }
        )
    return daily, missed_rows, industry_detail


def _live_symbol_weights(live: pd.DataFrame) -> pd.DataFrame:
    if live.empty:
        return pd.DataFrame(columns=["symbol", "strategy_live_weight", "strategy_name", "strategy_industry"])
    return (
        live.groupby("symbol", as_index=False)
        .agg(
            strategy_live_weight=("live_weight", "sum"),
            strategy_name=("name", "first"),
            strategy_industry=("industry", "first"),
        )
        .assign(strategy_industry=lambda d: d["strategy_industry"].fillna(UNKNOWN_INDUSTRY).replace({"": UNKNOWN_INDUSTRY}))
    )


def _industry_active_weights(
    *,
    row_key: dict[str, Any],
    live_by_symbol: pd.DataFrame,
    benchmark: pd.DataFrame,
    live_exposure: float,
    benchmark_symbol: str,
    benchmark_weight_date: pd.Timestamp,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    strategy_industry = (
        live_by_symbol.groupby("strategy_industry", as_index=True)["strategy_live_weight"].sum()
        if not live_by_symbol.empty
        else pd.Series(dtype=float)
    )
    benchmark_industry = benchmark.groupby("benchmark_industry", as_index=True)["benchmark_weight"].sum()
    industries = sorted(set(strategy_industry.index.astype(str)).union(set(benchmark_industry.index.astype(str))))
    rows: list[dict[str, Any]] = []
    raw_active_values: list[float] = []
    normalized_active_values: list[float] = []
    for industry in industries:
        strategy_raw = float(strategy_industry.get(industry, 0.0))
        strategy_norm = strategy_raw / live_exposure if live_exposure > EPS else np.nan
        benchmark_weight = float(benchmark_industry.get(industry, 0.0))
        raw_active = strategy_raw - benchmark_weight
        normalized_active = strategy_norm - benchmark_weight if not np.isnan(strategy_norm) else np.nan
        raw_active_values.append(raw_active)
        if not np.isnan(normalized_active):
            normalized_active_values.append(normalized_active)
        rows.append(
            {
                **_base_daily_fields(row_key),
                "benchmark_symbol": benchmark_symbol,
                "benchmark_weight_date": benchmark_weight_date,
                "industry": industry,
                "strategy_industry_weight_raw": strategy_raw,
                "strategy_industry_weight_normalized": strategy_norm,
                "benchmark_industry_weight": benchmark_weight,
                "raw_active_weight": raw_active,
                "normalized_active_weight": normalized_active,
            }
        )
    top_under = min(rows, key=lambda item: item["raw_active_weight"]) if rows else {}
    top_over = max(rows, key=lambda item: item["raw_active_weight"]) if rows else {}
    return rows, {
        "industry_l1_gap_raw": float(sum(abs(value) for value in raw_active_values)),
        "industry_l1_gap_normalized": float(sum(abs(value) for value in normalized_active_values))
        if normalized_active_values
        else np.nan,
        "top_industry_underweight": str(top_under.get("industry", "")),
        "top_industry_underweight_value": _optional_float(top_under.get("raw_active_weight")),
        "top_industry_overweight": str(top_over.get("industry", "")),
        "top_industry_overweight_value": _optional_float(top_over.get("raw_active_weight")),
    }


def _base_daily_fields(row_key: dict[str, Any]) -> dict[str, Any]:
    return {
        "strategy_id": str(row_key.get("strategy_id", "")),
        "walk_forward_preset": str(row_key.get("walk_forward_preset", "")),
        "fold": int(row_key.get("fold", -1)),
        "valid_start": str(row_key.get("valid_start", "")),
        "valid_end": str(row_key.get("valid_end", "")),
        "market_context_label": str(row_key.get("market_context_label", "")),
        "date": pd.Timestamp(row_key.get("date")).normalize(),
    }


def _insufficient_daily_row(row_key: dict[str, Any], exposure_row: dict[str, Any], benchmark_symbol: str) -> dict[str, Any]:
    return {
        **_base_daily_fields(row_key),
        "benchmark_symbol": benchmark_symbol,
        "benchmark_weight_date": "",
        "asof_status": "insufficient_asof_history",
        "benchmark_constituent_count": 0,
        "benchmark_weight_sum": np.nan,
        "strategy_live_exposure": _optional_float(exposure_row.get("live_exposure")),
        "reported_live_exposure": _optional_float(exposure_row.get("live_exposure")),
        "strategy_live_holding_count": _optional_int(exposure_row.get("live_holding_count")),
        "strategy_position_return": np.nan,
        "benchmark_daily_return": _optional_float(exposure_row.get("benchmark_daily_return")),
        "strategy_excess_daily_return": np.nan,
        "strategy_weight_in_benchmark": np.nan,
        "strategy_weight_outside_benchmark": np.nan,
        "benchmark_weight_held_by_strategy": np.nan,
        "benchmark_weight_missed_by_strategy": np.nan,
        "benchmark_top_n": np.nan,
        "benchmark_top_n_weight_total": np.nan,
        "benchmark_top_n_weight_held": np.nan,
        "benchmark_top_n_weight_missed": np.nan,
        "benchmark_top_n_coverage_ratio": np.nan,
        "constituent_overlap_count": 0,
        "outside_benchmark_count": 0,
        "industry_l1_gap_raw": np.nan,
        "industry_l1_gap_normalized": np.nan,
        "top_industry_underweight": "",
        "top_industry_underweight_value": np.nan,
        "top_industry_overweight": "",
        "top_industry_overweight_value": np.nan,
    }


def _fold_summary(daily_df: pd.DataFrame) -> pd.DataFrame:
    if daily_df.empty:
        return pd.DataFrame()
    keys = ["strategy_id", "walk_forward_preset", "fold", "valid_start", "valid_end", "market_context_label"]
    rows: list[dict[str, Any]] = []
    for key, group in daily_df.groupby(keys, dropna=False, sort=True):
        row = {name: value for name, value in zip(keys, key)}
        available = group[group["asof_status"] == "available"].copy()
        strategy_returns = pd.to_numeric(available.get("strategy_position_return", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
        benchmark_returns = pd.to_numeric(available.get("benchmark_daily_return", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
        strategy_total = _compound_return(strategy_returns)
        benchmark_total = _compound_return(benchmark_returns)
        row.update(
            {
                "days": int(len(group)),
                "available_days": int(len(available)),
                "asof_coverage_ratio": float(len(available) / len(group)) if len(group) else 0.0,
                "avg_live_exposure": _mean(available, "strategy_live_exposure"),
                "avg_strategy_weight_in_benchmark": _mean(available, "strategy_weight_in_benchmark"),
                "avg_strategy_weight_outside_benchmark": _mean(available, "strategy_weight_outside_benchmark"),
                "avg_benchmark_weight_held": _mean(available, "benchmark_weight_held_by_strategy"),
                "avg_benchmark_weight_missed": _mean(available, "benchmark_weight_missed_by_strategy"),
                "avg_top_n_coverage_ratio": _mean(available, "benchmark_top_n_coverage_ratio"),
                "avg_top_n_weight_missed": _mean(available, "benchmark_top_n_weight_missed"),
                "avg_industry_l1_gap_raw": _mean(available, "industry_l1_gap_raw"),
                "avg_industry_l1_gap_normalized": _mean(available, "industry_l1_gap_normalized"),
                "strategy_total_return": strategy_total,
                "benchmark_total_return": benchmark_total,
                "excess_total_return": strategy_total - benchmark_total,
                "strategy_annualized_return": _annualized_return(strategy_total, len(available)),
                "benchmark_annualized_return": _annualized_return(benchmark_total, len(available)),
                "primary_driver": "",
                "plain_language_summary": "",
            }
        )
        row["primary_driver"] = _primary_driver(row)
        row["plain_language_summary"] = _plain_language_summary(row)
        rows.append(row)
    return pd.DataFrame(rows)


def _missed_top_summary(missed_df: pd.DataFrame) -> pd.DataFrame:
    if missed_df.empty:
        return pd.DataFrame()
    keys = [
        "strategy_id",
        "walk_forward_preset",
        "fold",
        "valid_start",
        "valid_end",
        "market_context_label",
        "benchmark_symbol",
        "symbol",
        "name",
        "industry",
    ]
    out = (
        missed_df.groupby(keys, dropna=False, as_index=False)
        .agg(
            missed_days=("date", "nunique"),
            avg_benchmark_weight=("benchmark_weight", "mean"),
            max_benchmark_weight=("benchmark_weight", "max"),
            avg_benchmark_rank=("benchmark_rank", "mean"),
            first_missing_date=("date", "min"),
            last_missing_date=("date", "max"),
            top_n_parameter=("top_n_parameter", "max"),
        )
        .sort_values(["fold", "avg_benchmark_weight", "missed_days"], ascending=[True, False, False])
    )
    return out


def _primary_driver(row: dict[str, Any]) -> str:
    if float(row.get("asof_coverage_ratio", 0.0) or 0.0) < 0.95:
        return "asof_data_gap"
    if float(row.get("avg_live_exposure", 0.0) or 0.0) < 0.65:
        return "low_participation"
    if float(row.get("avg_top_n_coverage_ratio", 0.0) or 0.0) < 0.20:
        return "top_weight_constituent_omission"
    if float(row.get("avg_industry_l1_gap_normalized", 0.0) or 0.0) > 0.80:
        return "industry_mismatch"
    if float(row.get("excess_total_return", 0.0) or 0.0) < 0.0:
        return "selection_or_signal_lag"
    return "no_clear_lag_driver"


def _plain_language_summary(row: dict[str, Any]) -> str:
    driver = str(row.get("primary_driver", ""))
    if driver == "low_participation":
        return "强沪深300阶段主要问题是仓位参与不足，策略没有充分吃到指数上涨。"
    if driver == "top_weight_constituent_omission":
        return "强沪深300阶段主要问题是高权重成分覆盖不足，指数上涨由部分大权重股推动时策略跟不上。"
    if driver == "industry_mismatch":
        return "强沪深300阶段主要问题是行业结构偏离，持仓行业和沪深300权重结构差异较大。"
    if driver == "selection_or_signal_lag":
        return "仓位和覆盖并非唯一解释，剩余问题更像是个股选择或信号响应不足。"
    if driver == "asof_data_gap":
        return "as-of 权重覆盖不足，不能可靠解释该折。"
    return "该折没有识别出单一明确跑输原因。"


def _mean(df: pd.DataFrame, column: str) -> float:
    if df.empty or column not in df.columns:
        return np.nan
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    return float(values.mean()) if not values.empty else np.nan


def _compound_return(values: pd.Series) -> float:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return np.nan
    return float((1.0 + clean).prod() - 1.0)


def _annualized_return(total_return: float, days: int) -> float:
    if days <= 0 or np.isnan(total_return) or total_return <= -1.0:
        return np.nan
    return float((1.0 + total_return) ** (252.0 / days) - 1.0)


def _optional_float(value: Any) -> float:
    try:
        if value is None:
            return np.nan
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def _optional_int(value: Any) -> int:
    try:
        if value is None or pd.isna(value):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _format_dates_for_csv(df: pd.DataFrame) -> None:
    if df.empty:
        return
    for column in ["date", "benchmark_weight_date", "first_missing_date", "last_missing_date"]:
        if column in df.columns:
            parsed = pd.to_datetime(df[column], errors="coerce")
            df[column] = parsed.dt.strftime("%Y-%m-%d").fillna(df[column].astype(str))


def _write_blocked_outputs(
    *,
    daily_csv_path: Path,
    fold_csv_path: Path,
    missed_top_csv_path: Path,
    industry_csv_path: Path,
    report_md_path: Path,
    run_log_md_path: Path,
    status: str,
    reason: str,
    benchmark_symbol: str,
    db_path: Path,
    holdings_path: Path | None,
    daily_exposure_path: Path | None,
    candidate_folds_path: Path | None,
    market_context_path: Path | None,
    output_dir: Path,
    command: str | None,
    top_n: int,
    weight_date_lag_days: int,
    context_label: str,
) -> StrategyCsi300AttributionResult:
    blocked = pd.DataFrame([{"status": status, "reason": reason, "benchmark_symbol": benchmark_symbol}])
    blocked.to_csv(daily_csv_path, index=False)
    pd.DataFrame().to_csv(fold_csv_path, index=False)
    pd.DataFrame().to_csv(missed_top_csv_path, index=False)
    pd.DataFrame().to_csv(industry_csv_path, index=False)
    report_md_path.write_text(
        "\n".join(
            [
                "# 沪深300权重归因报告",
                "",
                f"- 状态：`{status}`",
                f"- 原因：{reason}",
                f"- 基准：`{benchmark_symbol}`",
                f"- 本地历史库：`{db_path}`",
                "",
                "本报告没有生成策略结论。缺少必要 as-of 数据或输入行时，继续计算会带来未来函数或误读风险。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _write_run_log(
        run_log_md_path,
        command=command,
        benchmark_symbol=benchmark_symbol,
        context_label=context_label,
        top_n=top_n,
        weight_date_lag_days=weight_date_lag_days,
        db_path=db_path,
        output_dir=output_dir,
        holdings_path=holdings_path,
        daily_exposure_path=daily_exposure_path,
        candidate_folds_path=candidate_folds_path,
        market_context_path=market_context_path,
        status=status,
    )
    return StrategyCsi300AttributionResult(
        daily_csv_path=daily_csv_path,
        fold_csv_path=fold_csv_path,
        missed_top_csv_path=missed_top_csv_path,
        industry_csv_path=industry_csv_path,
        report_md_path=report_md_path,
        run_log_md_path=run_log_md_path,
        status=status,
        daily_rows=0,
        fold_rows=0,
    )


def _write_report(
    path: Path,
    *,
    fold_df: pd.DataFrame,
    daily_df: pd.DataFrame,
    missed_df: pd.DataFrame,
    industry_df: pd.DataFrame,
    benchmark_symbol: str,
    context_label: str,
    top_n: int,
    db_path: Path,
    holdings_path: Path | None,
    daily_exposure_path: Path | None,
    candidate_folds_path: Path | None,
    market_context_path: Path | None,
    weight_date_lag_days: int,
) -> None:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# 沪深300权重归因报告",
        "",
        "本报告是 research-only 诊断，用来解释策略在强沪深300阶段跑输时，问题更接近仓位参与不足、高权重成分遗漏、行业结构偏离，还是持仓选择不足。",
        "",
        "## 运行口径",
        "",
        f"- 生成时间：{generated_at}",
        f"- 基准：`{benchmark_symbol}`",
        f"- 过滤市场状态：`{context_label}`",
        f"- 高权重成分检查范围：沪深300权重前 {top_n}",
        f"- 本地历史库：`{db_path}`",
        f"- 持仓输入：`{holdings_path}`",
        f"- 日度暴露输入：`{daily_exposure_path}`" if daily_exposure_path else "- 日度暴露输入：未提供",
        f"- 候选折输入：`{candidate_folds_path}`" if candidate_folds_path else "- 候选折输入：未提供",
        f"- 市场状态输入：`{market_context_path}`" if market_context_path else "- 市场状态输入：未提供",
        f"- 权重日期保守滞后：`{weight_date_lag_days}` 天",
        "",
        "权重使用规则：每个持仓日默认只使用 `cn_index_weights_asof.trade_date <= date - 1 day` 的最近一条记录；这是按日线研究归因的保守可见性口径。`asof_time` 仍是治理代理字段，不代表盘中真实发布时间。",
        "",
        "## 折级结论",
        "",
    ]
    if fold_df.empty:
        lines.append("没有可用折级结果。")
    else:
        show_cols = [
            "strategy_id",
            "walk_forward_preset",
            "fold",
            "days",
            "avg_live_exposure",
            "avg_benchmark_weight_held",
            "avg_top_n_coverage_ratio",
            "avg_industry_l1_gap_normalized",
            "excess_total_return",
            "primary_driver",
            "plain_language_summary",
        ]
        lines.extend(_markdown_table(fold_df[show_cols].head(20)))
    lines.extend(["", "## 最常遗漏的沪深300高权重成分", ""])
    if missed_df.empty:
        lines.append("没有遗漏高权重成分记录。")
    else:
        show_cols = [
            "strategy_id",
            "fold",
            "symbol",
            "name",
            "industry",
            "missed_days",
            "avg_benchmark_weight",
            "avg_benchmark_rank",
        ]
        lines.extend(_markdown_table(missed_df[show_cols].head(30)))
    lines.extend(["", "## 风险说明", ""])
    lines.extend(
        [
            "- 这不是交易建议，也不改变 admission 结论。",
            "- 归因使用日线持仓和日线基准权重，只解释已发生研究样本，不提供盘中择时能力。",
            "- 如果策略本身不是指数增强策略，低沪深300覆盖不一定是错误；它只说明强指数行情下跟随基准上涨的能力不足。",
            f"- 日度归因行数：{len(daily_df)}；行业主动权重行数：{len(industry_df)}。",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_run_log(
    path: Path,
    *,
    command: str | None,
    benchmark_symbol: str,
    context_label: str,
    top_n: int,
    weight_date_lag_days: int,
    db_path: Path,
    output_dir: Path,
    holdings_path: Path | None,
    daily_exposure_path: Path | None,
    candidate_folds_path: Path | None,
    market_context_path: Path | None,
    status: str,
) -> None:
    lines = [
        "# Strategy CSI300 Attribution Run Log",
        "",
        f"- generated_at: {datetime.now().isoformat(timespec='seconds')}",
        f"- status: {status}",
        f"- command: `{command or ''}`",
        f"- benchmark_symbol: `{benchmark_symbol}`",
        f"- context_label: `{context_label}`",
        f"- top_n: {top_n}",
        f"- weight_date_lag_days: {weight_date_lag_days}",
        f"- local_history_db: `{db_path}`",
        f"- holdings_path: `{holdings_path}`",
        f"- daily_exposure_path: `{daily_exposure_path}`" if daily_exposure_path else "- daily_exposure_path: ``",
        f"- candidate_folds_path: `{candidate_folds_path}`" if candidate_folds_path else "- candidate_folds_path: ``",
        f"- market_context_path: `{market_context_path}`" if market_context_path else "- market_context_path: ``",
        f"- output_dir: `{output_dir}`",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _markdown_table(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return ["（无记录）"]
    clean = df.copy()
    for col in clean.columns:
        if pd.api.types.is_float_dtype(clean[col]):
            clean[col] = clean[col].map(lambda value: "" if pd.isna(value) else f"{float(value):.4f}")
    headers = list(clean.columns)
    rows = [[str(value) for value in row] for row in clean.itertuples(index=False, name=None)]
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
        *["| " + " | ".join(row) + " |" for row in rows],
    ]
