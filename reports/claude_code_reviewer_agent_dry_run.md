# Claude Agent Output

- generated_at: 2026-06-03T16:58:13
- model: claude-opus-4-8[1M]
- dry_run: true

## Prompt Preview

# Task
基于当前项目代码上下文执行代码质量审查，优先列出 bug、行为回归风险、数据一致性风险、边界条件和缺失测试。

# Constraints
- 输出语言：中文。
- 采取代码审查立场，优先指出 bug、行为回归风险、数据一致性风险、边界条件和缺失测试。
- 发现问题时必须尽量给出文件路径、函数名或可定位线索。
- 不要重写整段代码，除非用户明确要求生成修复方案。
- 不要输出交易建议或策略参数优化建议，除非它们直接属于代码质量问题。

# Project Context
## phase0/cli.py

```text
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

from rich.console import Console

from phase0.config import load_config
from phase0.accounts import export_account_bill_html, load_simulated_accounts
from phase0.data_sources import ConnectivityResult, check_connectivity, fetch_yf_daily
from phase0.external_market_history import (
    load_us_daily_from_history,
    update_hk_market_history_from_config,
    update_us_market_history_from_config,
)
from phase0.financial_factors import update_financial_factors_from_config
from phase0.import_history import import_from_config, import_index_history_from_config
from phase0.local_history import configure_local_history
from phase0.quality import aggregate_quality, audit_quality
from phase0.reporting import (
    write_cost_sensitivity_report,
    write_data_source_report,
    write_effectiveness_gate_report,
    write_walk_forward_report,
)
from phase0.throttle import configure_akshare_throttle
from phase0.universe import build_local_factor_universe
from phase0.update_history import update_manual_history_from_config
from phase0.walk_forward import run_cost_sensitivity, run_walk_forward, save_walk_forward_csv


def _sync_watchlist_to_ecs(console: Console, local_dir: Path) -> None:
    # Watchlist remote mirror. This intentionally lives in the watchlist
    # program instead of a separate script so cron/manual reruns share one path.
    # The ECS target can be overridden by environment if the host/path changes.
    remote = os.environ.get("BRIEF_SYNC_REMOTE", "root@39.105.102.5")
    remote_dir = os.environ.get("BRIEF_SYNC_REMOTE_DIR", "/brief/")
    if not local_dir.exists() or not (local_dir / "index.html").exists():
        console.print(f"[yellow]Warning:[/yellow] skip ECS watchlist sync; missing {local_dir / 'index.html'}")
        return
    try:
        subprocess.run(
            ["rsync", "-avz", "--delete", f"{local_dir}/", f"{remote}:{remote_dir}"],
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        console.print(f"[yellow]Warning:[/yellow] ECS watchlist sync failed: {exc}")
        return
    console.print(f"Watchlist ECS: {remote}:{remote_dir}")


def _export_phase0_low_turnover_bill(
    *,
    config_path: Path,
    refresh_cache: bool = False,
    no_panel_cache: bool = False,
) -> dict:
    from scripts.export_low_turnover_bill import export_low_turnover_bill

    return export_low_turnover_bill(
        config_path=config_path,
        refresh_cache=refresh_cache,
        no_panel_cache=no_panel_cache,
    )


def _export_phase0_market_regime_report() -> dict:
    from scripts.export_market_regime_report import export_market_regime_report

    return export_market_regime_report(
        input_path=Path("reports/phase0_low_turnover_oos_curve.csv"),
        summary_output=Path("reports/phase0_market_regime_summary.csv"),
        segment_output=Path("reports/phase0_market_regime_segments.csv"),
        html_output=Path("reports/phase0_market_regime_report.html"),
    )


def _export_phase0_oos_report(
    *,
    config_path: Path,
    profile: str | None = None,
    output_dir: str | None = None,
    refresh_cache: bool = False,
    no_panel_cache: bool = False,
    slippage: float | None = None,
    commission: float | None = None,
    stamp_duty_sell: float | None = None,
    price_mode: str | None = None,
    lot_size: int | None = None,
    max_participation_rate: float | None = None,
    enable_limit_check: bool | None = None,
    enable_suspension_check: bool | None = None,
) -> dict:
    from scripts.export_low_turnover_oos_report import export_low_turnover_oos_report

    return export_low_turnover_oos_report(
        config_path=config_path,
        profile=profile,
        output_dir=output_dir,
        refresh_cache=refresh_cache,
        no_panel_cache=no_panel_cache,
        slippage=slippage,
        commission=commission,
        stamp_duty_sell=stamp_duty_sell,
        price_mode=price_mode,
        lot_size=lot_size,
        max_participation_rate=max_participation_rate,
        enable_limit_check=enable_limit_check,
        enable_suspension_check=enable_suspension_check,
    )


def _export_phase0_financial_pti(config_path: Path) -> dict:
    from scripts.audit_financial_pti import audit_financial_pti

    return audit_financial_pti(
        config_path=config_path,
        summary_output=Path("reports/phase0_financial_pti_summary.csv"),
        sample_output=Path("reports/phase0_financial_pti_problem_samples.csv"),
        html_output=Path("reports/phase0_financial_pti_report.html"),
    )


def _export_phase0_premarket(
    *,
    config_path: Path,
    output: str | Path | None = None,
    report_output: str | Path | None = None,
    refresh_cache: bool = False,
    no_panel_cache: bool = False,
) -> dict:
    from scripts.export_premarket_watchlist import export_premarket_watchlist

    kwargs = {
        "config_path": config_path,
        "refresh_cache": refresh_cache,
        "no_panel_cache": no_panel_cache,
    }
    if output is not None:
        kwargs["output"] = output
    if report_output is not None:
        kwargs["report_output"] = report_output
    return export_premarket_watchlist(**kwargs)


def _export_brief_account_bill(*, config_path: Path, brief_date: str | None = None) -> dict:
    cfg = load_config(config_path)
    accounts = load_simulated_accounts(cfg, config_path.parent)
    if not accounts:
        raise ValueError("no enabled simulated account configured")
    account = accounts[0]
    if brief_date is None:
        import sqlite3

        with sqlite3.connect(account.database_path) as conn:
            row = conn.execute(
                "SELECT MAX(brief_date) FROM account_daily_assets WHERE account_id = ?",
                (account.account_id,),
            ).fetchone()
        brief_date = str(row[0]) if row and row[0] else ""
    if not brief_date:
        raise ValueError("no account daily asset rows found; run brief watchlist first")
    output = config_path.parent / "reports" / brief_date / f"simulated_account_bill_{brief_date}.html"
    export_account_bill_html(account=account, brief_date=brief_date, output_path=output)
    return {"account": account.account_id, "brief_date": brief_date, "account_bill": output}


def _export_phase0_execution_gate(
    *,
    config_path: Path,
    profile: str | None = None,
    output_dir: str | None = None,
    refresh_cache: bool = False,
    no_panel_cache: bool = False,
    slippage: float | None = None,
    commission: float | None = None,
    stamp_duty_sell: float | None = None,
    price_mode: str | None = None,
    lot_size: int | None = None,
    max_participation_rate: float | None = None,
    enable_limit_check: bool | None = None,
    enable_suspension_check: bool | None = None,
) -> dict:
    from scripts.export_execution_effectiveness_report import export_execution_effectiveness_report

    return export_execution_effectiveness_report(
        config_path=config_path,
        profile=profile,
        output_dir=output_dir,
        refresh_cache=refresh_cache,
        no_panel_cache=no_panel_cache,
        slippage=slippage,
        commission=commission,
        stamp_duty_sell=stamp_duty_sell,
        price_mode=price_mode,
        lot_size=lot_size,
        max_participation_rate=max_participation_rate,
        enable_limit_check=enable_limit_check,
        enable_suspension_check=enable_suspension_check,
    )


def run_phase0(config_path: Path) -> int:
    console = Console()
    root = config_path.parent
    cfg = load_config(config_path)
    configure_local_history(cfg.get("local_history", {}), root)
    configure_akshare_throttle(cfg.get("data_sources", {}).get("akshare", {}))

    console.print("[bold]Phase 0 started[/bold]")
    years = int(cfg["years"])

    history_result = None
    update_cfg = cfg.get("manual_history_update", {})
    if bool(update_cfg.get("enabled", False)) and bool(update_cfg.get("run_before_phase0", True)):
        console.print("0) Checking/updating local A-share history through configured primary source...")
        history_result = update_manual_history_from_config(cfg, root, check_only=False)
        color = "green" if history_result.ok else "red"
        console.print(
            f"[{color}]Manual history status: {history_result.status}[/{color}] "
            f"latest={history_result.after_latest_date or history_result.before_latest_date or 'N/A'} "
            f"coverage={history_result.after_coverage:.4f} "
            f"source={history_result.primary_source or 'N/A'}"
        )

    us_result = None
    us_cfg = cfg.get("us_market_history", {})
    if bool(us_cfg.get("enabled", False)) and bool(us_cfg.get("run_before_phase0", True)):
        console.print("0b) Checking/updating US market history...")
        us_result = update_us_market_history_from_config(cfg, root, check_only=False)
        color = "green" if us_result.ok else "red"
        console.print(
            f"[{color}]US market history status: {us_result.status}[/{color}] "
            f"latest={us_result.latest_date or 'N/A'} "
            f"coverage={us_result.coverage:.4f} "
            f"source={us_result.source or 'N/A'}"
        )

    console.print("1) Checking data-source connectivity...")
    connectivity = check_connectivity(cfg["data_sources"], years=years)
    if history_result is not None:
        latest = history_result.after_latest_date or history_result.before_latest_date
        message = "; ".join(history_result.warnings[-3:])
        if history_result.primary_source:
            message = f"primary_source={history_result.primary_source}" + (f"; {message}" if message else "")
        connectivity.append(
            ConnectivityResult(
                source="manual-history",
                target="pre_run_update",
                ok=history_result.ok,
                rows=history_result.fetched_rows,
                latest_date=latest,
                error=history_result.status if not message else f"{history_result.status}; {message}",
            )
        )
    if us_result is not None:
        message = "; ".join(us_result.warnings[-3:])
        connectivity.append(
            ConnectivityResult(
                source="us-market-history",
                target="pre_run_update",
                ok=us_result.ok,
                rows=us_result.fetched_rows,
                latest_date=us_result.latest_date,
                error=us_result.status if not message else f"{us_result.status}; {message}",
            )
        )

    console.print("2) Running quality audit on US market history targets...")
    quality_results = []
    us_symbols = [str(item) for item in cfg.get("us_market_history", {}).get("symbols", [])]
    if us_symbols:
        from datetime import date, timedelta

        end = date.today()
        start = end - timedelta(days=365 * years + 20)
        us_bars = load_us_daily_from_history(us_symbols, start, end)
        for sym in us_symbols:
            df = us_bars[us_bars["symbol"] == sym].copy() if not us_bars.empty else us_bars
            if not df.empty:
                quality_results.append(audit_quality(sym, df))
    if not quality_results:
        for r in connectivity:
            if r.source == "yfinance" and r.ok:
                df = fetch_yf_daily(r.target, years=years)
                quality_results.append(audit_quality(r.target, df))
    quality_summary = aggregate_quality(quality_results)

    # Fallback: if yfinance is unavailable/rate-limited, run quality audit on
    # walk-forward symbol pool through AkShare-backed loaders so Phase 0 still
    # produces a usable quality section.
    if not quality_results:
        from phase0.walk_forward import _load_symbol  # local import to avoid cycle

        for sym in cfg.get("symbols", []):
            try:
                df = _load_symbol(sym, years=years)
                quality_
```

[truncated]


## phase0/accounts.py

```text
from __future__ import annotations

from dataclasses import dataclass
import html
from pathlib import Path
import re
import sqlite3
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_ACCOUNT_LEDGER = "data/simulated_trading/phase0_daily_account_ledger.csv"


@dataclass(frozen=True)
class SimulatedAccountConfig:
    account_id: str
    name: str
    initial_cash: float
    ledger_path: Path
    database_path: Path
    enabled: bool = True
    execution_price_mode: str = "next_open"
    max_participation_rate: float = 0.05
    lot_size: int = 100
    commission: float = 0.0
    stamp_duty_sell: float = 0.0
    slippage: float = 0.0
    conservative_price_buffer: float = 0.001
    enable_limit_check: bool = True
    enable_suspension_check: bool = True
    limit_up_down_pct: dict[str, float] | None = None


def load_simulated_accounts(config: dict[str, Any], root: Path) -> list[SimulatedAccountConfig]:
    walk_forward = config.get("walk_forward", {})
    execution = config.get("execution", {})
    limit_cfg = execution.get("limit_up_down_pct", {})
    raw_accounts = config.get("accounts", {}).get("simulated", [])
    if not raw_accounts:
        raw_accounts = [
            {
                "account_id": "default",
                "name": "默认模拟账户",
                "initial_cash": walk_forward.get("initial_cash", 1_000_000),
                "ledger_path": DEFAULT_ACCOUNT_LEDGER,
                "enabled": True,
            }
        ]

    accounts: list[SimulatedAccountConfig] = []
    for raw in raw_accounts:
        if not bool(raw.get("enabled", True)):
            continue
        ledger_path = Path(str(raw.get("ledger_path", DEFAULT_ACCOUNT_LEDGER)))
        if not ledger_path.is_absolute():
            ledger_path = root / ledger_path
        database_path = Path(str(raw.get("database_path", "data/simulated_trading/simulated_accounts.sqlite")))
        if not database_path.is_absolute():
            database_path = root / database_path
        accounts.append(
            SimulatedAccountConfig(
                account_id=str(raw.get("account_id", "default")),
                name=str(raw.get("name", raw.get("account_id", "默认模拟账户"))),
                initial_cash=float(raw.get("initial_cash", walk_forward.get("initial_cash", 1_000_000))),
                ledger_path=ledger_path,
                database_path=database_path,
                enabled=True,
                execution_price_mode=str(raw.get("execution_price_mode", execution.get("price_mode", "next_open"))),
                max_participation_rate=float(raw.get("max_participation_rate", execution.get("max_participation_rate", 0.05))),
                lot_size=int(raw.get("lot_size", execution.get("lot_size", 100))),
                commission=float(raw.get("commission", walk_forward.get("commission", 0.0))),
                stamp_duty_sell=float(raw.get("stamp_duty_sell", walk_forward.get("stamp_duty_sell", 0.0))),
                slippage=float(raw.get("slippage", walk_forward.get("slippage", 0.0))),
                conservative_price_buffer=float(raw.get("conservative_price_buffer", execution.get("conservative_price_buffer", 0.001))),
                enable_limit_check=bool(raw.get("enable_limit_check", execution.get("enable_limit_check", True))),
                enable_suspension_check=bool(raw.get("enable_suspension_check", execution.get("enable_suspension_check", True))),
                limit_up_down_pct={
                    "default": float(limit_cfg.get("default", 0.10)),
                    "star": float(limit_cfg.get("star", 0.20)),
                    "chinext": float(limit_cfg.get("chinext", 0.20)),
                    "bj": float(limit_cfg.get("bj", 0.30)),
                },
            )
        )
    return accounts


def parse_percent(value: Any) -> float:
    if pd.isna(value):
        return 0.0
    raw = str(value).strip().replace("%", "")
    if not raw:
        return 0.0
    try:
        return float(raw) / 100.0
    except ValueError:
        return 0.0


def round_lot_floor(shares: float, lot_size: int) -> float:
    if lot_size <= 1:
        return max(0.0, float(np.floor(shares)))
    return float(max(0, int(np.floor(float(shares) / lot_size) * lot_size)))


def price_mode_label(price_mode: str) -> str:
    labels = {
        "next_open": "执行日开盘价",
        "close": "执行日收盘价",
        "conservative": "执行日开盘保守价",
    }
    return labels.get(str(price_mode), str(price_mode))


def trade_time_for_price_mode(*, brief_date: str, signal_date: str, price_mode: str) -> str:
    if price_mode == "close":
        return f"{brief_date} 15:00"
    if price_mode == "next_open":
        return f"{brief_date} 09:30"
    if price_mode == "conservative":
        return f"{brief_date} 09:30"
    return f"{brief_date} 09:30"


def _safe_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"unsafe SQL identifier: {value}")
    return value


def _resolve_path(root: Path, value: Any) -> Path:
    path = Path(str(value or ""))
    return path if path.is_absolute() else root / path


def _limit_pct(symbol: str, account: SimulatedAccountConfig) -> float:
    limits = account.limit_up_down_pct or {}
    code = str(symbol).split(".")[-1]
    market = str(symbol).split(".")[0]
    if market == "BJ" or code.startswith(("4", "8")):
        return float(limits.get("bj", 0.30))
    if market == "SH" and code.startswith("688"):
        return float(limits.get("star", 0.20))
    if market == "SZ" and code.startswith("300"):
        return float(limits.get("chinext", 0.20))
    return float(limits.get("default", 0.10))


def _load_execution_prices(
    *,
    root: Path,
    local_history_cfg: dict[str, Any] | None,
    execution_date: str,
    symbols: list[str],
) -> dict[str, dict[str, float]]:
    if not symbols:
        return {}
    cfg = local_history_cfg or {}
    db_path = _resolve_path(root, cfg.get("path", "data/manual_history/a_share_history.sqlite"))
    if not db_path.exists():
        return {}
    daily_table = _safe_identifier(str(cfg.get("daily_table", "market_daily_bars")))
    market = str(cfg.get("market", "CN"))
    adjust_type = str(cfg.get("adjust_type", "qfq"))
    placeholders = ",".join("?" for _ in symbols)
    query = f"""
        SELECT b.symbol, b.open, b.high, b.low, b.close, b.volume, b.amount,
               (
                   SELECT p.close
                   FROM {daily_table} p
                   WHERE p.market = b.market
                     AND p.symbol = b.symbol
                     AND p.adjust_type = b.adjust_type
                     AND p.date < b.date
                   ORDER BY p.date DESC
                   LIMIT 1
               ) AS previous_close
        FROM {daily_table} b
        WHERE b.market = ?
          AND b.adjust_type = ?
          AND b.date = ?
          AND b.symbol IN ({placeholders})
    """
    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(query, (market, adjust_type, execution_date, *symbols)).fetchall()
    except (sqlite3.Error, ValueError):
        return {}
    out: dict[str, dict[str, float]] = {}
    for symbol, open_, high, low, close, volume, amount, previous_close in rows:
        out[str(symbol)] = {
            "open": float(open_) if open_ is not None else np.nan,
            "high": float(high) if high is not None else np.nan,
            "low": float(low) if low is not None else np.nan,
            "close": float(close) if close is not None else np.nan,
            "volume": float(volume) if volume is not None else np.nan,
            "amount": float(amount) if amount is not None else np.nan,
            "previous_close": float(previous_close) if previous_close is not None else np.nan,
        }
    return out


def _execution_price(price_row: dict[str, float], side: str, account: SimulatedAccountConfig) -> float:
    mode = account.execution_price_mode
    if mode == "close":
        return float(price_row.get("close", np.nan))
    base = float(price_row.get("open", np.nan))
    if not pd.notna(base) or base <= 0:
        base = float(price_row.get("close", np.nan))
    if mode == "conservative":
        if side == "buy":
            return base * (1.0 + account.conservative_price_buffer)
        return base * (1.0 - account.conservative_price_buffer)
    return base


def _trade_block_reasons(price_row: dict[str, float], side: str, account: SimulatedAccountConfig) -> list[str]:
    reasons: list[str] = []
    open_price = float(price_row.get("open", np.nan))
    close_price = float(price_row.get("close", np.nan))
    volume = float(price_row.get("volume", np.nan))
    amount = float(price_row.get("amount", np.nan))
    if account.enable_suspension_check:
        if not pd.notna(open_price) or open_price <= 0 or not pd.notna(close_price) or close_price <= 0:
            reasons.append("停牌/无有效价格")
        if pd.notna(volume) and volume <= 0:
            reasons.append("停牌/成交量为0")
        if pd.notna(amount) and amount <= 0:
            reasons.append("停牌/成交额为0")
    previous_close = float(price_row.get("previous_close", np.nan))
    check_price = close_price if account.execution_price_mode == "close" else open_price
    if account.enable_limit_check and pd.notna(previous_close) and previous_close > 0 and pd.notna(check_price):
        limit_pct = _limit_pct(str(price_row.get("symbol", "")), account)
        limit_up = previous_close * (1.0 + limit_pct)
        limit_down = previous_close * (1.0 - limit_pct)
        tolerance = 0.001
        if side == "buy" and check_price >= limit_up * (1.0 - tolerance):
            reasons.append("涨停不可买")
        if side == "sell" and check_price <= limit_down * (1.0 + tolerance):
            reasons.append("跌停不可卖")
    return reasons


def format_money(value: Any) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):,.2f}"


def format_pct(value: Any) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value) * 100:.2f}%"


def format_num(value: Any, digits: int = 2) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):,.{digits}f}"


def watchlist_to_account_frame(watchlist: pd.DataFrame, brief_date: str) -> pd.DataFrame:
    if watchlist.empty:
        return pd.DataFrame(columns=["brief_date", "signal_date", "symbol", "name", "signal_close", "target_weight", "weight_change"])
    if "信号日期" in watchlist.columns:
        signal_dates = watchlist["信号日期"].astype(str)
    else:
        signal_dates = pd.Series([brief_date] * len(watchlist), index=watchlist.index)
    return pd.DataFrame(
        {
            "brief_date": brief_date,
            "signal_date": signal_dates,
            "symbol": watchlist["股票代码"].astype(str),
            "name": watchlist["股票名称"].astype(str),
            "signal_close": pd.to_numeric(watchlist["收盘价"], errors="coerce"),
            "target_weight": watchlist["目标权重"].map(parse_percent),
            "weight_change": watchlist["权重变化"].map(parse_percent),
        }
    )


def collect_watchlist_frames(root: Path, current_watchlist: pd.DataFrame, current_brief_date: str) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    report_root = root / "reports"
    if report_root.exists():
        for path in sorted(report_root.glob("????-??-??/phase0_premarket_watchlist*.csv")):
            brief_date = path.parent.name
            if brief_date > current_brief_date or brief_date in frames:
                continue
            try:
                df = pd.read_csv(path, encoding="utf-8-sig")
            except Exception:
                continue
            required = {"股票代码", "股票名称", "收盘价", "目标权重", "权重变化"}
            if required.issubset(df.columns):
                frames[brief_date] = watchlist_to_account_frame(df, brief_date)
    frames[current_brief_date] = watchlist_to_account_frame(current_watchlist, current_brief_date)
    return dict(sorted(frames.items()))


def 
```

[truncated]


## phase0/reporting.py

```text
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from phase0.data_sources import ConnectivityResult
from phase0.quality import QualityResult


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = []
    out.append("| " + " | ".join(headers) + " |")
    out.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        out.append("| " + " | ".join(row) + " |")
    return "\n".join(out)


def write_data_source_report(
    path: Path,
    connectivity: list[ConnectivityResult],
    quality: list[QualityResult],
    quality_summary: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con_rows = []
    for r in connectivity:
        con_rows.append(
            [
                r.source,
                r.target,
                "OK" if r.ok else "FAIL",
                str(r.rows),
                r.latest_date,
                r.error[:120],
            ]
        )
    q_rows = []
    for q in quality:
        q_rows.append(
            [
                q.symbol,
                str(q.rows),
                f"{q.missing_ratio:.4f}",
                str(q.ohlc_violation_count),
                str(q.non_positive_price_count),
                str(q.duplicate_date_count),
                q.latest_date,
                str(q.data_delay_days),
            ]
        )

    lines = [
        "# Phase 0 Data Source & Quality Report",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Connectivity",
        "",
        _md_table(
            ["source", "target", "status", "rows", "latest_date", "error"],
            con_rows,
        ),
        "",
        "## Quality Audit",
        "",
        _md_table(
            ["symbol", "rows", "missing_ratio", "ohlc_viol", "non_pos", "dup_date", "latest_date", "delay_days"],
            q_rows,
        ),
        "",
        "## Quality Summary",
        "",
        _md_table(
            ["metric", "value"],
            [[k, str(v)] for k, v in quality_summary.items()],
        ),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_walk_forward_report(path: Path, summary: dict[str, Any], folds_df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    if not folds_df.empty:
        for _, row in folds_df.iterrows():
            rows.append(
                [
                    str(row["symbol"]),
                    str(int(row["fold"])),
                    str(row["train_start"]),
                    str(row["train_end"]),
                    str(row["valid_start"]),
                    str(row["valid_end"]),
                    f"{float(row['annualized_return']):.4f}",
                    f"{float(row['sharpe']):.4f}",
                    f"{float(row['max_drawdown']):.4f}",
                    f"{float(row['win_rate']):.4f}",
                    f"{float(row['turnover_annual']):.2f}",
                    str(int(row["trades"])),
                    str(row.get("selected_params", "")),
                ]
            )

    candidate_summary_rows = summary.get("candidate_summary_rows", []) or []
    summary_table_rows = [[k, str(v)] for k, v in summary.items() if k != "candidate_summary_rows"]
    candidate_rows = [
        [
            str(row.get("candidate", "")),
            f"{float(row.get('score', 0.0)):.4f}",
            f"{float(row.get('selection_score', row.get('score', 0.0))):.4f}",
            str(bool(row.get("eligible_for_selection", False))),
            str(row.get("governance_reason", "")),
            str(int(row.get("fold_count", 0))),
            str(int(row.get("symbol_count", 0))),
            str(row.get("panel_scope", "")),
            f"{float(row.get('annualized_return_mean', 0.0)):.4f}",
            f"{float(row.get('sharpe_mean', 0.0)):.4f}",
            f"{float(row.get('max_drawdown_mean', 0.0)):.4f}",
            f"{float(row.get('win_rate_mean', 0.0)):.4f}",
            f"{float(row.get('turnover_annual_mean', 0.0)):.2f}",
        ]
        for row in candidate_summary_rows
    ]

    lines = [
        "# Phase 0 Walk-Forward Report",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Summary",
        "",
        _md_table(["metric", "value"], summary_table_rows),
        "",
    ]
    if candidate_rows:
        lines.extend(
            [
                "## Candidate Summary",
                "",
                _md_table(
                    [
                        "candidate",
                        "score",
                        "selection_score",
                        "eligible",
                        "governance_reason",
                        "fold_count",
                        "symbol_count",
                        "panel_scope",
                        "annualized_return_mean",
                        "sharpe_mean",
                        "max_drawdown_mean",
                        "win_rate_mean",
                        "turnover_annual_mean",
                    ],
                    candidate_rows,
                ),
                "",
            ]
        )
    lines.extend(
        [
            "## Fold Details",
            "",
            _md_table(
                [
                    "symbol",
                    "fold",
                    "train_start",
                    "train_end",
                    "valid_start",
                    "valid_end",
                    "annual_ret",
                    "sharpe",
                    "max_dd",
                    "win_rate",
                    "turnover_annual",
                    "trades",
                    "selected_params",
                ],
                rows,
            ),
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_effectiveness_gate_report(path: Path, wf_summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sharpe = float(wf_summary.get("sharpe_mean", 0.0))
    mdd = float(wf_summary.get("max_drawdown_mean", 0.0))
    win = float(wf_summary.get("win_rate_mean", 0.0))
    decay = float(wf_summary.get("oos_return_decay_ratio", 0.0))
    ann = float(wf_summary.get("annualized_return_mean", 0.0))
    governance_ok = bool(wf_summary.get("selected_candidate_eligible", True))

    gates = [
        ("selected_candidate_eligible == True", governance_ok),
        ("annualized_return_mean > 0", ann > 0),
        ("sharpe_mean > 0.5", sharpe > 0.5),
        ("max_drawdown_mean > -0.25", mdd > -0.25),
        ("win_rate_mean > 0.45", win > 0.45),
        ("oos_return_decay_ratio < 0.30", decay < 0.30),
    ]
    passed = all(ok for _, ok in gates)

    lines = [
        "# Phase 0 Strategy Effectiveness Gate",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Overall verdict: {'PASS' if passed else 'FAIL'}",
        "",
        _md_table(["gate", "status"], [[name, "PASS" if ok else "FAIL"] for name, ok in gates]),
        "",
        "## Snapshot",
        "",
        _md_table(["metric", "value"], [[k, str(v)] for k, v in wf_summary.items()]),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_cost_sensitivity_report(path: Path, sensitivity_df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[list[str]] = []
    if not sensitivity_df.empty:
        for _, row in sensitivity_df.iterrows():
            rows.append(
                [
                    str(row.get("scenario", "")),
                    str(row.get("candidate", "")),
                    str(row.get("selected_candidate", "")),
                    str(bool(row.get("eligible_for_selection", False))),
                    str(row.get("governance_reason", "")),
                    str(int(row.get("fold_count", 0))),
                    str(row.get("panel_scope", "")),
                    f"{float(row.get('slippage', 0.0)):.5f}",
                    f"{float(row.get('commission', 0.0)):.5f}",
                    f"{float(row.get('stamp_duty_sell', 0.0)):.5f}",
                    f"{float(row.get('annualized_return_mean', 0.0)):.4f}",
                    f"{float(row.get('sharpe_mean', 0.0)):.4f}",
                    f"{float(row.get('max_drawdown_mean', 0.0)):.4f}",
                    f"{float(row.get('win_rate_mean', 0.0)):.4f}",
                    f"{float(row.get('turnover_annual_mean', 0.0)):.2f}",
                ]
            )

    lines = [
        "# Phase 0 Cost Sensitivity Report",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        _md_table(
            [
                "scenario",
                "candidate",
                "selected_candidate",
                "eligible",
                "governance_reason",
                "fold_count",
                "panel_scope",
                "slippage",
                "commission",
                "stamp_duty_sell",
                "annualized_return_mean",
                "sharpe_mean",
                "max_drawdown_mean",
                "win_rate_mean",
                "turnover_annual_mean",
            ],
            rows,
        ),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")

```

## phase0/walk_forward.py

```text
from __future__ import annotations

import copy
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from phase0.data_sources import fetch_cn_daily, fetch_hk_daily, fetch_yf_daily
from phase0.external_market_history import (
    configure_us_market_history,
    load_us_daily_from_history,
    us_market_history_runtime_fallback_enabled,
)
from phase0.local_history import (
    configure_local_history,
    load_daily_from_local_history,
    local_history_path,
    local_history_prefer_daily_for_backtest,
)
from phase0.strategies import available_strategies, get_strategy
from phase0.strategies.base import StrategyOutput
from phase0.throttle import configure_akshare_throttle
from phase0.universe import load_universe_symbols


MARKET_TICKERS = ["^NDX", "^SOX", "NVDA", "KWEB", "^VIX", "CNY=X"]
FINANCIAL_FACTOR_COLUMNS = [
    "roe",
    "revenue_growth",
    "profit_growth",
    "cash_flow_quality",
    "debt_to_asset",
]


def _xmarket_enabled(strategy_cfg: dict[str, Any]) -> bool:
    return bool(strategy_cfg.get("cross_market", {}).get("enabled", False))


@dataclass
class FoldResult:
    fold: int
    train_start: str
    train_end: str
    valid_start: str
    valid_end: str
    annualized_return: float
    sharpe: float
    max_drawdown: float
    win_rate: float
    turnover_annual: float
    trades: int
    passed_min_samples: bool
    selected_params: str = ""


def _annualized_return(r: pd.Series) -> float:
    if r.empty:
        return 0.0
    cum = float((1.0 + r).prod() - 1.0)
    yrs = max(len(r) / 252.0, 1 / 252.0)
    return float((1 + cum) ** (1 / yrs) - 1)


def _sharpe(r: pd.Series) -> float:
    if len(r) < 2:
        return 0.0
    std = float(r.std(ddof=1))
    if std == 0:
        return 0.0
    return float((r.mean() / std) * np.sqrt(252))


def _max_drawdown(r: pd.Series) -> float:
    if r.empty:
        return 0.0
    eq = (1 + r).cumprod()
    peak = eq.cummax()
    dd = (eq / peak) - 1
    return float(dd.min())


def _calc_metrics(returns: pd.Series, signals: pd.Series) -> dict[str, float]:
    ann = _annualized_return(returns)
    shp = _sharpe(returns)
    mdd = _max_drawdown(returns)

    realized = returns[signals != 0]
    win_rate = float((re
```

[truncated]


[context budget exhausted]
