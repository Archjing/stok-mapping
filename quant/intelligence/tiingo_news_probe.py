from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from quant.config import load_config
from quant.data_access.connectivity import DEFAULT_TIINGO_NEWS_SYMBOLS, fetch_tiingo_news
from quant.reporting.paths import report_config_path


DEFAULT_OUTPUT = "archive/intelligence/tiingo_news_probe_report.md"


def _resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _parse_csv_arg(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in str(raw).split(",") if part.strip()]


def _summarize(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {"rows": 0, "latest": "", "sample_titles": []}
    latest = ""
    if "published_date" in df.columns and not df["published_date"].isna().all():
        latest = str(pd.to_datetime(df["published_date"]).max())
    return {
        "rows": int(len(df)),
        "latest": latest,
        "sample_titles": [str(x) for x in df["title"].head(3).tolist()],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe Tiingo News API permission and filter behavior.",
    )
    parser.add_argument("--tickers", default=",".join(DEFAULT_TIINGO_NEWS_SYMBOLS))
    parser.add_argument("--tags", default="technology")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--token-env", default="TIINGO_API_TOKEN")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    root = Path.cwd()
    config_path = _resolve_path(root, args.config)
    config = load_config(config_path)
    load_dotenv(Path(".env"))

    end = date.today()
    start = end - timedelta(days=max(1, int(args.days)))
    tickers = _parse_csv_arg(args.tickers)
    tags = _parse_csv_arg(args.tags)

    probes: list[tuple[str, dict[str, Any]]] = [
        (
            "tickers_only",
            {
                "tickers": tickers,
                "tags": [],
                "start": None,
                "end": None,
                "limit": args.limit,
                "token_env": args.token_env,
            },
        ),
        (
            "tags_only",
            {
                "tickers": [],
                "tags": tags,
                "start": None,
                "end": None,
                "limit": args.limit,
                "token_env": args.token_env,
            },
        ),
        (
            "time_window_only",
            {
                "tickers": [],
                "tags": [],
                "start": start,
                "end": end,
                "limit": args.limit,
                "token_env": args.token_env,
            },
        ),
        (
            "combined_filters",
            {
                "tickers": tickers,
                "tags": tags,
                "start": start,
                "end": end,
                "limit": args.limit,
                "token_env": args.token_env,
            },
        ),
    ]

    lines = [
        "# Tiingo News Probe",
        "",
        f"- probe_date: `{date.today().isoformat()}`",
        f"- tickers: `{','.join(tickers) if tickers else '-'}`",
        f"- tags: `{','.join(tags) if tags else '-'}`",
        f"- time_window: `{start.isoformat()} -> {end.isoformat()}`",
        "",
    ]

    overall_ok = True
    for name, kwargs in probes:
        lines.append(f"## {name}")
        try:
            df = fetch_tiingo_news(**kwargs)
            summary = _summarize(df)
            lines.append(f"- status: `ok`")
            lines.append(f"- rows: `{summary['rows']}`")
            lines.append(f"- latest: `{summary['latest'] or '-'}`")
            lines.append(f"- sample_titles: `{'; '.join(summary['sample_titles']) if summary['sample_titles'] else '-'}`")
        except Exception as exc:
            overall_ok = False
            lines.append(f"- status: `error`")
            lines.append(f"- error: `{exc}`")
        lines.append("")

    if not overall_ok:
        lines.append("## Conclusion")
        lines.append("")
        lines.append("- Current token cannot fully validate Tiingo News API behavior. Check permission and rerun.")

    output_path = (
        _resolve_path(root, args.output)
        if args.output is not None
        else report_config_path(root=root, config=config, value=DEFAULT_OUTPUT)
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
