# Daily Brief Content Model Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the useful P0 Daily Brief content contract from `codex/daily-brief-content-model` into current `main` without overwriting newer documentation or the user's uncommitted work.

**Architecture:** Add a reporting-only dataclass contract that is independent of business databases and renderers. Keep account-return semantics explicit, reject incomplete confirmed snapshots, preserve conservative missing-bill behavior, and expose the model through `phase0.reporting`. Reconcile planning documents manually against current `main` instead of merging the stale branch wholesale.

**Tech Stack:** Python 3.12+, dataclasses, pytest, Git worktrees.

---

### Task 1: Import the P0 contract and original regression tests

**Files:**
- Create: `phase0/reporting/daily_brief.py`
- Modify: `phase0/reporting/__init__.py`
- Create: `tests/test_daily_brief_content_model.py`

- [ ] **Step 1: Restore the branch-owned files without merging its stale documentation**

Run:

```bash
git restore --source=codex/daily-brief-content-model -- phase0/reporting/daily_brief.py tests/test_daily_brief_content_model.py
```

Apply only the Daily Brief imports and `__all__` entries from the source branch to `phase0/reporting/__init__.py`.

- [ ] **Step 2: Run the imported tests**

Run:

```bash
/Users/aj/workspace/stok-mapping/.venv/bin/python -m pytest -q tests/test_daily_brief_content_model.py
```

Expected: `4 passed`.

### Task 2: Correct account return semantics with TDD

**Files:**
- Modify: `tests/test_daily_brief_content_model.py`
- Modify: `phase0/reporting/daily_brief.py`

- [ ] **Step 1: Write a failing cumulative-return test**

Add a confirmed snapshot with `total_asset=1_050_000`, `initial_cash=1_000_000`, and `daily_return=0.0123`. Assert `current_return == 0.05`; this proves the Daily Brief label means account return since initial capital rather than one-day return.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
/Users/aj/workspace/stok-mapping/.venv/bin/python -m pytest -q tests/test_daily_brief_content_model.py::test_account_summary_uses_confirmed_bill_snapshot
```

Expected: FAIL because the imported implementation returns `0.0123`.

- [ ] **Step 3: Implement cumulative return**

Compute confirmed `current_return` as `effective_total / initial_cash - 1.0` when `initial_cash` is non-zero. Keep it `None` for unconfirmed or missing bills.

- [ ] **Step 4: Run the focused test and verify GREEN**

Expected: PASS.

### Task 3: Reject inconsistent confirmed snapshots with TDD

**Files:**
- Modify: `tests/test_daily_brief_content_model.py`
- Modify: `phase0/reporting/daily_brief.py`

- [ ] **Step 1: Write failing validation tests**

Add tests asserting that a confirmed snapshot raises `ValueError` when any of `total_asset`, `cash_asset`, or `stock_asset` is missing or non-numeric, and when `cash_asset + stock_asset` does not match `total_asset` within one cent.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
/Users/aj/workspace/stok-mapping/.venv/bin/python -m pytest -q tests/test_daily_brief_content_model.py -k "incomplete or inconsistent"
```

Expected: FAIL because the imported implementation silently falls back field by field.

- [ ] **Step 3: Implement validation**

For confirmed bills, require all three asset fields to be numeric and finite, require non-negative assets, and require `abs(total_asset - cash_asset - stock_asset) <= 0.01`. Raise a diagnostic `ValueError` otherwise.

- [ ] **Step 4: Run the Daily Brief tests**

Expected: all Daily Brief tests pass.

### Task 4: Reconcile T6.6 documentation

**Files:**
- Modify: `docs/DEVELOPMENT_PLAN.md`
- Modify: `docs/tasks/WEEKLY_EXECUTION_CHECKLIST.md`
- Create: `docs/tasks/ops/DAILY_BRIEF_CONTENT_MODEL_TASKS.md`
- Modify: `docs/tasks/README.md`

- [ ] **Step 1: Preserve the richer T6.6 task definition**

Use the user's current T6.6 task document as the base because it contains the expanded content model and acceptance criteria. Mark the dataclass contract, section structure, missing-data rules, five account spans, and account-summary tests complete. Leave renderer, manifest, HTML snapshots, and route migration incomplete.

- [ ] **Step 2: Update current-plan status without dropping newer tasks**

Update only the T6.6 rows and checklist items. Preserve T6.7 and every later `main` planning change.

### Task 5: Verify and integrate

**Files:**
- Review all changed files.

- [ ] **Step 1: Run focused verification**

```bash
/Users/aj/workspace/stok-mapping/.venv/bin/python -m pytest -q tests/test_daily_brief_content_model.py
git diff --check
```

Expected: Daily Brief tests pass; no unintended whitespace errors.

- [ ] **Step 2: Run the full suite**

```bash
/Users/aj/workspace/stok-mapping/.venv/bin/python -m pytest -q
```

Expected integration gate: no failures beyond the seven documented `main` baseline failures. A clean merge into `main` requires resolving or explicitly accepting the baseline failures according to project policy.

- [ ] **Step 3: Review scope and commit**

Confirm that the diff contains only the content model, tests, T6.6 documentation, and this plan. Commit on `codex/integrate-daily-brief-content-model`.

- [ ] **Step 4: Merge only when the gate is met**

Merge into `main` only from a clean main worktree. Do not overwrite or stash the user's current uncommitted work. If the main worktree remains dirty, preserve the integration branch and report the exact blocker instead of forcing the merge.
