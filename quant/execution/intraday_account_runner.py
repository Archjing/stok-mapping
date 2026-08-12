from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from quant.config import load_config
from quant.execution.accounts import (
    SignalAccountExecutionResult,
    SimulatedAccountConfig,
    load_simulated_accounts,
)
from quant.execution.single_etf_intraday import (
    SingleEtfIntradayPolicy,
    reconcile_single_etf_intraday_post_close_session,
    run_single_etf_intraday_account_execution,
)
from quant.strategies import get_strategy


class IntradayAccountRunError(RuntimeError):
    """Raised when a configured intraday account cannot be replayed safely."""


@dataclass(frozen=True)
class ConfiguredIntradayAccountRun:
    config_path: Path
    account: SimulatedAccountConfig
    policy: SingleEtfIntradayPolicy
    panel: pd.DataFrame
    result: SignalAccountExecutionResult
    as_of_date: str
    state_written: bool
    reconciliation_status: str = "not_requested"
    reconciliation_differences: tuple[str, ...] = ()

    def summary(self) -> dict[str, Any]:
        metrics = self.result.metrics
        trades = self.result.trades
        first_date = str(self.panel["date"].min().date()) if not self.panel.empty else ""
        last_date = str(self.panel["date"].max().date()) if not self.panel.empty else ""
        return {
            "account_id": self.account.account_id,
            "strategy_id": self.account.strategy_id,
            "execution_model": self.account.execution_model,
            "execution_scope": "post_close_5min_replay",
            "as_of_date": self.as_of_date,
            "panel_start_date": first_date,
            "panel_end_date": last_date,
            "panel_sessions": int(len(self.panel)),
            "target_symbol": self.policy.target_symbol,
            "raw_signal_count": int(metrics.get("account_raw_signal_count", 0)),
            "entry_count": int(metrics.get("account_entry_count", 0)),
            "exit_count": int(metrics.get("account_exit_count", 0)),
            "completed_round_trip_count": int(metrics.get("account_completed_round_trip_count", 0)),
            "trade_count": int(len(trades)),
            "unfilled_order_count": int(metrics.get("account_unfilled_order_count", 0)),
            "intraday_data_missing_days": int(metrics.get("account_intraday_data_missing_days", 0)),
            "intraday_data_missing_dates": list(metrics.get("account_intraday_data_missing_dates", [])),
            "state_status": str(metrics.get("account_state_status", "unknown")),
            "execution_complete": bool(metrics.get("account_execution_complete", False)),
            "open_position_shares": float(metrics.get("account_open_position_shares", 0.0)),
            "planned_exit_date": str(metrics.get("account_planned_exit_date", "")),
            "annualized_return": float(metrics.get("account_annualized_return", 0.0)),
            "sharpe": float(metrics.get("account_sharpe", 0.0)),
            "max_drawdown": float(metrics.get("account_max_drawdown", 0.0)),
            "final_assets": float(metrics.get("account_final_assets", 0.0)),
            "trade_reason_counts": dict(metrics.get("account_trade_reason_counts", {})),
            "state_written": self.state_written,
            "reconciliation_status": self.reconciliation_status,
            "reconciliation_differences": list(self.reconciliation_differences),
            "state_database_path": str(self.account.database_path),
            "intraday_database_path": str(self.account.intraday_data_path or ""),
        }


def _select_account(config: dict[str, Any], root: Path, account_id: str) -> SimulatedAccountConfig:
    accounts = load_simulated_accounts(config, root)
    for account in accounts:
        if account.account_id == account_id:
            return account
    available = ", ".join(sorted(account.account_id for account in accounts)) or "none"
    raise IntradayAccountRunError(
        f"simulated account '{account_id}' is not enabled or does not exist; available: {available}"
    )


def _parse_as_of(value: str | None) -> pd.Timestamp:
    try:
        parsed = pd.Timestamp(value).normalize() if value else pd.Timestamp.today().normalize()
    except (TypeError, ValueError) as exc:
        raise IntradayAccountRunError("as_of_date must use YYYY-MM-DD") from exc
    if pd.isna(parsed):
        raise IntradayAccountRunError("as_of_date must use YYYY-MM-DD")
    return parsed


def run_configured_intraday_account(
    *,
    config_path: Path,
    account_id: str,
    as_of_date: str | None = None,
    recover_missing: bool = False,
) -> ConfiguredIntradayAccountRun:
    """Replay one configured single-ETF intraday account.

    The replay is read-only unless ``recover_missing`` is explicitly enabled.
    Recovery writes only missing or incomplete rows for the as-of session; an
    existing result that differs from the replay is reported, never replaced.
    """
    resolved_config = Path(config_path).resolve()
    config = load_config(resolved_config)
    root = resolved_config.parent
    account = _select_account(config, root, account_id)
    if account.execution_model != "single_etf_intraday":
        raise IntradayAccountRunError(
            f"account '{account.account_id}' uses execution_model={account.execution_model!r}, "
            "expected 'single_etf_intraday'"
        )
    if account.intraday_data_path is None:
        raise IntradayAccountRunError(f"account '{account.account_id}' has no intraday_data_path")
    if not account.intraday_data_path.exists():
        raise IntradayAccountRunError(f"intraday database does not exist: {account.intraday_data_path}")

    try:
        strategy = get_strategy(account.strategy_id)
    except KeyError as exc:
        raise IntradayAccountRunError(f"strategy is not registered: {account.strategy_id}") from exc
    if getattr(strategy, "account_execution_model", "daily_target_weight") != "single_etf_intraday":
        raise IntradayAccountRunError(
            f"strategy '{account.strategy_id}' does not declare single_etf_intraday execution"
        )

    as_of = _parse_as_of(as_of_date)
    strategy_cfg = dict(config.get("walk_forward", {}).get("strategy_v2", {}) or {})
    strategy_specific = dict(strategy_cfg.get("cross_market_semiconductor_timing", {}) or {})
    strategy_specific.update(account.strategy_params)
    strategy_specific.update(
        {
            "as_of_date": as_of.date().isoformat(),
            "project_root": str(root),
            "etf_database_path": str(account.intraday_data_path),
        }
    )
    strategy_cfg["cross_market_semiconductor_timing"] = strategy_specific

    us_database_path = root / "data/us_market_history.sqlite"
    if not us_database_path.exists():
        raise IntradayAccountRunError(f"US market database does not exist: {us_database_path}")

    params = strategy.account_execution_params(strategy_cfg)
    policy = SingleEtfIntradayPolicy.from_metadata(strategy.build_metadata(params))
    panel = strategy.prepare_panel(pd.DataFrame(), strategy_cfg)
    if panel.empty:
        raise IntradayAccountRunError("strategy panel is empty; verify ETF daily and SOX/VIX history")
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce").dt.normalize()
    panel = panel[panel["date"] <= as_of].copy()
    if account.simulation_start_date:
        start = pd.Timestamp(account.simulation_start_date).normalize()
        panel = panel[panel["date"] >= start].copy()
    panel = panel.sort_values("date").reset_index(drop=True)
    prepare_session = getattr(strategy, "prepare_intraday_account_session", None)
    if callable(prepare_session) and as_of not in set(panel["date"]):
        current_session = prepare_session(strategy_cfg)
        if current_session is not None and not current_session.empty:
            current_session = current_session.copy()
            current_session["date"] = pd.to_datetime(
                current_session["date"], errors="coerce"
            ).dt.normalize()
            current_session = current_session[current_session["date"] == as_of].copy()
            if account.simulation_start_date:
                current_session = current_session[current_session["date"] >= start].copy()
            if not current_session.empty:
                panel = (
                    pd.concat([panel, current_session], ignore_index=True)
                    .sort_values("date")
                    .drop_duplicates("date", keep="last")
                    .reset_index(drop=True)
                )
    if panel.empty:
        raise IntradayAccountRunError("strategy panel is empty after account date filters")

    result = run_single_etf_intraday_account_execution(
        signal_frame=panel,
        account=account,
        policy=policy,
    )
    execution_complete = bool(result.metrics.get("account_execution_complete", False))
    state_written = False
    reconciliation_status = "not_requested"
    reconciliation_differences: tuple[str, ...] = ()
    if recover_missing:
        if not execution_complete:
            missing = result.metrics.get("account_intraday_data_missing_dates", [])
            raise IntradayAccountRunError(
                "refusing to recover from an incomplete replay; missing intraday dates: "
                + (", ".join(str(value) for value in missing) or "unknown")
            )
        reconciliation = reconcile_single_etf_intraday_post_close_session(
            account=account,
            policy=policy,
            result=result,
            trade_date=as_of.date().isoformat(),
            recover_missing=True,
        )
        reconciliation_status = reconciliation.status
        reconciliation_differences = reconciliation.differences
        state_written = reconciliation.state_written
        if reconciliation.status == "mismatch":
            raise IntradayAccountRunError(
                "post-close replay differs from existing real-time state: "
                + ", ".join(reconciliation.differences)
            )

    return ConfiguredIntradayAccountRun(
        config_path=resolved_config,
        account=account,
        policy=policy,
        panel=panel,
        result=result,
        as_of_date=as_of.date().isoformat(),
        state_written=state_written,
        reconciliation_status=reconciliation_status,
        reconciliation_differences=reconciliation_differences,
    )
