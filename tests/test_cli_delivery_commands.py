from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

import quant.cli as cli
import quant.cli_commands.delivery as delivery_cli


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
    confirm_bill_args = parser.parse_args(["brief", "confirm-account-bills", "--date", "2026-07-02", "--all-accounts"])
    legacy_args = parser.parse_args(["daily-brief", "--watchlist", "--check-only"])

    assert daily_args.cmd == "brief"
    assert daily_args.brief_cmd == "daily"
    assert daily_args.skip_update is True
    assert daily_args.refresh_cache is True
    assert premarket_args.brief_cmd == "premarket"
    assert premarket_args.no_panel_cache is True
    assert bill_args.brief_cmd == "account-bill"
    assert bill_args.date == "2026-06-25"
    assert confirm_bill_args.brief_cmd == "confirm-account-bills"
    assert confirm_bill_args.date == "2026-07-02"
    assert confirm_bill_args.all_accounts is True
    assert legacy_args.cmd == "daily-brief"
    assert legacy_args.watchlist is True
    assert legacy_args.check_only is True


def test_sync_target_reads_environment_first(monkeypatch) -> None:
    monkeypatch.setenv("BRIEF_SYNC_REMOTE", "deploy@example")
    monkeypatch.setenv("BRIEF_SYNC_REMOTE_DIR", "/srv/brief/")

    assert delivery_cli._sync_target(
        "BRIEF_SYNC_REMOTE",
        "BRIEF_SYNC_REMOTE_DIR",
        default_remote="fallback@example",
        default_remote_dir="/fallback/",
    ) == ("deploy@example", "/srv/brief/")


def test_sync_target_falls_back_when_environment_is_empty(monkeypatch) -> None:
    monkeypatch.setenv("BRIEF_SYNC_REMOTE", "")
    monkeypatch.setenv("BRIEF_SYNC_REMOTE_DIR", "")

    assert delivery_cli._sync_target(
        "BRIEF_SYNC_REMOTE",
        "BRIEF_SYNC_REMOTE_DIR",
        default_remote="fallback@example",
        default_remote_dir="/fallback/",
    ) == ("fallback@example", "/fallback/")


def test_watchlist_sync_excludes_remote_preview_dir(monkeypatch, tmp_path: Path) -> None:
    local_dir = tmp_path / "watchlist_today"
    local_dir.mkdir()
    (local_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(cmd, *, check: bool):
        calls.append(cmd)

    monkeypatch.setattr(delivery_cli.subprocess, "run", fake_run)
    monkeypatch.setenv("BRIEF_SYNC_REMOTE", "deploy@example")
    monkeypatch.setenv("BRIEF_SYNC_REMOTE_DIR", "/srv/brief/")

    delivery_cli._sync_watchlist_to_remote(_silent_console(), local_dir)

    assert calls
    assert "--exclude=ui-test/" in calls[0]
    assert "--delete" in calls[0]


def test_watchlist_pipeline_updates_history_and_copies_latest(monkeypatch, tmp_path: Path) -> None:
    report = tmp_path / "report.html"
    report.write_text("<html>watchlist</html>", encoding="utf-8")
    stylesheet = tmp_path / "style.css"
    stylesheet.write_text(":root { --watchlist-page-bg: #fff; }", encoding="utf-8")
    account_bill = tmp_path / "account_bill.html"
    account_bill.write_text("<html>account bill</html>", encoding="utf-8")
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_load_config(path: Path) -> dict[str, object]:
        calls.append(("load_config", {"path": path}))
        return {"reporting": {}}

    def fake_update_manual_history_from_config(cfg, root, *, check_only: bool):
        calls.append(("update_history", {"cfg": cfg, "root": root, "check_only": check_only}))
        return _history_result(inserted_rows=2)

    def fake_export_premarket(**kwargs):
        calls.append(("export_premarket", kwargs))
        return {
            "watchlist": tmp_path / "watchlist.csv",
            "report": report,
            "rows": 3,
            "signal_date": "2026-06-25",
            "check_time": "2026-06-25 07:30:00",
            "account_bill": account_bill,
        }

    def fake_sync(console, local_dir: Path) -> None:
        calls.append(("sync", {"local_dir": local_dir}))

    def fake_build_quant_site(*, root, config, accounts):
        calls.append(("build_quant_site", {"root": root, "config": config, "accounts": accounts}))
        return {"site_root": root / "reports" / "static_site" / "quant"}

    def fake_sync_quant_site(*, root, site_root):
        calls.append(("sync_quant_site", {"root": root, "site_root": site_root}))
        return {"remote": "deploy@example", "remote_dir": "/var/www/spidermanread/quant/"}

    monkeypatch.setattr(delivery_cli, "load_config", fake_load_config)
    monkeypatch.setattr(delivery_cli, "update_manual_history_from_config", fake_update_manual_history_from_config)
    monkeypatch.setattr(delivery_cli, "export_premarket", fake_export_premarket)
    monkeypatch.setattr(delivery_cli, "_sync_watchlist_to_remote", fake_sync)
    monkeypatch.setattr(delivery_cli, "_sync_account_bill_to_cloud", fake_sync)
    monkeypatch.setattr(delivery_cli, "load_simulated_accounts", lambda cfg, root: [])
    monkeypatch.setattr(delivery_cli, "build_quant_static_site", fake_build_quant_site)
    monkeypatch.setattr(delivery_cli, "sync_quant_static_site", fake_sync_quant_site)
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
    assert ("sync", {"local_dir": tmp_path / "reports" / "account_bill_today"}) in calls
    assert ("build_quant_site", {"root": tmp_path, "config": {"reporting": {}}, "accounts": []}) in calls
    assert ("sync_quant_site", {"root": tmp_path, "site_root": tmp_path / "reports" / "static_site" / "quant"}) in calls
    export_call = next(call for call in calls if call[0] == "export_premarket")
    assert export_call == (
        "export_premarket",
            {
                "config_path": tmp_path / "config.yaml",
                "refresh_cache": True,
                "no_panel_cache": True,
                "as_of_date": None,
            },
        )
    assert (tmp_path / "reports" / "runs" / "latest" / "watchlist" / "index.html").read_text(encoding="utf-8") == "<html>watchlist</html>"
    assert (tmp_path / "reports" / "watchlist_today" / "index.html").read_text(encoding="utf-8") == "<html>watchlist</html>"
    assert (tmp_path / "reports" / "runs" / "latest" / "watchlist" / "style.css").read_text(encoding="utf-8") == stylesheet.read_text(
        encoding="utf-8"
    )
    assert (tmp_path / "reports" / "watchlist_today" / "style.css").read_text(encoding="utf-8") == stylesheet.read_text(encoding="utf-8")
    assert (tmp_path / "reports" / "runs" / "latest" / "account_bill" / "index.html").read_text(encoding="utf-8") == "<html>account bill</html>"
    assert (tmp_path / "reports" / "account_bill_today" / "index.html").read_text(encoding="utf-8") == "<html>account bill</html>"
    assert (tmp_path / "reports" / "runs" / "latest" / "account_bill" / "style.css").read_text(encoding="utf-8") == stylesheet.read_text(
        encoding="utf-8"
    )
    assert (tmp_path / "reports" / "account_bill_today" / "style.css").read_text(encoding="utf-8") == stylesheet.read_text(encoding="utf-8")
    assert (tmp_path / "external" / "brief_today" / "index.html").read_text(encoding="utf-8") == "<html>watchlist</html>"
    assert (tmp_path / "external" / "brief_today" / "style.css").read_text(encoding="utf-8") == stylesheet.read_text(encoding="utf-8")


def test_watchlist_pipeline_all_accounts_runs_each_enabled_account(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    reports: dict[str, Path] = {}

    class Account:
        def __init__(self, account_id: str) -> None:
            self.account_id = account_id

    def fake_load_config(path: Path) -> dict[str, object]:
        calls.append(("load_config", {"path": path}))
        return {"reporting": {}}

    def fake_update_manual_history_from_config(cfg, root, *, check_only: bool):
        calls.append(("update_history", {"cfg": cfg, "root": root, "check_only": check_only}))
        return _history_result(inserted_rows=0)

    def fake_load_accounts(cfg, root):
        return [Account("default"), Account("quality")]

    def fake_export_premarket(**kwargs):
        account_id = str(kwargs["account_id"])
        calls.append(("export_premarket", kwargs))
        report = tmp_path / f"{account_id}_report.html"
        report.write_text(f"<html>{account_id}</html>", encoding="utf-8")
        (report.parent / "style.css").write_text("body{}", encoding="utf-8")
        account_bill = tmp_path / f"{account_id}_account_bill.html"
        account_bill.write_text(f"<html>{account_id} bill</html>", encoding="utf-8")
        reports[account_id] = report
        return {
            "watchlist": tmp_path / f"{account_id}_watchlist.csv",
            "report": report,
            "rows": 1,
            "signal_date": "2026-06-25",
            "check_time": "2026-06-25 07:30:00",
            "account_id": account_id,
            "account_bill": account_bill,
        }

    monkeypatch.setattr(delivery_cli, "load_config", fake_load_config)
    monkeypatch.setattr(delivery_cli, "load_simulated_accounts", fake_load_accounts)
    monkeypatch.setattr(delivery_cli, "update_manual_history_from_config", fake_update_manual_history_from_config)
    monkeypatch.setattr(delivery_cli, "export_premarket", fake_export_premarket)
    monkeypatch.setattr(delivery_cli, "_sync_watchlist_to_remote", lambda console, local_dir: None)
    monkeypatch.setattr(delivery_cli, "_sync_account_bill_to_cloud", lambda console, local_dir: None)
    monkeypatch.setattr(delivery_cli, "build_quant_static_site", lambda **kwargs: {"site_root": tmp_path / "reports" / "static_site" / "quant"})
    monkeypatch.setattr(delivery_cli, "sync_quant_static_site", lambda **kwargs: {"remote": "deploy@example", "remote_dir": "/var/www/spidermanread/quant/"})
    monkeypatch.setattr(delivery_cli, "BRIEF_TODAY_MIRROR", tmp_path / "external" / "brief_today" / "index.html")
    monkeypatch.setattr(delivery_cli, "Console", lambda: _silent_console())

    exit_code = delivery_cli.run_watchlist_pipeline(
        config_path=tmp_path / "config.yaml",
        skip_update=True,
        all_accounts=True,
    )

    assert exit_code == 0
    export_calls = [call for call in calls if call[0] == "export_premarket"]
    assert [call[1]["account_id"] for call in export_calls] == ["default", "quality"]
    assert (tmp_path / "reports" / "runs" / "latest" / "accounts" / "default" / "watchlist" / "index.html").read_text(
        encoding="utf-8"
    ) == "<html>default</html>"
    assert (tmp_path / "reports" / "runs" / "latest" / "accounts" / "quality" / "watchlist" / "index.html").read_text(
        encoding="utf-8"
    ) == "<html>quality</html>"
    assert (tmp_path / "reports" / "runs" / "latest" / "accounts" / "default" / "account_bill" / "index.html").read_text(
        encoding="utf-8"
    ) == "<html>default bill</html>"
    assert (tmp_path / "reports" / "runs" / "latest" / "accounts" / "quality" / "account_bill" / "index.html").read_text(
        encoding="utf-8"
    ) == "<html>quality bill</html>"


def test_confirm_account_bills_rebuilds_ledgers_and_publishes_site(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    watchlist_path = (
        tmp_path
        / "reports"
        / "runs"
        / "2026-07-02"
        / "20260702_072000__premarket__default"
        / "premarket__watchlist.csv"
    )
    watchlist_path.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "盘前检查时间": "2026-07-02 07:20:00",
                "账户ID": "default",
                "策略ID": "strategy_a",
                "股票代码": "SH.600000",
                "股票名称": "浦发银行",
                "收盘价": "10.00",
                "目标权重": "10.00%",
                "权重变化": "10.00%",
            }
        ]
    ).to_csv(watchlist_path, index=False, encoding="utf-8-sig")

    class Account:
        def __init__(self, account_id: str, strategy_id: str) -> None:
            self.account_id = account_id
            self.strategy_id = strategy_id

    account = Account("default", "strategy_a")
    bill = tmp_path / "generated_account_bill.html"
    bill.write_text("<html>confirmed bill</html>", encoding="utf-8")
    (bill.parent / "style.css").write_text("body{}", encoding="utf-8")

    def fake_build_account_ledger(**kwargs):
        calls.append(("build_account_ledger", kwargs))
        return pd.DataFrame([{"brief_date": "2026-07-02", "total_asset": 1_000_000.0}]), {"total_asset": 1_000_000.0}

    def fake_export_brief_account_bill(**kwargs):
        calls.append(("export_account_bill", kwargs))
        return {"account": "default", "brief_date": "2026-07-02", "account_bill": bill, "status": "confirmed"}

    monkeypatch.setattr(delivery_cli, "load_config", lambda path: {"reporting": {}, "local_history": {"path": "data/a_share_history.sqlite"}})
    monkeypatch.setattr(delivery_cli, "load_simulated_accounts", lambda cfg, root: [account])
    monkeypatch.setattr(delivery_cli, "build_account_ledger", fake_build_account_ledger)
    monkeypatch.setattr(delivery_cli, "export_brief_account_bill", fake_export_brief_account_bill)
    monkeypatch.setattr(delivery_cli, "_sync_account_bill_to_cloud", lambda console, local_dir: calls.append(("sync_bill", {"local_dir": local_dir})))
    monkeypatch.setattr(delivery_cli, "build_quant_static_site", lambda **kwargs: {"site_root": tmp_path / "reports" / "static_site" / "quant"})
    monkeypatch.setattr(delivery_cli, "sync_quant_static_site", lambda **kwargs: {"remote": "deploy@example", "remote_dir": "/var/www/spidermanread/quant/"})
    monkeypatch.setattr(delivery_cli, "Console", lambda: _silent_console())

    exit_code = delivery_cli.confirm_account_bills_pipeline(
        config_path=tmp_path / "config.yaml",
        all_accounts=True,
        target_date="2026-07-02",
    )

    assert exit_code == 0
    build_call = next(call for call in calls if call[0] == "build_account_ledger")
    assert build_call[1]["root"] == tmp_path
    assert build_call[1]["current_brief_date"] == "2026-07-02"
    assert build_call[1]["account"] is account
    assert build_call[1]["local_history_cfg"] == {"path": "data/a_share_history.sqlite"}
    assert build_call[1]["current_watchlist"]["股票代码"].tolist() == ["SH.600000"]
    assert (
        "export_account_bill",
        {
            "config_path": tmp_path / "config.yaml",
            "brief_date": "2026-07-02",
            "account_id": "default",
        },
    ) in calls
    assert ("sync_bill", {"local_dir": tmp_path / "reports" / "account_bill_today"}) in calls
    assert (tmp_path / "reports" / "runs" / "latest" / "accounts" / "default" / "account_bill" / "index.html").read_text(
        encoding="utf-8"
    ) == "<html>confirmed bill</html>"
    assert (tmp_path / "reports" / "runs" / "latest" / "account_bill" / "index.html").read_text(encoding="utf-8") == (
        "<html>confirmed bill</html>"
    )
    assert (tmp_path / "reports" / "account_bill_today" / "index.html").read_text(encoding="utf-8") == "<html>confirmed bill</html>"


def test_confirm_account_bills_returns_failure_when_today_is_not_confirmed(monkeypatch, tmp_path: Path) -> None:
    watchlist_path = (
        tmp_path
        / "reports"
        / "runs"
        / "2026-07-02"
        / "20260702_072000__premarket__default"
        / "premarket__watchlist.csv"
    )
    watchlist_path.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "盘前检查时间": "2026-07-02 07:20:00",
                "账户ID": "default",
                "策略ID": "strategy_a",
                "股票代码": "SH.600000",
                "股票名称": "浦发银行",
                "收盘价": "10.00",
                "目标权重": "10.00%",
                "权重变化": "10.00%",
            }
        ]
    ).to_csv(watchlist_path, index=False, encoding="utf-8-sig")

    account = SimpleNamespace(account_id="default", strategy_id="strategy_a")
    export_calls: list[dict[str, object]] = []

    monkeypatch.setattr(delivery_cli, "load_config", lambda path: {"reporting": {}, "local_history": {}})
    monkeypatch.setattr(delivery_cli, "load_simulated_accounts", lambda cfg, root: [account])
    monkeypatch.setattr(delivery_cli, "build_account_ledger", lambda **kwargs: (pd.DataFrame(), {}))
    monkeypatch.setattr(delivery_cli, "export_brief_account_bill", lambda **kwargs: export_calls.append(kwargs))
    monkeypatch.setattr(delivery_cli, "_sync_account_bill_to_cloud", lambda console, local_dir: None)
    monkeypatch.setattr(delivery_cli, "build_quant_static_site", lambda **kwargs: {"site_root": tmp_path / "reports" / "static_site" / "quant"})
    monkeypatch.setattr(delivery_cli, "sync_quant_static_site", lambda **kwargs: {"remote": "deploy@example", "remote_dir": "/var/www/spidermanread/quant/"})
    monkeypatch.setattr(delivery_cli, "Console", lambda: _silent_console())

    exit_code = delivery_cli.confirm_account_bills_pipeline(
        config_path=tmp_path / "config.yaml",
        all_accounts=True,
        target_date="2026-07-02",
    )

    assert exit_code == 1
    assert export_calls == []


def test_watchlist_pipeline_forwards_as_of_date(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_export_premarket(**kwargs):
        calls.append(("export_premarket", kwargs))
        report = tmp_path / "watchlist.html"
        report.write_text("<html>watchlist</html>", encoding="utf-8")
        (report.parent / "style.css").write_text("body{}", encoding="utf-8")
        return {
            "watchlist": tmp_path / "watchlist.csv",
            "report": report,
            "rows": 1,
            "signal_date": "2026-06-30",
            "check_time": "2026-07-01 07:30",
            "account_bill": Path(""),
        }

    monkeypatch.setattr(delivery_cli, "load_config", lambda path: {"reporting": {}})
    monkeypatch.setattr(delivery_cli, "export_premarket", fake_export_premarket)
    monkeypatch.setattr(delivery_cli, "_sync_watchlist_to_remote", lambda console, local_dir: None)
    monkeypatch.setattr(delivery_cli, "build_quant_static_site", lambda **kwargs: {"site_root": tmp_path / "reports" / "static_site" / "quant"})
    monkeypatch.setattr(delivery_cli, "sync_quant_static_site", lambda **kwargs: {"remote": "deploy@example", "remote_dir": "/var/www/spidermanread/quant/"})
    monkeypatch.setattr(delivery_cli, "BRIEF_TODAY_MIRROR", tmp_path / "external" / "brief_today" / "index.html")
    monkeypatch.setattr(delivery_cli, "Console", lambda: _silent_console())

    exit_code = delivery_cli.run_watchlist_pipeline(
        config_path=tmp_path / "config.yaml",
        skip_update=True,
        as_of_date="2026-06-30",
    )

    assert exit_code == 0
    assert calls[0][1]["as_of_date"] == "2026-06-30"


def test_publish_watchlist_static_assets_without_regenerating_report(monkeypatch, tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    stylesheet = source_dir / "style.css"
    stylesheet.write_text(":root { --focus-strong:#eaa549; }", encoding="utf-8")
    for html_path in [
        tmp_path / "reports" / "runs" / "latest" / "watchlist" / "index.html",
        tmp_path / "reports" / "watchlist_today" / "index.html",
        tmp_path / "external" / "brief_today" / "index.html",
    ]:
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text("<html>existing</html>", encoding="utf-8")
    calls: list[tuple[str, dict[str, object]]] = []

    def fail_export(**kwargs):
        raise AssertionError("static asset publish must not regenerate watchlist")

    def fake_sync(console, local_dir: Path) -> None:
        calls.append(("sync", {"local_dir": local_dir}))

    monkeypatch.setattr(delivery_cli, "export_premarket", fail_export)
    monkeypatch.setattr(delivery_cli, "_sync_watchlist_to_remote", fake_sync)
    monkeypatch.setattr(delivery_cli, "BRIEF_TODAY_MIRROR", tmp_path / "external" / "brief_today" / "index.html")

    published = delivery_cli.publish_watchlist_static_assets(
        root=tmp_path,
        config={"reporting": {}},
        source_dir=source_dir,
        console=_silent_console(),
    )

    assert sorted(path.relative_to(tmp_path).as_posix() for path in published) == [
        "external/brief_today/style.css",
        "reports/runs/latest/watchlist/style.css",
        "reports/watchlist_today/style.css",
    ]
    assert ("sync", {"local_dir": tmp_path / "reports" / "watchlist_today"}) in calls
    assert (tmp_path / "reports" / "watchlist_today" / "index.html").read_text(encoding="utf-8") == "<html>existing</html>"
    assert (tmp_path / "reports" / "watchlist_today" / "style.css").read_text(encoding="utf-8") == stylesheet.read_text(
        encoding="utf-8"
    )


def test_watchlist_pipeline_check_only_stops_before_export(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    monkeypatch.setattr(delivery_cli, "load_config", lambda path: {"reporting": {}})
    monkeypatch.setattr(
        delivery_cli,
        "update_manual_history_from_config",
        lambda cfg, root, *, check_only: _history_result(ok=True, inserted_rows=0),
    )
    monkeypatch.setattr(delivery_cli, "Console", lambda: _silent_console())

    def fake_export_premarket(**kwargs):
        calls.append("export")
        return {}

    monkeypatch.setattr(delivery_cli, "export_premarket", fake_export_premarket)

    exit_code = delivery_cli.run_watchlist_pipeline(
        config_path=tmp_path / "config.yaml",
        skip_update=False,
        check_only=True,
    )

    assert exit_code == 0
    assert calls == []


def test_watchlist_pipeline_skips_account_bill_sync_when_bill_is_missing(monkeypatch, tmp_path: Path) -> None:
    report = tmp_path / "report.html"
    report.write_text("<html>watchlist</html>", encoding="utf-8")
    calls: list[tuple[str, dict[str, object]]] = []

    monkeypatch.setattr(delivery_cli, "load_config", lambda path: {"reporting": {}})
    monkeypatch.setattr(
        delivery_cli,
        "export_premarket",
        lambda **kwargs: {
            "watchlist": tmp_path / "watchlist.csv",
            "report": report,
            "rows": 3,
            "signal_date": "2026-06-25",
            "check_time": "2026-06-25 07:30:00",
            "account_bill": Path(""),
        },
    )
    monkeypatch.setattr(delivery_cli, "_sync_watchlist_to_remote", lambda console, local_dir: calls.append(("watchlist_sync", {"local_dir": local_dir})))
    monkeypatch.setattr(delivery_cli, "_sync_account_bill_to_cloud", lambda console, local_dir: calls.append(("bill_sync", {"local_dir": local_dir})))
    monkeypatch.setattr(delivery_cli, "build_quant_static_site", lambda **kwargs: {"site_root": tmp_path / "reports" / "static_site" / "quant"})
    monkeypatch.setattr(delivery_cli, "sync_quant_static_site", lambda **kwargs: {"remote": "deploy@example", "remote_dir": "/var/www/spidermanread/quant/"})
    monkeypatch.setattr(delivery_cli, "BRIEF_TODAY_MIRROR", tmp_path / "external" / "brief_today" / "index.html")
    monkeypatch.setattr(delivery_cli, "Console", lambda: _silent_console())

    exit_code = delivery_cli.run_watchlist_pipeline(
        config_path=tmp_path / "config.yaml",
        skip_update=True,
    )

    assert exit_code == 0
    assert ("watchlist_sync", {"local_dir": tmp_path / "reports" / "watchlist_today"}) in calls
    assert not any(call[0] == "bill_sync" for call in calls)
    assert not (tmp_path / "reports" / "account_bill_today" / "index.html").exists()


def test_delivery_handler_forwards_premarket_and_account_bill(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    bill = tmp_path / "account_bill.html"
    bill.write_text("<html>account bill</html>", encoding="utf-8")
    stylesheet = tmp_path / "style.css"
    stylesheet.write_text(":root { --text: #45373c; }", encoding="utf-8")

    def fake_export_premarket(**kwargs):
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
            "account_bill": bill,
        }

    def fake_sync(console, local_dir: Path) -> None:
        calls.append(("sync", {"local_dir": local_dir}))

    monkeypatch.setattr(delivery_cli, "export_premarket", fake_export_premarket)
    monkeypatch.setattr(delivery_cli, "export_brief_account_bill", fake_export_brief_account_bill)
    monkeypatch.setattr(delivery_cli, "_sync_account_bill_to_cloud", fake_sync)
    monkeypatch.setattr(delivery_cli, "load_config", lambda path: {"reporting": {}})

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
                    "as_of_date": None,
                },
            ),
        (
            "account_bill",
            {
                "config_path": (tmp_path / "config.yaml").resolve(),
                "brief_date": "2026-06-25",
            },
        ),
        ("sync", {"local_dir": (tmp_path / "reports" / "account_bill_today").resolve()}),
    ]
    assert (tmp_path / "reports" / "runs" / "latest" / "account_bill" / "index.html").read_text(encoding="utf-8") == "<html>account bill</html>"
    assert (tmp_path / "reports" / "account_bill_today" / "index.html").read_text(encoding="utf-8") == "<html>account bill</html>"
    assert (tmp_path / "reports" / "runs" / "latest" / "account_bill" / "style.css").read_text(encoding="utf-8") == stylesheet.read_text(
        encoding="utf-8"
    )
    assert (tmp_path / "reports" / "account_bill_today" / "style.css").read_text(encoding="utf-8") == stylesheet.read_text(encoding="utf-8")


def test_delivery_handler_forwards_confirm_account_bills(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_confirm_account_bills_pipeline(**kwargs):
        calls.append(kwargs)
        return 0

    monkeypatch.setattr(delivery_cli, "confirm_account_bills_pipeline", fake_confirm_account_bills_pipeline)

    exit_code = delivery_cli.handle_delivery_command(
        SimpleNamespace(
            cmd="brief",
            brief_cmd="confirm-account-bills",
            config=str(tmp_path / "config.yaml"),
            account_id="default",
            all_accounts=False,
            date="2026-07-02",
            as_of_date=None,
        ),
        parser=argparse.ArgumentParser(),
        console=_silent_console(),
    )

    assert exit_code == 0
    assert calls == [
        {
            "config_path": (tmp_path / "config.yaml").resolve(),
            "account_id": "default",
            "all_accounts": False,
            "target_date": "2026-07-02",
        }
    ]


def test_cli_main_delegates_delivery_commands(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str | None, bool]] = []

    def fake_handle_delivery_command(args, *, parser):
        calls.append((args.cmd, getattr(args, "brief_cmd", None), parser is not None))
        return 0

    monkeypatch.setattr(cli, "handle_delivery_command", fake_handle_delivery_command)
    monkeypatch.setattr("sys.argv", ["quant.cli", "brief", "watchlist", "--config", str(tmp_path / "config.yaml")])

    assert cli.main() == 0
    assert calls == [("brief", "watchlist", True)]
