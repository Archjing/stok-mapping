from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


EPS = 1e-12


@dataclass(frozen=True)
class StrategyParticipationOverlayResult:
    daily_csv_path: Path
    summary_csv_path: Path
    report_md_path: Path
    run_log_md_path: Path
    daily_rows: int
    summary_rows: int


def run_strategy_participation_overlay(
    *,
    config: dict[str, Any],
    root: Path,
    holdings_path: Path,
    daily_exposure_path: Path,
    output_dir: Path,
    min_exposure: float = 0.65,
    max_symbol_weight: float = 0.10,
    max_scale: float = 2.0,
    context_label: str = "relative_lag_in_strong_benchmark_context",
    config_path: Path | None = None,
    command: str | None = None,
) -> StrategyParticipationOverlayResult:
    """Run a research-only counterfactual minimum-exposure overlay on rebuilt holdings."""
    output_dir.mkdir(parents=True, exist_ok=True)
    holdings = _read_required_csv(holdings_path, "strategy_daily_holdings.csv")
    daily_exposure = _read_required_csv(daily_exposure_path, "strategy_daily_exposure.csv")
    _require_columns(
        holdings,
        ["strategy_id", "walk_forward_preset", "fold", "date", "symbol", "market_context_label", "live_weight", "ret"],
        holdings_path,
    )
    _require_columns(
        daily_exposure,
        ["walk_forward_preset", "fold", "date", "market_context_label"],
        daily_exposure_path,
    )
    holdings = holdings.copy()
    daily_exposure = daily_exposure.copy()
    holdings["date"] = pd.to_datetime(holdings["date"], errors="coerce").dt.normalize()
    daily_exposure["date"] = pd.to_datetime(daily_exposure["date"], errors="coerce").dt.normalize()
    if context_label and context_label != "all":
        holdings = holdings[holdings["market_context_label"].astype(str) == context_label].copy()
        daily_exposure = daily_exposure[daily_exposure["market_context_label"].astype(str) == context_label].copy()
    if holdings.empty:
        raise ValueError(f"no holdings rows available for context_label={context_label!r}")

    costs = _costs(config)
    daily = _overlay_daily_rows(
        holdings,
        daily_exposure,
        min_exposure=float(min_exposure),
        max_symbol_weight=float(max_symbol_weight),
        max_scale=float(max_scale),
        slippage=costs["slippage"],
        commission=costs["commission"],
        stamp_duty_sell=costs["stamp_duty_sell"],
    )
    summary = _overlay_summary(daily)

    daily_csv_path = output_dir / "strategy_participation_overlay_daily.csv"
    summary_csv_path = output_dir / "strategy_participation_overlay_summary.csv"
    report_md_path = output_dir / "strategy_participation_overlay_report.md"
    run_log_md_path = output_dir / "strategy_participation_overlay_run_log.md"
    daily.to_csv(daily_csv_path, index=False)
    summary.to_csv(summary_csv_path, index=False)
    _write_markdown(
        report_md_path,
        summary=summary,
        context_label=context_label,
        min_exposure=min_exposure,
        max_symbol_weight=max_symbol_weight,
        max_scale=max_scale,
        holdings_path=holdings_path,
        daily_exposure_path=daily_exposure_path,
    )
    _write_run_log(
        run_log_md_path,
        root=root,
        output_dir=output_dir,
        artifacts=[daily_csv_path, summary_csv_path, report_md_path],
        config_path=config_path,
        holdings_path=holdings_path,
        daily_exposure_path=daily_exposure_path,
        command=command,
        params={
            "min_exposure": min_exposure,
            "max_symbol_weight": max_symbol_weight,
            "max_scale": max_scale,
            "context_label": context_label,
            **costs,
        },
    )
    return StrategyParticipationOverlayResult(
        daily_csv_path=daily_csv_path,
        summary_csv_path=summary_csv_path,
        report_md_path=report_md_path,
        run_log_md_path=run_log_md_path,
        daily_rows=len(daily),
        summary_rows=len(summary),
    )


def _overlay_daily_rows(
    holdings: pd.DataFrame,
    daily_exposure: pd.DataFrame,
    *,
    min_exposure: float,
    max_symbol_weight: float,
    max_scale: float,
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
) -> pd.DataFrame:
    h = holdings.copy()
    h["live_weight"] = pd.to_numeric(h["live_weight"], errors="coerce").fillna(0.0)
    h["ret"] = pd.to_numeric(h["ret"], errors="coerce").fillna(0.0)
    h["symbol"] = h["symbol"].astype(str)
    group_cols = ["strategy_id", "walk_forward_preset", "fold", "market_context_label", "date"]
    frames: list[pd.DataFrame] = []
    for _, group in h.groupby(group_cols, dropna=False, sort=True):
        day = group.copy()
        exposure = float(day["live_weight"].abs().sum())
        if exposure <= EPS or exposure >= min_exposure:
            scale = 1.0
        else:
            scale = min(float(max_scale), float(min_exposure) / exposure)
        scaled = day["live_weight"] * scale
        capped = scaled.clip(lower=-float(max_symbol_weight), upper=float(max_symbol_weight))
        day["overlay_scale"] = scale
        day["overlay_live_weight"] = capped
        day["overlay_live_exposure"] = float(capped.abs().sum())
        day["base_position_ret"] = day["live_weight"] * day["ret"]
        day["overlay_position_ret"] = day["overlay_live_weight"] * day["ret"]
        frames.append(day)
    expanded = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if expanded.empty:
        return pd.DataFrame()

    rows: list[pd.DataFrame] = []
    fold_cols = ["strategy_id", "walk_forward_preset", "fold", "market_context_label"]
    for _, group in expanded.groupby(fold_cols, dropna=False, sort=True):
        group = group.copy().sort_values(["date", "symbol"])
        base_weights = group.pivot(index="date", columns="symbol", values="live_weight").fillna(0.0).sort_index()
        overlay_weights = group.pivot(index="date", columns="symbol", values="overlay_live_weight").fillna(0.0).sort_index()
        base_cost = _daily_cost(base_weights, slippage=slippage, commission=commission, stamp_duty_sell=stamp_duty_sell)
        overlay_cost = _daily_cost(overlay_weights, slippage=slippage, commission=commission, stamp_duty_sell=stamp_duty_sell)
        daily = group.groupby(["strategy_id", "walk_forward_preset", "fold", "market_context_label", "date"], dropna=False).agg(
            base_gross_return=("base_position_ret", "sum"),
            overlay_gross_return=("overlay_position_ret", "sum"),
            base_live_exposure=("live_weight", lambda s: float(pd.to_numeric(s, errors="coerce").fillna(0.0).abs().sum())),
            overlay_live_exposure=("overlay_live_weight", lambda s: float(pd.to_numeric(s, errors="coerce").fillna(0.0).abs().sum())),
            overlay_scale=("overlay_scale", "max"),
            live_holding_count=("live_weight", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0.0).abs().gt(EPS).sum())),
        ).reset_index()
        daily = daily.merge(base_cost.rename("base_cost"), left_on="date", right_index=True, how="left")
        daily = daily.merge(overlay_cost.rename("overlay_cost"), left_on="date", right_index=True, how="left")
        daily["base_net_return"] = daily["base_gross_return"] - daily["base_cost"].fillna(0.0)
        daily["overlay_net_return"] = daily["overlay_gross_return"] - daily["overlay_cost"].fillna(0.0)
        rows.append(daily)
    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    benchmark_cols = [
        col
        for col in ["walk_forward_preset", "fold", "date", "benchmark_daily_return", "benchmark_close"]
        if col in daily_exposure.columns
    ]
    if {"walk_forward_preset", "fold", "date"}.issubset(benchmark_cols):
        out = out.merge(daily_exposure[benchmark_cols].drop_duplicates(["walk_forward_preset", "fold", "date"]), on=["walk_forward_preset", "fold", "date"], how="left")
    out["base_excess_return"] = out["base_net_return"] - pd.to_numeric(out.get("benchmark_daily_return", 0.0), errors="coerce").fillna(0.0)
    out["overlay_excess_return"] = out["overlay_net_return"] - pd.to_numeric(out.get("benchmark_daily_return", 0.0), errors="coerce").fillna(0.0)
    return out.sort_values(["walk_forward_preset", "fold", "date"]).reset_index(drop=True)


def _daily_cost(
    weights: pd.DataFrame,
    *,
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
) -> pd.Series:
    turnover = weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1))
    sells = weights.diff().clip(upper=0).abs().sum(axis=1).fillna(0.0)
    return turnover * (float(slippage) + float(commission)) + sells * float(stamp_duty_sell)


def _overlay_summary(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    group_cols = ["walk_forward_preset", "fold", "market_context_label"]
    for key, group in daily.groupby(group_cols, dropna=False, sort=True):
        key_map = dict(zip(group_cols, key))
        rows.append({**key_map, **_summary_metrics(group, scope="fold")})
    rows.append({"walk_forward_preset": "ALL", "fold": 0, "market_context_label": "ALL", **_summary_metrics(daily, scope="all")})
    return pd.DataFrame(rows)


def _summary_metrics(group: pd.DataFrame, *, scope: str) -> dict[str, Any]:
    base = pd.to_numeric(group["base_net_return"], errors="coerce").fillna(0.0)
    overlay = pd.to_numeric(group["overlay_net_return"], errors="coerce").fillna(0.0)
    benchmark = pd.to_numeric(group.get("benchmark_daily_return", pd.Series(0.0, index=group.index)), errors="coerce").fillna(0.0)
    return {
        "scope": scope,
        "days": int(len(group)),
        "base_annualized_return": _annualized_return(base),
        "overlay_annualized_return": _annualized_return(overlay),
        "benchmark_annualized_return": _annualized_return(benchmark),
        "base_excess_annualized_return": _annualized_return(base) - _annualized_return(benchmark),
        "overlay_excess_annualized_return": _annualized_return(overlay) - _annualized_return(benchmark),
        "overlay_minus_base_annualized_return": _annualized_return(overlay) - _annualized_return(base),
        "base_sharpe": _sharpe(base),
        "overlay_sharpe": _sharpe(overlay),
        "base_max_drawdown": _max_drawdown(base),
        "overlay_max_drawdown": _max_drawdown(overlay),
        "avg_base_live_exposure": float(pd.to_numeric(group["base_live_exposure"], errors="coerce").mean()),
        "avg_overlay_live_exposure": float(pd.to_numeric(group["overlay_live_exposure"], errors="coerce").mean()),
        "avg_overlay_scale": float(pd.to_numeric(group["overlay_scale"], errors="coerce").mean()),
        "avg_live_holding_count": float(pd.to_numeric(group["live_holding_count"], errors="coerce").mean()),
        "base_total_cost": float(pd.to_numeric(group["base_cost"], errors="coerce").fillna(0.0).sum()),
        "overlay_total_cost": float(pd.to_numeric(group["overlay_cost"], errors="coerce").fillna(0.0).sum()),
        "interpretation": _interpretation(_annualized_return(base), _annualized_return(overlay), _annualized_return(benchmark)),
    }


def _annualized_return(r: pd.Series) -> float:
    r = pd.to_numeric(r, errors="coerce").fillna(0.0)
    if r.empty:
        return 0.0
    cum = float((1.0 + r).prod() - 1.0)
    years = max(len(r) / 252.0, 1 / 252.0)
    return float((1.0 + cum) ** (1.0 / years) - 1.0)


def _sharpe(r: pd.Series) -> float:
    r = pd.to_numeric(r, errors="coerce").fillna(0.0)
    if len(r) < 2:
        return 0.0
    std = float(r.std(ddof=1))
    if std <= EPS:
        return 0.0
    return float((r.mean() / std) * np.sqrt(252))


def _max_drawdown(r: pd.Series) -> float:
    r = pd.to_numeric(r, errors="coerce").fillna(0.0)
    if r.empty:
        return 0.0
    eq = (1.0 + r).cumprod()
    return float((eq / eq.cummax() - 1.0).min())


def _interpretation(base_ann: float, overlay_ann: float, benchmark_ann: float) -> str:
    if overlay_ann > base_ann and overlay_ann < benchmark_ann:
        return "overlay improves participation but still lags benchmark"
    if overlay_ann > base_ann and overlay_ann >= benchmark_ann:
        return "overlay closes the strong-benchmark lag in this counterfactual scope"
    return "overlay does not improve this counterfactual scope"


def _costs(config: dict[str, Any]) -> dict[str, float]:
    wcfg = config.get("walk_forward", {})
    return {
        "slippage": float(wcfg.get("slippage", 0.0)),
        "commission": float(wcfg.get("commission", 0.0)),
        "stamp_duty_sell": float(wcfg.get("stamp_duty_sell", 0.0)),
    }


def _write_markdown(
    path: Path,
    *,
    summary: pd.DataFrame,
    context_label: str,
    min_exposure: float,
    max_symbol_weight: float,
    max_scale: float,
    holdings_path: Path,
    daily_exposure_path: Path,
) -> None:
    lines = [
        "# Strategy Participation Overlay Counterfactual",
        "",
        "This is a research-only counterfactual. It rescales existing daily live holdings and does not change strategy code, admission, paper-review status, or trading eligibility.",
        "",
        "## Setup",
        "",
        f"- Context label: `{context_label}`",
        f"- Minimum exposure: `{min_exposure:.2%}`",
        f"- Max symbol weight: `{max_symbol_weight:.2%}`",
        f"- Max scale: `{max_scale:.2f}`",
        f"- Holdings input: `{holdings_path}`",
        f"- Daily exposure input: `{daily_exposure_path}`",
        "",
        "## Summary",
        "",
    ]
    lines.extend(_markdown_table(summary))
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This is not a valid trading rule by itself because it is applied to a diagnostic context slice.",
            "- It answers whether low exposure could plausibly explain strong-benchmark lag.",
            "- If useful, the next step must be a pre-registered T-1 benchmark regime rule implemented as a separate research candidate.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_run_log(
    path: Path,
    *,
    root: Path,
    output_dir: Path,
    artifacts: list[Path],
    config_path: Path | None,
    holdings_path: Path,
    daily_exposure_path: Path,
    command: str | None,
    params: dict[str, Any],
) -> None:
    lines = [
        "# Strategy Participation Overlay Run Log",
        "",
        f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
        "- iteration_id: `I11`",
        "- diagnostic_type: `participation_overlay_counterfactual`",
        "- promotion_boundary: `research_only; no admission rerun; no trading rule`",
        f"- config_path: `{config_path}`",
        f"- holdings_path: `{holdings_path}`",
        f"- daily_exposure_path: `{daily_exposure_path}`",
        f"- output_dir: `{output_dir}`",
        f"- command: `{command or ''}`",
        f"- git_head: `{_git(['rev-parse', '--short', 'HEAD'], root)}`",
        "",
        "## Parameters",
        "",
    ]
    for key, value in params.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Artifact Hashes", ""])
    for artifact in artifacts:
        lines.append(f"- `{artifact}` sha256=`{_sha256(artifact)}`")
    lines.extend(["", "## Git Status At Run", "", "```text", _git(["status", "--short"], root).strip() or "clean", "```", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _read_required_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    return pd.read_csv(path)


def _require_columns(df: pd.DataFrame, columns: list[str], path: Path) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"{path} missing required columns: {', '.join(missing)}")


def _markdown_table(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return ["_No rows._"]
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_float_dtype(out[col]):
            out[col] = out[col].map(lambda value: "" if pd.isna(value) else f"{float(value):.4f}")
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
