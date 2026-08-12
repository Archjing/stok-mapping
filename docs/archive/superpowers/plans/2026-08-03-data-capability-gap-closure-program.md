# Data Capability Gap Closure Program Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an auditable, point-in-time-safe data and feature foundation that closes the project’s highest-value A-share data gaps without making large historical downloads or unlicensed data sources a default dependency.

**Architecture:** Deliver the program as a shared Gate 0 followed by independently shippable phases. Build a metadata-only registry and lazily calculated local technical features in parallel with the corporate-action audit, but do not allow newly added price features into strategy experiments until the price-governance gate passes. Then build controlled broad-index/breadth assets, add historical industry classifications only from a time-versioned source, standardize fundamentals, and only after those gates assess opt-in macro and text/event sources. Source data stays in local SQLite and ignored caches, while code, configuration, tests, and global documentation are integrated through `main`.

**Tech Stack:** Python 3.14, pandas, NumPy, SQLite, PyYAML, pytest, existing `phase0` local-history/governance framework, Tushare connector, optional FRED connector, Git worktrees.

---

## 1. Decision, Scope, and Non-Goals

This is a **program-level sequencing plan**, not permission to begin all data downloads. Each phase has a hard gate. Do not start a later phase merely because its code can be written: start it only after the preceding phase has a passing coverage/audit report and an approved source policy.

The current local A-share asset is the primary input:

- `/Users/aj/workspace/stok-mapping/data/manual_history/a_share_history.sqlite`
- As checked on `2026-08-03`, daily bars cover `2016-05-03` through `2026-08-03`; daily-bar coverage for the target trading day is `0.9826`. The database contains QFQ and BFQ bars, daily basics, adjustment factors, financial factors, indexes, and PIT index membership/weights. Daily-basic coverage is market cap `1.0000`, PE `0.9972`, PB `0.9996`, and turnover `1.0000` on that target date.
- Critical known gaps are incomplete dividend events, index bars ending earlier than stock daily bars, no standardized feature registry, no canonical market-breadth/industry feature asset, no analyst-estimate-revision source, no local macro cache, and no production-grade news/sentiment or order-book data.

The external-market baseline is deliberately separated from the A-share foundation. At this plan's start, the local US and HK daily databases are stale at `2026-06-24`: Yahoo Finance is rate-limited for the configured US/HK refreshes, and the available Tushare `hk_daily` entitlement is limited to one request per hour. No strategy feature may treat either database as current until an independently auditable refresh succeeds. This is an operational source-availability issue, not a reason to silently change price-provider semantics.

The program covers the user’s requested capability list as follows:

| Capability group | Delivery phase | Required result before it can feed a strategy |
| --- | --- | --- |
| OHLCV, return/range/gap/volume change, volatility/extrema/drawdown | 1 | Registry entry, deterministic calculation, no future rows, test coverage |
| QFQ/BFQ and dividends/splits/rights | 2 | Action-event coverage audit and QFQ-as-of reconciliation pass |
| Broad market/style and breadth | 3 | Index freshness parity, PIT source date, coverage report |
| Historical industry classification / industry relative strength | 3B, separate source decision | Classification effective and as-of dates, coverage report; never backfill from current industry label |
| MA/EMA/MACD/RSI/Bollinger, momentum/reversal/volume shock | 1 | Registry entry and causal rolling-window tests |
| Turnover, northbound proxy, order-book/depth | 1 for turnover; 3 for northbound; separate feasibility for depth | Explicit source and timing contract; no proxy may be labeled order-book data |
| Financials and valuation | 4 | Announcement-date/PIT audit, daily as-of join tests, availability metrics |
| Analyst estimate revisions | 4B, separate source decision | Licensed/reliable source, revision timestamp, no backfilled “current consensus” |
| Macro, rates, FX, commodities | 5 | Per-series source contract, incremental cache, release-time/as-of rule |
| News, announcements, social sentiment | 6 | Entity link, publication/as-of time, coverage and leakage validation; explanation-only until promoted |

### Non-goals

- Do not materialize every feature for every symbol/date during Phase 1.
- Do not replace `qfq_asof` with `qfq_current`, and do not infer historical action information from today’s adjusted price alone.
- Do not add intraday, bid/ask, tick, order-book, social-media, or analyst-consensus data without a separate license, cost, retention, and point-in-time review.
- Do not route text or macro data directly into ranking/trading signals during this program’s early phases.
- Do not commit `reports/`, `logs/`, SQLite databases, or bulk downloaded files to Git.
- Do not modify source code from a research-only worktree. Data repair and source-code integration are separate responsibilities.

## 2. Data Download and Storage Policy

Phase 1 is intentionally **zero-download**: registry metadata and features derived from the local daily-bar table run locally and calculate only the dates/symbols requested by a caller.

The download policy for all later phases is:

| Class | Default | Allowed fetch scope | Storage | Approval/gate |
| --- | --- | --- | --- | --- |
| Registry metadata and derived local features | No network | None | In-memory result; optional ignored local cache | Automated tests pass |
| Corporate actions / index refresh | Disabled until audit | Missing symbols and dates only; chunked by exchange/calendar period | Existing local A-share SQLite plus ignored audit report | Pre/post coverage comparison and source quota confirmation |
| Financial-history repair | Disabled until PIT audit identifies gaps | Missing report/announcement ranges only | Existing local A-share SQLite plus ignored audit report | PIT audit pass for sampled symbols/dates |
| FRED macro | Disabled by default | One configured series, newest missing observations first; historical backfill only after a recorded need | `data/cache/fred/`, ignored except `.gitkeep` | Per-series contract and release-time test |
| FX / commodities / estimates / text / social / depth | No fetch | None before a source decision | Ignored local cache/database | License, cost, retention, as-of, coverage and leakage review |

Set a conservative operational budget before each acquisition run: record request parameters, source, start/end date, symbols/series count, row count before/after, database byte delta, and failed symbols. A job that expands beyond its approved symbol/date set, exceeds the configured byte budget, or cannot prove the source timestamp must stop without promoting its result.

## 3. Target Data Contracts

### 3.1 Shared feature-registry contract

Create a registry that is metadata only. It does not download data and it does not precompute a full feature lake. A consumer asks for named features for a bounded `symbol × date` panel; the registry resolves dependencies and computes them from already local fields.

Each feature definition must record:

| Field | Rule |
| --- | --- |
| `name` | Stable output name, e.g. `ema_20`, `rsi_14`, `drawdown_60` |
| `version` | Semantic formula version; formula changes require a new version or explicit migration |
| `frequency` | Initially `daily` only |
| `inputs` | Canonical source columns/tables, such as `close`, `volume`, `amount`, `turnover_rate` |
| `lookback_sessions` | Largest required historical window, including warm-up |
| `availability_lag_sessions` | `0` only if the feature uses the same day’s close after the market close; ranking for next-session execution must apply the project’s existing execution delay |
| `point_in_time_rule` | Must state which data timestamp is permitted; financial/index features require source publication/as-of fields |
| `missing_data_policy` | `preserve_nan`, `drop_until_warm`, or a documented causal fill; no backward fill |
| `source_freshness_rule` | Required source end date / tolerance for any persisted feature asset |
| `builder` | Pure callable that receives a sorted panel and returns Series/DataFrame with the original index |

The base formula convention is daily close-based research features on the chosen input price series. Existing `qfq_asof` selection remains the responsibility of the local-history/walk-forward layer; registry builders must never silently exchange it for `qfq_current`.

### 3.2 Feature tiers

- **Tier A — local price/volume:** daily bars and daily basic only. Examples: return, range, gap, MA/EMA/MACD/RSI/Bollinger, momentum/reversal, volume change/shock, rolling high/low, drawdown, turnover.
- **Tier B — governed local joins:** adjustment, financial PIT, index and industry features. Requires as-of audit fields and coverage metrics.
- **Tier C — external opt-in:** macro, FX, commodities, estimates and text. Requires a source-specific contract and cannot be enabled by a registry import.

## 4. Repository File Map

The paths below are the intended integration surface. Confirm exact existing function boundaries during each phase; do not combine a bulk historical data refresh with a code change in one commit.

| File | Responsibility |
| --- | --- |
| `phase0/research/features/__init__.py` | Export registry types and public feature-resolution API. |
| `phase0/research/features/registry.py` | Immutable feature specification, dependency resolution, request validation, and metadata manifest. |
| `phase0/research/features/technical.py` | Pure daily technical-feature builders. No I/O and no strategy-specific ranking. |
| `phase0/research/features/market_context.py` | Future Phase 3 PIT market breadth, index/industry return, and industry-strength builders. |
| `phase0/data_governance/feature_audit.py` | Coverage/freshness/as-of audit helpers and machine-readable audit result. |
| `phase0/data_governance/backfills/adjustment.py` | Existing dividend/action table creation and upsert boundary; extend only after audit tests exist. |
| `phase0/data_governance/backfills/tushare_history_audit_queries.py` | Bounded action/index/financial coverage queries and pre/post snapshots. |
| `phase0/data_governance/index_asof_backfill.py` | Existing PIT index-member/weight persistence; retain its table contract. |
| `phase0/data_access/connectivity.py` | Existing optional FRED/Tiingo connectors; do not enable a source globally without its Phase 5/6 gate. |
| `phase0/data_access/local_history.py` | Local source selection and adjusted-price mode; registry callers must use this boundary. |
| `phase0/walk_forward.py` | Existing strategy-panel assembly; migrate only selected shared features after equivalence tests. |
| `config.yaml` | Registry defaults, source disablement, bounded refresh budgets, feature freshness tolerances. |
| `tests/test_feature_registry.py` | Registry dependency, version, missing-data, and no-I/O behavior. |
| `tests/test_technical_features.py` | Numerical and causal rolling-window tests. |
| `tests/test_adjustment_coverage_audit.py` | Corporate-action completeness/reconciliation tests. |
| `tests/test_market_context_features.py` | PIT index/breadth/industry-strength tests. |
| `tests/test_financial_feature_asof.py` | Financial announcement-date/as-of join tests. |
| `tests/test_external_series_contract.py` | Macro release/as-of/cache-boundary tests. |
| `docs/data_governance/FEATURE_REGISTRY.md` | Registry contract, tiering, formulas, availability semantics, and consumer examples. |
| `docs/data_governance/SOURCE_CONTRACTS.md` | Per-source license, fields, timestamps, freshness, retention, and permitted usage. |
| `docs/data_governance/DATA_REFRESH_RUNBOOK.md` | Bounded backfill/refresh commands, stop conditions, verification, and rollback. |

## 5. Gate 0 — Establish a Reproducible Baseline and Data Contract

**Purpose:** Preserve the current evidence and establish the replay boundary before changing calculations or local data. This is a code-integration task on `main` (or a short-lived `codex/data-governance-foundation` worktree); it does not download data.

**Entrance criteria:** Current working tree is reviewed; the local A-share database is available but remains untracked.

### Task 0.1: Capture schema, freshness, and coverage baselines

**Files:**

- Create: `phase0/data_governance/feature_audit.py`
- Create: `tests/test_feature_audit.py`
- Create: `docs/data_governance/DATA_REFRESH_RUNBOOK.md`

- [ ] **Step 1: Write a failing audit-result schema test**

```python
from phase0.data_governance.feature_audit import audit_table_coverage

def test_audit_table_coverage_reports_rows_dates_and_group_counts(tmp_path):
    result = audit_table_coverage(
        database_path=tmp_path / "history.sqlite",
        table_name="market_daily_bars",
        date_column="date",
        group_columns=("adjust_type",),
    )
    assert set(result) == {"table", "row_count", "min_date", "max_date", "group_counts"}
```

- [ ] **Step 2: Run the new test and confirm the import fails**

Run: `./.venv/bin/python -m pytest -q tests/test_feature_audit.py::test_audit_table_coverage_reports_rows_dates_and_group_counts`

Expected: FAIL because `phase0.data_governance.feature_audit` does not yet exist.

- [ ] **Step 3: Implement a read-only audit helper**

```python
def audit_table_coverage(
    *,
    database_path: Path,
    table_name: str,
    date_column: str,
    group_columns: tuple[str, ...] = (),
) -> dict[str, object]:
    """Return deterministic local coverage metadata without changing the database."""
    table = safe_identifier(table_name)
    date_name = safe_identifier(date_column)
    groups = tuple(safe_identifier(column) for column in group_columns)
    with sqlite3.connect(f"file:{quote(str(database_path))}?mode=ro", uri=True) as conn:
        count, min_date, max_date = conn.execute(
            f"SELECT COUNT(*), MIN({date_name}), MAX({date_name}) FROM {table}"
        ).fetchone()
        group_counts = []
        if groups:
            group_sql = ", ".join(groups)
            rows = conn.execute(
                f"SELECT {group_sql}, COUNT(*) FROM {table} "
                f"GROUP BY {group_sql} ORDER BY {group_sql}"
            ).fetchall()
            group_counts = [dict(zip((*groups, "row_count"), (*row[:-1], int(row[-1])))) for row in rows]
    return {
        "table": table,
        "row_count": int(count),
        "min_date": min_date,
        "max_date": max_date,
        "group_counts": group_counts,
    }
```

Implementation requirements: validate all SQL identifiers with the project’s existing safe-identifier helper; use a read-only SQLite connection; return `None` dates and empty groups for an empty table; never create tables or indexes.

- [ ] **Step 4: Add bounded refresh runbook commands**

Document these required records for every later refresh: source/config revision, database path, approved symbols/series/date range, before/after audit JSON, row delta, byte delta, failed requests, and rollback snapshot location. State that database/report/log outputs are local-only.

- [ ] **Step 5: Run baseline validation**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_feature_audit.py tests/test_daily_basic_history.py tests/test_index_asof_audit.py tests/test_index_asof_backfill.py
```

Expected: PASS. Produce one ignored local coverage JSON per source table; do not add it to Git.

- [ ] **Step 6: Commit only code/tests/docs**

```bash
git add phase0/data_governance/feature_audit.py tests/test_feature_audit.py docs/data_governance/DATA_REFRESH_RUNBOOK.md
git commit -m "feat: add read-only data coverage audit"
```

**Exit gate:** A read-only audit can report row count, min/max dates, and required grouping counts for every Phase 1–4 source table. Every proposed source documents four distinct times where applicable: event/effective time, source publication time, first local visibility time, and ingestion time. If it cannot safely inspect the database schema or distinguish those times, stop and repair the audit/helper contract before any refresh.

## 6. Phase 1 — Metadata-Only Registry and Local Technical Features (No Download)

**Purpose:** Close the highest-value technical gaps using existing local OHLCV/daily-basic data. This phase should be the first implementation phase because it has the highest research ROI and does not require network, license, or bulk storage. Its code can proceed in parallel with Phase 2, but its newly added price features remain registry/diagnostic-only until Phase 2 passes its price-governance gate.

**Entrance criteria:** Phase 0 exit gate passes; current `qfq_asof` source-selection tests pass.

### Task 1.1: Define feature specifications and registry resolution

**Files:**

- Create: `phase0/research/features/__init__.py`
- Create: `phase0/research/features/registry.py`
- Create: `tests/test_feature_registry.py`
- Create: `docs/data_governance/FEATURE_REGISTRY.md`
- Modify: `config.yaml`

- [ ] **Step 1: Write registry validation tests**

```python
import pandas as pd
import pytest

from phase0.research.features.registry import FeatureSpec, FeatureRegistry

def test_registry_rejects_unknown_dependency_and_duplicate_name():
    registry = FeatureRegistry()
    with pytest.raises(ValueError, match="unknown dependency"):
        registry.register(FeatureSpec(name="bad", version="1", inputs=("missing",), lookback_sessions=1, availability_lag_sessions=0, missing_data_policy="preserve_nan", builder=lambda frame: frame["close"]))

def test_registry_resolves_dependency_before_requested_feature():
    registry = FeatureRegistry.with_base_fields({"close"})
    registry.register(FeatureSpec(name="ret_1", version="1", inputs=("close",), lookback_sessions=1, availability_lag_sessions=0, missing_data_policy="preserve_nan", builder=lambda frame: frame["close"].pct_change()))
    registry.register(FeatureSpec(name="ret_5", version="1", inputs=("ret_1",), lookback_sessions=5, availability_lag_sessions=0, missing_data_policy="preserve_nan", builder=lambda frame: frame["ret_1"].rolling(5).sum()))
    assert registry.resolve(("ret_5",)) == ("ret_1", "ret_5")
```

- [ ] **Step 2: Run tests and confirm the module is absent**

Run: `./.venv/bin/python -m pytest -q tests/test_feature_registry.py`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the metadata-only contract**

```python
@dataclass(frozen=True)
class FeatureSpec:
    name: str
    version: str
    inputs: tuple[str, ...]
    lookback_sessions: int
    availability_lag_sessions: int
    missing_data_policy: Literal["preserve_nan", "drop_until_warm"]
    builder: Callable[[pd.DataFrame], pd.Series | pd.DataFrame]

class FeatureRegistry:
    def register(self, spec: FeatureSpec) -> None:
        if spec.name in self._specs:
            raise ValueError(f"duplicate feature: {spec.name}")
        unknown = set(spec.inputs).difference(self._base_fields, self._specs)
        if unknown:
            raise ValueError(f"unknown dependency: {sorted(unknown)}")
        self._specs[spec.name] = spec

    def resolve(self, requested: tuple[str, ...]) -> tuple[str, ...]:
        resolved: list[str] = []
        visiting: set[str] = set()
        def visit(name: str) -> None:
            if name in self._base_fields or name in resolved:
                return
            if name in visiting or name not in self._specs:
                raise ValueError(f"unknown or cyclic feature: {name}")
            visiting.add(name)
            for dependency in self._specs[name].inputs:
                visit(dependency)
            visiting.remove(name)
            resolved.append(name)
        for name in requested:
            visit(name)
        return tuple(resolved)

    def build(self, panel: pd.DataFrame, requested: tuple[str, ...]) -> pd.DataFrame:
        result = panel.copy(deep=True)
        if not result.index.is_unique:
            raise ValueError("panel index must be unique")
        for name in self.resolve(requested):
            built = self._specs[name].builder(result)
            if isinstance(built, pd.Series):
                built = built.rename(name).to_frame()
            if not built.index.equals(result.index) or built.columns.has_duplicates:
                raise ValueError(f"misaligned builder output: {name}")
            result = result.join(built, how="left")
        return result
```

`build()` must be pure: no connector imports, no SQLite writes, no network calls, and no mutation of the caller’s frame. It must require a monotonically increasing date order within each symbol, preserve the input index, and fail if a builder returns duplicate/misaligned output columns.

- [ ] **Step 4: Add configuration defaults that keep external sources disabled**

Add a `feature_registry` block with `enabled: true`, `materialize_by_default: false`, `allow_network: false`, `frequency: daily`, and explicit freshness tolerances. Do not change the existing `data_sources.fred.enabled: false` setting.

- [ ] **Step 5: Run registry and existing price-governance tests**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_feature_registry.py tests/test_strategy_admission_config.py tests/test_daily_coverage_eligibility.py
```

Expected: PASS.

- [ ] **Step 6: Commit registry foundation**

```bash
git add phase0/research/features/__init__.py phase0/research/features/registry.py tests/test_feature_registry.py docs/data_governance/FEATURE_REGISTRY.md config.yaml
git commit -m "feat: add metadata-only daily feature registry"
```

### Task 1.2: Add causal price/volume technical builders

**Files:**

- Create: `phase0/research/features/technical.py`
- Create: `tests/test_technical_features.py`
- Modify: `phase0/research/features/__init__.py`
- Modify: `docs/data_governance/FEATURE_REGISTRY.md`

- [ ] **Step 1: Write numerical and anti-look-ahead tests**

```python
import numpy as np
import pandas as pd

from phase0.research.features.technical import build_rsi_14, build_rolling_drawdown_60

def test_rsi_uses_only_current_and_prior_closes():
    frame = pd.DataFrame({"symbol": ["A"] * 16, "date": pd.date_range("2024-01-01", periods=16), "close": range(1, 17)})
    baseline = build_rsi_14(frame).iloc[-1]
    changed = frame.copy()
    changed.loc[15, "close"] = 10_000
    assert build_rsi_14(changed).iloc[14] == baseline

def test_drawdown_is_zero_at_new_high_and_negative_after_decline():
    frame = pd.DataFrame({"symbol": ["A"] * 4, "close": [10.0, 12.0, 9.0, 12.0]})
    actual = build_rolling_drawdown_60(frame).to_numpy()
    np.testing.assert_allclose(actual, [0.0, 0.0, -0.25, 0.0])
```

- [ ] **Step 2: Run tests and confirm expected failure**

Run: `./.venv/bin/python -m pytest -q tests/test_technical_features.py`

Expected: FAIL because technical builders do not yet exist.

- [ ] **Step 3: Implement the initial Tier-A feature set**

Register these stable names and formulas: `return_1`, `open_close_return_1`, `gap_return_1`, `range_pct_1`, `volume_change_1`, `amount_change_1`, `volatility_20`, `rolling_high_20`, `rolling_low_20`, `drawdown_60`, `ma_3`, `ma_5`, `ma_10`, `ma_20`, `ma_60`, `ema_12`, `ema_26`, `macd_line_12_26`, `macd_signal_9`, `macd_hist_12_26_9`, `rsi_14`, `bollinger_mid_20`, `bollinger_upper_20_2`, `bollinger_lower_20_2`, `momentum_5`, `momentum_20`, `reversal_5`, `amount_ratio_20`, `volume_shock_z20`, `turnover_rate`.

Use explicit causal primitives, grouped by symbol, with `sort_values(["symbol", "date"], kind="stable")` before each grouped rolling/EMA calculation. `reversal_5` is `-return_5`; `volume_shock_z20` is `(log(volume) - rolling_mean(log(volume), 20)) / rolling_std(log(volume), 20)` and returns `NaN` where the denominator is zero or the window is incomplete. Bollinger standard deviation uses `ddof=0` and must be documented.

- [ ] **Step 4: Add equivalence tests for existing walk-forward columns**

For the existing `ma_20`, `momentum_20`, `vol20`, `amount_ratio20`, `breakout20`, gap and range columns, assert on a deterministic two-symbol fixture that registry results equal the corresponding legacy calculation. Do not migrate `phase0/walk_forward.py` until these equivalence tests pass.

- [ ] **Step 5: Run targeted and regression tests**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_technical_features.py tests/test_slow_multifactor_features.py tests/test_price_volume_low_turnover_strategy.py tests/test_strategy_market_context.py
```

Expected: PASS.

- [ ] **Step 6: Commit technical features**

```bash
git add phase0/research/features/technical.py phase0/research/features/__init__.py tests/test_technical_features.py docs/data_governance/FEATURE_REGISTRY.md
git commit -m "feat: add causal daily technical features"
```

### Task 1.3: Perform a bounded adoption, not a global rewrite

**Files:**

- Modify: `phase0/walk_forward.py:738-750`
- Modify: `tests/test_technical_features.py`

- [ ] **Step 1: Write an output-equivalence test for the walk-forward panel**

Use a two-symbol, forty-session fixture. Assert that every legacy column used by the current strategies has identical values before and after registry integration, including initial `NaN` locations.

- [ ] **Step 2: Replace only duplicated Tier-A calculations with registry calls**

Keep strategy-specific score construction in strategy modules. Make panel assembly request the named Tier-A columns and preserve existing column aliases until all callers migrate.

- [ ] **Step 3: Run full local-feature regression suite**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_technical_features.py tests/test_price_volume_low_turnover_strategy.py tests/test_strong_market_core_participation_strategy.py tests/test_strong_market_liquid_breadth_participation_strategy.py tests/test_strategy_market_context.py
```

Expected: PASS with no changes to existing strategy outputs on the deterministic fixture.

- [ ] **Step 4: Commit the limited migration**

```bash
git add phase0/walk_forward.py tests/test_technical_features.py
git commit -m "refactor: reuse shared daily features in walk forward"
```

**Exit gate:** Phase 1 provides all requested local technical indicators, does not download data, preserves current strategy features numerically, and documents formula/availability/missing-data semantics. Its output may be used for local diagnostics; it may not enter a new strategy experiment/admission run until the Phase 2 price-governance gate passes. If an equivalence test changes a legacy signal, stop and keep the legacy implementation until the discrepancy is explained in a separate decision record.

## 7. Phase 2 — Corporate-Action Completeness and Adjustment Audit

**Purpose:** Make the statement “adjusted prices handle company actions” evidence-based. Current adjustment factors are extensive, but dividend-event coverage is known to be inadequate; adjusted-price usability must be evaluated as an auditable whole, not inferred from any one table.

**Entrance criteria:** Phase 1 passes; `qfq_asof` remains the configured backtest mode; a local database snapshot and pre-refresh audit have been captured.

### Task 2.1: Add a corporate-action coverage and reconciliation audit

**Files:**

- Create: `tests/test_adjustment_coverage_audit.py`
- Modify: `phase0/data_governance/backfills/tushare_history_audit_queries.py`
- Modify: `phase0/data_governance/backfills/adjustment.py`
- Modify: `docs/data_governance/DATA_REFRESH_RUNBOOK.md`

- [ ] **Step 1: Write missing-event and as-of reconciliation tests**

Build temporary SQLite fixtures with BFQ bars, QFQ bars, factor rows, and a dividend event. Assert that the audit reports: per-symbol/date coverage, missing factor dates, action-event counts, and any QFQ/BFQ/factor reconciliation mismatch. Use an event announced after the test as-of date and assert it is excluded from an as-of audit snapshot.

- [ ] **Step 2: Run tests and confirm the audit fields are missing**

Run: `./.venv/bin/python -m pytest -q tests/test_adjustment_coverage_audit.py`

Expected: FAIL until the audit produces action timestamp, record count, factor coverage, and mismatch fields.

- [ ] **Step 3: Implement read-only action and adjustment audit queries**

Return one JSON-serializable result with `symbols_checked`, `bar_dates_checked`, `factor_missing_dates`, `action_events`, `event_dates_after_asof`, `reconciliation_mismatches`, and `coverage_ratio`. The audit must distinguish “no event occurred” from “event source has no coverage.”

- [ ] **Step 4: Produce and review the real-data pre-backfill audit**

Run the project’s existing local Tushare history audit path against the A-share SQLite database and save its JSON/CSV output under an ignored local report directory. Do not change the database in this step. Record the observed fact that `market_dividends` is currently incomplete rather than treating an empty/near-empty table as proof of no dividends.

- [ ] **Step 5: Commit audit-only change**

```bash
git add phase0/data_governance/backfills/tushare_history_audit_queries.py phase0/data_governance/backfills/adjustment.py tests/test_adjustment_coverage_audit.py docs/data_governance/DATA_REFRESH_RUNBOOK.md
git commit -m "feat: audit corporate-action and adjustment coverage"
```

### Task 2.2: Run a bounded company-action repair in a dedicated worktree

**Files:**

- Modify only ignored local data/report/log assets in the dedicated worktree.
- Do not modify: `phase0/`, `scripts/`, `tests/`, `config.yaml` from this worktree.

- [ ] **Step 1: Create an isolated data-repair worktree from the audited `main` commit**

```bash
git worktree add ../stok-mapping-action-repair -b codex/action-repair-data main
```

- [ ] **Step 2: Snapshot local database and restrict the request envelope**

Copy or snapshot the local SQLite database outside Git. Set the approved action repair range to dates/symbols flagged by the Phase 2.1 audit; no all-history “refresh everything” command is permitted.

- [ ] **Step 3: Execute the existing controlled backfill path in chunks**

Use the project’s existing Tushare history/backfill command with an explicit approved date window and chunk size. Persist every request failure and retry count to ignored logs. If the source cannot provide announcement/ex-date/record-date semantics required by the audit, stop this task and leave the source disabled for price-governance promotion.

- [ ] **Step 4: Run post-backfill audit and sampled reconciliation**

Compare pre/post `action_events`, factor coverage, and mismatches. Sample at least 20 symbols across different exchanges and event types, including before/after event dates. Verify that a signal on date `T` does not use an event first known after `T`.

- [ ] **Step 5: Write an ignored local repair report and decide outcome**

Outcome is one of: `passed_for_qfq_asof_audit`, `partially_covered_not_promoted`, or `source_insufficient`. Do not claim completed corporate-action support unless the first outcome is justified by the audit.

**Exit gate:** Complete only when the adjustment audit can measure coverage and the repaired source passes its agreed coverage threshold without as-of leakage. Otherwise retain the existing `qfq_asof` safeguard, mark action-event data incomplete, and continue strategy research only under the currently proven adjustment contract.

## 8. Phase 3 — Market, Industry, Style, Breadth, and Flow Proxies

**Purpose:** Turn existing index metadata/bars, PIT constituents/weights, and limited northbound data into governed market-context features. The existing PIT constituent/weight minimum asset covers `SH.000300`, `SH.000905`, and `SH.000852`; it is suitable for a controlled broad-index trial after freshness repair, not a claim of complete industry coverage. This phase does not invent order-book coverage: turnover and northbound proxies remain clearly labeled.

**Entrance criteria:** Phase 2 audit outcome is recorded; an index freshness audit shows that index dates and stock-bar dates are compared explicitly.

### Task 3.1: Refresh and audit index data to declared parity

**Files:**

- Create: `tests/test_market_context_features.py`
- Modify: `phase0/data_governance/feature_audit.py`
- Modify: `phase0/data_governance/index_asof_backfill.py`
- Modify: `docs/data_governance/SOURCE_CONTRACTS.md`

- [ ] **Step 1: Write index freshness and PIT availability tests**

Create a fixture whose stock bars extend to `2024-02-01` and whose index bars stop at `2024-01-31`. Assert the audit returns `stale_by_sessions > 0`. Add a constituent/weight row published after the as-of date and assert the feature builder excludes it.

- [ ] **Step 2: Implement `audit_index_freshness()` and the index source contract**

`audit_index_freshness()` must compare the configured daily-bar and index-bar calendars, report `daily_max_date`, `index_max_date`, `stale_by_sessions`, index coverage by category, and unavailable source dates. Document index ID, category, trading calendar, constituent/weight as-of timestamp, and permitted feature uses.

- [ ] **Step 3: Run a bounded index refresh**

In a dedicated data-repair worktree, request only the missing sessions from the current index maximum date through the current daily-bar maximum date, plus an approved buffer for late corrections. Run pre/post audits and preserve artifacts locally. Do not refresh unrelated indexes or reimport the database wholesale.

- [ ] **Step 4: Commit only audit/source-contract code and tests**

```bash
git add phase0/data_governance/feature_audit.py phase0/data_governance/index_asof_backfill.py tests/test_market_context_features.py docs/data_governance/SOURCE_CONTRACTS.md
git commit -m "feat: audit index freshness and as-of coverage"
```

### Task 3.2: Build PIT broad-index and breadth features from local assets

**Files:**

- Create: `phase0/research/features/market_context.py`
- Modify: `phase0/research/features/__init__.py`
- Modify: `phase0/strategies/strong_market_core_participation.py:483-489`
- Modify: `phase0/strategies/strong_market_liquid_breadth_participation.py:95-150`
- Modify: `tests/test_market_context_features.py`
- Modify: `docs/data_governance/FEATURE_REGISTRY.md`

- [ ] **Step 1: Write deterministic broad-index/breadth tests**

On a fixture with a market benchmark and a PIT stock universe, assert that `market_momentum_20` uses only benchmark observations through `T`, `market_breadth_advance_ratio` equals advances / (advances + declines), and no feature for `T` changes if an index or constituent row at `T+1` changes. Include a suspension/no-volume security and assert the breadth denominator reports why it was excluded.

- [ ] **Step 2: Implement Tier-B registry builders**

Provide `market_return_1`, `market_momentum_20`, `market_breadth_advance_ratio`, `market_breadth_net_advances`, `style_proxy_return_20`, and `northbound_net_buy_proxy` only where their underlying local source and as-of rule are present. Build breadth from the PIT universe and report its denominator/exclusions. If the source field is absent, return documented `NaN` plus audit metadata; do not fabricate zero. Do not build industry-relative features in this task because the local `market_stocks.industry` label is current-state metadata rather than a historical classification asset.

- [ ] **Step 3: Preserve only broad-index strategy behavior through compatibility aliases**

Migrate only reused broad-index or breadth calculations after testing exact equivalence on their existing fixtures. Keep strategy-specific filters/ranks in the strategy modules. Existing industry-relative-strength calculations remain unchanged until Task 3.3 passes.

- [ ] **Step 4: Run market-context regression tests**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_market_context_features.py tests/test_index_asof_audit.py tests/test_index_asof_backfill.py tests/test_strong_market_core_participation_strategy.py tests/test_strong_market_liquid_breadth_participation_strategy.py tests/test_price_volume_low_turnover_strategy.py
```

Expected: PASS.

- [ ] **Step 5: Commit the feature integration**

```bash
git add phase0/research/features/market_context.py phase0/research/features/__init__.py phase0/strategies/strong_market_core_participation.py phase0/strategies/strong_market_liquid_breadth_participation.py tests/test_market_context_features.py docs/data_governance/FEATURE_REGISTRY.md
git commit -m "feat: add point-in-time market breadth features"
```

### Task 3.3: Make a separate industry-history source decision, then build industry features only if approved

**Files:**

- Create: `docs/data_governance/INDUSTRY_CLASSIFICATION_SOURCE_DECISION.md`
- Create on approval: `phase0/data_governance/industry_classification.py`
- Create on approval: `tests/test_industry_classification_asof.py`
- Modify on approval: `phase0/research/features/market_context.py`
- Modify on approval: `phase0/strategies/strong_market_core_participation.py:483-489`
- Modify on approval: `phase0/strategies/strong_market_liquid_breadth_participation.py:95-150`

- [ ] **Step 1: Record the current limitation and source requirements**

Document that the current `market_stocks.industry` value has no proven historical effective-date/as-of history and must not be used to backfill historical sector membership. An acceptable source must provide stable security identifiers, classification standard/version, effective date, end date or supersession date, source publication/as-of time, and historical change coverage.

- [ ] **Step 2: Decide whether a qualified source exists**

Choose `defer_no_qualified_source`, `run_bounded_source_pilot`, or `integrate_approved_source`. The first two outcomes make no code/data changes beyond the decision record and leave existing strategy-local industry logic as an explicitly limited research artifact.

- [ ] **Step 3: Only for `integrate_approved_source`, write PIT classification tests**

Create a security that changes industry effective on `2024-07-01`, with the source published on `2024-07-03`. Assert that a signal on `2024-07-02` uses the old classification and a signal on `2024-07-03` uses the new classification. Assert that a future reclassification cannot alter a prior as-of panel.

- [ ] **Step 4: Only for `integrate_approved_source`, implement versioned as-of membership**

Persist classification rows with `symbol`, `classification_standard`, `classification_version`, `industry_code`, `effective_date`, `end_date`, `published_at`, and `ingested_at`; select the most recent row visible by signal date. Then register `industry_return_1`, `industry_relative_mom20`, and `industry_relative_mom60`, report classification coverage, and migrate strategy-local calculations only after fixture equivalence tests pass.

- [ ] **Step 5: Commit an approved integration separately**

```bash
git add phase0/data_governance/industry_classification.py phase0/research/features/market_context.py phase0/strategies/strong_market_core_participation.py phase0/strategies/strong_market_liquid_breadth_participation.py tests/test_industry_classification_asof.py docs/data_governance/INDUSTRY_CLASSIFICATION_SOURCE_DECISION.md
git commit -m "feat: add point-in-time industry classification features"
```

**Exit gate:** Broad-index data reaches an explicit freshness tolerance relative to daily bars; breadth has causal/PIT tests; northbound fields are labeled as proxies; industry features are unavailable unless a time-versioned source passes Task 3.3; order-book/depth remains unsupported rather than implied.

## 9. Phase 4 — Fundamentals, Valuation, and Estimate-Revisions Decision

**Purpose:** Standardize existing financial/daily-basic data with announcement-time safety. Estimate revisions are deliberately separated because the project does not presently have a qualified historical source for them.

**Entrance criteria:** Phase 3 passes or is explicitly deferred; Phase 0 audits report the current financial/daily-basic end dates and coverage.

### Task 4.1: Promote existing financial and valuation fields to Tier-B features

**Files:**

- Create: `phase0/research/features/fundamental.py`
- Create: `tests/test_financial_feature_asof.py`
- Modify: `phase0/data_governance/financial_pti.py`
- Modify: `phase0/research/features/__init__.py`
- Modify: `docs/data_governance/FEATURE_REGISTRY.md`

- [ ] **Step 1: Write announcement-date join tests**

Build a fixture with a report period of `2024-03-31`, announcement date `2024-04-30`, and trading dates before and after `2024-04-30`. Assert that `roe_ttm`, `revenue_growth_yoy`, `profit_growth_yoy`, `debt_to_assets`, `pe_ttm`, `pb`, `market_cap`, and `float_market_cap` are unavailable before the permitted announcement date and available afterward. Assert that a later restatement cannot alter an earlier as-of panel unless the restatement was already public at that time.

- [ ] **Step 2: Implement a single as-of join boundary**

The public builder accepts daily panel rows plus normalized financial/daily-basic source tables, selects the latest eligible record by `announcement_date <= signal_date`, records `source_announcement_date`, and preserves `NaN` where no eligible record exists. Do not forward-fill backward and do not use `report_date` as a publication proxy.

- [ ] **Step 3: Add coverage and stale-source diagnostics**

For every requested fundamental feature, output source availability ratio, median source age in sessions, and number of symbols with stale/missing values. Establish a config threshold that can block a strategy from using a feature when availability falls below the threshold.

- [ ] **Step 4: Validate against current factor diagnostics**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_financial_feature_asof.py tests/test_daily_basic_history.py tests/test_slow_multifactor_features.py tests/test_strategy_admission_config.py
```

Expected: PASS; existing slow-multifactor inputs retain their previous numeric output on the frozen fixture.

- [ ] **Step 5: Commit fundamentals integration**

```bash
git add phase0/research/features/fundamental.py phase0/research/features/__init__.py phase0/data_governance/financial_pti.py tests/test_financial_feature_asof.py docs/data_governance/FEATURE_REGISTRY.md config.yaml
git commit -m "feat: add point-in-time fundamental feature joins"
```

### Task 4.2: Make a go/no-go decision for analyst estimate revisions

**Files:**

- Modify: `docs/data_governance/SOURCE_CONTRACTS.md`
- Create: `docs/data_governance/ESTIMATE_REVISION_SOURCE_DECISION.md`

- [ ] **Step 1: Define minimum admission requirements for a candidate source**

The source must provide stable security identifiers, metric/period, consensus value, historical revision timestamps, source publication timestamp, analyst/broker coverage metadata, backfill policy, license/redistribution terms, and an API/bulk cost estimate.

- [ ] **Step 2: Evaluate candidate sources without integrating any data**

For each candidate, record field-level coverage for A shares, earliest history, update schedule, whether snapshots/revisions are historical rather than current-only, cost, license, and retention. Reject sources that cannot prove historical revision time.

- [ ] **Step 3: Record one decision**

Choose `defer_no_qualified_source`, `run_bounded_paid_source_pilot`, or `integrate_approved_source`. Only the last option permits a new implementation plan. The other two options add no connector and no download.

**Exit gate:** Existing financial/valuation fields have PIT join tests and availability metrics. Estimate revisions remain marked unavailable unless the separate source decision proves a qualified dataset.

## 10. Phase 5 — External Macro, Rates, FX, and Commodities (Opt-In)

**Purpose:** Add a small number of governed macro features only after local A-share feature integrity is established. Existing FRED connectivity is not equivalent to a research-ready macro feature asset.

**Entrance criteria:** Phase 4.1 passes; each requested series has a documented research hypothesis and source contract; no external source is enabled globally.

### Task 5.1: Establish an incremental external-series contract

**Files:**

- Create: `phase0/data_governance/external_series.py`
- Create: `tests/test_external_series_contract.py`
- Modify: `phase0/data_access/connectivity.py`
- Modify: `config.yaml`
- Modify: `docs/data_governance/SOURCE_CONTRACTS.md`

- [ ] **Step 1: Write cache-boundary and release-time tests**

Create a fake provider response with observations dated `T` but release timestamps at `T+7`. Assert that `load_asof(signal_date=T+3)` excludes the observation. Assert that an empty local cache raises a clear disabled-source error instead of fetching because a feature import occurred.

- [ ] **Step 2: Implement a read-only, source-disabled-by-default contract**

```python
@dataclass(frozen=True)
class ExternalSeriesContract:
    name: str
    provider: str
    observation_frequency: str
    release_timestamp_column: str
    allowed_feature_lag_sessions: int
    local_cache_path: Path
    enabled: bool = False
```

The loader reads an existing local cache only. A separately invoked refresh function must receive an explicit `series_name`, `start_date`, `end_date`, and byte/row budget and must write release timestamps, ingestion timestamp, provider revision marker, and raw observation value.

- [ ] **Step 3: Pilot one FRED series only**

Start with the existing configured `FEDFUNDS` or `VIXCLS` series, not the full configuration list. Fetch only the newest missing observations, record the release/as-of semantics, and leave `data_sources.fred.enabled: false` until the test and audit pass.

- [ ] **Step 4: Validate and commit source-contract code**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_external_series_contract.py tests/test_tiingo_news_probe_paths.py
```

Expected: PASS. Commit code/docs/config only; local macro cache remains ignored.

```bash
git add phase0/data_governance/external_series.py phase0/data_access/connectivity.py tests/test_external_series_contract.py config.yaml docs/data_governance/SOURCE_CONTRACTS.md
git commit -m "feat: add governed external-series cache contract"
```

### Task 5.2: Decide FX and commodity coverage separately

- [ ] **Step 1: Define the intended series and market relevance**

For each proposed FX/commodity series, specify Chinese market relevance, exchange/benchmark, currency/unit, timezone/trading calendar, source timestamp, historical revisions, and whether the signal is observed before the A-share decision time.

- [ ] **Step 2: Reject or approve a bounded source pilot**

No connector, schema, or backfill begins until the same standards as Task 5.1 are satisfied. A current-price-only free endpoint is not acceptable for historical backtests.

**Exit gate:** Macro is an optional, local-cache-backed input with explicit release timing. FX and commodities remain unavailable until individually approved; no “macro capability” claim is made from a connector alone.

## 11. Phase 6 — Announcements, News, Sentiment, Social, and Market Microstructure

**Purpose:** Preserve the current AI corpus and news connector for explanation/event-risk research, while making explicit what evidence would be required before any text or microstructure feature is allowed into a ranking model.

**Entrance criteria:** Phases 1–4 pass; a user-approved research hypothesis identifies a specific use case (for example, event-risk exclusion rather than return prediction).

### Task 6.1: Establish a text/event feature eligibility audit

**Files:**

- Create: `phase0/data_governance/text_event_audit.py`
- Create: `tests/test_text_event_audit.py`
- Modify: `docs/data_governance/SOURCE_CONTRACTS.md`
- Modify: `docs/PROJECT_ARCHITECTURE_OVERVIEW.md:857-900`

- [ ] **Step 1: Write timestamp/entity-linkage tests**

Use a fixture where an article is ingested before signal time but published after it. Assert that it is excluded. Use an article without a resolved symbol/industry entity and assert it cannot enter a per-security feature frame.

- [ ] **Step 2: Implement eligibility audit only**

The audit reports source, document count, publishing-time completeness, `as_of_time` completeness, entity-link rate, duplicate rate, language/market coverage, and timestamp violations. It does not create a sentiment score.

- [ ] **Step 3: Run corpus audit and write a local-only report**

Record the bounded current corpus coverage and explicitly label it insufficient for broad historical signal research if the sample cannot cover the intended backtest period.

- [ ] **Step 4: Commit governance-only work**

```bash
git add phase0/data_governance/text_event_audit.py tests/test_text_event_audit.py docs/data_governance/SOURCE_CONTRACTS.md docs/PROJECT_ARCHITECTURE_OVERVIEW.md
git commit -m "feat: add text-event data eligibility audit"
```

### Task 6.2: Make separate source decisions for sentiment, social, and depth

- [ ] **Step 1: Write source decision records**

Create one decision record per category: `news_and_announcements`, `social_sentiment`, and `order_book_microstructure`. Each record must list intended use, identifier resolution, point-in-time timestamp, history depth, coverage, licensing, rate/cost limits, storage impact, retention, and validation dataset.

- [ ] **Step 2: Apply the default decisions**

Keep news/announcements as explanation and event-risk inputs only. Mark social sentiment and order-book/depth as unsupported until a qualified source is approved. Do not map northbound net-buy or turnover to “funds flow/order-book” without an explicit proxy label.

**Exit gate:** Text/microstructure sources cannot enter strategy ranking unless their separate decision record, coverage audit, and leakage test pass. Until then the system truthfully reports explanation-only text and no order-book capability.

## 12. Program Acceptance Matrix and Stop Conditions

| Phase | Acceptance evidence | Stop / downgrade condition |
| --- | --- | --- |
| 0 | Read-only audit tests and reproducible coverage snapshot | Cannot inspect source schema safely |
| 1 | Feature registry + causal/equivalence tests; no network activity | Legacy output changes or registry triggers I/O |
| 2 | Corporate-action coverage/reconciliation audit and bounded repair report | Event timing/coverage cannot be proven |
| 3 | Index freshness parity report and PIT context-feature tests | Stale index data exceeds tolerance or source-time fields absent |
| 4 | Announcement-date financial joins and coverage metrics | Current values leak before publication; estimates source lacks revision history |
| 5 | Local cached macro with release-time contract | Provider cannot supply time-safe history or exceeds approved budget |
| 6 | Text eligibility audit and source-decision records | Timestamp/entity coverage inadequate for the stated use |

No phase directly promotes a strategy. Any feature later proposed for ranking must be evaluated through the existing `qfq_asof`, PIT universe, cost, walk-forward, overfit, industry-concentration, factor-diagnostic, and admission gates.

## 13. Recommended Execution Order and Effort

1. **Gate 0** — first (about 0.5–1 engineering day): establishes contracts, source freshness, and replay evidence for every later phase.
2. **Phase 1 and Phase 2** — begin after Gate 0; they can proceed as separate workstreams (about 2–4 engineering days for local registry, 1–3 engineering days plus data-repair runtime for action audit). Phase 2 must pass before Phase 1 price features enter a strategy experiment.
3. **Phase 3** — third (about 2–3 engineering days plus bounded broad-index refresh): makes broad market/breadth context reusable and time-safe. Historical industry features stay a separately approved source decision.
4. **Phase 4.1** — fourth (about 2–4 engineering days): uses existing financial/daily-basic assets. **Phase 4.2** is a source/cost decision, not implementation by default.
5. **Phase 5** — optional pilot (about 1–2 engineering days plus source review): one macro series, incremental only.
6. **Phase 6** — governance/feasibility work (about 1–2 engineering days): do not build sentiment/depth models before qualifying the data.

The critical path is Gate 0 → (Phase 1 and Phase 2) → Phase 3. Phases 4–6 can be scheduled after Phase 3, but estimate revisions, macro, text, social, and depth must remain isolated by their source contracts rather than folded into a single undifferentiated registry rollout.

## 14. Final Verification Before Any Feature Is Used in Research

- [ ] Run all new tests plus the current baseline:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_feature_audit.py \
  tests/test_feature_registry.py \
  tests/test_technical_features.py \
  tests/test_adjustment_coverage_audit.py \
  tests/test_market_context_features.py \
  tests/test_financial_feature_asof.py \
  tests/test_external_series_contract.py \
  tests/test_text_event_audit.py \
  tests/test_daily_basic_history.py \
  tests/test_index_asof_audit.py \
  tests/test_index_asof_backfill.py \
  tests/test_slow_multifactor_features.py \
  tests/test_strategy_market_context.py
```

Expected: PASS. Tests that belong to a deferred phase may be omitted only when their production modules have not been introduced; the phase record must say so explicitly.

- [ ] Run a local coverage audit for every enabled source and archive its JSON/CSV report outside Git.
- [ ] Confirm `config.yaml` still has external data sources disabled unless the relevant source contract and pilot have passed.
- [ ] Confirm every newly enabled feature records its source table, formula version, requested date range, missing-data policy, and as-of rule in its audit output.
- [ ] Run the existing strategy admission tests before any candidate uses a new feature. A passing unit test is necessary but not sufficient for admission.

## 15. Self-Review of This Program Plan

- The three requested groups—market, technical/behavioral, and fundamental/event data—are all mapped to a phase and acceptance condition. Historical industry classification is explicitly identified as a source gap rather than reconstructed from a current-state label.
- The plan separates local feature computation from external acquisition, so a feature registry does not imply a large download.
- QFQ/BFQ/corporate actions, financial announcement timing, index constituent timing, macro release timing, and text publication timing all have explicit point-in-time checks.
- Analyst revisions, social sentiment, and order-book/depth are intentionally not represented as existing capabilities; each requires an independent source decision because quality, licensing, and historical timing are the core risk.
- Research artifacts and databases remain local-only; executable code/config/tests/docs have small, reviewable commits.
