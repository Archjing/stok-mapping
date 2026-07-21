from pathlib import Path
from types import SimpleNamespace

import yaml

import phase0.cli as cli
import phase0.cli_commands.maintenance as maintenance_cli
import phase0.cli_commands.system as system_cli
from phase0.cli import summarize_system_maintenance_status
from phase0.cli_commands.system import summarize_system_maintenance_status as new_summarize_system_maintenance_status
from phase0.maintenance_orchestrator import (
    MaintenanceDecision,
    MaintenanceShardStatusRow,
    MaintenanceStatusResult,
    MaintenanceStatusRow,
    _default_registry,
    _run_health_gate,
    maintenance_status,
)


def test_daily_brief_uses_cn_health_scope_by_default() -> None:
    specs = _default_registry(Path("config.yaml"))
    daily_brief = next(item for item in specs if item.name == "daily_brief")
    assert daily_brief.health_scope == "cn"
    assert daily_brief.health_fail_on == "warning"


def test_update_tasks_default_health_gate_blocks_only_on_error() -> None:
    specs = _default_registry(Path("config.yaml"))
    by_name = {item.name: item for item in specs}

    assert by_name["financial_factors"].health_fail_on == "error"
    assert by_name["hk_market_history"].health_fail_on == "error"
    assert by_name["a_share_history"].health_fail_on == "error"
    assert by_name["account_bill_confirm"].health_fail_on == "error"
    assert by_name["us_market_history"].health_fail_on == "error"


def test_daily_brief_runs_all_enabled_simulated_accounts() -> None:
    specs = _default_registry(Path("config.yaml"))
    daily_brief = next(item for item in specs if item.name == "daily_brief")

    assert daily_brief.command == [
        ".venv/bin/python",
        "-m",
        "phase0.cli",
        "brief",
        "watchlist",
        "--config",
        "config.yaml",
        "--all-accounts",
    ]


def test_gov_policy_fetch_runs_with_prefetch_probe_before_daily_brief(monkeypatch) -> None:
    for name in [
        "GOV_POLICY_TIME",
        "GOV_POLICY_ORG",
        "GOV_POLICY_PTYPE",
        "GOV_POLICY_KEYWORD",
        "GOV_POLICY_LIMIT",
        "GOV_POLICY_MIN_ROWS",
        "GOV_POLICY_TIMEOUT",
        "GOV_POLICY_DATABASE_PATH",
        "GOV_POLICY_RAW_ARCHIVE_DIR",
        "GOV_POLICY_REFERENCE_DIR",
        "GOV_POLICY_PROBE_OUTPUT_JSON",
        "GOV_POLICY_PROBE_MIN_ROWS",
        "GOV_POLICY_PROBE_MIN_TOPICS",
        "GOV_POLICY_PROBE_MIN_DEPARTMENTS",
        "GOV_POLICY_PROBE_MIN_CONTENT_CHARS",
    ]:
        monkeypatch.delenv(name, raising=False)

    specs = _default_registry(Path("config.yaml"))
    by_name = {item.name: item for item in specs}
    names = [item.name for item in specs]
    gov_policy = by_name["gov_policy_fetch"]

    assert names.index("gov_policy_fetch") < names.index("daily_brief")
    assert gov_policy.schedule_value == "06:50"
    assert gov_policy.log_path == "logs/gov_policy_update.log"
    assert gov_policy.health_scope == "scheduler"
    assert gov_policy.health_fail_on == "warning"
    assert gov_policy.weekdays_only is False
    assert gov_policy.market_calendar == "all"
    assert gov_policy.retry_window_minutes == 90
    assert gov_policy.retry_interval_minutes == 15
    assert gov_policy.max_retries == 4
    assert gov_policy.command == [
        ".venv/bin/python",
        "-m",
        "phase0.cli",
        "ai-corpus",
        "fetch",
        "--config",
        "config.yaml",
        "--provider",
        "gov-policy",
        "--org",
        "国务院",
        "--ptype",
        "科技",
        "--keyword",
        "人工智能",
        "--limit",
        "20",
        "--min-rows",
        "1",
        "--timeout",
        "20",
        "--database-path",
        "data/ai_corpus/ai_corpus.sqlite",
        "--raw-archive-dir",
        "data/raw_data/ai_corpus/gov_policy",
        "--reference-dir",
        "data/reference/ai_corpus/gov_policy",
        "--refresh-reference",
        "--probe-before-fetch",
        "--probe-output-json",
        "reports/phase0/ai_corpus/probes/gov_policy_probe_%Y%m%dT%H%M%S.json",
        "--min-probe-rows",
        "1",
        "--min-probe-topics",
        "1",
        "--min-probe-departments",
        "0",
        "--min-probe-content-chars",
        "200",
    ]


def test_account_bill_confirm_runs_after_a_share_history() -> None:
    specs = _default_registry(Path("config.yaml"))
    by_name = {item.name: item for item in specs}
    names = [item.name for item in specs]
    account_bill_confirm = by_name["account_bill_confirm"]

    assert names.index("a_share_history") < names.index("account_bill_confirm") < names.index("us_market_history")
    assert account_bill_confirm.schedule_value == "16:45"
    assert account_bill_confirm.log_path == "logs/account_bill_confirm.log"
    assert account_bill_confirm.health_scope == "cn"
    assert account_bill_confirm.health_fail_on == "error"
    assert account_bill_confirm.market_calendar == "cn"
    assert account_bill_confirm.command == [
        ".venv/bin/python",
        "-m",
        "phase0.cli",
        "brief",
        "confirm-account-bills",
        "--config",
        "config.yaml",
        "--all-accounts",
    ]


def test_cctv_news_runs_daily_after_broadcast_with_retry() -> None:
    specs = _default_registry(Path("config.yaml"))
    by_name = {item.name: item for item in specs}
    names = [item.name for item in specs]
    cctv_news = by_name["cctv_news"]

    assert names.index("cninfo_risk_events") < names.index("cctv_news")
    assert cctv_news.schedule_value == "20:45"
    assert cctv_news.log_path == "logs/cctv_news_update.log"
    assert cctv_news.health_scope == "scheduler"
    assert cctv_news.health_fail_on == "warning"
    assert cctv_news.weekdays_only is False
    assert cctv_news.market_calendar == "all"
    assert cctv_news.retry_window_minutes == 180
    assert cctv_news.retry_interval_minutes == 30
    assert cctv_news.max_retries == 6
    assert cctv_news.command == [
        ".venv/bin/python",
        "-m",
        "phase0.cli",
        "ai-corpus",
        "fetch",
        "--config",
        "config.yaml",
        "--provider",
        "cctv-news",
        "--limit",
        "100",
        "--min-rows",
        "1",
    ]


def test_cninfo_risk_events_runs_daily_before_cctv_with_zero_row_tolerance(monkeypatch) -> None:
    for name in [
        "CNINFO_RISK_EVENTS_TIME",
        "CNINFO_RISK_EVENTS_EVENT_TYPE",
        "CNINFO_RISK_EVENTS_LIMIT",
        "CNINFO_RISK_EVENTS_MIN_ROWS",
        "CNINFO_RISK_EVENTS_DATABASE_PATH",
        "CNINFO_RISK_EVENTS_RAW_ARCHIVE_DIR",
    ]:
        monkeypatch.delenv(name, raising=False)

    specs = _default_registry(Path("config.yaml"))
    by_name = {item.name: item for item in specs}
    names = [item.name for item in specs]
    cninfo = by_name["cninfo_risk_events"]

    assert names.index("us_market_history") < names.index("cninfo_risk_events") < names.index("cctv_news")
    assert cninfo.schedule_value == "20:20"
    assert cninfo.log_path == "logs/cninfo_risk_events_update.log"
    assert cninfo.health_scope == "scheduler"
    assert cninfo.health_fail_on == "warning"
    assert cninfo.weekdays_only is False
    assert cninfo.market_calendar == "all"
    assert cninfo.retry_window_minutes == 120
    assert cninfo.retry_interval_minutes == 30
    assert cninfo.max_retries == 4
    assert cninfo.command == [
        ".venv/bin/python",
        "-m",
        "phase0.cli",
        "ai-corpus",
        "fetch",
        "--config",
        "config.yaml",
        "--provider",
        "cninfo",
        "--event-type",
        "risk_events",
        "--limit",
        "200",
        "--min-rows",
        "0",
        "--database-path",
        "data/ai_corpus/ai_corpus.sqlite",
        "--raw-archive-dir",
        "data/raw_data/ai_corpus/cninfo",
    ]


def test_manual_history_update_includes_bfq_execution_prices() -> None:
    config = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))

    assert config["phase0"]["local_history"]["execution_adjust_type"] == "bfq"
    assert "bfq" in config["phase0"]["manual_history_update"]["adjust_types"]


def test_health_gate_uses_config_option_not_last_command_arg(monkeypatch) -> None:
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return SimpleNamespace(returncode=0, stdout="ok")

    monkeypatch.setattr("phase0.maintenance_orchestrator.subprocess.run", fake_run)

    decision = MaintenanceDecision(
        task_name="daily_brief",
        decision="will_run",
        reason="scheduled_run",
        scheduled_time="07:20",
        command=[
            ".venv/bin/python",
            "-m",
            "phase0.cli",
            "brief",
            "watchlist",
            "--config",
            "config.yaml",
            "--all-accounts",
        ],
        log_path=Path("logs/daily_brief_pipeline.log"),
        stamp_path=Path("logs/scheduler/daily_brief.last"),
        lock_path=Path("logs/scheduler/locks/daily_brief.lock"),
        health_scope="cn",
        health_fail_on="warning",
        state_path=Path("logs/scheduler/daily_brief.state"),
        retry_window_minutes=20,
        retry_interval_minutes=5,
        max_retries=3,
    )

    ok, output = _run_health_gate(decision)

    assert ok is True
    assert output == "ok"
    assert captured["command"] == [
        ".venv/bin/python",
        "-m",
        "phase0.cli",
        "db-health",
        "--config",
        "config.yaml",
        "--scope",
        "cn",
        "--fail-on",
        "warning",
    ]


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
