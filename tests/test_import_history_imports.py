from __future__ import annotations

import phase0.import_history as legacy_import_history
import phase0.data_governance.import_history as governance_import_history


def test_import_history_legacy_import_aliases_governance_module() -> None:
    assert legacy_import_history is governance_import_history
    assert legacy_import_history.ImportResult is governance_import_history.ImportResult
    assert legacy_import_history.IndexImportResult is governance_import_history.IndexImportResult
    assert legacy_import_history.import_from_config is governance_import_history.import_from_config
    assert legacy_import_history.import_index_history_from_config is governance_import_history.import_index_history_from_config
