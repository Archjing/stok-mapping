from phase0.data_governance.db_health import run_database_health_check
from phase0.data_governance.index_asof_audit import run_index_asof_audit
from phase0.data_governance.index_asof_backfill import normalize_index_weight_rows
from phase0.data_governance.quality import QualityResult
from phase0.db_health import _check_cn_market_data, _connect
from phase0.index_asof_audit import run_index_asof_audit as legacy_run_index_asof_audit
from phase0.index_asof_backfill import normalize_index_weight_rows as legacy_normalize_index_weight_rows
from phase0.quality import QualityResult as LegacyQualityResult


def test_data_governance_new_imports_are_available() -> None:
    assert callable(run_database_health_check)
    assert callable(run_index_asof_audit)
    assert callable(normalize_index_weight_rows)
    assert QualityResult.__name__ == "QualityResult"


def test_legacy_data_governance_imports_remain_compatible() -> None:
    assert callable(_check_cn_market_data)
    assert callable(_connect)
    assert legacy_run_index_asof_audit is run_index_asof_audit
    assert legacy_normalize_index_weight_rows is normalize_index_weight_rows
    assert LegacyQualityResult is QualityResult
