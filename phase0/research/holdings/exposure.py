from __future__ import annotations

import copy
import hashlib
import re
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from phase0.data_governance.external_market_history import configure_us_market_history
from phase0.data_access.local_history import configure_local_history, load_index_daily_from_local_history, local_history_path
from phase0.strategies import get_strategy
from phase0.research.admission.strategy_scope import _force_strategy_set_enabled_for_admission
from phase0.strategies.constraints import apply_strategy_constraints
from phase0.throttle import configure_akshare_throttle
from phase0.walk_forward import (
    _attach_benchmark_fold_metrics,
    _build_account_execution_config,
    _calc_metrics,
    _effective_history_years,
    _load_cross_market_features,
    _normalize_strategy_output,
    _resolve_walk_forward_window,
    _signal_trace_summary,
    _strict_qfq_asof_enabled,
    _xmarket_enabled,
    iter_point_in_time_universe_folds,
)


EPS = 1e-12
UNKNOWN_INDUSTRY = "UNKNOWN"


@dataclass(frozen=True)
class StrategyHoldingsExposureResult:
    holdings_csv_path: Path
    daily_exposure_csv_path: Path
    industry_exposure_csv_path: Path
    summary_csv_path: Path
    coverage_csv_path: Path
    run_log_md_path: Path
    md_path: Path
    holdings_rows: int
    daily_rows: int
    summary_rows: int


def run_strategy_holdings_exposure(
    *,
    config: dict[str, Any],
    root: Path,
    config_path: Path | None,
    candidate_folds_path: Path,
    market_context_path: Path,
    strategy_id: str,
    output_dir: Path | None = None,
    presets: list[str] | None = None,
    folds: list[int] | None = None,
    benchmark_symbol: str | None = None,
    command: str | None = None,
) -> StrategyHoldingsExposureResult:
    """Rebuild research-only daily holdings for selected historical strategy folds."""
    output_dir = output_dir or market_context_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    configure_local_history(config.get("local_history", {}), root)
    configure_us_market_history(config.get("us_market_history", {}), root)
    configure_akshare_throttle(config.get("data_sources", {}).get("akshare", {}))

    candidate_folds = _read_required_csv(candidate_folds_path, "strategy_admission_candidate_folds.csv")
    market_context = _read_required_csv(market_context_path, "strategy_market_context_diagnostic.csv")
    _require_columns(
        candidate_folds,
        [
            "strategy_id",
            "walk_forward_preset",
            "fold",
            "valid_start",
            "valid_end",
            "annualized_return",
        ],
        candidate_folds_path,
    )
    candidate_folds = _ensure_optional_fold_metric_columns(candidate_folds)
    _require_columns(
        market_context,
        [
            "strategy_id",
            "walk_forward_preset",
            "fold",
            "market_context_label",
            "benchmark_return_bucket",
            "benchmark_trend_bucket",
        ],
        market_context_path,
    )
    selected = candidate_folds[candidate_folds["strategy_id"].astype(str) == str(strategy_id)].copy()
    if presets:
        wanted = {str(item) for item in presets}
        selected = selected[selected["walk_forward_preset"].astype(str).isin(wanted)].copy()
    if folds:
        wanted_folds = {int(item) for item in folds}
        selected = selected[selected["fold"].astype(int).isin(wanted_folds)].copy()
    if selected.empty:
        raise ValueError(f"no candidate folds found for strategy_id={strategy_id!r}")

    fold_keys = ["strategy_id", "walk_forward_preset", "fold"]
    _validate_unique_keys(selected, fold_keys, candidate_folds_path)
    _validate_unique_keys(market_context[market_context["strategy_id"].astype(str) == str(strategy_id)].copy(), fold_keys, market_context_path)
    context = selected[fold_keys].merge(market_context, on=fold_keys, how="left")
    context["market_context_label"] = context["market_context_label"].fillna("not_available")
    context_map = {
        (str(row["walk_forward_preset"]), int(row["fold"])): row.to_dict()
        for _, row in context.iterrows()
    }
    params_map = {
        (str(row["walk_forward_preset"]), int(row["fold"])): _parse_selected_params(
            _safe_str(row.get("selected_params")),
            config.get("walk_forward", {}).get("strategy_v2", {}),
        )
        for _, row in selected.iterrows()
    }

    all_holdings: list[pd.DataFrame] = []
    all_daily: list[pd.DataFrame] = []
    all_industry: list[pd.DataFrame] = []
    all_fold_rows: list[dict[str, Any]] = []
    audit_frames: list[pd.DataFrame] = []
    preset_names = _ordered_presets(selected)
    for preset_name in preset_names:
        scoped_config = copy.deepcopy(config)
        scoped_config.setdefault("walk_forward", {})["preset_name"] = preset_name
        wcfg = scoped_config["walk_forward"]
        strategy_cfg = wcfg.get("strategy_v2", {})
        _force_strategy_set_enabled_for_admission(strategy_cfg, [str(strategy_id)])
        window_cfg = _resolve_walk_forward_window(wcfg)
        years = _effective_history_years(int(scoped_config["years"]), window_cfg)
        use_point_in_time_universe = bool(
            scoped_config.get("universe", {}).get("enabled", False)
            and scoped_config.get("universe", {}).get("point_in_time_for_backtest", True)
            and scoped_config.get("local_history", {}).get("enabled", True)
        )
        if not use_point_in_time_universe:
            raise ValueError("strategy-holdings-exposure currently requires point-in-time universe folds")
        if not _strict_qfq_asof_enabled(scoped_config):
            raise ValueError("strategy-holdings-exposure requires qfq_asof price mode for this research diagnostic")

        target_folds = {
            int(value)
            for value in selected.loc[selected["walk_forward_preset"].astype(str) == preset_name, "fold"].tolist()
        }
        fold_contexts, universe_audit = iter_point_in_time_universe_folds(
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
        if not universe_audit.empty:
            audit = universe_audit.copy()
            audit["walk_forward_preset"] = preset_name
            audit_frames.append(audit)
        for fold_context in fold_contexts:
            fold = int(fold_context["fold"])
            if fold not in target_folds:
                continue
            context_row = context_map.get((preset_name, fold), {})
            selected_params = params_map.get((preset_name, fold))
            output, fold_row = _run_strategy_output_on_fold(
                scoped_config,
                strategy_id,
                fold=fold,
                train=fold_context["train"],
                valid=fold_context["valid"],
                slippage=float(wcfg["slippage"]),
                commission=float(wcfg["commission"]),
                stamp_duty_sell=float(wcfg["stamp_duty_sell"]),
                strategy_cfg={**strategy_cfg, "mode": "portfolio"},
                account_execution=_build_account_execution_config(scoped_config, wcfg, strategy_cfg),
                selected_params=selected_params,
            )
            fold_row.update(
                {
                    "walk_forward_preset": preset_name,
                    "market_context_label": _safe_str(context_row.get("market_context_label", "not_available")),
                    "benchmark_return_bucket": _safe_str(context_row.get("benchmark_return_bucket", "not_available")),
                    "benchmark_trend_bucket": _safe_str(context_row.get("benchmark_trend_bucket", "not_available")),
                    "universe_mode": "point_in_time",
                    "universe_as_of_date": _safe_str(fold_context.get("audit", {}).get("universe_as_of_date", "")),
                    "universe_symbol_count": _safe_int(fold_context.get("audit", {}).get("universe_symbol_count", 0)),
                    "universe_source": _safe_str(fold_context.get("audit", {}).get("universe_source", "")),
                }
            )
            all_fold_rows.append(fold_row)
            holdings = _holding_rows_from_signal(
                output.signal_frame,
                fold_row=fold_row,
                context_row=context_row,
            )
            if not holdings.empty:
                all_holdings.append(holdings)
                all_daily.append(_daily_exposure_from_holdings(holdings))
                all_industry.append(_industry_exposure_from_holdings(holdings))

    holdings_df = _concat_or_empty(all_holdings)
    daily_df = _concat_or_empty(all_daily)
    industry_df = _concat_or_empty(all_industry)
    fold_df = pd.DataFrame(all_fold_rows)
    summary_df = _summary_from_daily(daily_df, fold_df)
    coverage_df = _coverage_summary(
        holdings_df=holdings_df,
        daily_df=daily_df,
        fold_df=fold_df,
        audit_df=_concat_or_empty(audit_frames),
        benchmark_symbol=benchmark_symbol or str(config.get("benchmark_symbol", "SH.000300")),
        local_history_db=local_history_path(),
    )
    benchmark_df = _benchmark_daily_features(
        benchmark_symbol or str(config.get("benchmark_symbol", "SH.000300")),
        daily_df,
    )
    if not benchmark_df.empty and not daily_df.empty:
        daily_df = daily_df.merge(benchmark_df, on="date", how="left")

    holdings_csv_path = output_dir / "strategy_daily_holdings.csv"
    daily_exposure_csv_path = output_dir / "strategy_daily_exposure.csv"
    industry_exposure_csv_path = output_dir / "strategy_daily_industry_exposure.csv"
    summary_csv_path = output_dir / "strategy_holdings_exposure_summary.csv"
    coverage_csv_path = output_dir / "strategy_holdings_exposure_coverage.csv"
    run_log_md_path = output_dir / "strategy_holdings_exposure_run_log.md"
    md_path = output_dir / "strategy_holdings_exposure_report.md"
    holdings_df.to_csv(holdings_csv_path, index=False)
    daily_df.to_csv(daily_exposure_csv_path, index=False)
    industry_df.to_csv(industry_exposure_csv_path, index=False)
    summary_df.to_csv(summary_csv_path, index=False)
    coverage_df.to_csv(coverage_csv_path, index=False)
    _write_markdown(
        md_path,
        summary_df=summary_df,
        coverage_df=coverage_df,
        candidate_folds_path=candidate_folds_path,
        market_context_path=market_context_path,
        strategy_id=strategy_id,
    )
    _write_run_log(
        run_log_md_path,
        config=config,
        root=root,
        output_dir=output_dir,
        output_artifacts=[
            holdings_csv_path,
            daily_exposure_csv_path,
            industry_exposure_csv_path,
            summary_csv_path,
            coverage_csv_path,
            md_path,
        ],
        config_path=config_path,
        candidate_folds_path=candidate_folds_path,
        market_context_path=market_context_path,
        command=command,
    )
    return StrategyHoldingsExposureResult(
        holdings_csv_path=holdings_csv_path,
        daily_exposure_csv_path=daily_exposure_csv_path,
        industry_exposure_csv_path=industry_exposure_csv_path,
        summary_csv_path=summary_csv_path,
        coverage_csv_path=coverage_csv_path,
        run_log_md_path=run_log_md_path,
        md_path=md_path,
        holdings_rows=len(holdings_df),
        daily_rows=len(daily_df),
        summary_rows=len(summary_df),
    )


def _run_strategy_output_on_fold(
    config: dict[str, Any],
    strategy_name: str,
    *,
    fold: int,
    train: pd.DataFrame,
    valid: pd.DataFrame,
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
    strategy_cfg: dict[str, Any],
    account_execution: Any,
    selected_params: dict[str, Any] | None = None,
) -> tuple[Any, dict[str, Any]]:
    strategy = get_strategy(strategy_name)
    if not strategy.is_enabled(strategy_cfg):
        raise ValueError(f"strategy is not enabled: {strategy_name}")
    train_dates = set(pd.to_datetime(train["date"]).dt.normalize().unique())
    valid_dates = set(pd.to_datetime(valid["date"]).dt.normalize().unique())
    strategy_cfg_for_prepare = dict(strategy_cfg)
    train_sorted = sorted(pd.Timestamp(item).normalize() for item in train_dates)
    valid_sorted = sorted(pd.Timestamp(item).normalize() for item in valid_dates)
    strategy_cfg_for_prepare["_fold_prepare_context"] = {
        "train_start": train_sorted[0].date().isoformat() if train_sorted else "",
        "train_end": train_sorted[-1].date().isoformat() if train_sorted else "",
        "valid_start": valid_sorted[0].date().isoformat() if valid_sorted else "",
        "valid_end": valid_sorted[-1].date().isoformat() if valid_sorted else "",
    }
    prepared = strategy.prepare_panel(pd.concat([train, valid], ignore_index=True), strategy_cfg_for_prepare)
    if prepared.empty:
        raise ValueError(f"strategy prepared an empty panel: {strategy_name} fold={fold}")
    prepared["date"] = pd.to_datetime(prepared["date"]).dt.normalize()
    fold_train = prepared[prepared["date"].isin(train_dates)].copy()
    fold_valid = prepared[prepared["date"].isin(valid_dates)].copy()
    if fold_train.empty or fold_valid.empty:
        raise ValueError(f"fold has empty train/valid panel after strategy preparation: {strategy_name} fold={fold}")
    params = selected_params or strategy.select_params(
        fold_train,
        strategy_cfg,
        slippage=slippage,
        commission=commission,
        stamp_duty_sell=stamp_duty_sell,
    )
    if selected_params is not None:
        params = _complete_price_volume_params(params, fold_train)
    result = strategy.apply(
        fold_valid,
        params,
        slippage=slippage,
        commission=commission,
        stamp_duty_sell=stamp_duty_sell,
    )
    output = _normalize_strategy_output(result, fold_valid, strategy_name, params)
    constraint_result = apply_strategy_constraints(
        output,
        strategy_name=strategy_name,
        panel_scope=strategy.panel_scope,
        strategy_cfg=strategy_cfg,
        panel=fold_valid,
        slippage=slippage,
        commission=commission,
        stamp_duty_sell=stamp_duty_sell,
    )
    output = constraint_result.output
    metric = _calc_metrics(output.returns, output.exposure)
    meta = output.metadata or strategy.build_metadata(params)
    row = {
        "strategy_id": meta.get("strategy_id", strategy.name),
        "fold": int(fold),
        "train_start": str(pd.Timestamp(fold_train["date"].min()).date()),
        "train_end": str(pd.Timestamp(fold_train["date"].max()).date()),
        "valid_start": str(pd.Timestamp(fold_valid["date"].min()).date()),
        "valid_end": str(pd.Timestamp(fold_valid["date"].max()).date()),
        "annualized_return": metric["annualized_return"],
        "sharpe": metric["sharpe"],
        "max_drawdown": metric["max_drawdown"],
        "win_rate": metric["win_rate"],
        "turnover_annual": metric["turnover_annual"],
        "trades": metric["trades"],
        "selected_params": meta.get("formatted_params", strategy.format_params(params)),
        "supports_brief": meta.get("supports_brief", True),
        "supports_paper_trade": meta.get("supports_paper_trade", True),
    }
    row.update(constraint_result.metrics)
    row.update(_signal_trace_summary(output))
    row = _attach_benchmark_fold_metrics(
        row,
        config=config,
        valid_start=fold_valid["date"].min(),
        valid_end=fold_valid["date"].max(),
    )
    return output, row


def _parse_selected_params(text: str, strategy_cfg: dict[str, Any]) -> dict[str, Any] | None:
    if text.startswith("low_vol_low_turnover_quality@"):
        return _parse_low_vol_quality_params(text, strategy_cfg)
    if not text.startswith("price_volume_low_turnover@"):
        return None
    cfg = strategy_cfg.get("local_factor", {}).get("price_volume_low_turnover", {})
    constraints = strategy_cfg.get("constraints", {}).get("industry", {})
    weights_cfg = cfg.get("factor_weights", {})
    params: dict[str, Any] = {
        "eligible": True,
        "residual_window": _int_match(text, r"resid_mom(\d+)", 20),
        "residual_quantile": _float_match(text, r"resid_mom\d+@q([0-9.]+)", 0.6),
        "momentum_window": _int_match(text, r",mom(\d+)@q", 20),
        "momentum_quantile": _float_match(text, r",mom\d+@q([0-9.]+)", 0.55),
        "trend_window": _int_match(text, r",ma(\d+)", 20),
        "vol_quantile": _float_match(text, r",vol@q([0-9.]+)", 0.75),
        "amount_ratio_min": _float_match(text, r",amt=([0-9.]+)-", 1.0),
        "amount_ratio_max": _float_match(text, r",amt=[0-9.]+-([0-9.]+)", 3.0),
        "upper_shadow_max": _float_match(text, r",upper_shadow<=([0-9.]+)", 1.0),
        "breakout_required": _bool_match(text, r",breakout_required=(True|False)", False),
        "industry_relative_window": _int_match(text, r",industry_rel_mom(\d+)@q", 20),
        "industry_relative_enabled": "industry_rel_mom" in text,
        "industry_relative_quantile": _float_match(text, r",industry_rel_mom\d+@q([0-9.]+)", 0.5),
        "buy_top_n": _int_match(text, r",buy_top=(\d+)", 10),
        "hold_top_n": _int_match(text, r",hold_top=(\d+)", 20),
        "rebalance_days": _int_match(text, r",rebalance=(\d+)d", 40),
        "min_hold_days": _int_match(text, r",min_hold=(\d+)d", 20),
        "max_symbol_weight": _float_match(text, r",max_w=([0-9.]+)", float(cfg.get("max_symbol_weight", 0.10))),
        "target_vol": _float_match(text, r",target_vol=([0-9.]+)", float(strategy_cfg.get("target_vol", 0.18))),
        "turnover_penalty": _float_match(text, r",turnover_penalty=([0-9.]+)", 0.02),
        "max_names_per_industry": _optional_int(constraints.get("max_names_per_industry")),
        "factor_weights": {
            "residual_momentum": float(weights_cfg.get("residual_momentum", 0.40)),
            "momentum": float(weights_cfg.get("momentum", 0.20)),
            "low_volatility": float(weights_cfg.get("low_volatility", 0.20)),
            "amount_confirmation": float(weights_cfg.get("amount_confirmation", 0.10)),
            "industry_relative_strength": float(weights_cfg.get("industry_relative_strength", 0.10)),
        },
        "train_score": 0.0,
        "train_sharpe": 0.0,
        "train_trades": 0,
        "train_turnover_annual": 0.0,
    }
    return params


def _parse_low_vol_quality_params(text: str, strategy_cfg: dict[str, Any]) -> dict[str, Any]:
    cfg = strategy_cfg.get("local_factor", {}).get("low_vol_low_turnover_quality", {})
    constraints = strategy_cfg.get("constraints", {}).get("industry", {})
    weights_cfg = cfg.get("factor_weights", {})
    return {
        "eligible": True,
        "quality_quantile": _float_match(text, r"@q([0-9.]+)", 0.6),
        "quality_threshold": 0.0,
        "low_vol_window": _int_match(text, r"vol_window=(\d+)", 20),
        "low_vol_quantile": _float_match(text, r"vol_q=([0-9.]+)", 0.5),
        "vol_threshold": 0.0,
        "low_turnover_quantile": _float_match(text, r"turnover_q=([0-9.]+)", 0.5),
        "turnover_threshold": 0.0,
        "momentum_window": _int_match(text, r",mom(\d+)", 20),
        "buy_top_n": _int_match(text, r",buy_top=(\d+)", 10),
        "hold_top_n": _int_match(text, r",hold_top=(\d+)", 20),
        "rebalance_days": _int_match(text, r",rebalance=(\d+)d", 20),
        "min_hold_days": _int_match(text, r",min_hold=(\d+)d", 20),
        "max_symbol_weight": _float_match(text, r",max_w=([0-9.]+)", float(cfg.get("max_symbol_weight", 0.10))),
        "target_vol": _float_match(text, r",target_vol=([0-9.]+)", float(cfg.get("target_vol", strategy_cfg.get("target_vol", 0.18)))),
        "use_xmarket_overlay": bool(cfg.get("use_xmarket_overlay", False)),
        "max_names_per_industry": _optional_int(constraints.get("max_names_per_industry")),
        "factor_weights": {
            "quality": float(weights_cfg.get("quality", 0.25)),
            "low_volatility": float(weights_cfg.get("low_volatility", 0.40)),
            "low_turnover": float(weights_cfg.get("low_turnover", 0.25)),
            "medium_momentum": float(weights_cfg.get("medium_momentum", 0.10)),
        },
        "turnover_penalty": _float_match(text, r",turnover_penalty=([0-9.]+)", 0.02),
        "train_score": 0.0,
        "train_sharpe": 0.0,
        "train_trades": 0,
        "train_turnover_annual": 0.0,
    }


def _complete_price_volume_params(params: dict[str, Any], train: pd.DataFrame) -> dict[str, Any]:
    if "quality_quantile" in params:
        return _complete_low_vol_quality_params(params, train)
    out = dict(params)
    resid_col = f"resid_mom{int(out['residual_window'])}"
    mom_col = f"mom{int(out['momentum_window'])}"
    industry_col = f"industry_relative_mom{int(out.get('industry_relative_window', out['momentum_window']))}"
    out["residual_threshold"] = _quantile_or_default(train, resid_col, float(out["residual_quantile"]))
    out["momentum_threshold"] = _quantile_or_default(train, mom_col, float(out["momentum_quantile"]))
    out["vol_threshold"] = _quantile_or_default(train, "vol20", float(out["vol_quantile"]))
    if bool(out.get("industry_relative_enabled", False)):
        out["industry_relative_threshold"] = _quantile_or_default(
            train,
            industry_col,
            float(out.get("industry_relative_quantile", 0.5)),
            default=-np.inf,
        )
    else:
        out["industry_relative_threshold"] = -np.inf
    return out


def _complete_low_vol_quality_params(params: dict[str, Any], train: pd.DataFrame) -> dict[str, Any]:
    out = dict(params)
    vol_col = f"vol{int(out.get('low_vol_window', 20))}"
    out["quality_threshold"] = _quantile_or_default(
        train,
        "quality_growth_score",
        float(out.get("quality_quantile", 0.6)),
        default=1.1,
    )
    out["vol_threshold"] = _quantile_or_default(
        train,
        vol_col,
        float(out.get("low_vol_quantile", 0.5)),
    )
    out["turnover_threshold"] = _quantile_or_default(
        train,
        "turnover_rate20",
        float(out.get("low_turnover_quantile", 0.5)),
    )
    return out


def _quantile_or_default(df: pd.DataFrame, column: str, quantile: float, default: float = 0.0) -> float:
    if column not in df.columns:
        return default
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    return float(values.quantile(float(quantile))) if not values.empty else default


def _int_match(text: str, pattern: str, default: int) -> int:
    match = re.search(pattern, text)
    return int(match.group(1)) if match else int(default)


def _float_match(text: str, pattern: str, default: float) -> float:
    match = re.search(pattern, text)
    return float(match.group(1)) if match else float(default)


def _bool_match(text: str, pattern: str, default: bool) -> bool:
    match = re.search(pattern, text)
    if not match:
        return bool(default)
    return match.group(1) == "True"


def _optional_int(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        parsed = int(value)
        return parsed if parsed > 0 else None
    except (TypeError, ValueError):
        return None


def _holding_rows_from_signal(signal_frame: pd.DataFrame, *, fold_row: dict[str, Any], context_row: dict[str, Any]) -> pd.DataFrame:
    if signal_frame is None or signal_frame.empty:
        return pd.DataFrame()
    signal = signal_frame.copy()
    _require_columns(signal, ["date", "symbol"], Path("signal_frame"))
    signal["date"] = pd.to_datetime(signal["date"], errors="coerce").dt.normalize()
    signal["symbol"] = signal["symbol"].astype(str)
    signal["target_weight"] = _numeric(signal.get("weight_unshifted", pd.Series(0.0, index=signal.index)))
    signal["live_weight"] = _numeric(signal.get("weight", pd.Series(0.0, index=signal.index)))
    active = signal[(signal["target_weight"].abs() > EPS) | (signal["live_weight"].abs() > EPS)].copy()
    if active.empty:
        return pd.DataFrame()
    active["industry"] = _clean_industry(active.get("industry", pd.Series(UNKNOWN_INDUSTRY, index=active.index)))
    if "name" not in active.columns:
        active["name"] = ""
    active["strategy_id"] = _safe_str(fold_row.get("strategy_id"))
    active["walk_forward_preset"] = _safe_str(fold_row.get("walk_forward_preset"))
    active["fold"] = _safe_int(fold_row.get("fold"))
    active["valid_start"] = _safe_str(fold_row.get("valid_start"))
    active["valid_end"] = _safe_str(fold_row.get("valid_end"))
    active["market_context_label"] = _safe_str(context_row.get("market_context_label", fold_row.get("market_context_label", "not_available")))
    active["benchmark_return_bucket"] = _safe_str(context_row.get("benchmark_return_bucket", fold_row.get("benchmark_return_bucket", "not_available")))
    active["benchmark_trend_bucket"] = _safe_str(context_row.get("benchmark_trend_bucket", fold_row.get("benchmark_trend_bucket", "not_available")))
    active["universe_as_of_date"] = _safe_str(fold_row.get("universe_as_of_date"))
    keep = [
        "strategy_id",
        "walk_forward_preset",
        "fold",
        "valid_start",
        "valid_end",
        "market_context_label",
        "benchmark_return_bucket",
        "benchmark_trend_bucket",
        "universe_as_of_date",
        "date",
        "symbol",
        "name",
        "industry",
        "target_weight",
        "live_weight",
        "selected",
        "rank",
        "score",
        "quality_growth_score",
        "quality_rank_component",
        "low_vol_rank_component",
        "low_turnover_rank_component",
        "medium_momentum_rank_component",
        "quality_roe_component",
        "quality_cash_flow_component",
        "quality_profit_growth_component",
        "quality_revenue_growth_component",
        "quality_low_debt_component",
        "financial_announce_date",
        "financial_available_fields",
        "ret",
        "position_ret",
        "mom20",
        "mom60",
        "amount_ratio20",
        "vol20",
        "held_days",
        "review_day",
        "review_reason",
        "dynamic_review_trigger",
        "strong_index_context",
        "recovery_index_context",
        "recovery_quality_index_context",
        "recovery_tradable_index_context",
        "recovery_breadth_mom20_positive_ratio",
        "recovery_breadth_mom60_positive_ratio",
        "recovery_breadth_industry_positive_ratio",
        "recovery_breadth_avg_amount_ratio20",
        "recovery_leadership_index_context",
        "recovery_leadership_stability_ratio",
        "recovery_leadership_top_industry",
        "strong_index_ret20",
        "strong_index_ret60",
        "strong_index_close",
        "strong_index_ma120",
        "strong_index_vol20",
        "strong_index_vol_threshold",
        "strong_index_drawdown",
    ]
    return active[[col for col in keep if col in active.columns]].sort_values(["walk_forward_preset", "fold", "date", "symbol"]).reset_index(drop=True)


def _daily_exposure_from_holdings(holdings: pd.DataFrame) -> pd.DataFrame:
    if holdings.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    keys = ["strategy_id", "walk_forward_preset", "fold", "valid_start", "valid_end", "market_context_label", "date"]
    for key, group in holdings.groupby(keys, dropna=False, sort=True):
        key_map = dict(zip(keys, key))
        live = group[group["live_weight"].abs() > EPS].copy()
        target = group[group["target_weight"].abs() > EPS].copy()
        live_industry = live.groupby("industry")["live_weight"].apply(lambda s: s.abs().sum()).sort_values(ascending=False)
        target_industry = target.groupby("industry")["target_weight"].apply(lambda s: s.abs().sum()).sort_values(ascending=False)
        context_metrics = _daily_context_metrics(group)
        rows.append(
            {
                **key_map,
                **context_metrics,
                "live_holding_count": int(live["symbol"].nunique()) if not live.empty else 0,
                "target_holding_count": int(target["symbol"].nunique()) if not target.empty else 0,
                "live_exposure": float(live["live_weight"].abs().sum()) if not live.empty else 0.0,
                "target_exposure": float(target["target_weight"].abs().sum()) if not target.empty else 0.0,
                "live_top_industry": _first_index(live_industry),
                "live_top_industry_share": float(live_industry.iloc[0]) if not live_industry.empty else 0.0,
                "live_top3_industries_share": float(live_industry.head(3).sum()) if not live_industry.empty else 0.0,
                "target_top_industry": _first_index(target_industry),
                "target_top_industry_share": float(target_industry.iloc[0]) if not target_industry.empty else 0.0,
                "target_top3_industries_share": float(target_industry.head(3).sum()) if not target_industry.empty else 0.0,
                "unknown_live_weight": float(live.loc[live["industry"] == UNKNOWN_INDUSTRY, "live_weight"].abs().sum()) if not live.empty else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values(["walk_forward_preset", "fold", "date"]).reset_index(drop=True)


def _daily_context_metrics(group: pd.DataFrame) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    if "strong_index_context" in group.columns:
        metrics["strong_index_context"] = bool(group["strong_index_context"].fillna(False).astype(bool).any())
    if "recovery_index_context" in group.columns:
        metrics["recovery_index_context"] = bool(group["recovery_index_context"].fillna(False).astype(bool).any())
    if "recovery_quality_index_context" in group.columns:
        metrics["recovery_quality_index_context"] = bool(
            group["recovery_quality_index_context"].fillna(False).astype(bool).any()
        )
    if "recovery_tradable_index_context" in group.columns:
        metrics["recovery_tradable_index_context"] = bool(
            group["recovery_tradable_index_context"].fillna(False).astype(bool).any()
        )
    if "recovery_leadership_index_context" in group.columns:
        metrics["recovery_leadership_index_context"] = bool(
            group["recovery_leadership_index_context"].fillna(False).astype(bool).any()
        )
    if "review_day" in group.columns:
        metrics["review_day_count"] = int(bool(group["review_day"].fillna(False).astype(bool).any()))
    if "dynamic_review_trigger" in group.columns:
        metrics["dynamic_review_trigger_count"] = int(
            bool(group["dynamic_review_trigger"].fillna(False).astype(bool).any())
        )
    if "review_reason" in group.columns:
        metrics["review_reason"] = _mode(group, "review_reason")
    for column in [
        "strong_index_ret20",
        "strong_index_ret60",
        "strong_index_close",
        "strong_index_ma120",
        "strong_index_vol20",
        "strong_index_vol_threshold",
        "strong_index_drawdown",
        "recovery_breadth_mom20_positive_ratio",
        "recovery_breadth_mom60_positive_ratio",
        "recovery_breadth_industry_positive_ratio",
        "recovery_breadth_avg_amount_ratio20",
        "recovery_leadership_stability_ratio",
    ]:
        if column in group.columns:
            metrics[column] = _first_non_null_numeric(group[column])
    if "recovery_leadership_top_industry" in group.columns:
        metrics["recovery_leadership_top_industry"] = _mode(group, "recovery_leadership_top_industry")
    return metrics


def _industry_exposure_from_holdings(holdings: pd.DataFrame) -> pd.DataFrame:
    if holdings.empty:
        return pd.DataFrame()
    group_cols = ["strategy_id", "walk_forward_preset", "fold", "market_context_label", "date", "industry"]
    grouped = holdings.groupby(group_cols, dropna=False).agg(
        live_weight=("live_weight", lambda s: float(pd.to_numeric(s, errors="coerce").fillna(0.0).abs().sum())),
        target_weight=("target_weight", lambda s: float(pd.to_numeric(s, errors="coerce").fillna(0.0).abs().sum())),
        live_name_count=("symbol", lambda s: int(holdings.loc[s.index, "live_weight"].abs().gt(EPS).sum())),
        target_name_count=("symbol", lambda s: int(holdings.loc[s.index, "target_weight"].abs().gt(EPS).sum())),
    )
    return grouped.reset_index().sort_values(["walk_forward_preset", "fold", "date", "live_weight"], ascending=[True, True, True, False])


def _summary_from_daily(daily: pd.DataFrame, fold_df: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    group_cols = ["market_context_label"]
    for label, group in daily.groupby(group_cols, dropna=False):
        label_text = _safe_str(label[0] if isinstance(label, tuple) else label)
        fold_keys = group[["walk_forward_preset", "fold"]].drop_duplicates()
        related_folds = fold_df.merge(fold_keys, on=["walk_forward_preset", "fold"], how="inner") if not fold_df.empty else pd.DataFrame()
        rows.append(
            {
                "market_context_label": label_text,
                "fold_count": int(len(fold_keys)),
                "daily_count": int(len(group)),
                "avg_strategy_ann": _mean(related_folds, "annualized_return"),
                "avg_benchmark_ann": _mean(related_folds, "benchmark_annualized_return"),
                "avg_excess_ann": _mean(related_folds, "excess_annualized_return"),
                "avg_live_holding_count": _mean(group, "live_holding_count"),
                "avg_target_holding_count": _mean(group, "target_holding_count"),
                "avg_live_exposure": _mean(group, "live_exposure"),
                "avg_target_exposure": _mean(group, "target_exposure"),
                "avg_live_top_industry_share": _mean(group, "live_top_industry_share"),
                "p95_live_top_industry_share": _quantile(group, "live_top_industry_share", 0.95),
                "max_live_top_industry_share": _max(group, "live_top_industry_share"),
                "avg_live_top3_industries_share": _mean(group, "live_top3_industries_share"),
                "dominant_live_top_industry": _mode(group, "live_top_industry"),
                "avg_unknown_live_weight": _mean(group, "unknown_live_weight"),
                "interpretation": _summary_interpretation(label_text, group, related_folds),
            }
        )
    return pd.DataFrame(rows).sort_values(["fold_count", "market_context_label"], ascending=[False, True]).reset_index(drop=True)


def _coverage_summary(
    *,
    holdings_df: pd.DataFrame,
    daily_df: pd.DataFrame,
    fold_df: pd.DataFrame,
    audit_df: pd.DataFrame,
    benchmark_symbol: str,
    local_history_db: Path | None = None,
) -> pd.DataFrame:
    constituent_status = _benchmark_constituent_status(local_history_db, benchmark_symbol)
    return pd.DataFrame(
        [
            {
                "artifact": "strategy_daily_holdings",
                "status": "available" if not holdings_df.empty else "empty",
                "rows": int(len(holdings_df)),
                "note": "daily target/live holdings rebuilt from fold-local strategy signal_frame",
            },
            {
                "artifact": "strategy_daily_exposure",
                "status": "available" if not daily_df.empty else "empty",
                "rows": int(len(daily_df)),
                "note": "daily strategy industry concentration summary",
            },
            {
                "artifact": "fold_point_in_time_universe",
                "status": "available" if not audit_df.empty else "empty",
                "rows": int(len(audit_df)),
                "note": "industry metadata comes from fold-local PIT universe snapshots",
            },
            {
                "artifact": "benchmark_index_price",
                "status": _benchmark_price_status(benchmark_symbol, daily_df),
                "rows": int(len(daily_df)),
                "note": f"{benchmark_symbol} price context can be joined by date; this is not constituent exposure",
            },
            {
                "artifact": "benchmark_constituents",
                "status": constituent_status["status"],
                "rows": constituent_status["rows"],
                "note": constituent_status["note"],
            },
            {
                "artifact": "benchmark_style_exposure",
                "status": "not_available",
                "rows": 0,
                "note": "cannot claim full holdings-vs-CSI300 style attribution without constituent weights or style factors",
            },
            {
                "artifact": "fold_metrics",
                "status": "available" if not fold_df.empty else "empty",
                "rows": int(len(fold_df)),
                "note": "fold metrics rebuilt for audit only; no admission action is changed",
            },
        ]
    )


def _benchmark_constituent_status(local_history_db: Path | None, benchmark_symbol: str) -> dict[str, Any]:
    if local_history_db is None or not local_history_db.exists():
        return {
            "status": "not_available",
            "rows": 0,
            "note": "local history sqlite is unavailable; run index-asof-audit before full CSI300 weight attribution",
        }
    try:
        with sqlite3.connect(local_history_db) as conn:
            has_table = bool(
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
                    ("cn_index_weights_asof",),
                ).fetchone()
            )
            if not has_table:
                return {
                    "status": "not_available",
                    "rows": 0,
                    "note": "no cn_index_weights_asof table found; holdings exposure alone cannot do full CSI300 weight attribution",
                }
            rows = conn.execute(
                "SELECT COUNT(*) FROM cn_index_weights_asof WHERE index_code = ?",
                (benchmark_symbol,),
            ).fetchone()[0]
    except sqlite3.Error as exc:
        return {
            "status": "error",
            "rows": 0,
            "note": f"failed to inspect cn_index_weights_asof: {exc}",
        }
    if int(rows) <= 0:
        return {
            "status": "empty",
            "rows": 0,
            "note": f"cn_index_weights_asof exists but has no rows for {benchmark_symbol}",
        }
    return {
        "status": "available",
        "rows": int(rows),
        "note": "cn_index_weights_asof is available for follow-up CSI300 constituent weight attribution",
    }


def _benchmark_daily_features(benchmark_symbol: str, daily_df: pd.DataFrame) -> pd.DataFrame:
    if daily_df.empty or "date" not in daily_df.columns:
        return pd.DataFrame()
    dates = pd.to_datetime(daily_df["date"], errors="coerce").dropna()
    if dates.empty:
        return pd.DataFrame()
    try:
        index = load_index_daily_from_local_history(benchmark_symbol, dates.min().date(), dates.max().date())
    except (sqlite3.Error, pd.errors.DatabaseError):
        return pd.DataFrame()
    if index.empty or "close" not in index.columns:
        return pd.DataFrame()
    out = index[["date", "close"]].copy().sort_values("date")
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out["benchmark_close"] = pd.to_numeric(out["close"], errors="coerce")
    out["benchmark_daily_return"] = out["benchmark_close"].pct_change()
    return out[["date", "benchmark_close", "benchmark_daily_return"]]


def _benchmark_price_status(benchmark_symbol: str, daily_df: pd.DataFrame) -> str:
    if daily_df.empty or "date" not in daily_df.columns:
        return "empty"
    dates = pd.to_datetime(daily_df["date"], errors="coerce").dropna()
    if dates.empty:
        return "empty"
    try:
        index = load_index_daily_from_local_history(benchmark_symbol, dates.min().date(), dates.max().date())
    except (sqlite3.Error, pd.errors.DatabaseError):
        return "not_available"
    return "available" if not index.empty else "not_available"


def _write_markdown(
    path: Path,
    *,
    summary_df: pd.DataFrame,
    coverage_df: pd.DataFrame,
    candidate_folds_path: Path,
    market_context_path: Path,
    strategy_id: str,
) -> None:
    lines = [
        "# Strategy Holdings Exposure Diagnostic",
        "",
        "This is a research-only diagnostic. It rebuilds daily strategy holdings for existing fold evidence and does not rerun admission, change strategy weights, or create trading signals.",
        "",
        "## Scope",
        "",
        f"- Strategy: `{strategy_id}`",
        f"- Candidate folds: `{candidate_folds_path}`",
        f"- Market context: `{market_context_path}`",
        "- Boundary: holdings/industry exposure only; CSI300 constituent and style exposure are explicitly marked unavailable when no local table exists.",
        "",
        "## Summary",
        "",
    ]
    if summary_df.empty:
        lines.append("No daily holdings exposure rows were generated.")
    else:
        cols = [
            "market_context_label",
            "fold_count",
            "daily_count",
            "avg_strategy_ann",
            "avg_benchmark_ann",
            "avg_excess_ann",
            "avg_live_holding_count",
            "avg_live_exposure",
            "avg_live_top_industry_share",
            "avg_live_top3_industries_share",
            "dominant_live_top_industry",
            "interpretation",
        ]
        lines.extend(_markdown_table(summary_df[[col for col in cols if col in summary_df.columns]]))
    lines.extend(["", "## Coverage", ""])
    lines.extend(_markdown_table(coverage_df))
    lines.extend(
        [
            "",
            "## Decision Boundary",
            "",
            "- This diagnostic can support a holdings breadth and industry concentration discussion.",
            "- It cannot prove CSI300 constituent underweight or style underexposure until benchmark constituents/weights or style factors are available.",
            "- Admission, paper review, simulated trading, daily brief, and watchlist eligibility are unchanged.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_run_log(
    path: Path,
    *,
    config: dict[str, Any],
    root: Path,
    output_dir: Path,
    output_artifacts: list[Path],
    config_path: Path | None,
    candidate_folds_path: Path,
    market_context_path: Path,
    command: str | None,
) -> None:
    git_head = _git(["rev-parse", "--short", "HEAD"], root)
    git_status = _git(["status", "--short"], root)
    lines = [
        "# Strategy Holdings Exposure Run Log",
        "",
        f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
        "- iteration_id: `I10`",
        "- diagnostic_type: `daily_holdings_exposure`",
        "- promotion_boundary: `research_only; no admission rerun; no trading rule`",
        f"- config_path: `{config_path}`",
        f"- candidate_folds_path: `{candidate_folds_path}`",
        f"- market_context_path: `{market_context_path}`",
        f"- output_dir: `{output_dir}`",
        f"- benchmark_symbol: `{config.get('benchmark_symbol', 'SH.000300')}`",
        f"- command: `{command or ''}`",
        f"- git_head: `{git_head}`",
        "",
        "## Artifact Hashes",
        "",
    ]
    for artifact in output_artifacts:
        lines.append(f"- `{artifact}` sha256=`{_sha256(artifact)}`")
    lines.extend(["", "## Git Status At Run", "", "```text", git_status.strip() or "clean", "```", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _read_required_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    return pd.read_csv(path)


def _require_columns(df: pd.DataFrame, columns: list[str], path: Path) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"{path} missing required columns: {', '.join(missing)}")


def _validate_unique_keys(df: pd.DataFrame, keys: list[str], path: Path) -> None:
    if df.empty:
        return
    duplicate_count = int(df.duplicated(keys).sum())
    if duplicate_count:
        examples = df.loc[df.duplicated(keys, keep=False), keys].head(5).to_dict("records")
        raise ValueError(f"{path} has duplicate keys: count={duplicate_count}, examples={examples}")


def _ensure_optional_fold_metric_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for column in ["benchmark_annualized_return", "excess_annualized_return"]:
        if column not in out.columns:
            out[column] = np.nan
    return out


def _ordered_presets(df: pd.DataFrame) -> list[str]:
    seen: list[str] = []
    for value in df["walk_forward_preset"].astype(str).tolist():
        if value not in seen:
            seen.append(value)
    return seen


def _concat_or_empty(frames: list[pd.DataFrame]) -> pd.DataFrame:
    frames = [frame for frame in frames if frame is not None and not frame.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _numeric(values: Any) -> pd.Series:
    return pd.to_numeric(values, errors="coerce").fillna(0.0)


def _clean_industry(values: Any) -> pd.Series:
    series = pd.Series(values).fillna(UNKNOWN_INDUSTRY).astype(str).str.strip()
    return series.mask(series.eq("") | series.str.lower().eq("nan"), UNKNOWN_INDUSTRY)


def _first_index(series: pd.Series) -> str:
    return _safe_str(series.index[0]) if not series.empty else ""


def _first_non_null_numeric(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna()
    return float(values.iloc[0]) if not values.empty else 0.0


def _mean(df: pd.DataFrame, column: str) -> float:
    if df.empty or column not in df.columns:
        return 0.0
    values = pd.to_numeric(df[column], errors="coerce")
    return float(values.mean()) if values.notna().any() else 0.0


def _max(df: pd.DataFrame, column: str) -> float:
    if df.empty or column not in df.columns:
        return 0.0
    values = pd.to_numeric(df[column], errors="coerce")
    return float(values.max()) if values.notna().any() else 0.0


def _quantile(df: pd.DataFrame, column: str, q: float) -> float:
    if df.empty or column not in df.columns:
        return 0.0
    values = pd.to_numeric(df[column], errors="coerce")
    return float(values.quantile(q)) if values.notna().any() else 0.0


def _mode(df: pd.DataFrame, column: str) -> str:
    if df.empty or column not in df.columns:
        return ""
    values = df[column].dropna().astype(str)
    values = values[values.str.strip().ne("")]
    return str(values.mode().iloc[0]) if not values.empty else ""


def _summary_interpretation(label: str, group: pd.DataFrame, folds: pd.DataFrame) -> str:
    avg_excess = _mean(folds, "excess_annualized_return")
    avg_live = _mean(group, "avg_live_exposure") if "avg_live_exposure" in group.columns else _mean(group, "live_exposure")
    top1 = _mean(group, "live_top_industry_share")
    if label == "relative_lag_in_strong_benchmark_context":
        return (
            f"Strong benchmark context: average excess {avg_excess:.2%}; "
            f"average live exposure {avg_live:.2%}; top industry share {top1:.2%}. "
            "This supports a holdings-breadth/concentration check, not a full CSI300 constituent attribution."
        )
    return (
        f"Control context: average excess {avg_excess:.2%}; "
        f"average live exposure {avg_live:.2%}; top industry share {top1:.2%}."
    )


def _safe_str(value: Any) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    return str(value)


def _safe_int(value: Any) -> int:
    try:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _markdown_table(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return ["_No rows._"]
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_float_dtype(out[col]):
            out[col] = out[col].map(lambda v: "" if pd.isna(v) else f"{float(v):.4f}")
        else:
            out[col] = out[col].fillna("").astype(str)
    headers = list(out.columns)
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["----"] * len(headers)) + " |"]
    for _, row in out.iterrows():
        lines.append("| " + " | ".join(str(row[col]).replace("\n", " ") for col in headers) + " |")
    return lines


def _git(args: list[str], root: Path) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "not_available"


def _sha256(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
