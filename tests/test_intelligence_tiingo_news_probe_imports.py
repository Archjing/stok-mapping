from __future__ import annotations

import subprocess
import sys

import scripts.tiingo_news_probe as legacy_tiingo_probe
from phase0.intelligence import tiingo_news_probe


def test_tiingo_news_probe_new_import_is_available() -> None:
    assert callable(tiingo_news_probe.main)


def test_legacy_tiingo_news_probe_script_aliases_intelligence_module() -> None:
    assert legacy_tiingo_probe is tiingo_news_probe
    assert legacy_tiingo_probe.main is tiingo_news_probe.main


def test_legacy_tiingo_news_probe_script_help_runs_directly() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/tiingo_news_probe.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--tickers" in result.stdout
