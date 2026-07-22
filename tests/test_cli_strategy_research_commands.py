from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

import pytest

import phase0.cli as cli
import phase0.cli_commands.gates as gates_cli
import phase0.cli_commands.strategy_research as strategy_research_cli


def _silent_console() -> SimpleNamespace:
    return SimpleNamespace(print=lambda text: None)


def test_strategy_research_command_registration_preserves_args() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd")
    strategy_research_cli.register_strategy_research_commands(subparsers)

    overfit_args = parser.parse_args(
        [
            "overfit-diagnostic",
            "--candidates",
            "candidates.csv",
            "--folds",
            "folds.csv",
            "--output-dir",
            "overfit",
        ]
    )
    admission_args = parser.parse_args(
        [
            "strategy-admission",
            "--presets",
            "baseline_2y_1y_5fold",
            "quality_3y_1y_4fold",
            "--strategy-set",
            "baseline_admission_all_v1",
            "--strategies",
            "s1",
            "s2",
            "--output-dir",
            "admission",
            "--trace-run",
            "--profile",
            "--no-wf-cache",
            "--refresh-wf-cache",
            "--cost-multiplier",
            "1.5",
        ]
    )
    factor_args = parser.parse_args(["factor-effectiveness", "--output-dir", "factor"])

    assert overfit_args.cmd == "overfit-diagnostic"
    assert overfit_args.config == "config.yaml"
    assert overfit_args.candidates == "candidates.csv"
    assert overfit_args.folds == "folds.csv"
    assert overfit_args.output_dir == "overfit"
    assert admission_args.cmd == "strategy-admission"
    assert admission_args.presets == ["baseline_2y_1y_5fold", "quality_3y_1y_4fold"]
    assert admission_args.strategy_set == "baseline_admission_all_v1"
    assert admission_args.strategies == ["s1", "s2"]
    assert admission_args.output_dir == "admission"
    assert admission_args.trace_run is True
    assert admission_args.profile is True
    assert admission_args.no_wf_cache is True
    assert admission_args.refresh_wf_cache is True
    assert admission_args.cost_multiplier == 1.5
    assert factor_args.cmd == "factor-effectiveness"
    assert factor_args.config == "config.yaml"
    assert factor_args.output_dir == "factor"

    default_admission_args = parser.parse_args(["strategy-admission"])
    assert default_admission_args.cost_multiplier == 1.0


@pytest.mark.parametrize("value", ["0", "-1", "nan", "+inf", "-inf"])
def test_strategy_admission_rejects_non_positive_or_non_finite_cost_multiplier(value: str) -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd")
    strategy_research_cli.register_strategy_research_commands(subparsers)

    with pytest.raises(SystemExit):
        parser.parse_args(["strategy-admission", "--cost-multiplier", value])


def test_overfit_handler_forwards_paths(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_load_config(path: Path) -> dict[str, object]:
        return {"phase0": {"walk_forward": {}}}

    def fake_run_overfit_diagnostic(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            selected_candidate="sample_strategy",
            selected_risk_level="medium",
            csv_path=tmp_path / "overfit.csv",
            md_path=tmp_path / "overfit.md",
            rows=3,
        )

    monkeypatch.setattr(strategy_research_cli, "load_config", fake_load_config)
    monkeypatch.setattr(strategy_research_cli, "run_overfit_diagnostic", fake_run_overfit_diagnostic)
    args = SimpleNamespace(
        cmd="overfit-diagnostic",
        config=str(tmp_path / "config.yaml"),
        candidates=str(tmp_path / "candidates.csv"),
        folds=str(tmp_path / "folds.csv"),
        output_dir=str(tmp_path / "overfit"),
    )

    exit_code = strategy_research_cli.handle_strategy_research_command(
        args,
        parser=argparse.ArgumentParser(),
        console=_silent_console(),
    )

    assert exit_code == 0
    assert calls == [
        {
            "config": {"walk_forward": {}},
            "root": tmp_path,
            "candidates_path": (tmp_path / "candidates.csv").resolve(),
            "folds_path": (tmp_path / "folds.csv").resolve(),
            "output_dir": (tmp_path / "overfit").resolve(),
        }
    ]


def test_strategy_admission_handler_forwards_scope_and_trace(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []
    trace_messages: list[str] = []

    def fake_load_config(path: Path) -> dict[str, object]:
        return {"phase0": {"walk_forward": {"presets": {"baseline": {}}}}}

    def fake_describe_walk_forward_presets(walk_forward_cfg, presets, *, default_all: bool):
        calls.append(
            {
                "describe_walk_forward_cfg": walk_forward_cfg,
                "describe_presets": presets,
                "describe_default_all": default_all,
            }
        )
        return ["preset: baseline"]

    def fake_run_strategy_admission(**kwargs):
        calls.append(kwargs)
        kwargs["trace_callback"](
            {
                "event": "fold_result",
                "strategy_id": "sample_strategy",
                "fold": 1,
                "annualized_return": 0.12,
                "sharpe": 1.5,
            }
        )
        return SimpleNamespace(
            strategies=["sample_strategy"],
            presets=["baseline"],
            rows=1,
            matrix_csv=tmp_path / "matrix.csv",
            constraint_csv=tmp_path / "constraints.csv",
            folds_csv=tmp_path / "folds.csv",
            overfit_csv=tmp_path / "overfit.csv",
            report_md=tmp_path / "admission.md",
            governance_md=tmp_path / "governance.md",
        )

    monkeypatch.setattr(strategy_research_cli, "load_config", fake_load_config)
    monkeypatch.setattr(strategy_research_cli, "describe_walk_forward_presets", fake_describe_walk_forward_presets)
    monkeypatch.setattr(strategy_research_cli, "run_strategy_admission", fake_run_strategy_admission)
    args = SimpleNamespace(
        cmd="strategy-admission",
        config=str(tmp_path / "config.yaml"),
        presets=["baseline"],
        strategy_set="baseline_admission_all_v1",
        strategies=["sample_strategy"],
        output_dir=str(tmp_path / "admission"),
        trace_run=True,
        profile=True,
        no_wf_cache=True,
        refresh_wf_cache=True,
        cost_multiplier=1.5,
    )

    exit_code = strategy_research_cli.handle_strategy_research_command(
        args,
        parser=argparse.ArgumentParser(),
        console=SimpleNamespace(print=lambda text: trace_messages.append(str(text))),
    )

    assert exit_code == 0
    assert calls[0] == {
        "describe_walk_forward_cfg": {"presets": {"baseline": {}}},
        "describe_presets": ["baseline"],
        "describe_default_all": True,
    }
    assert calls[1]["config"] == {"walk_forward": {"presets": {"baseline": {}}}}
    assert calls[1]["root"] == tmp_path
    assert calls[1]["config_path"] == (tmp_path / "config.yaml").resolve()
    assert calls[1]["presets"] == ["baseline"]
    assert calls[1]["strategy_set"] == "baseline_admission_all_v1"
    assert calls[1]["strategies"] == ["sample_strategy"]
    assert calls[1]["output_dir"] == (tmp_path / "admission").resolve()
    assert callable(calls[1]["trace_callback"])
    assert calls[1]["profile_run"] is True
    assert calls[1]["no_wf_cache"] is True
    assert calls[1]["refresh_wf_cache"] is True
    assert calls[1]["cost_multiplier"] == 1.5
    assert any("WF fold result" in line for line in trace_messages)


def test_factor_effectiveness_handler_runs_health_gate_then_report(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_load_config(path: Path) -> dict[str, object]:
        return {"phase0": {"local_history": {}}}

    def fake_run_database_health_check(**kwargs):
        calls.append({"health": kwargs})
        return SimpleNamespace(
            status="pass",
            error_count=0,
            warning_count=0,
            info_count=1,
            summary_md=tmp_path / "health.md",
        )

    def fake_run_factor_effectiveness_report(**kwargs):
        calls.append({"factor": kwargs})
        return SimpleNamespace(
            factor_count=5,
            fold_count=4,
            summary_csv=tmp_path / "summary.csv",
            summary_md=tmp_path / "factor.md",
            group_returns_csv=tmp_path / "group.csv",
            ic_by_year_csv=tmp_path / "ic.csv",
            correlation_csv=tmp_path / "corr.csv",
            warnings=[],
        )

    monkeypatch.setattr(strategy_research_cli, "load_config", fake_load_config)
    monkeypatch.setattr(gates_cli, "run_database_health_check", fake_run_database_health_check)
    monkeypatch.setattr(strategy_research_cli, "run_factor_effectiveness_report", fake_run_factor_effectiveness_report)
    args = SimpleNamespace(
        cmd="factor-effectiveness",
        config=str(tmp_path / "config.yaml"),
        output_dir=str(tmp_path / "factor"),
    )

    exit_code = strategy_research_cli.handle_strategy_research_command(
        args,
        parser=argparse.ArgumentParser(),
        console=_silent_console(),
    )

    assert exit_code == 0
    assert calls == [
        {
            "health": {
                "config": {"local_history": {}},
                "root": tmp_path,
                "scope": "cn",
                "output_dir": None,
            }
        },
        {
            "factor": {
                "config": {"local_history": {}},
                "root": tmp_path,
                "output_dir": (tmp_path / "factor").resolve(),
            }
        },
    ]


def test_factor_effectiveness_handler_stops_when_health_gate_fails(monkeypatch, tmp_path: Path) -> None:
    called_factor = False

    def fake_load_config(path: Path) -> dict[str, object]:
        return {"phase0": {"local_history": {}}}

    def fake_run_database_health_check(**kwargs):
        return SimpleNamespace(
            status="error",
            error_count=1,
            warning_count=0,
            info_count=0,
            summary_md=tmp_path / "health.md",
        )

    def fake_run_factor_effectiveness_report(**kwargs):
        nonlocal called_factor
        called_factor = True

    monkeypatch.setattr(strategy_research_cli, "load_config", fake_load_config)
    monkeypatch.setattr(gates_cli, "run_database_health_check", fake_run_database_health_check)
    monkeypatch.setattr(strategy_research_cli, "run_factor_effectiveness_report", fake_run_factor_effectiveness_report)
    args = SimpleNamespace(cmd="factor-effectiveness", config=str(tmp_path / "config.yaml"), output_dir=None)

    exit_code = strategy_research_cli.handle_strategy_research_command(
        args,
        parser=argparse.ArgumentParser(),
        console=_silent_console(),
    )

    assert exit_code == 2
    assert called_factor is False


def test_cli_main_delegates_strategy_research_commands(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, bool]] = []

    def fake_handle_strategy_research_command(args, *, parser):
        calls.append((args.cmd, parser is not None))
        return 0

    monkeypatch.setattr(cli, "handle_strategy_research_command", fake_handle_strategy_research_command)
    monkeypatch.setattr(
        "sys.argv",
        [
            "phase0.cli",
            "strategy-admission",
            "--config",
            str(tmp_path / "config.yaml"),
        ],
    )

    assert cli.main() == 0
    assert calls == [("strategy-admission", True)]


def test_cli_keeps_strategy_research_compatibility_imports() -> None:
    assert cli._print_walk_forward_trace is strategy_research_cli._print_walk_forward_trace
    assert cli._run_db_health_gate is strategy_research_cli._run_db_health_gate
