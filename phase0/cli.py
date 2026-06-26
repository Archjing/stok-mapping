from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from collections import Counter
from pathlib import Path

from rich.console import Console

from phase0.adjustment_backfill import backfill_adjustment_factors_from_config
from phase0.config import load_config
from phase0.accounts import export_account_bill_html, load_simulated_accounts
from phase0.adjustment import run_adjustment_audit
from phase0.daily_basic_backfill import backfill_daily_basic_from_config
from phase0.data_sources import ConnectivityResult, check_connectivity, fetch_yf_daily
from phase0.data_governance.db_health import run_database_health_check
from phase0.data_governance.index_asof_audit import run_index_asof_audit
from phase0.data_governance.index_asof_backfill import backfill_index_asof_from_config
from phase0.data_governance.quality import aggregate_quality, audit_quality
from phase0.external_market_history import (
    load_us_daily_from_history,
    update_hk_market_history_from_config,
    update_us_market_history_from_config,
)
from phase0.factor_effectiveness import run_factor_effectiveness_report
from phase0.financial_factors import update_financial_factors_from_config
from phase0.import_history import import_from_config, import_index_history_from_config
from phase0.intelligence import (
    collect_intelligence,
    import_local_intelligence,
    review_intelligence_candidates,
    validate_intelligence_ledger,
)
from phase0.local_history import configure_local_history
from phase0.maintenance_orchestrator import maintenance_resume, maintenance_run_long_task, maintenance_status, maintenance_stop, maintenance_supervise, maintenance_tick
from phase0.overfit import run_overfit_diagnostic
from phase0.reporting import (
    write_cost_sensitivity_report,
    write_data_source_report,
    write_effectiveness_gate_report,
    write_walk_forward_report,
)
from phase0.reporting.paths import create_report_run, latest_dir, report_category_dir, report_path
from phase0.reporting.registry import scan_report_artifacts, write_report_manifest
from phase0.research.attribution.fold import run_strategy_fold_attribution
from phase0.strategy_admission import run_strategy_admission
from phase0.strategy_csi300_attribution import run_strategy_csi300_attribution
from phase0.strategy_core_reachability import run_strategy_core_reachability_diagnostic
from phase0.research.diagnostics.exposure import run_strategy_exposure_diagnostic
from phase0.research.diagnostics.filter import run_strategy_filter_diagnostic
from phase0.research.diagnostics.market_context import run_strategy_market_context
from phase0.strategy_failure_attribution import run_strategy_failure_attribution
from phase0.strategy_holdings_exposure import run_strategy_holdings_exposure
from phase0.strategy_missing_core_audit import run_missing_core_audit
from phase0.strategy_participation_overlay import run_strategy_participation_overlay
from phase0.strategy_role_card import run_strategy_role_card
from phase0.throttle import configure_akshare_throttle
from phase0.tushare_history_backfill import backfill_tushare_financials_from_config, backfill_tushare_history_from_config
from phase0.universe import build_local_factor_universe
from phase0.update_history import update_manual_history_from_config
from phase0.walk_forward import describe_walk_forward_presets, run_cost_sensitivity, run_walk_forward, save_walk_forward_csv


def summarize_system_maintenance_status(result) -> dict[str, object]:
    last_run_status_counts = Counter(row.last_run_status or "not_available" for row in result.rows)
    last_decision_counts = Counter(row.last_decision or "not_available" for row in result.rows)
    shard_status_counts = Counter(shard.status or "not_available" for shard in result.shards)
    return {
        "task_count": len(result.rows),
        "last_run_status_counts": dict(sorted(last_run_status_counts.items())),
        "last_decision_counts": dict(sorted(last_decision_counts.items())),
        "running_shard_count": int(shard_status_counts.get("running", 0)),
        "shard_status_counts": dict(sorted(shard_status_counts.items())),
    }


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


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


def _load_report_config_if_available(config_path: Path) -> dict | None:
    if not config_path.exists():
        return None
    return load_config(config_path)


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def _print_tushare_financial_progress(console: Console, progress: dict) -> None:
    target = int(progress.get("target_tasks") or 0)
    processed = int(progress.get("processed_tasks") or 0)
    elapsed = float(progress.get("elapsed_seconds") or 0.0)
    remaining = max(target - processed, 0)
    percent = (processed / target * 100.0) if target else 100.0
    rate = (processed / elapsed * 60.0) if elapsed > 0 else 0.0
    eta = _format_duration(remaining / (processed / elapsed)) if processed > 0 and elapsed > 0 else "unknown"
    event = str(progress.get("event") or "progress")
    label = "selected" if event == "start" else "progress"
    console.print(
        "[cyan]Tushare financial backfill {label}:[/cyan] "
        "{processed}/{target} ({percent:.1f}%), "
        "fetched={fetched}, empty={empty}, failed={failed}, inserted_rows={inserted}, "
        "rate={rate:.1f}/min, elapsed={elapsed_text}, eta={eta}".format(
            label=label,
            processed=processed,
            target=target,
            percent=percent,
            fetched=int(progress.get("fetched_tasks") or 0),
            empty=int(progress.get("empty_tasks") or 0),
            failed=int(progress.get("failed_tasks") or 0),
            inserted=int(progress.get("inserted_rows") or 0),
            rate=rate,
            elapsed_text=_format_duration(elapsed),
            eta=eta,
        )
    )


def _print_walk_forward_trace(console: Console, payload: dict[str, object]) -> None:
    event = str(payload.get("event") or "")
    strategy_id = str(payload.get("strategy_id") or "")
    fold = int(payload.get("fold") or 0)
    if event == "fold_start":
        console.print(
            "WF fold start: "
            f"strategy={strategy_id} fold={fold} "
            f"train={payload.get('train_start')}..{payload.get('train_end')} "
            f"valid={payload.get('valid_start')}..{payload.get('valid_end')} "
            f"train_symbols={payload.get('train_symbols')} valid_symbols={payload.get('valid_symbols')}"
        )
        return
    if event == "fold_params":
        console.print(
            "WF fold params: "
            f"strategy={strategy_id} fold={fold} eligible={payload.get('eligible')} "
            f"params={payload.get('formatted_params')}"
        )
        return
    if event == "fold_result":
        first_symbols = payload.get("first_target_symbols") or []
        console.print(
            "WF fold result: "
            f"strategy={strategy_id} fold={fold} "
            f"ann={float(payload.get('annualized_return') or 0.0):.4f} "
            f"sharpe={float(payload.get('sharpe') or 0.0):.4f} "
            f"turnover={float(payload.get('turnover_annual') or 0.0):.2f} "
            f"trades={int(payload.get('trades') or 0)} "
            f"target_days={int(payload.get('target_days') or 0)} "
            f"live_days={int(payload.get('live_days') or 0)} "
            f"avg_target_holdings={float(payload.get('avg_target_holdings') or 0.0):.2f} "
            f"avg_live_holdings={float(payload.get('avg_live_holdings') or 0.0):.2f} "
            f"trade_days={int(payload.get('trade_days') or 0)} "
            f"first_target_date={payload.get('first_target_date') or ''} "
            f"first_target_symbols={','.join(str(item) for item in first_symbols)} "
            f"constraint={payload.get('constraint_mode') or ''}/{payload.get('constraint_status') or ''}"
        )


def _run_db_health_gate(
    *,
    console: Console,
    config: dict,
    root: Path,
    scope: str,
    fail_on: str,
    label: str,
) -> int:
    console.print(f"[bold]{label} data health check started[/bold]")
    result = run_database_health_check(
        config=config,
        root=root,
        scope=scope,
        output_dir=None,
    )
    color = "green" if result.status == "pass" else ("yellow" if result.status == "warning" else "red")
    console.print(
        f"[{color}]{label} data health status: {result.status}[/{color}] "
        f"(errors={result.error_count}, warnings={result.warning_count}, info={result.info_count})"
    )
    console.print(f"Health report: {result.summary_md}")
    if fail_on == "error" and result.error_count > 0:
        return 2
    if fail_on == "warning" and (result.error_count > 0 or result.warning_count > 0):
        return 2
    return 0


def _export_phase0_low_turnover_bill(
    *,
    config_path: Path,
    strategy_id: str | None = None,
    refresh_cache: bool = False,
    no_panel_cache: bool = False,
) -> dict:
    from scripts.export_strategy_bill import DEFAULT_STRATEGY_ID, export_strategy_bill

    resolved_strategy_id = strategy_id or DEFAULT_STRATEGY_ID
    cfg = _load_report_config_if_available(config_path)
    report_run = create_report_run(root=config_path.resolve().parent, config=cfg, command="bill", scope=resolved_strategy_id)

    return export_strategy_bill(
        config_path=config_path,
        strategy_id=strategy_id,
        output=report_run.artifact("bill", "transactions", "csv"),
        daily_output=report_run.artifact("bill", "daily_assets", "csv"),
        preview_output=report_run.artifact("bill", "preview", "html"),
        refresh_cache=refresh_cache,
        no_panel_cache=no_panel_cache,
    )


def _export_phase0_market_regime_report(*, root: Path | None = None) -> dict:
    from scripts.export_market_regime_report import export_market_regime_report

    resolved_root = root or Path.cwd()
    legacy_input = resolved_root / "reports" / "phase0_low_turnover_oos_curve.csv"
    archive_input = (
        resolved_root
        / "reports"
        / "archive"
        / "legacy_root_reports"
        / "phase0_outputs"
        / "phase0_low_turnover_oos_curve.csv"
    )
    cfg = _load_report_config_if_available(resolved_root / "config.yaml")
    report_run = create_report_run(root=resolved_root, config=cfg, command="market-regime", scope="low_turnover")

    return export_market_regime_report(
        input_path=legacy_input if legacy_input.exists() else archive_input,
        summary_output=report_run.artifact("market_regime", "summary", "csv"),
        segment_output=report_run.artifact("market_regime", "segments", "csv"),
        html_output=report_run.artifact("market_regime", "report", "html"),
    )


def _export_phase0_oos_report(
    *,
    config_path: Path,
    strategy_id: str | None = None,
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
    from scripts.export_strategy_oos_report import export_strategy_oos_report

    return export_strategy_oos_report(
        config_path=config_path,
        strategy_id=strategy_id,
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

    cfg = _load_report_config_if_available(config_path)
    report_run = create_report_run(root=config_path.resolve().parent, config=cfg, command="financial-pti", scope="qfq_asof")

    return audit_financial_pti(
        config_path=config_path,
        summary_output=report_run.artifact("financial_pti", "summary", "csv"),
        sample_output=report_run.artifact("financial_pti", "problem_samples", "csv"),
        html_output=report_run.artifact("financial_pti", "report", "html"),
    )


def _export_phase0_universe_pit(config_path: Path, *, as_of_date: str) -> dict:
    from scripts.audit_universe_pit import audit_universe_pit

    cfg = _load_report_config_if_available(config_path)
    report_run = create_report_run(root=config_path.resolve().parent, config=cfg, command="universe-pti", scope=as_of_date)

    return audit_universe_pit(
        config_path=config_path,
        as_of_date=as_of_date,
        report_output=report_run.artifact("universe_pti", "report", "html"),
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

    report_run = None
    latest_report_output = None
    if output is None or report_output is None:
        cfg = _load_report_config_if_available(config_path)
        report_run = create_report_run(root=config_path.resolve().parent, config=cfg, command="premarket", scope="watchlist")
    if output is None and report_run is not None:
        output = report_run.artifact("premarket", "watchlist", "csv")
    if report_output is None and report_run is not None:
        report_output = report_run.artifact("premarket", "report", "html")
        latest_report_output = latest_dir(root=config_path.resolve().parent, config=cfg, channel="watchlist") / "index.html"

    kwargs = {
        "config_path": config_path,
        "output": output,
        "report_output": report_output,
        "refresh_cache": refresh_cache,
        "no_panel_cache": no_panel_cache,
    }
    if latest_report_output is not None:
        kwargs["latest_report_output"] = latest_report_output
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
    report_run = create_report_run(root=config_path.resolve().parent, config=cfg, command="brief-account-bill", scope=account.account_id)
    output = report_run.artifact("account_bill", "report", "html")
    export_account_bill_html(account=account, brief_date=brief_date, output_path=output)
    return {"account": account.account_id, "brief_date": brief_date, "account_bill": output}


def _export_phase0_execution_gate(
    *,
    config_path: Path,
    strategy_id: str | None = None,
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
        strategy_id=strategy_id,
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
                quality_results.append(audit_quality(sym, df))
            except Exception:
                continue
        quality_summary = aggregate_quality(quality_results)

    report_dir = report_category_dir(root=root, config=cfg, category="phase0")
    write_data_source_report(
        report_path(root=root, config=cfg, category="phase0", parts=("phase0_data_source_report.md",)),
        connectivity=connectivity,
        quality=quality_results,
        quality_summary=quality_summary,
    )

    console.print("3) Running walk-forward backtest baseline...")
    for line in describe_walk_forward_presets(cfg.get("walk_forward", {})):
        console.print(f"[cyan]{line}[/cyan]")
    wf = run_walk_forward(cfg)
    folds_df = wf["folds"]
    candidate_folds_df = wf.get("candidate_folds")
    summary = wf["summary"]

    if not folds_df.empty:
        save_walk_forward_csv(folds_df, report_path(root=root, config=cfg, category="phase0", parts=("phase0_walk_forward_folds.csv",)))
    if candidate_folds_df is not None and not candidate_folds_df.empty:
        save_walk_forward_csv(candidate_folds_df, report_path(root=root, config=cfg, category="phase0", parts=("phase0_walk_forward_candidates.csv",)))
    universe_audit_df = wf.get("universe_audit")
    if universe_audit_df is not None and not universe_audit_df.empty:
        save_walk_forward_csv(universe_audit_df, report_path(root=root, config=cfg, category="phase0", parts=("phase0_walk_forward_universe_audit.csv",)))
    write_walk_forward_report(
        report_path(root=root, config=cfg, category="phase0", parts=("phase0_walk_forward_report.md",)),
        summary=summary,
        folds_df=folds_df,
    )
    write_effectiveness_gate_report(
        report_path(root=root, config=cfg, category="phase0", parts=("phase0_effectiveness_report.md",)),
        wf_summary=summary,
        gate_cfg=cfg.get("walk_forward", {}).get("gate", {}),
    )

    console.print("4) Exporting selected strategy bill and daily assets...")
    bill_result = _export_phase0_low_turnover_bill(config_path=config_path)
    console.print(f"Bill: {bill_result['bill']}")
    console.print(f"Daily assets: {bill_result['daily']}")
    console.print(f"Bill preview: {bill_result['preview']}")
    console.print(f"Bill rows: {bill_result['rows']}")

    console.print("[green]Phase 0 complete[/green]")
    console.print(f"Reports: {report_dir}")
    return 0


def run_phase0_cost_sensitivity(config_path: Path, scenarios: list[dict[str, float | str]]) -> int:
    console = Console()
    root = config_path.parent
    cfg = load_config(config_path)
    configure_local_history(cfg.get("local_history", {}), root)
    configure_akshare_throttle(cfg.get("data_sources", {}).get("akshare", {}))

    cfg["cost_sensitivity"] = {
        "enabled": True,
        "scenarios": scenarios,
    }
    report_dir = report_category_dir(root=root, config=cfg, category="phase0")
    console.print("[bold]Phase 0 cost sensitivity started[/bold]")
    console.print("Scenarios:")
    for scenario in scenarios:
        console.print(
            f"- {scenario['name']}: "
            f"slippage={float(scenario['slippage']):.5f}, "
            f"commission={float(scenario['commission']):.5f}, "
            f"stamp_duty_sell={float(scenario['stamp_duty_sell']):.5f}"
        )

    sensitivity_df = run_cost_sensitivity(cfg)
    if not sensitivity_df.empty:
        save_walk_forward_csv(sensitivity_df, report_path(root=root, config=cfg, category="phase0", parts=("phase0_cost_sensitivity.csv",)))
    write_cost_sensitivity_report(
        report_path(root=root, config=cfg, category="phase0", parts=("phase0_cost_sensitivity_report.md",)),
        sensitivity_df,
    )

    console.print("[green]Phase 0 cost sensitivity complete[/green]")
    console.print(f"Reports: {report_dir}")
    return 0


def _parse_cost_scenario(text: str, cfg: dict) -> dict[str, float | str]:
    parts = [part.strip() for part in text.split(":")]
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"invalid cost scenario '{text}', expected name:slippage")
    wcfg = cfg.get("walk_forward", {})
    return {
        "name": parts[0],
        "slippage": float(parts[1]),
        "commission": float(wcfg.get("commission", 0.0)),
        "stamp_duty_sell": float(wcfg.get("stamp_duty_sell", 0.0)),
    }


def _configured_cost_scenarios(cfg: dict) -> list[dict[str, float | str]]:
    scenarios = cfg.get("cost_sensitivity", {}).get("scenarios", [])
    return [
        {
            "name": str(item["name"]),
            "slippage": float(item["slippage"]),
            "commission": float(item.get("commission", cfg.get("walk_forward", {}).get("commission", 0.0))),
            "stamp_duty_sell": float(item.get("stamp_duty_sell", cfg.get("walk_forward", {}).get("stamp_duty_sell", 0.0))),
        }
        for item in scenarios
    ]


def _print_manual_history_update_result(console: Console, result) -> None:
    color = "green" if result.ok else "red"
    console.print(f"[{color}]Manual history update status: {result.status}[/{color}]")
    console.print(f"Database: {result.db_path}")
    console.print(f"Calendar latest trade date: {result.calendar_trade_date}")
    console.print(f"Target trade date: {result.target_trade_date}")
    console.print(f"Before latest: {result.before_latest_date or 'N/A'} coverage={result.before_coverage:.4f}")
    console.print(f"After latest: {result.after_latest_date or 'N/A'} coverage={result.after_coverage:.4f}")
    console.print(f"Fetched rows: {result.fetched_rows}")
    console.print(f"Inserted rows: {result.inserted_rows}")
    console.print(f"Metadata updated rows: {result.metadata_updated_rows}")
    console.print(f"Primary source: {result.primary_source or 'N/A'}")
    if result.metadata_coverage:
        console.print(
            "Metadata coverage: "
            f"market_cap={result.metadata_coverage.get('market_cap', 0.0):.4f}, "
            f"pe={result.metadata_coverage.get('pe_ratio', 0.0):.4f}, "
            f"pb={result.metadata_coverage.get('pb_ratio', 0.0):.4f}, "
            f"turnover={result.metadata_coverage.get('turnover_rate', 0.0):.4f}"
        )
    if result.warnings:
        for warning in result.warnings:
            console.print(f"[yellow]Warning:[/yellow] {warning}")


def run_watchlist_pipeline(
    *,
    config_path: Path,
    skip_update: bool = False,
    check_only: bool = False,
    refresh_cache: bool = False,
    no_panel_cache: bool = False,
) -> int:
    console = Console()
    cfg = load_config(config_path)
    console.print("[bold]Phase 0 watchlist pipeline started[/bold]")

    history_result = None
    if skip_update:
        console.print("[yellow]1) Skipping A-share history update[/yellow]")
    else:
        console.print("1) Updating A-share history...")
        history_result = update_manual_history_from_config(cfg, config_path.parent, check_only=check_only)
        _print_manual_history_update_result(console, history_result)
        if not history_result.ok:
            console.print("[red]Watchlist stopped because A-share history update failed.[/red]")
            return 2
        if check_only:
            console.print("[yellow]Watchlist stopped after freshness check because --check-only was set.[/yellow]")
            return 0

    should_refresh_cache = bool(refresh_cache)
    if history_result is not None and int(history_result.inserted_rows) > 0:
        should_refresh_cache = True
        console.print("[yellow]2) New A-share rows inserted; refreshing strategy panel cache[/yellow]")
    else:
        console.print("2) Generating premarket watchlist...")

    result = _export_phase0_premarket(
        config_path=config_path,
        refresh_cache=should_refresh_cache,
        no_panel_cache=bool(no_panel_cache),
    )
    report_path = Path(result["report"])
    watchlist_today_paths = [
        latest_dir(root=config_path.parent, config=cfg, channel="watchlist") / "index.html",
        config_path.parent / "reports" / "watchlist_today" / "index.html",
        Path("/mnt/d/ZJ/Dev/brief_today/index.html"),
    ]
    for watchlist_today_path in watchlist_today_paths:
        watchlist_today_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(report_path, watchlist_today_path)
    _sync_watchlist_to_ecs(console, config_path.parent / "reports" / "watchlist_today")
    console.print("[green]Watchlist pipeline complete[/green]")
    console.print(f"Watchlist: {result['watchlist']}")
    console.print(f"Report: {result['report']}")
    for watchlist_today_path in watchlist_today_paths:
        console.print(f"Watchlist today: {watchlist_today_path}")
    if "ledger" in result:
        console.print(f"Simulation ledger: {result['ledger']}")
    if "account_ledger" in result:
        console.print(f"Account ledger: {result['account_ledger']}")
    if "account_bill" in result:
        console.print(f"Account bill: {result['account_bill']}")
    console.print(f"Rows: {result['rows']}")
    console.print(f"Signal date: {result['signal_date']}")
    console.print(f"Check time: {result['check_time']}")

    if history_result is not None and history_result.after_latest_date and result.get("signal_date"):
        if str(history_result.after_latest_date) != str(result["signal_date"]):
            console.print(
                "[yellow]Warning:[/yellow] "
                f"history latest date is {history_result.after_latest_date}, "
                f"but strategy signal date is {result['signal_date']}."
            )
    return 0


def run_daily_brief_pipeline(
    *,
    config_path: Path,
    watchlist: bool = False,
    skip_update: bool = False,
    check_only: bool = False,
    refresh_cache: bool = False,
    no_panel_cache: bool = False,
) -> int:
    console = Console()
    if not watchlist:
        console.print(
            "[yellow]Warning:[/yellow] full daily brief is not implemented yet; "
            "running --watchlist compatibility mode."
        )
    return run_watchlist_pipeline(
        config_path=config_path,
        skip_update=skip_update,
        check_only=check_only,
        refresh_cache=refresh_cache,
        no_panel_cache=no_panel_cache,
    )


def main() -> int:
    top_level_groups = {
        "Data Import & Update": [
            "backfill-adjustment-factors",
            "backfill-daily-basic",
            "backfill-index-asof",
            "backfill-tushare-financials",
            "backfill-tushare-history",
            "build-universe",
            "import-history",
            "import-index-history",
            "update-financials",
            "update-hk-market-history",
            "update-history",
            "update-us-market-history",
        ],
        "Delivery & Reports": [
            "bill",
            "brief",
            "daily-brief",
            "market-regime",
            "oos-report",
            "premarket",
        ],
        "Governance & Research": [
            "adjustment-audit",
            "cost-sensitivity",
            "db-health",
            "execution-gate",
            "factor-effectiveness",
            "financial-pti",
            "index-asof-audit",
            "intelligence",
            "overfit-diagnostic",
            "run",
            "strategy-admission",
            "strategy-core-reachability-diagnostic",
            "strategy-csi300-attribution",
            "strategy-exposure-diagnostic",
            "strategy-failure-attribution",
            "strategy-filter-diagnostic",
            "strategy-fold-attribution",
            "strategy-holdings-exposure",
            "strategy-market-context",
            "strategy-missing-core-audit",
            "strategy-participation-overlay",
            "strategy-role-card",
            "universe-pti",
        ],
        "Operations": [
            "dashboard",
            "maintain",
            "system",
        ],
    }
    grouped_help_lines = ["Top-level command index by category:"]
    for group_name in sorted(top_level_groups):
        grouped_help_lines.append(f"  {group_name}:")
        grouped_help_lines.extend([f"    - {name}" for name in sorted(top_level_groups[group_name])])
    parser = argparse.ArgumentParser(
        description="Run Phase 0 pipeline",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "\n".join(grouped_help_lines)
            + "\n\n"
            "Nested command groups:\n"
            "  brief: account-bill, daily, daily-brief, premarket, watchlist\n"
            "  dashboard: scan\n"
            "  intelligence: collect, import-local, review-candidates, validate\n"
            "  maintain: resume, run, status, stop, supervise, tick\n"
            "  system: status\n"
        ),
    )
    sub = parser.add_subparsers(dest="cmd")
    run_parser = sub.add_parser("run", help="Run phase0 pipeline")
    run_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    cost_parser = sub.add_parser("cost-sensitivity", help="Run explicit phase0 cost sensitivity scenarios")
    cost_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    cost_parser.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="Scenario in name:slippage format. Repeatable, e.g. --scenario base:0.001 --scenario stress:0.003",
    )
    cost_parser.add_argument(
        "--use-config-scenarios",
        action="store_true",
        help="Use cost_sensitivity.scenarios from config.yaml. Required when --scenario is omitted.",
    )
    bill_parser = sub.add_parser("bill", help="Export selected phase0 strategy bill artifacts")
    bill_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    bill_parser.add_argument("--strategy-id", default=None, help="Registered strategy ID; defaults to strategy_reports.default_strategy_id")
    bill_parser.add_argument("--refresh-cache", action="store_true", help="Rebuild cached market panel before exporting")
    bill_parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")
    market_regime_parser = sub.add_parser("market-regime", help="Export phase0 market-regime validation report")
    market_regime_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    oos_parser = sub.add_parser("oos-report", help="Export phase0 continuous OOS report with execution profile")
    oos_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    oos_parser.add_argument("--strategy-id", default=None, help="Registered strategy ID; defaults to strategy_reports.default_strategy_id")
    oos_parser.add_argument("--profile", choices=["research", "live"], default=None, help="Execution parameter profile: research or live")
    oos_parser.add_argument("--output-dir", default=None, help="Optional standalone output directory for OOS artifacts")
    oos_parser.add_argument("--slippage", type=float, default=None, help="Override profile slippage for this run")
    oos_parser.add_argument("--commission", type=float, default=None, help="Override profile commission for this run")
    oos_parser.add_argument("--stamp-duty-sell", type=float, default=None, help="Override profile sell stamp duty for this run")
    oos_parser.add_argument("--price-mode", choices=["close", "next_open", "conservative"], default=None, help="Override profile execution price mode")
    oos_parser.add_argument("--lot-size", type=int, default=None, help="Override profile lot size")
    oos_parser.add_argument("--max-participation-rate", type=float, default=None, help="Override profile max market-volume participation rate")
    oos_parser.add_argument("--enable-limit-check", action=argparse.BooleanOptionalAction, default=None, help="Override profile limit-up/down check")
    oos_parser.add_argument("--enable-suspension-check", action=argparse.BooleanOptionalAction, default=None, help="Override profile suspension check")
    oos_parser.add_argument("--refresh-cache", action="store_true", help="Rebuild cached market panel before exporting")
    oos_parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")
    financial_pti_parser = sub.add_parser("financial-pti", help="Audit financial factor point-in-time validity")
    financial_pti_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    universe_pti_parser = sub.add_parser("universe-pti", help="Audit point-in-time universe listing and industry boundaries")
    universe_pti_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    universe_pti_parser.add_argument("--date", required=True, help="As-of date in YYYY-MM-DD")
    adjustment_parser = sub.add_parser("adjustment-audit", help="Audit A-share price adjustment point-in-time readiness")
    adjustment_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    adjustment_parser.add_argument("--output-csv", default=None, help="Optional CSV output path")
    adjustment_parser.add_argument("--output-md", default=None, help="Optional Markdown output path")
    overfit_parser = sub.add_parser("overfit-diagnostic", help="Generate strategy overfitting diagnostic report")
    overfit_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    overfit_parser.add_argument("--candidates", default=None, help="Path to walk-forward candidates CSV")
    overfit_parser.add_argument("--folds", default=None, help="Path to walk-forward folds CSV")
    overfit_parser.add_argument("--output-dir", default=None, help="Output directory for diagnostic reports")
    admission_parser = sub.add_parser("strategy-admission", help="Run strategy admission window and constraint review")
    admission_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    admission_parser.add_argument("--presets", nargs="+", default=None, help="Walk-forward preset names to evaluate")
    admission_parser.add_argument("--strategy-set", default=None, help="Admission strategy set name from walk_forward.admission.strategy_sets")
    admission_parser.add_argument("--strategies", nargs="+", default=None, help="Strategy IDs to evaluate")
    admission_parser.add_argument("--output-dir", default=None, help="Output directory for admission reports")
    admission_parser.add_argument("--trace-run", action="store_true", help="Print fold-level walk-forward trace while running")
    attribution_parser = sub.add_parser("strategy-failure-attribution", help="Attribute failed strategy admission decisions from existing CSV artifacts")
    attribution_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    attribution_parser.add_argument("--admission-dir", default=None, help="Directory containing existing strategy admission CSV artifacts")
    attribution_parser.add_argument("--folds", default=None, help="Path to strategy_admission_candidate_folds.csv")
    attribution_parser.add_argument("--matrix", default=None, help="Path to strategy_admission_window_matrix.csv")
    attribution_parser.add_argument("--constraints", default=None, help="Path to strategy_admission_constraint_review.csv")
    attribution_parser.add_argument("--overfit", default=None, help="Path to overfit_diagnostic/strategy_overfit_diagnostic.csv")
    attribution_parser.add_argument("--output-dir", default=None, help="Output directory for failure attribution artifacts")
    market_context_parser = sub.add_parser("strategy-market-context", help="Overlay benchmark market context onto strategy fold attribution")
    market_context_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    market_context_parser.add_argument("--fold-attribution", required=True, help="Path to strategy_failure_fold_attribution.csv")
    market_context_parser.add_argument("--output-dir", default=None, help="Output directory for market context artifacts")
    market_context_parser.add_argument("--benchmark-symbol", default=None, help="Benchmark symbol; defaults to phase0.benchmark_symbol")
    market_context_parser.add_argument("--trend-window", type=int, default=120, help="Benchmark trend moving-average window")
    market_context_parser.add_argument("--vol-window", type=int, default=20, help="Benchmark volatility window")
    market_context_parser.add_argument("--vol-quantile", type=float, default=0.70, help="Rolling volatility quantile for high-vol context")
    exposure_parser = sub.add_parser("strategy-exposure-diagnostic", help="Diagnose strong-benchmark lag exposure proxies from existing strategy artifacts")
    exposure_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    exposure_parser.add_argument("--candidate-folds", required=True, help="Path to strategy_admission_candidate_folds.csv")
    exposure_parser.add_argument("--market-context", required=True, help="Path to strategy_market_context_diagnostic.csv")
    exposure_parser.add_argument("--universe", default=None, help="Optional universe metadata CSV; defaults to data/universe/local_factor_universe.csv")
    exposure_parser.add_argument("--output-dir", default=None, help="Output directory for exposure diagnostic artifacts")
    filter_parser = sub.add_parser("strategy-filter-diagnostic", help="Diagnose strategy empty-exposure and hard-filter bottlenecks")
    filter_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    filter_parser.add_argument("--candidate-folds", required=True, help="Path to strategy_admission_candidate_folds.csv")
    filter_parser.add_argument("--strategy", required=True, help="Strategy ID to diagnose")
    filter_parser.add_argument("--presets", nargs="+", default=None, help="Optional walk-forward preset names to include")
    filter_parser.add_argument("--folds", nargs="+", type=int, default=None, help="Optional fold numbers to include")
    filter_parser.add_argument("--output-dir", default=None, help="Output directory for filter diagnostic artifacts")
    core_reach_parser = sub.add_parser("strategy-core-reachability-diagnostic", help="Diagnose complete CSI300 core-weight reachability from as-of benchmark weights")
    core_reach_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    core_reach_parser.add_argument("--candidate-folds", required=True, help="Path to strategy_admission_candidate_folds.csv")
    core_reach_parser.add_argument("--output-dir", required=True, help="Output directory for core reachability artifacts")
    core_reach_parser.add_argument("--benchmark-symbol", default=None, help="Benchmark symbol; defaults to phase0.benchmark_symbol")
    core_reach_parser.add_argument("--presets", nargs="+", default=None, help="Optional walk-forward preset names to include")
    core_reach_parser.add_argument("--folds", nargs="+", type=int, default=None, help="Optional fold numbers to include")
    core_reach_parser.add_argument("--core-top-n", type=int, default=60, help="Benchmark rank cutoff for core constituents")
    core_reach_parser.add_argument("--core-cumulative-weight", type=float, default=0.60, help="Cumulative benchmark weight cutoff for core constituents")
    core_reach_parser.add_argument("--top-n", type=int, default=20, help="Complete benchmark top-weight constituent count to audit")
    core_reach_parser.add_argument("--min-amount", type=float, default=0.0, help="Minimum daily amount required for reachability")
    core_reach_parser.add_argument("--min-amount-ratio20", type=float, default=0.0, help="Minimum amount_ratio20 required for reachability")
    core_reach_parser.add_argument("--weight-date-lag-days", type=int, default=1, help="Calendar-day lag before looking up benchmark weights")
    core_reach_parser.add_argument("--seed-benchmark-core", action="store_true", help="Read-only experiment: append missing benchmark core/top members into the diagnostic panel")
    core_reach_parser.add_argument("--seed-top-n", type=int, default=None, help="Benchmark top-N members to seed when --seed-benchmark-core is used; defaults to --top-n")
    core_reach_parser.add_argument("--seed-core-top-n", type=int, default=None, help="Benchmark core rank cutoff to seed; defaults to --core-top-n")
    core_reach_parser.add_argument("--seed-core-cumulative-weight", type=float, default=None, help="Benchmark cumulative core weight to seed; defaults to --core-cumulative-weight")
    missing_core_parser = sub.add_parser("strategy-missing-core-audit", help="Audit why benchmark core members are missing from PIT panels")
    missing_core_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    missing_core_parser.add_argument("--missing-reasons", required=True, help="Path to strategy_core_reachability_failure_reasons.csv")
    missing_core_parser.add_argument("--candidate-folds", required=True, help="Path to strategy_admission_candidate_folds.csv")
    missing_core_parser.add_argument("--output-dir", required=True, help="Output directory for missing-core audit artifacts")
    missing_core_parser.add_argument("--top-symbols", type=int, default=30, help="Number of missing symbols to audit by total missing weight")
    holdings_parser = sub.add_parser("strategy-holdings-exposure", help="Rebuild research-only daily holdings and industry exposure for strategy folds")
    holdings_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    holdings_parser.add_argument("--candidate-folds", required=True, help="Path to strategy_admission_candidate_folds.csv")
    holdings_parser.add_argument("--market-context", required=True, help="Path to strategy_market_context_diagnostic.csv")
    holdings_parser.add_argument("--strategy", required=True, help="Strategy ID to rebuild")
    holdings_parser.add_argument("--presets", nargs="+", default=None, help="Optional walk-forward preset names to include")
    holdings_parser.add_argument("--folds", nargs="+", type=int, default=None, help="Optional fold numbers to include")
    holdings_parser.add_argument("--benchmark-symbol", default=None, help="Benchmark symbol; defaults to phase0.benchmark_symbol")
    holdings_parser.add_argument("--output-dir", default=None, help="Output directory for holdings exposure artifacts")
    fold_attr_parser = sub.add_parser("strategy-fold-attribution", help="Assemble read-only paired fold attribution from existing diagnostics")
    fold_attr_parser.add_argument("--quality-fold-attribution", required=True, help="Path to quality strategy_failure_fold_attribution.csv")
    fold_attr_parser.add_argument("--price-volume-fold-attribution", required=True, help="Path to price-volume strategy_failure_fold_attribution.csv")
    fold_attr_parser.add_argument("--quality-market-context", required=True, help="Path to quality strategy_market_context_diagnostic.csv")
    fold_attr_parser.add_argument("--price-volume-market-context", required=True, help="Path to price-volume strategy_market_context_diagnostic.csv")
    fold_attr_parser.add_argument("--quality-holdings", required=True, help="Path to quality strategy_daily_holdings.csv")
    fold_attr_parser.add_argument("--price-volume-holdings", required=True, help="Path to price-volume strategy_daily_holdings.csv")
    fold_attr_parser.add_argument("--quality-daily-exposure", required=True, help="Path to quality strategy_daily_exposure.csv")
    fold_attr_parser.add_argument("--price-volume-daily-exposure", required=True, help="Path to price-volume strategy_daily_exposure.csv")
    fold_attr_parser.add_argument("--output-dir", required=True, help="Output directory for paired fold attribution artifacts")
    index_asof_parser = sub.add_parser("index-asof-audit", help="Audit benchmark constituent and weight as-of data readiness")
    index_asof_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    index_asof_parser.add_argument("--benchmark-symbol", default=None, help="Benchmark symbol; defaults to phase0.benchmark_symbol")
    index_asof_parser.add_argument("--candidate-folds", default=None, help="Optional strategy_admission_candidate_folds.csv for fold-level coverage")
    index_asof_parser.add_argument("--output-dir", default=None, help="Output directory for index as-of audit artifacts")
    participation_parser = sub.add_parser("strategy-participation-overlay", help="Run research-only minimum-exposure counterfactual on daily holdings")
    participation_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    participation_parser.add_argument("--holdings", required=True, help="Path to strategy_daily_holdings.csv")
    participation_parser.add_argument("--daily-exposure", required=True, help="Path to strategy_daily_exposure.csv")
    participation_parser.add_argument("--output-dir", required=True, help="Output directory for participation overlay artifacts")
    participation_parser.add_argument("--min-exposure", type=float, default=0.65, help="Minimum gross exposure target for scoped rows")
    participation_parser.add_argument("--max-symbol-weight", type=float, default=0.10, help="Per-symbol live weight cap after scaling")
    participation_parser.add_argument("--max-scale", type=float, default=2.0, help="Maximum per-day scaling factor")
    participation_parser.add_argument("--context-label", default="relative_lag_in_strong_benchmark_context", help="Market context label to rescale; use 'all' for no filter")
    csi300_attr_parser = sub.add_parser("strategy-csi300-attribution", help="Attribute strong CSI300 lag using as-of benchmark weights")
    csi300_attr_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    csi300_attr_parser.add_argument("--holdings", default=None, help="Optional path to strategy_daily_holdings.csv")
    csi300_attr_parser.add_argument("--daily-exposure", default=None, help="Optional path to strategy_daily_exposure.csv")
    csi300_attr_parser.add_argument("--candidate-folds", default=None, help="Optional strategy_admission_candidate_folds.csv for fold date scaffolding")
    csi300_attr_parser.add_argument("--market-context", default=None, help="Optional strategy_market_context_diagnostic.csv for context filtering")
    csi300_attr_parser.add_argument("--output-dir", required=True, help="Output directory for CSI300 attribution artifacts")
    csi300_attr_parser.add_argument("--benchmark-symbol", default=None, help="Benchmark symbol; defaults to phase0.benchmark_symbol")
    csi300_attr_parser.add_argument("--context-label", default="relative_lag_in_strong_benchmark_context", help="Market context label to diagnose; use 'all' for no filter")
    csi300_attr_parser.add_argument("--top-n", type=int, default=20, help="Benchmark top-weight constituent count to audit")
    csi300_attr_parser.add_argument("--weight-date-lag-days", type=int, default=1, help="Calendar-day lag before looking up benchmark weights; default avoids same-day close as pre-trade visible")
    role_card_parser = sub.add_parser("strategy-role-card", help="Build a research-only strategy role card from existing diagnostics")
    role_card_parser.add_argument("--strategy", required=True, help="Strategy ID to summarize")
    role_card_parser.add_argument("--matrix", required=True, help="Path to strategy_admission_window_matrix.csv")
    role_card_parser.add_argument("--constraints", required=True, help="Path to strategy_admission_constraint_review.csv")
    role_card_parser.add_argument("--fold-attribution", default=None, help="Optional strategy_failure_fold_attribution.csv")
    role_card_parser.add_argument("--market-context", default=None, help="Optional strategy_market_context_diagnostic.csv")
    role_card_parser.add_argument("--holdings-summary", default=None, help="Optional strategy_holdings_exposure_summary.csv")
    role_card_parser.add_argument("--overlay-summary", default=None, help="Optional strategy_participation_overlay_summary.csv")
    role_card_parser.add_argument("--output-dir", required=True, help="Output directory for role-card artifacts")
    factor_parser = sub.add_parser("factor-effectiveness", help="Generate point-in-time factor effectiveness report")
    factor_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    factor_parser.add_argument("--output-dir", default=None, help="Output directory for factor effectiveness artifacts")
    db_health_parser = sub.add_parser("db-health", help="Run read-only SQLite database health checks")
    db_health_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    db_health_parser.add_argument(
        "--scope",
        choices=["all", "cn", "financial", "cross_market", "scheduler"],
        default="all",
        help="Health-check scope. Default: all",
    )
    db_health_parser.add_argument("--as-of", default=None, help="As-of date in YYYY-MM-DD. Defaults to today.")
    db_health_parser.add_argument("--output-dir", default=None, help="Output directory for health-check artifacts")
    db_health_parser.add_argument(
        "--fail-on",
        choices=["error", "warning", "never"],
        default="never",
        help="Exit with code 2 when result has errors, warnings, or never. Default: never.",
    )
    dashboard_parser = sub.add_parser("dashboard", help="Report dashboard commands")
    dashboard_sub = dashboard_parser.add_subparsers(dest="dashboard_cmd")
    dashboard_scan_parser = dashboard_sub.add_parser("scan", help="Scan reports and write dashboard manifest")
    dashboard_scan_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    dashboard_scan_parser.add_argument("--manifest", default=None, help="Optional manifest output path")
    intelligence_parser = sub.add_parser(
        "intelligence",
        help="Collect, import, review, and validate strategy intelligence metadata",
    )
    intelligence_sub = intelligence_parser.add_subparsers(dest="intelligence_cmd")
    intelligence_collect_parser = intelligence_sub.add_parser("collect", help="Collect configured intelligence metadata into an inbox CSV")
    intelligence_collect_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    intelligence_collect_parser.add_argument("--output-csv", default=None, help="Optional candidate inbox CSV output path")
    intelligence_collect_parser.add_argument("--output-report", default=None, help="Optional Markdown report output path")
    intelligence_collect_parser.add_argument("--limit", type=int, default=None, help="Optional per-source row/file limit")
    intelligence_import_parser = intelligence_sub.add_parser("import-local", help="Import local paper/report metadata into an inbox CSV")
    intelligence_import_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    intelligence_import_parser.add_argument("--source-dir", default="refdocs/papers", help="Local source directory to scan")
    intelligence_import_parser.add_argument("--output-csv", default=None, help="Optional candidate inbox CSV output path")
    intelligence_import_parser.add_argument("--output-report", default=None, help="Optional Markdown report output path")
    intelligence_import_parser.add_argument("--limit", type=int, default=None, help="Optional file limit")
    intelligence_review_parser = intelligence_sub.add_parser(
        "review-candidates",
        help="Generate review suggestions for an intelligence inbox CSV",
    )
    intelligence_review_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    intelligence_review_parser.add_argument("--candidates-csv", required=True, help="Candidate inbox CSV to review")
    intelligence_review_parser.add_argument("--output-csv", default=None, help="Optional review suggestions CSV output path")
    intelligence_review_parser.add_argument("--output-report", default=None, help="Optional Markdown review report output path")
    intelligence_review_parser.add_argument("--limit", type=int, default=None, help="Optional candidate row limit")
    intelligence_review_parser.add_argument(
        "--excerpt-chars",
        type=int,
        default=2000,
        help="Maximum source excerpt chars per candidate",
    )
    intelligence_validate_parser = intelligence_sub.add_parser("validate", help="Validate the strategy intelligence ledger CSV")
    intelligence_validate_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    intelligence_validate_parser.add_argument("--ledger", default=None, help="Ledger CSV path. Defaults to config intelligence.ledger")
    intelligence_validate_parser.add_argument("--output-report", default=None, help="Optional Markdown validation report output path")
    maintain_parser = sub.add_parser("maintain", help="Maintenance orchestrator commands")
    maintain_sub = maintain_parser.add_subparsers(dest="maintain_cmd")
    maintain_tick_parser = maintain_sub.add_parser("tick", help="Evaluate scheduled maintenance tasks")
    maintain_tick_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    maintain_tick_parser.add_argument("--dry-run", action="store_true", help="Only evaluate scheduling decisions, do not start tasks")
    maintain_tick_parser.add_argument("--as-of", default=None, help="Optional local time in YYYY-MM-DD HH:MM")
    maintain_status_parser = maintain_sub.add_parser("status", help="Show maintenance orchestrator task status")
    maintain_status_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    maintain_status_parser.add_argument("--write-report", action="store_true", help="Write the default Markdown maintenance report")
    maintain_status_parser.add_argument("--output-md", default=None, help="Optional Markdown report path")
    maintain_supervise_parser = maintain_sub.add_parser("supervise", help="Refresh long-running shard status without starting or stopping tasks")
    maintain_supervise_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    maintain_supervise_parser.add_argument("--task", choices=["tushare_financial_backfill"], default="tushare_financial_backfill", help="Task name")
    maintain_supervise_parser.add_argument("--run-id", type=int, default=None, help="Optional run id")
    maintain_supervise_parser.add_argument("--dry-run", action="store_true", help="Show candidate status updates without writing them")
    maintain_run_parser = maintain_sub.add_parser("run", help="Start an orchestrated maintenance task")
    maintain_run_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    maintain_run_parser.add_argument("--task", required=True, choices=["tushare_financial_backfill"], help="Task name")
    maintain_run_parser.add_argument("--start-period", default="2018-06-30", help="Financial start period in YYYY-MM-DD")
    maintain_run_parser.add_argument("--end-period", default="2026-03-31", help="Financial end period in YYYY-MM-DD")
    maintain_run_parser.add_argument("--shard-count", type=int, default=3, help="Number of shards. Default: 3")
    maintain_run_parser.add_argument("--max-requests-per-minute", type=int, default=67, help="Per-shard request throttle. Default: 67")
    maintain_run_parser.add_argument("--retry-failed", action=argparse.BooleanOptionalAction, default=True, help="Retry failed backfill tasks")
    maintain_run_parser.add_argument("--missing-fields-only", action="store_true", help="Only patch rows that have missing fields")
    maintain_run_parser.add_argument("--limit-tasks", type=int, default=None, help="Optional per-shard task limit")
    maintain_run_parser.add_argument("--dry-run", action="store_true", help="Register shard commands without starting processes")
    maintain_stop_parser = maintain_sub.add_parser("stop", help="Stop an orchestrated long-running task")
    maintain_stop_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    maintain_stop_parser.add_argument("--task", choices=["tushare_financial_backfill"], default="tushare_financial_backfill", help="Task name")
    maintain_stop_parser.add_argument("--run-id", type=int, default=None, help="Optional run id")
    maintain_stop_parser.add_argument("--dry-run", action="store_true", help="Show matched shards without stopping them")
    maintain_resume_parser = maintain_sub.add_parser("resume", help="Resume non-running, non-succeeded shards")
    maintain_resume_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    maintain_resume_parser.add_argument("--task", choices=["tushare_financial_backfill"], default="tushare_financial_backfill", help="Task name")
    maintain_resume_parser.add_argument("--run-id", type=int, default=None, help="Optional run id")
    maintain_resume_parser.add_argument("--dry-run", action="store_true", help="Show matched shards without restarting them")
    system_parser = sub.add_parser("system", help="System orchestrator commands")
    system_sub = system_parser.add_subparsers(dest="system_cmd")
    system_status_parser = system_sub.add_parser("status", help="Show read-only system status summary")
    system_status_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    brief_parser = sub.add_parser("brief", help="Brief delivery commands")
    brief_sub = brief_parser.add_subparsers(dest="brief_cmd")
    brief_daily_parser = brief_sub.add_parser("daily", help="Generate the daily brief; currently uses watchlist output")
    brief_daily_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    brief_daily_parser.add_argument("--skip-update", action="store_true", help="Skip A-share history update")
    brief_daily_parser.add_argument("--check-only", action="store_true", help="Only check A-share history freshness; do not export")
    brief_daily_parser.add_argument("--refresh-cache", action="store_true", help="Rebuild cached market panel before exporting")
    brief_daily_parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")
    brief_daily_compat_parser = brief_sub.add_parser("daily-brief", help="Compatibility alias for brief daily")
    brief_daily_compat_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    brief_daily_compat_parser.add_argument("--skip-update", action="store_true", help="Skip A-share history update")
    brief_daily_compat_parser.add_argument("--check-only", action="store_true", help="Only check A-share history freshness; do not export")
    brief_daily_compat_parser.add_argument("--refresh-cache", action="store_true", help="Rebuild cached market panel before exporting")
    brief_daily_compat_parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")
    brief_watchlist_parser = brief_sub.add_parser("watchlist", help="Generate the phase0 watchlist trial brief")
    brief_watchlist_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    brief_watchlist_parser.add_argument("--skip-update", action="store_true", help="Skip A-share history update")
    brief_watchlist_parser.add_argument("--check-only", action="store_true", help="Only check A-share history freshness; do not export")
    brief_watchlist_parser.add_argument("--refresh-cache", action="store_true", help="Rebuild cached market panel before exporting")
    brief_watchlist_parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")
    brief_premarket_parser = brief_sub.add_parser("premarket", help="Export the raw 07:30 premarket watchlist without updating history")
    brief_premarket_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    brief_premarket_parser.add_argument("--refresh-cache", action="store_true", help="Rebuild cached market panel before exporting")
    brief_premarket_parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")
    brief_account_bill_parser = brief_sub.add_parser("account-bill", help="Export simulated account bill HTML from SQLite")
    brief_account_bill_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    brief_account_bill_parser.add_argument("--date", default=None, help="Brief/account date in YYYY-MM-DD. Defaults to latest account date.")
    premarket_parser = sub.add_parser("premarket", help="Export phase0 07:30 premarket watchlist")
    premarket_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    premarket_parser.add_argument("--refresh-cache", action="store_true", help="Rebuild cached market panel before exporting")
    premarket_parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")
    daily_brief_parser = sub.add_parser("daily-brief", help="Run the daily delivery pipeline")
    daily_brief_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    daily_brief_parser.add_argument(
        "--watchlist",
        action="store_true",
        help="Export the phase0 watchlist trial brief; the full daily brief is reserved for later product stages",
    )
    daily_brief_parser.add_argument("--skip-update", action="store_true", help="Skip A-share history update and only export the watchlist")
    daily_brief_parser.add_argument("--check-only", action="store_true", help="Only check A-share history freshness; do not export the watchlist")
    daily_brief_parser.add_argument("--refresh-cache", action="store_true", help="Rebuild cached market panel before exporting")
    daily_brief_parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")
    execution_gate_parser = sub.add_parser("execution-gate", help="Run phase0 account execution effectiveness gate")
    execution_gate_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    execution_gate_parser.add_argument("--strategy-id", default=None, help="Registered strategy ID; defaults to strategy_reports.default_strategy_id")
    execution_gate_parser.add_argument("--profile", choices=["research", "live"], default=None, help="Execution parameter profile: research or live")
    execution_gate_parser.add_argument("--output-dir", default=None, help="Optional standalone output directory for live execution backtest artifacts")
    execution_gate_parser.add_argument("--slippage", type=float, default=None, help="Override profile slippage for this run")
    execution_gate_parser.add_argument("--commission", type=float, default=None, help="Override profile commission for this run")
    execution_gate_parser.add_argument("--stamp-duty-sell", type=float, default=None, help="Override profile sell stamp duty for this run")
    execution_gate_parser.add_argument("--price-mode", choices=["close", "next_open", "conservative"], default=None, help="Override profile execution price mode")
    execution_gate_parser.add_argument("--lot-size", type=int, default=None, help="Override profile lot size")
    execution_gate_parser.add_argument("--max-participation-rate", type=float, default=None, help="Override profile max market-volume participation rate")
    execution_gate_parser.add_argument("--enable-limit-check", action=argparse.BooleanOptionalAction, default=None, help="Override profile limit-up/down check")
    execution_gate_parser.add_argument("--enable-suspension-check", action=argparse.BooleanOptionalAction, default=None, help="Override profile suspension check")
    execution_gate_parser.add_argument("--refresh-cache", action="store_true", help="Rebuild cached market panel before exporting")
    execution_gate_parser.add_argument("--no-panel-cache", action="store_true", help="Disable market panel cache for this export")
    universe_parser = sub.add_parser("build-universe", help="Build local-factor A-share universe")
    universe_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    history_parser = sub.add_parser("import-history", help="Import manual A-share history zip files")
    history_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    index_history_parser = sub.add_parser("import-index-history", help="Rebuild manual A-share index history tables only")
    index_history_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    update_history_parser = sub.add_parser("update-history", help="Incrementally update manual A-share history database")
    update_history_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    update_history_parser.add_argument("--check-only", action="store_true", help="Only check freshness, do not fetch or write")
    update_history_parser.add_argument(
        "--no-build-universe",
        action="store_true",
        help="Do not rebuild local factor universe after a successful update",
    )
    daily_basic_backfill_parser = sub.add_parser("backfill-daily-basic", help="Backfill historical A-share daily_basic valuation rows")
    daily_basic_backfill_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    daily_basic_backfill_parser.add_argument("--start-date", required=True, help="Start date in YYYY-MM-DD")
    daily_basic_backfill_parser.add_argument("--end-date", required=True, help="End date in YYYY-MM-DD")
    daily_basic_backfill_parser.add_argument("--limit-dates", type=int, default=None, help="Optional cap for number of open dates to fetch")
    adjustment_backfill_parser = sub.add_parser("backfill-adjustment-factors", help="Backfill A-share Tushare adj_factor and dividend tables")
    adjustment_backfill_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    adjustment_backfill_parser.add_argument("--start-date", required=True, help="Start date in YYYY-MM-DD")
    adjustment_backfill_parser.add_argument("--end-date", required=True, help="End date in YYYY-MM-DD")
    adjustment_backfill_parser.add_argument("--limit-dates", type=int, default=None, help="Optional cap for number of open dates to fetch")
    adjustment_backfill_parser.add_argument("--no-skip-existing", action="store_true", help="Refetch dates already present in market_adj_factors")
    adjustment_backfill_parser.add_argument("--no-dividends", action="store_true", help="Only fetch adj_factor; skip dividend table")
    adjustment_backfill_parser.add_argument(
        "--max-requests-per-minute",
        type=int,
        default=180,
        help="Client-side Tushare request throttle. Default 180 is below the 2000-point 200/minute tier.",
    )
    index_asof_backfill_parser = sub.add_parser("backfill-index-asof", help="Backfill benchmark index constituent and weight as-of tables")
    index_asof_backfill_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    index_asof_backfill_parser.add_argument("--index-code", default=None, help="Project index code, defaults to benchmark_symbol")
    index_asof_backfill_parser.add_argument("--start-date", default="2016-01-01", help="Start date in YYYY-MM-DD")
    index_asof_backfill_parser.add_argument("--end-date", required=True, help="End date in YYYY-MM-DD")
    index_asof_backfill_parser.add_argument("--input-csv", default=None, help="Optional CSV with index_code, con_code, trade_date, weight")
    index_asof_backfill_parser.add_argument(
        "--max-requests-per-minute",
        type=int,
        default=180,
        help="Client-side Tushare request throttle. Default 180 is below the 2000-point 200/minute tier.",
    )
    index_asof_backfill_parser.add_argument("--weights-table", default="cn_index_weights_asof", help="Target SQLite weights table")
    index_asof_backfill_parser.add_argument("--constituents-table", default="cn_index_constituents_asof", help="Target SQLite constituents table")
    tushare_backfill_parser = sub.add_parser("backfill-tushare-history", help="Backfill Tushare historical A-share fields and audit coverage")
    tushare_backfill_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    tushare_backfill_parser.add_argument("--start-date", default="2016-01-01", help="Start date in YYYY-MM-DD")
    tushare_backfill_parser.add_argument("--end-date", required=True, help="End date in YYYY-MM-DD")
    tushare_backfill_parser.add_argument("--limit-dates", type=int, default=None, help="Optional cap for daily open dates to fetch")
    tushare_backfill_parser.add_argument("--limit-periods", type=int, default=None, help="Optional cap for financial periods to fetch")
    tushare_backfill_parser.add_argument("--no-skip-existing", action="store_true", help="Refetch dates/periods already present locally")
    tushare_backfill_parser.add_argument("--no-daily-basic", action="store_true", help="Skip Tushare daily_basic backfill")
    tushare_backfill_parser.add_argument("--no-adj-factor", action="store_true", help="Skip Tushare adj_factor backfill")
    tushare_backfill_parser.add_argument("--no-dividends", action="store_true", help="Skip Tushare dividend backfill")
    tushare_backfill_parser.add_argument("--no-financial", action="store_true", help="Skip Tushare financial factor backfill")
    tushare_backfill_parser.add_argument(
        "--max-requests-per-minute",
        type=int,
        default=180,
        help="Client-side Tushare request throttle. Default 180 is below the 2000-point 200/minute tier.",
    )
    tushare_financial_parser = sub.add_parser("backfill-tushare-financials", help="Backfill Tushare financial factors by ts_code with resumable tasks")
    tushare_financial_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    tushare_financial_parser.add_argument("--period", default=None, help="Single financial period in YYYY-MM-DD")
    tushare_financial_parser.add_argument("--start-period", default="2016-03-31", help="Start financial period in YYYY-MM-DD")
    tushare_financial_parser.add_argument("--end-period", default="2018-03-31", help="End financial period in YYYY-MM-DD")
    tushare_financial_parser.add_argument("--limit-symbols", type=int, default=None, help="Optional cap for target symbols per period")
    tushare_financial_parser.add_argument("--limit-tasks", type=int, default=None, help="Optional cap for selected task rows to process")
    tushare_financial_parser.add_argument("--retry-failed", action="store_true", help="Retry failed tasks in addition to pending tasks")
    tushare_financial_parser.add_argument("--replace-existing", action="store_true", help="Replace existing valid financial rows")
    tushare_financial_parser.add_argument(
        "--missing-fields-only",
        action="store_true",
        help="Only patch existing financial rows that have missing fields",
    )
    tushare_financial_parser.add_argument(
        "--missing-fields",
        default="roe,revenue_growth,profit_growth,operating_cash_flow_to_net_profit,debt_to_asset",
        help="Comma-separated financial fields to patch when --missing-fields-only is set",
    )
    tushare_financial_parser.add_argument("--shard-index", type=int, default=0, help="Shard index for distributed runs")
    tushare_financial_parser.add_argument("--shard-count", type=int, default=1, help="Total shard count for distributed runs")
    tushare_financial_parser.add_argument("--max-runtime-minutes", type=int, default=None, help="Stop gracefully after this many minutes")
    tushare_financial_parser.add_argument(
        "--max-requests-per-minute",
        type=int,
        default=120,
        help="Client-side Tushare request throttle. Default 120 is conservative for long financial backfills.",
    )
    us_history_parser = sub.add_parser("update-us-market-history", help="Incrementally update US market history database")
    us_history_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    us_history_parser.add_argument("--check-only", action="store_true", help="Only check freshness, do not fetch or write")
    hk_history_parser = sub.add_parser("update-hk-market-history", help="Incrementally update HK market history database")
    hk_history_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    hk_history_parser.add_argument("--check-only", action="store_true", help="Only check freshness, do not fetch or write")
    financial_parser = sub.add_parser("update-financials", help="Update A-share quarterly financial factors")
    financial_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    financial_parser.add_argument("--periods", type=int, default=None, help="Override number of recent quarters to fetch")
    financial_parser.add_argument(
        "--no-build-universe",
        action="store_true",
        help="Do not rebuild local factor universe after a successful update",
    )

    args = parser.parse_args()
    if args.cmd == "bill":
        config_path = Path(args.config).resolve()
        console = Console()
        console.print("[bold]Phase 0 bill export started[/bold]")
        result = _export_phase0_low_turnover_bill(
            config_path=config_path,
            strategy_id=args.strategy_id,
            refresh_cache=bool(args.refresh_cache),
            no_panel_cache=bool(args.no_panel_cache),
        )
        console.print("[green]Bill export complete[/green]")
        console.print(f"Strategy: {result.get('strategy_id', '')}")
        console.print(f"Bill: {result['bill']}")
        console.print(f"Daily assets: {result['daily']}")
        console.print(f"Preview: {result['preview']}")
        console.print(f"Rows: {result['rows']}")
        return 0
    if args.cmd == "market-regime":
        console = Console()
        console.print("[bold]Phase 0 market-regime report started[/bold]")
        result = _export_phase0_market_regime_report()
        console.print("[green]Market-regime report complete[/green]")
        console.print(f"Summary: {result['summary']}")
        console.print(f"Segments: {result['segments']}")
        console.print(f"HTML: {result['html']}")
        console.print(f"Rows: {result['rows']}")
        return 0
    if args.cmd == "oos-report":
        config_path = Path(args.config).resolve()
        console = Console()
        console.print("[bold]Phase 0 OOS report started[/bold]")
        result = _export_phase0_oos_report(
            config_path=config_path,
            strategy_id=args.strategy_id,
            profile=args.profile,
            output_dir=args.output_dir,
            refresh_cache=bool(args.refresh_cache),
            no_panel_cache=bool(args.no_panel_cache),
            slippage=args.slippage,
            commission=args.commission,
            stamp_duty_sell=args.stamp_duty_sell,
            price_mode=args.price_mode,
            lot_size=args.lot_size,
            max_participation_rate=args.max_participation_rate,
            enable_limit_check=args.enable_limit_check,
            enable_suspension_check=args.enable_suspension_check,
        )
        console.print("[green]OOS report complete[/green]")
        console.print(f"Strategy: {result.get('strategy_id', '')}")
        console.print(f"Profile: {result['profile']}")
        console.print(f"Daily assets: {result['daily_assets']}")
        console.print(f"Report: {result['report']}")
        console.print(f"Curve: {result['curve']}")
        console.print(f"Fold: {result['fold']}")
        return 0
    if args.cmd == "financial-pti":
        config_path = Path(args.config).resolve()
        console = Console()
        console.print("[bold]Phase 0 financial PTI audit started[/bold]")
        result = _export_phase0_financial_pti(config_path)
        console.print("[green]Financial PTI audit complete[/green]")
        console.print(f"Verdict: {result['verdict']}")
        console.print(f"Summary: {result['summary']}")
        console.print(f"Samples: {result['samples']}")
        console.print(f"HTML: {result['html']}")
        return 0
    if args.cmd == "universe-pti":
        config_path = Path(args.config).resolve()
        console = Console()
        console.print("[bold]Phase 0 universe PTI audit started[/bold]")
        result = _export_phase0_universe_pit(config_path, as_of_date=str(args.date))
        console.print("[green]Universe PTI audit complete[/green]")
        console.print(f"Report: {result['report']}")
        console.print(f"Selected count: {result['selected_count']}")
        console.print(f"Boundary violations: {result['boundary_violations']}")
        console.print(f"Historical industry constraint effective: {result['industry_effective']}")
        return 0
    if args.cmd == "adjustment-audit":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        console = Console()
        console.print("[bold]A-share price adjustment audit started[/bold]")
        result = run_adjustment_audit(
            config=cfg.get("phase0", cfg),
            root=config_path.parent,
            output_csv=Path(args.output_csv).resolve() if args.output_csv else None,
            output_md=Path(args.output_md).resolve() if args.output_md else None,
        )
        color = "green" if result.can_build_qfq_asof else "yellow"
        console.print(f"[{color}]Adjustment audit verdict: {result.verdict}[/{color}]")
        console.print(f"Can build qfq_asof: {result.can_build_qfq_asof}")
        console.print(f"CSV: {result.csv_path}")
        console.print(f"Markdown: {result.md_path}")
        for warning in result.warnings[:10]:
            console.print(f"[yellow]Warning:[/yellow] {warning}")
        return 0
    if args.cmd == "overfit-diagnostic":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        console = Console()
        console.print("[bold]Strategy overfit diagnostic started[/bold]")
        result = run_overfit_diagnostic(
            config=cfg.get("phase0", cfg),
            root=config_path.parent,
            candidates_path=Path(args.candidates).resolve() if args.candidates else None,
            folds_path=Path(args.folds).resolve() if args.folds else None,
            output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
        )
        console.print("[green]Overfit diagnostic complete[/green]")
        console.print(f"Selected candidate: {result.selected_candidate}")
        console.print(f"Selected risk level: {result.selected_risk_level}")
        console.print(f"CSV: {result.csv_path}")
        console.print(f"Markdown: {result.md_path}")
        console.print(f"Rows: {result.rows}")
        return 0
    if args.cmd == "strategy-admission":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        phase_cfg = cfg.get("phase0", cfg)
        console = Console()
        console.print("[bold]Strategy admission review started[/bold]")
        for line in describe_walk_forward_presets(phase_cfg.get("walk_forward", {}), args.presets, default_all=True):
            console.print(f"[cyan]{line}[/cyan]")
        result = run_strategy_admission(
            config=phase_cfg,
            root=config_path.parent,
            config_path=config_path,
            presets=args.presets,
            strategy_set=args.strategy_set,
            strategies=args.strategies,
            output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
            trace_callback=(lambda payload: _print_walk_forward_trace(console, payload)) if args.trace_run else None,
        )
        console.print("[green]Strategy admission review complete[/green]")
        console.print(f"Strategies: {result.strategies}")
        console.print(f"Presets: {result.presets}")
        console.print(f"Rows: {result.rows}")
        console.print(f"Window matrix CSV: {result.matrix_csv}")
        console.print(f"Constraint review CSV: {result.constraint_csv}")
        console.print(f"Candidate folds CSV: {result.folds_csv}")
        console.print(f"Overfit CSV: {result.overfit_csv}")
        console.print(f"Markdown: {result.report_md}")
        console.print(f"Governance Markdown: {result.governance_md}")
        return 0
    if args.cmd == "strategy-failure-attribution":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        console = Console()
        console.print("[bold]Strategy failure attribution started[/bold]")
        result = run_strategy_failure_attribution(
            config=cfg.get("phase0", cfg),
            root=config_path.parent,
            admission_dir=Path(args.admission_dir).resolve() if args.admission_dir else None,
            folds_path=Path(args.folds).resolve() if args.folds else None,
            matrix_path=Path(args.matrix).resolve() if args.matrix else None,
            constraint_path=Path(args.constraints).resolve() if args.constraints else None,
            overfit_path=Path(args.overfit).resolve() if args.overfit else None,
            output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
        )
        console.print("[green]Strategy failure attribution complete[/green]")
        console.print(f"Strategies: {result.strategies}")
        console.print(f"Rows: {result.rows}")
        console.print(f"CSV: {result.csv_path}")
        console.print(f"Markdown: {result.md_path}")
        if result.fold_csv_path is not None:
            console.print(f"Fold CSV: {result.fold_csv_path}")
        if result.fold_md_path is not None:
            console.print(f"Fold Markdown: {result.fold_md_path}")
        return 0
    if args.cmd == "strategy-market-context":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        phase_cfg = cfg.get("phase0", cfg)
        configure_local_history(phase_cfg.get("local_history", {}), config_path.parent)
        console = Console()
        console.print("[bold]Strategy market context diagnostic started[/bold]")
        result = run_strategy_market_context(
            config=phase_cfg,
            root=config_path.parent,
            fold_attribution_path=Path(args.fold_attribution).resolve(),
            output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
            benchmark_symbol=args.benchmark_symbol,
            trend_window=args.trend_window,
            vol_window=args.vol_window,
            vol_quantile=args.vol_quantile,
        )
        console.print("[green]Strategy market context diagnostic complete[/green]")
        console.print(f"Benchmark: {result.benchmark_symbol}")
        console.print(f"Rows: {result.rows}")
        console.print(f"CSV: {result.csv_path}")
        console.print(f"Summary CSV: {result.summary_csv_path}")
        console.print(f"Coverage CSV: {result.coverage_csv_path}")
        console.print(f"Markdown: {result.md_path}")
        return 0
    if args.cmd == "strategy-exposure-diagnostic":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        phase_cfg = cfg.get("phase0", cfg)
        console = Console()
        console.print("[bold]Strategy exposure diagnostic started[/bold]")
        result = run_strategy_exposure_diagnostic(
            config=phase_cfg,
            root=config_path.parent,
            config_path=config_path,
            candidate_folds_path=Path(args.candidate_folds).resolve(),
            market_context_path=Path(args.market_context).resolve(),
            universe_path=Path(args.universe).resolve() if args.universe else None,
            output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
            command=" ".join(os.sys.argv),
        )
        console.print("[green]Strategy exposure diagnostic complete[/green]")
        console.print(f"Rows: {result.rows}")
        console.print(f"Strong lag rows: {result.strong_lag_rows}")
        console.print(f"CSV: {result.csv_path}")
        console.print(f"Summary CSV: {result.summary_csv_path}")
        console.print(f"Run log: {result.run_log_md_path}")
        console.print(f"Markdown: {result.md_path}")
        return 0
    if args.cmd == "strategy-filter-diagnostic":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        phase_cfg = cfg.get("phase0", cfg)
        console = Console()
        console.print("[bold]Strategy filter diagnostic started[/bold]")
        result = run_strategy_filter_diagnostic(
            config=phase_cfg,
            root=config_path.parent,
            config_path=config_path,
            candidate_folds_path=Path(args.candidate_folds).resolve(),
            strategy_id=args.strategy,
            presets=args.presets,
            folds=args.folds,
            output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
            command=" ".join(os.sys.argv),
        )
        console.print("[green]Strategy filter diagnostic complete[/green]")
        console.print(f"Rows: {result.rows}")
        console.print(f"Folds: {result.folds}")
        console.print(f"Fold summary CSV: {result.fold_summary_csv_path}")
        console.print(f"Daily CSV: {result.daily_csv_path}")
        console.print(f"Funnel CSV: {result.funnel_csv_path}")
        console.print(f"Markdown: {result.md_path}")
        return 0
    if args.cmd == "strategy-core-reachability-diagnostic":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        phase_cfg = cfg.get("phase0", cfg)
        console = Console()
        console.print("[bold]Strategy core reachability diagnostic started[/bold]")
        result = run_strategy_core_reachability_diagnostic(
            config=phase_cfg,
            root=config_path.parent,
            config_path=config_path,
            candidate_folds_path=Path(args.candidate_folds).resolve(),
            output_dir=Path(args.output_dir).resolve(),
            benchmark_symbol=args.benchmark_symbol,
            presets=args.presets,
            folds=args.folds,
            core_top_n=args.core_top_n,
            core_cumulative_weight=args.core_cumulative_weight,
            top_n=args.top_n,
            min_amount=args.min_amount,
            min_amount_ratio20=args.min_amount_ratio20,
            weight_date_lag_days=args.weight_date_lag_days,
            seed_benchmark_core=args.seed_benchmark_core,
            seed_top_n=args.seed_top_n,
            seed_core_top_n=args.seed_core_top_n,
            seed_core_cumulative_weight=args.seed_core_cumulative_weight,
            command=" ".join(os.sys.argv),
        )
        console.print("[green]Strategy core reachability diagnostic complete[/green]")
        console.print(f"Status: {result.status}")
        console.print(f"Daily rows: {result.daily_rows}")
        console.print(f"Fold rows: {result.fold_rows}")
        console.print(f"Daily CSV: {result.daily_csv_path}")
        console.print(f"Fold summary CSV: {result.fold_summary_csv_path}")
        console.print(f"Failure reasons CSV: {result.failure_reason_csv_path}")
        console.print(f"Markdown: {result.report_md_path}")
        console.print(f"Run log: {result.run_log_md_path}")
        return 0
    if args.cmd == "strategy-missing-core-audit":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        phase_cfg = cfg.get("phase0", cfg)
        console = Console()
        console.print("[bold]Strategy missing-core audit started[/bold]")
        result = run_missing_core_audit(
            config=phase_cfg,
            root=config_path.parent,
            config_path=config_path,
            missing_reasons_path=Path(args.missing_reasons).resolve(),
            candidate_folds_path=Path(args.candidate_folds).resolve(),
            output_dir=Path(args.output_dir).resolve(),
            top_symbols=args.top_symbols,
            command=" ".join(os.sys.argv),
        )
        console.print("[green]Strategy missing-core audit complete[/green]")
        console.print(f"Symbol rows: {result.symbol_rows}")
        console.print(f"Event rows: {result.event_rows}")
        console.print(f"Symbol CSV: {result.symbol_csv_path}")
        console.print(f"Event CSV: {result.event_csv_path}")
        console.print(f"Markdown: {result.report_md_path}")
        console.print(f"Run log: {result.run_log_md_path}")
        return 0
    if args.cmd == "strategy-holdings-exposure":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        phase_cfg = cfg.get("phase0", cfg)
        console = Console()
        console.print("[bold]Strategy holdings exposure diagnostic started[/bold]")
        result = run_strategy_holdings_exposure(
            config=phase_cfg,
            root=config_path.parent,
            config_path=config_path,
            candidate_folds_path=Path(args.candidate_folds).resolve(),
            market_context_path=Path(args.market_context).resolve(),
            strategy_id=args.strategy,
            presets=args.presets,
            folds=args.folds,
            benchmark_symbol=args.benchmark_symbol,
            output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
            command=" ".join(os.sys.argv),
        )
        console.print("[green]Strategy holdings exposure diagnostic complete[/green]")
        console.print(f"Holdings rows: {result.holdings_rows}")
        console.print(f"Daily rows: {result.daily_rows}")
        console.print(f"Summary rows: {result.summary_rows}")
        console.print(f"Holdings CSV: {result.holdings_csv_path}")
        console.print(f"Daily exposure CSV: {result.daily_exposure_csv_path}")
        console.print(f"Industry exposure CSV: {result.industry_exposure_csv_path}")
        console.print(f"Summary CSV: {result.summary_csv_path}")
        console.print(f"Coverage CSV: {result.coverage_csv_path}")
        console.print(f"Run log: {result.run_log_md_path}")
        console.print(f"Markdown: {result.md_path}")
        return 0
    if args.cmd == "strategy-fold-attribution":
        console = Console()
        console.print("[bold]Strategy fold attribution assembly started[/bold]")
        result = run_strategy_fold_attribution(
            quality_fold_attribution_path=Path(args.quality_fold_attribution).resolve(),
            price_volume_fold_attribution_path=Path(args.price_volume_fold_attribution).resolve(),
            quality_market_context_path=Path(args.quality_market_context).resolve(),
            price_volume_market_context_path=Path(args.price_volume_market_context).resolve(),
            quality_holdings_path=Path(args.quality_holdings).resolve(),
            price_volume_holdings_path=Path(args.price_volume_holdings).resolve(),
            quality_daily_exposure_path=Path(args.quality_daily_exposure).resolve(),
            price_volume_daily_exposure_path=Path(args.price_volume_daily_exposure).resolve(),
            output_dir=Path(args.output_dir).resolve(),
        )
        console.print("[green]Strategy fold attribution assembly complete[/green]")
        console.print(f"Paired rows: {result.paired_rows}")
        console.print(f"Paired fold CSV: {result.paired_fold_csv_path}")
        console.print(f"Daily exposure CSV: {result.daily_exposure_csv_path}")
        console.print(f"Top holdings CSV: {result.top_holding_csv_path}")
        console.print(f"Quality bucket CSV: {result.quality_bucket_csv_path}")
        console.print(f"Turnover cost CSV: {result.turnover_cost_csv_path}")
        console.print(f"Markdown: {result.md_path}")
        return 0
    if args.cmd == "index-asof-audit":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        phase_cfg = cfg.get("phase0", cfg)
        console = Console()
        console.print("[bold]Index as-of data audit started[/bold]")
        result = run_index_asof_audit(
            config=phase_cfg,
            root=config_path.parent,
            config_path=config_path,
            benchmark_symbol=args.benchmark_symbol,
            candidate_folds_path=Path(args.candidate_folds).resolve() if args.candidate_folds else None,
            output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
            command=" ".join(os.sys.argv),
        )
        console.print("[green]Index as-of data audit complete[/green]")
        console.print(f"Benchmark: {result.benchmark_symbol}")
        console.print(f"Database: {result.db_path}")
        console.print(f"Constituents: {result.constituent_status}")
        console.print(f"Weights: {result.weight_status}")
        console.print(f"Fold rows: {result.fold_rows}")
        console.print(f"Capability CSV: {result.capability_csv_path}")
        console.print(f"Fold coverage CSV: {result.fold_coverage_csv_path}")
        console.print(f"Markdown: {result.report_md_path}")
        console.print(f"Run log: {result.run_log_md_path}")
        return 0
    if args.cmd == "strategy-participation-overlay":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        phase_cfg = cfg.get("phase0", cfg)
        console = Console()
        console.print("[bold]Strategy participation overlay counterfactual started[/bold]")
        result = run_strategy_participation_overlay(
            config=phase_cfg,
            root=config_path.parent,
            config_path=config_path,
            holdings_path=Path(args.holdings).resolve(),
            daily_exposure_path=Path(args.daily_exposure).resolve(),
            output_dir=Path(args.output_dir).resolve(),
            min_exposure=args.min_exposure,
            max_symbol_weight=args.max_symbol_weight,
            max_scale=args.max_scale,
            context_label=args.context_label,
            command=" ".join(os.sys.argv),
        )
        console.print("[green]Strategy participation overlay counterfactual complete[/green]")
        console.print(f"Daily rows: {result.daily_rows}")
        console.print(f"Summary rows: {result.summary_rows}")
        console.print(f"Daily CSV: {result.daily_csv_path}")
        console.print(f"Summary CSV: {result.summary_csv_path}")
        console.print(f"Markdown: {result.report_md_path}")
        console.print(f"Run log: {result.run_log_md_path}")
        return 0
    if args.cmd == "strategy-csi300-attribution":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        phase_cfg = cfg.get("phase0", cfg)
        console = Console()
        console.print("[bold]Strategy CSI300 attribution started[/bold]")
        result = run_strategy_csi300_attribution(
            config=phase_cfg,
            root=config_path.parent,
            holdings_path=Path(args.holdings).resolve() if args.holdings else None,
            daily_exposure_path=Path(args.daily_exposure).resolve() if args.daily_exposure else None,
            candidate_folds_path=Path(args.candidate_folds).resolve() if args.candidate_folds else None,
            market_context_path=Path(args.market_context).resolve() if args.market_context else None,
            output_dir=Path(args.output_dir).resolve(),
            benchmark_symbol=args.benchmark_symbol,
            context_label=args.context_label,
            top_n=args.top_n,
            weight_date_lag_days=args.weight_date_lag_days,
            command=" ".join(os.sys.argv),
        )
        console.print("[green]Strategy CSI300 attribution complete[/green]")
        console.print(f"Status: {result.status}")
        console.print(f"Daily rows: {result.daily_rows}")
        console.print(f"Fold rows: {result.fold_rows}")
        console.print(f"Daily CSV: {result.daily_csv_path}")
        console.print(f"Fold CSV: {result.fold_csv_path}")
        console.print(f"Missed top weights CSV: {result.missed_top_csv_path}")
        console.print(f"Industry CSV: {result.industry_csv_path}")
        console.print(f"Markdown: {result.report_md_path}")
        console.print(f"Run log: {result.run_log_md_path}")
        return 0
    if args.cmd == "strategy-role-card":
        console = Console()
        console.print("[bold]Strategy role card generation started[/bold]")
        result = run_strategy_role_card(
            strategy_id=args.strategy,
            matrix_path=Path(args.matrix).resolve(),
            constraints_path=Path(args.constraints).resolve(),
            fold_attribution_path=Path(args.fold_attribution).resolve() if args.fold_attribution else None,
            market_context_path=Path(args.market_context).resolve() if args.market_context else None,
            holdings_summary_path=Path(args.holdings_summary).resolve() if args.holdings_summary else None,
            overlay_summary_path=Path(args.overlay_summary).resolve() if args.overlay_summary else None,
            output_dir=Path(args.output_dir).resolve(),
        )
        console.print("[green]Strategy role card generation complete[/green]")
        console.print(f"Strategy: {result.strategy_id}")
        console.print(f"Admission action: {result.admission_action}")
        console.print(f"Rows: {result.rows}")
        console.print(f"Rule CSV: {result.rule_csv_path}")
        console.print(f"Markdown: {result.report_md_path}")
        return 0
    if args.cmd == "factor-effectiveness":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        console = Console()
        gate_exit = _run_db_health_gate(
            console=console,
            config=cfg.get("phase0", cfg),
            root=config_path.parent,
            scope="cn",
            fail_on="error",
            label="Factor effectiveness",
        )
        if gate_exit != 0:
            return gate_exit
        console.print("[bold]Factor effectiveness diagnostic started[/bold]")
        result = run_factor_effectiveness_report(
            config=cfg.get("phase0", cfg),
            root=config_path.parent,
            output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
        )
        console.print("[green]Factor effectiveness diagnostic complete[/green]")
        console.print(f"Factors: {result.factor_count}")
        console.print(f"Valid folds: {result.fold_count}")
        console.print(f"Summary CSV: {result.summary_csv}")
        console.print(f"Markdown: {result.summary_md}")
        console.print(f"Group returns: {result.group_returns_csv}")
        console.print(f"Yearly IC: {result.ic_by_year_csv}")
        console.print(f"Correlation: {result.correlation_csv}")
        for warning in result.warnings[:10]:
            console.print(f"[yellow]Warning:[/yellow] {warning}")
        return 0
    if args.cmd == "db-health":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        console = Console()
        console.print("[bold]Database health check started[/bold]")
        result = run_database_health_check(
            config=cfg.get("phase0", cfg),
            root=config_path.parent,
            scope=str(args.scope),
            as_of_date=str(args.as_of) if args.as_of else None,
            output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
        )
        color = "green" if result.status == "pass" else ("yellow" if result.status == "warning" else "red")
        console.print(f"[{color}]Database health status: {result.status}[/{color}]")
        console.print(f"Summary rows: {result.summary_rows}")
        console.print(
            f"Findings: errors={result.error_count}, warnings={result.warning_count}, info={result.info_count}"
        )
        console.print(f"Summary CSV: {result.summary_csv}")
        console.print(f"Findings CSV: {result.findings_csv}")
        console.print(f"Markdown: {result.summary_md}")
        if args.fail_on == "error" and result.error_count > 0:
            return 2
        if args.fail_on == "warning" and (result.error_count > 0 or result.warning_count > 0):
            return 2
        return 0
    if args.cmd == "dashboard":
        console = Console()
        if args.dashboard_cmd == "scan":
            config_path = Path(args.config).resolve()
            root = config_path.parent
            manifest_path = Path(args.manifest).resolve() if args.manifest else None
            console.print("[bold]Report dashboard scan started[/bold]")
            manifest = write_report_manifest(root=root, manifest_path=manifest_path)
            artifacts = scan_report_artifacts(root)
            run_count = len({artifact.run_id for artifact in artifacts})
            type_counts = Counter(artifact.type for artifact in artifacts)
            category_counts = Counter(artifact.legacy_category for artifact in artifacts)
            console.print("[green]Report dashboard scan complete[/green]")
            console.print(f"Manifest: {manifest}")
            console.print(f"Runs: {run_count}")
            console.print(f"Artifacts: {len(artifacts)}")
            console.print(f"Artifact types: {_format_counts(dict(type_counts))}")
            console.print(f"Categories: {_format_counts(dict(category_counts))}")
            return 0
        parser.error("dashboard requires a subcommand: scan")
    if args.cmd == "intelligence":
        console = Console()
        if args.intelligence_cmd == "collect":
            config_path = Path(args.config).resolve()
            console.print("[bold]Strategy intelligence collect started[/bold]")
            result = collect_intelligence(
                config_path,
                output_csv=args.output_csv,
                output_report=args.output_report,
                limit=args.limit,
            )
            color = "green" if result.status == "ok" else "yellow"
            console.print(f"[{color}]Intelligence collect status: {result.status}[/{color}]")
            console.print(f"Candidate rows: {result.rows}")
            console.print(f"Candidate CSV: {result.candidates_csv}")
            console.print(f"Markdown: {result.report_md}")
            for warning in (result.warnings or [])[:10]:
                console.print(f"[yellow]Warning:[/yellow] {warning}")
            return 0
        if args.intelligence_cmd == "import-local":
            config_path = Path(args.config).resolve()
            console.print("[bold]Strategy intelligence local import started[/bold]")
            result = import_local_intelligence(
                config_path,
                source_dir=args.source_dir,
                output_csv=args.output_csv,
                output_report=args.output_report,
                limit=args.limit,
            )
            color = "green" if result.status == "ok" else "yellow"
            console.print(f"[{color}]Intelligence import status: {result.status}[/{color}]")
            console.print(f"Candidate rows: {result.rows}")
            console.print(f"Candidate CSV: {result.candidates_csv}")
            console.print(f"Markdown: {result.report_md}")
            for warning in (result.warnings or [])[:10]:
                console.print(f"[yellow]Warning:[/yellow] {warning}")
            return 0
        if args.intelligence_cmd == "review-candidates":
            config_path = Path(args.config).resolve()
            console.print("[bold]Strategy intelligence candidate review started[/bold]")
            result = review_intelligence_candidates(
                config_path,
                candidates_csv=args.candidates_csv,
                output_csv=args.output_csv,
                output_report=args.output_report,
                limit=args.limit,
                excerpt_chars=args.excerpt_chars,
            )
            color = "green" if result.status == "ok" else "yellow"
            console.print(f"[{color}]Intelligence review status: {result.status}[/{color}]")
            console.print(f"Rows: {result.row_count}")
            console.print(f"Review CSV: {result.review_csv}")
            console.print(f"Markdown: {result.report_md}")
            for warning in result.warnings[:10]:
                console.print(f"[yellow]Warning:[/yellow] {warning}")
            return 0
        if args.intelligence_cmd == "validate":
            config_path = Path(args.config).resolve()
            console.print("[bold]Strategy intelligence ledger validation started[/bold]")
            result = validate_intelligence_ledger(
                config_path,
                ledger=args.ledger,
                output_report=args.output_report,
            )
            color = "green" if result.status == "ok" else "red"
            console.print(f"[{color}]Intelligence validation status: {result.status}[/{color}]")
            console.print(f"Rows: {result.row_count}")
            console.print(f"Errors: {result.error_count}")
            console.print(f"Warnings: {result.warning_count}")
            console.print(f"Markdown: {result.report_md}")
            for error in result.errors[:10]:
                console.print(f"[red]Error:[/red] {error}")
            for warning in result.warnings[:10]:
                console.print(f"[yellow]Warning:[/yellow] {warning}")
            return 2 if result.error_count > 0 else 0
        parser.error("intelligence requires a subcommand: collect, import-local, review-candidates, or validate")
    if args.cmd == "maintain":
        console = Console()
        if args.maintain_cmd == "tick":
            config_path = Path(args.config).resolve()
            console.print("[bold]Maintenance tick started[/bold]")
            result = maintenance_tick(
                config_path,
                as_of=args.as_of,
                dry_run=bool(args.dry_run),
            )
            console.print("[green]Maintenance tick complete[/green]")
            console.print(f"State DB: {result.state_db}")
            console.print(f"As of: {result.as_of}")
            console.print(f"Dry run: {result.dry_run}")
            console.print(f"Executed runs: {result.executed_runs}")
            for item in result.decisions:
                color = "green" if item.decision == "will_run" else ("yellow" if item.decision == "skipped" else "red")
                console.print(
                    f"[{color}]{item.task_name}[/{color}] "
                    f"{item.decision} at {item.scheduled_time} | {item.reason}"
                )
            return 0
        if args.maintain_cmd == "status":
            config_path = Path(args.config).resolve()
            console.print("[bold]Maintenance status started[/bold]")
            result = maintenance_status(
                config_path,
                output_md=Path(args.output_md).resolve() if args.output_md else None,
                write_report=bool(args.write_report),
            )
            console.print("[green]Maintenance status complete[/green]")
            console.print(f"State DB: {result.state_db}")
            console.print(f"Generated at: {result.generated_at}")
            if result.report_path:
                console.print(f"Report: {result.report_path}")
            for row in result.rows:
                console.print(
                    f"{row.task_name}: enabled={row.enabled}, schedule={row.schedule_value}, "
                    f"last_decision={row.last_decision}, last_reason={row.last_reason}, "
                    f"last_run={row.last_run_status}, log={row.log_path}"
                )
            if result.shards:
                console.print("[bold]Maintenance shards[/bold]")
                for shard in result.shards[:20]:
                    console.print(
                        f"run={shard.run_id} task={shard.task_name} shard={shard.shard_index}/{shard.shard_count} "
                        f"status={shard.status} pid={shard.pid} log={shard.log_path}"
                    )
                    if shard.report_path or shard.error_summary or shard.key_conclusion:
                        console.print(
                            f"  report={shard.report_path or 'N/A'} error={shard.error_summary or 'N/A'} "
                            f"conclusion={shard.key_conclusion or 'N/A'}"
                        )
            return 0
        if args.maintain_cmd == "supervise":
            config_path = Path(args.config).resolve()
            result = maintenance_supervise(
                config_path,
                task_name=args.task,
                run_id=args.run_id,
                dry_run=bool(args.dry_run),
            )
            console.print(f"Maintenance supervise status: {result.status}")
            console.print(f"State DB: {result.state_db}")
            if result.message:
                console.print(f"Message: {result.message}")
            for shard in result.shard_rows[:20]:
                console.print(
                    f"run={shard.run_id} shard={shard.shard_index}/{shard.shard_count} "
                    f"status={shard.status} pid={shard.pid} log={shard.log_path}"
                )
                if shard.report_path or shard.error_summary or shard.key_conclusion:
                    console.print(
                        f"  report={shard.report_path or 'N/A'} error={shard.error_summary or 'N/A'} "
                        f"conclusion={shard.key_conclusion or 'N/A'}"
                    )
            return 0
        if args.maintain_cmd == "run":
            config_path = Path(args.config).resolve()
            result = maintenance_run_long_task(
                config_path,
                task_name=args.task,
                start_period=args.start_period,
                end_period=args.end_period,
                shard_count=args.shard_count,
                max_requests_per_minute=args.max_requests_per_minute,
                retry_failed=bool(args.retry_failed),
                missing_fields_only=bool(args.missing_fields_only),
                limit_tasks=args.limit_tasks,
                dry_run=bool(args.dry_run),
            )
            console.print(f"Maintenance run status: {result.status}")
            console.print(f"State DB: {result.state_db}")
            console.print(f"Run ID: {result.run_id}")
            if result.message:
                console.print(f"Message: {result.message}")
            for shard in result.shard_rows:
                console.print(
                    f"shard={shard.shard_index}/{shard.shard_count} status={shard.status} "
                    f"pid={shard.pid} log={shard.log_path}"
                )
            return 0 if result.status not in {"blocked"} else 2
        if args.maintain_cmd == "stop":
            config_path = Path(args.config).resolve()
            result = maintenance_stop(
                config_path,
                task_name=args.task,
                run_id=args.run_id,
                dry_run=bool(args.dry_run),
            )
            console.print(f"Maintenance stop status: {result.status}")
            console.print(f"State DB: {result.state_db}")
            if result.message:
                console.print(f"Message: {result.message}")
            for shard in result.shard_rows[:20]:
                console.print(
                    f"run={shard.run_id} shard={shard.shard_index}/{shard.shard_count} "
                    f"status={shard.status} pid={shard.pid} log={shard.log_path}"
                )
            return 0
        if args.maintain_cmd == "resume":
            config_path = Path(args.config).resolve()
            result = maintenance_resume(
                config_path,
                task_name=args.task,
                run_id=args.run_id,
                dry_run=bool(args.dry_run),
            )
            console.print(f"Maintenance resume status: {result.status}")
            console.print(f"State DB: {result.state_db}")
            if result.message:
                console.print(f"Message: {result.message}")
            for shard in result.shard_rows[:20]:
                console.print(
                    f"run={shard.run_id} shard={shard.shard_index}/{shard.shard_count} "
                    f"status={shard.status} pid={shard.pid} log={shard.log_path}"
                )
            return 0
        parser.error("maintain requires a subcommand: tick, status, supervise, run, stop, or resume")
    if args.cmd == "system":
        console = Console()
        if args.system_cmd == "status":
            config_path = Path(args.config).resolve()
            console.print("[bold]System status started[/bold]")
            maintenance_result = maintenance_status(config_path, refresh_state=False, read_only=True)
            summary = summarize_system_maintenance_status(maintenance_result)
            console.print("[green]System status complete[/green]")
            console.print(f"Maintenance state DB: {maintenance_result.state_db}")
            console.print(f"Maintenance generated at: {maintenance_result.generated_at}")
            console.print(f"Maintenance tasks: {summary['task_count']}")
            console.print(f"Maintenance last_run_status: {_format_counts(summary['last_run_status_counts'])}")
            console.print(f"Maintenance last_decision: {_format_counts(summary['last_decision_counts'])}")
            console.print(f"Maintenance running shards: {summary['running_shard_count']}")
            console.print(f"Maintenance shard_status: {_format_counts(summary['shard_status_counts'])}")
            return 0
        parser.error("system requires a subcommand: status")
    if args.cmd == "brief":
        if args.brief_cmd in {"daily", "daily-brief", "watchlist"}:
            return run_daily_brief_pipeline(
                config_path=Path(args.config).resolve(),
                watchlist=True,
                skip_update=bool(args.skip_update),
                check_only=bool(args.check_only),
                refresh_cache=bool(args.refresh_cache),
                no_panel_cache=bool(args.no_panel_cache),
            )
        if args.brief_cmd == "premarket":
            config_path = Path(args.config).resolve()
            console = Console()
            console.print("[bold]Phase 0 premarket watchlist started[/bold]")
            result = _export_phase0_premarket(
                config_path=config_path,
                refresh_cache=bool(args.refresh_cache),
                no_panel_cache=bool(args.no_panel_cache),
            )
            console.print("[green]Premarket watchlist complete[/green]")
            console.print(f"Watchlist: {result['watchlist']}")
            console.print(f"Report: {result['report']}")
            console.print(f"Rows: {result['rows']}")
            console.print(f"Signal date: {result['signal_date']}")
            console.print(f"Check time: {result['check_time']}")
            return 0
        if args.brief_cmd == "account-bill":
            console = Console()
            result = _export_brief_account_bill(
                config_path=Path(args.config).resolve(),
                brief_date=args.date,
            )
            console.print("[green]Account bill export complete[/green]")
            console.print(f"Account: {result['account']}")
            console.print(f"Date: {result['brief_date']}")
            console.print(f"Account bill: {result['account_bill']}")
            return 0
        parser.error("brief requires a subcommand: daily, watchlist, premarket, or account-bill")
    if args.cmd == "premarket":
        config_path = Path(args.config).resolve()
        console = Console()
        console.print("[bold]Phase 0 premarket watchlist started[/bold]")
        result = _export_phase0_premarket(
            config_path=config_path,
            refresh_cache=bool(args.refresh_cache),
            no_panel_cache=bool(args.no_panel_cache),
        )
        console.print("[green]Premarket watchlist complete[/green]")
        console.print(f"Watchlist: {result['watchlist']}")
        console.print(f"Report: {result['report']}")
        console.print(f"Rows: {result['rows']}")
        console.print(f"Signal date: {result['signal_date']}")
        console.print(f"Check time: {result['check_time']}")
        return 0
    if args.cmd == "daily-brief":
        return run_daily_brief_pipeline(
            config_path=Path(args.config).resolve(),
            watchlist=bool(args.watchlist),
            skip_update=bool(args.skip_update),
            check_only=bool(args.check_only),
            refresh_cache=bool(args.refresh_cache),
            no_panel_cache=bool(args.no_panel_cache),
        )
    if args.cmd == "execution-gate":
        config_path = Path(args.config).resolve()
        console = Console()
        console.print("[bold]Phase 0 account execution gate started[/bold]")
        result = _export_phase0_execution_gate(
            config_path=config_path,
            strategy_id=args.strategy_id,
            profile=args.profile,
            output_dir=args.output_dir,
            refresh_cache=bool(args.refresh_cache),
            no_panel_cache=bool(args.no_panel_cache),
            slippage=args.slippage,
            commission=args.commission,
            stamp_duty_sell=args.stamp_duty_sell,
            price_mode=args.price_mode,
            lot_size=args.lot_size,
            max_participation_rate=args.max_participation_rate,
            enable_limit_check=args.enable_limit_check,
            enable_suspension_check=args.enable_suspension_check,
        )
        console.print("[green]Account execution gate complete[/green]")
        console.print(f"Strategy: {result.get('strategy_id', '')}")
        console.print(f"Verdict: {result['verdict']}")
        console.print(f"Folds: {result['folds']}")
        console.print(f"Report: {result['report']}")
        return 0
    if args.cmd == "update-financials":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        result = update_financial_factors_from_config(cfg, config_path.parent, periods=args.periods)
        console = Console()
        color = "green" if result.ok else "red"
        console.print(f"[{color}]Financial factor update status: {result.status}[/{color}]")
        console.print(f"Database: {result.db_path}")
        console.print(f"Periods requested: {', '.join(result.periods_requested) or 'N/A'}")
        console.print(f"Periods updated: {', '.join(result.periods_updated) or 'N/A'}")
        console.print(f"Fetched rows: {result.fetched_rows}")
        console.print(f"Inserted rows: {result.inserted_rows}")
        if result.factor_coverage:
            console.print(
                "Financial factor coverage: "
                f"latest={result.factor_coverage.get('latest_factor', 0.0):.4f}, "
                f"roe={result.factor_coverage.get('roe', 0.0):.4f}, "
                f"revenue_growth={result.factor_coverage.get('revenue_growth', 0.0):.4f}, "
                f"profit_growth={result.factor_coverage.get('profit_growth', 0.0):.4f}, "
                f"cash_flow_quality={result.factor_coverage.get('cash_flow_quality', 0.0):.4f}, "
                f"debt_to_asset={result.factor_coverage.get('debt_to_asset', 0.0):.4f}"
            )
        if result.warnings:
            for warning in result.warnings:
                console.print(f"[yellow]Warning:[/yellow] {warning}")
        if not result.ok:
            return 2
        if (
            not args.no_build_universe
            and result.inserted_rows > 0
            and bool(cfg.get("financial_factors", {}).get("rebuild_universe_after", True))
        ):
            universe_result = build_local_factor_universe(cfg, config_path.parent)
            console.print("[green]Universe rebuild complete[/green]")
            console.print(f"Source: {universe_result.source}")
            console.print(f"Selected: {universe_result.selected_count}/{universe_result.target_size}")
            if universe_result.warnings:
                for warning in universe_result.warnings:
                    console.print(f"[yellow]Warning:[/yellow] {warning}")
        return 0
    if args.cmd == "cost-sensitivity":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        scenarios = [_parse_cost_scenario(text, cfg) for text in args.scenario]
        if args.use_config_scenarios:
            scenarios = _configured_cost_scenarios(cfg)
        if not scenarios:
            console = Console()
            console.print(
                "[red]No cost sensitivity scenarios specified.[/red] "
                "Use --scenario name:slippage or --use-config-scenarios."
            )
            return 2
        return run_phase0_cost_sensitivity(config_path, scenarios)
    if args.cmd == "update-history":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        result = update_manual_history_from_config(cfg, config_path.parent, check_only=args.check_only)
        console = Console()
        _print_manual_history_update_result(console, result)
        if not result.ok:
            return 2
        if (
            not args.check_only
            and not args.no_build_universe
            and result.status in {"updated", "metadata_updated"}
            and bool(cfg.get("manual_history_update", {}).get("rebuild_universe_after", False))
        ):
            universe_result = build_local_factor_universe(cfg, config_path.parent)
            console.print("[green]Universe rebuild complete[/green]")
            console.print(f"Source: {universe_result.source}")
            console.print(f"Selected: {universe_result.selected_count}/{universe_result.target_size}")
            if universe_result.warnings:
                for warning in universe_result.warnings:
                    console.print(f"[yellow]Warning:[/yellow] {warning}")
        return 0
    if args.cmd == "backfill-daily-basic":
        config_path = Path(args.config).resolve()
        console = Console()
        console.print("[bold]A-share daily_basic backfill started[/bold]")
        result = backfill_daily_basic_from_config(
            config_path,
            start_date=str(args.start_date),
            end_date=str(args.end_date),
            limit_dates=args.limit_dates,
        )
        console.print("[green]A-share daily_basic backfill complete[/green]")
        console.print(f"Database: {result.db_path}")
        console.print(f"Table: {result.table_name}")
        console.print(f"Status: {result.status}")
        console.print(f"Target dates: {result.target_dates}")
        console.print(f"Fetched dates: {result.fetched_dates}")
        console.print(f"Inserted rows: {result.inserted_rows}")
        console.print(f"Skipped existing dates: {result.skipped_existing_dates}")
        if result.warnings:
            console.print("Warnings:")
            for item in result.warnings[:20]:
                console.print(f"- {item}")
        return 0
    if args.cmd == "backfill-adjustment-factors":
        config_path = Path(args.config).resolve()
        console = Console()
        console.print("[bold]A-share adjustment factor backfill started[/bold]")
        result = backfill_adjustment_factors_from_config(
            config_path,
            start_date=str(args.start_date),
            end_date=str(args.end_date),
            limit_dates=args.limit_dates,
            skip_existing=not bool(args.no_skip_existing),
            include_dividends=not bool(args.no_dividends),
            max_requests_per_minute=int(args.max_requests_per_minute),
        )
        color = "green" if result.status in {"ok", "empty"} else "red"
        console.print(f"[{color}]Adjustment factor backfill status: {result.status}[/{color}]")
        console.print(f"Database: {result.db_path}")
        console.print(f"Target dates: {result.target_dates}")
        console.print(f"Fetched dates: {result.fetched_dates}")
        console.print(f"Inserted adj_factor rows: {result.inserted_adj_factor_rows}")
        console.print(f"Inserted dividend rows: {result.inserted_dividend_rows}")
        console.print(f"Skipped existing dates: {result.skipped_existing_dates}")
        if result.warnings:
            console.print("Warnings:")
            for item in result.warnings[:20]:
                console.print(f"- {item}")
        return 0 if result.status != "missing_tushare_token" else 2
    if args.cmd == "backfill-tushare-history":
        config_path = Path(args.config).resolve()
        console = Console()
        console.print("[bold]Tushare historical backfill started[/bold]")
        result = backfill_tushare_history_from_config(
            config_path,
            start_date=str(args.start_date),
            end_date=str(args.end_date),
            max_requests_per_minute=int(args.max_requests_per_minute),
            limit_dates=args.limit_dates,
            limit_periods=args.limit_periods,
            skip_existing=not bool(args.no_skip_existing),
            include_daily_basic=not bool(args.no_daily_basic),
            include_adj_factor=not bool(args.no_adj_factor),
            include_dividends=not bool(args.no_dividends),
            include_financial=not bool(args.no_financial),
        )
        color = "green" if result.status == "ok" else "yellow"
        console.print(f"[{color}]Tushare historical backfill status: {result.status}[/{color}]")
        console.print(f"Database: {result.db_path}")
        console.print(f"Daily basic: fetched {result.daily_basic_fetched_dates}/{result.daily_basic_target_dates}, rows {result.daily_basic_inserted_rows}")
        console.print(f"Adj factor: fetched {result.adj_factor_fetched_dates}/{result.adj_factor_target_dates}, rows {result.adj_factor_inserted_rows}")
        console.print(f"Dividends rows: {result.dividend_inserted_rows}")
        console.print(f"Financial: fetched {result.financial_fetched_periods}/{result.financial_target_periods}, rows {result.financial_inserted_rows}")
        console.print(f"Audit CSV: {result.audit_csv}")
        console.print(f"Audit Markdown: {result.audit_md}")
        if result.warnings:
            console.print("Warnings:")
            for item in result.warnings[:30]:
                console.print(f"- {item}")
        return 0 if result.status != "missing_tushare_token" else 2
    if args.cmd == "backfill-index-asof":
        config_path = Path(args.config).resolve()
        console = Console()
        console.print("[bold]Index as-of backfill started[/bold]")
        result = backfill_index_asof_from_config(
            config_path,
            index_code=str(args.index_code) if args.index_code else None,
            start_date=str(args.start_date),
            end_date=str(args.end_date),
            input_csv=Path(args.input_csv).resolve() if args.input_csv else None,
            max_requests_per_minute=int(args.max_requests_per_minute),
            weights_table=str(args.weights_table),
            constituents_table=str(args.constituents_table),
        )
        color = "green" if result.status == "ok" else "yellow"
        console.print(f"[{color}]Index as-of backfill status: {result.status}[/{color}]")
        console.print(f"Database: {result.db_path}")
        console.print(f"Index: {result.index_code} ({result.vendor_index_code})")
        console.print(f"Source: {result.source}")
        console.print(f"Fetched rows: {result.fetched_rows}")
        console.print(f"Inserted weight rows: {result.inserted_weight_rows}")
        console.print(f"Inserted constituent rows: {result.inserted_constituent_rows}")
        console.print(f"Trade dates: {result.distinct_trade_dates} ({result.min_trade_date or 'N/A'}..{result.max_trade_date or 'N/A'})")
        console.print(f"Audit CSV: {result.audit_csv}")
        console.print(f"Audit Markdown: {result.audit_md}")
        if result.warnings:
            console.print("Warnings:")
            for item in result.warnings[:30]:
                console.print(f"- {item}")
        return 0 if result.status not in {"missing_tushare_token"} else 2
    if args.cmd == "backfill-tushare-financials":
        config_path = Path(args.config).resolve()
        console = Console()
        console.print("[bold]Tushare financial backfill started[/bold]")
        result = backfill_tushare_financials_from_config(
            config_path,
            start_period=str(args.start_period),
            end_period=str(args.end_period),
            period=str(args.period) if args.period else None,
            max_requests_per_minute=int(args.max_requests_per_minute),
            max_runtime_minutes=args.max_runtime_minutes,
            limit_symbols=args.limit_symbols,
            limit_tasks=args.limit_tasks,
            retry_failed=bool(args.retry_failed),
            replace_existing=bool(args.replace_existing),
            missing_fields_only=bool(args.missing_fields_only),
            missing_fields=[item.strip() for item in str(args.missing_fields).split(",") if item.strip()],
            shard_index=int(args.shard_index),
            shard_count=int(args.shard_count),
            progress_callback=lambda progress: _print_tushare_financial_progress(console, progress),
        )
        color = "green" if result.status == "ok" else "yellow"
        console.print(f"[{color}]Tushare financial backfill status: {result.status}[/{color}]")
        console.print(f"Database: {result.db_path}")
        console.print(f"Target tasks: {result.target_tasks}")
        console.print(f"Processed tasks: {result.processed_tasks}")
        console.print(f"Fetched: {result.fetched_tasks}")
        console.print(f"Empty: {result.empty_tasks}")
        console.print(f"Failed: {result.failed_tasks}")
        console.print(f"Inserted rows: {result.inserted_rows}")
        console.print(f"Audit CSV: {result.audit_csv}")
        console.print(f"Audit Markdown: {result.audit_md}")
        if result.warnings:
            console.print("Warnings:")
            for item in result.warnings[:30]:
                console.print(f"- {item}")
        return 0 if result.status != "missing_tushare_token" else 2
    if args.cmd == "update-us-market-history":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        result = update_us_market_history_from_config(cfg, config_path.parent, check_only=args.check_only)
        console = Console()
        color = "green" if result.ok else "red"
        console.print(f"[{color}]US market history update status: {result.status}[/{color}]")
        console.print(f"Database: {result.db_path}")
        console.print(f"Latest date: {result.latest_date or 'N/A'}")
        console.print(f"Coverage: {result.coverage:.4f} ({result.covered_symbols}/{result.symbol_count})")
        console.print(f"Fetched rows: {result.fetched_rows}")
        console.print(f"Inserted rows: {result.inserted_rows}")
        console.print(f"Updated rows: {result.updated_rows}")
        console.print(f"Source: {result.source or 'N/A'}")
        if result.warnings:
            for warning in result.warnings:
                console.print(f"[yellow]Warning:[/yellow] {warning}")
        return 0 if result.ok else 2
    if args.cmd == "update-hk-market-history":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        result = update_hk_market_history_from_config(cfg, config_path.parent, check_only=args.check_only)
        console = Console()
        color = "green" if result.ok else "red"
        console.print(f"[{color}]HK market history update status: {result.status}[/{color}]")
        console.print(f"Database: {result.db_path}")
        console.print(f"Latest date: {result.latest_date or 'N/A'}")
        console.print(f"Coverage: {result.coverage:.4f} ({result.covered_symbols}/{result.symbol_count})")
        console.print(f"Fetched rows: {result.fetched_rows}")
        console.print(f"Inserted rows: {result.inserted_rows}")
        console.print(f"Updated rows: {result.updated_rows}")
        console.print(f"Source: {result.source or 'N/A'}")
        if result.warnings:
            for warning in result.warnings:
                console.print(f"[yellow]Warning:[/yellow] {warning}")
        return 0 if result.ok else 2
    if args.cmd == "import-history":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        result = import_from_config(cfg, config_path.parent)
        console = Console()
        console.print("[green]Manual history import complete[/green]")
        console.print(f"Database: {result.db_path}")
        console.print(f"Start date: {result.start_date}")
        console.print(f"QFQ: {result.qfq_files} files, {result.qfq_rows} rows")
        console.print(f"BFQ: {result.bfq_files} files, {result.bfq_rows} rows")
        console.print(f"Symbols: {result.symbols}")
        console.print(f"Stock meta rows: {result.stock_meta_rows}")
        console.print(f"Trading calendar rows: {result.calendar_rows}")
        console.print(f"Delisted stock rows: {result.delisted_rows}")
        console.print(f"Index meta rows: {result.index_meta_rows}")
        console.print(f"Index daily bars: {result.index_files} files, {result.index_rows} rows")
        return 0
    if args.cmd == "import-index-history":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        result = import_index_history_from_config(cfg, config_path.parent)
        console = Console()
        console.print("[green]Manual index history import complete[/green]")
        console.print(f"Database: {result.db_path}")
        console.print(f"Start date: {result.start_date}")
        console.print(f"Index meta rows: {result.index_meta_rows}")
        console.print(f"Index daily bars: {result.index_files} files, {result.index_rows} rows")
        return 0
    if args.cmd == "build-universe":
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        result = build_local_factor_universe(cfg, config_path.parent)
        console = Console()
        console.print("[green]Universe build complete[/green]")
        console.print(f"Source: {result.source}")
        console.print(f"Selected: {result.selected_count}/{result.target_size}")
        console.print(f"Universe: {result.output_path}")
        console.print(f"Report: {result.report_path}")
        if result.warnings:
            for warning in result.warnings:
                console.print(f"[yellow]Warning:[/yellow] {warning}")
        return 0
    if args.cmd != "run":
        parser.print_help()
        return 1

    config_path = Path(args.config).resolve()
    cfg = load_config(config_path)
    console = Console()
    gate_exit = _run_db_health_gate(
        console=console,
        config=cfg.get("phase0", cfg),
        root=config_path.parent,
        scope="cn",
        fail_on="error",
        label="Phase 0 run",
    )
    if gate_exit != 0:
        return gate_exit
    return run_phase0(config_path)


if __name__ == "__main__":
    raise SystemExit(main())
