from __future__ import annotations

import importlib
import pytest

from quant.config import load_config_document, select_quant_config
from quant.maintenance_orchestrator import _effective_maintenance_command


def test_select_quant_config_prefers_quant_root() -> None:
    data = {"quant": {"name": "x"}, "other": 1}
    assert select_quant_config(data) == {"name": "x"}


def test_select_quant_config_warns_on_legacy_phase0_root() -> None:
    data = {"phase0": {"name": "x"}}
    with pytest.warns(DeprecationWarning, match="deprecated"):
        selected = select_quant_config(data)
    assert selected == {"name": "x"}


def test_select_quant_config_rejects_both_roots() -> None:
    data = {"quant": {}, "phase0": {}}
    with pytest.raises(ValueError, match="both 'quant' and legacy 'phase0'"):
        select_quant_config(data)


def test_select_quant_config_raises_when_missing() -> None:
    with pytest.raises(ValueError, match="missing 'quant'"):
        select_quant_config({})


def test_load_config_document_returns_raw_document(tmp_path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("quant:\n  name: x\n", encoding="utf-8")
    doc = load_config_document(config_path)
    assert doc == {"quant": {"name": "x"}}


def test_phase0_cli_module_is_thin_forwarder_to_quant_cli() -> None:
    phase0_cli = importlib.import_module("phase0.cli")
    quant_cli = importlib.import_module("quant.cli")
    assert phase0_cli.main is quant_cli.main


def test_phase0_application_modules_are_not_importable() -> None:
    # Only 'phase0.cli' and the package __init__ are retained. Importing the old
    # application modules must fail so nothing silently relies on a second namespace.
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("phase0.walk_forward")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("phase0.reporting.paths")


def test_phase0_import_blocked_via_import_statement() -> None:
    with pytest.raises(ImportError):
        from phase0 import walk_forward  # noqa: F401


def test_effective_maintenance_command_migrates_phase0_cli_to_quant_cli() -> None:
    command = ["python", "-m", "phase0.cli", "maintain", "tick"]
    assert _effective_maintenance_command(command) == [
        "python",
        "-m",
        "quant.cli",
        "maintain",
        "tick",
    ]


def test_effective_maintenance_command_preserves_artifact_arguments() -> None:
    command = [
        "python",
        "-m",
        "phase0.cli",
        "report",
        "--output-dir",
        "reports/phase0/daily",
    ]
    assert _effective_maintenance_command(command) == [
        "python",
        "-m",
        "quant.cli",
        "report",
        "--output-dir",
        "reports/phase0/daily",
    ]


def test_effective_maintenance_command_keeps_quant_cli_unchanged() -> None:
    command = ["python", "-m", "quant.cli", "maintain", "tick"]
    assert _effective_maintenance_command(command) == command
