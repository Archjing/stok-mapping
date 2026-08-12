from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from collections.abc import Mapping
from pathlib import Path
from typing import Any


_INVALID_CHARS = re.compile(r"[^a-z0-9]+")
DEFAULT_REPORT_ROOT = "reports"
LEGACY_PHASE0_REPORT_CATEGORY = "phase0"
DEFAULT_REPORT_CATEGORIES = {
    "archive": "archive",
    "database_health": "database_health",
    # Persisted artifact namespace retained across the Python package rename.
    LEGACY_PHASE0_REPORT_CATEGORY: "phase0",
    "runs": "runs",
    "strategy_admission": "strategy_admission",
    "strategy_governance": "strategy_governance",
}


def slug(value: str) -> str:
    text = _INVALID_CHARS.sub("_", value.strip().lower()).strip("_")
    return text or "default"


def _reporting_config(config: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not config:
        return {}
    return config.get("reporting", {}) or {}


def _category_map(config: Mapping[str, Any] | None) -> dict[str, str]:
    categories = dict(DEFAULT_REPORT_CATEGORIES)
    configured = _reporting_config(config).get("categories", {}) or {}
    for key, value in configured.items():
        if str(key).strip() and str(value).strip():
            categories[str(key)] = str(value)
    return categories


def report_root(*, root: Path, config: Mapping[str, Any] | None = None) -> Path:
    configured = str(_reporting_config(config).get("root_dir") or DEFAULT_REPORT_ROOT)
    path = Path(configured)
    return path if path.is_absolute() else root / path


def report_category_dir(*, root: Path, config: Mapping[str, Any] | None = None, category: str) -> Path:
    categories = _category_map(config)
    category_path = Path(categories.get(category, category))
    if category_path.is_absolute():
        return category_path
    return report_root(root=root, config=config) / category_path


def report_path(*, root: Path, config: Mapping[str, Any] | None = None, category: str, parts: tuple[str, ...]) -> Path:
    return report_category_dir(root=root, config=config, category=category).joinpath(*parts)


def report_config_path(
    *,
    root: Path,
    config: Mapping[str, Any] | None = None,
    value: str | Path,
    default_category: str | None = None,
) -> Path:
    """Resolve a report config value, not an arbitrary user CLI path."""
    path = Path(value)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == str(_reporting_config(config).get("root_dir") or DEFAULT_REPORT_ROOT):
        return root / path
    categories = _category_map(config)
    category_keys = set(categories)
    category_roots = {Path(raw).parts[0] for raw in categories.values() if Path(raw).parts}
    if path.parts and path.parts[0] in category_keys:
        mapped = Path(categories[path.parts[0]]).joinpath(*path.parts[1:])
        return report_root(root=root, config=config) / mapped
    if path.parts and path.parts[0] in category_roots:
        return report_root(root=root, config=config) / path
    if default_category:
        return report_category_dir(root=root, config=config, category=default_category) / path
    return root / path


@dataclass(frozen=True)
class ReportRunPath:
    root: Path
    run_dir: Path
    run_id: str
    command: str
    scope: str

    def artifact(self, family: str, artifact: str, ext: str) -> Path:
        extension = ext.strip().lower().lstrip(".")
        if not extension:
            raise ValueError("artifact extension must not be empty")
        return self.run_dir / f"{slug(family)}__{slug(artifact)}.{extension}"


def create_report_run(
    *,
    root: Path,
    command: str,
    scope: str,
    config: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> ReportRunPath:
    timestamp = now or datetime.now()
    command_slug = slug(command)
    scope_slug = slug(scope)
    run_id = f"{timestamp:%Y%m%d_%H%M%S}__{command_slug}__{scope_slug}"
    run_dir = report_category_dir(root=root, config=config, category="runs") / f"{timestamp:%Y-%m-%d}" / run_id
    return ReportRunPath(
        root=root,
        run_dir=run_dir,
        run_id=run_id,
        command=command_slug,
        scope=scope_slug,
    )


def latest_dir(*, root: Path, channel: str, config: Mapping[str, Any] | None = None) -> Path:
    return report_category_dir(root=root, config=config, category="runs") / "latest" / slug(channel)


def scratch_dir(
    *,
    root: Path,
    purpose: str,
    config: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> Path:
    timestamp = now or datetime.now()
    return report_category_dir(root=root, config=config, category="runs") / "scratch" / f"{timestamp:%Y-%m-%d}" / slug(purpose)
