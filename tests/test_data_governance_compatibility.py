from __future__ import annotations

from importlib import import_module

import pytest


@pytest.mark.parametrize(
    ("legacy_module_name", "new_module_name", "symbols"),
    [
        (
            "phase0.adjustment",
            "phase0.data_governance.adjustment",
            [
                "AdjustmentAuditResult",
                "ensure_adj_factor_table",
                "upsert_adj_factors",
                "build_qfq_asof_bars",
                "compute_qfq_asof",
                "run_adjustment_audit",
            ],
        ),
        (
            "phase0.external_market_history",
            "phase0.data_governance.external_market_history",
            [
                "MarketHistoryUpdateResult",
                "configure_us_market_history",
                "configure_hk_market_history",
                "update_us_market_history_from_config",
                "update_hk_market_history_from_config",
                "load_us_daily_from_history",
            ],
        ),
        (
            "phase0.financial_factors",
            "phase0.data_governance.financial_factors",
            [
                "FinancialFactorUpdateResult",
                "update_financial_factors_from_config",
                "ensure_financial_factor_table",
                "financial_factor_coverage",
            ],
        ),
        (
            "phase0.import_history",
            "phase0.data_governance.import_history",
            ["ImportResult", "IndexImportResult", "import_from_config", "import_index_history_from_config"],
        ),
        (
            "phase0.daily_basic_backfill",
            "phase0.data_governance.backfills.daily_basic",
            ["DailyBasicBackfillResult", "backfill_daily_basic_from_config"],
        ),
        (
            "phase0.adjustment_backfill",
            "phase0.data_governance.backfills.adjustment",
            ["AdjustmentBackfillResult", "backfill_adjustment_factors_from_config"],
        ),
        (
            "phase0.tushare_history_backfill",
            "phase0.data_governance.backfills.tushare_history",
            [
                "TushareHistoryBackfillResult",
                "TushareFinancialBackfillResult",
                "backfill_tushare_history_from_config",
                "backfill_tushare_financials_from_config",
            ],
        ),
    ],
)
def test_data_governance_legacy_imports_alias_new_modules(
    legacy_module_name: str,
    new_module_name: str,
    symbols: list[str],
) -> None:
    legacy_module = import_module(legacy_module_name)
    new_module = import_module(new_module_name)

    assert legacy_module is new_module
    for symbol in symbols:
        assert getattr(legacy_module, symbol) is getattr(new_module, symbol)


@pytest.mark.parametrize(
    ("legacy_module_name", "new_module_name", "symbols"),
    [
        ("phase0.db_health", "phase0.data_governance.db_health", ["run_database_health_check"]),
        ("phase0.index_asof_audit", "phase0.data_governance.index_asof_audit", ["run_index_asof_audit"]),
        (
            "phase0.index_asof_backfill",
            "phase0.data_governance.index_asof_backfill",
            ["normalize_index_weight_rows"],
        ),
        ("phase0.quality", "phase0.data_governance.quality", ["QualityResult"]),
    ],
)
def test_data_governance_legacy_imports_expose_selected_symbols(
    legacy_module_name: str,
    new_module_name: str,
    symbols: list[str],
) -> None:
    legacy_module = import_module(legacy_module_name)
    new_module = import_module(new_module_name)

    for symbol in symbols:
        assert getattr(legacy_module, symbol) is getattr(new_module, symbol)
