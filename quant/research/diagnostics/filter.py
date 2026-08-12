from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from quant.data_governance.external_market_history import configure_us_market_history
from quant.data_access.local_history import configure_local_history
from quant.strategies import get_strategy
from quant.strategies.strong_index_participation import build_hard_filter_masks
from quant.data_access.throttle import configure_akshare_throttle
from quant.walk_forward import (
    _effective_history_years,
    _load_cross_market_features,
    _resolve_walk_forward_window,
    _strict_qfq_asof_enabled,
    _xmarket_enabled,
    iter_point_in_time_universe_folds,
)


FILTER_STEPS = [
    ("complete_required", "Required fields complete"),
    ("mom20_positive", "20d momentum positive"),
    ("mom60_positive", "60d momentum positive"),
    ("close_above_ma60", "Close above MA60"),
    ("amount_ratio_min", "Amount ratio >= min"),
    ("amount_ratio_max", "Amount ratio <= max"),
    ("upper_shadow", "Upper shadow <= max"),
    ("vol20_p80", "Vol20 <= date p80"),
    ("valid_industry", "Industry available"),
    ("hard_base", "All stock hard filters"),
    ("strong_index_context", "Strong index context"),
    ("eligible_for_new_buy", "Hard filters and strong context"),
]


@dataclass(frozen=True)
class StrategyFilterDiagnosticResult:
    fold_summary_csv_path: Path
    daily_csv_path: Path
    funnel_csv_path: Path
    md_path: Path
    rows: int
    folds: int


def run_strategy_filter_diagnostic(
    *,
    config: dict[str, Any],
    root: Path,
    config_path: Path | None,
    candidate_folds_path: Path,
    strategy_id: str,
    output_dir: Path | None = None,
    presets: list[str] | None = None,
    folds: list[int] | None = None,
    command: str | None = None,
) -> StrategyFilterDiagnosticResult:
    output_dir = output_dir or candidate_folds_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    configure_local_history(config.get("local_history", {}), root)
    configure_us_market_history(config.get("us_market_history", {}), root)
    configure_akshare_throttle(config.get("data_sources", {}).get("akshare", {}))

    candidate_folds = _read_required_csv(candidate_folds_path, "strategy_admission_candidate_folds.csv")
    _require_columns(
        candidate_folds,
        [
            "strategy_id",
            "walk_forward_preset",
            "fold",
            "valid_start",
            "valid_end",
            "trades",
            "avg_live_holdings",
        ],
        candidate_folds_path,
    )
    selected = candidate_folds[candidate_folds["strategy_id"].astype(str) == str(strategy_id)].copy()
    if presets:
        selected = selected[selected["walk_forward_preset"].astype(str).isin({str(item) for item in presets})].copy()
    if folds:
        selected = selected[selected["fold"].astype(int).isin({int(item) for item in folds})].copy()
    if selected.empty:
        raise ValueError(f"no candidate folds found for strategy_id={strategy_id!r}")

    daily_frames: list[pd.DataFrame] = []
    fold_rows: list[dict[str, Any]] = []
    funnel_rows: list[dict[str, Any]] = []
    for preset_name in _ordered_presets(selected):
        scoped_config = copy.deepcopy(config)
        scoped_config.setdefault("walk_forward", {})["preset_name"] = preset_name
        wcfg = scoped_config["walk_forward"]
        strategy_cfg = wcfg.get("strategy_v2", {})
        window_cfg = _resolve_walk_forward_window(wcfg)
        years = _effective_history_years(int(scoped_config["years"]), window_cfg)
        if not _strict_qfq_asof_enabled(scoped_config):
            raise ValueError("strategy-filter-diagnostic requires qfq_asof price mode")
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
            if fold not in target_folds:
                continue
            fold_candidate = selected[
                (selected["walk_forward_preset"].astype(str) == str(preset_name))
                & (selected["fold"].astype(int) == fold)
            ].iloc[0]
            prepared_valid, params = _prepared_valid_panel(
                strategy_id=strategy_id,
                train=fold_context["train"],
                valid=fold_context["valid"],
                strategy_cfg={**strategy_cfg, "mode": "portfolio"},
            )
            daily = _daily_filter_rows(
                prepared_valid,
                params=params,
                strategy_id=strategy_id,
                preset_name=str(preset_name),
                fold=fold,
                candidate_row=fold_candidate,
            )
            if not daily.empty:
                daily_frames.append(daily)
                fold_rows.append(_fold_summary_row(daily, fold_candidate))
                funnel_rows.extend(_funnel_rows(daily, fold_candidate))

    daily_df = _concat_or_empty(daily_frames)
    fold_summary_df = pd.DataFrame(fold_rows)
    funnel_df = pd.DataFrame(funnel_rows)

    fold_summary_csv_path = output_dir / "strategy_filter_fold_summary.csv"
    daily_csv_path = output_dir / "strategy_filter_daily_diagnostic.csv"
    funnel_csv_path = output_dir / "strategy_filter_funnel.csv"
    md_path = output_dir / "strategy_filter_diagnostic_report.md"
    fold_summary_df.to_csv(fold_summary_csv_path, index=False)
    daily_df.to_csv(daily_csv_path, index=False)
    funnel_df.to_csv(funnel_csv_path, index=False)
    _write_markdown(
        md_path,
        fold_summary_df=fold_summary_df,
        funnel_df=funnel_df,
        candidate_folds_path=candidate_folds_path,
        config_path=config_path,
        command=command,
    )
    return StrategyFilterDiagnosticResult(
        fold_summary_csv_path=fold_summary_csv_path,
        daily_csv_path=daily_csv_path,
        funnel_csv_path=funnel_csv_path,
        md_path=md_path,
        rows=len(daily_df),
        folds=int(fold_summary_df["fold"].nunique()) if "fold" in fold_summary_df.columns else 0,
    )


def _prepared_valid_panel(
    *,
    strategy_id: str,
    train: pd.DataFrame,
    valid: pd.DataFrame,
    strategy_cfg: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    strategy = get_strategy(strategy_id)
    prepared = strategy.prepare_panel(pd.concat([train, valid], ignore_index=True), strategy_cfg)
    if prepared.empty:
        return prepared, {}
    prepared["date"] = pd.to_datetime(prepared["date"]).dt.normalize()
    train_dates = set(pd.to_datetime(train["date"]).dt.normalize().unique())
    valid_dates = set(pd.to_datetime(valid["date"]).dt.normalize().unique())
    fold_train = prepared[prepared["date"].isin(train_dates)].copy()
    fold_valid = prepared[prepared["date"].isin(valid_dates)].copy()
    params = strategy.select_params(
        fold_train,
        strategy_cfg,
        slippage=0.0,
        commission=0.0,
        stamp_duty_sell=0.0,
    )
    return fold_valid, params


def _daily_filter_rows(
    panel: pd.DataFrame,
    *,
    params: dict[str, Any],
    strategy_id: str,
    preset_name: str,
    fold: int,
    candidate_row: pd.Series,
) -> pd.DataFrame:
    if panel.empty:
        return pd.DataFrame()
    d = panel.copy().sort_values(["date", "symbol"]).reset_index(drop=True)
    numeric_cols = [
        "close",
        "mom20",
        "mom60",
        "ma60",
        "amount_ratio20",
        "upper_shadow_pct",
        "vol20",
        "ret",
        "resid_mom20",
        "industry_relative_mom20",
        "breakout20",
        "benchmark_weight",
    ]
    for col in numeric_cols:
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce")
    if "strong_index_context" not in d.columns:
        d["strong_index_context"] = False
    d["strong_index_context"] = d["strong_index_context"].fillna(False).astype(bool)
    d["resid_mom20"] = d.get("resid_mom20", pd.Series(0.0, index=d.index)).fillna(0.0)
    d["industry_relative_mom20"] = d.get("industry_relative_mom20", pd.Series(0.0, index=d.index)).fillna(0.0)
    d["breakout20"] = d.get("breakout20", pd.Series(0.0, index=d.index)).fillna(0.0)
    if "benchmark_weight" not in d.columns:
        d["benchmark_weight"] = 0.0
    d["benchmark_weight"] = pd.to_numeric(d["benchmark_weight"], errors="coerce").fillna(0.0).clip(lower=0.0)
    masks = build_hard_filter_masks(d, params)
    hard_base = masks["hard_base"]
    strong = d["strong_index_context"]
    daily_review_strategy = strategy_id == "strong_market_effective_participation_v1"
    rebalance_days = 1 if daily_review_strategy else max(1, int(params.get("rebalance_days", 20)))
    dynamic_trigger_enabled = bool(params.get("dynamic_strong_context_trigger", False))
    rows: list[dict[str, Any]] = []
    previous_context_is_strong = False
    for day_idx, (date_value, day) in enumerate(d.groupby("date", sort=True)):
        idx = day.index
        context_is_strong = bool(strong.loc[idx].any())
        review_reason = _review_reason_for_diagnostic(
            day_idx=day_idx,
            rebalance_days=rebalance_days,
            context_is_strong=context_is_strong,
            previous_context_is_strong=previous_context_is_strong,
            dynamic_trigger_enabled=dynamic_trigger_enabled,
        )
        row = {
            "strategy_id": strategy_id,
            "walk_forward_preset": preset_name,
            "fold": int(fold),
            "valid_start": _safe_str(candidate_row.get("valid_start")),
            "valid_end": _safe_str(candidate_row.get("valid_end")),
            "date": pd.Timestamp(date_value).date().isoformat(),
            "universe_rows": int(len(day)),
            "strong_index_context": context_is_strong,
            "review_day": bool(review_reason),
            "review_reason": review_reason,
            "dynamic_review_trigger": review_reason == "dynamic_strong_context_on",
            "strong_index_close": _first_numeric(day, "strong_index_close"),
            "strong_index_ret20": _first_numeric(day, "strong_index_ret20"),
            "strong_index_ret60": _first_numeric(day, "strong_index_ret60"),
            "strong_index_drawdown": _first_numeric(day, "strong_index_drawdown"),
        }
        benchmark_weight = pd.to_numeric(day["benchmark_weight"], errors="coerce").fillna(0.0)
        benchmark_member = benchmark_weight > 0
        hard_benchmark_member = benchmark_member & hard_base.loc[idx]
        eligible_benchmark_member = benchmark_member & hard_base.loc[idx] & strong.loc[idx]
        top20_benchmark_member = benchmark_weight.rank(method="first", ascending=False) <= 20
        top20_eligible_member = top20_benchmark_member & eligible_benchmark_member
        row.update(
            {
                "benchmark_member_count": int(benchmark_member.sum()),
                "benchmark_member_share": float(benchmark_member.mean()) if len(day) else 0.0,
                "benchmark_weight_sum": float(benchmark_weight.sum()),
                "hard_filter_benchmark_member_count": int(hard_benchmark_member.sum()),
                "hard_filter_benchmark_weight_sum": float(benchmark_weight.where(hard_benchmark_member, 0.0).sum()),
                "eligible_benchmark_member_count": int(eligible_benchmark_member.sum()),
                "eligible_benchmark_weight_sum": float(benchmark_weight.where(eligible_benchmark_member, 0.0).sum()),
                "panel_top20_benchmark_weight_sum": float(benchmark_weight.where(top20_benchmark_member, 0.0).sum()),
                "panel_top20_eligible_benchmark_member_count": int(top20_eligible_member.sum()),
                "panel_top20_eligible_benchmark_weight_sum": float(benchmark_weight.where(top20_eligible_member, 0.0).sum()),
            }
        )
        for step, _label in FILTER_STEPS:
            if step == "strong_index_context":
                count = len(day) if row["strong_index_context"] else 0
            elif step == "eligible_for_new_buy":
                count = int((hard_base.loc[idx] & strong.loc[idx]).sum())
            else:
                count = int(masks[step].loc[idx].sum())
            row[f"{step}_count"] = count
            row[f"{step}_share"] = float(count / len(day)) if len(day) else 0.0
        rows.append(row)
        previous_context_is_strong = context_is_strong
    return pd.DataFrame(rows)


def _fold_summary_row(daily: pd.DataFrame, candidate_row: pd.Series) -> dict[str, Any]:
    total_days = len(daily)
    strong_days = int(daily["strong_index_context"].sum()) if total_days else 0
    days_with_candidates = int((daily["eligible_for_new_buy_count"] > 0).sum()) if total_days else 0
    rebalance_days = int(daily["review_day"].fillna(False).astype(bool).sum()) if "review_day" in daily.columns else _rebalance_day_count(daily)
    fixed_rebalance_days = (
        int(daily["review_reason"].astype(str).eq("fixed_rebalance").sum())
        if "review_reason" in daily.columns
        else _rebalance_day_count(daily)
    )
    dynamic_review_days = (
        int(daily["review_reason"].astype(str).eq("dynamic_strong_context_on").sum())
        if "review_reason" in daily.columns
        else 0
    )
    review_mask = daily["review_day"].fillna(False).astype(bool) if "review_day" in daily.columns else pd.Series(False, index=daily.index)
    strong_rebalance_days = int((review_mask & daily["strong_index_context"].fillna(False).astype(bool)).sum()) if total_days else 0
    candidate_rebalance_days = int((review_mask & (daily["eligible_for_new_buy_count"] > 0)).sum()) if total_days else 0
    main_bottleneck = _main_bottleneck(daily)
    strong_daily = daily[daily["strong_index_context"].fillna(False).astype(bool)].copy() if total_days else daily
    return {
        "strategy_id": _safe_str(candidate_row.get("strategy_id")),
        "walk_forward_preset": _safe_str(candidate_row.get("walk_forward_preset")),
        "fold": _safe_int(candidate_row.get("fold")),
        "valid_start": _safe_str(candidate_row.get("valid_start")),
        "valid_end": _safe_str(candidate_row.get("valid_end")),
        "valid_days": total_days,
        "strong_context_days": strong_days,
        "strong_context_share": float(strong_days / total_days) if total_days else 0.0,
        "days_with_eligible_new_buy": days_with_candidates,
        "days_with_eligible_new_buy_share": float(days_with_candidates / total_days) if total_days else 0.0,
        "rebalance_day_count": rebalance_days,
        "fixed_rebalance_day_count": fixed_rebalance_days,
        "dynamic_review_day_count": dynamic_review_days,
        "strong_rebalance_day_count": strong_rebalance_days,
        "candidate_rebalance_day_count": candidate_rebalance_days,
        "avg_hard_filter_candidates": _mean(daily, "hard_base_count"),
        "avg_eligible_new_buy_candidates": _mean(daily, "eligible_for_new_buy_count"),
        "max_eligible_new_buy_candidates": _max(daily, "eligible_for_new_buy_count"),
        "avg_benchmark_members": _mean(daily, "benchmark_member_count"),
        "avg_hard_filter_benchmark_members": _mean(daily, "hard_filter_benchmark_member_count"),
        "avg_hard_filter_benchmark_weight": _mean(daily, "hard_filter_benchmark_weight_sum"),
        "avg_eligible_benchmark_members_on_strong_days": _mean(strong_daily, "eligible_benchmark_member_count"),
        "avg_eligible_benchmark_weight_on_strong_days": _mean(strong_daily, "eligible_benchmark_weight_sum"),
        "max_eligible_benchmark_weight_on_strong_days": _max(strong_daily, "eligible_benchmark_weight_sum"),
        "avg_panel_top20_eligible_benchmark_members_on_strong_days": _mean(strong_daily, "panel_top20_eligible_benchmark_member_count"),
        "avg_panel_top20_eligible_benchmark_weight_on_strong_days": _mean(strong_daily, "panel_top20_eligible_benchmark_weight_sum"),
        "admission_trades": _safe_int(candidate_row.get("trades")),
        "admission_avg_live_holdings": _safe_float(candidate_row.get("avg_live_holdings")),
        "admission_ann": _safe_float(candidate_row.get("annualized_return")),
        "benchmark_ann": _safe_float(candidate_row.get("benchmark_annualized_return")),
        "excess_ann": _safe_float(candidate_row.get("excess_annualized_return")),
        "main_bottleneck": main_bottleneck,
        "interpretation": _interpret_fold(daily, candidate_row, main_bottleneck),
    }


def _funnel_rows(daily: pd.DataFrame, candidate_row: pd.Series) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for step, label in FILTER_STEPS:
        count_col = f"{step}_count"
        share_col = f"{step}_share"
        rows.append(
            {
                "strategy_id": _safe_str(candidate_row.get("strategy_id")),
                "walk_forward_preset": _safe_str(candidate_row.get("walk_forward_preset")),
                "fold": _safe_int(candidate_row.get("fold")),
                "valid_start": _safe_str(candidate_row.get("valid_start")),
                "valid_end": _safe_str(candidate_row.get("valid_end")),
                "step": step,
                "label": label,
                "avg_count": _mean(daily, count_col),
                "median_count": _median(daily, count_col),
                "max_count": _max(daily, count_col),
                "avg_share": _mean(daily, share_col),
                "days_nonzero": int((pd.to_numeric(daily[count_col], errors="coerce").fillna(0.0) > 0).sum()) if count_col in daily.columns else 0,
                "valid_days": int(len(daily)),
            }
        )
    return rows


def _main_bottleneck(daily: pd.DataFrame) -> str:
    if daily.empty:
        return "no_valid_panel"
    strong_share = _share_metric(daily, "strong_index_context_share", "strong_index_context")
    hard_share = _mean(daily, "hard_base_share")
    eligible_share = _mean(daily, "eligible_for_new_buy_share")
    if strong_share <= 0.05:
        return "strong_index_context_too_rare"
    if hard_share <= 0.01:
        return "stock_hard_filters_too_strict"
    if eligible_share <= 0.01:
        return "context_and_stock_filters_do_not_overlap"
    return "eligible_but_construction_or_hold_rules_limit_trades"


def _share_metric(df: pd.DataFrame, share_column: str, bool_column: str) -> float:
    if share_column in df.columns:
        return _mean(df, share_column)
    if bool_column in df.columns:
        values = df[bool_column].fillna(False).astype(bool)
        return float(values.mean()) if len(values) else 0.0
    return 0.0


def _interpret_fold(daily: pd.DataFrame, candidate_row: pd.Series, main_bottleneck: str) -> str:
    trades = _safe_int(candidate_row.get("trades"))
    avg_live = _safe_float(candidate_row.get("avg_live_holdings"))
    if main_bottleneck == "strong_index_context_too_rare":
        return "Strong-index gate was rarely true, so the strategy mostly stayed in cash."
    if main_bottleneck == "stock_hard_filters_too_strict":
        return "The stock hard filters left too few candidates even before the strong-index gate."
    if main_bottleneck == "context_and_stock_filters_do_not_overlap":
        return "Strong-index days and stock hard-filter pass days did not overlap enough to create target holdings."
    if trades <= 0 or avg_live <= 0:
        return "Candidates existed on some days, but rebalance timing or hold rules produced no live exposure."
    return "The strategy opened positions, so failure should be explained by return quality rather than only by empty exposure."


def _write_markdown(
    path: Path,
    *,
    fold_summary_df: pd.DataFrame,
    funnel_df: pd.DataFrame,
    candidate_folds_path: Path,
    config_path: Path | None,
    command: str | None,
) -> None:
    lines = [
        "# Strategy Filter Diagnostic Report",
        "",
        f"Generated at: {pd.Timestamp.now().isoformat(timespec='seconds')}",
        "",
        "## Scope",
        "",
        f"- Config: `{config_path.as_posix() if config_path else ''}`",
        f"- Candidate folds: `{candidate_folds_path.as_posix()}`",
        f"- Command: `{command or ''}`",
        "",
        "## Fold Summary",
        "",
        _md_table(
            [
                "fold",
                "strong_days",
                "eligible_days",
                "strong_rebal",
                "candidate_rebal",
                "fixed_rebal",
                "dynamic_rebal",
                "avg_candidates",
                "avg_bench_members",
                "eligible_bench_w",
                "panel_top20_eligible_w",
                "max_candidates",
                "trades",
                "avg_live",
                "main_bottleneck",
            ],
            [
                [
                    str(_safe_int(row.get("fold"))),
                    f"{_safe_int(row.get('strong_context_days'))}/{_safe_int(row.get('valid_days'))}",
                    f"{_safe_int(row.get('days_with_eligible_new_buy'))}/{_safe_int(row.get('valid_days'))}",
                    f"{_safe_int(row.get('strong_rebalance_day_count'))}/{_safe_int(row.get('rebalance_day_count'))}",
                    f"{_safe_int(row.get('candidate_rebalance_day_count'))}/{_safe_int(row.get('rebalance_day_count'))}",
                    str(_safe_int(row.get("fixed_rebalance_day_count"))),
                    str(_safe_int(row.get("dynamic_review_day_count"))),
                    f"{_safe_float(row.get('avg_eligible_new_buy_candidates')):.2f}",
                    f"{_safe_float(row.get('avg_benchmark_members')):.2f}",
                    f"{_safe_float(row.get('avg_eligible_benchmark_weight_on_strong_days')):.4f}",
                    f"{_safe_float(row.get('avg_panel_top20_eligible_benchmark_weight_on_strong_days')):.4f}",
                    f"{_safe_float(row.get('max_eligible_new_buy_candidates')):.0f}",
                    str(_safe_int(row.get("admission_trades"))),
                    f"{_safe_float(row.get('admission_avg_live_holdings')):.2f}",
                    _safe_str(row.get("main_bottleneck")),
                ]
                for _, row in fold_summary_df.iterrows()
            ],
        ),
        "",
        "## Interpretation",
        "",
    ]
    for _, row in fold_summary_df.iterrows():
        lines.append(
            f"- Fold {_safe_int(row.get('fold'))}: {_safe_str(row.get('interpretation'))} "
            f"eligible_new_buy_days={_safe_int(row.get('days_with_eligible_new_buy'))}, "
            f"trades={_safe_int(row.get('admission_trades'))}."
        )
    lines.extend(
        [
            "",
            "## Funnel Notes",
            "",
            "The funnel is diagnostic only. It does not change admission status and must not be used to tune thresholds inside this run.",
            "",
        ]
    )
    if not funnel_df.empty:
        compact = funnel_df[funnel_df["step"].isin(["strong_index_context", "hard_base", "eligible_for_new_buy"])].copy()
        lines.append(
            _md_table(
                ["fold", "step", "avg_count", "days_nonzero", "valid_days"],
                [
                    [
                        str(_safe_int(row.get("fold"))),
                        _safe_str(row.get("step")),
                        f"{_safe_float(row.get('avg_count')):.2f}",
                        str(_safe_int(row.get("days_nonzero"))),
                        str(_safe_int(row.get("valid_days"))),
                    ]
                    for _, row in compact.iterrows()
                ],
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _ordered_presets(df: pd.DataFrame) -> list[str]:
    return [str(item) for item in dict.fromkeys(df["walk_forward_preset"].astype(str).tolist())]


def _rebalance_day_count(daily: pd.DataFrame) -> int:
    return int(len(daily.iloc[::20])) if not daily.empty else 0


def _review_reason_for_diagnostic(
    *,
    day_idx: int,
    rebalance_days: int,
    context_is_strong: bool,
    previous_context_is_strong: bool,
    dynamic_trigger_enabled: bool,
) -> str:
    if day_idx % rebalance_days == 0:
        return "fixed_rebalance"
    if dynamic_trigger_enabled and context_is_strong and not previous_context_is_strong:
        return "dynamic_strong_context_on"
    return ""


def _concat_or_empty(frames: list[pd.DataFrame]) -> pd.DataFrame:
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _read_required_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    return pd.read_csv(path)


def _require_columns(df: pd.DataFrame, columns: list[str], path: Path) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"{path} missing required columns: {', '.join(missing)}")


def _first_numeric(df: pd.DataFrame, column: str) -> float:
    if column not in df.columns:
        return np.nan
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    return float(values.iloc[0]) if not values.empty else np.nan


def _mean(df: pd.DataFrame, column: str) -> float:
    if column not in df.columns:
        return 0.0
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    return float(values.mean()) if not values.empty else 0.0


def _median(df: pd.DataFrame, column: str) -> float:
    if column not in df.columns:
        return 0.0
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    return float(values.median()) if not values.empty else 0.0


def _max(df: pd.DataFrame, column: str) -> float:
    if column not in df.columns:
        return 0.0
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    return float(values.max()) if not values.empty else 0.0


def _safe_str(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value)


def _safe_int(value: Any) -> int:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return int(parsed) if pd.notna(parsed) else 0


def _safe_float(value: Any) -> float:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return float(parsed) if pd.notna(parsed) else 0.0


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)
