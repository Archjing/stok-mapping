# A-Share ETF Sector History Capability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an auditable A-share ETF catalog plus sector-scoped historical raw bars and adjustment factors, with resumable backfills and strict point-in-time adjusted reads.

**Architecture:** Synchronize the full lightweight ETF catalog, but never default to full-market ETF history. Resolve only explicitly configured sector/universe symbols into an immutable run manifest, persist ETF data and run state in a dedicated SQLite database, and calculate `qfq_asof` from raw bars and factors at read time without using future factors or backward filling missing factors.

**Tech Stack:** Python 3.14, pandas, SQLite, requests, PyYAML, argparse, pytest, Tushare Pro, existing Phase 0 CLI conventions.

---

## Non-Negotiable Scope Boundary

- Full-catalog metadata sync is allowed because it is lightweight.
- Historical downloads require a named configured universe. There is no `all`, wildcard, inferred-name, or catalog-wide fallback.
- Sector membership is an explicit project classification in `config.yaml`; ETF names are not used to infer sectors.
- `--sector` is repeatable and selects one or more configured sectors. Omitting it means every sector inside the named universe, never every ETF in the catalog.
- Every new history run must support `--dry-run` and report symbol count, annual chunks, dataset count, total provider calls, and the configured hard limits before any history endpoint is called.
- The implementation stores data in `data/etf_history.sqlite`, not in `data/manual_history/a_share_history.sqlite`.
- `market_stocks`, the stock universe, stock valuation/fundamental filters, and existing stock daily tables remain unchanged.
- Historical tables store only raw exchange prices and separate adjustment factors.
- Research reads may request `qfq_asof`; execution-price reads remain raw.
- Tracking-index observations from the current Tushare catalog are not represented as historical PIT mappings unless configuration supplies explicit effective dates.
- Reports, logs, SQLite databases, and provider payloads are local runtime assets and must not be committed.
- The MVP does not add ETF holdings, NAV, creation/redemption data, intraday data, realtime quotes, automated scheduling, strategy admission, or simulated/live ETF trading.

## Status And Exit Contract

Run statuses:

- `planned`: manifest and tasks exist, no task has started.
- `running`: at least one task has started and the run is not terminal.
- `ok`: every persisted history task succeeded. This is task completion, not research admission.
- `partial`: at least one task is `empty` or `failed`, while at least one task succeeded.
- `failed`: no task succeeded or manifest validation failed after run creation.

Audit statuses stored separately on the run:

- `not_run`: no audit has evaluated the completed run.
- `pass`: the latest audit found no blocking invariant violation.
- `blocking`: the latest audit found missing/invalid coverage; the run is not research-admitted even if task status is `ok`.
- `error`: the audit itself could not evaluate its invariants.

Task statuses:

- `pending`, `running`, `succeeded`, `empty`, `failed`.

CLI exit codes:

- `0`: task-level backfill `ok`, or a successful catalog sync/universe dry-run/audit.
- `2`: partial, failed, missing token, permission denied, stale catalog, invalid universe, resume mismatch, or blocking audit finding.

An empty provider response is not a successful history task. It is persisted as `empty`, explained in the audit, and prevents an `ok` run when the chunk overlaps the ETF's effective listed interval. A run is usable for strict historical research only when `status='ok' AND audit_status='pass'`.

## File Map

| File | Responsibility |
| --- | --- |
| `phase0/data_access/symbols.py` | Convert suffix-qualified Tushare symbols to local symbols and back without stock-prefix guessing. |
| `phase0/data_access/providers/tushare.py` | Typed Tushare errors plus normalized `etf_basic`, `fund_daily`, and `fund_adj` calls. |
| `phase0/data_governance/etf_store.py` | ETF schema, unique keys, UPSERTs, catalog snapshots, immutable manifests, runs, and tasks. |
| `phase0/data_governance/etf_catalog.py` | Transactional active+delisted catalog synchronization and freshness checks. |
| `phase0/data_governance/etf_universe.py` | Explicit universe/sector parsing, lifecycle clipping, tracking assertions, and config digesting. |
| `phase0/data_governance/backfills/etf_history.py` | Annual task planning, throttled execution, task transactions, retry, and resume. |
| `phase0/data_access/etf_history.py` | Raw and strict `qfq_asof` reads from the dedicated ETF database. |
| `phase0/data_governance/etf_audit.py` | Manifest, task, bar, factor, empty-chunk, and PIT coverage audit report. |
| `phase0/cli_commands/data_update.py` | Register and handle ETF catalog, resolve, backfill, and audit commands. |
| `phase0/cli.py` | Add ETF commands to the top-level command index. |
| `config.yaml` | Dedicated ETF database, limits, retry/freshness settings, and explicit sector universes. |
| `data/manual_history/README.md` | Document ETF data semantics, commands, resume rules, and local-only assets. |
| `tests/test_tushare_etf_provider.py` | Symbol conversion, provider normalization, unit conversion, and typed failures. |
| `tests/test_etf_store.py` | Schema keys, idempotent UPSERTs, snapshots, manifests, runs, and tasks. |
| `tests/test_etf_catalog.py` | Active+delisted atomic sync, permission failures, and freshness. |
| `tests/test_etf_universe.py` | Explicit membership, sector uniqueness, tracking assertions, clipping, and digests. |
| `tests/test_backfill_etf_history.py` | Task generation, limits, run status, retries, idempotency, and resume behavior. |
| `tests/test_etf_history_reader.py` | Raw reads, as-of truncation, no future factors, and fail-closed coverage. |
| `tests/test_etf_audit.py` | Blocking empty/factor findings and report contents. |
| `tests/test_cli_data_update_commands.py` | Parser wiring, forwarded arguments, printed summaries, and exit codes. |

## Task 0: Isolate The Implementation And Probe Real Tushare Capabilities

**Files:**
- Copy into worktree: `docs/superpowers/plans/2026-08-11-etf-data-capability.md`
- No source-code changes.

- [ ] **Step 1: Record the dirty main checkout without changing it**

Run:

```bash
cd /Users/aj/workspace/stok-mapping
git status --short --branch
git rev-parse main
```

Expected: existing daily/index backfill changes and local cache files remain visible. Do not stage, stash, reset, clean, or edit them.

- [ ] **Step 2: Create an isolated worktree from committed `main`**

Run with the `superpowers:using-git-worktrees` skill:

```bash
cd /Users/aj/workspace/stok-mapping
git worktree add .worktrees/etf-data-capability -b codex/etf-data-capability main
cp docs/superpowers/plans/2026-08-11-etf-data-capability.md .worktrees/etf-data-capability/docs/superpowers/plans/
cd .worktrees/etf-data-capability
git status --short --branch
```

Expected: only the copied plan is untracked or modified in the new worktree; the original dirty checkout is untouched.

- [ ] **Step 3: Commit the plan as the first isolated change**

```bash
git add docs/superpowers/plans/2026-08-11-etf-data-capability.md
git commit -m "docs: plan A-share ETF data capability"
```

Expected: one documentation commit on `codex/etf-data-capability`.

- [ ] **Step 4: Establish the committed baseline**

Run:

```bash
./.venv/bin/python -m pytest -q
```

Expected: record the exact pass/fail count and failure names. Existing failures may be documented, but every ETF-targeted test introduced below must pass before its task commit.

- [ ] **Step 5: Probe live ETF endpoint permissions without printing the token**

Create `/tmp/probe_tushare_etf_permissions.py` with:

```python
import os
import requests

TOKEN = os.environ.get("TUSHARE_TOKEN", "").strip()
URL = "http://api.tushare.pro"

if not TOKEN:
    raise SystemExit("missing TUSHARE_TOKEN")


def probe(api_name: str, params: dict[str, str], fields: str) -> list[dict[str, object]]:
    response = requests.post(
        URL,
        json={"api_name": api_name, "token": TOKEN, "params": params, "fields": fields},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data", {})
    names = data.get("fields", [])
    items = data.get("items", [])
    print(api_name, "code=", payload.get("code"), "rows=", len(items), "msg=", payload.get("msg"))
    return [dict(zip(names, item, strict=True)) for item in items]


active = probe(
    "etf_basic",
    {"list_status": "L"},
    "ts_code,csname,index_code,index_name,list_date,list_status,exchange",
)
probe("etf_basic", {"list_status": "D"}, "ts_code,csname,index_code,list_date,delist_date,list_status,exchange")
probe("fund_daily", {"ts_code": "510300.SH", "start_date": "20260105", "end_date": "20260109"}, "ts_code,trade_date,open,high,low,close,vol,amount")
probe("fund_adj", {"ts_code": "510300.SH", "start_date": "20260105", "end_date": "20260109"}, "ts_code,trade_date,adj_factor")

for ts_code in ("510300.SH", "159915.SZ", "512480.SH"):
    row = next((item for item in active if item.get("ts_code") == ts_code), None)
    print(
        "tracking-observation",
        ts_code,
        "index_code=", None if row is None else row.get("index_code"),
        "index_name=", None if row is None else row.get("index_name"),
    )
```

Run:

```bash
./.venv/bin/python /tmp/probe_tushare_etf_permissions.py
```

Expected: four endpoint summary lines plus three tracking-observation lines, but no token. Inspect at least one returned `list_status='D'` row and confirm whether `delist_date` is populated. If the provider omits a reliable delist date, do not synthesize one: keep the catalog observation nullable and make delisted-fund lifecycle resolution fail closed until a dated source is added. Treat the printed tracking mapping as an observation, not a historical fact. Only add `expected_tracking_index` to versioned configuration after this probe verifies the exact normalized code; otherwise leave the assertion absent. Missing token or permission does not justify fake success; it means implementation can continue with mocked tests, while live acceptance remains explicitly unverified.

## Task 1: Add ETF-Safe Symbols And Typed Tushare Provider Methods

**Files:**
- Create: `phase0/data_access/symbols.py`
- Modify: `phase0/data_access/providers/tushare.py`
- Create: `tests/test_tushare_etf_provider.py`

- [ ] **Step 1: Write failing symbol and provider tests**

Create `tests/test_tushare_etf_provider.py` with tests covering these exact assertions:

```python
from __future__ import annotations

import pandas as pd
import pytest

from phase0.data_access import symbols
from phase0.data_access.providers import tushare as provider
from phase0.data_access.providers.tushare import TushareConfig, TusharePermissionError


def test_suffix_qualified_symbols_do_not_guess_exchange_from_prefix() -> None:
    assert symbols.from_tushare_symbol("510300.SH") == "SH.510300"
    assert symbols.from_tushare_symbol("159915.SZ") == "SZ.159915"
    assert symbols.from_tushare_symbol("931865.CSI") == "CSI.931865"
    assert symbols.from_tushare_symbol("510300") == ""
    assert symbols.to_tushare_symbol("SH.512480") == "512480.SH"
    assert symbols.normalize_etf_symbol("SH.510300") == "SH.510300"
    assert symbols.normalize_etf_symbol("510300.SH") == "SH.510300"
    with pytest.raises(ValueError, match="exchange-qualified"):
        symbols.normalize_etf_symbol("510300")
    with pytest.raises(ValueError, match="SH or SZ"):
        symbols.normalize_etf_symbol("CSI.931865")


def test_fetch_etf_basic_preserves_observed_tracking_mapping(monkeypatch) -> None:
    def fake_call(api_name, *, params, fields, cfg):
        assert api_name == "etf_basic"
        assert params == {"list_status": "L"}
        return pd.DataFrame([{
            "ts_code": "510300.SH", "csname": "300ETF", "extname": "沪深300ETF",
            "cname": "华泰柏瑞沪深300ETF", "index_code": "000300.SH",
            "index_name": "沪深300", "setup_date": "20120504", "list_date": "20120528",
            "delist_date": None, "list_status": "L", "exchange": "SH",
            "mgt_name": "华泰柏瑞基金", "custod_name": "工商银行",
            "mgt_fee": "0.50", "etf_type": "股票型",
        }])

    monkeypatch.setattr(provider, "_call", fake_call)
    frame = provider.fetch_tushare_etf_basic(list_status="L", cfg=TushareConfig(enabled=True))
    assert frame.loc[0, "symbol"] == "SH.510300"
    assert frame.loc[0, "index_code_raw"] == "000300.SH"
    assert frame.loc[0, "tracking_index_symbol"] == "SH.000300"
    assert frame.loc[0, "list_date"] == "2012-05-28"
    assert frame.loc[0, "management_fee"] == 0.5


def test_fetch_etf_daily_converts_provider_units(monkeypatch) -> None:
    monkeypatch.setattr(provider, "_call", lambda *args, **kwargs: pd.DataFrame([{
        "ts_code": "510300.SH", "trade_date": "20260105", "open": 4.0,
        "high": 4.1, "low": 3.9, "close": 4.05, "pre_close": 3.98,
        "change": 0.07, "pct_chg": 1.7588, "vol": 123.0, "amount": 456.0,
    }]))
    frame = provider.fetch_tushare_etf_daily(
        "510300.SH", start_date="2026-01-01", end_date="2026-01-05", cfg=TushareConfig(enabled=True)
    )
    assert frame.loc[0, "symbol"] == "SH.510300"
    assert frame.loc[0, "volume"] == 12300.0
    assert frame.loc[0, "amount"] == 456000.0
    assert frame.loc[0, "price_mode"] == "raw"


def test_permission_error_is_not_normalized_to_empty(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"code": 40203, "msg": "permission denied", "data": {"fields": [], "items": []}}

    monkeypatch.setenv("TUSHARE_TOKEN", "test-token")
    monkeypatch.setattr(provider.requests, "post", lambda *args, **kwargs: FakeResponse())
    with pytest.raises(TusharePermissionError, match="permission denied"):
        provider._call("etf_basic", params={"list_status": "L"}, fields=["ts_code"], cfg=TushareConfig(enabled=True, max_retries=1))
```

- [ ] **Step 2: Run the tests and verify RED**

```bash
./.venv/bin/python -m pytest -q tests/test_tushare_etf_provider.py
```

Expected: import or attribute failures for the new symbol/provider contracts.

- [ ] **Step 3: Implement the asset-safe symbol boundary**

Create `phase0/data_access/symbols.py`:

```python
from __future__ import annotations

import re

_TUSHARE_TO_LOCAL = {"SH": "SH", "SZ": "SZ", "BJ": "BJ", "CSI": "CSI"}
_LOCAL_TO_TUSHARE = {value: key for key, value in _TUSHARE_TO_LOCAL.items()}


def from_tushare_symbol(value: object) -> str:
    raw = str(value or "").strip().upper()
    match = re.fullmatch(r"(\d{6})\.([A-Z]+)", raw)
    if match is None:
        return ""
    code, suffix = match.groups()
    prefix = _TUSHARE_TO_LOCAL.get(suffix)
    return f"{prefix}.{code}" if prefix else ""


def to_tushare_symbol(value: object) -> str:
    raw = str(value or "").strip().upper()
    match = re.fullmatch(r"([A-Z]+)\.(\d{6})", raw)
    if match is None:
        return ""
    prefix, code = match.groups()
    suffix = _LOCAL_TO_TUSHARE.get(prefix)
    return f"{code}.{suffix}" if suffix else ""


def normalize_etf_symbol(value: object) -> str:
    raw = str(value or "").strip().upper()
    local = raw if re.fullmatch(r"(?:SH|SZ)\.\d{6}", raw) else from_tushare_symbol(raw)
    if not local:
        raise ValueError("ETF symbol must be exchange-qualified, for example SH.510300 or 510300.SH")
    if not re.fullmatch(r"(?:SH|SZ)\.\d{6}", local):
        raise ValueError("ETF symbol exchange must be SH or SZ")
    return local
```

This is separate from `normalize_cn_symbol`; existing stock callers retain their current behavior.

- [ ] **Step 4: Add typed provider errors and normalized ETF methods**

Modify `phase0/data_access/providers/tushare.py` so `TushareAPIError` remains a `RuntimeError` for compatibility, permission/token failures are distinguishable, and these public functions return fixed columns:

```python
class TushareAPIError(RuntimeError):
    def __init__(self, api_name: str, code: object, message: str):
        super().__init__(f"Tushare {api_name} failed: code={code}, msg={message}")
        self.api_name = api_name
        self.code = code
        self.message = message


class TusharePermissionError(TushareAPIError):
    """The token is valid but the endpoint or fields are not authorized."""


class TushareTokenError(TushareAPIError):
    """The configured token is missing, invalid, or rejected."""
```

In `_call`, classify a nonzero API response before retrying:

```python
code = data.get("code")
message = str(data.get("msg") or "unknown error")
if code != 0:
    lowered = message.lower()
    if "permission" in lowered or "权限" in message:
        raise TusharePermissionError(api_name, code, message)
    if "token" in lowered or "token" in message:
        raise TushareTokenError(api_name, code, message)
    raise TushareAPIError(api_name, code, message)
```

Do not retry typed API rejections; retain retries for transport/timeout failures. Add:

```python
ETF_CATALOG_COLUMNS = [
    "symbol", "ts_code", "name", "short_name", "exchange", "list_status",
    "setup_date", "list_date", "delist_date", "etf_type", "management_name",
    "custodian_name", "management_fee", "index_code_raw",
    "tracking_index_symbol", "tracking_index_name", "source",
]
ETF_DAILY_COLUMNS = [
    "symbol", "ts_code", "date", "price_mode", "open", "high", "low", "close",
    "pre_close", "change_amount", "change_pct", "volume", "amount", "source",
]
ETF_FACTOR_COLUMNS = ["symbol", "ts_code", "date", "adj_factor", "source"]
```

Implement `fetch_tushare_etf_basic`, `fetch_tushare_etf_daily`, and `fetch_tushare_etf_adj_factors` using `_call`, `from_tushare_symbol`, ISO dates, numeric coercion, `vol * 100`, `amount * 1000`, and sources `tushare.etf_basic`, `tushare.fund_daily`, and `tushare.fund_adj`. Empty successful responses must return empty frames with the fixed columns; exceptions must propagate.

- [ ] **Step 5: Run focused and provider regression tests**

```bash
./.venv/bin/python -m pytest -q tests/test_tushare_etf_provider.py tests/test_tushare_provider.py
```

Expected: all tests pass, including existing stock provider tests.

- [ ] **Step 6: Commit the provider boundary**

```bash
git add phase0/data_access/symbols.py phase0/data_access/providers/tushare.py tests/test_tushare_etf_provider.py
git commit -m "feat: add Tushare ETF provider boundary"
```

## Task 2: Create The Dedicated ETF SQLite Contract

**Files:**
- Create: `phase0/data_governance/etf_store.py`
- Create: `tests/test_etf_store.py`

- [ ] **Step 1: Write failing schema and UPSERT tests**

Create `tests/test_etf_store.py` with in-memory tests asserting:

```python
from __future__ import annotations

import sqlite3

from phase0.data_governance.etf_store import ensure_etf_schema


def test_etf_schema_has_unique_raw_data_and_task_keys() -> None:
    with sqlite3.connect(":memory:") as conn:
        ensure_etf_schema(conn)
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {
            "etf_catalog_sync_runs", "market_etfs", "market_etf_tracking_mappings",
            "market_etf_daily_bars", "market_etf_adj_factors", "etf_backfill_runs",
            "etf_backfill_manifest_members", "etf_backfill_tasks",
        } <= tables
        conn.execute("INSERT INTO market_etf_daily_bars(symbol,date,open,high,low,close,source,fetched_at) VALUES ('SH.510300','2026-01-05',4,4.1,3.9,4.05,'test','2026-01-06T00:00:00')")
        with __import__("pytest").raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO market_etf_daily_bars(symbol,date,open,high,low,close,source,fetched_at) VALUES ('SH.510300','2026-01-05',4,4.1,3.9,4.05,'test','2026-01-06T00:00:00')")


def test_etf_schema_does_not_create_stock_tables() -> None:
    with sqlite3.connect(":memory:") as conn:
        ensure_etf_schema(conn)
        names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "market_stocks" not in names
    assert "market_daily_bars" not in names
```

Add idempotency tests for catalog, mapping, raw bars, factors, manifest members, and tasks: applying the same logical row twice must leave one row and update mutable payload columns.

- [ ] **Step 2: Run the tests and verify RED**

```bash
./.venv/bin/python -m pytest -q tests/test_etf_store.py
```

Expected: `ModuleNotFoundError` for `phase0.data_governance.etf_store`.

- [ ] **Step 3: Implement the exact schema**

Create `phase0/data_governance/etf_store.py`. Use `phase0.data_governance.sql.safe_identifier` for configurable table names and create these tables in one transaction:

```sql
CREATE TABLE IF NOT EXISTS etf_catalog_sync_runs (
    snapshot_id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('running','ok','failed')),
    active_result TEXT NOT NULL,
    delisted_result TEXT NOT NULL,
    active_rows INTEGER NOT NULL DEFAULT 0,
    delisted_rows INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS market_etfs (
    catalog_snapshot_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    ts_code TEXT NOT NULL,
    name TEXT,
    short_name TEXT,
    exchange TEXT NOT NULL,
    list_status TEXT NOT NULL,
    setup_date TEXT,
    list_date TEXT NOT NULL,
    delist_date TEXT,
    etf_type TEXT,
    management_name TEXT,
    custodian_name TEXT,
    management_fee REAL,
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (catalog_snapshot_id, symbol),
    UNIQUE (catalog_snapshot_id, ts_code)
);

CREATE TABLE IF NOT EXISTS market_etf_tracking_mappings (
    catalog_snapshot_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    index_code_raw TEXT,
    tracking_index_symbol TEXT,
    tracking_index_name TEXT,
    mapping_kind TEXT NOT NULL CHECK (mapping_kind IN ('provider_observation','config_override')),
    source TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    effective_from TEXT,
    effective_to TEXT,
    is_point_in_time INTEGER NOT NULL CHECK (is_point_in_time IN (0,1)),
    PRIMARY KEY (catalog_snapshot_id, symbol, mapping_kind, observed_at)
);

CREATE TABLE IF NOT EXISTS market_etf_daily_bars (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    pre_close REAL,
    change_amount REAL,
    change_pct REAL,
    volume REAL,
    amount REAL,
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS market_etf_adj_factors (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    adj_factor REAL NOT NULL,
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS etf_backfill_runs (
    run_id TEXT PRIMARY KEY,
    universe_name TEXT NOT NULL,
    requested_sectors_json TEXT NOT NULL,
    requested_start TEXT NOT NULL,
    requested_end TEXT NOT NULL,
    config_digest TEXT NOT NULL,
    catalog_snapshot_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('planned','running','ok','partial','failed')),
    audit_status TEXT NOT NULL DEFAULT 'not_run' CHECK (audit_status IN ('not_run','pass','blocking','error')),
    target_tasks INTEGER NOT NULL DEFAULT 0,
    succeeded_tasks INTEGER NOT NULL DEFAULT 0,
    empty_tasks INTEGER NOT NULL DEFAULT 0,
    failed_tasks INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    audited_at TEXT,
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS etf_backfill_manifest_members (
    run_id TEXT NOT NULL,
    universe_name TEXT NOT NULL,
    catalog_snapshot_id TEXT NOT NULL,
    sector TEXT NOT NULL,
    symbol TEXT NOT NULL,
    ts_code TEXT NOT NULL,
    requested_start TEXT NOT NULL,
    requested_end TEXT NOT NULL,
    effective_start TEXT NOT NULL,
    effective_end TEXT NOT NULL,
    expected_tracking_index TEXT,
    resolved_tracking_index TEXT,
    mapping_assertion_status TEXT NOT NULL,
    PRIMARY KEY (run_id, sector, symbol)
);

CREATE TABLE IF NOT EXISTS etf_backfill_tasks (
    run_id TEXT NOT NULL,
    sector TEXT NOT NULL,
    symbol TEXT NOT NULL,
    ts_code TEXT NOT NULL,
    dataset TEXT NOT NULL CHECK (dataset IN ('daily','adj_factor')),
    chunk_start TEXT NOT NULL,
    chunk_end TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending','running','succeeded','empty','failed')),
    attempt_count INTEGER NOT NULL DEFAULT 0,
    fetched_rows INTEGER NOT NULL DEFAULT 0,
    inserted_rows INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    started_at TEXT,
    updated_at TEXT NOT NULL,
    finished_at TEXT,
    PRIMARY KEY (run_id, sector, symbol, dataset, chunk_start, chunk_end)
);
```

Add indexes on catalog snapshot/status, bar/factor date, task run/status, and manifest run/sector. Foreign keys are not required for MVP because the project does not globally enable SQLite foreign-key enforcement; application-level invariants and primary keys remain mandatory.

- [ ] **Step 4: Implement idempotent persistence helpers**

Expose the following exact signatures and implement each body with parameterized SQL:

- `ensure_etf_schema(conn: sqlite3.Connection) -> None`
- `upsert_etf_catalog(conn: sqlite3.Connection, frame: pd.DataFrame, *, snapshot_id: str, fetched_at: str) -> int`
- `insert_tracking_observations(conn: sqlite3.Connection, frame: pd.DataFrame, *, snapshot_id: str, observed_at: str) -> int`
- `upsert_etf_daily_bars(conn: sqlite3.Connection, frame: pd.DataFrame, *, fetched_at: str) -> int`
- `upsert_etf_adj_factors(conn: sqlite3.Connection, frame: pd.DataFrame, *, fetched_at: str) -> int`
- `insert_manifest_members(conn: sqlite3.Connection, rows: list[dict[str, object]]) -> int`
- `insert_backfill_tasks(conn: sqlite3.Connection, rows: list[dict[str, object]]) -> int`
- `refresh_run_counts(conn: sqlite3.Connection, run_id: str) -> dict[str, int]`

Catalog rows use `ON CONFLICT(catalog_snapshot_id, symbol) DO UPDATE`; tracking observations use `ON CONFLICT(catalog_snapshot_id, symbol, mapping_kind, observed_at) DO UPDATE`; bars and factors use their logical keys. Manifests and tasks use plain `INSERT` and treat a primary-key collision as a planning error. Each helper returns the number of logical input rows after deduplication. `refresh_run_counts` performs one grouped task query, updates the four count columns on the run, and returns the same counts as a dictionary.

- [ ] **Step 5: Run schema tests**

```bash
./.venv/bin/python -m pytest -q tests/test_etf_store.py tests/test_data_governance_table_helpers.py
```

Expected: all tests pass and no stock table is created.

- [ ] **Step 6: Commit the storage contract**

```bash
git add phase0/data_governance/etf_store.py tests/test_etf_store.py
git commit -m "feat: add dedicated ETF history store"
```

## Task 3: Synchronize A Complete Lightweight Catalog Atomically

**Files:**
- Create: `phase0/data_governance/etf_catalog.py`
- Create: `tests/test_etf_catalog.py`

- [ ] **Step 1: Write failing catalog synchronization tests**

Create tests for these cases:

```python
def test_catalog_snapshot_is_published_only_after_active_and_delisted_calls_succeed(tmp_path, monkeypatch):
    frames = {"L": _catalog_frame("510300.SH", "L"), "D": _catalog_frame("510050.SH", "D")}
    monkeypatch.setattr(catalog, "fetch_tushare_etf_basic", lambda *, list_status, cfg: frames[list_status])
    result = catalog.sync_etf_catalog(tmp_path / "etf.sqlite", provider_cfg=TushareConfig(enabled=True))
    assert result.status == "ok"
    with sqlite3.connect(tmp_path / "etf.sqlite") as conn:
        rows = conn.execute("SELECT symbol,catalog_snapshot_id FROM market_etfs ORDER BY symbol").fetchall()
    assert rows == [("SH.510050", result.snapshot_id), ("SH.510300", result.snapshot_id)]


def test_permission_denied_does_not_publish_partial_snapshot(tmp_path, monkeypatch):
    def fake_fetch(*, list_status, cfg):
        if list_status == "D":
            raise TusharePermissionError("etf_basic", 40203, "permission denied")
        return _catalog_frame("510300.SH", "L")

    monkeypatch.setattr(catalog, "fetch_tushare_etf_basic", fake_fetch)
    result = catalog.sync_etf_catalog(tmp_path / "etf.sqlite", provider_cfg=TushareConfig(enabled=True))
    assert result.status == "failed"
    assert result.error_kind == "permission_denied"
    with sqlite3.connect(tmp_path / "etf.sqlite") as conn:
        assert conn.execute("SELECT COUNT(*) FROM market_etfs WHERE catalog_snapshot_id=?", (result.snapshot_id,)).fetchone()[0] == 0


def test_successful_empty_response_is_distinct_from_permission_failure(tmp_path, monkeypatch):
    frames = {"L": _catalog_frame("510300.SH", "L"), "D": pd.DataFrame(columns=ETF_CATALOG_COLUMNS)}
    monkeypatch.setattr(catalog, "fetch_tushare_etf_basic", lambda *, list_status, cfg: frames[list_status])
    result = catalog.sync_etf_catalog(tmp_path / "etf.sqlite", provider_cfg=TushareConfig(enabled=True))
    assert result.status == "ok"
    with sqlite3.connect(tmp_path / "etf.sqlite") as conn:
        assert conn.execute("SELECT delisted_result FROM etf_catalog_sync_runs WHERE snapshot_id=?", (result.snapshot_id,)).fetchone()[0] == "empty"


def test_latest_catalog_rejects_stale_snapshot(tmp_path):
    with sqlite3.connect(tmp_path / "etf.sqlite") as conn:
        ensure_etf_schema(conn)
        conn.execute("INSERT INTO etf_catalog_sync_runs VALUES (?,?,?,?,?,?,?,?,?)", ("old", "ok", "ok", "ok", 1, 1, "2026-08-01T00:00:00", "2026-08-01T00:01:00", None))
        with pytest.raises(StaleETFCatalogError):
            catalog.latest_completed_catalog_snapshot(conn, max_age_days=7, now=datetime(2026, 8, 11))
```

Define `_catalog_frame(ts_code, list_status)` at the top of the test file to return one fully normalized provider row with dates, exchange, source, and tracking fields.

- [ ] **Step 2: Run the tests and verify RED**

```bash
./.venv/bin/python -m pytest -q tests/test_etf_catalog.py
```

Expected: import failures for the new catalog module.

- [ ] **Step 3: Implement transactional catalog sync**

Create these contracts in `phase0/data_governance/etf_catalog.py`:

```python
@dataclass(frozen=True)
class ETFCatalogSyncResult:
    status: str
    snapshot_id: str
    active_rows: int
    delisted_rows: int
    error_kind: str | None
    error_message: str | None


class StaleETFCatalogError(RuntimeError):
    """No completed catalog snapshot satisfies the configured freshness bound."""
```

Expose `sync_etf_catalog(db_path: Path, *, provider_cfg: TushareConfig, now: datetime | None = None) -> ETFCatalogSyncResult` and `latest_completed_catalog_snapshot(conn: sqlite3.Connection, *, max_age_days: int, now: datetime | None = None) -> str`.

Implementation sequence:

1. Create a UUID `snapshot_id`; insert a `running` sync row.
2. Fetch `list_status="L"` and `list_status="D"` before publishing any catalog row.
3. Open one SQLite transaction, UPSERT both frames with the same snapshot ID, insert provider tracking observations with that same `catalog_snapshot_id` and `is_point_in_time=0`, and mark the sync `ok`.
4. If token, permission, API, network, or data validation fails, mark the sync `failed` with a sanitized message and leave no catalog rows carrying that snapshot ID.
5. Record successful empty responses as `empty`, not `failed`.
6. `latest_completed_catalog_snapshot` selects only `status='ok'`, verifies `finished_at`, and raises when older than the configured maximum age.

Do not delete or overwrite older successful snapshots or observations; both catalog and tracking queries filter by exactly one completed `catalog_snapshot_id`.

- [ ] **Step 4: Run catalog and provider tests**

```bash
./.venv/bin/python -m pytest -q tests/test_etf_catalog.py tests/test_tushare_etf_provider.py tests/test_etf_store.py
```

Expected: all tests pass, including atomic failure behavior.

- [ ] **Step 5: Commit catalog synchronization**

```bash
git add phase0/data_governance/etf_catalog.py tests/test_etf_catalog.py
git commit -m "feat: synchronize ETF catalog snapshots"
```

## Task 4: Resolve Explicit Sector Universes Into Immutable Manifests

**Files:**
- Create: `phase0/data_governance/etf_universe.py`
- Modify: `config.yaml`
- Create: `tests/test_etf_universe.py`

- [ ] **Step 1: Add the explicit MVP configuration**

Add under `phase0` in `config.yaml`:

```yaml
  etf_history:
    enabled: true
    path: "data/etf_history.sqlite"
    catalog_max_age_days: 7
    chunk_years: 1
    max_symbols_per_run: 50
    max_tasks_per_run: 1000
    max_requests_per_minute: 100
    max_retries: 3
    retry_backoff_seconds: 2.0
    stale_running_minutes: 30
    report_dir: "reports/database_health/etf_history"
    universes:
      sector_core_v1:
        sectors:
          broad_market:
            - symbol: "SH.510300"
            - symbol: "SZ.159915"
          semiconductor:
            - symbol: "SH.512480"
```

No selector key other than explicit `symbol` and optional `expected_tracking_index` is accepted in MVP. The checked-in sample intentionally omits tracking assertions until Task 0 records the provider's real `index_code`/`index_name`; adding a verified assertion is a separate, reviewable configuration change.

- [ ] **Step 2: Write failing resolver tests**

Create tests that build a completed catalog snapshot and assert:

```python
def test_resolver_returns_only_three_configured_symbols():
    assert {(row.sector, row.symbol) for row in manifest.members} == {
        ("broad_market", "SH.510300"),
        ("broad_market", "SZ.159915"),
        ("semiconductor", "SH.512480"),
    }


def test_unconfigured_catalog_etf_is_not_selected():
    assert "SH.588000" not in {row.symbol for row in manifest.members}


def test_tracking_index_mismatch_fails_closed(cfg_with_wrong_tracking_assertion):
    with pytest.raises(ETFUniverseError, match="tracking index mismatch"):
        resolve_etf_universe(conn, phase0_cfg=cfg_with_wrong_tracking_assertion, universe_name="sector_core_v1", requested_sectors=None, start_date=date(2018, 1, 1), end_date=date(2026, 8, 11))


def test_same_symbol_in_two_sectors_fails_closed():
    with pytest.raises(ETFUniverseError, match="multiple sectors"):
        resolve_etf_universe(conn, phase0_cfg=cfg, universe_name="sector_core_v1", requested_sectors=None, start_date=date(2018, 1, 1), end_date=date(2026, 8, 11))


def test_dates_are_clipped_to_listing_lifecycle():
    member = manifest.members[0]
    assert member.effective_start == date(2012, 5, 28)
    assert member.effective_end == date(2020, 12, 31)


def test_digest_is_stable_for_key_order_and_changes_for_membership():
    assert digest_a == digest_b
    assert digest_a != digest_c
```

Define `conn` and `cfg` fixtures in the same file using the sample configuration and a completed catalog snapshot. Define `cfg_with_wrong_tracking_assertion` by deep-copying `cfg` and adding `expected_tracking_index: "SH.999999"` for `SH.510300`, while the synthetic snapshot mapping is `SH.000300`. Also cover missing symbol, malformed suffix, unsupported exchange, stale catalog, `start > end`, unknown/repeated `--sector`, no lifecycle overlap, a delisted member without `delist_date`, and the rule that `requested_sectors=None` selects all sectors in `sector_core_v1` but no catalog-only ETF.

- [ ] **Step 3: Implement strict config parsing and digesting**

Create immutable types in `phase0/data_governance/etf_universe.py`:

```python
@dataclass(frozen=True)
class ETFManifestMember:
    universe_name: str
    sector: str
    symbol: str
    ts_code: str
    requested_start: date
    requested_end: date
    effective_start: date
    effective_end: date
    expected_tracking_index: str | None
    resolved_tracking_index: str | None
    mapping_assertion_status: str


@dataclass(frozen=True)
class ETFUniverseManifest:
    universe_name: str
    requested_sectors: tuple[str, ...]
    requested_start: date
    requested_end: date
    config_digest: str
    catalog_snapshot_id: str
    members: tuple[ETFManifestMember, ...]


class ETFUniverseError(RuntimeError):
    """The requested ETF acquisition universe is invalid or non-reproducible."""
```

Canonicalize the selected universe plus history-affecting settings with `json.dumps(value, sort_keys=True, separators=(",", ":"))`, then SHA-256 it. Reject unknown selector keys so a typo cannot broaden the acquisition boundary.

- [ ] **Step 4: Implement lifecycle and tracking validation**

Expose:

```python
def resolve_etf_universe(
    conn: sqlite3.Connection,
    *,
    phase0_cfg: dict[str, object],
    universe_name: str,
    requested_sectors: list[str] | None,
    start_date: date,
    end_date: date,
    now: datetime | None = None,
) -> ETFUniverseManifest:
    """Resolve and validate one deterministic manifest from a completed catalog snapshot."""
```

Implement the body with the validation sequence below; the docstring shown here is the public contract, not a temporary stub.

For each configured symbol:

1. Require `SH.` or `SZ.` and a reversible Tushare code.
2. Require a row from the latest completed catalog snapshot.
3. Require config sector uniqueness.
4. Read the provider-observed tracking mapping with `WHERE catalog_snapshot_id = manifest.catalog_snapshot_id AND symbol = ?`; never select the latest observation across snapshots.
5. If `expected_tracking_index` is present, require exact normalized equality.
6. Clip requested dates to `[list_date, delist_date]`; open-ended listed ETFs use requested end. A `list_status='D'` member without a reliable `delist_date` fails closed instead of being treated as still listed.
7. Exclude no-overlap members with an explicit diagnostic; fail if the final manifest is empty.
8. Sort sectors and symbols deterministically.
9. Do not treat provider observations without effective dates as historical PIT metadata.

Persist the exact manifest only when creating a run; dry-run returns it without database mutation.

- [ ] **Step 5: Run resolver tests**

```bash
./.venv/bin/python -m pytest -q tests/test_etf_universe.py tests/test_etf_catalog.py
```

Expected: all tests pass and catalog-only symbols never enter the manifest.

- [ ] **Step 6: Commit the universe boundary**

```bash
git add config.yaml phase0/data_governance/etf_universe.py tests/test_etf_universe.py
git commit -m "feat: resolve explicit ETF sector universes"
```

## Task 5: Persist Annual Tasks And Enforce Safe Resume

**Files:**
- Modify: `phase0/data_governance/backfills/__init__.py` only if exports are required by project convention.
- Create: `phase0/data_governance/backfills/etf_history.py`
- Create: `tests/test_backfill_etf_history.py`

- [ ] **Step 1: Write failing planner/resume tests**

Create deterministic tests for:

```python
def test_three_symbols_create_symbol_year_dataset_tasks():
    # Two datasets per symbol per clipped calendar-year chunk.
    assert {(t.sector, t.symbol, t.dataset, t.chunk_start.year) for t in tasks} == expected


def test_task_count_limit_fails_before_provider_calls():
    with pytest.raises(ETFBackfillPlanError, match="max_tasks_per_run"):
        create_etf_backfill_run(conn, manifest, limits=ETFBackfillLimits(max_symbols=1, max_tasks=2))


@pytest.mark.parametrize(("limit_symbols", "limit_tasks"), [(0, None), (-1, None), (None, 0), (None, -1)])
def test_non_positive_cli_limits_fail_closed(limit_symbols, limit_tasks):
    with pytest.raises(ETFBackfillPlanError, match="must be positive"):
        enforce_requested_limits(
            manifest,
            plan_etf_task_specs(manifest),
            configured=ETFBackfillLimits(max_symbols=50, max_tasks=1000),
            limit_symbols=limit_symbols,
            limit_tasks=limit_tasks,
        )


def test_resume_rejects_config_digest_drift():
    with pytest.raises(ETFResumeMismatchError, match="config_digest"):
        validate_resume_contract(conn, run_id, phase0_cfg=changed_phase0_cfg)


def test_resume_rejects_run_manifest_catalog_or_date_mismatch():
    with pytest.raises(ETFResumeMismatchError):
        validate_resume_contract(conn, run_id, phase0_cfg=phase0_cfg)


def test_resume_selects_only_pending_and_failed_tasks():
    assert [task.status for task in resumable] == ["failed", "pending"]


def test_stale_running_task_is_reset_but_recent_running_task_is_not():
    assert stale.status == "pending"
    assert recent.status == "running"
```

Use a temporary SQLite fixture populated through `ensure_etf_schema`, `insert_manifest_members`, and `insert_backfill_tasks`. For the catalog/date mismatch test, mutate one persisted manifest row after run creation so it disagrees with `etf_backfill_runs`; do not construct a replacement manifest from the current catalog. Verify successful tasks are never selected for resume.

- [ ] **Step 2: Run the planner tests and verify RED**

```bash
./.venv/bin/python -m pytest -q tests/test_backfill_etf_history.py -k 'plan or resume or task'
```

Expected: missing module/contracts.

- [ ] **Step 3: Implement fixed calendar-year chunk generation**

Create:

```python
@dataclass(frozen=True)
class ETFBackfillTask:
    run_id: str
    sector: str
    symbol: str
    ts_code: str
    dataset: str
    chunk_start: date
    chunk_end: date
    status: str


@dataclass(frozen=True)
class ETFBackfillTaskSpec:
    sector: str
    symbol: str
    ts_code: str
    dataset: str
    chunk_start: date
    chunk_end: date


@dataclass(frozen=True)
class ETFBackfillLimits:
    max_symbols: int
    max_tasks: int


class ETFBackfillPlanError(RuntimeError):
    """The requested run exceeds limits or cannot produce a valid task set."""


class ETFResumeMismatchError(RuntimeError):
    """Current inputs do not match the persisted run contract."""


def annual_chunks(start: date, end: date) -> list[tuple[date, date]]:
    chunks: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(end, date(cursor.year, 12, 31))
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def plan_etf_task_specs(manifest: ETFUniverseManifest) -> list[ETFBackfillTaskSpec]:
    specs = [
        ETFBackfillTaskSpec(member.sector, member.symbol, member.ts_code, dataset, chunk_start, chunk_end)
        for member in manifest.members
        for chunk_start, chunk_end in annual_chunks(member.effective_start, member.effective_end)
        for dataset in ("daily", "adj_factor")
    ]
    return sorted(
        specs,
        key=lambda item: (item.sector, item.symbol, item.chunk_start, item.dataset),
    )


def enforce_requested_limits(
    manifest: ETFUniverseManifest,
    specs: list[ETFBackfillTaskSpec],
    *,
    configured: ETFBackfillLimits,
    limit_symbols: int | None,
    limit_tasks: int | None,
) -> tuple[int, int]:
    if configured.max_symbols <= 0 or configured.max_tasks <= 0:
        raise ETFBackfillPlanError("configured ETF backfill limits must be positive")
    if limit_symbols is not None and limit_symbols <= 0:
        raise ETFBackfillPlanError("limit_symbols must be positive")
    if limit_tasks is not None and limit_tasks <= 0:
        raise ETFBackfillPlanError("limit_tasks must be positive")
    symbol_cap = min(
        configured.max_symbols,
        limit_symbols if limit_symbols is not None else configured.max_symbols,
    )
    task_cap = min(
        configured.max_tasks,
        limit_tasks if limit_tasks is not None else configured.max_tasks,
    )
    symbol_count = len({member.symbol for member in manifest.members})
    if symbol_count > symbol_cap:
        raise ETFBackfillPlanError(f"symbol count {symbol_count} exceeds max_symbols_per_run {symbol_cap}")
    if len(specs) > task_cap:
        raise ETFBackfillPlanError(f"task count {len(specs)} exceeds max_tasks_per_run {task_cap}")
    return symbol_cap, task_cap
```

Generate `daily` and `adj_factor` tasks for every manifest member and chunk. `--limit-symbols` and `--limit-tasks` are stricter safety caps, not truncation controls: exceeding either fails before inserting the run or calling a provider.

- [ ] **Step 4: Implement run creation and exact resume validation**

Expose these exact functions:

- `create_etf_backfill_run(conn: sqlite3.Connection, manifest: ETFUniverseManifest, *, limits: ETFBackfillLimits, now: datetime | None = None) -> str`
- `load_persisted_manifest(conn: sqlite3.Connection, run_id: str) -> ETFUniverseManifest`
- `load_resumable_tasks(conn: sqlite3.Connection, run_id: str, *, stale_running_minutes: int, now: datetime | None = None) -> list[ETFBackfillTask]`
- `validate_resume_contract(conn: sqlite3.Connection, run_id: str, *, phase0_cfg: dict[str, object]) -> ETFUniverseManifest`

`load_persisted_manifest` reconstructs only from `etf_backfill_runs` and `etf_backfill_manifest_members`. The run row is authoritative for `config_digest` and `requested_sectors_json`; each persisted member repeats `universe_name`, `catalog_snapshot_id`, and requested dates so resume can detect row-level corruption or drift. Resume verifies those repeated fields against the run row, verifies that the referenced catalog snapshot still has `status='ok'`, and verifies that the current history-affecting configuration for that named universe hashes to the stored run-level digest. Any mismatch rejects resume and requires a new run. Reset only `running` tasks older than the configured timeout. Never resolve membership from the current catalog and never replace the persisted task list.

- [ ] **Step 5: Run planner/resume tests**

```bash
./.venv/bin/python -m pytest -q tests/test_backfill_etf_history.py -k 'plan or resume or task'
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit persistent task planning**

```bash
git add phase0/data_governance/backfills/etf_history.py phase0/data_governance/backfills/__init__.py tests/test_backfill_etf_history.py
git commit -m "feat: plan resumable ETF history tasks"
```

If `backfills/__init__.py` does not require an export, omit it from both the change and `git add` command.

## Task 6: Execute Sector-Batched History With Transactional Task State

**Files:**
- Modify: `phase0/data_governance/backfills/etf_history.py`
- Modify: `tests/test_backfill_etf_history.py`

- [ ] **Step 1: Write failing execution tests**

Add tests with a recording fake provider:

```python
def test_failure_continues_other_tasks_but_run_is_partial():
    assert result.status == "partial"
    assert result.succeeded_tasks > 0
    assert result.failed_tasks == 1


def test_resume_does_not_call_provider_for_succeeded_tasks():
    assert resumed_provider.calls == failed_and_pending_keys


@pytest.mark.parametrize(("limit_symbols", "limit_tasks"), [(1, None), (None, 2)])
def test_resume_rejects_new_run_limits(config_path, run_id, limit_symbols, limit_tasks):
    with pytest.raises(ETFBackfillPlanError, match="resume rejects"):
        backfill_etf_history_from_config(
            config_path,
            resume_run_id=run_id,
            limit_symbols=limit_symbols,
            limit_tasks=limit_tasks,
        )


def test_rerun_upserts_without_duplicate_rows():
    assert conn.execute("SELECT COUNT(*) FROM market_etf_daily_bars").fetchone()[0] == expected_unique_bars


def test_daily_success_with_factor_failure_is_not_ok():
    assert result.status == "partial"
    assert result.exit_code == 2


def test_empty_listed_chunk_is_persisted_and_blocks_ok():
    assert task.status == "empty"
    assert result.status == "partial"
```

Also assert deterministic sector/symbol/year/dataset ordering, retry count, request throttling through an injected sleeper/clock, and sanitized errors without token values.

- [ ] **Step 2: Run execution tests and verify RED**

```bash
./.venv/bin/python -m pytest -q tests/test_backfill_etf_history.py -k 'failure or resume or duplicate or factor or empty or throttle'
```

Expected: failures because the runner is not implemented.

- [ ] **Step 3: Implement the provider protocol and rate limiter**

Use an injectable protocol so tests do not require network access:

```python
class ETFHistoryProvider(Protocol):
    def daily(self, ts_code: str, start_date: date, end_date: date) -> pd.DataFrame:
        raise NotImplementedError

    def adj_factor(self, ts_code: str, start_date: date, end_date: date) -> pd.DataFrame:
        raise NotImplementedError


@dataclass(frozen=True)
class ETFBackfillResult:
    run_id: str
    status: str
    target_tasks: int
    succeeded_tasks: int
    empty_tasks: int
    failed_tasks: int
    inserted_rows: int
    db_path: Path

    @property
    def exit_code(self) -> int:
        return 0 if self.status == "ok" else 2


@dataclass(frozen=True)
class ETFBackfillDryRunResult:
    manifest: ETFUniverseManifest
    task_specs: tuple[ETFBackfillTaskSpec, ...]
    symbol_count: int
    chunk_count: int
    dataset_count: int
    provider_call_count: int
    effective_symbol_limit: int
    effective_task_limit: int
    symbol_headroom: int
    task_headroom: int


def build_etf_dry_run_result(
    manifest: ETFUniverseManifest,
    specs: list[ETFBackfillTaskSpec],
    *,
    symbol_cap: int,
    task_cap: int,
) -> ETFBackfillDryRunResult:
    symbol_count = len({member.symbol for member in manifest.members})
    chunk_count = len({
        (spec.sector, spec.symbol, spec.chunk_start, spec.chunk_end)
        for spec in specs
    })
    dataset_count = len({spec.dataset for spec in specs})
    return ETFBackfillDryRunResult(
        manifest=manifest,
        task_specs=tuple(specs),
        symbol_count=symbol_count,
        chunk_count=chunk_count,
        dataset_count=dataset_count,
        provider_call_count=len(specs),
        effective_symbol_limit=symbol_cap,
        effective_task_limit=task_cap,
        symbol_headroom=symbol_cap - symbol_count,
        task_headroom=task_cap - len(specs),
    )
```

Replace protocol method bodies with `raise NotImplementedError` rather than an ellipsis in executable source. Implement a monotonic-clock rate limiter that spaces requests by `60 / max_requests_per_minute`; inject `clock` and `sleep` in tests.

- [ ] **Step 4: Implement one-task/one-transaction execution**

Expose:

```python
def execute_etf_backfill_run(
    db_path: Path,
    run_id: str,
    *,
    provider: ETFHistoryProvider,
    max_requests_per_minute: int,
    max_retries: int,
    retry_backoff_seconds: float,
    stale_running_minutes: int,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
) -> ETFBackfillResult:
    """Execute persisted pending/failed tasks and return terminal run counts."""
```

Implement the body with the transaction sequence below; do not leave the docstring-only body in committed code.

For each selected task:

1. Mark `running` and increment `attempt_count` in a short transaction.
2. Throttle, call the exact dataset endpoint, and retry only transport/API errors classified as retryable.
3. Validate returned symbol and dates stay inside the task key.
4. In one transaction, UPSERT data and mark `succeeded`, or mark `empty` when the provider successfully returns no rows.
5. On final error, persist `failed` with a sanitized error and continue other tasks.
6. Refresh run counts after each task.
7. Finalize `ok` only when all target tasks are `succeeded`; otherwise use `partial` when any succeeded, else `failed`.

Use one SQLite writer. Do not add multiprocessing or parallel writes in MVP.

- [ ] **Step 5: Add the config-facing orchestration function**

Implement:

```python
def backfill_etf_history_from_config(
    config_path: Path,
    *,
    universe_name: str | None = None,
    sectors: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    dry_run: bool = False,
    resume_run_id: str | None = None,
    limit_symbols: int | None = None,
    limit_tasks: int | None = None,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
) -> ETFBackfillResult | ETFBackfillDryRunResult:
    """Resolve a dry-run, create a new persisted run, or resume an immutable run."""
```

Implement the body by loading `config.yaml`, resolving the dedicated path, constructing the provider adapter, and applying these mutually exclusive modes:

```python
if resume_run_id is not None:
    if any(
        value is not None
        for value in (universe_name, sectors, start_date, end_date, limit_symbols, limit_tasks)
    ) or dry_run:
        raise ETFBackfillPlanError("resume rejects universe, sector, dates, limits, and dry-run")
    with sqlite3.connect(db_path) as conn:
        manifest = validate_resume_contract(conn, resume_run_id, phase0_cfg=phase0_cfg)
    return execute_etf_backfill_run(db_path, resume_run_id, provider=provider, **runner_settings)

if universe_name is None or start_date is None or end_date is None:
    raise ETFBackfillPlanError("new run requires universe, start_date, and end_date")

with sqlite3.connect(db_path) as conn:
    manifest = resolve_etf_universe(
        conn,
        phase0_cfg=phase0_cfg,
        universe_name=universe_name,
        requested_sectors=sectors,
        start_date=date.fromisoformat(start_date),
        end_date=date.fromisoformat(end_date),
    )
    specs = plan_etf_task_specs(manifest)
    symbol_cap, task_cap = enforce_requested_limits(
        manifest,
        specs,
        configured=configured_limits,
        limit_symbols=limit_symbols,
        limit_tasks=limit_tasks,
    )
    if dry_run:
        return build_etf_dry_run_result(
            manifest,
            specs,
            symbol_cap=symbol_cap,
            task_cap=task_cap,
        )
    run_id = create_etf_backfill_run(conn, manifest, limits=configured_limits)
return execute_etf_backfill_run(db_path, run_id, provider=provider, **runner_settings)
```

The implementation may factor this sequence into private helpers, but the validation order and side-effect boundary must remain exact: validate selectors and limits before inserting a run or calling a history endpoint.

A dry-run returns `ETFBackfillDryRunResult`; the CLI only formats that object and never recomputes task counts or limits. It prints the selected sectors, symbols, annual chunks, two datasets, total task/provider-call count, and hard-limit headroom without inserting a run or calling history endpoints. A new run persists the manifest before tasks. A resume loads its persisted manifest and refuses current-config or persisted run/manifest drift. Resume-only accepts no universe, sector, date, dry-run, or limit arguments.

- [ ] **Step 6: Run the full backfill test file**

```bash
./.venv/bin/python -m pytest -q tests/test_backfill_etf_history.py
```

Expected: all tests pass; first-run partial/resume behavior is deterministic.

- [ ] **Step 7: Commit the runner**

```bash
git add phase0/data_governance/backfills/etf_history.py tests/test_backfill_etf_history.py
git commit -m "feat: execute resumable ETF history backfills"
```

## Task 7: Add A Strict Point-In-Time ETF History Reader

**Files:**
- Create: `phase0/data_access/etf_history.py`
- Create: `tests/test_etf_history_reader.py`

- [ ] **Step 1: Write failing raw and PIT reader tests**

Create tests for:

```python
def test_raw_reader_returns_unadjusted_exchange_prices():
    assert frame.loc[0, "close"] == 4.05
    assert frame.loc[0, "price_mode"] == "raw"


def test_qfq_asof_never_queries_or_uses_future_factor():
    assert queried_factor_end == date(2026, 1, 6)
    assert frame["date"].max().date() <= date(2026, 1, 6)


def test_qfq_asof_formula_uses_factor_at_or_before_asof():
    assert frame.loc[0, "close"] == pytest.approx(raw_close * bar_factor / asof_factor)


def test_missing_factor_for_an_actual_bar_fails_closed():
    with pytest.raises(ETFAdjustmentCoverageError, match="missing factor"):
        reader.load_qfq_asof("SH.510300", date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 6))


def test_no_factor_at_or_before_asof_fails_closed():
    with pytest.raises(ETFAdjustmentCoverageError, match="as-of factor"):
        reader.load_qfq_asof("SH.510300", date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 6))


def test_end_date_after_asof_is_truncated():
    assert frame["date"].max().date() == as_of_date
```

Build each test with an actual temporary SQLite database and reader instance. Include `510300.SH`, `512480.SH`, and `159915.SZ` normalization coverage.

- [ ] **Step 2: Run the reader tests and verify RED**

```bash
./.venv/bin/python -m pytest -q tests/test_etf_history_reader.py
```

Expected: missing module/contracts.

- [ ] **Step 3: Implement raw reads and fail-closed `qfq_asof`**

Create:

```python
class ETFAdjustmentCoverageError(RuntimeError):
    """Raw ETF bars cannot be adjusted without crossing the as-of boundary or imputing factors."""


@dataclass(frozen=True)
class ETFHistoryReader:
    db_path: Path

    def load_raw(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        normalized = normalize_etf_symbol(symbol)
        return _query_raw(self.db_path, normalized, start, end)

    def load_qfq_asof(self, symbol: str, start: date, end: date, as_of_date: date) -> pd.DataFrame:
        normalized = normalize_etf_symbol(symbol)
        effective_end = min(end, as_of_date)
        raw = _query_raw(self.db_path, normalized, start, effective_end)
        factors = _query_factors(self.db_path, normalized, start, as_of_date)
        return compute_etf_qfq_asof(raw, factors, as_of_date)
```

Import `normalize_etf_symbol` from `phase0.data_access.symbols`. Both raw and factor queries receive the same validated local symbol. Bare codes, unsupported exchanges, malformed suffixes, and any value that cannot round-trip are rejected before SQLite access.

Implement `compute_etf_qfq_asof` with exact-date factor coverage for every returned bar:

```python
def compute_etf_qfq_asof(raw: pd.DataFrame, factors: pd.DataFrame, as_of_date: date) -> pd.DataFrame:
    if raw.empty:
        return raw.assign(price_mode="qfq_asof")
    if factors.empty:
        raise ETFAdjustmentCoverageError("no as-of factor coverage")
    bars = raw.copy()
    fac = factors.copy()
    bars["date"] = pd.to_datetime(bars["date"])
    fac["date"] = pd.to_datetime(fac["date"])
    cutoff = pd.Timestamp(as_of_date)
    bars = bars[bars["date"] <= cutoff].copy()
    fac = fac[fac["date"] <= cutoff].copy()
    asof_rows = fac.sort_values("date")
    if asof_rows.empty:
        raise ETFAdjustmentCoverageError("no as-of factor at or before requested date")
    asof_factor = float(asof_rows.iloc[-1]["adj_factor"])
    if not pd.notna(asof_factor) or asof_factor <= 0:
        raise ETFAdjustmentCoverageError("invalid as-of factor")
    merged = bars.merge(fac[["date", "adj_factor"]], on="date", how="left", validate="one_to_one")
    missing = merged.loc[merged["adj_factor"].isna(), "date"]
    if not missing.empty:
        dates = ",".join(missing.dt.strftime("%Y-%m-%d").head(10))
        raise ETFAdjustmentCoverageError(f"missing factor for bar dates: {dates}")
    ratio = merged["adj_factor"].astype(float) / asof_factor
    for column in ("open", "high", "low", "close", "pre_close"):
        if column in merged.columns:
            merged[column] = pd.to_numeric(merged[column], errors="coerce") * ratio
    merged["price_mode"] = "qfq_asof"
    return merged.drop(columns=["adj_factor"])
```

Do not use `bfill`, `ffill`, factors after `as_of_date`, or persisted current-qfq bars.

- [ ] **Step 4: Run reader and existing adjustment regression tests**

```bash
./.venv/bin/python -m pytest -q tests/test_etf_history_reader.py tests/test_adjustment.py tests/test_local_history.py
```

Expected: ETF tests pass and the existing stock reader remains unchanged.

- [ ] **Step 5: Commit the PIT reader**

```bash
git add phase0/data_access/etf_history.py tests/test_etf_history_reader.py
git commit -m "feat: add PIT-safe ETF history reader"
```

## Task 8: Add Audit, CLI, Configuration Output, And Documentation

**Files:**
- Create: `phase0/data_governance/etf_audit.py`
- Modify: `phase0/cli_commands/data_update.py`
- Modify: `phase0/cli.py`
- Modify: `data/manual_history/README.md`
- Create: `tests/test_etf_audit.py`
- Modify: `tests/test_cli_data_update_commands.py`

- [ ] **Step 1: Write failing audit tests**

Create tests proving:

```python
def test_audit_pass_requires_all_tasks_succeeded_and_factor_coverage_for_bar_dates():
    assert report.status == "PASS"
    assert stored_audit_status == "pass"


def test_failed_or_empty_task_blocks_pass():
    assert report.status == "FAIL"
    assert stored_audit_status == "blocking"
    assert "empty listed chunk" in report.blocking_findings


def test_audit_error_is_distinct_from_blocking_data():
    assert report.status == "ERROR"
    assert stored_audit_status == "error"


def test_factor_coverage_uses_actual_bar_dates_not_calendar_dates():
    assert report.factor_missing_bar_dates == 0


def test_report_contains_manifest_and_task_identity():
    assert report.run_id in markdown
    assert report.config_digest in markdown
    assert report.catalog_snapshot_id in markdown
    assert "semiconductor" in markdown
    assert "SH.512480" in markdown
```

Use a temporary report directory and verify generated `.json` and `.md` paths.

- [ ] **Step 2: Implement the audit result and report writer**

Create:

```python
@dataclass(frozen=True)
class ETFAuditResult:
    status: str
    run_id: str
    universe_name: str
    config_digest: str
    catalog_snapshot_id: str
    target_tasks: int
    succeeded_tasks: int
    empty_tasks: int
    failed_tasks: int
    factor_missing_bar_dates: int
    blocking_findings: tuple[str, ...]
    json_path: Path
    markdown_path: Path


def audit_etf_history(db_path: Path, run_id: str, *, report_dir: Path) -> ETFAuditResult:
    """Evaluate blocking invariants and write deterministic JSON and Markdown reports."""
```

Implement the function body with the invariant queries below; do not commit a docstring-only implementation.

Audit invariants and persistence:

1. Run counts equal grouped task counts.
2. Every manifest member has both datasets for every planned chunk.
3. Every `daily` bar date has an exact factor date.
4. Duplicate logical keys are zero.
5. Any `failed` task blocks PASS.
6. Any `empty` task overlapping a manifest effective interval blocks PASS.
7. Provider tracking observations without effective dates are labeled non-PIT metadata.
8. JSON and Markdown include run ID, universe, sectors, symbols, dates, config digest, catalog snapshot, task counts, failed/empty keys, data ranges, and factor gaps.
9. In the same transaction as final audit persistence, update `etf_backfill_runs.audit_status` to `pass`, `blocking`, or `error` and set `audited_at`; never rewrite the task-level run `status`.

- [ ] **Step 3: Write failing CLI parser and handler tests**

Add assertions in `tests/test_cli_data_update_commands.py` for:

```text
sync-etf-catalog --config config.yaml
resolve-etf-universe --config config.yaml --universe sector_core_v1 --start-date 2018-01-01 --end-date 2026-08-11
backfill-etf-history --config config.yaml --universe sector_core_v1 --sector semiconductor --start-date 2018-01-01 --end-date 2026-08-11 --dry-run
backfill-etf-history --config config.yaml --resume-run-id <run-id>
audit-etf-history --config config.yaml --run-id <run-id>
```

Mock each orchestration function. Return a populated `ETFBackfillDryRunResult` for dry-run and assert the CLI prints its counts without recomputing them. Assert path resolution, exact forwarded arguments, concise console output, and exit code `2` for partial/failed/missing-token/permission-denied/stale-catalog outcomes. Add parser and direct-handler cases proving `--resume-run-id` rejects universe, sector, dates, dry-run, `--limit-symbols`, and `--limit-tasks`.

- [ ] **Step 4: Register and handle the four CLI commands**

Modify `DATA_UPDATE_COMMANDS`, `register_data_update_commands`, and `handle_data_update_command` in `phase0/cli_commands/data_update.py`. Required flags:

- `sync-etf-catalog`: `--config`.
- `resolve-etf-universe`: `--config`, `--universe`, repeatable `--sector`, `--start-date`, `--end-date`.
- `backfill-etf-history`: new-run flags above plus `--dry-run`, `--limit-symbols`, `--limit-tasks`; resume uses `--resume-run-id` and rejects every selector, date, dry-run, and limit argument.
- `audit-etf-history`: `--config`, `--run-id`.

Add the four names to the `Data Import & Update` group in `phase0/cli.py`. Never print tokens or raw request payloads.

- [ ] **Step 5: Document exact commands and data semantics**

Add an ETF section to `data/manual_history/README.md` containing:

```bash
./.venv/bin/python -m phase0.cli sync-etf-catalog --config config.yaml
./.venv/bin/python -m phase0.cli resolve-etf-universe --config config.yaml --universe sector_core_v1 --start-date 2018-01-01 --end-date 2026-08-11
./.venv/bin/python -m phase0.cli backfill-etf-history --config config.yaml --universe sector_core_v1 --sector semiconductor --start-date 2018-01-01 --end-date 2026-08-11 --dry-run
./.venv/bin/python -m phase0.cli backfill-etf-history --config config.yaml --universe sector_core_v1 --start-date 2018-01-01 --end-date 2026-08-11
./.venv/bin/python -m phase0.cli backfill-etf-history --config config.yaml --resume-run-id <run-id>
./.venv/bin/python -m phase0.cli audit-etf-history --config config.yaml --run-id <run-id>
```

Document full-catalog/lightweight versus configured-history/scoped behavior, the dedicated database, raw execution prices, `qfq_asof`, no future factors, non-PIT tracking observations, partial/nonzero exits, resume immutability, and local-only report/database policy.

- [ ] **Step 6: Run audit and CLI tests**

```bash
./.venv/bin/python -m pytest -q tests/test_etf_audit.py tests/test_cli_data_update_commands.py
```

Expected: all tests pass.

- [ ] **Step 7: Commit the user-facing capability**

```bash
git add phase0/data_governance/etf_audit.py phase0/cli_commands/data_update.py phase0/cli.py data/manual_history/README.md tests/test_etf_audit.py tests/test_cli_data_update_commands.py
git commit -m "feat: expose and audit ETF history workflows"
```

## Task 9: Prove End-To-End Safety And Prepare Integration

**Files:**
- Modify only if a defect is found: files owned by Tasks 1-8.
- Runtime-only: `data/etf_history.sqlite`, `reports/database_health/etf_history/*`, logs.

- [ ] **Step 1: Run all ETF-targeted tests**

```bash
./.venv/bin/python -m pytest -q \
  tests/test_tushare_etf_provider.py \
  tests/test_etf_store.py \
  tests/test_etf_catalog.py \
  tests/test_etf_universe.py \
  tests/test_backfill_etf_history.py \
  tests/test_etf_history_reader.py \
  tests/test_etf_audit.py \
  tests/test_cli_data_update_commands.py
```

Expected: all targeted tests pass.

- [ ] **Step 2: Run the full test suite**

```bash
./.venv/bin/python -m pytest -q
```

Expected: no new failures relative to Task 0. Record existing unrelated failures separately with exact names; do not hide them in the ETF result.

- [ ] **Step 3: Prove the three-symbol acquisition boundary with dry-run**

```bash
./.venv/bin/python -m phase0.cli sync-etf-catalog --config config.yaml
./.venv/bin/python -m phase0.cli resolve-etf-universe \
  --config config.yaml \
  --universe sector_core_v1 \
  --start-date 2025-01-01 \
  --end-date 2026-08-11
./.venv/bin/python -m phase0.cli backfill-etf-history \
  --config config.yaml \
  --universe sector_core_v1 \
  --start-date 2025-01-01 \
  --end-date 2026-08-11 \
  --dry-run
```

Expected: exactly three symbols, two sectors, and `3 symbols × 2 years × 2 datasets = 12` tasks, subject only to lifecycle clipping. No catalog ETF outside the configured three appears.

- [ ] **Step 4: Run a bounded live smoke only when Task 0 proved permissions**

```bash
./.venv/bin/python -m phase0.cli backfill-etf-history \
  --config config.yaml \
  --universe sector_core_v1 \
  --sector semiconductor \
  --start-date 2026-01-05 \
  --end-date 2026-01-09 \
  --limit-symbols 1 \
  --limit-tasks 2
```

Expected: exactly `SH.512480`, one daily task, one factor task, terminal task status `ok`, audit status still `not_run`, and exit code `0`. If live permissions were unavailable, skip this command and explicitly record that only mocked integration was verified.

- [ ] **Step 5: Audit the smoke run and inspect logical uniqueness**

```bash
./.venv/bin/python -m phase0.cli audit-etf-history --config config.yaml --run-id <run-id>
sqlite3 data/etf_history.sqlite "SELECT symbol,date,COUNT(*) FROM market_etf_daily_bars GROUP BY symbol,date HAVING COUNT(*)>1;"
sqlite3 data/etf_history.sqlite "SELECT symbol,date,COUNT(*) FROM market_etf_adj_factors GROUP BY symbol,date HAVING COUNT(*)>1;"
sqlite3 data/etf_history.sqlite "SELECT status,COUNT(*) FROM etf_backfill_tasks WHERE run_id='<run-id>' GROUP BY status;"
```

Expected: audit `PASS`; `etf_backfill_runs.status='ok'` and `audit_status='pass'`; both duplicate queries return no rows; all smoke tasks are `succeeded`.

- [ ] **Step 6: Re-run the proven failure/resume scenario**

Run the dedicated deterministic regression:

```bash
./.venv/bin/python -m pytest -q tests/test_backfill_etf_history.py::test_resume_does_not_call_provider_for_succeeded_tasks
```

Expected: first run partial, resume calls only failed/pending task keys, final rows remain unique.

- [ ] **Step 7: Inspect the final diff and local-asset boundary**

```bash
git status --short
git diff --check
git diff main...HEAD --stat
git ls-files 'data/*.sqlite' 'reports/database_health/etf_history/*' 'logs/*'
```

Expected: source/config/docs/tests only; no SQLite database, report, log, token, or downloaded payload is tracked.

- [ ] **Step 8: Perform a final code review before integration**

Review the recent ETF changes, related CLI call chain, tests, and config. Block integration for:

- any historical catalog-wide default;
- any use of stock universe/fundamental tables for ETF membership;
- any `bfill`/future factor use;
- any task success inferred from a date-level row;
- any resume that rebuilds membership from current config/catalog;
- any partial run returning exit code `0`;
- any token or provider payload written to logs/reports;
- any SQLite/report/log file staged for commit.

- [ ] **Step 9: Commit final integration fixes, if any**

```bash
git add phase0 config.yaml data/manual_history/README.md tests docs/superpowers/plans/2026-08-11-etf-data-capability.md
git commit -m "test: verify ETF data capability end to end"
```

If no tracked file changed after the previous commits, do not create an empty commit.

## Risks And Mitigations

| Risk | Trigger | Impact | Mitigation | Rollback |
| --- | --- | --- | --- | --- |
| Accidental full-market history | Missing/invalid universe falls back to catalog | Excess requests, unstable scope | No fallback; explicit symbols only; caps and dry-run | Stop run; delete dedicated run/tasks and local ETF DB if disposable |
| Survivor bias | Only listed ETFs synchronized | Historical research omits delisted funds | Require successful `L` and `D` catalog calls per snapshot | Mark snapshot failed; keep prior completed snapshot |
| Tracking mapping misrepresented as PIT | Current catalog index mapping used historically | Look-ahead metadata claims | Store `observed_at`, `is_point_in_time=0`; require explicit dated override for PIT claims | Remove dependent research result and rerun with dated mapping |
| Future factor leakage | Current-qfq persistence, `bfill`, or factor query past as-of | Invalid backtests | Raw-only bars; exact bar-date factors; query cutoff; fail closed | Disable adjusted reads and use raw until fixed |
| False completion | Any row/date treated as whole-symbol success | Silent gaps | Task key is run×sector×symbol×dataset×chunk; audit exact task/factor coverage | Resume failed/pending tasks only |
| Task completion mistaken for research admission | Backfill is `ok` before audit runs | Strategies consume incomplete factor coverage | Separate `status` from `audit_status`; require `ok` plus `pass` for strict research | Block readers/admission on missing audit PASS and rerun audit after repair |
| Resume drift | Config/catalog changes during interrupted run | Different membership under same run ID | Immutable manifest plus digest/snapshot/date validation | Start a new run ID |
| SQLite contention | Parallel writers | Locked database or partial state | Single writer, short transactions, annual chunks | Stop process; stale-running recovery after timeout |
| Tushare permission/transport failure | Token level or network changes | No usable catalog/history | Typed failures, nonzero exit, initial live probe | Preserve previous completed snapshot/data; retry later |
| Dirty-main contamination | Implementation in current checkout | Mixes unrelated uncommitted work | Dedicated worktree and branch | Remove isolated worktree/branch; original checkout remains unchanged |

## Acceptance Criteria

1. Full catalog sync is lightweight and includes successful active and delisted endpoint results; failed permissions cannot publish a partial snapshot.
2. Historical commands cannot run without an explicit configured universe or resume run ID; there is no `all`, wildcard, name inference, or catalog fallback.
3. Repeated `--sector` values select only those configured sectors. Omitting `--sector` selects all sectors inside the named universe, never the full catalog.
4. The sample universe resolves exactly `SH.510300`, `SZ.159915`, and `SH.512480`; catalog-only ETFs are excluded. A semiconductor-only dry-run resolves exactly `SH.512480`.
5. Dry-run prints selected sectors, symbols, annual chunks, dataset count, provider-call/task count, and hard-limit headroom without inserting a run or calling history endpoints.
6. Missing symbols, exchange mismatches, stale catalog, duplicate sector membership, and configured tracking-index mismatches fail closed; the default sample makes no unverified tracking assertion.
7. Requested dates are clipped to list/delist dates, and the manifest records requested/effective ranges, sectors, config digest, and catalog snapshot.
8. Catalog rows and tracking observations from different snapshots coexist and are always queried by the manifest's exact `catalog_snapshot_id`.
9. Tasks are keyed by `run_id × sector × symbol × dataset × date_chunk`; no date-level shortcut can mark a symbol complete.
10. A simulated task failure yields `partial` and exit `2`; resume calls only pending/failed tasks and creates no duplicate bars/factors.
11. Any daily or factor failure for a resolved symbol prevents `ok`.
12. Empty is a visible task result; an empty chunk inside the effective listed interval blocks audit PASS.
13. Factor coverage is measured against actual bar dates, not calendar dates.
14. `qfq_asof` never queries or uses a factor after `as_of_date`, truncates end dates to as-of, preserves raw prices, and raises on missing factors without `bfill`.
15. Raw and factor readers use the same strict ETF symbol normalizer; bare codes and unsupported exchanges fail before SQLite access.
16. Provider tracking observations without effective dates are labeled non-PIT metadata.
17. Audit reports include run, universe, sector, symbol, date range, digest, catalog snapshot, task states, failures, empty chunks, and factor gaps.
18. Backfill task completion and audit admission are separate: runner may set `status='ok'`, audit sets `audit_status`, and strict research requires `status='ok' AND audit_status='pass'`.
19. Targeted tests pass; the full suite has no new failures relative to baseline.
20. No database, report, log, provider payload, or secret is tracked by Git.

## Rollout And Rollback

- Rollout order: catalog sync → universe dry-run → one-symbol/five-day live smoke → audit → bounded sector backfill → longer requested range.
- Do not schedule the workflow in MVP. Establish manual reliability and request-budget evidence first.
- To stop safely, terminate between tasks; committed data and task states remain resumable.
- To abandon the capability before integration, remove the isolated worktree and branch. The dirty original `main` checkout is unaffected.
- To reset local runtime data after integration, archive or delete only `data/etf_history.sqlite` and its ETF report directory; never modify the stock history database.
