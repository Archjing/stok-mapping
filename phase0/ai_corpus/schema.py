from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

AI_CORPUS_DOCUMENT_COLUMNS = [
    "document_id",
    "corpus_type",
    "event_type",
    "provider",
    "source",
    "source_id",
    "published_at",
    "issued_at",
    "ingested_at",
    "as_of_time",
    "title",
    "summary",
    "content_html",
    "raw_text",
    "url",
    "org",
    "pcode",
    "ptype",
    "symbols",
    "industries",
    "topics",
    "language",
    "dedupe_key",
    "content_hash",
    "raw_path",
    "parse_status",
    "source_confidence",
    "parser_version",
]

AI_CORPUS_REQUIRED_COLUMNS = {
    "document_id",
    "corpus_type",
    "provider",
    "source_id",
    "published_at",
    "ingested_at",
    "as_of_time",
    "title",
    "url",
    "dedupe_key",
    "content_hash",
    "raw_path",
    "parse_status",
    "parser_version",
}


@dataclass(frozen=True)
class AiCorpusProviderSpec:
    name: str
    canonical_name: str
    corpus_types: tuple[str, ...]
    source: str
    base_url: str
    parser_version: str
    raw_archive_dir: str
    supported_parameters: tuple[str, ...]
    status: str
    notes: str = ""


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return " ".join(text.split())


def content_sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def stable_document_id(provider: str, source_id: str, content_hash: str) -> str:
    payload = json.dumps(
        {"provider": provider, "source_id": source_id, "content_hash": content_hash},
        ensure_ascii=False,
        sort_keys=True,
    )
    return f"{provider}:{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]}"


def stable_dedupe_key(*parts: str) -> str:
    cleaned = [safe_text(part) for part in parts if safe_text(part)]
    return "|".join(cleaned)


def ensure_document_columns(row: dict[str, Any]) -> dict[str, str]:
    normalized = {column: safe_text(row.get(column, "")) for column in AI_CORPUS_DOCUMENT_COLUMNS}
    missing = [column for column in AI_CORPUS_REQUIRED_COLUMNS if not normalized.get(column)]
    if missing:
        raise ValueError(f"ai corpus document missing required fields: {', '.join(sorted(missing))}")
    return normalized


def normalize_documents(rows: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    return [ensure_document_columns(row) for row in rows]


def select_fields(rows: list[dict[str, Any]], fields: list[str] | None) -> list[dict[str, Any]]:
    if not fields:
        return rows
    selected: list[dict[str, Any]] = []
    for row in rows:
        enriched = dict(row)
        alias_values = {
            "pubtime": enriched.get("published_at", ""),
            "puborg": enriched.get("org", ""),
        }
        for alias, value in alias_values.items():
            if alias in fields and alias not in enriched:
                enriched[alias] = value
        selected.append({field: enriched.get(field, "") for field in fields})
    return selected


def resolve_path(root: Path, raw: str | Path) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else root / path
