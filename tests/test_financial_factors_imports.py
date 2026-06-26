from __future__ import annotations

import phase0.financial_factors as legacy_financial_factors
import phase0.data_governance.financial_factors as governance_financial_factors


def test_financial_factors_legacy_import_aliases_governance_module() -> None:
    assert legacy_financial_factors is governance_financial_factors
    assert legacy_financial_factors.FinancialFactorUpdateResult is governance_financial_factors.FinancialFactorUpdateResult
    assert (
        legacy_financial_factors.update_financial_factors_from_config
        is governance_financial_factors.update_financial_factors_from_config
    )
    assert legacy_financial_factors.ensure_financial_factor_table is governance_financial_factors.ensure_financial_factor_table
    assert legacy_financial_factors.financial_factor_coverage is governance_financial_factors.financial_factor_coverage
