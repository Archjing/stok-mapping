from __future__ import annotations

from importlib import import_module
import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    ("script_module_name", "governance_module_name", "symbols"),
    [
        (
            "scripts.audit_financial_pti",
            "phase0.data_governance.financial_pti",
            ["audit_financial_pti"],
        ),
        (
            "scripts.audit_universe_pit",
            "phase0.data_governance.universe_pit",
            ["audit_universe_pit"],
        ),
        (
            "scripts.check_local_history_consistency",
            "phase0.data_governance.local_history_consistency",
            ["_build_comparison"],
        ),
    ],
)
def test_data_governance_script_wrappers_alias_packaged_modules(
    script_module_name: str,
    governance_module_name: str,
    symbols: list[str],
) -> None:
    script_module = import_module(script_module_name)
    governance_module = import_module(governance_module_name)

    assert script_module is governance_module
    for symbol in symbols:
        assert getattr(script_module, symbol) is getattr(governance_module, symbol)


@pytest.mark.parametrize(
    ("script_path", "help_flag"),
    [
        ("scripts/audit_financial_pti.py", "--summary-output"),
        ("scripts/check_local_history_consistency.py", "--snapshot"),
    ],
)
def test_data_governance_script_wrappers_show_help(script_path: str, help_flag: str) -> None:
    result = subprocess.run(
        [sys.executable, script_path, "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert help_flag in result.stdout
