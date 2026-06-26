from __future__ import annotations

import phase0.tushare_source as legacy_tushare
from phase0.data_access.providers import tushare
from phase0.data_access.providers.tushare import TushareConfig, normalize_adj_factors, tushare_config
from phase0.tushare_source import TushareConfig as LegacyTushareConfig
from phase0.tushare_source import normalize_adj_factors as legacy_normalize_adj_factors
from phase0.tushare_source import tushare_config as legacy_tushare_config


def test_tushare_provider_new_imports_are_available() -> None:
    assert TushareConfig.__name__ == "TushareConfig"
    assert callable(tushare_config)
    assert callable(normalize_adj_factors)


def test_legacy_tushare_source_import_aliases_provider_module() -> None:
    assert legacy_tushare is tushare
    assert LegacyTushareConfig is TushareConfig
    assert legacy_tushare_config is tushare_config
    assert legacy_normalize_adj_factors is normalize_adj_factors
