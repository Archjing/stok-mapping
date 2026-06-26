from __future__ import annotations

import phase0.external_market_history as legacy_external_market_history
import phase0.data_governance.external_market_history as governance_external_market_history


def test_external_market_history_legacy_import_aliases_governance_module() -> None:
    assert legacy_external_market_history is governance_external_market_history
    assert (
        legacy_external_market_history.MarketHistoryUpdateResult
        is governance_external_market_history.MarketHistoryUpdateResult
    )
    assert (
        legacy_external_market_history.configure_us_market_history
        is governance_external_market_history.configure_us_market_history
    )
    assert (
        legacy_external_market_history.configure_hk_market_history
        is governance_external_market_history.configure_hk_market_history
    )
    assert (
        legacy_external_market_history.update_us_market_history_from_config
        is governance_external_market_history.update_us_market_history_from_config
    )
    assert (
        legacy_external_market_history.update_hk_market_history_from_config
        is governance_external_market_history.update_hk_market_history_from_config
    )
    assert (
        legacy_external_market_history.load_us_daily_from_history
        is governance_external_market_history.load_us_daily_from_history
    )
