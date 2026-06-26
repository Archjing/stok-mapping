import phase0.intelligence as intelligence
from phase0.intelligence import validation
from phase0.intelligence.schema import IntelligenceValidationResult, LEDGER_COLUMNS


def test_intelligence_validation_exports_remain_compatible() -> None:
    assert intelligence.validate_intelligence_ledger is validation.validate_intelligence_ledger
    assert intelligence.IntelligenceValidationResult is IntelligenceValidationResult
    assert intelligence.LEDGER_COLUMNS is LEDGER_COLUMNS


def test_legacy_validation_private_helpers_alias_new_module() -> None:
    assert intelligence._read_ledger is validation._read_ledger
    assert intelligence._read_csv_rows is validation._read_csv_rows
    assert intelligence._local_path_exists is validation._local_path_exists
    assert intelligence._validate_rag_manifest is validation._validate_rag_manifest
