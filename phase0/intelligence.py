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

REVIEW_SUGGESTION_COLUMNS = [
    "suggested_quality_score",
    "suggested_novelty_score",
    "suggested_actionability_score",
    "suggested_data_availability",
    "suggested_bias_risk",
    "suggested_recommended_action",
    "suggested_status",
    "review_rationale",
    "source_excerpt",
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

RAG_MANIFEST_COLUMNS = [
    "corpus_id",
    "path",
    "doc_type",
    "trust_level",
    "intelligence_id",
    "source_path_or_url",
    "tags",
    "linked_tasks",
    "status",
    "last_reviewed",
]

VALID_RAG_DOC_TYPES = {
    "index",
    "ledger",
    "monthly_scan",
    "note",
    "source",
    "translation",
    "wiki",
}

VALID_RAG_TRUST_LEVELS = {
    "candidate",
    "curated",
    "derived",
    "runtime_report",
    "source",
}

VALID_RAG_STATUSES = {
    "active",
    "archived",
    "draft",
    "evaluated",
    "screened",
}


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


@dataclass(frozen=True)
class IntelligenceReviewResult:
    status: str
    row_count: int
    review_csv: Path
    report_md: Path
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
    with output_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in LEDGER_COLUMNS})


def _write_review_csv(rows: list[dict[str, str]], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = LEDGER_COLUMNS + REVIEW_SUGGESTION_COLUMNS
    with output_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in fieldnames})


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


def _read_candidate_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    with path.open(newline="", encoding="utf-8-sig") as f:
        return [dict(row) for row in csv.DictReader(f)]


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


def _source_excerpt(root: Path, source_path_or_url: str, max_chars: int) -> tuple[str, str | None]:
    source = _safe_text(source_path_or_url)
    if not source or "://" in source:
        return "", None
    path = _resolve_path(root, source)
    if not path.exists():
        return "", f"source path missing: {source}"
    if path.suffix.lower() not in {".md", ".txt", ".csv", ".json"}:
        return "", f"source excerpt skipped for non-text file: {source}"
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        return "", f"cannot read source excerpt: {source}: {exc}"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    excerpt = "\n".join(lines)
    return excerpt[:max_chars], None


def _contains_any(text: str, needles: list[str]) -> bool:
    lowered = text.lower()
    return any(needle.lower() in lowered for needle in needles)


def _review_suggestion(row: dict[str, str], excerpt: str, source_warning: str | None) -> dict[str, str]:
    title = _safe_text(row.get("title"))
    topic_tags = _safe_text(row.get("topic_tags"))
    strategy_tags = _safe_text(row.get("strategy_tags"))
    evidence_type = _safe_text(row.get("evidence_type"))
    source = _safe_text(row.get("source_path_or_url"))
    text = "\n".join([title, topic_tags, strategy_tags, evidence_type, source, excerpt])

    quality_score = 3
    novelty_score = 3
    actionability_score = 3
    data_availability = "partial"
    risks: list[str] = ["overfit"]
    rationale: list[str] = []

    if source_warning:
        quality_score = min(quality_score, 2)
        actionability_score = min(actionability_score, 2)
        data_availability = "missing"
        rationale.append(source_warning)

    if _contains_any(text, ["review", "literature", "综述", "报告", "reference", "参考文献"]):
        quality_score = max(quality_score, 3)
        actionability_score = min(actionability_score, 3)
        rationale.append("source looks like review/reference material; useful for context but needs translation before experiment")

    if _contains_any(text, ["lasso", "因子", "factor", "多因子", "roe", "pe", "pb", "换手"]):
        novelty_score = max(novelty_score, 4)
        actionability_score = max(actionability_score, 4)
        data_availability = "ready"
        rationale.append("factor-style idea maps to existing daily/factor diagnostics")

    if _contains_any(text, ["portfolio", "组合", "asset characteristics", "资产特征", "权重"]):
        novelty_score = max(novelty_score, 3)
        actionability_score = max(actionability_score, 4)
        rationale.append("portfolio construction idea can map to candidate strategy or sleeve review")

    if _contains_any(text, ["svm", "xgboost", "random forest", "机器学习", "deep learning", "transformer", "lstm", "gnn", "reinforcement"]):
        novelty_score = max(novelty_score, 4)
        risks.append("model-risk")
        risks.append("parameter-instability")
        rationale.append("ML method needs strict walk-forward and overfit diagnostics")

    if _contains_any(text, ["text", "sentiment", "analyst", "新闻", "公告", "研报", "情绪", "文本"]):
        novelty_score = max(novelty_score, 4)
        data_availability = "external_required" if data_availability != "missing" else data_availability
        risks.append("text-delay")
        risks.append("data-license")
        rationale.append("text/event source requires as-of, delay, dedupe, and licensing governance")

    if _contains_any(text, ["high-frequency", "高频", "分钟", "tick", "融资融券", "margin"]):
        actionability_score = min(actionability_score, 2)
        data_availability = "external_required" if data_availability != "missing" else data_availability
        risks.append("execution-reality")
        rationale.append("data or execution assumption is not covered by current daily V1 workflow")

    if _contains_any(text, ["网络", "graph", "relation", "关联"]):
        data_availability = "missing" if data_availability not in {"external_required", "missing"} else data_availability
        risks.append("lookahead-relation")
        rationale.append("relation/network features need explicit construction and as-of audit")

    if _contains_any(text, ["k线", "均线", "ma", "moving average", "ohlcv", "volume", "量价"]):
        actionability_score = max(actionability_score, 4)
        data_availability = "ready" if data_availability != "missing" else data_availability
        risks.append("turnover-cost")
        rationale.append("price/volume idea is locally testable but cost and turnover sensitivity matter")

    if not excerpt and not source_warning:
        quality_score = min(quality_score, 3)
        rationale.append("no source excerpt available; suggestion is metadata-only")

    if actionability_score >= 4 and data_availability in {"ready", "partial"}:
        recommended_action = "create_strategy_task"
        status = "screened"
    elif data_availability == "external_required":
        recommended_action = "create_data_task"
        status = "screened"
    elif quality_score <= 2:
        recommended_action = "archive_only"
        status = "archived"
    else:
        recommended_action = "screen_later"
        status = "collected"

    risks = list(dict.fromkeys(risks))
    rationale = rationale or ["metadata suggests a generic candidate; human review required before ledger entry"]
    return {
        "suggested_quality_score": str(max(1, min(5, quality_score))),
        "suggested_novelty_score": str(max(1, min(5, novelty_score))),
        "suggested_actionability_score": str(max(1, min(5, actionability_score))),
        "suggested_data_availability": data_availability,
        "suggested_bias_risk": ";".join(risks),
        "suggested_recommended_action": recommended_action,
        "suggested_status": status,
        "review_rationale": " | ".join(rationale),
        "source_excerpt": excerpt.replace("\r", " ").replace("\n", " ")[:1000],
    }


def _write_review_report(
    *,
    report_md: Path,
    candidates_csv: Path,
    review_csv: Path,
    rows: list[dict[str, str]],
    warnings: list[str],
) -> None:
    report_md.parent.mkdir(parents=True, exist_ok=True)
    action_counts: dict[str, int] = {}
    availability_counts: dict[str, int] = {}
    for row in rows:
        action = row.get("suggested_recommended_action", "")
        availability = row.get("suggested_data_availability", "")
        action_counts[action] = action_counts.get(action, 0) + 1
        availability_counts[availability] = availability_counts.get(availability, 0) + 1

    lines = [
        "# Intelligence Candidate Review Report",
        "",
        f"- Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"- Candidate CSV: {candidates_csv}",
        f"- Review CSV: {review_csv}",
        f"- Candidate rows: {len(rows)}",
        "- Mode: rule_based_llm_ready_review",
        "- Ledger updated: no",
        "- RAG manifest updated: no",
        "",
        "## Suggested Action Counts",
        "",
        "| Action | Rows |",
        "| --- | ---: |",
    ]
    for action, count in sorted(action_counts.items()):
        lines.append(f"| {action or 'blank'} | {count} |")
    lines.extend(["", "## Suggested Data Availability Counts", "", "| Data Availability | Rows |", "| --- | ---: |"])
    for availability, count in sorted(availability_counts.items()):
        lines.append(f"| {availability or 'blank'} | {count} |")
    lines.extend(
        [
            "",
            "## Review Sample",
            "",
            "| id | title | quality | novelty | actionability | data | action | rationale |",
            "| --- | --- | ---: | ---: | ---: | --- | --- | --- |",
        ]
    )
    for row in rows[:30]:
        title = row.get("title", "").replace("|", "/")
        rationale = row.get("review_rationale", "").replace("|", "/")[:180]
        lines.append(
            f"| {row.get('intelligence_id', '')} | {title} | "
            f"{row.get('suggested_quality_score', '')} | {row.get('suggested_novelty_score', '')} | "
            f"{row.get('suggested_actionability_score', '')} | {row.get('suggested_data_availability', '')} | "
            f"{row.get('suggested_recommended_action', '')} | {rationale} |"
        )
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {warning}" for warning in warnings] if warnings else ["- None"])
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- These are review suggestions, not official ledger entries.",
            "- Human review is required before writing quality scores, bias risks, or reviewed_at to the formal ledger.",
            "- Do not treat this report as strategy effectiveness evidence.",
        ]
    )
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def review_intelligence_candidates(
    config_path: Path,
    *,
    candidates_csv: str | Path,
    output_csv: str | Path | None = None,
    output_report: str | Path | None = None,
    limit: int | None = None,
    excerpt_chars: int = 2000,
) -> IntelligenceReviewResult:
    root = config_path.parent
    cfg = load_config(config_path)
    intel_cfg = cfg.get("intelligence", {})
    inbox_dir = intel_cfg.get("inbox_dir", "data/intelligence/inbox")
    report_dir = intel_cfg.get("report_dir", "reports/archive/intelligence")
    candidates_path = _resolve_path(root, candidates_csv)
    review_csv = _configured_path(
        root=root,
        intel_cfg=intel_cfg,
        override=output_csv,
        config_key="review_csv",
        fallback=f"{inbox_dir}/intelligence_review_suggestions_{_date_tag()}.csv",
    )
    report = _configured_path(
        root=root,
        intel_cfg=intel_cfg,
        override=output_report,
        config_key="review_report",
        fallback=f"{report_dir}/intelligence_review_report_{_date_tag()}.md",
    )
    rows = _read_candidate_rows(candidates_path)
    if limit is not None and limit > 0:
        rows = rows[: int(limit)]
    reviewed_rows: list[dict[str, str]] = []
    warnings: list[str] = []
    for row in rows:
        excerpt, source_warning = _source_excerpt(root, _safe_text(row.get("source_path_or_url")), excerpt_chars)
        if source_warning:
            warnings.append(f"{_safe_text(row.get('intelligence_id')) or _safe_text(row.get('title'))}: {source_warning}")
        reviewed = dict(row)
        reviewed.update(_review_suggestion(row, excerpt, source_warning))
        reviewed_rows.append(reviewed)
    _write_review_csv(reviewed_rows, review_csv)
    _write_review_report(
        report_md=report,
        candidates_csv=candidates_path,
        review_csv=review_csv,
        rows=reviewed_rows,
        warnings=warnings,
    )
    return IntelligenceReviewResult(
        status="ok" if not warnings else "ok_with_warnings",
        row_count=len(reviewed_rows),
        review_csv=review_csv,
        report_md=report,
        warnings=warnings,
    )



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
    report_dir = intel_cfg.get("report_dir", "reports/archive/intelligence")
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
    report_dir = intel_cfg.get("report_dir", "reports/archive/intelligence")
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


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    with path.open(newline="", encoding="utf-8-sig") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _local_path_exists(root: Path, raw_path: str) -> bool:
    if not raw_path or "://" in raw_path:
        return True
    path = Path(raw_path)
    if path.is_absolute():
        return path.exists()
    return (root / path).exists()


def _validate_rag_manifest(
    *,
    root: Path,
    manifest_path: Path,
    ledger_rows: list[dict[str, str]],
) -> tuple[int, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        rows = _read_csv_rows(manifest_path)
    except FileNotFoundError:
        return 0, errors, [f"rag manifest missing: {manifest_path}"]
    except Exception as exc:
        return 0, [f"cannot read rag manifest: {exc}"], warnings

    if rows:
        missing_cols = [col for col in RAG_MANIFEST_COLUMNS if col not in rows[0]]
        if missing_cols:
            errors.append(f"rag manifest missing columns: {', '.join(missing_cols)}")

    ledger_ids = {_safe_text(row.get("intelligence_id")) for row in ledger_rows if _safe_text(row.get("intelligence_id"))}
    seen_corpus_ids: set[str] = set()
    for idx, row in enumerate(rows, start=2):
        corpus_id = _safe_text(row.get("corpus_id")) or f"manifest line {idx}"
        if not _safe_text(row.get("corpus_id")):
            errors.append(f"{corpus_id}: missing corpus_id")
        elif corpus_id in seen_corpus_ids:
            warnings.append(f"{corpus_id}: duplicate corpus_id")
        seen_corpus_ids.add(corpus_id)

        corpus_path = _safe_text(row.get("path"))
        if not corpus_path:
            errors.append(f"{corpus_id}: missing path")
        elif not _local_path_exists(root, corpus_path):
            errors.append(f"{corpus_id}: corpus path missing: {corpus_path}")

        doc_type = _safe_text(row.get("doc_type"))
        if doc_type and doc_type not in VALID_RAG_DOC_TYPES:
            errors.append(f"{corpus_id}: invalid doc_type: {doc_type}")

        trust_level = _safe_text(row.get("trust_level"))
        if trust_level and trust_level not in VALID_RAG_TRUST_LEVELS:
            errors.append(f"{corpus_id}: invalid trust_level: {trust_level}")

        status = _safe_text(row.get("status"))
        if status and status not in VALID_RAG_STATUSES:
            errors.append(f"{corpus_id}: invalid status: {status}")

        intelligence_id = _safe_text(row.get("intelligence_id"))
        if intelligence_id and intelligence_id not in ledger_ids:
            errors.append(f"{corpus_id}: intelligence_id not found in ledger: {intelligence_id}")

    return len(rows), errors, warnings


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
    manifest_path = _configured_path(
        root=root,
        intel_cfg=intel_cfg,
        override=None,
        config_key="rag_manifest",
        fallback="knowledge/intelligence/rag_manifest.csv",
    )
    report = _configured_path(
        root=root,
        intel_cfg=intel_cfg,
        override=output_report,
        config_key="validate_report",
        fallback=f"reports/archive/intelligence/intelligence_validate_report_{_date_tag()}.md",
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
    manifest_rows, manifest_errors, manifest_warnings = _validate_rag_manifest(
        root=root,
        manifest_path=manifest_path,
        ledger_rows=rows,
    )
    errors.extend(manifest_errors)
    warnings.extend(manifest_warnings)
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Intelligence Ledger Validation Report",
        "",
        f"- Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"- Ledger: {ledger_path}",
        f"- RAG Manifest: {manifest_path}",
        f"- Rows: {len(rows)}",
        f"- Manifest Rows: {manifest_rows}",
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
