import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import quant.cli as cli
import quant.cli_commands.dashboard as dashboard_cli
from quant.reporting.registry import (
    classify_legacy_artifact,
    classify_legacy_brief_artifact,
    scan_report_artifacts,
    write_report_manifest,
)


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_scan_report_artifacts_detects_supported_report_types_with_relative_paths(tmp_path: Path) -> None:
    _write(tmp_path / "reports" / "strategy_admission" / "strategy_admission_report.md")
    _write(tmp_path / "reports" / "2026-06-23" / "phase0_watchlist_report_2026-06-23.html")
    _write(tmp_path / "reports" / "database_health" / "database_health_summary.csv")
    _write(tmp_path / "reports" / "database_health" / "ignore.txt")
    _write(tmp_path / "reports" / "report_dashboard" / "ignored.md")

    artifacts = scan_report_artifacts(tmp_path)

    assert {artifact.type for artifact in artifacts} == {"csv", "html", "markdown"}
    assert {artifact.path for artifact in artifacts} == {
        "reports/2026-06-23/phase0_watchlist_report_2026-06-23.html",
        "reports/database_health/database_health_summary.csv",
        "reports/strategy_admission/strategy_admission_report.md",
    }
    assert all(not artifact.path.startswith("/") for artifact in artifacts)
    assert all(Path(artifact.path).as_posix() == artifact.path for artifact in artifacts)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (
            "reports/runs/2026-06-23/20260623_180318__db_health__scheduler/database_health__summary.csv",
            "standard_run",
        ),
        ("reports/phase0_walk_forward_report.md", "legacy_root_flat"),
        ("reports/database_health/database_health_report.md", "legacy_module_dir"),
        ("reports/2026-06-23/phase0_watchlist_report_2026-06-23.html", "legacy_date_dir"),
        ("reports/20260623/phase0_watchlist_report_20260623.html", "legacy_date_dir"),
        ("reports/strategy_admission/strategy_admission_report.md", "legacy_experiment_dir"),
        ("reports/strategy_admission_sleeve_composite_v1_20260623/strategy_admission_report.md", "legacy_experiment_dir"),
        ("reports/candidate_experiments_v1/report.md", "legacy_experiment_dir"),
        ("reports/watchlist_today/index.html", "legacy_latest_mirror"),
        ("reports/current/index.html", "legacy_latest_mirror"),
        ("reports/tmp_validation/pit_preview.html", "legacy_scratch"),
        ("reports/tmp/pit_preview.html", "legacy_scratch"),
    ],
)
def test_classify_legacy_artifact_categories(path: str, expected: str) -> None:
    assert classify_legacy_artifact(Path(path)) == expected


def test_write_report_manifest_has_runs_and_artifacts_shape(tmp_path: Path) -> None:
    _write(tmp_path / "reports" / "strategy_admission" / "strategy_admission_report.md")
    _write(tmp_path / "reports" / "20260623" / "phase0_watchlist_report_20260623.html")

    manifest_path = write_report_manifest(root=tmp_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest_path == tmp_path / "reports" / "runs" / "report_dashboard" / "manifest.json"
    assert payload["schema_version"] == 1
    assert payload["project_root"] == "."
    assert payload["generated_at"]
    assert sorted(payload) == ["artifacts", "generated_at", "project_root", "runs", "schema_version"]
    assert len(payload["runs"]) == 2
    assert len(payload["artifacts"]) == 2
    assert {artifact["path"] for artifact in payload["artifacts"]} == {
        "reports/20260623/phase0_watchlist_report_20260623.html",
        "reports/strategy_admission/strategy_admission_report.md",
    }
    assert all(not artifact["path"].startswith("/") for artifact in payload["artifacts"])
    assert {run["legacy_category"] for run in payload["runs"]} == {"legacy_date_dir", "legacy_experiment_dir"}


def test_standard_run_manifest_uses_run_directory_id_and_module(tmp_path: Path) -> None:
    _write(
        tmp_path
        / "reports"
        / "runs"
        / "2026-06-23"
        / "20260623_180318__db_health__scheduler"
        / "database_health__summary.csv"
    )

    artifacts = scan_report_artifacts(tmp_path)

    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert artifact.legacy_category == "standard_run"
    assert artifact.run_id == "20260623_180318__db_health__scheduler"
    assert artifact.module == "db_health"


def test_legacy_date_dir_artifacts_do_not_collapse_across_modules_or_files(tmp_path: Path) -> None:
    _write(tmp_path / "reports" / "2026-06-23" / "brief" / "index.html")
    _write(tmp_path / "reports" / "2026-06-23" / "database_health" / "database_health_summary.csv")
    _write(tmp_path / "reports" / "2026-06-23" / "phase0_watchlist_report_2026-06-23.html")
    _write(tmp_path / "reports" / "2026-06-23" / "phase0_premarket_watchlist_2026-06-23.csv")

    manifest_path = write_report_manifest(root=tmp_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    runs_by_id = {run["run_id"]: run for run in payload["runs"]}
    artifacts_by_path = {artifact["path"]: artifact for artifact in payload["artifacts"]}

    assert set(runs_by_id) == {
        "legacy_date_dir__2026-06-23__brief",
        "legacy_date_dir__2026-06-23__database_health",
        "legacy_date_dir__2026-06-23__phase0_premarket_watchlist_2026-06-23",
        "legacy_date_dir__2026-06-23__phase0_watchlist_report_2026-06-23",
    }
    assert artifacts_by_path["reports/2026-06-23/brief/index.html"]["run_id"] == "legacy_date_dir__2026-06-23__brief"
    assert (
        artifacts_by_path["reports/2026-06-23/database_health/database_health_summary.csv"]["run_id"]
        == "legacy_date_dir__2026-06-23__database_health"
    )
    assert (
        artifacts_by_path["reports/2026-06-23/phase0_watchlist_report_2026-06-23.html"]["run_id"]
        == "legacy_date_dir__2026-06-23__phase0_watchlist_report_2026-06-23"
    )
    assert (
        artifacts_by_path["reports/2026-06-23/phase0_premarket_watchlist_2026-06-23.csv"]["run_id"]
        == "legacy_date_dir__2026-06-23__phase0_premarket_watchlist_2026-06-23"
    )
    assert runs_by_id["legacy_date_dir__2026-06-23__brief"]["artifact_ids"] == [
        artifacts_by_path["reports/2026-06-23/brief/index.html"]["artifact_id"]
    ]
    assert runs_by_id["legacy_date_dir__2026-06-23__database_health"]["artifact_ids"] == [
        artifacts_by_path["reports/2026-06-23/database_health/database_health_summary.csv"]["artifact_id"]
    ]
    assert all(run["legacy_category"] == "legacy_date_dir" for run in payload["runs"])


def test_dashboard_scan_cli_writes_manifest_and_prints_counts(monkeypatch, capsys, tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("quant: {}\n", encoding="utf-8")
    calls = []

    def fake_write_report_manifest(*, root, manifest_path=None, reports_dir=None):
        calls.append((root, manifest_path, reports_dir))
        return root / "reports" / "runs" / "report_dashboard" / "manifest.json"

    monkeypatch.setattr(dashboard_cli, "write_report_manifest", fake_write_report_manifest)
    monkeypatch.setattr(
        dashboard_cli,
        "scan_report_artifacts",
        lambda root: [
            SimpleNamespace(run_id="run-a", type="markdown", legacy_category="legacy_module_dir"),
            SimpleNamespace(run_id="run-a", type="csv", legacy_category="legacy_module_dir"),
            SimpleNamespace(run_id="run-b", type="html", legacy_category="legacy_date_dir"),
        ],
    )
    monkeypatch.setattr(dashboard_cli, "Console", lambda: SimpleNamespace(print=print))
    monkeypatch.setattr("sys.argv", ["quant.cli", "dashboard", "scan", "--config", str(config_path)])

    exit_code = cli.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert calls == [(tmp_path, None, None)]
    assert "Report dashboard scan started" in captured.out
    assert "Manifest:" in captured.out
    assert "Runs: 2" in captured.out
    assert "Artifacts: 3" in captured.out
    assert "csv=1, html=1, markdown=1" in captured.out
    assert "Categories: legacy_date_dir=1, legacy_module_dir=2" in captured.out


def test_dashboard_scan_handler_writes_manifest_and_prints_counts(monkeypatch, capsys, tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("quant: {}\n", encoding="utf-8")
    calls = []

    def fake_write_report_manifest(*, root, manifest_path=None, reports_dir=None):
        calls.append((root, manifest_path, reports_dir))
        return root / "custom_manifest.json"

    monkeypatch.setattr(dashboard_cli, "write_report_manifest", fake_write_report_manifest)
    monkeypatch.setattr(
        dashboard_cli,
        "scan_report_artifacts",
        lambda root: [
            SimpleNamespace(run_id="run-a", type="markdown", legacy_category="legacy_module_dir"),
            SimpleNamespace(run_id="run-b", type="csv", legacy_category="legacy_module_dir"),
        ],
    )
    monkeypatch.setattr(dashboard_cli, "Console", lambda: SimpleNamespace(print=print))
    parser = cli.argparse.ArgumentParser()
    args = cli.argparse.Namespace(
        dashboard_cmd="scan",
        config=str(config_path),
        manifest=str(tmp_path / "manifest.json"),
    )

    exit_code = dashboard_cli.handle_dashboard_command(args, parser=parser)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert calls == [(tmp_path, tmp_path / "manifest.json", None)]
    assert "Runs: 2" in captured.out
    assert "Artifacts: 2" in captured.out
    assert "csv=1, markdown=1" in captured.out


def test_quant_registry_still_classifies_legacy_premarket_artifact(tmp_path: Path) -> None:
    path = tmp_path / "phase0_premarket_watchlist_2026-08-12.csv"
    path.write_text("symbol\nSH.512480\n", encoding="utf-8")
    result = classify_legacy_brief_artifact(path.name)
    assert result == "brief"


def test_quant_registry_rejects_non_legacy_brief_filenames() -> None:
    assert classify_legacy_brief_artifact("daily_watchlist_2026-08-12.csv") is None
    assert classify_legacy_brief_artifact("phase0_backfill_report_2026-08-12.md") is None

