from __future__ import annotations

import phase0.local_history as legacy_local_history
import phase0.data_access.local_history as data_access_local_history


def test_local_history_legacy_import_aliases_data_access_module() -> None:
    assert legacy_local_history is data_access_local_history
    assert legacy_local_history.LocalHistorySettings is data_access_local_history.LocalHistorySettings
    assert legacy_local_history.normalize_cn_symbol is data_access_local_history.normalize_cn_symbol
    assert legacy_local_history.configure_local_history is data_access_local_history.configure_local_history
    assert legacy_local_history.local_history_path is data_access_local_history.local_history_path
    assert legacy_local_history.load_daily_from_local_history is data_access_local_history.load_daily_from_local_history
    assert legacy_local_history.load_index_daily_from_local_history is data_access_local_history.load_index_daily_from_local_history
    assert (
        legacy_local_history.load_snapshot_from_local_history_as_of
        is data_access_local_history.load_snapshot_from_local_history_as_of
    )
