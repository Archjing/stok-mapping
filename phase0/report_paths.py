from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


_INVALID_CHARS = re.compile(r"[^a-z0-9]+")


def slug(value: str) -> str:
    text = _INVALID_CHARS.sub("_", value.strip().lower()).strip("_")
    return text or "default"


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
    now: datetime | None = None,
) -> ReportRunPath:
    timestamp = now or datetime.now()
    command_slug = slug(command)
    scope_slug = slug(scope)
    run_id = f"{timestamp:%Y%m%d_%H%M%S}__{command_slug}__{scope_slug}"
    run_dir = root / "reports" / "runs" / f"{timestamp:%Y-%m-%d}" / run_id
    return ReportRunPath(
        root=root,
        run_dir=run_dir,
        run_id=run_id,
        command=command_slug,
        scope=scope_slug,
    )


def latest_dir(*, root: Path, channel: str) -> Path:
    return root / "reports" / "latest" / slug(channel)


def scratch_dir(*, root: Path, purpose: str, now: datetime | None = None) -> Path:
    timestamp = now or datetime.now()
    return root / "reports" / "scratch" / f"{timestamp:%Y-%m-%d}" / slug(purpose)
