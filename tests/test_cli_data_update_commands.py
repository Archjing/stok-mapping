from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

import quant.cli as cli
import quant.cli_commands.data_update as data_update_cli
from quant.data_access.providers.tushare import TusharePermissionError, TushareTokenError
from quant.data_governance.backfills.etf_history import ETFBackfillDryRunResult, ETFBackfillResult
from quant.data_governance.etf_catalog import ETFCatalogSyncResult, StaleETFCatalogError
from quant.data_governance.etf_universe import ETFManifestMember, ETFUniverseManifest


def _silent_console() -> SimpleNamespace:
    return SimpleNamespace(print=lambda text: None)


def _recording_console() -> tuple[SimpleNamespace, list[str]]:
    lines: list[str] = []
    return SimpleNamespace(print=lambda text: lines.append(str(text))), lines


def _history_result(*, ok: bool = True, status: str = "updated", inserted_rows: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        ok=ok,
        status=status,
        db_path=Path("history.sqlite"),
        calendar_trade_date="2026-06-26",
        target_trade_date="2026-06-25",
        before_latest_date="2026-06-24",
        before_coverage=0.99,
        after_latest_date="2026-06-25",
        after_coverage=1.0,
        fetched_rows=inserted_rows,
        inserted_rows=inserted_rows,
        metadata_updated_rows=0,
        primary_source="tushare",
        metadata_coverage={},
        warnings=[],
    )


def _universe_result() -> SimpleNamespace:
    return SimpleNamespace(
        source="local_history_sqlite",
        selected_count=500,
        target_size=500,
        output_path=Path("universe.csv"),
        report_path=Path("universe.md"),
        warnings=[],
    )


def _etf_manifest() -> ETFUniverseManifest:
    member = ETFManifestMember(
        universe_name="sector_core_v1",
        sector="semiconductor",
        symbol="SH.512480",
        ts_code="512480.SH",
        requested_start=date(2026, 1, 1),
        requested_end=date(2026, 8, 11),
        effective_start=date(2026, 1, 1),
        effective_end=date(2026, 8, 11),
        expected_tracking_index=None,
        resolved_tracking_index="CSI.931865",
        mapping_assertion_status="not_configured",
    )
    return ETFUniverseManifest(
        universe_name="sector_core_v1",
        requested_sectors=("semiconductor",),
        requested_start=date(2026, 1, 1),
        requested_end=date(2026, 8, 11),
        config_digest="digest-123",
        catalog_snapshot_id="snapshot-123",
        members=(member,),
    )


def test_data_update_command_registration_preserves_args() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd")
    data_update_cli.register_data_update_commands(subparsers)

    update_args = parser.parse_args(["update-history", "--check-only", "--no-build-universe"])
    daily_basic_args = parser.parse_args(
        ["backfill-daily-basic", "--start-date", "2026-01-01", "--end-date", "2026-01-31", "--limit-dates", "3"]
    )
    tushare_args = parser.parse_args(
        [
            "backfill-tushare-history",
            "--end-date",
            "2026-06-25",
            "--no-daily-basic",
            "--no-adj-factor",
            "--no-dividends",
            "--no-financial",
        ]
    )
    financial_args = parser.parse_args(
        [
            "backfill-tushare-financials",
            "--period",
            "2026-03-31",
            "--missing-fields-only",
            "--missing-fields",
            "roe,debt_to_asset",
            "--shard-index",
            "1",
            "--shard-count",
            "3",
        ]
    )

    assert update_args.cmd == "update-history"
    assert update_args.check_only is True
    assert update_args.no_build_universe is True
    assert daily_basic_args.limit_dates == 3
    assert tushare_args.start_date == "2016-01-01"
    assert tushare_args.no_daily_basic is True
    assert financial_args.period == "2026-03-31"
    assert financial_args.missing_fields_only is True
    assert financial_args.missing_fields == "roe,debt_to_asset"
    assert financial_args.shard_index == 1
    assert financial_args.shard_count == 3


def test_etf_command_registration_preserves_scoped_arguments() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd")
    data_update_cli.register_data_update_commands(subparsers)

    sync_args = parser.parse_args(["sync-etf-catalog", "--config", "custom.yaml"])
    universe_args = parser.parse_args([
        "resolve-etf-universe", "--universe", "sector_core_v1", "--sector", "semiconductor",
        "--start-date", "2018-01-01", "--end-date", "2026-08-11",
    ])
    dry_run_args = parser.parse_args([
        "backfill-etf-history", "--universe", "sector_core_v1", "--sector", "semiconductor",
        "--start-date", "2018-01-01", "--end-date", "2026-08-11", "--dry-run",
        "--limit-symbols", "1", "--limit-tasks", "2",
    ])
    resume_args = parser.parse_args(["backfill-etf-history", "--resume-run-id", "run-123"])
    audit_args = parser.parse_args(["audit-etf-history", "--run-id", "run-123"])

    assert sync_args.config == "custom.yaml"
    assert universe_args.sector == ["semiconductor"]
    assert dry_run_args.universe == "sector_core_v1"
    assert dry_run_args.dry_run is True
    assert dry_run_args.limit_symbols == 1
    assert dry_run_args.limit_tasks == 2
    assert resume_args.resume_run_id == "run-123"
    assert audit_args.run_id == "run-123"
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["backfill-etf-history", "--resume-run-id", "run-123", "--universe", "sector_core_v1"])
    assert exc_info.value.code == 2


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sector", ["semiconductor"]),
        ("start_date", "2026-01-01"),
        ("end_date", "2026-08-11"),
        ("dry_run", True),
        ("limit_symbols", 1),
        ("limit_tasks", 2),
    ],
)
def test_etf_resume_direct_handler_rejects_new_run_arguments(field: str, value: object) -> None:
    values = {
        "cmd": "backfill-etf-history",
        "config": "config.yaml",
        "universe": None,
        "sector": None,
        "start_date": None,
        "end_date": None,
        "dry_run": False,
        "resume_run_id": "run-123",
        "limit_symbols": None,
        "limit_tasks": None,
    }
    values[field] = value
    with pytest.raises(SystemExit) as exc_info:
        data_update_cli.handle_data_update_command(
            SimpleNamespace(**values),
            parser=argparse.ArgumentParser(),
            console=_silent_console(),
        )
    assert exc_info.value.code == 2


def test_etf_handlers_forward_arguments_and_use_dry_run_result_counts(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    manifest = _etf_manifest()
    dry_run = ETFBackfillDryRunResult(
        manifest=manifest,
        task_specs=(),
        symbol_count=17,
        chunk_count=9,
        dataset_count=2,
        provider_call_count=34,
        effective_symbol_limit=50,
        effective_task_limit=1000,
        symbol_headroom=33,
        task_headroom=966,
    )

    def fake_sync(config_path: Path):
        calls.append(("sync", {"config_path": config_path}))
        return ETFCatalogSyncResult("ok", "snapshot-123", 10, 2, None, None)

    def fake_resolve(config_path: Path, **kwargs):
        calls.append(("resolve", {"config_path": config_path, **kwargs}))
        return manifest

    def fake_backfill(config_path: Path, **kwargs):
        calls.append(("backfill", {"config_path": config_path, **kwargs}))
        return dry_run

    def fake_audit(config_path: Path, run_id: str):
        calls.append(("audit", {"config_path": config_path, "run_id": run_id}))
        return SimpleNamespace(
            status="PASS", run_id=run_id, succeeded_tasks=34, target_tasks=34,
            factor_missing_bar_dates=0, json_path=tmp_path / "audit.json",
            markdown_path=tmp_path / "audit.md", exit_code=0,
        )

    monkeypatch.setattr(data_update_cli, "sync_etf_catalog_from_config", fake_sync)
    monkeypatch.setattr(data_update_cli, "resolve_etf_universe_from_config", fake_resolve)
    monkeypatch.setattr(data_update_cli, "backfill_etf_history_from_config", fake_backfill)
    monkeypatch.setattr(data_update_cli, "audit_etf_history_from_config", fake_audit)
    console, lines = _recording_console()
    config = str(tmp_path / "config.yaml")

    assert data_update_cli.handle_data_update_command(
        SimpleNamespace(cmd="sync-etf-catalog", config=config), parser=argparse.ArgumentParser(), console=console,
    ) == 0
    assert data_update_cli.handle_data_update_command(
        SimpleNamespace(cmd="resolve-etf-universe", config=config, universe="sector_core_v1", sector=["semiconductor"], start_date="2018-01-01", end_date="2026-08-11"),
        parser=argparse.ArgumentParser(), console=console,
    ) == 0
    assert data_update_cli.handle_data_update_command(
        SimpleNamespace(cmd="backfill-etf-history", config=config, universe="sector_core_v1", sector=["semiconductor"], start_date="2018-01-01", end_date="2026-08-11", dry_run=True, resume_run_id=None, limit_symbols=1, limit_tasks=20),
        parser=argparse.ArgumentParser(), console=console,
    ) == 0
    assert data_update_cli.handle_data_update_command(
        SimpleNamespace(cmd="audit-etf-history", config=config, run_id="run-123"),
        parser=argparse.ArgumentParser(), console=console,
    ) == 0

    resolved_config = (tmp_path / "config.yaml").resolve()
    assert calls == [
        ("sync", {"config_path": resolved_config}),
        ("resolve", {"config_path": resolved_config, "universe_name": "sector_core_v1", "requested_sectors": ["semiconductor"], "start_date": "2018-01-01", "end_date": "2026-08-11"}),
        ("backfill", {"config_path": resolved_config, "universe_name": "sector_core_v1", "sectors": ["semiconductor"], "start_date": "2018-01-01", "end_date": "2026-08-11", "dry_run": True, "resume_run_id": None, "limit_symbols": 1, "limit_tasks": 20}),
        ("audit", {"config_path": resolved_config, "run_id": "run-123"}),
    ]
    output = "\n".join(lines)
    assert "Symbols: 17" in output
    assert "Annual chunks: 9" in output
    assert "Provider calls/tasks: 34" in output
    assert "Task headroom: 966/1000" in output


@pytest.mark.parametrize("status", ["partial", "failed"])
def test_etf_backfill_unsuccessful_status_returns_two(monkeypatch, tmp_path: Path, status: str) -> None:
    monkeypatch.setattr(
        data_update_cli,
        "backfill_etf_history_from_config",
        lambda *args, **kwargs: ETFBackfillResult("run-123", status, 2, 1, 0, 1, 5, tmp_path / "etf.sqlite"),
    )
    exit_code = data_update_cli.handle_data_update_command(
        SimpleNamespace(cmd="backfill-etf-history", config=str(tmp_path / "config.yaml"), universe="sector_core_v1", sector=None, start_date="2026-01-01", end_date="2026-08-11", dry_run=False, resume_run_id=None, limit_symbols=None, limit_tasks=None),
        parser=argparse.ArgumentParser(), console=_silent_console(),
    )
    assert exit_code == 2


@pytest.mark.parametrize(
    "error",
    [
        TushareTokenError("fund_daily", None, "token=RAW_SECRET_TOKEN"),
        TusharePermissionError("etf_basic", 40203, "payload=RAW_SECRET_TOKEN permission denied"),
        StaleETFCatalogError("latest ETF catalog snapshot is older than 7 days"),
    ],
)
def test_etf_handler_errors_return_two_without_raw_provider_payload(monkeypatch, tmp_path: Path, error: Exception) -> None:
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(data_update_cli, "resolve_etf_universe_from_config", fail)
    console, lines = _recording_console()
    exit_code = data_update_cli.handle_data_update_command(
        SimpleNamespace(cmd="resolve-etf-universe", config=str(tmp_path / "config.yaml"), universe="sector_core_v1", sector=None, start_date="2026-01-01", end_date="2026-08-11"),
        parser=argparse.ArgumentParser(), console=console,
    )
    assert exit_code == 2
    assert "RAW_SECRET_TOKEN" not in "\n".join(lines)


def test_etf_catalog_failure_does_not_print_raw_error_message(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        data_update_cli,
        "sync_etf_catalog_from_config",
        lambda config_path: ETFCatalogSyncResult("failed", "snapshot-123", 0, 0, "permission_denied", "payload=RAW_SECRET_TOKEN"),
    )
    console, lines = _recording_console()
    exit_code = data_update_cli.handle_data_update_command(
        SimpleNamespace(cmd="sync-etf-catalog", config=str(tmp_path / "config.yaml")),
        parser=argparse.ArgumentParser(), console=console,
    )
    assert exit_code == 2
    assert "permission_denied" in "\n".join(lines)
    assert "RAW_SECRET_TOKEN" not in "\n".join(lines)


def test_update_history_handler_rebuilds_universe_when_configured(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_load_config(path: Path) -> dict[str, object]:
        return {"manual_history_update": {"rebuild_universe_after": True}}

    def fake_update_manual_history_from_config(cfg, root, *, check_only: bool):
        calls.append(("update_history", {"cfg": cfg, "root": root, "check_only": check_only}))
        return _history_result(status="metadata_updated", inserted_rows=2)

    def fake_build_local_factor_universe(cfg, root):
        calls.append(("build_universe", {"cfg": cfg, "root": root}))
        return _universe_result()

    monkeypatch.setattr(data_update_cli, "load_config", fake_load_config)
    monkeypatch.setattr(data_update_cli, "update_manual_history_from_config", fake_update_manual_history_from_config)
    monkeypatch.setattr(data_update_cli, "build_local_factor_universe", fake_build_local_factor_universe)
    args = SimpleNamespace(
        cmd="update-history",
        config=str(tmp_path / "config.yaml"),
        check_only=False,
        no_build_universe=False,
    )

    exit_code = data_update_cli.handle_data_update_command(
        args,
        parser=argparse.ArgumentParser(),
        console=_silent_console(),
    )

    assert exit_code == 0
    assert calls == [
        ("update_history", {"cfg": {"manual_history_update": {"rebuild_universe_after": True}}, "root": tmp_path, "check_only": False}),
        ("build_universe", {"cfg": {"manual_history_update": {"rebuild_universe_after": True}}, "root": tmp_path}),
    ]


def test_update_financials_handler_forwards_periods_and_rebuilds_universe(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    console, lines = _recording_console()

    def fake_load_config(path: Path) -> dict[str, object]:
        return {"financial_factors": {"rebuild_universe_after": True}}

    def fake_update_financial_factors_from_config(cfg, root, *, periods):
        calls.append(("update_financials", {"cfg": cfg, "root": root, "periods": periods}))
        return SimpleNamespace(
            ok=True,
            status="updated",
            db_path=tmp_path / "history.sqlite",
            periods_requested=["2026Q1"],
            periods_updated=["2026Q1"],
            fetched_rows=10,
            inserted_rows=10,
            factor_coverage={},
            warnings=[],
        )

    def fake_build_local_factor_universe(cfg, root):
        calls.append(("build_universe", {"cfg": cfg, "root": root}))
        return _universe_result()

    monkeypatch.setattr(data_update_cli, "load_config", fake_load_config)
    monkeypatch.setattr(data_update_cli, "update_financial_factors_from_config", fake_update_financial_factors_from_config)
    monkeypatch.setattr(data_update_cli, "build_local_factor_universe", fake_build_local_factor_universe)
    args = SimpleNamespace(
        cmd="update-financials",
        config=str(tmp_path / "config.yaml"),
        periods=16,
        no_build_universe=False,
    )

    exit_code = data_update_cli.handle_data_update_command(
        args,
        parser=argparse.ArgumentParser(),
        console=console,
    )

    assert exit_code == 0
    assert lines[:3] == [
        "Financial factor update started",
        f"Config: {tmp_path / 'config.yaml'}",
        "Periods override: recent 16 quarters",
    ]
    assert calls == [
        ("update_financials", {"cfg": {"financial_factors": {"rebuild_universe_after": True}}, "root": tmp_path, "periods": 16}),
        ("build_universe", {"cfg": {"financial_factors": {"rebuild_universe_after": True}}, "root": tmp_path}),
    ]


def test_backfill_handlers_forward_arguments_and_exit_codes(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_backfill_daily_basic_from_config(config_path, **kwargs):
        calls.append(("daily_basic", {"config_path": config_path, **kwargs}))
        return SimpleNamespace(
            db_path=tmp_path / "history.sqlite",
            table_name="market_daily_basic",
            status="ok",
            target_dates=2,
            fetched_dates=2,
            inserted_rows=20,
            skipped_existing_dates=0,
            warnings=[],
        )

    def fake_backfill_adjustment_factors_from_config(config_path, **kwargs):
        calls.append(("adjustment", {"config_path": config_path, **kwargs}))
        return SimpleNamespace(
            status="missing_tushare_token",
            db_path=tmp_path / "history.sqlite",
            target_dates=1,
            fetched_dates=0,
            inserted_adj_factor_rows=0,
            inserted_dividend_rows=0,
            skipped_existing_dates=0,
            warnings=[],
        )

    def fake_backfill_index_asof_from_config(config_path, **kwargs):
        calls.append(("index_asof", {"config_path": config_path, **kwargs}))
        return SimpleNamespace(
            status="ok",
            db_path=tmp_path / "history.sqlite",
            index_code="SH.000905",
            vendor_index_code="000905.SH",
            source="input_csv",
            fetched_rows=3,
            inserted_weight_rows=3,
            inserted_constituent_rows=3,
            distinct_trade_dates=1,
            min_trade_date="2026-06-25",
            max_trade_date="2026-06-25",
            audit_csv=tmp_path / "audit.csv",
            audit_md=tmp_path / "audit.md",
            warnings=[],
        )

    monkeypatch.setattr(data_update_cli, "backfill_daily_basic_from_config", fake_backfill_daily_basic_from_config)
    monkeypatch.setattr(data_update_cli, "backfill_adjustment_factors_from_config", fake_backfill_adjustment_factors_from_config)
    monkeypatch.setattr(data_update_cli, "backfill_index_asof_from_config", fake_backfill_index_asof_from_config)

    daily_exit = data_update_cli.handle_data_update_command(
        SimpleNamespace(
            cmd="backfill-daily-basic",
            config=str(tmp_path / "config.yaml"),
            start_date="2026-01-01",
            end_date="2026-01-31",
            limit_dates=3,
        ),
        parser=argparse.ArgumentParser(),
        console=_silent_console(),
    )
    adjustment_exit = data_update_cli.handle_data_update_command(
        SimpleNamespace(
            cmd="backfill-adjustment-factors",
            config=str(tmp_path / "config.yaml"),
            start_date="2026-01-01",
            end_date="2026-01-31",
            limit_dates=2,
            no_skip_existing=True,
            no_dividends=True,
            max_requests_per_minute=90,
        ),
        parser=argparse.ArgumentParser(),
        console=_silent_console(),
    )
    index_exit = data_update_cli.handle_data_update_command(
        SimpleNamespace(
            cmd="backfill-index-asof",
            config=str(tmp_path / "config.yaml"),
            index_code="SH.000905",
            start_date="2026-01-01",
            end_date="2026-01-31",
            input_csv=str(tmp_path / "weights.csv"),
            max_requests_per_minute=120,
            weights_table="weights",
            constituents_table="constituents",
        ),
        parser=argparse.ArgumentParser(),
        console=_silent_console(),
    )

    assert daily_exit == 0
    assert adjustment_exit == 2
    assert index_exit == 0
    assert calls == [
        (
            "daily_basic",
            {
                "config_path": (tmp_path / "config.yaml").resolve(),
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "limit_dates": 3,
            },
        ),
        (
            "adjustment",
            {
                "config_path": (tmp_path / "config.yaml").resolve(),
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "limit_dates": 2,
                "skip_existing": False,
                "include_dividends": False,
                "max_requests_per_minute": 90,
            },
        ),
        (
            "index_asof",
            {
                "config_path": (tmp_path / "config.yaml").resolve(),
                "index_code": "SH.000905",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "input_csv": (tmp_path / "weights.csv").resolve(),
                "max_requests_per_minute": 120,
                "weights_table": "weights",
                "constituents_table": "constituents",
            },
        ),
    ]


def test_tushare_financial_backfill_forwards_progress_callback(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []
    lines: list[str] = []

    def fake_backfill_tushare_financials_from_config(config_path, **kwargs):
        calls.append({"config_path": config_path, **kwargs})
        kwargs["progress_callback"]({"event": "start", "target_tasks": 2, "processed_tasks": 1, "elapsed_seconds": 60})
        return SimpleNamespace(
            status="ok",
            db_path=tmp_path / "history.sqlite",
            target_tasks=2,
            processed_tasks=1,
            fetched_tasks=1,
            empty_tasks=0,
            failed_tasks=0,
            inserted_rows=5,
            audit_csv=tmp_path / "audit.csv",
            audit_md=tmp_path / "audit.md",
            warnings=[],
        )

    monkeypatch.setattr(data_update_cli, "backfill_tushare_financials_from_config", fake_backfill_tushare_financials_from_config)
    args = SimpleNamespace(
        cmd="backfill-tushare-financials",
        config=str(tmp_path / "config.yaml"),
        period="2026-03-31",
        start_period="2025-03-31",
        end_period="2026-03-31",
        max_requests_per_minute=120,
        max_runtime_minutes=30,
        limit_symbols=10,
        limit_tasks=20,
        retry_failed=True,
        replace_existing=True,
        missing_fields_only=True,
        missing_fields="roe, debt_to_asset",
        shard_index=1,
        shard_count=3,
    )

    exit_code = data_update_cli.handle_data_update_command(
        args,
        parser=argparse.ArgumentParser(),
        console=SimpleNamespace(print=lambda text: lines.append(str(text))),
    )

    assert exit_code == 0
    assert len(calls) == 1
    assert calls[0]["config_path"] == (tmp_path / "config.yaml").resolve()
    assert calls[0]["missing_fields"] == ["roe", "debt_to_asset"]
    assert calls[0]["shard_index"] == 1
    assert calls[0]["shard_count"] == 3
    assert callable(calls[0]["progress_callback"])
    assert any("Tushare financial backfill selected" in line for line in lines)


def test_tushare_history_and_build_universe_handlers_forward_args(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_load_config(path: Path) -> dict[str, object]:
        return {"phase0": "config"}

    def fake_backfill_tushare_history_from_config(config_path, **kwargs):
        calls.append(("tushare_history", {"config_path": config_path, **kwargs}))
        return SimpleNamespace(
            status="missing_tushare_token",
            db_path=tmp_path / "history.sqlite",
            daily_basic_fetched_dates=0,
            daily_basic_target_dates=1,
            daily_basic_inserted_rows=0,
            adj_factor_fetched_dates=0,
            adj_factor_target_dates=1,
            adj_factor_inserted_rows=0,
            dividend_inserted_rows=0,
            financial_fetched_periods=0,
            financial_target_periods=1,
            financial_inserted_rows=0,
            audit_csv=tmp_path / "audit.csv",
            audit_md=tmp_path / "audit.md",
            warnings=[],
        )

    def fake_build_local_factor_universe(cfg, root):
        calls.append(("build_universe", {"cfg": cfg, "root": root}))
        return _universe_result()

    monkeypatch.setattr(data_update_cli, "load_config", fake_load_config)
    monkeypatch.setattr(data_update_cli, "backfill_tushare_history_from_config", fake_backfill_tushare_history_from_config)
    monkeypatch.setattr(data_update_cli, "build_local_factor_universe", fake_build_local_factor_universe)

    tushare_exit = data_update_cli.handle_data_update_command(
        SimpleNamespace(
            cmd="backfill-tushare-history",
            config=str(tmp_path / "config.yaml"),
            start_date="2026-01-01",
            end_date="2026-01-31",
            max_requests_per_minute=100,
            limit_dates=5,
            limit_periods=2,
            no_skip_existing=True,
            no_daily_basic=True,
            no_adj_factor=False,
            no_dividends=True,
            no_financial=False,
        ),
        parser=argparse.ArgumentParser(),
        console=_silent_console(),
    )
    universe_exit = data_update_cli.handle_data_update_command(
        SimpleNamespace(cmd="build-universe", config=str(tmp_path / "config.yaml")),
        parser=argparse.ArgumentParser(),
        console=_silent_console(),
    )

    assert tushare_exit == 2
    assert universe_exit == 0
    assert calls == [
        (
            "tushare_history",
            {
                "config_path": (tmp_path / "config.yaml").resolve(),
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "max_requests_per_minute": 100,
                "limit_dates": 5,
                "limit_periods": 2,
                "skip_existing": False,
                "include_daily_basic": False,
                "include_adj_factor": True,
                "include_dividends": False,
                "include_financial": True,
            },
        ),
        ("build_universe", {"cfg": {"phase0": "config"}, "root": tmp_path}),
    ]


def test_external_market_and_import_handlers_forward_args(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_load_config(path: Path) -> dict[str, object]:
        return {"phase0": "config"}

    def fake_update_us_market_history_from_config(cfg, root, *, check_only: bool, force_start_date=None):
        calls.append(("us", {"cfg": cfg, "root": root, "check_only": check_only}))
        return SimpleNamespace(ok=False, status="error", db_path=tmp_path / "us.sqlite", latest_date=None, coverage=0.0, covered_symbols=0, symbol_count=1, fetched_rows=0, inserted_rows=0, updated_rows=0, source=None, warnings=[])

    def fake_update_hk_market_history_from_config(cfg, root, *, check_only: bool):
        calls.append(("hk", {"cfg": cfg, "root": root, "check_only": check_only}))
        return SimpleNamespace(ok=True, status="fresh", db_path=tmp_path / "hk.sqlite", latest_date="2026-06-25", coverage=1.0, covered_symbols=1, symbol_count=1, fetched_rows=0, inserted_rows=0, updated_rows=0, source="local", warnings=[])

    def fake_update_europe_market_history_from_config(cfg, root, *, check_only: bool):
        calls.append(("europe", {"cfg": cfg, "root": root, "check_only": check_only}))
        return SimpleNamespace(ok=True, status="updated", db_path=tmp_path / "euro.sqlite", latest_date="2026-08-10", coverage=1.0, covered_symbols=2, symbol_count=2, fetched_rows=4, inserted_rows=4, updated_rows=0, source="yfinance", warnings=[])

    def fake_import_from_config(cfg, root):
        calls.append(("import_history", {"cfg": cfg, "root": root}))
        return SimpleNamespace(db_path=tmp_path / "history.sqlite", start_date="2016-01-01", qfq_files=1, qfq_rows=2, bfq_files=1, bfq_rows=2, symbols=1, stock_meta_rows=1, calendar_rows=1, delisted_rows=0, index_meta_rows=1, index_files=1, index_rows=2)

    def fake_import_index_history_from_config(cfg, root):
        calls.append(("import_index", {"cfg": cfg, "root": root}))
        return SimpleNamespace(db_path=tmp_path / "history.sqlite", start_date="2016-01-01", index_meta_rows=1, index_files=1, index_rows=2)

    monkeypatch.setattr(data_update_cli, "load_config", fake_load_config)
    monkeypatch.setattr(data_update_cli, "update_us_market_history_from_config", fake_update_us_market_history_from_config)
    monkeypatch.setattr(data_update_cli, "update_hk_market_history_from_config", fake_update_hk_market_history_from_config)
    monkeypatch.setattr(data_update_cli, "update_europe_market_history_from_config", fake_update_europe_market_history_from_config)
    monkeypatch.setattr(data_update_cli, "import_from_config", fake_import_from_config)
    monkeypatch.setattr(data_update_cli, "import_index_history_from_config", fake_import_index_history_from_config)

    us_exit = data_update_cli.handle_data_update_command(
        SimpleNamespace(cmd="update-us-market-history", config=str(tmp_path / "config.yaml"), check_only=True),
        parser=argparse.ArgumentParser(),
        console=_silent_console(),
    )
    hk_exit = data_update_cli.handle_data_update_command(
        SimpleNamespace(cmd="update-hk-market-history", config=str(tmp_path / "config.yaml"), check_only=False),
        parser=argparse.ArgumentParser(),
        console=_silent_console(),
    )
    europe_exit = data_update_cli.handle_data_update_command(
        SimpleNamespace(cmd="update-europe-market-history", config=str(tmp_path / "config.yaml"), check_only=True),
        parser=argparse.ArgumentParser(),
        console=_silent_console(),
    )
    import_exit = data_update_cli.handle_data_update_command(
        SimpleNamespace(cmd="import-history", config=str(tmp_path / "config.yaml")),
        parser=argparse.ArgumentParser(),
        console=_silent_console(),
    )
    index_import_exit = data_update_cli.handle_data_update_command(
        SimpleNamespace(cmd="import-index-history", config=str(tmp_path / "config.yaml")),
        parser=argparse.ArgumentParser(),
        console=_silent_console(),
    )

    assert us_exit == 2
    assert hk_exit == 0
    assert europe_exit == 0
    assert import_exit == 0
    assert index_import_exit == 0
    assert calls == [
        ("us", {"cfg": {"phase0": "config"}, "root": tmp_path, "check_only": True}),
        ("hk", {"cfg": {"phase0": "config"}, "root": tmp_path, "check_only": False}),
        ("europe", {"cfg": {"phase0": "config"}, "root": tmp_path, "check_only": True}),
        ("import_history", {"cfg": {"phase0": "config"}, "root": tmp_path}),
        ("import_index", {"cfg": {"phase0": "config"}, "root": tmp_path}),
    ]


def test_cli_main_delegates_data_update_commands(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, bool]] = []

    def fake_handle_data_update_command(args, *, parser):
        calls.append((args.cmd, parser is not None))
        return 0

    monkeypatch.setattr(cli, "handle_data_update_command", fake_handle_data_update_command)
    monkeypatch.setattr("sys.argv", ["quant.cli", "update-history", "--config", str(tmp_path / "config.yaml")])

    assert cli.main() == 0
    assert calls == [("update-history", True)]
