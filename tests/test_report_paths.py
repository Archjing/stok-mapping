from datetime import datetime
from pathlib import Path

from phase0.report_paths import create_report_run, latest_dir, scratch_dir


def test_create_report_run_uses_date_command_and_scope(tmp_path: Path) -> None:
    run = create_report_run(
        root=tmp_path,
        command="strategy-admission",
        scope="baseline admission all v1",
        now=datetime(2026, 6, 23, 10, 30, 12),
    )

    assert run.run_id == "20260623_103012__strategy_admission__baseline_admission_all_v1"
    assert run.run_dir == tmp_path / "reports" / "runs" / "2026-06-23" / run.run_id


def test_artifact_uses_family_artifact_extension(tmp_path: Path) -> None:
    run = create_report_run(
        root=tmp_path,
        command="strategy-admission",
        scope="baseline_admission_all_v1",
        now=datetime(2026, 6, 23, 10, 30, 12),
    )

    assert run.artifact("strategy-admission", "window matrix", "csv") == (
        run.run_dir / "strategy_admission__window_matrix.csv"
    )


def test_latest_and_scratch_directories_are_separate(tmp_path: Path) -> None:
    assert latest_dir(root=tmp_path, channel="daily brief") == tmp_path / "reports" / "latest" / "daily_brief"
    assert scratch_dir(root=tmp_path, purpose="strategy admission trace", now=datetime(2026, 6, 23, 1, 2, 3)) == (
        tmp_path / "reports" / "scratch" / "2026-06-23" / "strategy_admission_trace"
    )


def test_latest_watchlist_entry_path(tmp_path: Path) -> None:
    assert latest_dir(root=tmp_path, channel="watchlist") / "index.html" == (
        tmp_path / "reports" / "latest" / "watchlist" / "index.html"
    )


def test_standard_report_artifact_names_for_core_commands(tmp_path: Path) -> None:
    admission = create_report_run(
        root=tmp_path,
        command="strategy-admission",
        scope="baseline_admission_all_v1",
        now=datetime(2026, 6, 23, 10, 30, 12),
    )
    health = create_report_run(
        root=tmp_path,
        command="db-health",
        scope="cn",
        now=datetime(2026, 6, 23, 10, 30, 12),
    )
    factors = create_report_run(
        root=tmp_path,
        command="factor-effectiveness",
        scope="qfq_asof",
        now=datetime(2026, 6, 23, 10, 30, 12),
    )

    assert admission.artifact("strategy_admission", "report", "md").name == "strategy_admission__report.md"
    assert admission.artifact("strategy_admission", "governance", "md").name == "strategy_admission__governance.md"
    assert health.artifact("database_health", "summary", "csv").name == "database_health__summary.csv"
    assert health.artifact("database_health", "report", "md").name == "database_health__report.md"
    assert factors.artifact("factor_effectiveness", "summary", "csv").name == "factor_effectiveness__summary.csv"
    assert factors.artifact("factor_effectiveness", "report", "md").name == "factor_effectiveness__report.md"
