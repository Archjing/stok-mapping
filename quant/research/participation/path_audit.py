from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class StrategyParticipationPathAuditResult:
    daily_csv_path: Path
    summary_csv_path: Path
    report_md_path: Path
    daily_rows: int
    summary_rows: int


def run_strategy_participation_path_audit(
    *,
    daily_exposure_path: Path,
    output_dir: Path,
    target_high_threshold: float = 0.80,
    live_low_threshold: float = 0.50,
) -> StrategyParticipationPathAuditResult:
    """Audit whether intended high participation becomes live exposure."""
    output_dir.mkdir(parents=True, exist_ok=True)
    daily = _read_daily_exposure(daily_exposure_path)
    audited = _daily_audit(
        daily,
        target_high_threshold=float(target_high_threshold),
        live_low_threshold=float(live_low_threshold),
    )
    summary = _summary(audited)

    daily_path = output_dir / "strategy_participation_path_daily.csv"
    summary_path = output_dir / "strategy_participation_path_summary.csv"
    md_path = output_dir / "strategy_participation_path_audit.md"
    audited.to_csv(daily_path, index=False)
    summary.to_csv(summary_path, index=False)
    _write_markdown(
        md_path,
        daily_exposure_path=daily_exposure_path,
        summary=summary,
        target_high_threshold=target_high_threshold,
        live_low_threshold=live_low_threshold,
    )
    return StrategyParticipationPathAuditResult(
        daily_csv_path=daily_path,
        summary_csv_path=summary_path,
        report_md_path=md_path,
        daily_rows=len(audited),
        summary_rows=len(summary),
    )


def _read_daily_exposure(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"daily exposure not found: {path}")
    daily = pd.read_csv(path)
    _require_columns(
        daily,
        [
            "strategy_id",
            "walk_forward_preset",
            "fold",
            "market_context_label",
            "date",
            "target_exposure",
            "live_exposure",
        ],
        path,
    )
    out = daily.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.date.astype(str)
    out["fold"] = pd.to_numeric(out["fold"], errors="coerce").fillna(0).astype(int)
    out["target_exposure"] = pd.to_numeric(out["target_exposure"], errors="coerce").fillna(0.0)
    out["live_exposure"] = pd.to_numeric(out["live_exposure"], errors="coerce").fillna(0.0)
    return out


def _daily_audit(
    daily: pd.DataFrame,
    *,
    target_high_threshold: float,
    live_low_threshold: float,
) -> pd.DataFrame:
    group_keys = ["strategy_id", "walk_forward_preset", "fold"]
    out = daily.copy().sort_values([*group_keys, "date"]).reset_index(drop=True)
    out["previous_target_exposure"] = out.groupby(group_keys, dropna=False)["target_exposure"].shift(1)
    out["target_exposure_bucket"] = out["target_exposure"].map(_target_bucket)
    out["live_exposure_bucket"] = out["live_exposure"].map(_live_bucket)
    out["target_minus_live_exposure"] = (out["target_exposure"] - out["live_exposure"]).round(12)
    out["abs_live_minus_target_exposure"] = (out["live_exposure"] - out["target_exposure"]).abs().round(12)
    out["abs_live_minus_previous_target_exposure"] = (
        out["live_exposure"] - out["previous_target_exposure"]
    ).abs().round(12)
    out["is_high_target_day"] = out["target_exposure"].ge(target_high_threshold)
    out["is_low_live_day"] = out["live_exposure"].lt(live_low_threshold)
    out["is_low_live_after_high_target"] = out["is_high_target_day"] & out["is_low_live_day"]
    keep = [
        "strategy_id",
        "walk_forward_preset",
        "fold",
        "valid_start",
        "valid_end",
        "market_context_label",
        "date",
        "target_exposure",
        "previous_target_exposure",
        "live_exposure",
        "target_minus_live_exposure",
        "abs_live_minus_target_exposure",
        "abs_live_minus_previous_target_exposure",
        "target_exposure_bucket",
        "live_exposure_bucket",
        "is_high_target_day",
        "is_low_live_day",
        "is_low_live_after_high_target",
        "benchmark_daily_return",
        "target_top_industry",
        "live_top_industry",
    ]
    return out[[col for col in keep if col in out.columns]].sort_values(["fold", "date"]).reset_index(drop=True)


def _summary(audited: pd.DataFrame) -> pd.DataFrame:
    keys = ["strategy_id", "walk_forward_preset", "fold", "market_context_label"]
    rows: list[dict[str, object]] = []
    for key, group in audited.groupby(keys, dropna=False, sort=True):
        key_map = dict(zip(keys, key))
        rows.append(
            {
                **key_map,
                "days": int(len(group)),
                "avg_target_exposure": round(float(group["target_exposure"].mean()), 6),
                "avg_live_exposure": round(float(group["live_exposure"].mean()), 6),
                "avg_target_minus_live_exposure": round(float(group["target_minus_live_exposure"].mean()), 6),
                "high_target_days": int(group["is_high_target_day"].sum()),
                "low_live_days": int(group["is_low_live_day"].sum()),
                "low_live_after_high_target_days": int(group["is_low_live_after_high_target"].sum()),
                "days_with_previous_target": int(group["previous_target_exposure"].notna().sum()),
                "avg_abs_live_minus_target_exposure": round(
                    float(group["abs_live_minus_target_exposure"].mean()),
                    6,
                ),
                "avg_abs_live_minus_previous_target_exposure": round(
                    float(group["abs_live_minus_previous_target_exposure"].mean()),
                    6,
                ),
                "target_bucket_counts": _bucket_counts(group["target_exposure_bucket"]),
                "live_bucket_counts": _bucket_counts(group["live_exposure_bucket"]),
            }
        )
    return pd.DataFrame(rows).sort_values(["fold", "market_context_label"]).reset_index(drop=True)


def _target_bucket(value: float) -> str:
    if value >= 0.80:
        return "strong_high"
    if value >= 0.30:
        return "mixed_mid"
    return "risk_or_low"


def _live_bucket(value: float) -> str:
    if value >= 0.80:
        return "high_live"
    if value >= 0.50:
        return "mid_live"
    if value >= 0.20:
        return "low_mid_live"
    return "low_live"


def _bucket_counts(series: pd.Series) -> str:
    counts = series.astype(str).value_counts().sort_index()
    return "; ".join(f"{key}={int(value)}" for key, value in counts.items())


def _write_markdown(
    path: Path,
    *,
    daily_exposure_path: Path,
    summary: pd.DataFrame,
    target_high_threshold: float,
    live_low_threshold: float,
) -> None:
    lines = [
        "# Strategy Participation Path Audit",
        "",
        f"- Daily exposure input: `{daily_exposure_path}`",
        f"- High target threshold: `{target_high_threshold:.2f}`",
        f"- Low live threshold: `{live_low_threshold:.2f}`",
        "- Diagnostic type: research-only participation path audit.",
        "",
        "## Summary",
    ]
    lines.extend(_frame_to_markdown(summary))
    lines.extend(
        [
            "",
            "## Reading Guide",
            "",
            "- `high_target_days` counts days where the strategy intended high exposure.",
            "- `low_live_after_high_target_days` counts days where high intended exposure did not become live exposure.",
            "- `avg_abs_live_minus_previous_target_exposure` checks whether live exposure mainly follows the prior trading day's target.",
            "- If strong benchmark windows show mostly `risk_or_low` target buckets, the problem is upstream market-context triggering rather than execution lag.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _frame_to_markdown(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return ["", "No rows."]
    display = df.copy()
    return ["", display.to_markdown(index=False)]


def _require_columns(df: pd.DataFrame, columns: list[str], path: Path) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"{path} missing required columns: {', '.join(missing)}")
