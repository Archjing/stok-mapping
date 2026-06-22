from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import feedparser
import pandas as pd
import requests

from phase0.config import load_config

LEDGER_COLUMNS = [
    "intelligence_id",
    "title",
    "source_type",
    "source_path_or_url",
    "published_at",
    "collected_at",
    "market_scope",
    "topic_tags",
    "strategy_tags",
    "evidence_type",
    "quality_score",
    "novelty_score",
    "actionability_score",
    "data_availability",
    "bias_risk",
    "recommended_action",
    "status",
    "linked_strategy_task",
    "reviewed_at",
]

VALID_STATUSES = {
    "collected",
    "screened",
    "evaluated",
    "translated",
    "experiment_planned",
    "accepted",
    "rejected",
    "archived",
}

VALID_DATA_AVAILABILITY = {"ready", "partial", "missing", "external_required"}


@dataclass(frozen=True)
class IntelligenceResult:
    status: str
    rows: int
    candidates_csv: Path | None = None
    report_md: Path | None = None
    warnings: list[str] | None = None


@dataclass(frozen=True)
class IntelligenceValidationResult:
    status: str
    row_count: int
    error_count: int
    warning_count: int
    report_md: Path | None
    errors: list[str]
    warnings: list[str]


def _resolve_path(root: Path, raw: str | Path) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else root / path


def _date_tag() -> str:
    return date.today().isoformat()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _configured_path(
    *,
    root: Path,
    intel_cfg: dict[str, Any],
    override: str | Path | None,
    config_key: str,
    fallback: str,
) -> Path:
    raw = override or intel_cfg.get(config_key) or fallback
    return _resolve_path(root, raw)


def _candidate_id(source_type: str, source: str, title: str, published_at: str) -> str:
    raw = "|".join([source_type, source, title, published_at])
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"INT-AUTO-{digest}"


def _topic_tags_from_text(text: str) -> str:
    lowered = text.lower()
    tags: list[str] = []
    patterns = [
        ("machine-learning", ["machine learning", "机器学习", "xgboost", "random forest", "svm"]),
        ("deep-learning", ["deep learning", "transformer", "lstm", "gnn", "reinforcement"]),
        ("multifactor", ["multi-factor", "multifactor", "多因子", "factor"]),
        ("portfolio", ["portfolio", "组合", "asset allocation"]),
        ("sentiment", ["sentiment", "情绪", "news", "text", "文本"]),
        ("volatility", ["volatility", "波动"]),
        ("risk", ["risk", "风险", "drawdown"]),
    ]
    for tag, needles in patterns:
        if any(needle in lowered for needle in needles):
            tags.append(tag)
    return ";".join(dict.fromkeys(tags))


def _strategy_tags_from_topics(topics: str) -> str:
    mapping = {
        "machine-learning": "ml-ranking",
        "deep-learning": "ml-baseline",
        "multifactor": "factor-model",
        "portfolio": "portfolio-construction",
        "sentiment": "text-event",
        "volatility": "volatility-overlay",
        "risk": "risk-control",
    }
    tags = [mapping[item] for item in topics.split(";") if item in mapping]
    return ";".join(dict.fromkeys(tags))


def _candidate_row(
    *,
    title: str,
    source_type: str,
    source_path_or_url: str,
    published_at: str = "",
    market_scope: str = "",
    evidence_type: str = "metadata",
    topic_tags: str = "",
    strategy_tags: str = "",
) -> dict[str, str]:
    title = title.strip()
    source_path_or_url = source_path_or_url.strip()
    published_at = published_at.strip()
    topics = topic_tags or _topic_tags_from_text(" ".join([title, source_path_or_url]))
    strategies = strategy_tags or _strategy_tags_from_topics(topics)
    return {
        "intelligence_id": _candidate_id(source_type, source_path_or_url, title, published_at),
        "title": title,
        "source_type": source_type,
        "source_path_or_url": source_path_or_url,
        "published_at": published_at,
        "collected_at": _date_tag(),
        "market_scope": market_scope,
        "topic_tags": topics,
        "strategy_tags": strategies,
        "evidence_type": evidence_type,
        "quality_score": "",
        "novelty_score": "",
        "actionability_score": "",
        "data_availability": "",
        "bias_risk": "",
        "recommended_action": "screen",
        "status": "collected",
        "linked_strategy_task": "T5.2",
        "reviewed_at": "",
    }


def _dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, str]] = []
    for row in rows:
        key = (
            _safe_text(row.get("title")).lower(),
            _safe_text(row.get("source_path_or_url")),
            _safe_text(row.get("published_at")),
        )
        if key in seen or not key[0]:
            continue
        seen.add(key)
        out.append(row)
    return out


def _write_candidates(rows: list[dict[str, str]], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in LEDGER_COLUMNS})


def _write_collect_report(
    *,
    report_md: Path,
    title: str,
    rows: list[dict[str, str]],
    warnings: list[str],
    source_counts: dict[str, int],
) -> None:
    report_md.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        title,
        "",
        f"- Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"- Candidate rows: {len(rows)}",
        "",
        "## Source Counts",
        "",
        "| Source | Rows |",
        "| --- | ---: |",
    ]
    for source, count in sorted(source_counts.items()):
        lines.append(f"| {source} | {count} |")
    lines.extend(
        [
            "",
            "## Candidates",
            "",
            "| id | title | source_type | published_at | status |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in rows[:50]:
        lines.append(
            f"| {row.get('intelligence_id', '')} | {row.get('title', '').replace('|', '/')} | "
            f"{row.get('source_type', '')} | {row.get('published_at', '')} | {row.get('status', '')} |"
        )
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {warning}" for warning in warnings] if warnings else ["- None"])
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _title_from_markdown(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()[:80]:
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()
            if stripped.lower().startswith("title:"):
                return stripped.split(":", 1)[1].strip().strip('"')
    except OSError:
        pass
    return path.stem.replace("_", " ")


def _relative_source(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _rows_from_local_file(path: Path, root: Path) -> list[dict[str, str]]:
    suffix = path.suffix.lower()
    rel = _relative_source(path, root)
    rows: list[dict[str, str]] = []
    if suffix == ".md":
        rows.append(
            _candidate_row(
                title=_title_from_markdown(path),
                source_type="paper",
                source_path_or_url=rel,
                evidence_type="local_markdown",
            )
        )
    elif suffix == ".pdf":
        rows.append(
            _candidate_row(
                title=path.stem.replace("_", " "),
                source_type="paper",
                source_path_or_url=rel,
                evidence_type="local_pdf",
            )
        )
    elif suffix == ".csv":
        try:
            frame = pd.read_csv(path)
            title_col = next((col for col in ["title", "Title", "name"] if col in frame.columns), None)
            url_col = next((col for col in ["paper_url", "url", "source_path_or_url", "pdf_url"] if col in frame.columns), None)
            date_col = next((col for col in ["published_at", "year", "date"] if col in frame.columns), None)
            for _, item in frame.iterrows():
                title = _safe_text(item.get(title_col)) if title_col else ""
                if not title:
                    continue
                rows.append(
                    _candidate_row(
                        title=title,
                        source_type="paper",
                        source_path_or_url=_safe_text(item.get(url_col)) if url_col else rel,
                        published_at=_safe_text(item.get(date_col)) if date_col else "",
                        market_scope=_safe_text(item.get("market_scope")),
                        evidence_type="local_csv",
                    )
                )
        except Exception:
            rows.append(
                _candidate_row(
                    title=path.stem,
                    source_type="manual_note",
                    source_path_or_url=rel,
                    evidence_type="local_csv_unparsed",
                )
            )
    elif suffix == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("papers") or data.get("items") or []
            else:
                items = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                title = _safe_text(item.get("title"))
                if not title:
                    continue
                rows.append(
                    _candidate_row(
                        title=title,
                        source_type="paper",
                        source_path_or_url=_safe_text(item.get("paper_url") or item.get("url") or rel),
                        published_at=_safe_text(item.get("year") or item.get("published_at")),
                        evidence_type="local_json",
                    )
                )
        except Exception:
            rows.append(
                _candidate_row(
                    title=path.stem,
                    source_type="manual_note",
                    source_path_or_url=rel,
                    evidence_type="local_json_unparsed",
                )
            )
    return rows


def _collect_local_dir(root: Path, raw_source: str | Path, limit: int | None) -> tuple[list[dict[str, str]], list[str]]:
    source = _resolve_path(root, raw_source)
    warnings: list[str] = []
    rows: list[dict[str, str]] = []
    if not source.exists():
        warnings.append(f"source_dir does not exist: {source}")
        return rows, warnings
    files = sorted([p for p in source.rglob("*") if p.suffix.lower() in {".md", ".pdf", ".csv", ".json"}])
    if limit is not None and limit > 0:
        files = files[: int(limit)]
    for path in files:
        rows.extend(_rows_from_local_file(path, root))
    return _dedupe_rows(rows), warnings


def import_local_intelligence(
    config_path: Path,
    *,
    source_dir: str | Path | None = None,
    output_csv: str | Path | None = None,
    output_report: str | Path | None = None,
    limit: int | None = None,
) -> IntelligenceResult:
    root = config_path.parent
    cfg = load_config(config_path)
    intel_cfg = cfg.get("intelligence", {})
    inbox_dir = intel_cfg.get("inbox_dir", "data/intelligence/inbox")
    report_dir = intel_cfg.get("report_dir", "reports/intelligence")
    raw_source = source_dir or "refdocs/papers"
    output = _configured_path(
        root=root,
        intel_cfg=intel_cfg,
        override=output_csv,
        config_key="candidate_csv",
        fallback=f"{inbox_dir}/intelligence_candidates_{_date_tag()}.csv",
    )
    report = _configured_path(
        root=root,
        intel_cfg=intel_cfg,
        override=output_report,
        config_key="import_report",
        fallback=f"{report_dir}/intelligence_import_local_report_{_date_tag()}.md",
    )
    rows, warnings = _collect_local_dir(root, raw_source, limit)
    _write_candidates(rows, output)
    _write_collect_report(
        report_md=report,
        title="# Intelligence Local Import Report",
        rows=rows,
        warnings=warnings,
        source_counts={str(raw_source): len(rows)},
    )
    return IntelligenceResult(
        status="ok" if not warnings else "ok_with_warnings",
        rows=len(rows),
        candidates_csv=output,
        report_md=report,
        warnings=warnings,
    )


def _fetch_rss(url: str, limit: int | None) -> tuple[list[dict[str, str]], str | None]:
    if not url.strip():
        return [], "rss source has empty url"
    parsed = feedparser.parse(url)
    if parsed.bozo:
        return [], f"rss parse warning for {url}: {parsed.bozo_exception}"
    rows: list[dict[str, str]] = []
    entries = parsed.entries[: int(limit)] if limit and limit > 0 else parsed.entries
    for entry in entries:
        title = _safe_text(entry.get("title"))
        link = _safe_text(entry.get("link"))
        published = _safe_text(entry.get("published") or entry.get("updated"))
        if title:
            rows.append(
                _candidate_row(
                    title=title,
                    source_type="research_report",
                    source_path_or_url=link or url,
                    published_at=published,
                    evidence_type="rss_metadata",
                )
            )
    return rows, None


def _fetch_arxiv(query: str, limit: int | None) -> tuple[list[dict[str, str]], str | None]:
    max_results = max(1, int(limit or 20))
    url = "http://export.arxiv.org/api/query?" + urlencode({"search_query": query, "start": 0, "max_results": max_results})
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except Exception as exc:
        return [], f"arxiv failed: {exc}"
    parsed = feedparser.parse(response.text)
    rows: list[dict[str, str]] = []
    for entry in parsed.entries:
        rows.append(
            _candidate_row(
                title=_safe_text(entry.get("title")),
                source_type="paper",
                source_path_or_url=_safe_text(entry.get("link")),
                published_at=_safe_text(entry.get("published"))[:10],
                evidence_type="arxiv_metadata",
            )
        )
    return rows, None


def _fetch_openalex(query: str, limit: int | None) -> tuple[list[dict[str, str]], str | None]:
    params = {"search": query, "per-page": max(1, min(200, int(limit or 25)))}
    try:
        response = requests.get("https://api.openalex.org/works", params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return [], f"openalex failed: {exc}"
    rows: list[dict[str, str]] = []
    for item in data.get("results", []):
        title = _safe_text(item.get("title"))
        if not title:
            continue
        rows.append(
            _candidate_row(
                title=title,
                source_type="paper",
                source_path_or_url=_safe_text(item.get("doi") or item.get("id")),
                published_at=_safe_text(item.get("publication_year")),
                evidence_type="openalex_metadata",
            )
        )
    return rows, None


def _fetch_crossref(query: str, limit: int | None) -> tuple[list[dict[str, str]], str | None]:
    params = {"query": query, "rows": max(1, min(100, int(limit or 25)))}
    try:
        response = requests.get("https://api.crossref.org/works", params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return [], f"crossref failed: {exc}"
    rows: list[dict[str, str]] = []
    for item in data.get("message", {}).get("items", []):
        titles = item.get("title") or []
        title = _safe_text(titles[0] if titles else "")
        if not title:
            continue
        year = ""
        date_parts = item.get("published-print", item.get("published-online", {})).get("date-parts", [[]])
        if date_parts and date_parts[0]:
            year = str(date_parts[0][0])
        rows.append(
            _candidate_row(
                title=title,
                source_type="paper",
                source_path_or_url=_safe_text(item.get("URL") or item.get("DOI")),
                published_at=year,
                evidence_type="crossref_metadata",
            )
        )
    return rows, None


def collect_intelligence(
    config_path: Path,
    *,
    output_csv: str | Path | None = None,
    output_report: str | Path | None = None,
    limit: int | None = None,
) -> IntelligenceResult:
    root = config_path.parent
    cfg = load_config(config_path)
    intel_cfg = cfg.get("intelligence", {})
    sources = intel_cfg.get("sources", [])
    inbox_dir = intel_cfg.get("inbox_dir", "data/intelligence/inbox")
    report_dir = intel_cfg.get("report_dir", "reports/intelligence")
    output = _configured_path(
        root=root,
        intel_cfg=intel_cfg,
        override=output_csv,
        config_key="candidate_csv",
        fallback=f"{inbox_dir}/intelligence_candidates_{_date_tag()}.csv",
    )
    report = _configured_path(
        root=root,
        intel_cfg=intel_cfg,
        override=output_report,
        config_key="collect_report",
        fallback=f"{report_dir}/intelligence_collect_report_{_date_tag()}.md",
    )
    rows: list[dict[str, str]] = []
    warnings: list[str] = []
    source_counts: dict[str, int] = {}
    for source in sources:
        if not bool(source.get("enabled", False)):
            continue
        kind = str(source.get("type", "")).strip()
        name = str(source.get("name", kind or "unknown"))
        before = len(rows)
        if kind == "local_dir":
            fetched, local_warnings = _collect_local_dir(root, source.get("path", "refdocs/papers"), limit)
            rows.extend(fetched)
            warnings.extend([f"{name}: {warning}" for warning in local_warnings])
        elif kind == "rss":
            fetched, warning = _fetch_rss(str(source.get("url", "")), limit)
            rows.extend(fetched)
            if warning:
                warnings.append(f"{name}: {warning}")
        elif kind == "arxiv":
            fetched, warning = _fetch_arxiv(str(source.get("query", "quantitative finance stock")), limit)
            rows.extend(fetched)
            if warning:
                warnings.append(f"{name}: {warning}")
        elif kind == "openalex":
            fetched, warning = _fetch_openalex(str(source.get("query", "quantitative investment stock strategy")), limit)
            rows.extend(fetched)
            if warning:
                warnings.append(f"{name}: {warning}")
        elif kind == "crossref":
            fetched, warning = _fetch_crossref(str(source.get("query", "quantitative investment stock strategy")), limit)
            rows.extend(fetched)
            if warning:
                warnings.append(f"{name}: {warning}")
        else:
            warnings.append(f"unsupported intelligence source type: {kind}")
        source_counts[name] = len(rows) - before
    rows = _dedupe_rows(rows)
    _write_candidates(rows, output)
    _write_collect_report(
        report_md=report,
        title="# Intelligence Collect Report",
        rows=rows,
        warnings=warnings,
        source_counts=source_counts,
    )
    return IntelligenceResult(
        status="ok" if not warnings else "ok_with_warnings",
        rows=len(rows),
        candidates_csv=output,
        report_md=report,
        warnings=warnings,
    )


def _read_ledger(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    with path.open(newline="", encoding="utf-8-sig") as f:
        return [dict(row) for row in csv.DictReader(f)]


def validate_intelligence_ledger(
    config_path: Path,
    *,
    ledger: str | Path | None = None,
    output_report: str | Path | None = None,
) -> IntelligenceValidationResult:
    root = config_path.parent
    cfg = load_config(config_path)
    intel_cfg = cfg.get("intelligence", {})
    ledger_path = _configured_path(
        root=root,
        intel_cfg=intel_cfg,
        override=ledger,
        config_key="ledger",
        fallback="knowledge/intelligence/strategy_intelligence_ledger.csv",
    )
    report = _configured_path(
        root=root,
        intel_cfg=intel_cfg,
        override=output_report,
        config_key="validate_report",
        fallback=f"reports/intelligence/intelligence_validate_report_{_date_tag()}.md",
    )
    errors: list[str] = []
    warnings: list[str] = []
    try:
        rows = _read_ledger(ledger_path)
    except Exception as exc:
        rows = []
        errors.append(f"cannot read ledger: {exc}")
    if rows:
        missing_cols = [col for col in LEDGER_COLUMNS if col not in rows[0]]
        if missing_cols:
            errors.append(f"missing columns: {', '.join(missing_cols)}")
    seen_keys: set[tuple[str, str, str]] = set()
    for idx, row in enumerate(rows, start=2):
        ident = _safe_text(row.get("intelligence_id")) or f"line {idx}"
        if not _safe_text(row.get("title")):
            errors.append(f"{ident}: missing title")
        source = _safe_text(row.get("source_path_or_url"))
        if not source:
            errors.append(f"{ident}: missing source_path_or_url")
        elif source.startswith("refdocs/") or source.startswith("docs/"):
            if not (root / source).exists():
                errors.append(f"{ident}: local source path missing: {source}")
        status = _safe_text(row.get("status"))
        if status and status not in VALID_STATUSES:
            errors.append(f"{ident}: invalid status: {status}")
        data_availability = _safe_text(row.get("data_availability"))
        if data_availability and data_availability not in VALID_DATA_AVAILABILITY:
            errors.append(f"{ident}: invalid data_availability: {data_availability}")
        for score_col in ["quality_score", "novelty_score", "actionability_score"]:
            score = _safe_text(row.get(score_col))
            if score:
                try:
                    value = int(float(score))
                    if value < 1 or value > 5:
                        errors.append(f"{ident}: {score_col} out of range: {score}")
                except ValueError:
                    errors.append(f"{ident}: invalid {score_col}: {score}")
        key = (_safe_text(row.get("title")).lower(), source, _safe_text(row.get("published_at")))
        if key in seen_keys:
            warnings.append(f"{ident}: duplicate title/source/date")
        seen_keys.add(key)
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Intelligence Ledger Validation Report",
        "",
        f"- Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"- Ledger: {ledger_path}",
        f"- Rows: {len(rows)}",
        f"- Errors: {len(errors)}",
        f"- Warnings: {len(warnings)}",
        "",
        "## Errors",
        "",
    ]
    lines.extend([f"- {item}" for item in errors] or ["- None"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {item}" for item in warnings] or ["- None"])
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    status = "ok" if not errors else "error"
    return IntelligenceValidationResult(
        status=status,
        row_count=len(rows),
        error_count=len(errors),
        warning_count=len(warnings),
        report_md=report,
        errors=errors,
        warnings=warnings,
    )
