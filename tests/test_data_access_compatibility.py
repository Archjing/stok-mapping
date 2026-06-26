from __future__ import annotations

from importlib import import_module

import pytest


@pytest.mark.parametrize(
    ("legacy_module_name", "new_module_name", "symbols"),
    [
        (
            "phase0.data_sources",
            "phase0.data_access.connectivity",
            [
                "ConnectivityResult",
                "check_connectivity",
                "fetch_yf_daily",
                "fetch_fred_series",
                "fetch_tiingo_daily",
                "fetch_tiingo_news",
                "fetch_cn_daily",
                "fetch_hk_daily",
                "fetch_tushare_hk_daily",
            ],
        ),
        (
            "phase0.tushare_source",
            "phase0.data_access.providers.tushare",
            ["TushareConfig", "normalize_adj_factors", "tushare_config"],
        ),
        (
            "phase0.throttle",
            "phase0.data_access.throttle",
            [
                "AkshareThrottleSettings",
                "AkshareThrottle",
                "akshare_throttle",
                "configure_akshare_throttle",
                "fetch_with_akshare_retries",
            ],
        ),
        (
            "phase0.local_history",
            "phase0.data_access.local_history",
            [
                "LocalHistorySettings",
                "normalize_cn_symbol",
                "configure_local_history",
                "local_history_path",
                "load_daily_from_local_history",
                "load_index_daily_from_local_history",
                "load_snapshot_from_local_history_as_of",
            ],
        ),
    ],
)
def test_data_access_legacy_imports_alias_new_modules(
    legacy_module_name: str,
    new_module_name: str,
    symbols: list[str],
) -> None:
    legacy_module = import_module(legacy_module_name)
    new_module = import_module(new_module_name)

    assert legacy_module is new_module
    for symbol in symbols:
        assert getattr(legacy_module, symbol) is getattr(new_module, symbol)
