from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

import quant.cli as cli
import quant.cli_commands.pipeline_run as pipeline_run_cli


def test_pipeline_run_command_registration_preserves_args() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd")
    pipeline_run_cli.register_pipeline_run_commands(subparsers)

    run_args = parser.parse_args(["run", "--config", "custom.yaml", "--profile", "--no-wf-cache", "--refresh-wf-cache"])
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
    assert run_args.profile is True
    assert run_args.no_wf_cache is True
    assert run_args.refresh_wf_cache is True
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

    def fake_run_pipeline_cost_sensitivity(config_path: Path, scenarios: list[dict[str, float | str]]) -> int:
        calls.append({"config_path": config_path, "scenarios": scenarios})
        return 0

    monkeypatch.setattr(pipeline_run_cli, "load_config", fake_load_config)
    monkeypatch.setattr(pipeline_run_cli, "run_pipeline_cost_sensitivity", fake_run_pipeline_cost_sensitivity)
    args = SimpleNamespace(
        cmd="cost-sensitivity",
        config=str(tmp_path / "config.yaml"),
        scenario=["base:0.001", "stress:0.003"],
        use_config_scenarios=False,
    )

    exit_code = pipeline_run_cli.handle_pipeline_run_command(
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
        return {"local_history": {}}

    def fake_run_db_health_gate(**kwargs) -> int:
        calls.append(("gate", kwargs))
        return 0

    def fake_run_pipeline(
        config_path: Path,
        *,
        profile: bool = False,
        no_wf_cache: bool = False,
        refresh_wf_cache: bool = False,
    ) -> int:
        calls.append(
            (
                "run",
                {
                    "config_path": config_path,
                    "profile": profile,
                    "no_wf_cache": no_wf_cache,
                    "refresh_wf_cache": refresh_wf_cache,
                },
            )
        )
        return 0

    monkeypatch.setattr(pipeline_run_cli, "load_config", fake_load_config)
    monkeypatch.setattr(pipeline_run_cli, "_run_db_health_gate", fake_run_db_health_gate)
    monkeypatch.setattr(pipeline_run_cli, "run_pipeline", fake_run_pipeline)
    args = SimpleNamespace(
        cmd="run",
        config=str(tmp_path / "config.yaml"),
        profile=True,
        no_wf_cache=True,
        refresh_wf_cache=True,
    )

    exit_code = pipeline_run_cli.handle_pipeline_run_command(
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
    assert calls[1] == (
        "run",
        {
            "config_path": (tmp_path / "config.yaml").resolve(),
            "profile": True,
            "no_wf_cache": True,
            "refresh_wf_cache": True,
        },
    )


def test_pipeline_run_compatibility_exports_remain_available() -> None:
    assert cli.run_pipeline is pipeline_run_cli.run_pipeline
    assert cli.run_pipeline_cost_sensitivity is pipeline_run_cli.run_pipeline_cost_sensitivity
    assert cli._parse_cost_scenario is pipeline_run_cli._parse_cost_scenario
    assert cli._configured_cost_scenarios is pipeline_run_cli._configured_cost_scenarios


def test_phase0_cost_sensitivity_uses_configured_phase0_category(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
quant:
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

    monkeypatch.setattr(pipeline_run_cli, "configure_local_history", lambda cfg, root: None)
    monkeypatch.setattr(pipeline_run_cli, "configure_akshare_throttle", lambda cfg: None)
    monkeypatch.setattr(pipeline_run_cli, "run_cost_sensitivity", lambda cfg, *, root=None: pd.DataFrame({"scenario": ["base"]}))
    monkeypatch.setattr(pipeline_run_cli, "save_walk_forward_csv", lambda df, output_path: saved_paths.append(Path(output_path)))
    monkeypatch.setattr(pipeline_run_cli, "write_cost_sensitivity_report", lambda path, df: report_paths.append(Path(path)))

    exit_code = pipeline_run_cli.run_pipeline_cost_sensitivity(
        config_path,
        [{"name": "base", "slippage": 0.001, "commission": 0.0, "stamp_duty_sell": 0.0}],
    )

    assert exit_code == 0
    assert saved_paths == [tmp_path / "local_reports" / "phase_zero" / "phase0_cost_sensitivity.csv"]
    assert report_paths == [tmp_path / "local_reports" / "phase_zero" / "phase0_cost_sensitivity_report.md"]
