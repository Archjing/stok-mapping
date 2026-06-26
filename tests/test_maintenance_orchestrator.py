from pathlib import Path
from types import SimpleNamespace

import phase0.cli as cli
import phase0.cli_commands.maintenance as maintenance_cli
import phase0.cli_commands.system as system_cli
from phase0.cli import summarize_system_maintenance_status
from phase0.cli_commands.system import summarize_system_maintenance_status as new_summarize_system_maintenance_status
from phase0.maintenance_orchestrator import (
    MaintenanceShardStatusRow,
    MaintenanceStatusResult,
    MaintenanceStatusRow,
    _default_registry,
    maintenance_status,
)


def test_daily_brief_uses_cn_health_scope_by_default() -> None:
    specs = _default_registry(Path("config.yaml"))
    daily_brief = next(item for item in specs if item.name == "daily_brief")
    assert daily_brief.health_scope == "cn"


def test_system_status_summary_counts_maintenance_rows_and_running_shards() -> None:
    result = MaintenanceStatusResult(
        state_db=Path("data/maintenance/maintenance.sqlite"),
        generated_at="2026-06-23T08:00:00",
        rows=[
            MaintenanceStatusRow(
                task_name="daily_brief",
                enabled=True,
                schedule_type="time",
                schedule_value="07:20",
                last_decision="will_run",
                last_reason="scheduled_time",
                last_tick_at="2026-06-23T07:20:00",
                last_success_at="2026-06-23T07:21:00",
                last_run_status="succeeded",
                last_error="",
                retry_count=0,
                log_path=Path("logs/daily_brief_pipeline.log"),
                state_path=Path("logs/scheduler/daily_brief.state"),
            ),
            MaintenanceStatusRow(
                task_name="hk_market_history",
                enabled=True,
                schedule_type="time",
                schedule_value="16:20",
                last_decision="skipped",
                last_reason="not_in_window",
                last_tick_at="2026-06-23T08:00:00",
                last_success_at="",
                last_run_status="",
                last_error="",
                retry_count=0,
                log_path=Path("logs/hk_market_history_update.log"),
                state_path=Path("logs/scheduler/hk_market_history.state"),
            ),
        ],
        shards=[
            MaintenanceShardStatusRow(
                run_id=1,
                task_name="tushare_financial_backfill",
                shard_index=0,
                shard_count=3,
                status="running",
                pid=123,
                started_at="2026-06-23T07:00:00",
                finished_at="",
                exit_code=None,
                log_path=Path("logs/backfill.log"),
            ),
            MaintenanceShardStatusRow(
                run_id=1,
                task_name="tushare_financial_backfill",
                shard_index=1,
                shard_count=3,
                status="succeeded",
                pid=None,
                started_at="2026-06-23T07:00:00",
                finished_at="2026-06-23T07:30:00",
                exit_code=0,
                log_path=Path("logs/backfill.log"),
            ),
        ],
    )

    summary = summarize_system_maintenance_status(result)

    assert summary == {
        "task_count": 2,
        "last_run_status_counts": {"not_available": 1, "succeeded": 1},
        "last_decision_counts": {"skipped": 1, "will_run": 1},
        "running_shard_count": 1,
        "shard_status_counts": {"running": 1, "succeeded": 1},
    }
    assert new_summarize_system_maintenance_status(result) == summary


def test_system_status_cli_reads_maintenance_status_without_refresh(monkeypatch, capsys) -> None:
    calls = []

    def fake_maintenance_status(config_path, **kwargs):
        calls.append((config_path, kwargs))
        return MaintenanceStatusResult(
            state_db=Path("data/maintenance/maintenance.sqlite"),
            generated_at="2026-06-23T08:00:00",
            rows=[],
            shards=[],
        )

    monkeypatch.setattr(system_cli, "maintenance_status", fake_maintenance_status)
    monkeypatch.setattr(system_cli, "Console", lambda: SimpleNamespace(print=print))
    monkeypatch.setattr(
        cli.argparse.ArgumentParser,
        "exit",
        lambda self, status=0, message=None: (_ for _ in ()).throw(SystemExit(status)),
    )
    monkeypatch.setattr("sys.argv", ["phase0.cli", "system", "status", "--config", "config.yaml"])

    try:
        exit_code = cli.main()
    except SystemExit as exc:
        exit_code = int(exc.code or 0)

    captured = capsys.readouterr()

    assert exit_code == 0
    assert calls == [(Path("config.yaml").resolve(), {"refresh_state": False, "read_only": True})]
    assert "System status started" in captured.out
    assert "Maintenance running shards: 0" in captured.out


def test_maintenance_status_read_only_missing_db_does_not_create_db(tmp_path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "phase0:\n"
        "  maintenance_orchestrator:\n"
        "    state_db: data/maintenance/missing.sqlite\n",
        encoding="utf-8",
    )

    result = maintenance_status(config_path, refresh_state=False, read_only=True)

    expected_specs = _default_registry(config_path)
    expected_db = tmp_path / "data" / "maintenance" / "missing.sqlite"

    assert result.state_db == expected_db
    assert not expected_db.exists()
    assert [row.task_name for row in result.rows] == [spec.name for spec in expected_specs]
    assert all(row.last_tick_at == "" for row in result.rows)
    assert all(row.last_success_at == "" for row in result.rows)
    assert result.shards == []


def test_maintain_status_cli_keeps_default_refresh_behavior(monkeypatch, capsys) -> None:
    calls = []

    def fake_maintenance_status(config_path, **kwargs):
        calls.append((config_path, kwargs))
        return MaintenanceStatusResult(
            state_db=Path("data/maintenance/maintenance.sqlite"),
            generated_at="2026-06-23T08:00:00",
            rows=[],
            shards=[],
        )

    monkeypatch.setattr(maintenance_cli, "maintenance_status", fake_maintenance_status)
    monkeypatch.setattr(maintenance_cli, "Console", lambda: SimpleNamespace(print=print))
    monkeypatch.setattr(
        cli.argparse.ArgumentParser,
        "exit",
        lambda self, status=0, message=None: (_ for _ in ()).throw(SystemExit(status)),
    )
    monkeypatch.setattr("sys.argv", ["phase0.cli", "maintain", "status", "--config", "config.yaml"])

    try:
        exit_code = cli.main()
    except SystemExit as exc:
        exit_code = int(exc.code or 0)

    captured = capsys.readouterr()

    assert exit_code == 0
    assert calls == [
        (
            Path("config.yaml").resolve(),
            {"output_md": None, "write_report": False},
        )
    ]
    assert "Maintenance status started" in captured.out


def test_maintain_tick_cli_forwards_dry_run_without_starting_tasks(monkeypatch, capsys) -> None:
    calls = []

    def fake_maintenance_tick(config_path, **kwargs):
        calls.append((config_path, kwargs))
        return SimpleNamespace(
            state_db=Path("data/maintenance/maintenance.sqlite"),
            as_of="2026-06-23 08:00",
            dry_run=True,
            executed_runs=0,
            decisions=[
                SimpleNamespace(
                    task_name="daily_brief",
                    decision="skipped",
                    scheduled_time="07:20",
                    reason="not_in_window",
                )
            ],
        )

    monkeypatch.setattr(maintenance_cli, "maintenance_tick", fake_maintenance_tick)
    monkeypatch.setattr(maintenance_cli, "Console", lambda: SimpleNamespace(print=print))
    monkeypatch.setattr(
        cli.argparse.ArgumentParser,
        "exit",
        lambda self, status=0, message=None: (_ for _ in ()).throw(SystemExit(status)),
    )
    monkeypatch.setattr(
        "sys.argv",
        ["phase0.cli", "maintain", "tick", "--config", "config.yaml", "--dry-run", "--as-of", "2026-06-23 08:00"],
    )

    try:
        exit_code = cli.main()
    except SystemExit as exc:
        exit_code = int(exc.code or 0)

    captured = capsys.readouterr()

    assert exit_code == 0
    assert calls == [
        (
            Path("config.yaml").resolve(),
            {"as_of": "2026-06-23 08:00", "dry_run": True},
        )
    ]
    assert "Maintenance tick started" in captured.out
    assert "Dry run: True" in captured.out
