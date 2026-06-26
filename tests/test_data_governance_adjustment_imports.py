from __future__ import annotations

import phase0.adjustment as legacy_adjustment
import phase0.data_governance.adjustment as data_governance_adjustment


def test_adjustment_legacy_import_aliases_data_governance_module() -> None:
    assert legacy_adjustment is data_governance_adjustment
    assert legacy_adjustment.AdjustmentAuditResult is data_governance_adjustment.AdjustmentAuditResult
    assert legacy_adjustment.ensure_adj_factor_table is data_governance_adjustment.ensure_adj_factor_table
    assert legacy_adjustment.upsert_adj_factors is data_governance_adjustment.upsert_adj_factors
    assert legacy_adjustment.build_qfq_asof_bars is data_governance_adjustment.build_qfq_asof_bars
    assert legacy_adjustment.compute_qfq_asof is data_governance_adjustment.compute_qfq_asof
    assert legacy_adjustment.run_adjustment_audit is data_governance_adjustment.run_adjustment_audit
