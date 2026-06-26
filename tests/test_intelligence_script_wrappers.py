from __future__ import annotations

from importlib import import_module
import subprocess
import sys

import pandas as pd
import pytest

from phase0.intelligence.hk_a_mapping_factors import _normalize_ah_comparison, _normalize_hsgt_hist


@pytest.mark.parametrize(
    ("script_module_name", "intelligence_module_name", "symbols", "script_path", "help_flag"),
    [
        (
            "scripts.export_hk_a_mapping_factors",
            "phase0.intelligence.hk_a_mapping_factors",
            ["_normalize_ah_comparison", "_normalize_hsgt_hist"],
            "scripts/export_hk_a_mapping_factors.py",
            "--holding-symbol",
        ),
        (
            "scripts.tiingo_news_probe",
            "phase0.intelligence.tiingo_news_probe",
            ["main"],
            "scripts/tiingo_news_probe.py",
            "--tickers",
        ),
    ],
)
def test_intelligence_script_wrappers_alias_packaged_modules_and_show_help(
    script_module_name: str,
    intelligence_module_name: str,
    symbols: list[str],
    script_path: str,
    help_flag: str,
) -> None:
    script_module = import_module(script_module_name)
    intelligence_module = import_module(intelligence_module_name)

    assert script_module is intelligence_module
    for symbol in symbols:
        assert getattr(script_module, symbol) is getattr(intelligence_module, symbol)

    result = subprocess.run(
        [sys.executable, script_path, "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert help_flag in result.stdout


def test_hk_a_mapping_normalizes_ah_comparison_with_local_prices() -> None:
    raw = pd.DataFrame(
        {
            "H股代码": ["00700"],
            "名称": ["腾讯控股"],
            "H股最新价": ["390.5"],
            "AH溢价率": ["12.3%"],
        }
    )
    a_prices = pd.DataFrame(
        {
            "match_name": ["腾讯控股"],
            "a_symbol": ["CN.000001"],
            "a_code": ["000001"],
            "a_name": ["腾讯控股"],
            "a_trade_date": ["2026-06-25"],
            "a_close": [100.0],
        }
    )

    result = _normalize_ah_comparison(raw, a_prices)

    assert result.loc[0, "a_symbol"] == "CN.000001"
    assert result.loc[0, "h_price"] == 390.5
    assert result.loc[0, "akshare_ah_premium_or_ratio"] == 12.3


def test_hk_a_mapping_normalizes_hsgt_history() -> None:
    raw = pd.DataFrame(
        {
            "日期": ["2026-06-24", "2026-06-25"],
            "当日成交净买额": ["1,000", "2,000"],
            "成交金额": ["10,000", "20,000"],
        }
    )

    result = _normalize_hsgt_hist(raw, "北向资金")

    assert list(result["channel"]) == ["北向资金", "北向资金"]
    assert list(result["net_buy_amount"]) == [1000, 2000]
    assert result.loc[1, "net_buy_ma5"] == 1500
