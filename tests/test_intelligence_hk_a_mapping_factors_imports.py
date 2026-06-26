from __future__ import annotations

import subprocess
import sys

import pandas as pd

import scripts.export_hk_a_mapping_factors as legacy_hk_mapping
from phase0.intelligence import hk_a_mapping_factors
from phase0.intelligence.hk_a_mapping_factors import _normalize_ah_comparison, _normalize_hsgt_hist


def test_hk_a_mapping_factors_new_imports_are_available() -> None:
    assert callable(_normalize_ah_comparison)
    assert callable(_normalize_hsgt_hist)


def test_legacy_hk_a_mapping_script_aliases_intelligence_module() -> None:
    assert legacy_hk_mapping is hk_a_mapping_factors
    assert legacy_hk_mapping._normalize_ah_comparison is _normalize_ah_comparison


def test_legacy_hk_a_mapping_script_help_runs_directly() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/export_hk_a_mapping_factors.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--holding-symbol" in result.stdout


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
