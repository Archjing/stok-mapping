from __future__ import annotations

from phase0.execution import accounts as execution_accounts
from phase0.reporting import account_bill
from phase0.reporting.account_bill import (
    export_account_bill_html,
    format_money,
    format_num,
    format_pct,
    load_latest_account_snapshot,
)


def test_account_bill_reporting_imports_are_available() -> None:
    assert callable(format_money)
    assert callable(format_pct)
    assert callable(format_num)
    assert callable(load_latest_account_snapshot)
    assert callable(export_account_bill_html)


def test_execution_accounts_reexports_account_bill_helpers() -> None:
    assert execution_accounts.format_money is account_bill.format_money
    assert execution_accounts.format_pct is account_bill.format_pct
    assert execution_accounts.format_num is account_bill.format_num
    assert execution_accounts.load_latest_account_snapshot is account_bill.load_latest_account_snapshot
    assert execution_accounts.export_account_bill_html is account_bill.export_account_bill_html
