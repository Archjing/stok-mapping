from __future__ import annotations

from datetime import datetime
from pathlib import Path

from phase0.config import load_config
from phase0.intelligence.candidates import read_candidate_rows, write_review_csv
from phase0.intelligence.common import configured_path, date_tag, resolve_path, safe_text
from phase0.intelligence.schema import IntelligenceReviewResult
from phase0.reporting.paths import report_config_path


def _source_excerpt(root: Path, source_path_or_url: str, max_chars: int) -> tuple[str, str | None]:
    source = safe_text(source_path_or_url)
    if not source or "://" in source:
        return "", None
    path = resolve_path(root, source)
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
    title = safe_text(row.get("title"))
    topic_tags = safe_text(row.get("topic_tags"))
    strategy_tags = safe_text(row.get("strategy_tags"))
    evidence_type = safe_text(row.get("evidence_type"))
    source = safe_text(row.get("source_path_or_url"))
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
    report_dir = intel_cfg.get("report_dir", "archive/intelligence")
    candidates_path = resolve_path(root, candidates_csv)
    review_csv = configured_path(
        root=root,
        intel_cfg=intel_cfg,
        override=output_csv,
        config_key="review_csv",
        fallback=f"{inbox_dir}/intelligence_review_suggestions_{date_tag()}.csv",
    )
    report = configured_path(
        root=root,
        intel_cfg=intel_cfg,
        override=output_report,
        config_key="review_report",
        fallback=report_config_path(root=root, config=cfg, value=f"{report_dir}/intelligence_review_report_{date_tag()}.md"),
    )
    rows = read_candidate_rows(candidates_path)
    if limit is not None and limit > 0:
        rows = rows[: int(limit)]
    reviewed_rows: list[dict[str, str]] = []
    warnings: list[str] = []
    for row in rows:
        excerpt, source_warning = _source_excerpt(root, safe_text(row.get("source_path_or_url")), excerpt_chars)
        if source_warning:
            warnings.append(f"{safe_text(row.get('intelligence_id')) or safe_text(row.get('title'))}: {source_warning}")
        reviewed = dict(row)
        reviewed.update(_review_suggestion(row, excerpt, source_warning))
        reviewed_rows.append(reviewed)
    write_review_csv(reviewed_rows, review_csv)
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
