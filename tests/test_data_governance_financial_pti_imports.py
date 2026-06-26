from __future__ import annotations

import subprocess
import sys

import scripts.audit_financial_pti as legacy_financial_pti
from phase0.data_governance import financial_pti
from phase0.data_governance.financial_pti import audit_financial_pti


def test_financial_pti_new_imports_are_available() -> None:
    assert callable(audit_financial_pti)


def test_legacy_financial_pti_script_aliases_data_governance_module() -> None:
    assert legacy_financial_pti is financial_pti
    assert legacy_financial_pti.audit_financial_pti is audit_financial_pti


def test_legacy_financial_pti_script_help_runs_directly() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/audit_financial_pti.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--summary-output" in result.stdout
