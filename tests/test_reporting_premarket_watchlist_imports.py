from __future__ import annotations

import subprocess
import sys

import scripts.export_premarket_watchlist as legacy_premarket_watchlist
from phase0.reporting import premarket_watchlist
from phase0.reporting.premarket_watchlist import (
    DEFAULT_REPORT_OUTPUT,
    _latest_trade_date,
    _resolve_report_output_template,
    export_premarket_watchlist,
)


def test_premarket_watchlist_new_imports_are_available() -> None:
    assert DEFAULT_REPORT_OUTPUT == "phase0_premarket_report.html"
    assert callable(export_premarket_watchlist)
    assert callable(_resolve_report_output_template)
    assert callable(_latest_trade_date)


def test_legacy_premarket_watchlist_script_aliases_reporting_module() -> None:
    assert legacy_premarket_watchlist is premarket_watchlist
    assert legacy_premarket_watchlist.DEFAULT_REPORT_OUTPUT is DEFAULT_REPORT_OUTPUT
    assert legacy_premarket_watchlist.export_premarket_watchlist is export_premarket_watchlist
    assert legacy_premarket_watchlist._resolve_report_output_template is _resolve_report_output_template
    assert legacy_premarket_watchlist._latest_trade_date is _latest_trade_date


def test_legacy_premarket_watchlist_script_help_runs_directly() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/export_premarket_watchlist.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--top-candidates" in result.stdout
