from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import quant.cli as cli
import quant.cli_commands.data_governance as data_governance_cli


def test_data_governance_command_registration_preserves_args() -> None:
    parser = cli.argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd")
    data_governance_cli.register_data_governance_commands(subparsers)

    adjustment_args = parser.parse_args(["adjustment-audit", "--output-csv", "out.csv", "--output-md", "out.md"])
    db_args = parser.parse_args(["db-health", "--scope", "scheduler", "--fail-on", "warning"])
    capacity_args = parser.parse_args(["db-capacity", "--quick-check", "--row-counts", "--output-dir", "capacity"])
    index_args = parser.parse_args(
        [
            "index-asof-audit",
            "--benchmark-symbol",
            "SH.000300",
            "--candidate-folds",
            "folds.csv",
            "--output-dir",
            "audit",
        ]
    )

    assert adjustment_args.cmd == "adjustment-audit"
    assert adjustment_args.config == "config.yaml"
    assert adjustment_args.output_csv == "out.csv"
    assert adjustment_args.output_md == "out.md"
    assert db_args.cmd == "db-health"
    assert db_args.scope == "scheduler"
    assert db_args.fail_on == "warning"
    assert capacity_args.cmd == "db-capacity"
    assert capacity_args.quick_check is True
    assert capacity_args.row_counts is True
    assert capacity_args.output_dir == "capacity"
    assert index_args.cmd == "index-asof-audit"
    assert index_args.benchmark_symbol == "SH.000300"
    assert index_args.candidate_folds == "folds.csv"
    assert index_args.output_dir == "audit"


def test_adjustment_audit_handler_forwards_paths(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []
    lines: list[str] = []

    def fake_load_config(path):
        return {"local_history": {}}

    def fake_run_adjustment_audit(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            can_build_qfq_asof=True,
            verdict="pass",
            csv_path=tmp_path / "adjustment.csv",
            md_path=tmp_path / "adjustment.md",
            warnings=["sample warning"],
        )

    monkeypatch.setattr(data_governance_cli, "load_config", fake_load_config)
    monkeypatch.setattr(data_governance_cli, "run_adjustment_audit", fake_run_adjustment_audit)
    args = SimpleNamespace(
        cmd="adjustment-audit",
        config=str(tmp_path / "config.yaml"),
        output_csv=str(tmp_path / "custom.csv"),
        output_md=str(tmp_path / "custom.md"),
    )

    exit_code = data_governance_cli.handle_data_governance_command(
        args,
        parser=cli.argparse.ArgumentParser(),
        console=SimpleNamespace(print=lambda text: lines.append(str(text))),
    )

    assert exit_code == 0
    assert calls == [
        {
            "config": {"local_history": {}},
            "root": tmp_path,
            "output_csv": (tmp_path / "custom.csv").resolve(),
            "output_md": (tmp_path / "custom.md").resolve(),
        }
    ]
    assert any("Adjustment audit verdict" in line for line in lines)
    assert any("sample warning" in line for line in lines)


def test_index_asof_handler_forwards_audit_args(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_load_config(path):
        return {"benchmark_symbol": "SH.000300"}

    def fake_run_index_asof_audit(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            benchmark_symbol="SH.000300",
            db_path=tmp_path / "history.sqlite",
            constituent_status="available",
            weight_status="available",
            fold_rows=2,
            capability_csv_path=tmp_path / "capability.csv",
            fold_coverage_csv_path=tmp_path / "coverage.csv",
            report_md_path=tmp_path / "index_asof.md",
            run_log_md_path=tmp_path / "run_log.md",
        )

    monkeypatch.setattr(data_governance_cli, "load_config", fake_load_config)
    monkeypatch.setattr(data_governance_cli, "run_index_asof_audit", fake_run_index_asof_audit)
    monkeypatch.setattr(data_governance_cli.os, "sys", SimpleNamespace(argv=["quant.cli", "index-asof-audit"]))
    args = SimpleNamespace(
        cmd="index-asof-audit",
        config=str(tmp_path / "config.yaml"),
        benchmark_symbol="SH.000300",
        candidate_folds=str(tmp_path / "folds.csv"),
        output_dir=str(tmp_path / "audit"),
    )

    exit_code = data_governance_cli.handle_data_governance_command(
        args,
        parser=cli.argparse.ArgumentParser(),
        console=SimpleNamespace(print=lambda text: None),
    )

    assert exit_code == 0
    assert calls == [
        {
            "config": {"benchmark_symbol": "SH.000300"},
            "root": tmp_path,
            "config_path": (tmp_path / "config.yaml").resolve(),
            "benchmark_symbol": "SH.000300",
            "candidate_folds_path": (tmp_path / "folds.csv").resolve(),
            "output_dir": (tmp_path / "audit").resolve(),
            "command": "quant.cli index-asof-audit",
        }
    ]


def test_db_health_handler_forwards_args_and_fail_on(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_load_config(path):
        return {"local_history": {}}

    def fake_run_database_health_check(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            status="warning",
            summary_rows=1,
            error_count=0,
            warning_count=1,
            info_count=0,
            summary_csv=tmp_path / "summary.csv",
            findings_csv=tmp_path / "findings.csv",
            summary_md=tmp_path / "report.md",
        )

    monkeypatch.setattr(data_governance_cli, "load_config", fake_load_config)
    monkeypatch.setattr(data_governance_cli, "run_database_health_check", fake_run_database_health_check)
    base_args = {
        "cmd": "db-health",
        "config": str(tmp_path / "config.yaml"),
        "scope": "scheduler",
        "as_of": "2026-06-26",
        "output_dir": str(tmp_path / "health"),
    }

    never_exit = data_governance_cli.handle_data_governance_command(
        SimpleNamespace(**base_args, fail_on="never"),
        parser=cli.argparse.ArgumentParser(),
        console=SimpleNamespace(print=lambda text: None),
    )
    warning_exit = data_governance_cli.handle_data_governance_command(
        SimpleNamespace(**base_args, fail_on="warning"),
        parser=cli.argparse.ArgumentParser(),
        console=SimpleNamespace(print=lambda text: None),
    )
    error_exit = data_governance_cli.handle_data_governance_command(
        SimpleNamespace(**base_args, fail_on="error"),
        parser=cli.argparse.ArgumentParser(),
        console=SimpleNamespace(print=lambda text: None),
    )

    assert never_exit == 0
    assert warning_exit == 2
    assert error_exit == 0
    assert calls[0] == {
        "config": {"local_history": {}},
        "root": tmp_path,
        "scope": "scheduler",
        "as_of_date": "2026-06-26",
        "output_dir": (tmp_path / "health").resolve(),
    }


def test_cli_main_delegates_data_governance_commands(monkeypatch, tmp_path: Path) -> None:
    calls = []

    def fake_handle_data_governance_command(args, *, parser):
        calls.append((args.cmd, Path(args.config), parser is not None))
        return 0

    monkeypatch.setattr(cli, "handle_data_governance_command", fake_handle_data_governance_command)
    monkeypatch.setattr("sys.argv", ["quant.cli", "db-health", "--config", str(tmp_path / "config.yaml")])

    assert cli.main() == 0
    assert calls == [("db-health", tmp_path / "config.yaml", True)]


def test_db_capacity_handler_forwards_read_only_audit_args(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []
    lines: list[str] = []

    def fake_run_sqlite_capacity_audit(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            status="warning",
            database_count=3,
            backup_count=2,
            total_primary_bytes=1024,
            total_backup_bytes=2048,
            warning_count=1,
            error_count=0,
            json_path=tmp_path / "capacity.json",
            markdown_path=tmp_path / "capacity.md",
        )

    monkeypatch.setattr(data_governance_cli, "run_sqlite_capacity_audit", fake_run_sqlite_capacity_audit)
    args = SimpleNamespace(
        cmd="db-capacity",
        config=str(tmp_path / "config.yaml"),
        output_dir=str(tmp_path / "capacity"),
        quick_check=True,
        row_counts=True,
    )

    exit_code = data_governance_cli.handle_data_governance_command(
        args,
        parser=cli.argparse.ArgumentParser(),
        console=SimpleNamespace(print=lambda text: lines.append(str(text))),
    )

    assert exit_code == 0
    assert calls == [
        {
            "root": tmp_path,
            "output_dir": (tmp_path / "capacity").resolve(),
            "quick_check": True,
            "row_counts": True,
        }
    ]
    assert any("SQLite capacity audit" in line for line in lines)
    assert any("capacity.json" in line for line in lines)
