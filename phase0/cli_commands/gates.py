from __future__ import annotations

from pathlib import Path

from rich.console import Console

from phase0.data_governance.db_health import run_database_health_check


def run_db_health_gate(
    *,
    console: Console,
    config: dict,
    root: Path,
    scope: str,
    fail_on: str,
    label: str,
) -> int:
    console.print(f"[bold]{label} data health check started[/bold]")
    result = run_database_health_check(
        config=config,
        root=root,
        scope=scope,
        output_dir=None,
    )
    color = "green" if result.status == "pass" else ("yellow" if result.status == "warning" else "red")
    console.print(
        f"[{color}]{label} data health status: {result.status}[/{color}] "
        f"(errors={result.error_count}, warnings={result.warning_count}, info={result.info_count})"
    )
    console.print(f"Health report: {result.summary_md}")
    if fail_on == "error" and result.error_count > 0:
        return 2
    if fail_on == "warning" and (result.error_count > 0 or result.warning_count > 0):
        return 2
    return 0
