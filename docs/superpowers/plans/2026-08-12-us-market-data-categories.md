# US Market Data Categories Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the 21-symbol US market history maintainable as named data categories with per-symbol audit, OHLC quality protection, common-session reads, and research-only premarket context without changing semiconductor timing trades.

**Architecture:** Extend the existing `MarketHistorySettings` with configuration-derived instrument metadata while preserving the legacy `symbols` form. Keep `us_daily_bars` as the sole daily-bar store, add a per-symbol audit table linked to the existing run audit, and isolate read-only common-session logic in `us_market_features`. The strategy consumes the core SOX/VIX reader only; non-core groups render as explicitly non-trading research context.

**Tech Stack:** Python 3, pandas, SQLite, PyYAML, pytest, existing static HTML renderer.

## Completion record — 2026-08-12

- Implemented the five task areas on `codex/us-market-data-categories`.
- Focused regression verification: `48 passed` across external-market history, common-session reader, semiconductor timing strategy, static-site rendering, and data-update CLI tests.
- The production US history database was checked in read-only mode using the final 21-symbol category configuration. No database, report, or log artifact is part of this change.
- The existing strategy still uses only the `core_signal` group (`^SOX`, `^VIX`). All added groups are research context only and are explicitly labelled as non-trading inputs.

---

### Task 1: Add category configuration and migration-safe audit tables

**Files:**
- Modify: `config.yaml:184-196`
- Modify: `phase0/data_governance/external_market_history.py`
- Test: `tests/test_external_market_history.py`

- [ ] **Step 1: Write failing configuration tests**

```python
def test_settings_flattens_configured_instrument_groups(tmp_path: Path) -> None:
    settings = external_market_history._build_settings(
        {"instrument_groups": {"core": {"symbols": ["^SOX", "^VIX"]}, "rates": {"symbols": ["^TNX", "^SOX"]}}},
        root=tmp_path,
        defaults=_settings(tmp_path / "data/us.sqlite"),
        default_symbols=[],
    )
    assert settings.symbols == ["^SOX", "^VIX", "^TNX"]
    assert settings.symbol_groups["core"].critical is False
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_external_market_history.py -q`

Expected: fail because `MarketHistorySettings` has no `symbol_groups` metadata.

- [ ] **Step 3: Implement the minimal configuration model**

```python
@dataclass(frozen=True)
class MarketInstrumentGroup:
    name: str
    symbols: tuple[str, ...]
    purpose: str = ""
    required_for: tuple[str, ...] = ()
    critical: bool = False
    asset_types: dict[str, str] = field(default_factory=dict)
```

Parse `instrument_groups`, reject non-mapping groups, empty names, non-string symbols, and one symbol assigned incompatible asset types. Flatten groups in config order with first-seen deduplication. If absent, preserve old `symbols` behavior.

- [ ] **Step 4: Add SQLite metadata and per-symbol audit schema**

Add `us_market_instruments` and `us_data_source_symbol_runs` using `CREATE TABLE IF NOT EXISTS`. The latter records the parent run id, group name, symbol, asset type, request window, rows fetched/inserted/updated, latest date, status, and message.

- [ ] **Step 5: Run focused tests**

Run: `./.venv/bin/python -m pytest tests/test_external_market_history.py -q`

Expected: PASS.

### Task 2: Enforce OHLC quality and per-symbol update results

**Files:**
- Modify: `phase0/data_governance/external_market_history.py`
- Test: `tests/test_external_market_history.py`

- [ ] **Step 1: Write failing update tests**

```python
def test_invalid_ohlc_does_not_replace_existing_valid_bar_and_is_audited(...):
    ...
    assert db_close == 10.0
    assert audit_status == "invalid_data"

def test_symbol_fetch_failure_is_recorded_with_group(...):
    ...
    assert rows == [("core_signal", "^VIX", "failed")]
```

- [ ] **Step 2: Run focused tests and verify failures**

Run: `./.venv/bin/python -m pytest tests/test_external_market_history.py -q`

Expected: failures because no symbol audit or OHLC gate exists.

- [ ] **Step 3: Implement validation and audit writes**

Validate normalized bars before upsert: required OHLC numeric and positive, and `low <= open/close <= high`. Treat zero volume as valid. Record `updated`, `empty`, `failed`, or `invalid_data` for every configured symbol. A critical-group failure must make the aggregate run non-OK; noncritical failure remains explicit in warnings and audit records.

- [ ] **Step 4: Run focused tests**

Run: `./.venv/bin/python -m pytest tests/test_external_market_history.py -q`

Expected: PASS.

### Task 3: Add common completed-session research reader and preserve the core signal

**Files:**
- Create: `phase0/data_governance/us_market_features.py`
- Modify: `phase0/strategies/cross_market_semiconductor_timing.py:231-270`
- Test: `tests/test_us_market_features.py`
- Test: `tests/test_cross_market_semiconductor_timing.py`

- [ ] **Step 1: Write failing common-session tests**

```python
def test_snapshot_uses_latest_common_completed_session(tmp_path: Path):
    snapshot = load_completed_market_snapshot(..., symbols=["^SOX", "^VIX"])
    assert snapshot.as_of_date == "2026-08-11"
    assert set(snapshot.bars["symbol"]) == {"^SOX", "^VIX"}

def test_snapshot_never_mixes_a_newer_vix_with_prior_sox(tmp_path: Path):
    ...
    assert snapshot.as_of_date == "2026-08-11"
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `./.venv/bin/python -m pytest tests/test_us_market_features.py -q`

Expected: fail because the module does not exist.

- [ ] **Step 3: Implement the reader**

Expose `load_completed_market_snapshot` and `load_group_daily_features`. Both accept an explicit database path, table name, requested symbols, and optional as-of date; both inner-join symbols on the same date and return structured availability metadata rather than forward filling. The panel calculates close-to-close return and rolling volatility only after common-session alignment.

- [ ] **Step 4: Migrate SOX/VIX loader without behavior change**

Use the reader for the strategy's core group, calculate SOX returns after common-session alignment, and retain the existing next-China-trading-day mapping. Add a regression assertion that the migrated loader produces the same SOX return/VIX dates for a fixed fixture.

- [ ] **Step 5: Run reader and strategy tests**

Run: `./.venv/bin/python -m pytest tests/test_us_market_features.py tests/test_cross_market_semiconductor_timing.py -q`

Expected: PASS.

### Task 4: Expose research context in the premarket page and command output

**Files:**
- Modify: `phase0/reporting/semiconductor_timing_watchlist.py`
- Modify: `phase0/cli_commands/data_update.py:642-656`
- Test: `tests/test_quant_static_site.py`
- Test: `tests/test_external_market_history.py`

- [ ] **Step 1: Write failing rendering and CLI-summary tests**

```python
assert "研究市场背景（不参与自动交易信号）" in watchlist_html
assert "半导体产业链共振" in watchlist_html
assert "AMD" in watchlist_html
```

- [ ] **Step 2: Run focused tests and verify failures**

Run: `./.venv/bin/python -m pytest tests/test_quant_static_site.py tests/test_external_market_history.py -q`

Expected: failure because the context section and category summary do not exist.

- [ ] **Step 3: Implement read-only reporting**

Add a context table per non-core configured group showing the latest common date, close, one-day return, source, and unavailable reason. Render it after the core signal section with a permanent non-trading disclaimer. Extend `update-us-market-history` output with group-level coverage/common date and failed-symbol summaries.

- [ ] **Step 4: Run focused tests**

Run: `./.venv/bin/python -m pytest tests/test_quant_static_site.py tests/test_external_market_history.py -q`

Expected: PASS.

### Task 5: Document, verify, commit, and reconcile completed development-plan goals

**Files:**
- Modify: `docs/PHASE0_CLI_USER_GUIDE.md`
- Modify: `docs/DEVELOPMENT_PLAN.md`
- Test: `tests/test_external_market_history.py`
- Test: `tests/test_us_market_features.py`
- Test: `tests/test_cross_market_semiconductor_timing.py`
- Test: `tests/test_quant_static_site.py`

- [ ] **Step 1: Document category configuration and operational semantics**

Document the category configuration, per-symbol audit tables, `--check-only` behavior, common completed-session rule, and that research context/news does not alter orders.

- [ ] **Step 2: Run the focused regression suite**

Run: `./.venv/bin/python -m pytest tests/test_external_market_history.py tests/test_us_market_features.py tests/test_cross_market_semiconductor_timing.py tests/test_quant_static_site.py -q`

Expected: PASS.

- [ ] **Step 3: Run a local SQLite smoke audit without modifying production data**

Run: `./.venv/bin/python -m phase0.cli update-us-market-history --config config.yaml --check-only`

Expected: summary includes configured categories and their common completed-session dates. If external configuration/database is unavailable in the worktree, record the limitation and use the test fixture audit as the verification boundary.

- [ ] **Step 4: Update Development Plan only for evidenced completion**

Use this session's verified implementation history for previously completed work. Mark only goals supported by current evidence or direct session history; preserve incomplete or merely planned items.

- [ ] **Step 5: Commit the completed change**

```bash
git add config.yaml phase0/data_governance/external_market_history.py \
  phase0/data_governance/us_market_features.py \
  phase0/strategies/cross_market_semiconductor_timing.py \
  phase0/reporting/semiconductor_timing_watchlist.py \
  phase0/cli_commands/data_update.py tests/test_external_market_history.py \
  tests/test_us_market_features.py tests/test_cross_market_semiconductor_timing.py \
  tests/test_quant_static_site.py docs/PHASE0_CLI_USER_GUIDE.md \
  docs/DEVELOPMENT_PLAN.md docs/superpowers/plans/2026-08-12-us-market-data-categories.md
git commit -m "feat: govern US market data categories"
```
