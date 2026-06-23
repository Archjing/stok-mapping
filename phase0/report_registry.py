from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SUPPORTED_REPORT_SUFFIXES = {
    ".csv": "csv",
    ".html": "html",
    ".md": "markdown",
}
LATEST_DIR_NAMES = {"brief_today", "watchlist_today", "latest", "current"}
SCRATCH_DIR_NAMES = {"scratch", "smoke", "tmp", "tmp_validation"}
EXPERIMENT_DIR_HINTS = ("experiment", "experiments", "candidate", "admission", "strategy_admission")


@dataclass(frozen=True)
class ReportArtifact:
    artifact_id: str
    run_id: str
    title: str
    path: str
    type: str
    module: str
    created_at: str
    status: str
    tags: list[str]
    description: str
    legacy_category: str


@dataclass(frozen=True)
class ReportRun:
    run_id: str
    command: str
    module: str
    started_at: str
    finished_at: str
    status: str
    summary: str
    tags: list[str]
    artifact_ids: list[str]
    legacy_category: str


def classify_legacy_artifact(path: Path) -> str:
    parts = path.parts
    if len(parts) < 2 or parts[0] != "reports":
        return "outside_reports"
    if len(parts) == 2:
        return "legacy_root_flat"
    first = parts[1]
    if first == "runs":
        return "standard_run"
    if first in SCRATCH_DIR_NAMES:
        return "legacy_scratch"
    if first in LATEST_DIR_NAMES:
        return "legacy_latest_mirror"
    if _is_date_dir(first):
        return "legacy_date_dir"
    if _looks_like_experiment_dir(first):
        return "legacy_experiment_dir"
    return "legacy_module_dir"


def scan_report_artifacts(root: Path, *, reports_dir: Path | None = None) -> list[ReportArtifact]:
    base = reports_dir or root / "reports"
    if not base.exists():
        return []

    artifacts: list[ReportArtifact] = []
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        artifact_type = SUPPORTED_REPORT_SUFFIXES.get(path.suffix.lower())
        if artifact_type is None:
            continue
        rel_path = _relative_path(root, path)
        if rel_path.startswith("reports/report_dashboard/"):
            continue
        legacy_category = classify_legacy_artifact(Path(rel_path))
        module = _module_from_relative_path(Path(rel_path), legacy_category)
        run_id = _run_id_from_relative_path(Path(rel_path), legacy_category)
        artifact_id = _stable_artifact_id(rel_path)
        artifacts.append(
            ReportArtifact(
                artifact_id=artifact_id,
                run_id=run_id,
                title=_title_from_path(path),
                path=rel_path,
                type=artifact_type,
                module=module,
                created_at=_mtime_iso(path),
                status="indexed",
                tags=_tags_from_path(Path(rel_path), module, legacy_category),
                description="",
                legacy_category=legacy_category,
            )
        )
    return sorted(artifacts, key=lambda artifact: (artifact.type, artifact.path))


def write_report_manifest(
    *,
    root: Path,
    manifest_path: Path | None = None,
    reports_dir: Path | None = None,
) -> Path:
    manifest = manifest_path or root / "reports" / "report_dashboard" / "manifest.json"
    artifacts = scan_report_artifacts(root, reports_dir=reports_dir)
    runs = _runs_from_artifacts(artifacts)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project_root": ".",
        "runs": [asdict(run) for run in runs],
        "artifacts": [asdict(artifact) for artifact in artifacts],
    }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def _runs_from_artifacts(artifacts: list[ReportArtifact]) -> list[ReportRun]:
    grouped: dict[str, list[ReportArtifact]] = {}
    for artifact in artifacts:
        grouped.setdefault(artifact.run_id, []).append(artifact)

    runs: list[ReportRun] = []
    for run_id, items in sorted(grouped.items()):
        first = items[0]
        finished_at = max(item.created_at for item in items)
        runs.append(
            ReportRun(
                run_id=run_id,
                command=first.module,
                module=first.module,
                started_at="",
                finished_at=finished_at,
                status="indexed",
                summary=f"{first.module} report set indexed from {first.legacy_category}",
                tags=sorted({tag for item in items for tag in item.tags}),
                artifact_ids=[item.artifact_id for item in items],
                legacy_category=first.legacy_category,
            )
        )
    return runs


def _is_iso_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _is_compact_date(value: str) -> bool:
    if len(value) != 8 or not value.isdigit():
        return False
    try:
        datetime.strptime(value, "%Y%m%d")
    except ValueError:
        return False
    return True


def _is_date_dir(value: str) -> bool:
    return _is_iso_date(value) or _is_compact_date(value)


def _looks_like_experiment_dir(value: str) -> bool:
    lowered = value.lower()
    if any(token in lowered for token in EXPERIMENT_DIR_HINTS):
        return True
    return any(char.isdigit() for char in value) and ("_" in value or "-" in value)


def _relative_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _module_from_relative_path(path: Path, legacy_category: str) -> str:
    parts = path.parts
    if len(parts) < 2:
        return "reports"
    if legacy_category == "legacy_root_flat":
        return _module_from_filename(parts[-1])
    if legacy_category == "legacy_date_dir":
        return _module_from_filename(parts[-1])
    if legacy_category == "legacy_latest_mirror":
        return parts[1].replace("_today", "")
    if legacy_category == "standard_run" and len(parts) >= 4:
        run_parts = parts[3].split("__")
        if len(run_parts) >= 3:
            return run_parts[1]
    return parts[1]


def _module_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    if stem.startswith("phase0_watchlist") or stem.startswith("phase0_premarket"):
        return "brief"
    if stem.startswith("database_health"):
        return "database_health"
    if stem.startswith("strategy_admission"):
        return "strategy_admission"
    if stem.startswith("tushare_"):
        return "tushare_backfill"
    return stem.split("__", 1)[0].split("_report", 1)[0]


def _run_id_from_relative_path(path: Path, legacy_category: str) -> str:
    parts = path.parts
    if legacy_category == "legacy_root_flat":
        return f"legacy_root__{path.stem}"
    if legacy_category == "legacy_date_dir" and len(parts) >= 3:
        group = parts[2] if len(parts) >= 4 else path.stem
        return f"{legacy_category}__{parts[1]}__{group}"
    if legacy_category == "standard_run" and len(parts) >= 4:
        return parts[3]
    if len(parts) >= 3:
        return f"{legacy_category}__{parts[1]}"
    return f"{legacy_category}__{path.stem}"


def _stable_artifact_id(path: str) -> str:
    safe = "".join(char if char.isalnum() else "_" for char in path.lower()).strip("_")
    return safe[:180]


def _title_from_path(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").title()


def _mtime_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")


def _tags_from_path(path: Path, module: str, legacy_category: str) -> list[str]:
    tags = {module, legacy_category, path.suffix.lower().lstrip(".")}
    for part in path.parts[1:-1]:
        if part not in {"reports"}:
            tags.add(part)
    return sorted(tags)
