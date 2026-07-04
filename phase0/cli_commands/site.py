from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from rich.console import Console

from phase0.config import load_config
from phase0.execution.accounts import load_simulated_accounts
from phase0.reporting.quant_static_site import build_quant_static_site, quant_site_root, sync_quant_static_site


SITE_COMMANDS = frozenset({"site"})


def register_site_commands(subparsers: argparse._SubParsersAction) -> None:
    site_parser = subparsers.add_parser("site", help="Build and publish static quant account console")
    site_sub = site_parser.add_subparsers(dest="site_cmd")
    build_parser = site_sub.add_parser("build", help="Build local /quant/ static console")
    build_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    for command_name, help_text in [
        ("sync", "Sync existing local /quant/ static console to remote"),
        ("publish", "Build local /quant/ static console and sync it to remote"),
    ]:
        parser = site_sub.add_parser(command_name, help=help_text)
        parser.add_argument("--config", default="config.yaml", help="Path to config file")
        parser.add_argument("--remote", default=None, help="Remote rsync host, e.g. user@example")
        parser.add_argument("--remote-dir", default=None, help="Remote directory; must end with /quant/")


def _build_site(config_path: Path) -> dict[str, Any]:
    config = load_config(config_path)
    root = config_path.parent
    accounts = load_simulated_accounts(config, root)
    return build_quant_static_site(root=root, config=config, accounts=accounts)


def handle_site_command(args: argparse.Namespace, *, parser: argparse.ArgumentParser, console: Any | None = None) -> int:
    site_console = console or Console()
    if args.cmd != "site":
        parser.error("site command expected")
    if args.site_cmd not in {"build", "sync", "publish"}:
        parser.error("site requires a subcommand: build, sync, or publish")

    config_path = Path(args.config).resolve()
    config = load_config(config_path)
    root = config_path.parent
    site_root = quant_site_root(root=root, config=config)

    if args.site_cmd in {"build", "publish"}:
        result = _build_site(config_path)
        site_root = Path(result["site_root"])
        site_console.print("[green]Quant static site build complete[/green]")
        site_console.print(f"Site root: {site_root}")
        site_console.print(f"Accounts: {result['accounts']}")

    if args.site_cmd in {"sync", "publish"}:
        sync_result = sync_quant_static_site(
            root=root,
            site_root=site_root,
            remote=args.remote,
            remote_dir=args.remote_dir,
        )
        site_console.print("[green]Quant static site sync complete[/green]")
        site_console.print(f"Remote: {sync_result['remote']}:{sync_result['remote_dir']}")

    return 0
