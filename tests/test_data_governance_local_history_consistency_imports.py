from __future__ import annotations

import subprocess
import sys

import scripts.check_local_history_consistency as legacy_consistency
from phase0.data_governance import local_history_consistency
from phase0.data_governance.local_history_consistency import _build_comparison


def test_local_history_consistency_new_imports_are_available() -> None:
    assert callable(_build_comparison)


def test_legacy_local_history_consistency_script_aliases_data_governance_module() -> None:
    assert legacy_consistency is local_history_consistency
    assert legacy_consistency._build_comparison is _build_comparison


def test_legacy_local_history_consistency_script_help_runs_directly() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_local_history_consistency.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--snapshot" in result.stdout
