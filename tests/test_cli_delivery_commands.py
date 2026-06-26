from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

import phase0.cli as cli
import phase0.cli_commands.delivery as delivery_cli


def _silent_console() -> SimpleNamespace:
    return SimpleNamespace(print=lambda text: None)


def _history_result(*, ok: bool = True, inserted_rows: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        ok=ok,
        status="updated" if inserted_rows else "fresh",
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


def test_delivery_command_registration_preserves_args() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd")
    delivery_cli.register_delivery_commands(subparsers)

    daily_args = parser.parse_args(["brief", "daily", "--skip-update", "--refresh-cache"])
    premarket_args = parser.parse_args(["brief", "premarket", "--no-panel-cache"])
    bill_args = parser.parse_args(["brief", "account-bill", "--date", "2026-06-25"])
    legacy_args = parser.parse_args(["daily-brief", "--watchlist", "--check-only"])

    assert daily_args.cmd == "brief"
    assert daily_args.brief_cmd == "daily"
    assert daily_args.skip_update is True
    assert daily_args.refresh_cache is True
    assert premarket_args.brief_cmd == "premarket"
    assert premarket_args.no_panel_cache is True
    assert bill_args.brief_cmd == "account-bill"
    assert bill_args.date == "2026-06-25"
    assert legacy_args.cmd == "daily-brief"
    assert legacy_args.watchlist is True
    assert legacy_args.check_only is True


def test_watchlist_pipeline_updates_history_and_copies_latest(monkeypatch, tmp_path: Path) -> None:
    report = tmp_path / "report.html"
    report.write_text("<html>watchlist</html>", encoding="utf-8")
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_load_config(path: Path) -> dict[str, object]:
        calls.append(("load_config", {"path": path}))
        return {"reporting": {}}

    def fake_update_manual_history_from_config(cfg, root, *, check_only: bool):
        calls.append(("update_history", {"cfg": cfg, "root": root, "check_only": check_only}))
        return _history_result(inserted_rows=2)

    def fake_export_phase0_premarket(**kwargs):
        calls.append(("export_premarket", kwargs))
        return {
            "watchlist": tmp_path / "watchlist.csv",
            "report": report,
            "rows": 3,
            "signal_date": "2026-06-25",
            "check_time": "2026-06-25 07:30:00",
        }

    def fake_sync(console, local_dir: Path) -> None:
        calls.append(("sync", {"local_dir": local_dir}))

    monkeypatch.setattr(delivery_cli, "load_config", fake_load_config)
    monkeypatch.setattr(delivery_cli, "update_manual_history_from_config", fake_update_manual_history_from_config)
    monkeypatch.setattr(delivery_cli, "export_phase0_premarket", fake_export_phase0_premarket)
    monkeypatch.setattr(delivery_cli, "_sync_watchlist_to_ecs", fake_sync)
    monkeypatch.setattr(delivery_cli, "BRIEF_TODAY_MIRROR", tmp_path / "external" / "brief_today" / "index.html")
    monkeypatch.setattr(delivery_cli, "Console", lambda: _silent_console())

    exit_code = delivery_cli.run_watchlist_pipeline(
        config_path=tmp_path / "config.yaml",
        skip_update=False,
        check_only=False,
        refresh_cache=False,
        no_panel_cache=True,
    )

    assert exit_code == 0
    assert ("update_history", {"cfg": {"reporting": {}}, "root": tmp_path, "check_only": False}) in calls
    assert ("sync", {"local_dir": tmp_path / "reports" / "watchlist_today"}) in calls
    export_call = next(call for call in calls if call[0] == "export_premarket")
    assert export_call == (
        "export_premarket",
        {
            "config_path": tmp_path / "config.yaml",
            "refresh_cache": True,
            "no_panel_cache": True,
        },
    )
    assert (tmp_path / "reports" / "runs" / "latest" / "watchlist" / "index.html").read_text(encoding="utf-8") == "<html>watchlist</html>"
    assert (tmp_path / "reports" / "watchlist_today" / "index.html").read_text(encoding="utf-8") == "<html>watchlist</html>"
    assert (tmp_path / "external" / "brief_today" / "index.html").read_text(encoding="utf-8") == "<html>watchlist</html>"


def test_watchlist_pipeline_check_only_stops_before_export(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    monkeypatch.setattr(delivery_cli, "load_config", lambda path: {"reporting": {}})
    monkeypatch.setattr(
        delivery_cli,
        "update_manual_history_from_config",
        lambda cfg, root, *, check_only: _history_result(ok=True, inserted_rows=0),
    )
    monkeypatch.setattr(delivery_cli, "Console", lambda: _silent_console())

    def fake_export_phase0_premarket(**kwargs):
        calls.append("export")
        return {}

    monkeypatch.setattr(delivery_cli, "export_phase0_premarket", fake_export_phase0_premarket)

    exit_code = delivery_cli.run_watchlist_pipeline(
        config_path=tmp_path / "config.yaml",
        skip_update=False,
        check_only=True,
    )

    assert exit_code == 0
    assert calls == []


def test_delivery_handler_forwards_premarket_and_account_bill(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_export_phase0_premarket(**kwargs):
        calls.append(("premarket", kwargs))
        return {
            "watchlist": tmp_path / "watchlist.csv",
            "report": tmp_path / "report.html",
            "rows": 1,
            "signal_date": "2026-06-25",
            "check_time": "2026-06-25 07:30:00",
        }

    def fake_export_brief_account_bill(**kwargs):
        calls.append(("account_bill", kwargs))
        return {
            "account": "default",
            "brief_date": "2026-06-25",
            "account_bill": tmp_path / "account_bill.html",
        }

    monkeypatch.setattr(delivery_cli, "export_phase0_premarket", fake_export_phase0_premarket)
    monkeypatch.setattr(delivery_cli, "export_brief_account_bill", fake_export_brief_account_bill)

    premarket_exit = delivery_cli.handle_delivery_command(
        SimpleNamespace(
            cmd="brief",
            brief_cmd="premarket",
            config=str(tmp_path / "config.yaml"),
            refresh_cache=True,
            no_panel_cache=False,
        ),
        parser=argparse.ArgumentParser(),
        console=_silent_console(),
    )
    bill_exit = delivery_cli.handle_delivery_command(
        SimpleNamespace(
            cmd="brief",
            brief_cmd="account-bill",
            config=str(tmp_path / "config.yaml"),
            date="2026-06-25",
        ),
        parser=argparse.ArgumentParser(),
        console=_silent_console(),
    )

    assert premarket_exit == 0
    assert bill_exit == 0
    assert calls == [
        (
            "premarket",
            {
                "config_path": (tmp_path / "config.yaml").resolve(),
                "refresh_cache": True,
                "no_panel_cache": False,
            },
        ),
        (
            "account_bill",
            {
                "config_path": (tmp_path / "config.yaml").resolve(),
                "brief_date": "2026-06-25",
            },
        ),
    ]


def test_cli_main_delegates_delivery_commands(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str | None, bool]] = []

    def fake_handle_delivery_command(args, *, parser):
        calls.append((args.cmd, getattr(args, "brief_cmd", None), parser is not None))
        return 0

    monkeypatch.setattr(cli, "handle_delivery_command", fake_handle_delivery_command)
    monkeypatch.setattr("sys.argv", ["phase0.cli", "brief", "watchlist", "--config", str(tmp_path / "config.yaml")])

    assert cli.main() == 0
    assert calls == [("brief", "watchlist", True)]
