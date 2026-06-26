from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from phase0.config import load_config
from phase0.intelligence.common import configured_path, date_tag, safe_text
from phase0.intelligence.schema import (
    LEDGER_COLUMNS,
    RAG_MANIFEST_COLUMNS,
    VALID_DATA_AVAILABILITY,
    VALID_RAG_DOC_TYPES,
    VALID_RAG_STATUSES,
    VALID_RAG_TRUST_LEVELS,
    VALID_STATUSES,
    IntelligenceValidationResult,
)
from phase0.reporting.paths import report_config_path


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

    ledger_ids = {safe_text(row.get("intelligence_id")) for row in ledger_rows if safe_text(row.get("intelligence_id"))}
    seen_corpus_ids: set[str] = set()
    for idx, row in enumerate(rows, start=2):
        corpus_id = safe_text(row.get("corpus_id")) or f"manifest line {idx}"
        if not safe_text(row.get("corpus_id")):
            errors.append(f"{corpus_id}: missing corpus_id")
        elif corpus_id in seen_corpus_ids:
            warnings.append(f"{corpus_id}: duplicate corpus_id")
        seen_corpus_ids.add(corpus_id)

        corpus_path = safe_text(row.get("path"))
        if not corpus_path:
            errors.append(f"{corpus_id}: missing path")
        elif not _local_path_exists(root, corpus_path):
            errors.append(f"{corpus_id}: corpus path missing: {corpus_path}")

        doc_type = safe_text(row.get("doc_type"))
        if doc_type and doc_type not in VALID_RAG_DOC_TYPES:
            errors.append(f"{corpus_id}: invalid doc_type: {doc_type}")

        trust_level = safe_text(row.get("trust_level"))
        if trust_level and trust_level not in VALID_RAG_TRUST_LEVELS:
            errors.append(f"{corpus_id}: invalid trust_level: {trust_level}")

        status = safe_text(row.get("status"))
        if status and status not in VALID_RAG_STATUSES:
            errors.append(f"{corpus_id}: invalid status: {status}")

        intelligence_id = safe_text(row.get("intelligence_id"))
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
    ledger_path = configured_path(
        root=root,
        intel_cfg=intel_cfg,
        override=ledger,
        config_key="ledger",
        fallback="knowledge/intelligence/strategy_intelligence_ledger.csv",
    )
    manifest_path = configured_path(
        root=root,
        intel_cfg=intel_cfg,
        override=None,
        config_key="rag_manifest",
        fallback="knowledge/intelligence/rag_manifest.csv",
    )
    report = configured_path(
        root=root,
        intel_cfg=intel_cfg,
        override=output_report,
        config_key="validate_report",
        fallback=report_config_path(
            root=root,
            config=cfg,
            value=f"{intel_cfg.get('report_dir', 'archive/intelligence')}/intelligence_validate_report_{date_tag()}.md",
        ),
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
        ident = safe_text(row.get("intelligence_id")) or f"line {idx}"
        if not safe_text(row.get("title")):
            errors.append(f"{ident}: missing title")
        source = safe_text(row.get("source_path_or_url"))
        if not source:
            errors.append(f"{ident}: missing source_path_or_url")
        elif source.startswith("refdocs/") or source.startswith("docs/"):
            if not (root / source).exists():
                errors.append(f"{ident}: local source path missing: {source}")
        status = safe_text(row.get("status"))
        if status and status not in VALID_STATUSES:
            errors.append(f"{ident}: invalid status: {status}")
        data_availability = safe_text(row.get("data_availability"))
        if data_availability and data_availability not in VALID_DATA_AVAILABILITY:
            errors.append(f"{ident}: invalid data_availability: {data_availability}")
        for score_col in ["quality_score", "novelty_score", "actionability_score"]:
            score = safe_text(row.get(score_col))
            if score:
                try:
                    value = int(float(score))
                    if value < 1 or value > 5:
                        errors.append(f"{ident}: {score_col} out of range: {score}")
                except ValueError:
                    errors.append(f"{ident}: invalid {score_col}: {score}")
        key = (safe_text(row.get("title")).lower(), source, safe_text(row.get("published_at")))
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
