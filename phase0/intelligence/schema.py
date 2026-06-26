from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
