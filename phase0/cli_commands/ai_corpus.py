from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd
from rich.console import Console

from phase0.ai_corpus import (
    fetch_ai_corpus,
    get_provider_spec,
    provider_registry_rows,
    query_ai_corpus_documents,
    upsert_ai_corpus_documents,
)
from phase0.ai_corpus.registry import canonical_provider_name
from phase0.ai_corpus.schema import select_fields
from phase0.config import load_config

AI_CORPUS_COMMANDS = {"ai-corpus"}


def _ai_corpus_config(cfg: dict[str, Any]) -> dict[str, Any]:
    return cfg.get("ai_corpus", {})


def _default_db_path(root: Path, cfg: dict[str, Any], override: str | None = None) -> Path:
    raw = override or _ai_corpus_config(cfg).get("database_path", "data/ai_corpus/ai_corpus.sqlite")
    path = Path(raw)
    return path if path.is_absolute() else root / path


def _default_archive_dir(cfg: dict[str, Any], *, provider_default: str, override: str | None = None) -> str:
    return override or _ai_corpus_config(cfg).get("raw_archive_dir") or provider_default


def _parse_fields(raw: str | None) -> list[str] | None:
    return [item.strip() for item in raw.split(",") if item.strip()] if raw else None


def _write_frame(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


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

    fetch_parser = ai_sub.add_parser("fetch", help="Fetch provider rows and upsert them into the local AI corpus database")
    fetch_parser.add_argument("--config", default="config.yaml", help="Path to config file")
    fetch_parser.add_argument("--provider", default="gov-policy", help="Provider name, for example gov-policy/npr/cctv-news")
    fetch_parser.add_argument("--org", default=None, help="Publishing organization, for example 国务院 or 工业和信息化部")
    fetch_parser.add_argument("--ptype", default=None, help="Policy topic, for example 科技")
    fetch_parser.add_argument("--keyword", default=None, help="Keyword query")
    fetch_parser.add_argument("--start-date", default=None, help="Published start date")
    fetch_parser.add_argument("--end-date", default=None, help="Published end date")
    fetch_parser.add_argument("--limit", type=int, default=100, help="Maximum rows to fetch")
    fetch_parser.add_argument("--fields", default=None, help="Comma-separated output fields")
    fetch_parser.add_argument("--fixture-dir", default=None, help="Fixture directory for offline parser/provider validation")
    fetch_parser.add_argument("--database-path", default=None, help="Override local AI corpus SQLite path")
    fetch_parser.add_argument("--raw-archive-dir", default=None, help="Override raw archive directory")
    fetch_parser.add_argument("--output-csv", default=None, help="Optional CSV export path")
    fetch_parser.add_argument("--no-content", action="store_true", help="Fetch list rows only; skip content page parsing")

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
    if args.ai_corpus_cmd == "fetch":
        provider = canonical_provider_name(args.provider)
        spec = get_provider_spec(provider)
        if spec.status not in {"implemented_mvp", "fixture_mvp"}:
            ai_console.print(f"[yellow]Provider {provider} is {spec.status}; no production fetch is implemented.[/yellow]")
            return 2
        if spec.status == "fixture_mvp" and not args.fixture_dir:
            ai_console.print(f"[yellow]Provider {provider} is fixture-only; pass --fixture-dir for validation.[/yellow]")
            return 2
        db_path = _default_db_path(root, cfg, args.database_path)
        frame = fetch_ai_corpus(
            provider=provider,
            root=root,
            org=args.org,
            ptype=args.ptype,
            keyword=args.keyword,
            start_date=args.start_date,
            end_date=args.end_date,
            include_content=not args.no_content,
            fields=None,
            limit=args.limit,
            fixture_dir=args.fixture_dir,
            raw_archive_dir=_default_archive_dir(cfg, provider_default=spec.raw_archive_dir, override=args.raw_archive_dir),
        )
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
    parser.error("ai-corpus requires a subcommand: registry, fetch, query, or export")
    return 2
