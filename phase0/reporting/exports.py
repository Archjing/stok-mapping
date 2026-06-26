from __future__ import annotations

from pathlib import Path

from phase0.accounts import export_account_bill_html, load_simulated_accounts
from phase0.config import load_config
from phase0.reporting.paths import create_report_run, latest_dir


def _load_report_config_if_available(config_path: Path) -> dict | None:
    if not config_path.exists():
        return None
    return load_config(config_path)


def export_phase0_low_turnover_bill(
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


def export_phase0_market_regime_report(*, root: Path | None = None) -> dict:
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


def export_phase0_oos_report(
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


def export_phase0_financial_pti(config_path: Path) -> dict:
    from scripts.audit_financial_pti import audit_financial_pti

    cfg = _load_report_config_if_available(config_path)
    report_run = create_report_run(root=config_path.resolve().parent, config=cfg, command="financial-pti", scope="qfq_asof")

    return audit_financial_pti(
        config_path=config_path,
        summary_output=report_run.artifact("financial_pti", "summary", "csv"),
        sample_output=report_run.artifact("financial_pti", "problem_samples", "csv"),
        html_output=report_run.artifact("financial_pti", "report", "html"),
    )


def export_phase0_universe_pit(config_path: Path, *, as_of_date: str) -> dict:
    from scripts.audit_universe_pit import audit_universe_pit

    cfg = _load_report_config_if_available(config_path)
    report_run = create_report_run(root=config_path.resolve().parent, config=cfg, command="universe-pti", scope=as_of_date)

    return audit_universe_pit(
        config_path=config_path,
        as_of_date=as_of_date,
        report_output=report_run.artifact("universe_pti", "report", "html"),
    )


def export_phase0_premarket(
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


def export_brief_account_bill(*, config_path: Path, brief_date: str | None = None) -> dict:
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


def export_phase0_execution_gate(
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
