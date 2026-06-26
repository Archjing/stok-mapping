from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

import phase0.cli as cli
import phase0.cli_commands.phase0_run as phase0_run_cli


def test_phase0_run_command_registration_preserves_args() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd")
    phase0_run_cli.register_phase0_run_commands(subparsers)

    run_args = parser.parse_args(["run", "--config", "custom.yaml"])
    scenario_args = parser.parse_args(
        [
            "cost-sensitivity",
            "--config",
            "custom.yaml",
            "--scenario",
            "base:0.001",
            "--scenario",
            "stress:0.003",
        ]
    )
    config_scenario_args = parser.parse_args(["cost-sensitivity", "--use-config-scenarios"])

    assert run_args.cmd == "run"
    assert run_args.config == "custom.yaml"
    assert scenario_args.cmd == "cost-sensitivity"
    assert scenario_args.config == "custom.yaml"
    assert scenario_args.scenario == ["base:0.001", "stress:0.003"]
    assert scenario_args.use_config_scenarios is False
    assert config_scenario_args.config == "config.yaml"
    assert config_scenario_args.use_config_scenarios is True


def test_cost_sensitivity_handler_parses_scenarios_and_forwards(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_load_config(path: Path) -> dict[str, object]:
        return {"walk_forward": {"commission": 0.0002, "stamp_duty_sell": 0.001}}

    def fake_run_phase0_cost_sensitivity(config_path: Path, scenarios: list[dict[str, float | str]]) -> int:
        calls.append({"config_path": config_path, "scenarios": scenarios})
        return 0

    monkeypatch.setattr(phase0_run_cli, "load_config", fake_load_config)
    monkeypatch.setattr(phase0_run_cli, "run_phase0_cost_sensitivity", fake_run_phase0_cost_sensitivity)
    args = SimpleNamespace(
        cmd="cost-sensitivity",
        config=str(tmp_path / "config.yaml"),
        scenario=["base:0.001", "stress:0.003"],
        use_config_scenarios=False,
    )

    exit_code = phase0_run_cli.handle_phase0_run_command(
        args,
        parser=argparse.ArgumentParser(),
        console=SimpleNamespace(print=lambda text: None),
    )

    assert exit_code == 0
    assert calls == [
        {
            "config_path": (tmp_path / "config.yaml").resolve(),
            "scenarios": [
                {"name": "base", "slippage": 0.001, "commission": 0.0002, "stamp_duty_sell": 0.001},
                {"name": "stress", "slippage": 0.003, "commission": 0.0002, "stamp_duty_sell": 0.001},
            ],
        }
    ]


def test_run_handler_runs_health_gate_before_phase0(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_load_config(path: Path) -> dict[str, object]:
        return {"phase0": {"local_history": {}}}

    def fake_run_db_health_gate(**kwargs) -> int:
        calls.append(("gate", kwargs))
        return 0

    def fake_run_phase0(config_path: Path) -> int:
        calls.append(("run", {"config_path": config_path}))
        return 0

    monkeypatch.setattr(phase0_run_cli, "load_config", fake_load_config)
    monkeypatch.setattr(phase0_run_cli, "_run_db_health_gate", fake_run_db_health_gate)
    monkeypatch.setattr(phase0_run_cli, "run_phase0", fake_run_phase0)
    args = SimpleNamespace(cmd="run", config=str(tmp_path / "config.yaml"))

    exit_code = phase0_run_cli.handle_phase0_run_command(
        args,
        parser=argparse.ArgumentParser(),
        console=SimpleNamespace(print=lambda text: None),
    )

    assert exit_code == 0
    assert calls[0][0] == "gate"
    assert calls[0][1]["config"] == {"local_history": {}}
    assert calls[0][1]["root"] == tmp_path
    assert calls[0][1]["scope"] == "cn"
    assert calls[0][1]["fail_on"] == "error"
    assert calls[0][1]["label"] == "Phase 0 run"
    assert calls[1] == ("run", {"config_path": (tmp_path / "config.yaml").resolve()})


def test_phase0_run_compatibility_exports_remain_available() -> None:
    assert cli.run_phase0 is phase0_run_cli.run_phase0
    assert cli.run_phase0_cost_sensitivity is phase0_run_cli.run_phase0_cost_sensitivity
    assert cli._parse_cost_scenario is phase0_run_cli._parse_cost_scenario
    assert cli._configured_cost_scenarios is phase0_run_cli._configured_cost_scenarios


def test_phase0_cost_sensitivity_uses_configured_phase0_category(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
phase0:
  reporting:
    root_dir: local_reports
    categories:
      phase0: phase_zero
  local_history: {}
  data_sources: {}
  walk_forward: {}
""",
        encoding="utf-8",
    )
    saved_paths: list[Path] = []
    report_paths: list[Path] = []

    monkeypatch.setattr(phase0_run_cli, "configure_local_history", lambda cfg, root: None)
    monkeypatch.setattr(phase0_run_cli, "configure_akshare_throttle", lambda cfg: None)
    monkeypatch.setattr(phase0_run_cli, "run_cost_sensitivity", lambda cfg: pd.DataFrame({"scenario": ["base"]}))
    monkeypatch.setattr(phase0_run_cli, "save_walk_forward_csv", lambda df, output_path: saved_paths.append(Path(output_path)))
    monkeypatch.setattr(phase0_run_cli, "write_cost_sensitivity_report", lambda path, df: report_paths.append(Path(path)))

    exit_code = phase0_run_cli.run_phase0_cost_sensitivity(
        config_path,
        [{"name": "base", "slippage": 0.001, "commission": 0.0, "stamp_duty_sell": 0.0}],
    )

    assert exit_code == 0
    assert saved_paths == [tmp_path / "local_reports" / "phase_zero" / "phase0_cost_sensitivity.csv"]
    assert report_paths == [tmp_path / "local_reports" / "phase_zero" / "phase0_cost_sensitivity_report.md"]
