from __future__ import annotations

import copy
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from quant.data_governance.external_market_history import configure_us_market_history
from quant.data_access.local_history import configure_local_history, load_daily_from_local_history, local_history_path
from quant.data_access.throttle import configure_akshare_throttle
from quant.walk_forward import (
    _effective_history_years,
    _load_cross_market_features,
    _resolve_walk_forward_window,
    _strict_qfq_asof_enabled,
    _xmarket_enabled,
    iter_point_in_time_universe_folds,
)


@dataclass(frozen=True)
class StrategyCoreReachabilityResult:
    daily_csv_path: Path
    fold_summary_csv_path: Path
    failure_reason_csv_path: Path
    report_md_path: Path
    run_log_md_path: Path
    daily_rows: int
    fold_rows: int
    status: str


def run_strategy_core_reachability_diagnostic(
    *,
    config: dict[str, Any],
    root: Path,
    config_path: Path | None,
    candidate_folds_path: Path,
    output_dir: Path,
    benchmark_symbol: str | None = None,
    presets: list[str] | None = None,
    folds: list[int] | None = None,
    core_top_n: int = 60,
    core_cumulative_weight: float = 0.60,
    top_n: int = 20,
    min_amount: float = 0.0,
    min_amount_ratio20: float = 0.0,
    weight_date_lag_days: int = 1,
    seed_benchmark_core: bool = False,
    seed_top_n: int | None = None,
    seed_core_top_n: int | None = None,
    seed_core_cumulative_weight: float | None = None,
    command: str | None = None,
) -> StrategyCoreReachabilityResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    configure_local_history(config.get("local_history", {}), root)
    configure_us_market_history(config.get("us_market_history", {}), root)
    configure_akshare_throttle(config.get("data_sources", {}).get("akshare", {}))

    candidate_folds = _read_required_csv(candidate_folds_path, "strategy_admission_candidate_folds.csv")
    _require_columns(candidate_folds, ["walk_forward_preset", "fold", "valid_start", "valid_end"], candidate_folds_path)
    selected = candidate_folds.copy()
    if presets:
        selected = selected[selected["walk_forward_preset"].astype(str).isin({str(item) for item in presets})].copy()
    if folds:
        selected = selected[selected["fold"].astype(int).isin({int(item) for item in folds})].copy()
    if selected.empty:
        raise ValueError("no candidate folds selected for strategy-core-reachability-diagnostic")

    if not _strict_qfq_asof_enabled(config):
        raise ValueError("strategy-core-reachability-diagnostic requires qfq_asof price mode")

    benchmark = benchmark_symbol or str(config.get("benchmark_symbol") or "SH.000300")
    db_path = local_history_path()
    max_valid_date = pd.to_datetime(selected["valid_end"], errors="coerce").dropna().max()
    if pd.isna(max_valid_date):
        raise ValueError("candidate folds have no valid_end date")
    benchmark_weights = _load_benchmark_weights(db_path=db_path, benchmark_symbol=benchmark, max_date=pd.Timestamp(max_valid_date))

    daily_frames: list[pd.DataFrame] = []
    reason_frames: list[pd.DataFrame] = []
    for preset_name in _ordered_presets(selected):
        scoped_config = copy.deepcopy(config)
        scoped_config.setdefault("walk_forward", {})["preset_name"] = preset_name
        wcfg = scoped_config["walk_forward"]
        strategy_cfg = wcfg.get("strategy_v2", {})
        window_cfg = _resolve_walk_forward_window(wcfg)
        years = _effective_history_years(int(scoped_config["years"]), window_cfg)
        target_folds = {
            int(value)
            for value in selected.loc[selected["walk_forward_preset"].astype(str) == str(preset_name), "fold"].tolist()
        }
        contexts, _audit = iter_point_in_time_universe_folds(
            scoped_config,
            years=years,
            train_years=int(window_cfg["train_years"]),
            validate_years=int(window_cfg["validate_years"]),
            min_samples=int(wcfg["min_samples"]),
            strategy_cfg=strategy_cfg,
            xfeatures=_load_cross_market_features(years, strategy_cfg.get("cross_market", {})) if _xmarket_enabled(strategy_cfg) else None,
            window_cfg=window_cfg,
            include_folds=target_folds,
        )
        for fold_context in contexts:
            fold = int(fold_context["fold"])
            fold_candidate = selected[
                (selected["walk_forward_preset"].astype(str) == str(preset_name))
                & (selected["fold"].astype(int) == fold)
            ].iloc[0]
            daily, reasons = _diagnose_fold(
                panel=_seed_benchmark_panel(
                    panel=fold_context["valid"],
                    candidate_row=fold_candidate,
                    benchmark_weights=benchmark_weights,
                    years=years,
                    strategy_cfg=strategy_cfg,
                    seed_benchmark_core=seed_benchmark_core,
                    seed_top_n=seed_top_n if seed_top_n is not None else top_n,
                    seed_core_top_n=seed_core_top_n if seed_core_top_n is not None else core_top_n,
                    seed_core_cumulative_weight=(
                        seed_core_cumulative_weight
                        if seed_core_cumulative_weight is not None
                        else core_cumulative_weight
                    ),
                    weight_date_lag_days=weight_date_lag_days,
                ),
                candidate_row=fold_candidate,
                benchmark_weights=benchmark_weights,
                benchmark_symbol=benchmark,
                top_n=top_n,
                core_top_n=core_top_n,
                core_cumulative_weight=core_cumulative_weight,
                min_amount=min_amount,
                min_amount_ratio20=min_amount_ratio20,
                weight_date_lag_days=weight_date_lag_days,
            )
            if not daily.empty:
                daily_frames.append(daily)
            if not reasons.empty:
                reason_frames.append(reasons)

    daily_df = _concat_or_empty(daily_frames)
    reason_df = _concat_or_empty(reason_frames)
    fold_summary_df = _fold_summary(daily_df)
    status = _overall_status(fold_summary_df)

    daily_csv_path = output_dir / "strategy_core_reachability_daily.csv"
    fold_summary_csv_path = output_dir / "strategy_core_reachability_fold_summary.csv"
    failure_reason_csv_path = output_dir / "strategy_core_reachability_failure_reasons.csv"
    report_md_path = output_dir / "strategy_core_reachability_report.md"
    run_log_md_path = output_dir / "strategy_core_reachability_run_log.md"

    daily_df.to_csv(daily_csv_path, index=False)
    fold_summary_df.to_csv(fold_summary_csv_path, index=False)
    reason_df.to_csv(failure_reason_csv_path, index=False)
    _write_report(
        report_md_path,
        fold_summary_df=fold_summary_df,
        daily_df=daily_df,
        benchmark_symbol=benchmark,
        top_n=top_n,
        core_top_n=core_top_n,
        core_cumulative_weight=core_cumulative_weight,
        min_amount=min_amount,
        min_amount_ratio20=min_amount_ratio20,
        weight_date_lag_days=weight_date_lag_days,
        seed_benchmark_core=seed_benchmark_core,
        seed_top_n=seed_top_n if seed_top_n is not None else top_n,
        seed_core_top_n=seed_core_top_n if seed_core_top_n is not None else core_top_n,
        seed_core_cumulative_weight=seed_core_cumulative_weight if seed_core_cumulative_weight is not None else core_cumulative_weight,
        status=status,
    )
    _write_run_log(
        run_log_md_path,
        config_path=config_path,
        candidate_folds_path=candidate_folds_path,
        command=command,
        benchmark_symbol=benchmark,
        output_dir=output_dir,
        status=status,
    )

    return StrategyCoreReachabilityResult(
        daily_csv_path=daily_csv_path,
        fold_summary_csv_path=fold_summary_csv_path,
        failure_reason_csv_path=failure_reason_csv_path,
        report_md_path=report_md_path,
        run_log_md_path=run_log_md_path,
        daily_rows=len(daily_df),
        fold_rows=len(fold_summary_df),
        status=status,
    )


def _diagnose_fold(
    *,
    panel: pd.DataFrame,
    candidate_row: pd.Series,
    benchmark_weights: pd.DataFrame,
    benchmark_symbol: str,
    top_n: int,
    core_top_n: int,
    core_cumulative_weight: float,
    min_amount: float,
    min_amount_ratio20: float,
    weight_date_lag_days: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if panel.empty:
        return pd.DataFrame(), pd.DataFrame()
    d = panel.copy()
    d["date"] = pd.to_datetime(d["date"], errors="coerce").dt.normalize()
    d["symbol"] = d["symbol"].astype(str).str.strip()
    for col in ["close", "amount", "amount_ratio20", "volume", "ret"]:
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce")
    panel_by_date = {pd.Timestamp(date_value): day.copy() for date_value, day in d.groupby("date", sort=False)}
    weight_date_map = _asof_weight_date_map(
        pd.Series(list(panel_by_date.keys())),
        benchmark_weights["trade_date_dt"],
        lag_days=weight_date_lag_days,
    )
    weights_by_date = {pd.Timestamp(key): frame.copy() for key, frame in benchmark_weights.groupby("trade_date_dt", sort=False)}

    daily_rows: list[dict[str, Any]] = []
    reason_rows: list[dict[str, Any]] = []
    for date_value in sorted(panel_by_date):
        day = panel_by_date[pd.Timestamp(date_value)].copy()
        weight_date = weight_date_map.get(pd.Timestamp(date_value))
        if weight_date is None or pd.isna(weight_date):
            daily_rows.append(_missing_weight_row(candidate_row, benchmark_symbol, date_value))
            continue
        benchmark = weights_by_date.get(pd.Timestamp(weight_date), pd.DataFrame()).copy()
        if benchmark.empty:
            daily_rows.append(_missing_weight_row(candidate_row, benchmark_symbol, date_value, weight_date=weight_date))
            continue
        benchmark = benchmark.sort_values(["benchmark_weight", "symbol"], ascending=[False, True]).reset_index(drop=True)
        benchmark["benchmark_rank"] = np.arange(1, len(benchmark) + 1)
        core = _select_core(benchmark, core_top_n=core_top_n, core_cumulative_weight=core_cumulative_weight)
        top = benchmark.head(int(top_n)).copy()
        reachable, reasons = _reachable_core(
            core=core,
            panel_day=day,
            min_amount=min_amount,
            min_amount_ratio20=min_amount_ratio20,
        )
        reachable_symbols = set(reachable["symbol"].astype(str))
        core_weight = float(core["benchmark_weight"].sum())
        top_weight = float(top["benchmark_weight"].sum())
        reachable_core_weight = float(reachable["benchmark_weight"].sum())
        reachable_top_weight = float(top.loc[top["symbol"].astype(str).isin(reachable_symbols), "benchmark_weight"].sum())
        daily_rows.append(
            {
                "strategy_id": _safe_str(candidate_row.get("strategy_id")),
                "walk_forward_preset": _safe_str(candidate_row.get("walk_forward_preset")),
                "fold": _safe_int(candidate_row.get("fold")),
                "valid_start": _safe_str(candidate_row.get("valid_start")),
                "valid_end": _safe_str(candidate_row.get("valid_end")),
                "date": pd.Timestamp(date_value).date().isoformat(),
                "benchmark_symbol": benchmark_symbol,
                "benchmark_weight_date": pd.Timestamp(weight_date).date().isoformat(),
                "asof_status": "available",
                "benchmark_member_count": int(len(benchmark)),
                "benchmark_weight_sum": float(benchmark["benchmark_weight"].sum()),
                "core_member_count": int(len(core)),
                "core_weight_sum": core_weight,
                "reachable_core_member_count": int(len(reachable)),
                "reachable_core_weight_sum": reachable_core_weight,
                "reachable_core_weight_ratio": reachable_core_weight / core_weight if core_weight > 1e-12 else np.nan,
                "top_n": int(top_n),
                "top_n_weight_sum": top_weight,
                "reachable_top_n_member_count": int(top["symbol"].astype(str).isin(reachable_symbols).sum()),
                "reachable_top_n_weight_sum": reachable_top_weight,
                "reachable_top_n_weight_ratio": reachable_top_weight / top_weight if top_weight > 1e-12 else np.nan,
                "panel_overlap_core_member_count": int((reasons["failure_reason"] != "missing_from_pit_panel").sum()) if not reasons.empty else int(len(core)),
                "panel_overlap_core_weight_sum": _weight_for_reasons(reasons, exclude_reason="missing_from_pit_panel"),
                "min_amount": float(min_amount),
                "min_amount_ratio20": float(min_amount_ratio20),
                "core_top_n": int(core_top_n),
                "core_cumulative_weight": float(core_cumulative_weight),
            }
        )
        reason_rows.extend(
            {
                "strategy_id": _safe_str(candidate_row.get("strategy_id")),
                "walk_forward_preset": _safe_str(candidate_row.get("walk_forward_preset")),
                "fold": _safe_int(candidate_row.get("fold")),
                "date": pd.Timestamp(date_value).date().isoformat(),
                "benchmark_weight_date": pd.Timestamp(weight_date).date().isoformat(),
                "symbol": str(row["symbol"]),
                "benchmark_rank": int(row["benchmark_rank"]),
                "benchmark_weight": float(row["benchmark_weight"]),
                "failure_reason": str(row["failure_reason"]),
            }
            for _, row in reasons.iterrows()
            if str(row["failure_reason"]) != "reachable"
        )
    return pd.DataFrame(daily_rows), pd.DataFrame(reason_rows)


def _seed_benchmark_panel(
    *,
    panel: pd.DataFrame,
    candidate_row: pd.Series,
    benchmark_weights: pd.DataFrame,
    years: int,
    strategy_cfg: dict[str, Any],
    seed_benchmark_core: bool,
    seed_top_n: int,
    seed_core_top_n: int,
    seed_core_cumulative_weight: float,
    weight_date_lag_days: int,
) -> pd.DataFrame:
    if not seed_benchmark_core or panel.empty:
        return panel
    valid_start = pd.to_datetime(candidate_row.get("valid_start"), errors="coerce")
    valid_end = pd.to_datetime(candidate_row.get("valid_end"), errors="coerce")
    if pd.isna(valid_start) or pd.isna(valid_end):
        return panel
    d = panel.copy()
    d["date"] = pd.to_datetime(d["date"], errors="coerce").dt.normalize()
    d["symbol"] = d["symbol"].astype(str).str.strip()
    panel_symbols = set(d["symbol"].dropna().astype(str))
    valid_dates = pd.Series(sorted(d["date"].dropna().unique()))
    if valid_dates.empty:
        return panel
    weight_date_map = _asof_weight_date_map(valid_dates, benchmark_weights["trade_date_dt"], lag_days=weight_date_lag_days)
    weights_by_date = {pd.Timestamp(key): frame.copy() for key, frame in benchmark_weights.groupby("trade_date_dt", sort=False)}
    seed_symbols: set[str] = set()
    for date_value in valid_dates:
        weight_date = weight_date_map.get(pd.Timestamp(date_value))
        if weight_date is None or pd.isna(weight_date):
            continue
        benchmark = weights_by_date.get(pd.Timestamp(weight_date), pd.DataFrame()).copy()
        if benchmark.empty:
            continue
        benchmark = benchmark.sort_values(["benchmark_weight", "symbol"], ascending=[False, True]).reset_index(drop=True)
        benchmark["benchmark_rank"] = np.arange(1, len(benchmark) + 1)
        core = _select_core(
            benchmark,
            core_top_n=int(seed_core_top_n),
            core_cumulative_weight=float(seed_core_cumulative_weight),
        )
        top = benchmark.head(max(1, int(seed_top_n)))
        seed_symbols.update(core["symbol"].astype(str).tolist())
        seed_symbols.update(top["symbol"].astype(str).tolist())
    missing_symbols = sorted(seed_symbols - panel_symbols)
    if not missing_symbols:
        out = d.copy()
        out["benchmark_seeded"] = False
        return out
    seeded_frames: list[pd.DataFrame] = []
    start = pd.Timestamp(valid_start).date()
    end = pd.Timestamp(valid_end).date()
    as_of = end
    for symbol in missing_symbols:
        hist = load_daily_from_local_history(
            symbol,
            start=start,
            end=end,
            price_adjustment=strategy_cfg.get("price_adjustment", "qfq_asof"),
            as_of_date=as_of,
        )
        if hist.empty:
            continue
        seeded = hist.copy()
        seeded["date"] = pd.to_datetime(seeded["date"], errors="coerce").dt.normalize()
        seeded = seeded[seeded["date"].isin(set(valid_dates))].copy()
        if seeded.empty:
            continue
        seeded["symbol"] = symbol
        if "industry" not in seeded.columns:
            seeded["industry"] = _lookup_stock_industry(symbol)
        else:
            seeded["industry"] = seeded["industry"].fillna(_lookup_stock_industry(symbol))
        seeded["benchmark_seeded"] = True
        seeded_frames.append(seeded)
    out = d.copy()
    out["benchmark_seeded"] = False
    if not seeded_frames:
        return out
    seeded_panel = pd.concat(seeded_frames, ignore_index=True, sort=False)
    combined = pd.concat([out, seeded_panel], ignore_index=True, sort=False)
    return combined.drop_duplicates(["date", "symbol"], keep="first").sort_values(["date", "symbol"]).reset_index(drop=True)


def _lookup_stock_industry(symbol: str) -> str:
    db_path = local_history_path()
    if not db_path.exists():
        return ""
    try:
        with sqlite3.connect(db_path) as conn:
            if not _table_exists(conn, "market_stocks"):
                return ""
            columns = _table_columns(conn, "market_stocks")
            if "industry" not in columns or "symbol" not in columns:
                return ""
            where = "symbol = ?"
            params: tuple[Any, ...] = (symbol,)
            if "market" in columns:
                where = "market = ? AND symbol = ?"
                params = ("CN", symbol)
            order_by = " ORDER BY updated_at DESC" if "updated_at" in columns else ""
            row = conn.execute(
                f"SELECT industry FROM market_stocks WHERE {where}{order_by} LIMIT 1",
                params,
            ).fetchone()
    except sqlite3.Error:
        return ""
    if not row:
        return ""
    return _safe_str(row[0])


def _select_core(benchmark: pd.DataFrame, *, core_top_n: int, core_cumulative_weight: float) -> pd.DataFrame:
    d = benchmark.copy().sort_values(["benchmark_weight", "symbol"], ascending=[False, True]).reset_index(drop=True)
    d["cumulative_weight"] = pd.to_numeric(d["benchmark_weight"], errors="coerce").fillna(0.0).cumsum()
    by_rank = d["benchmark_rank"].le(max(1, int(core_top_n)))
    by_weight = d["cumulative_weight"].le(max(0.0, float(core_cumulative_weight)))
    if not by_weight.any() and not d.empty:
        by_weight.iloc[0] = True
    return d[by_rank | by_weight].copy()


def _reachable_core(
    *,
    core: pd.DataFrame,
    panel_day: pd.DataFrame,
    min_amount: float,
    min_amount_ratio20: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    panel = panel_day.copy()
    panel["symbol"] = panel["symbol"].astype(str).str.strip()
    cols = ["symbol", "close", "amount", "amount_ratio20", "volume", "industry"]
    for col in cols:
        if col not in panel.columns:
            panel[col] = np.nan
    merged = core.merge(panel[cols], on="symbol", how="left")
    reasons = []
    for _, row in merged.iterrows():
        reason = "reachable"
        if pd.isna(row.get("close")):
            reason = "missing_from_pit_panel"
        elif not np.isfinite(_float(row.get("close"))) or _float(row.get("close")) <= 0:
            reason = "invalid_price"
        elif "amount" in row and _float(row.get("amount")) < float(min_amount):
            reason = "amount_below_min"
        elif "amount_ratio20" in row and _float(row.get("amount_ratio20")) < float(min_amount_ratio20):
            reason = "amount_ratio20_below_min"
        elif _invalid_industry(row.get("industry")):
            reason = "missing_industry"
        reasons.append(reason)
    out = merged.copy()
    out["failure_reason"] = reasons
    reachable = out[out["failure_reason"].eq("reachable")].copy()
    return reachable, out[["symbol", "benchmark_rank", "benchmark_weight", "failure_reason"]].copy()


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
        df = pd.read_sql_query(
            """
            SELECT index_code, trade_date, symbol, weight
            FROM cn_index_weights_asof
            WHERE index_code = ?
              AND trade_date <= ?
            ORDER BY trade_date, weight DESC, symbol
            """,
            conn,
            params=(benchmark_symbol, max_date.date().isoformat()),
        )
    if df.empty:
        raise ValueError(f"cn_index_weights_asof has no rows for {benchmark_symbol} before {max_date.date()}")
    df["trade_date_dt"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.normalize()
    df = df.dropna(subset=["trade_date_dt"]).copy()
    df["symbol"] = df["symbol"].astype(str).str.strip()
    df["benchmark_weight"] = pd.to_numeric(df["weight"], errors="coerce").fillna(0.0)
    sums = df.groupby("trade_date_dt")["benchmark_weight"].transform("sum")
    divisor = np.where(sums > 2.0, 100.0, 1.0)
    df["benchmark_weight"] = df["benchmark_weight"] / divisor
    df["benchmark_rank"] = df.groupby("trade_date_dt")["benchmark_weight"].rank(method="first", ascending=False).astype(int)
    return df


def _asof_weight_date_map(
    dates: pd.Series,
    weight_dates: pd.Series,
    *,
    lag_days: int,
) -> dict[pd.Timestamp, pd.Timestamp | None]:
    parsed_dates = pd.to_datetime(dates, errors="coerce").dropna()
    parsed_weight_dates = pd.to_datetime(weight_dates, errors="coerce").dropna()
    unique_dates = pd.DataFrame({"date": pd.to_datetime(sorted(parsed_dates.dt.normalize().unique())).astype("datetime64[ns]")})
    unique_weight_dates = pd.DataFrame(
        {"benchmark_weight_date": pd.to_datetime(sorted(parsed_weight_dates.dt.normalize().unique())).astype("datetime64[ns]")}
    )
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


def _fold_summary(daily_df: pd.DataFrame) -> pd.DataFrame:
    if daily_df.empty:
        return pd.DataFrame()
    rows = []
    for keys, group in daily_df.groupby(["strategy_id", "walk_forward_preset", "fold", "valid_start", "valid_end"], dropna=False):
        strategy_id, preset, fold, valid_start, valid_end = keys
        rows.append(
            {
                "strategy_id": strategy_id,
                "walk_forward_preset": preset,
                "fold": int(fold),
                "valid_start": valid_start,
                "valid_end": valid_end,
                "daily_count": int(len(group)),
                "asof_available_day_count": int(group["asof_status"].astype(str).eq("available").sum()),
                "asof_coverage_ratio": float(group["asof_status"].astype(str).eq("available").mean()) if len(group) else 0.0,
                "avg_core_weight_sum": _mean(group, "core_weight_sum"),
                "avg_reachable_core_weight_sum": _mean(group, "reachable_core_weight_sum"),
                "min_reachable_core_weight_sum": _min(group, "reachable_core_weight_sum"),
                "avg_reachable_core_weight_ratio": _mean(group, "reachable_core_weight_ratio"),
                "min_reachable_core_weight_ratio": _min(group, "reachable_core_weight_ratio"),
                "avg_top_n_weight_sum": _mean(group, "top_n_weight_sum"),
                "avg_reachable_top_n_weight_sum": _mean(group, "reachable_top_n_weight_sum"),
                "min_reachable_top_n_weight_sum": _min(group, "reachable_top_n_weight_sum"),
                "avg_reachable_top_n_weight_ratio": _mean(group, "reachable_top_n_weight_ratio"),
                "min_reachable_top_n_weight_ratio": _min(group, "reachable_top_n_weight_ratio"),
                "avg_reachable_core_member_count": _mean(group, "reachable_core_member_count"),
                "min_reachable_core_member_count": _min(group, "reachable_core_member_count"),
                "main_status": _fold_status(group),
            }
        )
    return pd.DataFrame(rows)


def _overall_status(fold_summary_df: pd.DataFrame) -> str:
    if fold_summary_df.empty:
        return "no_rows"
    if fold_summary_df["main_status"].astype(str).eq("pass").all():
        return "pass"
    if fold_summary_df["main_status"].astype(str).eq("blocked_no_asof_weights").any():
        return "blocked_no_asof_weights"
    return "needs_research"


def _fold_status(group: pd.DataFrame) -> str:
    available = group[group["asof_status"].astype(str).eq("available")]
    if available.empty:
        return "blocked_no_asof_weights"
    avg_core = _mean(available, "reachable_core_weight_sum")
    avg_core_ratio = _mean(available, "reachable_core_weight_ratio")
    avg_top_ratio = _mean(available, "reachable_top_n_weight_ratio")
    if avg_core >= 0.50 and avg_core_ratio >= 0.90 and avg_top_ratio >= 0.98:
        return "pass"
    return "core_reachability_below_threshold"


def _write_report(
    path: Path,
    *,
    fold_summary_df: pd.DataFrame,
    daily_df: pd.DataFrame,
    benchmark_symbol: str,
    top_n: int,
    core_top_n: int,
    core_cumulative_weight: float,
    min_amount: float,
    min_amount_ratio20: float,
    weight_date_lag_days: int,
    seed_benchmark_core: bool,
    seed_top_n: int,
    seed_core_top_n: int,
    seed_core_cumulative_weight: float,
    status: str,
) -> None:
    lines = [
        "# Strategy Core Reachability Diagnostic",
        "",
        f"Generated at: {pd.Timestamp.now().isoformat(timespec='seconds')}",
        "",
        "## Scope",
        "",
        f"- Benchmark: `{benchmark_symbol}`",
        f"- Weight lookup lag days: `{int(weight_date_lag_days)}`",
        f"- Core top N: `{int(core_top_n)}`",
        f"- Core cumulative weight target: `{float(core_cumulative_weight):.2f}`",
        f"- Full benchmark top N: `{int(top_n)}`",
        f"- Minimum amount: `{float(min_amount):.2f}`",
        f"- Minimum amount_ratio20: `{float(min_amount_ratio20):.4f}`",
        f"- Seed benchmark core panel: `{bool(seed_benchmark_core)}`",
        f"- Seed top N: `{int(seed_top_n)}`",
        f"- Seed core top N: `{int(seed_core_top_n)}`",
        f"- Seed core cumulative weight: `{float(seed_core_cumulative_weight):.2f}`",
        f"- Overall status: `{status}`",
        "",
        "## Fold Summary",
        "",
        _md_table(
            [
                "fold",
                "days",
                "asof",
                "reachable_core_w",
                "core_cov",
                "min_core_w",
                "reachable_top_w",
                "top_cov",
                "min_top_w",
                "reachable_names",
                "status",
            ],
            [
                [
                    str(_safe_int(row.get("fold"))),
                    str(_safe_int(row.get("daily_count"))),
                    f"{_safe_float(row.get('asof_coverage_ratio')):.2%}",
                    f"{_safe_float(row.get('avg_reachable_core_weight_sum')):.2%}",
                    f"{_safe_float(row.get('avg_reachable_core_weight_ratio')):.2%}",
                    f"{_safe_float(row.get('min_reachable_core_weight_sum')):.2%}",
                    f"{_safe_float(row.get('avg_reachable_top_n_weight_sum')):.2%}",
                    f"{_safe_float(row.get('avg_reachable_top_n_weight_ratio')):.2%}",
                    f"{_safe_float(row.get('min_reachable_top_n_weight_sum')):.2%}",
                    f"{_safe_float(row.get('avg_reachable_core_member_count')):.1f}",
                    _safe_str(row.get("main_status")),
                ]
                for _, row in fold_summary_df.iterrows()
            ],
        ),
        "",
        "## Interpretation",
        "",
        "This is a read-only reachability diagnostic. It does not create a strategy, admission decision, watchlist, or trading signal.",
        "The Top-N metric uses the complete benchmark weight table, not only stocks visible in the strategy panel.",
        "Top-N absolute weight is benchmark concentration; Top-N coverage ratio is the reachability gate because the benchmark Top-N total weight changes by period.",
        "",
    ]
    if not daily_df.empty:
        latest = daily_df.sort_values("date").groupby("fold").tail(1)
        lines.extend(
            [
                "## Latest Fold Dates",
                "",
                _md_table(
                    ["fold", "date", "weight_date", "reachable_core_w", "reachable_top_w"],
                    [
                        [
                            str(_safe_int(row.get("fold"))),
                            _safe_str(row.get("date")),
                            _safe_str(row.get("benchmark_weight_date")),
                            f"{_safe_float(row.get('reachable_core_weight_sum')):.2%}",
                            f"{_safe_float(row.get('reachable_top_n_weight_sum')):.2%}",
                        ]
                        for _, row in latest.iterrows()
                    ],
                ),
                "",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_run_log(
    path: Path,
    *,
    config_path: Path | None,
    candidate_folds_path: Path,
    command: str | None,
    benchmark_symbol: str,
    output_dir: Path,
    status: str,
) -> None:
    lines = [
        "# Strategy Core Reachability Run Log",
        "",
        f"- generated_at: `{pd.Timestamp.now().isoformat(timespec='seconds')}`",
        f"- status: `{status}`",
        f"- benchmark_symbol: `{benchmark_symbol}`",
        f"- config_path: `{config_path or ''}`",
        f"- candidate_folds_path: `{candidate_folds_path}`",
        f"- output_dir: `{output_dir}`",
        f"- command: `{command or ''}`",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _missing_weight_row(
    candidate_row: pd.Series,
    benchmark_symbol: str,
    date_value: pd.Timestamp,
    *,
    weight_date: pd.Timestamp | None = None,
) -> dict[str, Any]:
    return {
        "strategy_id": _safe_str(candidate_row.get("strategy_id")),
        "walk_forward_preset": _safe_str(candidate_row.get("walk_forward_preset")),
        "fold": _safe_int(candidate_row.get("fold")),
        "valid_start": _safe_str(candidate_row.get("valid_start")),
        "valid_end": _safe_str(candidate_row.get("valid_end")),
        "date": pd.Timestamp(date_value).date().isoformat(),
        "benchmark_symbol": benchmark_symbol,
        "benchmark_weight_date": "" if weight_date is None or pd.isna(weight_date) else pd.Timestamp(weight_date).date().isoformat(),
        "asof_status": "missing",
    }


def _weight_for_reasons(reasons: pd.DataFrame, *, exclude_reason: str) -> float:
    if reasons.empty:
        return 0.0
    keep = reasons[reasons["failure_reason"].astype(str) != exclude_reason]
    return float(pd.to_numeric(keep["benchmark_weight"], errors="coerce").fillna(0.0).sum())


def _invalid_industry(value: Any) -> bool:
    text = str(value).strip()
    return not text or text.lower() == "nan"


def _float(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return np.nan
    return out


def _concat_or_empty(frames: list[pd.DataFrame]) -> pd.DataFrame:
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _ordered_presets(df: pd.DataFrame) -> list[str]:
    return [str(item) for item in dict.fromkeys(df["walk_forward_preset"].astype(str).tolist())]


def _read_required_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    return pd.read_csv(path)


def _require_columns(df: pd.DataFrame, columns: list[str], path: Path) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"{path} missing required columns: {', '.join(missing)}")


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?", (table,)).fetchone())


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    safe = _safe_identifier(table)
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({safe})").fetchall()}


def _safe_identifier(value: str) -> str:
    if not value.replace("_", "").isalnum() or value[0].isdigit():
        raise ValueError(f"Unsafe SQL identifier: {value}")
    return value


def _mean(df: pd.DataFrame, column: str) -> float:
    if column not in df.columns:
        return 0.0
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    return float(values.mean()) if not values.empty else 0.0


def _min(df: pd.DataFrame, column: str) -> float:
    if column not in df.columns:
        return 0.0
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    return float(values.min()) if not values.empty else 0.0


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
