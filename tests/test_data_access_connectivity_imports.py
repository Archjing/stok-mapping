from __future__ import annotations

import phase0.data_sources as legacy_data_sources
from phase0.data_access import connectivity
from phase0.data_access.connectivity import (
    ConnectivityResult,
    check_connectivity,
    fetch_cn_daily,
    fetch_fred_series,
    fetch_hk_daily,
    fetch_tiingo_daily,
    fetch_tiingo_news,
    fetch_tushare_hk_daily,
    fetch_yf_daily,
)


def test_connectivity_new_imports_are_available() -> None:
    assert ConnectivityResult.__name__ == "ConnectivityResult"
    assert callable(check_connectivity)
    assert callable(fetch_yf_daily)
    assert callable(fetch_fred_series)
    assert callable(fetch_tiingo_daily)
    assert callable(fetch_tiingo_news)
    assert callable(fetch_cn_daily)
    assert callable(fetch_hk_daily)
    assert callable(fetch_tushare_hk_daily)


def test_legacy_data_sources_import_aliases_connectivity_module() -> None:
    assert legacy_data_sources is connectivity
    assert legacy_data_sources.ConnectivityResult is ConnectivityResult
    assert legacy_data_sources.check_connectivity is check_connectivity
    assert legacy_data_sources.fetch_yf_daily is fetch_yf_daily
    assert legacy_data_sources.fetch_fred_series is fetch_fred_series
    assert legacy_data_sources.fetch_tiingo_daily is fetch_tiingo_daily
    assert legacy_data_sources.fetch_tiingo_news is fetch_tiingo_news
    assert legacy_data_sources.fetch_cn_daily is fetch_cn_daily
    assert legacy_data_sources.fetch_hk_daily is fetch_hk_daily
    assert legacy_data_sources.fetch_tushare_hk_daily is fetch_tushare_hk_daily
