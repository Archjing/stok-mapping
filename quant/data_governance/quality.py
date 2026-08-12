from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class QualityResult:
    symbol: str
    rows: int
    missing_ratio: float
    ohlc_violation_count: int
    non_positive_price_count: int
    duplicate_date_count: int
    latest_date: str
    data_delay_days: int


def ohlc_violation_count(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    need = {"open", "high", "low", "close"}
    if not need.issubset(df.columns):
        return 0
    invalid = (df["high"] < df[["open", "close"]].max(axis=1)) | (df["low"] > df[["open", "close"]].min(axis=1))
    return int(invalid.fillna(False).sum())


def audit_quality(symbol: str, df: pd.DataFrame) -> QualityResult:
    if df.empty:
        return QualityResult(symbol, 0, 1.0, 0, 0, 0, "", 9999)

    d = df.copy()
    if "date" in d.columns:
        d["date"] = pd.to_datetime(d["date"], errors="coerce")
    else:
        d["date"] = pd.NaT

    cols = [c for c in ["open", "high", "low", "close", "volume"] if c in d.columns]
    missing_ratio = float(d[cols].isna().mean().mean()) if cols else 1.0
    violation = ohlc_violation_count(d)

    non_positive = 0
    for c in ["open", "high", "low", "close"]:
        if c in d.columns:
            non_positive += int((pd.to_numeric(d[c], errors="coerce") <= 0).fillna(False).sum())

    dup_dates = int(d["date"].duplicated().sum())
    latest_ts = d["date"].max()
    latest_date = "" if pd.isna(latest_ts) else str(latest_ts.date())
    delay_days = 9999 if pd.isna(latest_ts) else int((date.today() - latest_ts.date()).days)

    return QualityResult(
        symbol=symbol,
        rows=len(d),
        missing_ratio=round(missing_ratio, 6),
        ohlc_violation_count=violation,
        non_positive_price_count=non_positive,
        duplicate_date_count=dup_dates,
        latest_date=latest_date,
        data_delay_days=delay_days,
    )


def aggregate_quality(results: list[QualityResult]) -> dict[str, Any]:
    if not results:
        return {"coverage": 0.0, "avg_missing_ratio": 1.0, "avg_delay_days": 9999, "score": 0.0}

    coverage = sum(1 for r in results if r.rows > 0) / len(results)
    avg_missing = float(np.mean([r.missing_ratio for r in results]))
    avg_delay = float(np.mean([r.data_delay_days for r in results]))
    total_viol = sum(r.ohlc_violation_count + r.non_positive_price_count + r.duplicate_date_count for r in results)

    score = 100.0
    score -= (1 - coverage) * 40
    score -= min(avg_missing * 100, 20)
    score -= min(avg_delay, 14)
    score -= min(total_viol * 0.1, 20)
    score = max(0.0, round(score, 2))

    return {
        "coverage": round(coverage, 4),
        "avg_missing_ratio": round(avg_missing, 6),
        "avg_delay_days": round(avg_delay, 2),
        "total_integrity_violations": total_viol,
        "score": score,
    }
