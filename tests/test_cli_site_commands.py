from __future__ import annotations

import argparse
from pathlib import Path

import phase0.cli as cli
import phase0.cli_commands.site as site_cli


def test_site_command_registration_supports_build_sync_publish() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd")
    site_cli.register_site_commands(subparsers)

    build = parser.parse_args(["site", "build", "--config", "config.yaml"])
    sync = parser.parse_args(["site", "sync", "--config", "config.yaml"])
    publish = parser.parse_args(["site", "publish", "--config", "config.yaml"])

    assert build.cmd == "site"
    assert build.site_cmd == "build"
    assert sync.site_cmd == "sync"
    assert publish.site_cmd == "publish"


def test_site_build_uses_enabled_accounts(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, object]] = []

    class Account:
        account_id = "default"

    def fake_load_config(path: Path) -> dict:
        calls.append(("load_config", path))
        return {"reporting": {}}

    def fake_load_accounts(config: dict, root: Path) -> list[Account]:
        calls.append(("load_accounts", root))
        return [Account()]

    def fake_build(*, root: Path, config: dict, accounts: list[Account]) -> dict:
        calls.append(("build", [account.account_id for account in accounts]))
        return {"site_root": root / "reports" / "static_site" / "quant", "accounts": len(accounts)}

    monkeypatch.setattr(site_cli, "load_config", fake_load_config)
    monkeypatch.setattr(site_cli, "load_simulated_accounts", fake_load_accounts)
    monkeypatch.setattr(site_cli, "build_quant_static_site", fake_build)

    exit_code = site_cli.handle_site_command(
        argparse.Namespace(cmd="site", site_cmd="build", config=str(tmp_path / "config.yaml"), remote=None, remote_dir=None),
        parser=argparse.ArgumentParser(),
    )

    assert exit_code == 0
    assert ("build", ["default"]) in calls


def test_site_publish_builds_then_syncs(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(site_cli, "load_config", lambda path: {"reporting": {}})
    monkeypatch.setattr(site_cli, "load_simulated_accounts", lambda config, root: [])

    def fake_build(*, root: Path, config: dict, accounts: list) -> dict:
        site_root = root / "reports" / "static_site" / "quant"
        calls.append(("build", site_root))
        return {"site_root": site_root, "accounts": 0}

    def fake_sync(*, root: Path, site_root: Path, remote: str | None = None, remote_dir: str | None = None) -> dict:
        calls.append(("sync", site_root))
        return {"remote": "deploy@example", "remote_dir": "/var/www/spidermanread/quant/"}

    monkeypatch.setattr(site_cli, "build_quant_static_site", fake_build)
    monkeypatch.setattr(site_cli, "sync_quant_static_site", fake_sync)

    exit_code = site_cli.handle_site_command(
        argparse.Namespace(cmd="site", site_cmd="publish", config=str(tmp_path / "config.yaml"), remote=None, remote_dir=None),
        parser=argparse.ArgumentParser(),
    )

    assert exit_code == 0
    assert [item[0] for item in calls] == ["build", "sync"]


def test_cli_main_delegates_site_commands(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str | None, bool]] = []

    def fake_handle_site_command(args, *, parser):
        calls.append((args.cmd, getattr(args, "site_cmd", None), parser is not None))
        return 0

    monkeypatch.setattr(cli, "handle_site_command", fake_handle_site_command)
    monkeypatch.setattr("sys.argv", ["phase0.cli", "site", "build", "--config", str(tmp_path / "config.yaml")])

    assert cli.main() == 0
    assert calls == [("site", "build", True)]
