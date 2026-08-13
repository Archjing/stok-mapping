from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from rich.console import Console

from quant.ai_corpus import (
    DEFAULT_REFERENCE_DIR,
    fetch_ai_corpus,
    get_provider_spec,
    probe_gov_policy_source,
    provider_registry_rows,
    query_ai_corpus_documents,
    upsert_ai_corpus_documents,
)
from quant.ai_corpus.registry import canonical_provider_name
from quant.ai_corpus.schema import select_fields
from quant.config import load_config

AI_CORPUS_COMMANDS = {"ai-corpus"}
DEFAULT_GOV_POLICY_PROBE_REPORT = "reports/phase0/ai_corpus/probes/gov_policy_probe_%Y%m%dT%H%M%S.json"


def _ai_corpus_config(cfg: dict[str, Any]) -> dict[str, Any]:
    return cfg.get("ai_corpus", {})


def _default_db_path(root: Path, cfg: dict[str, Any], override: str | None = None) -> Path:
    raw = override or _ai_corpus_config(cfg).get("database_path", "data/ai_corpus/ai_corpus.sqlite")
    path = Path(raw)
    return path if path.is_absolute() else root / path


def _default_archive_dir(cfg: dict[str, Any], *, provider_default: str, override: str | None = None) -> str:
    return override or _ai_corpus_config(cfg).get("raw_archive_dir") or provider_default


def _provider_config(cfg: dict[str, Any], provider: str) -> dict[str, Any]:
    value = _ai_corpus_config(cfg).get(provider, {})
    return value if isinstance(value, dict) else {}


def _merge_source_urls(provider_config: dict[str, Any], cli_urls: list[str] | None) -> dict[str, Any]:
    """Merge --source-url CLI values into the provider config."""
    merged = dict(provider_config or {})
    if cli_urls:
        existing = list(merged.get("source_urls") or [])
        merged["source_urls"] = existing + [url for url in cli_urls if url not in existing]
    return merged


def _parse_fields(raw: str | None) -> list[str] | None:
    return [item.strip() for item in raw.split(",") if item.strip()] if raw else None


def _write_frame(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _resolve_output_path(root: Path, raw: str | Path) -> Path:
    expanded = datetime.now().strftime(str(raw))
    path = Path(expanded)
    return path if path.is_absolute() else root / path


def _write_json_report(root: Path, raw: str | Path, payload: dict[str, Any]) -> Path:
    path = _resolve_output_path(root, raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _add_probe_audit_arguments(command_parser: argparse.ArgumentParser) -> None:
    command_parser.add_argument("--min-probe-rows", type=int, default=1, help="Minimum rows required for gov-policy source probe")
    command_parser.add_argument("--min-probe-topics", type=int, default=1, help="Minimum effective topic mappings required for gov-policy probe")
    command_parser.add_argument("--min-probe-departments", type=int, default=0, help="Minimum effective department mappings required for gov-policy probe")
    command_parser.add_argument("--min-probe-content-chars", type=int, default=200, help="Minimum raw text length for sample gov-policy content page")
    command_parser.add_argument(
        "--require-topic-tree",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require ztflTree in gov-policy probe response",
    )
    command_parser.add_argument(
        "--require-content-html",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require content_html in sample gov-policy content probe",
    )


def _probe_audit_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "min_rows": int(getattr(args, "min_probe_rows", 1) or 1),
        "require_topic_tree": bool(getattr(args, "require_topic_tree", True)),
        "min_topic_count": int(getattr(args, "min_probe_topics", 1) or 1),
        "min_department_count": int(getattr(args, "min_probe_departments", 0) or 0),
        "require_content_html": bool(getattr(args, "require_content_html", True)),
        "min_content_raw_text_length": int(getattr(args, "min_probe_content_chars", 200) or 0),
    }


def _probe_report_ok(report: dict[str, Any]) -> bool:
    audit = report.get("audit")
    if isinstance(audit, dict) and "ok" in audit:
        return bool(report.get("ok")) and bool(audit.get("ok"))
    return bool(report.get("ok"))


def _print_probe_audit_summary(report: dict[str, Any], console: Console, *, prefix: str = "Audit") -> None:
    audit = report.get("audit")
    if not isinstance(audit, dict):
        return
    console.print(f"{prefix} OK: {audit.get('ok')}")
    console.print(f"{prefix} errors: {audit.get('error_count', 0)}")
    console.print(f"{prefix} warnings: {audit.get('warning_count', 0)}")


def _print_markdown(frame: pd.DataFrame, console: Console) -> None:
    if frame.empty:
        console.print("No rows.")
        return
    columns = [column for column in ["published_at", "title", "org", "pcode", "url"] if column in frame.columns]
    console.print("| " + " | ".join(columns) + " |")
    console.print("| " + " | ".join(["---"] * len(columns)) + " |")
    for _, row in frame[columns].iterrows():
        console.print("| " + " | ".join(str(row.get(column, "")).replace("|", "/") for column in columns) + " |")


def register_ai_corpus_commands(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("ai-corpus", help="Fetch, store, and query local AI corpus documents")
    ai_sub = parser.add_subparsers(dest="ai_corpus_cmd")

    registry_parser = ai_sub.add_parser("registry", help="Show AI corpus provider registry")
    registry_parser.add_argument("--config", default="config.yaml", help="Path to config file")

    probe_parser = ai_sub.add_parser("probe", help="Probe provider source health and emit a machine-readable report")
    probe_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    probe_parser.add_argument("--provider", default="gov-policy", help="Provider name")
    probe_parser.add_argument("--collection", default="all", help="Provider collection, for example all/department/gazette")
    probe_parser.add_argument("--org", default="国务院", help="Publishing organization")
    probe_parser.add_argument("--ptype", default="科技", help="Policy topic")
    probe_parser.add_argument("--keyword", default="人工智能", help="Keyword query")
    probe_parser.add_argument("--start-date", default=None, help="Published start date")
    probe_parser.add_argument("--end-date", default=None, help="Published end date")
    probe_parser.add_argument("--reference-dir", default=None, help="Override provider reference cache directory")
    probe_parser.add_argument(
        "--refresh-reference",
        action="store_true",
        help="Refresh provider reference cache before probing",
    )
    probe_parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout seconds")
    probe_parser.add_argument("--no-content", action="store_true", help="Skip content page parser probe")
    probe_parser.add_argument("--output-json", default=None, help="Optional JSON report path")
    _add_probe_audit_arguments(probe_parser)

    fetch_parser = ai_sub.add_parser("fetch", help="Fetch provider rows and upsert them into the local AI corpus database")
    fetch_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    fetch_parser.add_argument("--provider", default="gov-policy", help="Provider name, for example gov-policy/npr/cctv-news/cninfo/us-market-news")
    fetch_parser.add_argument("--event-type", default=None, help="Event type for event providers, for example risk_events/abnormal_trading")
    fetch_parser.add_argument("--org", default=None, help="Publishing organization, for example 国务院 or 工业和信息化部")
    fetch_parser.add_argument("--ptype", default=None, help="Policy topic, for example 科技")
    fetch_parser.add_argument("--keyword", default=None, help="Keyword query")
    fetch_parser.add_argument("--symbols", default=None, help="Comma-separated symbol filters for providers that support symbol search")
    fetch_parser.add_argument("--date", default=None, help="Single program date for date-based providers such as cctv-news")
    fetch_parser.add_argument("--start-date", default=None, help="Published start date")
    fetch_parser.add_argument("--end-date", default=None, help="Published end date")
    fetch_parser.add_argument("--limit", type=int, default=100, help="Maximum rows to fetch")
    fetch_parser.add_argument("--min-rows", type=int, default=0, help="Fail when fetched rows are below this threshold")
    fetch_parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout seconds")
    fetch_parser.add_argument("--fields", default=None, help="Comma-separated output fields")
    fetch_parser.add_argument("--fixture-dir", default=None, help="Fixture directory for offline parser/provider validation")
    fetch_parser.add_argument("--database-path", default=None, help="Override local AI corpus SQLite path")
    fetch_parser.add_argument("--raw-archive-dir", default=None, help="Override raw archive directory")
    fetch_parser.add_argument("--reference-dir", default=None, help="Override provider reference cache directory")
    fetch_parser.add_argument(
        "--source-url",
        action="append",
        default=None,
        dest="source_urls",
        help="Source page URL (repeatable); for URL-driven providers such as semi-supply-chain",
    )
    fetch_parser.add_argument(
        "--refresh-reference",
        action="store_true",
        help="Refresh provider reference cache before fetching",
    )
    fetch_parser.add_argument("--output-csv", default=None, help="Optional CSV export path")
    fetch_parser.add_argument("--no-content", action="store_true", help="Fetch list rows only; skip content page parsing")
    fetch_parser.add_argument("--full-program-only", action="store_true", help="For cctv-news, fetch only the complete program row")
    fetch_parser.add_argument(
        "--probe-before-fetch",
        action="store_true",
        help="For gov-policy, run source probe first and abort fetch when the probe fails",
    )
    fetch_parser.add_argument(
        "--probe-output-json",
        default=None,
        help="JSON probe report path for --probe-before-fetch; strftime tokens are supported",
    )
    fetch_parser.add_argument("--probe-no-content", action="store_true", help="Skip content parser check in pre-fetch probe")
    _add_probe_audit_arguments(fetch_parser)

    query_parser = ai_sub.add_parser("query", help="Query the local AI corpus database")
    query_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    query_parser.add_argument("--provider", default=None, help="Provider filter")
    query_parser.add_argument("--corpus-type", default=None, help="Corpus type filter")
    query_parser.add_argument("--event-type", default=None, help="Event type filter")
    query_parser.add_argument("--keyword", default=None, help="Keyword filter")
    query_parser.add_argument("--start-date", default=None, help="Published start date")
    query_parser.add_argument("--end-date", default=None, help="Published end date")
    query_parser.add_argument("--limit", type=int, default=100, help="Maximum rows")
    query_parser.add_argument("--database-path", default=None, help="Override local AI corpus SQLite path")
    query_parser.add_argument("--format", choices=["table", "markdown", "csv"], default="table", help="Output format")
    query_parser.add_argument("--output-csv", default=None, help="CSV output path when --format csv")

    export_parser = ai_sub.add_parser("export", help="Export provider results or local query results")
    export_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    export_parser.add_argument("--provider", default="gov-policy", help="Provider name")
    export_parser.add_argument("--event-type", default=None, help="Event type filter for stored rows")
    export_parser.add_argument("--start-date", default=None, help="Published start date")
    export_parser.add_argument("--end-date", default=None, help="Published end date")
    export_parser.add_argument("--keyword", default=None, help="Keyword filter")
    export_parser.add_argument("--limit", type=int, default=100, help="Maximum rows")
    export_parser.add_argument("--database-path", default=None, help="Override local AI corpus SQLite path")
    export_parser.add_argument("--output-csv", required=True, help="CSV output path")

    event_parser = ai_sub.add_parser("event-study", help="Run an event study over corpus documents")
    event_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    event_parser.add_argument("--provider", default=None, help="Provider filter (e.g. cninfo / gov_policy)")
    event_parser.add_argument("--event-type", default=None, help="Event type filter (e.g. abnormal_trading)")
    event_parser.add_argument("--start-date", default=None, help="Published start date")
    event_parser.add_argument("--end-date", default=None, help="Published end date")
    event_parser.add_argument("--benchmark", default="SH.000300", help="Market-model benchmark symbol")
    event_parser.add_argument("--database-path", default=None, help="Override local AI corpus SQLite path")
    event_parser.add_argument("--market-db", default=None, help="Override market history SQLite path")
    event_parser.add_argument("--output-dir", default=None, help="Output directory for report + CSV")


def handle_ai_corpus_command(args: argparse.Namespace, *, parser: argparse.ArgumentParser, console: Any | None = None) -> int:
    ai_console = console or Console()
    config_path = Path(getattr(args, "config", "config.yaml")).resolve()
    cfg = load_config(config_path)
    root = config_path.parent
    if args.ai_corpus_cmd == "registry":
        for row in provider_registry_rows():
            ai_console.print(
                f"{row['name']}: status={row['status']}; corpus_types={row['corpus_types']}; parser={row['parser_version']}"
            )
        return 0
    if args.ai_corpus_cmd == "probe":
        provider = canonical_provider_name(args.provider)
        if provider != "gov_policy":
            ai_console.print(f"[yellow]Provider probe is not implemented yet: {provider}[/yellow]")
            return 2
        report = probe_gov_policy_source(
            root=root,
            org=args.org,
            ptype=args.ptype,
            keyword=args.keyword,
            start_date=args.start_date,
            end_date=args.end_date,
            collection=getattr(args, "collection", "all"),
            reference_dir=args.reference_dir or DEFAULT_REFERENCE_DIR,
            refresh_reference=bool(args.refresh_reference),
            timeout=args.timeout,
            content_probe=not args.no_content,
            **_probe_audit_kwargs(args),
        )
        output_json = getattr(args, "output_json", None)
        output_path: Path | None = None
        if output_json:
            output_path = _write_json_report(root, output_json, report)
        ai_console.print("[bold]AI corpus probe complete[/bold]")
        ai_console.print(f"Provider: {provider}")
        ai_console.print(f"OK: {report.get('ok')}")
        ai_console.print(f"Rows: {report.get('search', {}).get('row_count', 0)}")
        _print_probe_audit_summary(report, ai_console)
        if output_path:
            ai_console.print(f"JSON: {output_path}")
        if report.get("errors"):
            ai_console.print(f"[yellow]Errors: {report['errors']}[/yellow]")
        return 0 if _probe_report_ok(report) else 2
    if args.ai_corpus_cmd == "fetch":
        provider = canonical_provider_name(args.provider)
        spec = get_provider_spec(provider)
        if spec.status not in {"implemented_mvp", "fixture_mvp"}:
            ai_console.print(f"[yellow]Provider {provider} is {spec.status}; no production fetch is implemented.[/yellow]")
            return 2
        if spec.status == "fixture_mvp" and not args.fixture_dir:
            ai_console.print(f"[yellow]Provider {provider} is fixture-only; pass --fixture-dir for validation.[/yellow]")
            return 2
        start_date = args.start_date
        end_date = args.end_date
        if provider == "cctv":
            if getattr(args, "date", None):
                start_date = getattr(args, "date")
                end_date = getattr(args, "date")
            elif not start_date and not end_date:
                today = datetime.now().date().strftime("%Y%m%d")
                start_date = today
                end_date = today
        db_path = _default_db_path(root, cfg, args.database_path)
        configured_archive_dir = _provider_config(cfg, provider).get("raw_archive_dir")
        refresh_reference = bool(getattr(args, "refresh_reference", False))
        if provider == "gov_policy" and bool(getattr(args, "probe_before_fetch", False)):
            report = probe_gov_policy_source(
                root=root,
                org=args.org,
                ptype=args.ptype,
                keyword=args.keyword,
                start_date=args.start_date,
                end_date=end_date,
                collection="all",
                reference_dir=getattr(args, "reference_dir", None) or DEFAULT_REFERENCE_DIR,
                refresh_reference=refresh_reference,
                timeout=getattr(args, "timeout", 20),
                content_probe=not (bool(getattr(args, "probe_no_content", False)) or bool(args.no_content)),
                **_probe_audit_kwargs(args),
            )
            report_path = _write_json_report(
                root,
                getattr(args, "probe_output_json", None) or DEFAULT_GOV_POLICY_PROBE_REPORT,
                report,
            )
            ai_console.print("[bold]AI corpus pre-fetch probe complete[/bold]")
            ai_console.print(f"Probe OK: {report.get('ok')}")
            ai_console.print(f"Probe rows: {report.get('search', {}).get('row_count', 0)}")
            _print_probe_audit_summary(report, ai_console, prefix="Probe audit")
            ai_console.print(f"Probe JSON: {report_path}")
            if not _probe_report_ok(report):
                if report.get("errors"):
                    ai_console.print(f"[yellow]Probe errors: {report['errors']}[/yellow]")
                return 2
            refresh_reference = False
        frame = fetch_ai_corpus(
            provider=provider,
            root=root,
            event_type=getattr(args, "event_type", None),
            org=args.org,
            ptype=args.ptype,
            keyword=args.keyword,
            symbols=_parse_fields(getattr(args, "symbols", None)),
            start_date=start_date,
            end_date=end_date,
            include_content=not args.no_content,
            include_segments=not getattr(args, "full_program_only", False),
            fields=None,
            limit=args.limit,
            fixture_dir=args.fixture_dir,
            raw_archive_dir=_default_archive_dir(
                cfg,
                provider_default=spec.raw_archive_dir,
                override=args.raw_archive_dir or configured_archive_dir,
            ),
            reference_dir=getattr(args, "reference_dir", None),
            refresh_reference=refresh_reference,
            timeout=getattr(args, "timeout", 20),
            provider_config=_merge_source_urls(_provider_config(cfg, provider), getattr(args, "source_urls", None)),
        )
        min_rows = int(getattr(args, "min_rows", 0) or 0)
        if min_rows > 0 and len(frame) < min_rows:
            ai_console.print(f"[yellow]Fetched rows below --min-rows: rows={len(frame)}, min_rows={min_rows}[/yellow]")
            return 2
        changed = upsert_ai_corpus_documents(db_path, frame.to_dict(orient="records"))
        output_fields = _parse_fields(args.fields)
        output_frame = frame if not output_fields else pd.DataFrame(select_fields(frame.to_dict(orient="records"), output_fields))
        if args.output_csv:
            _write_frame(output_frame, root / args.output_csv if not Path(args.output_csv).is_absolute() else Path(args.output_csv))
        ai_console.print("[bold]AI corpus fetch complete[/bold]")
        ai_console.print(f"Provider: {provider}")
        ai_console.print(f"Rows: {len(frame)}")
        ai_console.print(f"Database: {db_path}")
        ai_console.print(f"Upsert changes: {changed}")
        return 0
    if args.ai_corpus_cmd == "query":
        db_path = _default_db_path(root, cfg, args.database_path)
        provider = canonical_provider_name(args.provider) if args.provider else None
        rows = query_ai_corpus_documents(
            db_path,
            provider=provider,
            corpus_type=args.corpus_type,
            event_type=args.event_type,
            keyword=args.keyword,
            start_date=args.start_date,
            end_date=args.end_date,
            limit=args.limit,
        )
        frame = pd.DataFrame(rows)
        if args.format == "csv":
            if not args.output_csv:
                parser.error("ai-corpus query --format csv requires --output-csv")
            _write_frame(frame, root / args.output_csv if not Path(args.output_csv).is_absolute() else Path(args.output_csv))
        elif args.format == "markdown":
            _print_markdown(frame, ai_console)
        else:
            ai_console.print(frame[["published_at", "title", "org", "pcode", "url"]].to_string(index=False) if not frame.empty else "No rows.")
        return 0
    if args.ai_corpus_cmd == "export":
        db_path = _default_db_path(root, cfg, args.database_path)
        provider = canonical_provider_name(args.provider) if args.provider else None
        rows = query_ai_corpus_documents(
            db_path,
            provider=provider,
            event_type=args.event_type,
            keyword=args.keyword,
            start_date=args.start_date,
            end_date=args.end_date,
            limit=args.limit,
        )
        output = Path(args.output_csv)
        _write_frame(pd.DataFrame(rows), output if output.is_absolute() else root / output)
        ai_console.print(f"Exported rows: {len(rows)}")
        ai_console.print(f"CSV: {output}")
        return 0
    if args.ai_corpus_cmd == "event-study":
        from quant.research.event_study.report import run_event_study

        db_path = _default_db_path(root, cfg, args.database_path)
        market_db = Path(args.market_db) if args.market_db else (root / "data/a_share_history.sqlite")
        market_db = market_db if market_db.is_absolute() else root / market_db
        output_dir = Path(args.output_dir) if args.output_dir else None
        if output_dir and not output_dir.is_absolute():
            output_dir = root / output_dir
        try:
            result = run_event_study(
                corpus_db=db_path,
                market_db=market_db,
                provider=canonical_provider_name(args.provider) if args.provider else None,
                event_type=args.event_type,
                start_date=args.start_date,
                end_date=args.end_date,
                benchmark=args.benchmark,
                output_dir=output_dir,
            )
        except ValueError as exc:
            ai_console.print(f"[yellow]Event study failed: {exc}[/yellow]")
            return 2
        ai_console.print("[bold]Event study complete[/bold]")
        ai_console.print(f"Events: {result.n_events}")
        ai_console.print(f"Linked: {result.n_linked}")
        ai_console.print(f"Report: {result.report_md_path}")
        ai_console.print(f"Detail CSV: {result.detail_csv_path}")
        return 0
    parser.error("ai-corpus requires a subcommand: registry, probe, fetch, query, export, or event-study")
    return 2
