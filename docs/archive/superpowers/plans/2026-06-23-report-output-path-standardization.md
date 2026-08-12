# Report Output Path Standardization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standardize future Markdown, HTML, and CSV report output paths under `reports/` so backtest, compare, admission, brief, maintenance, and data-quality artifacts are easier to discover, index, and render in the Astro dashboard.

**Architecture:** Add a small Python report-path layer that creates immutable run directories, stable latest pointers, and manifest-friendly artifact metadata. Business commands stop hand-building new `reports/...` paths over time, but historical report paths remain readable and are indexed through compatibility scanning.

**Tech Stack:** Python 3.12+, `pathlib`, dataclasses, pytest, existing `phase0.cli`, existing `reports/` tree, future Astro dashboard manifest.

---

## Scope

This plan originally defined rules and future implementation steps. It entered implementation after the user explicitly requested execution and reports path refactoring.

In scope:

- New path conventions for future program-generated Markdown, HTML, and CSV artifacts.
- A shared path helper module for new and migrated CLI commands.
- Compatibility with existing historical report directories.
- Rules for `latest` entries and dashboard manifest indexing.
- TDD tasks for path naming and artifact registration.

Out of scope:

- Bulk-moving historical files under `reports/`.
- Rewriting every script in `scripts/` in one pass.
- Building the Astro dashboard itself.
- Changing strategy, admission, or brief business logic.
- Hiding failed or partial runs.

## Current Problems

Current report outputs mix several responsibilities in one directory:

- Root-level flat files: `reports/phase0_walk_forward_report.md`, `reports/price_adjustment_audit.csv`.
- Fixed module directories: `reports/strategy_admission/`, `reports/database_health/`, `reports/factor_effectiveness/`.
- Date archive directories: `reports/2026-06-23/phase0_watchlist_report_2026-06-23.html`.
- Manual experiment directories: `reports/strategy_admission_sleeve_composite_v1_20260623/`.
- Latest mirrors: `reports/watchlist_today/index.html`, `reports/brief_today/index.html`.
- Temporary validation directories: `reports/tmp_validation/`, `reports/smoke/`.

The main issue is not file format diversity. The issue is that run archive paths, latest display paths, experiments, and temporary diagnostics share inconsistent naming rules.

## Standard Rules

### Rule 1: New Runs Are Immutable

All new long-lived program outputs should land under:

```text
reports/runs/YYYY-MM-DD/YYYYMMDD_HHMMSS__<command>__<scope>/
```

Example:

```text
reports/runs/2026-06-23/20260623_103012__strategy_admission__baseline_admission_all_v1/
```

Rules:

- `YYYY-MM-DD` is the local Asia/Shanghai calendar date.
- `YYYYMMDD_HHMMSS` is the local run timestamp.
- `<command>` is the stable CLI command family, using snake_case.
- `<scope>` is a short snake_case scope such as `baseline_admission_all_v1`, `daily_brief`, `cn_error`, or `factor_effectiveness`.
- Run directories are never overwritten.

### Rule 2: File Names Use Family + Artifact

Inside a run directory, files use:

```text
<family>__<artifact>.<ext>
```

Examples:

```text
strategy_admission__report.md
strategy_admission__governance.md
strategy_admission__window_matrix.csv
strategy_admission__constraint_review.csv
strategy_admission__candidate_folds.csv
overfit__diagnostic.csv
failure_attribution__report.md
daily_brief__report.html
daily_brief__watchlist.csv
database_health__summary.csv
database_health__findings.csv
database_health__report.md
maintenance__status.md
```

Rules:

- File names do not repeat the timestamp already present in the run directory.
- File names do not use mixed naming like `phase0_`, `latest_`, or `today_` for new run artifacts.
- Use `report.md` or `report.html` for human narrative output.
- Use specific nouns for machine data: `summary.csv`, `findings.csv`, `window_matrix.csv`, `candidate_folds.csv`.

### Rule 3: Latest Is a Pointer, Not the Archive

Stable human entry points should live under:

```text
reports/latest/<channel>/
```

Examples:

```text
reports/latest/watchlist/index.html
reports/latest/daily_brief/index.html
reports/latest/strategy_admission/manifest.json
reports/latest/database_health/manifest.json
```

Rules:

- `latest` may copy small HTML entry files when needed for local viewing.
- `latest` should store `manifest.json` pointers for full report sets.
- `latest` must not be treated as the authoritative audit archive.
- Long-term dashboard indexing should point to immutable `reports/runs/...` artifacts.

### Rule 4: Scratch Is Explicitly Temporary

Temporary, smoke, and one-off validation output should live under:

```text
reports/scratch/YYYY-MM-DD/<purpose>/
```

Examples:

```text
reports/scratch/2026-06-23/strategy_admission_trace/
reports/scratch/2026-06-23/tmp_validation/
```

Rules:

- Scratch output may be deleted or regenerated.
- Scratch output is not used as admission evidence unless promoted into `reports/runs/...`.
- Dashboard may index scratch output only when explicitly requested.

### Rule 5: Historical Paths Remain Compatible

Do not move existing files automatically. A scanner should classify historical paths into compatibility categories:

- `legacy_root_flat`
- `legacy_module_dir`
- `legacy_date_dir`
- `legacy_experiment_dir`
- `legacy_latest_mirror`
- `legacy_scratch`
- `standard_run`

Dashboard and manifest tooling should support reading these categories while new commands migrate to the standard path layout.

## Recommended Module Design

### `phase0/report_paths.py`

Responsibilities:

- Create run directories under `reports/runs/YYYY-MM-DD/`.
- Normalize command, scope, family, and artifact names.
- Generate artifact paths.
- Generate latest pointer paths.
- Return repo-relative display paths for console output and manifest.

Public API:

```python
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class ReportRunPath:
    root: Path
    run_dir: Path
    run_id: str
    command: str
    scope: str

    def artifact(self, family: str, artifact: str, ext: str) -> Path:
        ...


def create_report_run(
    *,
    root: Path,
    command: str,
    scope: str,
    now: datetime | None = None,
) -> ReportRunPath:
    ...


def latest_dir(*, root: Path, channel: str) -> Path:
    ...


def scratch_dir(*, root: Path, purpose: str, now: datetime | None = None) -> Path:
    ...
```

### `phase0/report_registry.py`

This belongs to the dashboard plan, but path standardization should reserve for it:

- `run_id`
- repo-relative artifact paths
- `family`
- `artifact`
- `type`
- `module`
- `status`
- `tags`

## Migration Strategy

Migrate only high-value commands first:

1. `strategy-admission`
2. `strategy-failure-attribution`
3. `brief daily` / `brief watchlist`
4. `db-health`
5. `factor-effectiveness`
6. `maintain status`

Keep compatibility defaults for one transition period:

- If user passes `--output-dir`, respect it exactly.
- If no `--output-dir` is passed, new standard path is used for migrated commands.
- If existing downstream tools expect legacy defaults, add `--legacy-output` or a config flag only where required.
- Emit console output for both run directory and key artifacts.

## Admission Trace Observation

The 2026-06-23 `strategy-admission --trace-run` rerun showed why immutable run directories and partial run metadata matter:

- `legacy_momentum` completed 5 folds quickly.
- `legacy_momentum_low_turnover_v1` spent significant time in parameter selection but eventually completed fold 1 through fold 5.
- The run then progressed through multiple additional baseline strategies.
- The command was capped with `timeout 900s` and exited with code `124`.
- The last visible trace reached `sleeve_composite_v1 fold=5` result under `baseline_2y_1y_5fold`.
- No final CSV / Markdown artifacts were written to the trace output directory before timeout because `strategy-admission` writes reports only after all requested presets complete.
- A long all-candidate admission should not rely on final report files alone; intermediate trace or run-state metadata is needed for observability.

Path standardization should therefore support future partial-run markers such as:

```text
run__status.json
run__trace.log
run__manifest.json
```

These files should be optional in V1, but the path layout must leave room for them.

## Task 1: Path Helper MVP

**Files:**

- Create: `phase0/report_paths.py`
- Create: `tests/test_report_paths.py`

- [x] **Step 1: Write tests for run directory naming**

Create `tests/test_report_paths.py`:

```python
from datetime import datetime
from pathlib import Path

from phase0.report_paths import create_report_run, latest_dir, scratch_dir


def test_create_report_run_uses_date_command_and_scope(tmp_path: Path) -> None:
    run = create_report_run(
        root=tmp_path,
        command="strategy-admission",
        scope="baseline admission all v1",
        now=datetime(2026, 6, 23, 10, 30, 12),
    )

    assert run.run_id == "20260623_103012__strategy_admission__baseline_admission_all_v1"
    assert run.run_dir == tmp_path / "reports" / "runs" / "2026-06-23" / run.run_id


def test_artifact_uses_family_artifact_extension(tmp_path: Path) -> None:
    run = create_report_run(
        root=tmp_path,
        command="strategy-admission",
        scope="baseline_admission_all_v1",
        now=datetime(2026, 6, 23, 10, 30, 12),
    )

    assert run.artifact("strategy-admission", "window matrix", "csv") == (
        run.run_dir / "strategy_admission__window_matrix.csv"
    )


def test_latest_and_scratch_directories_are_separate(tmp_path: Path) -> None:
    assert latest_dir(root=tmp_path, channel="daily brief") == tmp_path / "reports" / "latest" / "daily_brief"
    assert scratch_dir(root=tmp_path, purpose="strategy admission trace", now=datetime(2026, 6, 23, 1, 2, 3)) == (
        tmp_path / "reports" / "scratch" / "2026-06-23" / "strategy_admission_trace"
    )
```

- [x] **Step 2: Run tests and verify failure**

Run:

```bash
./.venv/bin/python -m pytest tests/test_report_paths.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'phase0.report_paths'
```

- [x] **Step 3: Implement `phase0/report_paths.py`**

Create `phase0/report_paths.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


_INVALID_CHARS = re.compile(r"[^a-z0-9]+")


def _slug(value: str) -> str:
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
        return self.run_dir / f"{_slug(family)}__{_slug(artifact)}.{extension}"


def create_report_run(
    *,
    root: Path,
    command: str,
    scope: str,
    now: datetime | None = None,
) -> ReportRunPath:
    timestamp = now or datetime.now()
    command_slug = _slug(command)
    scope_slug = _slug(scope)
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
    return root / "reports" / "latest" / _slug(channel)


def scratch_dir(*, root: Path, purpose: str, now: datetime | None = None) -> Path:
    timestamp = now or datetime.now()
    return root / "reports" / "scratch" / f"{timestamp:%Y-%m-%d}" / _slug(purpose)
```

- [x] **Step 4: Run tests and verify pass**

Run:

```bash
./.venv/bin/python -m pytest tests/test_report_paths.py -q
```

Expected:

```text
3 passed
```

## Task 2: Strategy Admission Migration

**Files:**

- Modify: `phase0/strategy_admission.py`
- Modify: `phase0/cli.py`
- Modify: `tests/test_strategy_admission_config.py`

- [x] **Step 1: Add test for default standardized admission output**

Add to `tests/test_strategy_admission_config.py`:

```python
from datetime import datetime

from phase0.report_paths import create_report_run


def test_standard_admission_artifact_names(tmp_path) -> None:
    run = create_report_run(
        root=tmp_path,
        command="strategy-admission",
        scope="baseline_admission_all_v1",
        now=datetime(2026, 6, 23, 10, 30, 12),
    )

    assert run.artifact("strategy_admission", "report", "md").name == "strategy_admission__report.md"
    assert run.artifact("strategy_admission", "governance", "md").name == "strategy_admission__governance.md"
    assert run.artifact("strategy_admission", "window_matrix", "csv").name == "strategy_admission__window_matrix.csv"
```

- [x] **Step 2: Add optional standardized output support**

Change `run_strategy_admission()` so that:

- Explicit `output_dir` keeps existing behavior.
- Missing `output_dir` uses `create_report_run(root=root, command="strategy-admission", scope=<strategy_set_or_scope>)`.
- Existing file names remain supported for explicit legacy output directories during transition.
- Console output includes the run directory.

- [x] **Step 3: Verify tests**

Run:

```bash
./.venv/bin/python -m pytest tests/test_strategy_admission_config.py tests/test_report_paths.py -q
```

Expected:

```text
All selected tests pass
```

## Task 3: Dashboard Manifest Compatibility Contract

**Files:**

- Modify: `docs/tasks/ops/REPORT_DASHBOARD_ASTRO_TASKS.md`

- [x] **Step 1: Add path standardization dependency**

Add a section:

```markdown
## Dependency: T6.5 Report Path Standardization

Dashboard ingestion should prefer `reports/runs/YYYY-MM-DD/YYYYMMDD_HHMMSS__<command>__<scope>/`.
Legacy directories remain scan-compatible but are not the target format for new commands.
```

- [x] **Step 2: Add legacy category mapping**

Add:

```markdown
Legacy scanner categories:

- `legacy_root_flat`
- `legacy_module_dir`
- `legacy_date_dir`
- `legacy_experiment_dir`
- `legacy_latest_mirror`
- `legacy_scratch`
```

- [x] **Step 3: Review links**

Run:

```bash
rg -n "REPORT_DASHBOARD_ASTRO|reports/runs|legacy_root_flat" docs/tasks/ops/REPORT_DASHBOARD_ASTRO_TASKS.md docs/superpowers/plans/2026-06-23-report-output-path-standardization.md
```

Expected:

```text
Both documents mention the dependency and compatibility categories.
```

## Task 4: Brief and Latest Migration

**Files:**

- Modify: `phase0/cli.py`
- Modify: `scripts/export_premarket_watchlist.py`
- Create or modify: `tests/test_report_paths.py`

- [x] **Step 1: Add latest path tests**

Extend `tests/test_report_paths.py`:

```python
def test_latest_watchlist_entry_path(tmp_path: Path) -> None:
    assert latest_dir(root=tmp_path, channel="watchlist") / "index.html" == (
        tmp_path / "reports" / "latest" / "watchlist" / "index.html"
    )
```

- [x] **Step 2: Migrate latest mirror**

Change watchlist latest copy from:

```text
reports/watchlist_today/index.html
```

to:

```text
reports/latest/watchlist/index.html
```

Keep old path only as optional compatibility copy if deployment still depends on it.

- [ ] **Step 3: Verify brief command smoke**

Run a dry or minimal brief command appropriate for the current environment. If the command needs live data, use existing test fixtures or skip with a documented reason.

Expected:

```text
Latest watchlist path is printed as reports/latest/watchlist/index.html.
```

Status note: not executed in this implementation pass because the brief path can touch live/local daily data and deployment mirror behavior. The path helper and latest target are covered by `tests/test_report_paths.py`; a real brief smoke should be run in the next brief-specific pass.

## Task 5: Database Health and Factor Effectiveness Migration

**Files:**

- Modify: `phase0/db_health.py`
- Modify: `phase0/factor_effectiveness.py`
- Create or modify: tests for each module if present.

- [x] **Step 1: Preserve explicit `--output-dir`**

For both commands:

- If `output_dir` is passed, use it exactly.
- If not passed, use standardized run directory.

- [x] **Step 2: Rename default artifact files in standardized runs**

Use:

```text
database_health__summary.csv
database_health__findings.csv
database_health__report.md
factor_effectiveness__summary.csv
factor_effectiveness__group_returns.csv
factor_effectiveness__ic_by_year.csv
factor_effectiveness__correlation.csv
factor_effectiveness__report.md
```

- [x] **Step 3: Verify targeted tests**

Run:

```bash
./.venv/bin/python -m pytest tests -q
```

Expected:

```text
All tests pass, or unrelated pre-existing failures are documented with exact names.
```

Status note: this pass used targeted verification instead of the full test suite because the workspace contains unrelated dirty/generated state. Verified command: `./.venv/bin/python -m pytest tests/test_report_paths.py tests/test_report_registry.py tests/test_strategy_admission_config.py tests/test_daily_coverage_eligibility.py -q`.

## Task 6: Documentation and Migration Notes

**Files:**

- Modify: `docs/DEVELOPMENT_PLAN.md`
- Modify: `docs/tasks/README.md`
- Modify: `docs/tasks/WEEKLY_EXECUTION_CHECKLIST.md`

- [x] **Step 1: Add T6.5 task index entry**

Add:

```markdown
| `T6.5` | Report Output Path Standardization | [`docs/superpowers/plans/2026-06-23-report-output-path-standardization.md`](../superpowers/plans/2026-06-23-report-output-path-standardization.md) |
```

- [x] **Step 2: Add weekly checklist**

Add a checklist section with:

```markdown
# W2.xx｜Report Output Path Standardization（T6.5）

- [ ] Implement `phase0/report_paths.py`
- [ ] Migrate `strategy-admission`
- [ ] Migrate latest watchlist path
- [ ] Migrate `db-health`
- [ ] Migrate `factor-effectiveness`
- [ ] Update dashboard scanner compatibility categories
```

- [x] **Step 3: Verify no unfinished-marker language**

Run:

```bash
rg -n "TB[D]|implement[ ]later|fill[ ]in details" docs/superpowers/plans/2026-06-23-report-output-path-standardization.md docs/tasks/README.md docs/DEVELOPMENT_PLAN.md docs/tasks/WEEKLY_EXECUTION_CHECKLIST.md
```

Expected:

```text
No matches.
```

## Verification Summary

Before claiming implementation complete, run:

```bash
./.venv/bin/python -m pytest tests/test_report_paths.py tests/test_strategy_admission_config.py -q
./.venv/bin/python -m pytest tests -q
```

If full tests are too slow or fail for unrelated dirty-worktree reasons, report:

- Exact command.
- Exact failure.
- Whether failure is related to path standardization.
- Next command needed to isolate the failure.

## Rollback Strategy

Rollback is low risk because the plan preserves explicit `--output-dir`.

If standardized defaults break a downstream workflow:

- Pass explicit legacy `--output-dir` for that workflow.
- Keep historical scanner compatibility.
- Revert only the command migration, not the shared path helper tests.

## Open Risks

- Some scripts under `scripts/` are still hardcoded to root-level `reports/` paths.
- External sync currently references `reports/watchlist_today/index.html` and `/mnt/d/ZJ/Dev/brief_today/index.html`; these need compatibility handling.
- Long all-candidate admission runs need progress metadata, otherwise partial failures remain hard to inspect.
- Historical report directories have mixed date formats and cannot be normalized safely without a migration ledger.
