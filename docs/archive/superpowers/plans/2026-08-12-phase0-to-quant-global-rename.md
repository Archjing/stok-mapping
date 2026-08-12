# Phase0 to Quant Global Namespace Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the active `phase0` Python namespace and CLI identity with `quant`, while preserving current operational behavior, historical artifacts, and a time-bounded legacy CLI entry point.

**Architecture:** `quant` becomes the only canonical application package. All repository-owned Python imports, runtime commands, scheduler commands, tests, and active documentation move to `quant.*`. A minimal `phase0.cli` forwarding package remains temporarily so old operator commands invoke `quant.cli` without loading a second copy of domain modules; historical report names, SQLite schemas, strategy IDs, and local data paths are not mechanically renamed.

**Tech Stack:** Python 3.12, argparse, PyYAML, pytest, uv, SQLite, shell scheduler wrapper, Git worktree.

---

## Status and Execution Boundary

This document records a deferred, independent global refactor. Writing this plan does **not** authorize the rename now.

When execution is approved later:

- create an isolated Git worktree and a `codex/phase0-to-quant` branch;
- do not combine this migration with the China option analytics implementation or strategy research;
- do not copy local SQLite files, reports, logs, caches, or simulated-account ledgers into Git;
- preserve unrelated dirty changes in the main checkout;
- pause feature development while the package-move commit is in progress, because nearly every active Python module is affected.

Current impact snapshot recorded on 2026-08-12:

- approximately 134 files under `phase0/`;
- approximately 94 test files containing `phase0` references;
- approximately 23 scripts containing `phase0` references;
- approximately 39 documentation files containing `phase0` references;
- current canonical module entry: `python -m phase0.cli`;
- current console script: `stok-phase0 = "phase0.cli:main"`;
- current configuration root: `phase0:`;
- current scheduler wrapper invokes `phase0.cli maintain ...`.

Re-run the inventory at execution time; these counts are planning evidence, not fixed acceptance values.

## Migration Contract

### Names that must change

| Current | Canonical after migration |
| --- | --- |
| `phase0/` application package | `quant/` |
| `phase0.*` repository-owned imports | `quant.*` |
| `python -m phase0.cli` | `python -m quant.cli` |
| `stok-phase0` primary console script | `stok-quant` |
| `config.yaml` root key `phase0:` | `quant:` |
| `docs/PHASE0_CLI_USER_GUIDE.md` | `docs/QUANT_CLI_USER_GUIDE.md` |
| active documentation examples | `./runit ...` or `python -m quant.cli ...` |
| `phase0/cli_commands/phase0_run.py` | `quant/cli_commands/pipeline_run.py` |
| `PHASE0_RUN_COMMANDS` and matching handler names | neutral `PIPELINE_RUN_COMMANDS` names |

### Names that must not be mechanically changed

The namespace migration must not silently rewrite historical identity or data contracts:

- existing files such as `reports/phase0_*`;
- existing ledger files such as `data/simulated_trading/phase0_daily_account_ledger.csv`;
- report category directory `reports/phase0/` while existing readers still depend on it;
- existing SQLite table names, columns, migrations, and database paths;
- strategy IDs and candidate IDs already stored in reports or account records;
- Git history, archived design documents, archived reports, and research citations;
- user-owned local runtime assets under `data/`, `reports/`, and `logs/`.

These are compatibility identifiers, not Python package names. Any future artifact rename must have its own migration map and dual-read policy.

### Compatibility policy

During the compatibility window:

- `quant.*` is the only supported import namespace for new and repository-owned code;
- `python -m phase0.cli ...` remains available as a thin forwarder to `quant.cli.main`;
- `stok-phase0` remains as a deprecated console-script alias pointing to the same thin forwarder;
- arbitrary imports such as `from phase0.walk_forward import ...` are not maintained as a second package tree;
- `config.yaml` is written with `quant:`, while the loader temporarily accepts legacy `phase0:` with a deprecation warning;
- if both `quant:` and `phase0:` appear, startup fails rather than guessing which configuration wins.

This policy prevents `phase0.module` and `quant.module` from loading the same implementation under two module identities, which could split module-level state, monkeypatch targets, caches, and class identities.

The compatibility topology is intentionally narrow: do not create broad
`phase0.*` leaf-module wrappers, do not use `from quant... import *`, and do not
alias only the `phase0` root package. Those patterns make module identity and
monkeypatch behavior dependent on import order. The only retained Python
compatibility module is `phase0.cli`, which forwards to `quant.cli.main`; all
legacy domain imports must fail so the implementation cannot be loaded twice.

## File Map

| File or directory | Responsibility after migration |
| --- | --- |
| `quant/` | Canonical application package moved from `phase0/`. |
| `quant/cli.py` | Canonical CLI parser and dispatcher. |
| `quant/cli_commands/pipeline_run.py` | Neutral replacement for `phase0_run.py`. |
| `quant/config.py` | Select `quant:` config and temporarily read legacy `phase0:` safely. |
| `phase0/__init__.py` | Temporary deprecated compatibility-package marker only. |
| `phase0/cli.py` | Temporary legacy CLI forwarder; must import only `quant.cli`. |
| `phase0/__main__.py` | Optional forwarding support for `python -m phase0`; no domain logic. |
| `tests/test_quant_namespace_migration.py` | Namespace, compatibility, config, and duplicate-module guards. |
| `tests/test_cli_pipeline_run_commands.py` | Renamed command-registration and compatibility tests. |
| `tests/test_scheduler_shell_wrappers.py` | Proves scheduler uses `quant.cli`. |
| `scripts/run_project_scheduler.sh` | Production cron wrapper switched to `quant.cli`. |
| `runit` | Preferred local wrapper switched to `quant.cli`. |
| `pyproject.toml` | Adds `stok-quant`; retains deprecated `stok-phase0` temporarily. |
| `config.yaml` | Renames only the active root key to `quant:`; preserves artifact paths. |
| `docs/QUANT_CLI_USER_GUIDE.md` | Canonical operator guide. |
| `docs/PHASE0_CLI_USER_GUIDE.md` | Temporary short redirect/deprecation document. |
| `docs/architecture/PHASE0_TO_QUANT_COMPATIBILITY.md` | Records intentionally preserved legacy artifact names and removal criteria. |

## Task 1: Establish an Isolated Baseline

**Files:**
- Read: `AGENTS.md`
- Read: `pyproject.toml`
- Read: `config.yaml`
- Read: `scripts/run_project_scheduler.sh`
- Read: `runit`
- Create at execution time: isolated worktree outside the main checkout

- [ ] **Step 1: Create an isolated worktree**

Use the `superpowers:using-git-worktrees` skill. From the main checkout, resolve the current `main` commit and create a dedicated branch without carrying working-tree changes:

```bash
git rev-parse main
git worktree add ../stok-mapping-phase0-to-quant -b codex/phase0-to-quant main
```

Expected: a clean worktree at `../stok-mapping-phase0-to-quant` on `codex/phase0-to-quant`.

- [ ] **Step 2: Record the exact baseline**

Run inside the new worktree:

```bash
git status --short --branch
git rev-parse HEAD
rg -l "phase0" --glob '!.git/**' --glob '!data/**' --glob '!logs/**' --glob '!reports/**' . > /tmp/phase0-to-quant-inventory.txt
wc -l /tmp/phase0-to-quant-inventory.txt
```

Expected: clean status and a non-empty inventory. Save the commit hash in the implementation report, not in source code.

- [ ] **Step 3: Run the pre-migration test suite**

```bash
./.venv/bin/python -m pytest -q
```

Expected: all currently passing tests pass. Any pre-existing failures must be recorded with exact test IDs before migration proceeds; do not attribute them to the rename.

- [ ] **Step 4: Record current operator entry-point behavior**

```bash
./runit --help
./.venv/bin/python -m phase0.cli maintain tick --config config.yaml --dry-run --as-of "2026-08-12 08:00"
```

Expected: CLI help succeeds and the dry run reports scheduling decisions without starting tasks.

- [ ] **Step 5: Record the strategy registry baseline**

```bash
./.venv/bin/python -c 'import json; import phase0.strategies as s; rows = [{"strategy_id": name, "class_module": type(s.get_strategy(name)).__module__, "class_name": type(s.get_strategy(name)).__name__} for name in s.available_strategies()]; print(json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=True))' > /tmp/phase0-to-quant-strategy-registry-before.json
./.venv/bin/python -c 'import json; rows = json.load(open("/tmp/phase0-to-quant-strategy-registry-before.json", encoding="utf-8")); assert rows; assert len(rows) == len({row["strategy_id"] for row in rows}); print(f"strategies={len(rows)}")'
```

Expected: a non-empty, duplicate-free baseline containing each stable strategy
ID and its pre-migration class identity. The JSON file is an execution audit
artifact and must not be committed.

- [ ] **Step 6: Commit only a baseline note if required by the execution workflow**

Do not commit generated test output. If no tracked baseline document is required, make no commit for this task.

## Task 2: Add Migration Contract Tests Before Moving the Package

**Files:**
- Create: `tests/test_quant_namespace_migration.py`
- Modify later in this task: `tests/test_quant_namespace_migration.py`

- [ ] **Step 1: Write failing canonical-import tests**

Create `tests/test_quant_namespace_migration.py` with:

```python
from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_quant_cli_is_the_canonical_cli_module() -> None:
    module = importlib.import_module("quant.cli")
    assert callable(module.main)
    assert Path(module.__file__).resolve().is_relative_to(ROOT / "quant")


def test_quant_domain_module_has_one_canonical_identity() -> None:
    module = importlib.import_module("quant.walk_forward")
    assert module.__name__ == "quant.walk_forward"
    assert "phase0.walk_forward" not in sys.modules


def test_legacy_phase0_cli_forwards_to_quant_cli() -> None:
    legacy = importlib.import_module("phase0.cli")
    canonical = importlib.import_module("quant.cli")
    assert legacy.main is canonical.main


def test_legacy_domain_import_is_not_a_second_supported_namespace() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("phase0.walk_forward")


def test_quant_cli_module_help_succeeds() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "quant.cli", "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "usage:" in completed.stdout.lower()


@pytest.mark.parametrize(
    "imports",
    [
        ("phase0.cli", "quant.cli", "quant.strategies"),
        ("quant.strategies", "quant.cli", "phase0.cli"),
    ],
)
def test_import_order_does_not_split_strategy_registry_identity(
    imports: tuple[str, str, str],
) -> None:
    script = f"""
import importlib
import json
import sys

for name in {imports!r}:
    importlib.import_module(name)

strategies = importlib.import_module("quant.strategies")
registry = importlib.import_module("quant.strategies.registry")
strategy_names = strategies.available_strategies()
strategy_classes = {{
    name: type(strategies.get_strategy(name))
    for name in strategy_names
}}
assert strategy_names
assert len(strategy_names) == len(set(strategy_names))
assert all(cls.__module__.startswith("quant.strategies.") for cls in strategy_classes.values())
assert "phase0.strategies" not in sys.modules
assert not any(name.startswith("phase0.strategies.") for name in sys.modules)
assert strategies.available_strategies is registry.available_strategies
print(json.dumps(strategy_names))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip().startswith("[")
```

- [ ] **Step 2: Run the tests and verify the canonical namespace is missing**

```bash
./.venv/bin/python -m pytest tests/test_quant_namespace_migration.py -q
```

Expected: failures include `ModuleNotFoundError: No module named 'quant'`.

- [ ] **Step 3: Add a repository-owned import guard**

Append:

```python
def test_repository_owned_python_does_not_import_phase0_domain_modules() -> None:
    roots = [ROOT / "quant", ROOT / "scripts", ROOT / "tests"]
    violations: list[str] = []
    allowed = {
        ROOT / "tests" / "test_quant_namespace_migration.py",
    }
    for base in roots:
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if path in allowed:
                continue
            text = path.read_text(encoding="utf-8")
            for line_number, line in enumerate(text.splitlines(), start=1):
                stripped = line.strip()
                if stripped.startswith("from phase0") or stripped.startswith("import phase0"):
                    violations.append(f"{path.relative_to(ROOT)}:{line_number}:{stripped}")
    assert violations == []
```

Expected before migration: the test fails with a concrete list of old imports.

The subprocess cases are mandatory because `quant.strategies.__init__` imports
all built-in strategies for registration. An in-process test that runs after
pytest has already populated `sys.modules` cannot prove that legacy-first and
canonical-first startup produce the same registry and class identities.

- [ ] **Step 4: Commit the red migration contract**

```bash
git add tests/test_quant_namespace_migration.py
git commit -m "test: define quant namespace migration contract"
```

## Task 3: Move the Canonical Python Package

**Files:**
- Move: `phase0/` to `quant/`
- Create: `phase0/__init__.py`
- Create: `phase0/cli.py`
- Create: `phase0/__main__.py`
- Modify: all `*.py` files under `quant/`, `tests/`, and `scripts/` that import `phase0.*`

- [ ] **Step 1: Move the package as one Git operation**

```bash
git mv phase0 quant
mkdir phase0
```

Expected: Git recognizes most application files as renames rather than delete/add pairs.

- [ ] **Step 2: Mechanically migrate repository-owned imports**

Replace only Python import/module-path references in tracked Python files:

```text
from phase0...  -> from quant...
import phase0... -> import quant...
"phase0.module" -> "quant.module" when used by importlib or monkeypatch
'phase0.module' -> 'quant.module' when used by importlib or monkeypatch
```

Do not globally replace report filenames, database paths, strategy IDs, explanatory history, or archived documentation.

Run after editing:

```bash
rg -n '^(from phase0|import phase0)|["'"']phase0\.[A-Za-z_]' quant tests scripts --glob '*.py'
```

Expected: only the intentional legacy-compatibility assertions in `tests/test_quant_namespace_migration.py` remain.

- [ ] **Step 3: Create the minimal legacy CLI package**

Create `phase0/__init__.py`:

```python
"""Deprecated CLI compatibility package.

Application code lives under :mod:`quant`. Only ``phase0.cli`` is retained
temporarily so existing operator commands can forward to the canonical CLI.
"""
```

Create `phase0/cli.py`:

```python
from __future__ import annotations

import sys

from quant.cli import main


def _warn() -> None:
    print(
        "DEPRECATION: 'python -m phase0.cli' is deprecated; use "
        "'python -m quant.cli' or './runit'.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    _warn()
    raise SystemExit(main())
```

Create `phase0/__main__.py`:

```python
from __future__ import annotations

from phase0.cli import _warn, main


if __name__ == "__main__":
    _warn()
    raise SystemExit(main())
```

The shim must not alias `sys.modules`, extend `__path__`, or import any `phase0` domain module.

- [ ] **Step 4: Verify canonical and legacy CLI imports**

```bash
./.venv/bin/python -m pytest tests/test_quant_namespace_migration.py -q
./.venv/bin/python -m quant.cli --help
./.venv/bin/python -m phase0.cli --help
```

Expected: tests pass; both commands return zero; only the legacy command emits the deprecation line.

- [ ] **Step 5: Compare the strategy registry with the recorded baseline**

```bash
./.venv/bin/python -c 'import json; import quant.strategies as s; before = json.load(open("/tmp/phase0-to-quant-strategy-registry-before.json", encoding="utf-8")); before_ids = [row["strategy_id"] for row in before]; after_ids = s.available_strategies(); assert after_ids == before_ids, (before_ids, after_ids); classes = [type(s.get_strategy(name)) for name in after_ids]; assert all(cls.__module__.startswith("quant.strategies.") for cls in classes); assert len(classes) == len({id(cls) for cls in classes}); print(f"strategies={len(after_ids)} registry_identity=canonical")'
```

Expected: the strategy ID list is byte-for-byte identical to the baseline,
every class belongs to `quant.strategies.*`, and each registered ID resolves to
one canonical class. This is a blocking gate because strategy registration is
performed through import-time decorators in `quant.strategies.__init__`.

- [ ] **Step 6: Commit the package move**

```bash
git add quant phase0 tests scripts
git commit -m "refactor: move application namespace to quant"
```

## Task 4: Rename Phase-Specific Internal Code Symbols

**Files:**
- Move: `quant/cli_commands/phase0_run.py` to `quant/cli_commands/pipeline_run.py`
- Modify: `quant/cli.py`
- Modify: `quant/cli_commands/pipeline_run.py`
- Move: `tests/test_cli_phase0_run_commands.py` to `tests/test_cli_pipeline_run_commands.py`
- Modify: `tests/test_cli_pipeline_run_commands.py`
- Modify: modules importing `export_phase0_*` from `quant/reporting/exports.py`
- Modify: `quant/reporting/exports.py`

- [ ] **Step 1: Rename the run command module and its test**

```bash
git mv quant/cli_commands/phase0_run.py quant/cli_commands/pipeline_run.py
git mv tests/test_cli_phase0_run_commands.py tests/test_cli_pipeline_run_commands.py
```

- [ ] **Step 2: Rename active Python identifiers without changing CLI behavior**

Use these exact mappings:

```text
PHASE0_RUN_COMMANDS -> PIPELINE_RUN_COMMANDS
register_phase0_run_commands -> register_pipeline_run_commands
handle_phase0_run_command -> handle_pipeline_run_command
run_phase0 -> run_pipeline
run_phase0_cost_sensitivity -> run_pipeline_cost_sensitivity
phase0_run_cli -> pipeline_run_cli
```

Keep the user-visible subcommands such as `run` and `cost-sensitivity` unchanged.

- [ ] **Step 3: Rename active export helper identifiers**

In `quant/reporting/exports.py` and callers, use:

```text
export_phase0_low_turnover_bill -> export_low_turnover_bill
export_phase0_market_regime_report -> export_market_regime_report
export_phase0_oos_report -> export_oos_report
export_phase0_financial_pti -> export_financial_pti
export_phase0_universe_pit -> export_universe_pit
export_phase0_premarket -> export_premarket
export_phase0_execution_gate -> export_execution_gate
```

Do not rename output files in the same task. Function names are code identity; output paths are compatibility contracts.

- [ ] **Step 4: Update tests to patch canonical paths**

Every monkeypatch/import string must target `quant.*`. For example:

```python
monkeypatch.setattr("quant.reporting.quant_static_site.subprocess.run", fake_run)
```

Dynamic import tests must use names such as:

```python
module = importlib.import_module("quant.data_governance.cross_market_reference_history")
```

- [ ] **Step 5: Run focused tests**

```bash
./.venv/bin/python -m pytest \
  tests/test_cli_pipeline_run_commands.py \
  tests/test_cli_research_commands.py \
  tests/test_cli_strategy_research_commands.py \
  tests/test_cli_report_output_paths.py \
  tests/test_reporting_script_wrappers.py \
  tests/test_data_governance_script_wrappers.py \
  tests/test_intelligence_script_wrappers.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit internal naming cleanup**

```bash
git add quant tests scripts
git commit -m "refactor: remove phase-specific internal code names"
```

## Task 5: Migrate the Configuration Root Safely

**Files:**
- Modify: `quant/config.py`
- Modify: `config.yaml`
- Modify: `quant/cli_commands/pipeline_run.py`
- Modify: `quant/cli_commands/strategy_research.py`
- Modify: `quant/cli_commands/data_governance.py`
- Modify: `quant/cli_commands/research.py`
- Modify: `quant/research/core_coverage/core_reachability.py`
- Modify: `tests/test_quant_namespace_migration.py`
- Modify: `tests/test_maintenance_orchestrator.py`
- Modify: tests containing inline `phase0:` YAML fixtures

- [ ] **Step 1: Write failing configuration-selection tests**

Append to `tests/test_quant_namespace_migration.py`:

```python
from quant.config import select_quant_config


def test_select_quant_config_prefers_the_only_canonical_root() -> None:
    assert select_quant_config({"quant": {"benchmark_symbol": "SH.000300"}}) == {
        "benchmark_symbol": "SH.000300"
    }


def test_select_quant_config_accepts_legacy_root_with_warning() -> None:
    with pytest.warns(DeprecationWarning, match="phase0"):
        result = select_quant_config({"phase0": {"benchmark_symbol": "SH.000300"}})
    assert result["benchmark_symbol"] == "SH.000300"


def test_select_quant_config_rejects_ambiguous_dual_roots() -> None:
    with pytest.raises(ValueError, match="both 'quant' and legacy 'phase0'"):
        select_quant_config({"quant": {}, "phase0": {}})


def test_select_quant_config_rejects_missing_roots() -> None:
    with pytest.raises(ValueError, match="missing 'quant' section"):
        select_quant_config({})
```

- [ ] **Step 2: Verify the tests fail**

```bash
./.venv/bin/python -m pytest tests/test_quant_namespace_migration.py -q
```

Expected: failure because `select_quant_config` is not defined.

- [ ] **Step 3: Implement one configuration selector**

Replace `quant/config.py` with behavior equivalent to:

```python
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, Mapping

import yaml

from quant.env import load_project_env


def select_quant_config(data: Mapping[str, Any]) -> dict[str, Any]:
    has_quant = "quant" in data
    has_legacy = "phase0" in data
    if has_quant and has_legacy:
        raise ValueError("config contains both 'quant' and legacy 'phase0' sections")
    if has_quant:
        selected = data["quant"]
    elif has_legacy:
        warnings.warn(
            "config root 'phase0' is deprecated; rename it to 'quant'",
            DeprecationWarning,
            stacklevel=2,
        )
        selected = data["phase0"]
    else:
        raise ValueError("config.yaml missing 'quant' section")
    if not isinstance(selected, dict):
        raise ValueError("selected quant configuration must be a mapping")
    return selected


def load_config_document(config_path: Path) -> dict[str, Any]:
    load_project_env(config_path.parent)
    with config_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError("config document must be a mapping")
    return data


def load_config(config_path: Path) -> dict[str, Any]:
    return select_quant_config(load_config_document(config_path))
```

- [ ] **Step 4: Replace scattered root selection**

Replace constructs such as:

```python
cfg.get("phase0", cfg)
```

with:

```python
select_quant_config(cfg)
```

Import `select_quant_config` from `quant.config`. This applies to the exact files listed in this task. The selector must be the only place that accepts the legacy root.

- [ ] **Step 5: Rename only the root key in the real configuration**

In `config.yaml`, change:

```yaml
phase0:
```

to:

```yaml
quant:
```

Do not alter nested values such as existing ledger filenames or report output paths in this task.

- [ ] **Step 6: Update active YAML fixtures**

Tests exercising current configuration use `quant:`. Keep one explicit legacy fixture only in `tests/test_quant_namespace_migration.py`.

- [ ] **Step 7: Run focused configuration tests**

```bash
./.venv/bin/python -m pytest \
  tests/test_quant_namespace_migration.py \
  tests/test_maintenance_orchestrator.py \
  tests/test_cli_pipeline_run_commands.py \
  tests/test_cli_research_commands.py \
  tests/test_cli_strategy_research_commands.py \
  tests/test_cli_data_governance_commands.py -q
```

Expected: all tests pass and current `config.yaml` loads through `quant:`.

- [ ] **Step 8: Commit the configuration migration**

```bash
git add quant/config.py quant/cli_commands quant/research config.yaml tests
git commit -m "refactor: migrate configuration root to quant"
```

## Task 6: Switch Packaging and Human-Facing CLI Entry Points

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `runit`
- Modify: `tests/test_quant_namespace_migration.py`
- Create locally, do not commit: `/tmp/stok-mapping-quant-wheel-venv/`

- [ ] **Step 1: Write console-entry assertions**

Append a TOML-level test:

```python
import tomllib


def test_pyproject_exposes_quant_and_temporary_legacy_cli_aliases() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = data["project"]["scripts"]
    assert scripts["stok-quant"] == "quant.cli:main"
    assert scripts["stok-phase0"] == "phase0.cli:main"


def test_runit_invokes_quant_cli() -> None:
    text = (ROOT / "runit").read_text(encoding="utf-8")
    assert "-m quant.cli" in text
    assert "-m phase0.cli" not in text


def test_reporting_package_data_is_declared() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_data = data["tool"]["setuptools"]["package-data"]["quant.reporting"]
    assert "templates/*.html" in package_data
    assert "static/*.css" in package_data
    assert "static/research/*.html" in package_data
```

- [ ] **Step 2: Verify entry-point tests fail**

```bash
./.venv/bin/python -m pytest tests/test_quant_namespace_migration.py -q
```

Expected: failures mention missing `stok-quant`, the old `runit` target, and
missing package-data declarations.

- [ ] **Step 3: Update console scripts**

Set the console scripts and an explicit build backend/package-data contract:

```toml
[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

[project.scripts]
stok-quant = "quant.cli:main"
stok-phase0 = "phase0.cli:main"

[tool.setuptools.packages.find]
include = ["quant*", "phase0*"]

[tool.setuptools.package-data]
"quant.reporting" = [
  "templates/*.html",
  "static/*.css",
  "static/research/*.html",
]
```

`stok-phase0` is compatibility-only and will be removed in Task 12 after the observation window.
If `static/research/*.html` has no tracked files at execution time, keep the
declaration for future pages but do not add local generated research pages to
the migration commit solely to satisfy the glob.

- [ ] **Step 4: Update the local wrapper**

Change the final line of `runit` to:

```bash
exec "${PYTHON_BIN}" -m quant.cli "$@"
```

- [ ] **Step 5: Regenerate the lock metadata**

```bash
uv lock
uv sync
```

Expected: project environment exposes both `stok-quant` and the temporary alias.

- [ ] **Step 6: Verify every supported entry point**

```bash
./runit --help
./.venv/bin/python -m quant.cli --help
./.venv/bin/python -m phase0.cli --help
./.venv/bin/stok-quant --help
./.venv/bin/stok-phase0 --help
```

Expected: all commands return zero; only legacy forms print the deprecation message.

- [ ] **Step 7: Build a wheel and inspect its contents**

```bash
rm -rf dist
uv build --wheel
./.venv/bin/python -m zipfile -l dist/stok_mapping-*.whl
```

Expected: the wheel contains both `quant/` and the thin `phase0/` compatibility
package, plus `quant/reporting/templates/account_bill.html`,
`quant/reporting/templates/watchlist.html`, and
`quant/reporting/static/style.css`. Tracked research HTML files, if any, must
also be present.

- [ ] **Step 8: Install the wheel into a clean environment**

```bash
rm -rf /tmp/stok-mapping-quant-wheel-venv
uv venv --python 3.12 /tmp/stok-mapping-quant-wheel-venv
uv pip install --python /tmp/stok-mapping-quant-wheel-venv/bin/python dist/stok_mapping-*.whl
cd /tmp
/tmp/stok-mapping-quant-wheel-venv/bin/stok-quant --help
/tmp/stok-mapping-quant-wheel-venv/bin/stok-phase0 --help
/tmp/stok-mapping-quant-wheel-venv/bin/python -c 'from importlib.resources import files; root = files("quant.reporting"); assert root.joinpath("templates/account_bill.html").is_file(); assert root.joinpath("templates/watchlist.html").is_file(); assert root.joinpath("static/style.css").is_file()'
```

Expected: dependency installation succeeds, both installed console scripts
return zero outside the repository, the legacy script emits its deprecation
message, and all required reporting resources resolve from the installed wheel.
Running from `/tmp` is required so the source checkout cannot mask a broken
wheel.

- [ ] **Step 9: Commit the packaging switch**

```bash
git add pyproject.toml uv.lock runit tests/test_quant_namespace_migration.py
git commit -m "build: expose quant CLI entry points"
```

## Task 7: Switch Scheduler and Operational Scripts

**Files:**
- Modify: `scripts/run_project_scheduler.sh`
- Modify: `scripts/run_daily_brief_pipeline.sh`
- Modify: `scripts/update_manual_history_daily.sh`
- Modify: `scripts/update_financial_factors_weekly.sh`
- Modify: every repository-owned shell/Python wrapper found by `rg -n 'phase0\.cli|from phase0|import phase0' scripts`
- Modify: `quant/maintenance_orchestrator.py`
- Modify: `tests/test_scheduler_shell_wrappers.py`
- Modify: scheduler-related CLI tests containing `sys.argv = ["phase0.cli", ...]`
- Modify: `tests/test_maintenance_orchestrator.py`

- [ ] **Step 1: Make scheduler tests require the canonical CLI**

Update `tests/test_scheduler_shell_wrappers.py` so the scheduler assertion is equivalent to:

```python
def test_project_scheduler_invokes_quant_cli() -> None:
    text = (ROOT / "scripts" / "run_project_scheduler.sh").read_text(encoding="utf-8")
    assert text.count("-m quant.cli") == 2
    assert "-m phase0.cli" not in text
```

- [ ] **Step 2: Verify the scheduler test fails**

```bash
./.venv/bin/python -m pytest tests/test_scheduler_shell_wrappers.py -q
```

Expected: failure because the wrapper still invokes `phase0.cli`.

- [ ] **Step 3: Switch scheduler warm-up and tick commands**

In `scripts/run_project_scheduler.sh`, use:

```bash
"${PYTHON_BIN}" -m quant.cli maintain status --config "${CONFIG_PATH}" >/dev/null

exec "${PYTHON_BIN}" -m quant.cli maintain tick --config "${CONFIG_PATH}"
```

- [ ] **Step 4: Switch every built-in scheduler command**

In `quant/maintenance_orchestrator.py`, every command assembled as:

```python
str(python_bin), "-m", "phase0.cli"
```

must become:

```python
str(python_bin), "-m", "quant.cli"
```

This ensures scheduled child tasks never depend on the compatibility shim.

- [ ] **Step 5: Add an execution-boundary normalizer for persisted commands**

Add this helper near the subprocess execution helpers in
`quant/maintenance_orchestrator.py`:

```python
from collections.abc import Sequence


def _effective_maintenance_command(command: Sequence[str]) -> list[str]:
    effective = [str(part) for part in command]
    for index in range(len(effective) - 1):
        if effective[index] == "-m" and effective[index + 1] == "phase0.cli":
            effective[index + 1] = "quant.cli"
    return effective
```

Use it immediately before every execution of a command read from persisted
`command_json`, especially `maintenance_resume`:

```python
original_command = [str(part) for part in json.loads(str(row["command_json"]))]
effective_command = _effective_maintenance_command(original_command)
log_path = _resolve_path(root, str(row["log_path"]))

if not dry_run:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handle = log_path.open("ab")
    if effective_command != original_command:
        audit_line = (
            "maintenance_command_normalized "
            f"original={json.dumps(original_command, ensure_ascii=False)} "
            f"effective={json.dumps(effective_command, ensure_ascii=False)}\n"
        )
        handle.write(audit_line.encode("utf-8"))
    process = subprocess.Popen(
        effective_command,
        stdout=handle,
        stderr=subprocess.STDOUT,
        cwd=str(root),
        start_new_session=True,
    )
```

Do not update historical `maintenance_runs.command_json` or
`maintenance_shards.command_json`. They remain the original audit record; the
log records the effective command used after migration.

- [ ] **Step 6: Test legacy persisted-command recovery**

Add focused tests to `tests/test_maintenance_orchestrator.py`:

```python
from quant.maintenance_orchestrator import _effective_maintenance_command


def test_effective_command_migrates_only_the_legacy_cli_module() -> None:
    original = ["/tmp/python", "-m", "phase0.cli", "run", "--config", "config.yaml"]

    effective = _effective_maintenance_command(original)

    assert original[2] == "phase0.cli"
    assert effective == ["/tmp/python", "-m", "quant.cli", "run", "--config", "config.yaml"]


def test_effective_command_preserves_non_cli_phase0_artifact_arguments() -> None:
    original = [
        "/tmp/python",
        "-m",
        "quant.cli",
        "export",
        "--output",
        "reports/phase0/example.json",
    ]

    assert _effective_maintenance_command(original) == original
```

Also add a `maintenance_resume` test that seeds a temporary shard with legacy
`command_json`, monkeypatches `quant.maintenance_orchestrator.subprocess.Popen`,
and asserts the spawned command contains `quant.cli` while the SQLite row still
contains `phase0.cli`.

Run:

```bash
./.venv/bin/python -m pytest \
  tests/test_maintenance_orchestrator.py \
  -k 'effective_command or resume' -q
```

Expected: command normalization and immutable audit-history tests pass.

- [ ] **Step 7: Switch remaining active wrappers**

Update active shell/Python scripts to import `quant.*` and invoke `quant.cli`. Historical text in archived docs is not part of this task.

- [ ] **Step 8: Run scheduler and wrapper tests**

```bash
./.venv/bin/python -m pytest \
  tests/test_scheduler_shell_wrappers.py \
  tests/test_maintenance_orchestrator.py \
  tests/test_data_governance_script_wrappers.py \
  tests/test_reporting_script_wrappers.py \
  tests/test_intelligence_script_wrappers.py -q
```

Expected: all selected tests pass.

- [ ] **Step 9: Exercise the scheduler read-only path**

```bash
./.venv/bin/python -m quant.cli maintain tick \
  --config config.yaml \
  --dry-run \
  --as-of "2026-08-12 08:00"
```

Expected: scheduling decisions are printed and no task process is started.

- [ ] **Step 10: Commit operational entry-point migration**

```bash
git add scripts quant/maintenance_orchestrator.py tests
git commit -m "ops: switch scheduler to quant CLI"
```

## Task 8: Preserve Historical Artifacts Explicitly

**Files:**
- Create: `docs/architecture/PHASE0_TO_QUANT_COMPATIBILITY.md`
- Modify: `quant/reporting/paths.py`
- Modify: `quant/reporting/registry.py`
- Modify: `tests/test_report_registry.py`
- Modify: `tests/test_execution_reporting_compatibility.py`
- Modify: `tests/test_premarket_account_holding_days.py`

- [ ] **Step 1: Write the compatibility document**

Create `docs/architecture/PHASE0_TO_QUANT_COMPATIBILITY.md` containing this explicit table:

```markdown
# Phase0 to Quant Compatibility Boundaries

`quant` is the application namespace. The following `phase0` strings remain
because they identify existing persisted artifacts rather than Python modules.

| Legacy identifier | Policy |
| --- | --- |
| `reports/phase0/` | Keep readable and writable until a separate artifact migration is approved. |
| `reports/phase0_*` | Keep existing filenames stable. New report families may use neutral names. |
| `data/simulated_trading/phase0_daily_account_ledger.csv` | Keep as configured persisted account state. |
| `data/simulated_trading/phase0_daily_brief_ledger.csv` | Keep as configured persisted brief state. |
| SQLite schemas and rows containing `phase0` | Do not rewrite in the namespace migration. |
| archived documents and Git history | Do not rewrite. |
```

- [ ] **Step 2: Name legacy report behavior in code**

In `quant/reporting/paths.py`, retain the existing mapping but make intent explicit:

```python
LEGACY_PHASE0_REPORT_CATEGORY = "phase0"

DEFAULT_REPORT_CATEGORY_PATHS = {
    # Persisted artifact namespace retained across the Python package rename.
    LEGACY_PHASE0_REPORT_CATEGORY: "phase0",
    # existing remaining mappings follow
}
```

Use the actual existing mapping variable name if it differs; do not introduce a duplicate registry.

- [ ] **Step 3: Preserve legacy discovery behavior**

Keep report registry matching for filenames beginning with `phase0_watchlist` and `phase0_premarket`. Add a regression test proving a pre-migration report is still classified after imports move to `quant.reporting.registry`.

Example assertion:

```python
def test_quant_registry_still_classifies_legacy_premarket_artifact(tmp_path) -> None:
    path = tmp_path / "phase0_premarket_watchlist_2026-08-12.csv"
    path.write_text("symbol\nSH.512480\n", encoding="utf-8")
    result = classify_legacy_artifact(path)
    assert result is not None
```

- [ ] **Step 4: Confirm no persisted path changed accidentally**

```bash
git diff main...HEAD -- config.yaml quant | rg 'phase0_daily|reports/phase0|phase0_premarket|phase0_watchlist'
```

Expected: differences are comments/import context only; persisted values remain byte-for-byte unchanged unless a test requires an explicit compatibility constant.

- [ ] **Step 5: Run artifact compatibility tests**

```bash
./.venv/bin/python -m pytest \
  tests/test_report_registry.py \
  tests/test_execution_reporting_compatibility.py \
  tests/test_premarket_account_holding_days.py \
  tests/test_premarket_watchlist_html.py -q
```

Expected: old artifact names remain readable.

- [ ] **Step 6: Commit compatibility boundaries**

```bash
git add docs/architecture/PHASE0_TO_QUANT_COMPATIBILITY.md quant/reporting tests
git commit -m "docs: preserve legacy phase0 artifact contracts"
```

## Task 9: Handle Cache and Runtime Identity Changes

**Files:**
- Modify: `quant/walk_forward.py`
- Modify: `quant/reporting/strategy_bill.py`
- Modify: cache-related tests for walk-forward and reporting
- Modify: `docs/architecture/PHASE0_TO_QUANT_COMPATIBILITY.md`

- [ ] **Step 1: Add a cache namespace version**

In `quant/walk_forward.py`, add near cache-key construction:

```python
CACHE_NAMESPACE_VERSION = "quant-v1"
```

Include it in every prepared-panel and fold-cache key payload:

```python
cache_key_payload["namespace_version"] = CACHE_NAMESPACE_VERSION
```

If the current implementation builds a tuple rather than a dictionary, prepend `CACHE_NAMESPACE_VERSION` to that tuple. Use one constant for all walk-forward cache families.

- [ ] **Step 2: Add an equivalent report-panel cache version**

In `quant/reporting/strategy_bill.py`, include:

```python
PANEL_CACHE_NAMESPACE_VERSION = "quant-v1"
```

and incorporate it into the cache key before `pd.read_pickle` or `pd.to_pickle` is used.

- [ ] **Step 3: Test that old cache identities are rejected**

Construct a temporary cache payload with the pre-migration key and assert the canonical code recomputes rather than accepting it. The assertion must verify behavior, not deletion of the old file.

- [ ] **Step 4: Document local-cache behavior**

Add:

```markdown
Runtime caches are disposable. The namespace migration bumps the cache-key
version to `quant-v1`; old cache files remain on disk but are ignored. The
migration does not delete user-owned cache files automatically.
```

- [ ] **Step 5: Run focused cache tests**

Run the exact existing cache test files identified by:

```bash
rg -l "prepared.*cache|fold.*cache|panel.*cache|read_pickle|to_pickle" tests --glob 'test_*.py'
```

Then pass that explicit file list to `pytest -q`. Expected: all identified tests pass, including the new stale-key regression.

- [ ] **Step 6: Commit cache identity protection**

```bash
git add quant/walk_forward.py quant/reporting/strategy_bill.py tests docs/architecture/PHASE0_TO_QUANT_COMPATIBILITY.md
git commit -m "fix: isolate caches after quant namespace migration"
```

## Task 10: Update Active Documentation Without Rewriting History

**Files:**
- Move: `docs/PHASE0_CLI_USER_GUIDE.md` to `docs/QUANT_CLI_USER_GUIDE.md`
- Create: `docs/PHASE0_CLI_USER_GUIDE.md`
- Modify: `README.md`
- Modify: active files under `docs/` that instruct operators to run `phase0.cli`
- Do not modify: archived reports and historical plans solely to replace names

- [ ] **Step 1: Move the canonical CLI guide**

```bash
git mv docs/PHASE0_CLI_USER_GUIDE.md docs/QUANT_CLI_USER_GUIDE.md
```

Update its title and active examples to prefer:

```bash
./runit <command>
```

When the full Python form is useful, use:

```bash
./.venv/bin/python -m quant.cli <command>
```

- [ ] **Step 2: Add a short redirect at the old documentation path**

Create `docs/PHASE0_CLI_USER_GUIDE.md`:

```markdown
# Deprecated Phase0 CLI Guide Path

The application CLI is now documented in
[`QUANT_CLI_USER_GUIDE.md`](QUANT_CLI_USER_GUIDE.md).

Use `./runit ...` or `./.venv/bin/python -m quant.cli ...`.
The legacy `python -m phase0.cli ...` entry point is temporary.
```

- [ ] **Step 3: Update active README instructions**

Replace current operator commands and architecture statements with `quant.cli` and `quant.*`. Keep sentences that explicitly describe legacy filenames or historical results.

- [ ] **Step 4: Classify remaining documentation references**

Run:

```bash
rg -n "phase0\.cli|phase0/|phase0\." README.md docs --glob '*.md'
```

For every remaining hit, classify it as one of:

- compatibility documentation;
- persisted artifact path;
- historical/archived record;
- stale active instruction that must be corrected.

No stale active instruction may remain.

- [ ] **Step 5: Commit documentation migration**

```bash
git add README.md docs
git commit -m "docs: make quant the canonical project namespace"
```

## Task 11: Run Full Migration Verification

**Files:**
- Modify only if verification exposes migration defects
- Create locally, do not commit: `/tmp/phase0-to-quant-final-audit.txt`

- [ ] **Step 1: Run the namespace guard**

```bash
./.venv/bin/python -m pytest tests/test_quant_namespace_migration.py -q
```

Expected: all migration contract tests pass.

- [ ] **Step 2: Audit repository-owned Python imports**

```bash
rg -n '^(from phase0|import phase0)|["'"']phase0\.[A-Za-z_]' quant tests scripts --glob '*.py' > /tmp/phase0-to-quant-final-audit.txt
```

Expected: only explicit compatibility-test strings remain. Review the file manually; do not accept unrelated hits.

- [ ] **Step 3: Compile canonical and compatibility packages**

```bash
./.venv/bin/python -m compileall -q quant phase0
```

Expected: exit code zero.

- [ ] **Step 4: Run the complete test suite**

```bash
./.venv/bin/python -m pytest -q
```

Expected: no new failure relative to Task 1. Pre-existing failures must match the recorded IDs and failure reasons exactly.

- [ ] **Step 5: Verify read-only operational commands**

```bash
./runit --help
./runit system status --config config.yaml
./runit maintain tick --config config.yaml --dry-run --as-of "2026-08-12 08:00"
./.venv/bin/python -m phase0.cli --help
```

Expected: canonical commands succeed; the legacy command succeeds with a deprecation message.

- [ ] **Step 6: Verify installed console scripts**

```bash
uv sync
./.venv/bin/stok-quant --help
./.venv/bin/stok-phase0 --help
```

Expected: both succeed; `stok-phase0` is visibly deprecated.

- [ ] **Step 7: Inspect the Git diff for forbidden artifact rewrites**

```bash
git diff --stat main...HEAD
git diff main...HEAD -- config.yaml | rg 'phase0_daily|phase0_premarket|reports/phase0'
git status --short
```

Expected: application-package rename is large but focused; persisted artifact paths remain unchanged; the worktree contains no databases, reports, logs, caches, or generated site files.

- [ ] **Step 8: Request code review**

Use `superpowers:requesting-code-review`. The review must explicitly evaluate:

- duplicate module identity;
- scheduler entry points;
- config ambiguity handling;
- package-data paths for templates/static assets;
- monkeypatch and dynamic-import strings;
- cache invalidation;
- accidental report/database/strategy-ID renames.

- [ ] **Step 9: Commit verification fixes**

If review or verification required changes:

```bash
git add <only-the-reviewed-files>
git commit -m "fix: complete quant namespace migration"
```

If no changes are required, do not create an empty commit.

## Task 12: Observe Compatibility Before Removing the Legacy CLI

**Files:**
- Read during observation: `logs/scheduler/*.log`
- Read during observation: operator automation definitions outside Git, if available
- Modify after observation: `pyproject.toml`
- Modify after observation: `uv.lock`
- Modify after observation: `phase0/`
- Modify after observation: `tests/test_quant_namespace_migration.py`
- Modify after observation: `docs/QUANT_CLI_USER_GUIDE.md`
- Modify after observation: `docs/architecture/PHASE0_TO_QUANT_COMPATIBILITY.md`

This task is a separate cleanup release. Do not perform it in the initial namespace-switch release.

- [ ] **Step 1: Start the observation window after deployment**

Minimum observation requirement:

- 30 natural days after the quant migration is deployed;
- at least 10 completed A-share trading days;
- at least one successful run of every enabled scheduled task;
- no scheduler or operator automation invoking `phase0.cli` except deliberate compatibility tests.
- no running or retriable persisted shard depends on an unhandled legacy CLI command.

- [ ] **Step 2: Audit local and remote automation**

Search project-owned definitions:

```bash
rg -n "phase0\.cli|stok-phase0" scripts config.yaml README.md docs pyproject.toml
```

Inspect installed cron/system scheduler definitions using the environment-appropriate read-only command. Record every external caller and migrate it to `./runit` or `quant.cli` before removal.

- [ ] **Step 3: Review logs for compatibility warnings**

```bash
rg -n "DEPRECATION: 'python -m phase0\.cli'" logs
```

Expected removal gate: no non-test invocation during the final 10 A-share trading days.

- [ ] **Step 4: Audit persisted scheduler commands before removal**

Run read-only queries against the configured maintenance database:

```bash
sqlite3 data/maintenance/orchestrator.sqlite \
  "SELECT shard_id, run_id, task_name, status, command_json FROM maintenance_shards WHERE status IN ('running','pending','failed') AND command_json LIKE '%phase0.cli%';"
sqlite3 data/maintenance/orchestrator.sqlite \
  "SELECT task_name, command_json FROM maintenance_registry WHERE enabled = 1 AND command_json LIKE '%phase0.cli%';"
```

Expected: no enabled registry row uses `phase0.cli`; legacy shard rows are
either terminal or have already demonstrated successful execution-boundary
normalization. Preserve query output in the deployment audit, not in Git.

- [ ] **Step 5: Remove the legacy console script**

Delete this entry from `pyproject.toml`:

```toml
stok-phase0 = "phase0.cli:main"
```

Keep:

```toml
stok-quant = "quant.cli:main"
```

- [ ] **Step 6: Remove the compatibility package**

Delete only:

```text
phase0/__init__.py
phase0/__main__.py
phase0/cli.py
```

Then remove the empty `phase0/` directory. This task must not delete persisted `phase0_*` artifacts.

- [ ] **Step 7: Update the migration contract test**

Replace the legacy-forwarder assertion with:

```python
def test_legacy_phase0_cli_has_been_removed() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("phase0.cli")
```

Remove the temporary console alias assertion.

- [ ] **Step 8: Regenerate and verify packaging**

```bash
uv lock
uv sync
./.venv/bin/python -m pytest tests/test_quant_namespace_migration.py -q
./.venv/bin/python -m pytest -q
./.venv/bin/stok-quant --help
```

Expected: tests pass and only the canonical console script is installed.

- [ ] **Step 9: Commit compatibility removal**

```bash
git add pyproject.toml uv.lock phase0 tests docs
git commit -m "refactor: remove deprecated phase0 CLI compatibility"
```

## Task 13: Merge and Post-Merge Verification

**Files:**
- No new source files expected
- Read: Git status, scheduler state, and current documentation

- [ ] **Step 1: Use the finishing-development-branch workflow**

Invoke `superpowers:finishing-a-development-branch`. Review the branch against the latest `main`; do not merge over unrelated dirty main-worktree changes.

- [ ] **Step 2: Verify the exact merge result in a clean checkout**

```bash
git status --short --branch
./.venv/bin/python -m pytest -q
./runit maintain tick --config config.yaml --dry-run --as-of "2026-08-12 08:00"
```

Expected: clean checkout, tests match the reviewed branch, and scheduler evaluation works through `quant.cli`.

- [ ] **Step 3: Run one supervised real scheduler cycle**

At an approved maintenance time, allow the existing cron wrapper to run normally. Verify:

- `scripts/run_project_scheduler.sh` starts through `quant.cli`;
- maintenance state is updated;
- scheduled child commands use `quant.cli`;
- no enabled task fails because of import paths or package-data lookup;
- no local SQLite, report, or ledger path changed unexpectedly.

- [ ] **Step 4: Record the deployment boundary**

Update `docs/architecture/PHASE0_TO_QUANT_COMPATIBILITY.md` with the deployed commit hash and compatibility-window start date. Do not claim the legacy CLI is removable until Task 12 gates are satisfied.

## Acceptance Criteria

The initial migration release is complete only when all of the following hold:

- `quant` is the only canonical application package;
- all repository-owned domain imports use `quant.*`;
- `./runit`, scheduler wrappers, built-in scheduled commands, and active docs use `quant.cli`;
- `config.yaml` uses `quant:`;
- a legacy `phase0:` config is accepted only through one tested selector and emits a warning;
- simultaneous `quant:` and `phase0:` config roots fail clearly;
- `python -m phase0.cli` is only a thin, visibly deprecated forwarding entry point;
- importing `phase0.walk_forward` or other legacy domain modules is not supported;
- both legacy-first and canonical-first fresh-process tests produce one canonical strategy registry, the same strategy-ID set, and `quant.strategies.*` class identities;
- package templates and static assets continue to resolve from `quant/reporting/`;
- a clean wheel installed outside the repository exposes both temporary CLI scripts and contains all required reporting package data;
- the complete test suite has no migration-caused failures;
- scheduler dry-run and one supervised real scheduler cycle succeed;
- persisted legacy scheduler commands remain unchanged as audit records but resume through a logged, tested `quant.cli` effective command;
- historical reports, SQLite schemas, ledger paths, strategy IDs, and local runtime assets remain intact;
- runtime caches use a new namespace version and old caches are ignored rather than deleted;
- the compatibility-removal date is governed by Task 12, not by convenience.

## Rollback Strategy

If the initial migration fails before merge:

- keep the migration isolated in its worktree;
- fix or abandon the branch without changing the main checkout;
- do not copy generated runtime assets back to main.

If it fails after merge but before the compatibility window ends:

- revert the migration commits as a group using non-destructive `git revert`;
- restore scheduler commands to `phase0.cli` through the revert;
- retain existing databases, reports, ledgers, and caches because the migration does not rewrite them;
- do not use `git reset --hard` on a user worktree.

If only an external automation still calls the old name:

- keep the compatibility shim in place;
- update that automation to `./runit` or `quant.cli`;
- extend the observation window rather than reintroducing a second domain package namespace.

## Estimated Effort and Priority

Recommended priority: medium. The rename improves semantics and future maintainability, but it does not add trading or data capability. Execute it during a feature freeze, preferably before adding many more top-level modules such as China option analytics.

Estimated engineering effort:

- inventory and contract tests: 0.5 day;
- package/import/config migration: 1.5–2.5 days;
- scheduler, scripts, tests, and active docs: 1–2 days;
- full verification and review: 0.5–1 day;
- compatibility observation: 30 natural days, mostly operational waiting;
- legacy CLI cleanup after the gate: 0.5 day.

Critical risks are operational entry points, duplicate module identity, config ambiguity, monkeypatch/dynamic-import strings, package-data lookup, and accidental persisted-artifact renames—not the directory move itself.
