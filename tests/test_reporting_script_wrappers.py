from __future__ import annotations

from importlib import import_module
import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    ("script_module_name", "reporting_module_name", "symbols", "script_path", "help_flag"),
    [
        (
            "scripts.export_execution_effectiveness_report",
            "phase0.reporting.execution_effectiveness",
            ["DEFAULT_OUTPUT_DIR", "export_execution_effectiveness_report"],
            "scripts/export_execution_effectiveness_report.py",
            "--strategy-id",
        ),
        (
            "scripts.export_hk_market_history_report",
            "phase0.reporting.hk_market_history",
            ["build_report"],
            "scripts/export_hk_market_history_report.py",
            "--output",
        ),
        (
            "scripts.export_market_regime_report",
            "phase0.reporting.market_regime",
            ["export_market_regime_report"],
            "scripts/export_market_regime_report.py",
            "--summary-output",
        ),
        (
            "scripts.export_premarket_watchlist",
            "phase0.reporting.premarket_watchlist",
            [
                "DEFAULT_REPORT_OUTPUT",
                "export_premarket_watchlist",
                "_resolve_report_output_template",
                "_latest_trade_date",
            ],
            "scripts/export_premarket_watchlist.py",
            "--top-candidates",
        ),
        (
            "scripts.export_strategy_bill",
            "phase0.reporting.strategy_bill",
            [
                "DEFAULT_STRATEGY_ID",
                "DEFAULT_PANEL_CACHE",
                "export_strategy_bill",
                "_execution_settings",
                "_panel_cache_key",
                "_load_or_build_panel",
            ],
            "scripts/export_strategy_bill.py",
            "--strategy-id",
        ),
        (
            "scripts.export_strategy_oos_report",
            "phase0.reporting.strategy_oos",
            ["DEFAULT_PROFILE_OOS_REPORT_OUTPUT", "export_strategy_oos_report"],
            "scripts/export_strategy_oos_report.py",
            "--strategy-id",
        ),
        (
            "scripts.export_strategy_period_compare",
            "phase0.reporting.strategy_period_compare",
            ["DEFAULT_COMPARE_TITLE", "main"],
            "scripts/export_strategy_period_compare.py",
            "--early-curve",
        ),
    ],
)
def test_reporting_script_wrappers_alias_reporting_modules_and_show_help(
    script_module_name: str,
    reporting_module_name: str,
    symbols: list[str],
    script_path: str,
    help_flag: str,
) -> None:
    script_module = import_module(script_module_name)
    reporting_module = import_module(reporting_module_name)

    assert script_module is reporting_module
    for symbol in symbols:
        assert getattr(script_module, symbol) is getattr(reporting_module, symbol)

    result = subprocess.run(
        [sys.executable, script_path, "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert help_flag in result.stdout
