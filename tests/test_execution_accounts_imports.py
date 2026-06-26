from __future__ import annotations

import phase0.accounts as legacy_accounts
from phase0.execution import accounts
from phase0.execution.accounts import (
    SimulatedAccountConfig,
    export_account_bill_html,
    load_simulated_accounts,
    run_signal_account_execution,
)


def test_execution_accounts_new_imports_are_available() -> None:
    assert SimulatedAccountConfig.__name__ == "SimulatedAccountConfig"
    assert callable(load_simulated_accounts)
    assert callable(run_signal_account_execution)
    assert callable(export_account_bill_html)


def test_legacy_accounts_import_aliases_execution_module() -> None:
    assert legacy_accounts is accounts
    assert legacy_accounts.SimulatedAccountConfig is SimulatedAccountConfig
    assert legacy_accounts.load_simulated_accounts is load_simulated_accounts
    assert legacy_accounts.run_signal_account_execution is run_signal_account_execution
    assert legacy_accounts.export_account_bill_html is export_account_bill_html
