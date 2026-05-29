from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from phase0.env import prepare_imports
from phase0.local_history import configure_local_history, load_snapshot_from_local_history, normalize_cn_symbol
from phase0.throttle import configure_akshare_throttle, fetch_with_akshare_retries

prepare_imports()

import akshare as ak  # noqa: E402


@dataclass
class UniverseBuildResult:
    universe: pd.DataFrame
    snapshot: pd.DataFrame
    source: str
    target_size: int
    selected_count: int
    snapshot_count: int
    output_path: Path
    snapshot_path: Path
    report_path: Path
    warnings: list[str]


def _first_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    normalized = {str(col).strip().lower(): col for col in df.columns}
    for name in candidates:
        key = name.strip().lower()
        if key in normalized:
            return str(normalized[key])
    return None


def _clean_numeric(series: pd.Series | None) -> pd.Series:
    if series is None:
        return pd.Series(dtype=float)
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.replace("亿", "", regex=False)
        .str.replace("--", "", regex=False)
        .str.replace("-", "", regex=False)
        .replace({"": np.nan, "nan": np.nan, "None": np.nan})
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _series_or_empty(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    col = _first_column(df, candidates)
    if col is None:
        return pd.Series(np.nan, index=df.index)
    return df[col]


def _load_akshare_snapshot(cfg: dict[str, Any]) -> pd.DataFrame:
    configure_akshare_throttle(cfg.get("akshare", {}))
    raw = fetch_with_akshare_retries(lambda: ak.stock_zh_a_spot_em())
    if raw is None or raw.empty:
        return pd.DataFrame()

    df = raw.copy()
    code = _series_or_empty(df, ["代码", "code", "symbol"])
    out = pd.DataFrame(
        {
            "symbol": code.map(normalize_cn_symbol),
            "name": _series_or_empty(df, ["名称", "name"]),
            "industry": _series_or_empty(df, ["行业", "所属行业", "板块"]),
            "latest_price": _clean_numeric(_series_or_empty(df, ["最新价", "最新", "收盘"])),
            "pct_change": _clean_numeric(_series_or_empty(df, ["涨跌幅", "涨跌幅%", "pct_chg"])),
            "amount": _clean_numeric(_series_or_empty(df, ["成交额", "成交金额", "amount"])),
            "volume": _clean_numeric(_series_or_empty(df, ["成交量", "volume"])),
            "turnover_rate": _clean_numeric(_series_or_empty(df, ["换手率", "turnover_rate"])),
            "total_mv": _clean_numeric(_series_or_empty(df, ["总市值", "total_mv"])),
            "circ_mv": _clean_numeric(_series_or_empty(df, ["流通市值", "circ_mv"])),
            "pe_ttm": _clean_numeric(_series_or_empty(df, ["市盈率-动态", "市盈率TTM", "市盈率", "pe_ttm"])),
            "pb": _clean_numeric(_series_or_empty(df, ["市净率", "pb"])),
        }
    )
    out["source"] = "akshare.stock_zh_a_spot_em"
    out["as_of_date"] = date.today().isoformat()
    return out


def _load_akshare_industry_map(cfg: dict[str, Any], max_boards: int) -> dict[str, str]:
    configure_akshare_throttle(cfg.get("akshare", {}))
    boards = fetch_with_akshare_retries(lambda: ak.stock_board_industry_name_em())
    if boards is None or boards.empty:
        return {}
    name_col = _first_column(boards, ["板块名称", "名称", "name"])
    if name_col is None:
        return {}

    mapping: dict[str, str] = {}
    for board_name in boards[name_col].dropna().astype(str).head(max_boards):
        try:
            cons = fetch_with_akshare_retries(lambda board_name=board_name: ak.stock_board_industry_cons_em(symbol=board_name))
        except Exception:
            continue
        if cons is None or cons.empty:
            continue
        code_col = _first_column(cons, ["代码", "code", "symbol"])
        if code_col is None:
            continue
        for raw_code in cons[code_col].dropna():
            symbol = normalize_cn_symbol(raw_code)
            if symbol and symbol not in mapping:
                mapping[symbol] = board_name
    return mapping


def _filter_snapshot(snapshot: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    if snapshot.empty:
        return snapshot
    universe_cfg = cfg.get("universe", {})
    allowed_markets = set(universe_cfg.get("markets", ["SH", "SZ"]))
    exclude_name_patterns = universe_cfg.get("exclude_name_patterns", ["ST", "*ST", "退"])
    min_amount = float(universe_cfg.get("min_amount", 0))
    min_total_mv = float(universe_cfg.get("min_total_mv", 0))

    df = snapshot.copy()
    df = df[df["symbol"].astype(str).str.contains(r"^(?:SH|SZ|BJ)\.\d{6}$", regex=True, na=False)]
    df = df[df["symbol"].str.split(".").str[0].isin(allowed_markets)]
    if exclude_name_patterns:
        pattern = "|".join(re.escape(str(p)) for p in exclude_name_patterns)
        df = df[~df["name"].astype(str).str.contains(pattern, case=False, regex=True, na=False)]
    df = df[df["latest_price"].fillna(0) > 0]
    if "amount" in df.columns:
        df = df[df["amount"].fillna(0) >= min_amount]
    if min_total_mv > 0 and df["total_mv"].notna().any():
        df = df[df["total_mv"].fillna(0) >= min_total_mv]
    return df.drop_duplicates("symbol").reset_index(drop=True)


def _score_snapshot(snapshot: pd.DataFrame) -> pd.DataFrame:
    df = snapshot.copy()
    amount = df["amount"].fillna(0)
    mv_base = df["circ_mv"].where(df["circ_mv"].notna(), df["total_mv"]).fillna(0)
    df["liquidity_rank"] = amount.rank(method="average", pct=True)
    df["size_rank"] = mv_base.rank(method="average", pct=True)
    df["universe_score"] = 0.60 * df["liquidity_rank"] + 0.40 * df["size_rank"]
    return df.sort_values(["universe_score", "amount"], ascending=False).reset_index(drop=True)


def _select_balanced_universe(scored: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    universe_cfg = cfg.get("universe", {})
    target_size = int(universe_cfg.get("target_size", 500))
    max_industry_weight = float(universe_cfg.get("max_industry_weight", 0.12))
    max_per_industry = max(1, int(math.ceil(target_size * max_industry_weight)))
    if scored.empty:
        return scored
    if "industry" not in scored.columns or scored["industry"].replace("", np.nan).isna().all():
        return scored.head(target_size).copy()

    selected: list[int] = []
    industry_counts: dict[str, int] = {}
    for idx, row in scored.iterrows():
        industry = str(row.get("industry") or "UNKNOWN")
        if industry_counts.get(industry, 0) >= max_per_industry:
            continue
        selected.append(idx)
        industry_counts[industry] = industry_counts.get(industry, 0) + 1
        if len(selected) >= target_size:
            break

    if len(selected) < target_size:
        selected_set = set(selected)
        for idx in scored.index:
            if idx not in selected_set:
                selected.append(int(idx))
            if len(selected) >= target_size:
                break
    return scored.loc[selected].head(target_size).reset_index(drop=True)


def build_local_factor_universe(cfg: dict[str, Any], root: Path) -> UniverseBuildResult:
    configure_local_history(cfg.get("local_history", {}), root)
    universe_cfg = cfg.get("universe", {})
    target_size = int(universe_cfg.get("target_size", 500))
    out_dir = root / universe_cfg.get("output_dir", "data/universe")
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / universe_cfg.get("output_file", "local_factor_universe.csv")
    snapshot_path = out_dir / universe_cfg.get("snapshot_file", "a_share_snapshot.csv")
    report_path = out_dir / universe_cfg.get("report_file", "local_factor_universe_report.md")

    warnings: list[str] = []
    try:
        snapshot = _load_akshare_snapshot(cfg.get("data_sources", {}))
    except Exception as exc:
        warnings.append(f"AkShare all-A snapshot failed: {exc}")
        snapshot = pd.DataFrame()
    source = "akshare"
    if snapshot.empty:
        snapshot = load_snapshot_from_local_history(days=int(universe_cfg.get("fallback_days", 90)))
        warning = snapshot.attrs.get("warning") if hasattr(snapshot, "attrs") else None
        if warning:
            warnings.append(str(warning))
        if snapshot.empty:
            warnings.append("AkShare all-A snapshot was empty and configured local history fallback returned no usable current snapshot.")
        else:
            warnings.append("AkShare all-A snapshot was empty; used configured local history fallback.")
        source = "local_history_sqlite"

    if (
        bool(universe_cfg.get("fetch_industry", True))
        and not snapshot.empty
        and snapshot["industry"].replace("", np.nan).isna().all()
        and source == "akshare"
    ):
        try:
            industry_map = _load_akshare_industry_map(
                cfg.get("data_sources", {}),
                max_boards=int(universe_cfg.get("industry_max_boards", 120)),
            )
            if industry_map:
                snapshot["industry"] = snapshot["symbol"].map(industry_map).fillna("")
            else:
                warnings.append("AkShare industry board mapping returned no usable industry data.")
        except Exception as exc:
            warnings.append(f"AkShare industry board mapping failed: {exc}")

    filtered = _filter_snapshot(snapshot, cfg)
    scored = _score_snapshot(filtered) if not filtered.empty else filtered
    universe = _select_balanced_universe(scored, cfg)
    universe["universe_rank"] = np.arange(1, len(universe) + 1)

    snapshot.to_csv(snapshot_path, index=False, encoding="utf-8")
    universe.to_csv(output_path, index=False, encoding="utf-8")
    _write_universe_report(
        report_path,
        universe=universe,
        snapshot=snapshot,
        source=source,
        target_size=target_size,
        warnings=warnings,
    )
    return UniverseBuildResult(
        universe=universe,
        snapshot=snapshot,
        source=source,
        target_size=target_size,
        selected_count=len(universe),
        snapshot_count=len(snapshot),
        output_path=output_path,
        snapshot_path=snapshot_path,
        report_path=report_path,
        warnings=warnings,
    )


def load_universe_symbols(cfg: dict[str, Any], root: Path) -> list[str]:
    universe_cfg = cfg.get("universe", {})
    path = root / universe_cfg.get("output_dir", "data/universe") / universe_cfg.get("output_file", "local_factor_universe.csv")
    if not path.exists():
        return []
    df = pd.read_csv(path)
    if "symbol" not in df.columns:
        return []
    min_usable = int(universe_cfg.get("min_usable_size", min(100, universe_cfg.get("target_size", 500))))
    if len(df) < min_usable:
        return []
    limit = int(universe_cfg.get("walk_forward_limit", universe_cfg.get("target_size", 500)))
    return [str(sym) for sym in df["symbol"].dropna().head(limit).tolist()]


def _write_universe_report(
    path: Path,
    *,
    universe: pd.DataFrame,
    snapshot: pd.DataFrame,
    source: str,
    target_size: int,
    warnings: list[str],
) -> None:
    industry_counts = (
        universe["industry"].replace("", "UNKNOWN").fillna("UNKNOWN").value_counts().head(20)
        if "industry" in universe.columns and not universe.empty
        else pd.Series(dtype=int)
    )
    lines = [
        "# Local Factor Universe Report",
        "",
        f"Generated at: {date.today().isoformat()}",
        "",
        "## Summary",
        "",
        "| metric | value |",
        "| --- | --- |",
        f"| source | {source} |",
        f"| target_size | {target_size} |",
        f"| snapshot_count | {len(snapshot)} |",
        f"| selected_count | {len(universe)} |",
        f"| has_industry | {bool('industry' in universe.columns and universe['industry'].replace('', np.nan).notna().any())} |",
        f"| has_market_cap | {bool('total_mv' in universe.columns and universe['total_mv'].notna().any())} |",
        f"| has_valuation | {bool('pe_ttm' in universe.columns and universe['pe_ttm'].notna().any())} |",
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {w}" for w in warnings] or ["- None"])
    lines.extend(["", "## Top Industries", "", "| industry | count |", "| --- | --- |"])
    for industry, count in industry_counts.items():
        lines.append(f"| {industry} | {int(count)} |")
    lines.extend(["", "## Top 20 Symbols", "", "| rank | symbol | name | industry | amount | total_mv | pe_ttm | pb |", "| --- | --- | --- | --- | --- | --- | --- | --- |"])
    for _, row in universe.head(20).iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(int(row.get("universe_rank", 0))),
                    str(row.get("symbol", "")),
                    str(row.get("name", "")),
                    str(row.get("industry", "")),
                    f"{float(row.get('amount', np.nan)):.2f}" if pd.notna(row.get("amount", np.nan)) else "",
                    f"{float(row.get('total_mv', np.nan)):.2f}" if pd.notna(row.get("total_mv", np.nan)) else "",
                    f"{float(row.get('pe_ttm', np.nan)):.2f}" if pd.notna(row.get("pe_ttm", np.nan)) else "",
                    f"{float(row.get('pb', np.nan)):.2f}" if pd.notna(row.get("pb", np.nan)) else "",
                ]
            )
            + " |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
