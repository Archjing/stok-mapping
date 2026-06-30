from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

import phase0.cli as cli
import phase0.cli_commands.data_update as data_update_cli


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

    def fake_update_us_market_history_from_config(cfg, root, *, check_only: bool):
        calls.append(("us", {"cfg": cfg, "root": root, "check_only": check_only}))
        return SimpleNamespace(ok=False, status="error", db_path=tmp_path / "us.sqlite", latest_date=None, coverage=0.0, covered_symbols=0, symbol_count=1, fetched_rows=0, inserted_rows=0, updated_rows=0, source=None, warnings=[])

    def fake_update_hk_market_history_from_config(cfg, root, *, check_only: bool):
        calls.append(("hk", {"cfg": cfg, "root": root, "check_only": check_only}))
        return SimpleNamespace(ok=True, status="fresh", db_path=tmp_path / "hk.sqlite", latest_date="2026-06-25", coverage=1.0, covered_symbols=1, symbol_count=1, fetched_rows=0, inserted_rows=0, updated_rows=0, source="local", warnings=[])

    def fake_import_from_config(cfg, root):
        calls.append(("import_history", {"cfg": cfg, "root": root}))
        return SimpleNamespace(db_path=tmp_path / "history.sqlite", start_date="2016-01-01", qfq_files=1, qfq_rows=2, bfq_files=1, bfq_rows=2, symbols=1, stock_meta_rows=1, calendar_rows=1, delisted_rows=0, index_meta_rows=1, index_files=1, index_rows=2)

    def fake_import_index_history_from_config(cfg, root):
        calls.append(("import_index", {"cfg": cfg, "root": root}))
        return SimpleNamespace(db_path=tmp_path / "history.sqlite", start_date="2016-01-01", index_meta_rows=1, index_files=1, index_rows=2)

    monkeypatch.setattr(data_update_cli, "load_config", fake_load_config)
    monkeypatch.setattr(data_update_cli, "update_us_market_history_from_config", fake_update_us_market_history_from_config)
    monkeypatch.setattr(data_update_cli, "update_hk_market_history_from_config", fake_update_hk_market_history_from_config)
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
    assert import_exit == 0
    assert index_import_exit == 0
    assert calls == [
        ("us", {"cfg": {"phase0": "config"}, "root": tmp_path, "check_only": True}),
        ("hk", {"cfg": {"phase0": "config"}, "root": tmp_path, "check_only": False}),
        ("import_history", {"cfg": {"phase0": "config"}, "root": tmp_path}),
        ("import_index", {"cfg": {"phase0": "config"}, "root": tmp_path}),
    ]


def test_cli_main_delegates_data_update_commands(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, bool]] = []

    def fake_handle_data_update_command(args, *, parser):
        calls.append((args.cmd, parser is not None))
        return 0

    monkeypatch.setattr(cli, "handle_data_update_command", fake_handle_data_update_command)
    monkeypatch.setattr("sys.argv", ["phase0.cli", "update-history", "--config", str(tmp_path / "config.yaml")])

    assert cli.main() == 0
    assert calls == [("update-history", True)]
