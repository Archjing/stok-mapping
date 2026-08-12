# Low-Churn Multifactor Strategy R&D Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and evaluate a fixed-weight, low-churn A-share multifactor candidate that combines PIT quality, earnings improvement, value, low volatility, and medium-term residual momentum without weakening the existing admission gate.

**Architecture:** Extract point-in-time valuation access and low-churn allocation into reusable modules, then add `sleeve_composite_low_churn_v2` as a new research-only strategy. Extend the existing factor-effectiveness diagnostic to evaluate the exact factor inputs before running full admission. Keep source/config changes on a code-integration worktree; run long research in a second clean research worktree that writes only ignored reports, logs, caches, and databases.

**Tech Stack:** Python 3.14 project runtime, pandas, NumPy, SQLite, PyYAML, pytest, existing `phase0` walk-forward/admission framework, Git worktrees.

---

## Scope And Decision Contract

This plan deliberately does not tune the 13 rejected candidates, add intraday signals, introduce machine learning, or promote any strategy to paper trading. It produces one new research-only candidate and the evidence needed to accept, revise, or stop it.

The implementation must preserve these boundaries:

- `main` receives reusable code, global configuration, tests, and strategy documentation only.
- The research branch receives reports/logs/cache artifacts only; it must not modify `phase0/`, `scripts/`, `tests/`, or `config.yaml`.
- `sleeve_composite_low_churn_v1` remains behaviorally unchanged and is the benchmark.
- `sleeve_composite_low_churn_v2` is not added to `baseline_admission_all_v1`, `compare_strategies`, simulated accounts, Daily Brief, or watchlists.
- `supports_paper_trade` and `supports_brief` remain `False` until a separate promotion change is reviewed after admission.
- The strategy uses only information visible by signal date. Forward returns may appear only inside diagnostics as labels and must never be merged back into a strategy signal frame.

Recommended engineering effort: 4-5 engineer days plus long-running research. The critical path is PIT factor plumbing, v1-preserving allocator extraction, and two-window admission.

## File Map

| File | Responsibility |
| --- | --- |
| `phase0/data_access/daily_basic_history.py` | Read exact-date PIT valuation and market-cap fields from local SQLite and merge them into panels. |
| `phase0/research/factors/__init__.py` | Export shared slow-factor feature APIs. |
| `phase0/research/factors/slow_multifactor.py` | Compute five raw factors, industry/size-neutral ranks, factor availability, and fixed-weight composite scores. |
| `phase0/research/diagnostics/factor_effectiveness.py` | Reuse the shared features in the existing IC/group-return diagnostic. |
| `phase0/strategies/low_churn_allocator.py` | Own the rebalance schedule, buy/hold rank buffer, minimum holding period, industry slots, delayed weights, and costs. |
| `phase0/strategies/sleeve_composite.py` | Delegate v1 low-churn allocation to the shared allocator without changing v1 scores or outputs. |
| `phase0/strategies/sleeve_composite_low_churn_v2.py` | Define the new fixed-weight strategy and its signal metadata. |
| `phase0/strategies/__init__.py` | Register the v2 strategy. |
| `phase0/research/admission/strategy_scope.py` | Allow scoped admission to enable the v2 config switch. |
| `phase0/research/admission/runner.py` | Apply and record explicit cost multipliers for sensitivity runs. |
| `phase0/research/admission/reports.py` | Include cost multiplier in the reproducible command hint. |
| `phase0/cli_commands/strategy_research.py` | Expose `--cost-multiplier` on `strategy-admission`. |
| `phase0/walk_forward.py` | Include v2 in financial diagnostics without changing existing strategy logic. |
| `config.yaml` | Add a disabled v2 config block and a research-only strategy set. |
| `docs/strategy_explanations/sleeve_composite_low_churn_v2.md` | Explain signals, execution, limitations, and promotion boundary. |
| `docs/strategy_explanations/INDEX.md` | Link the new explanation. |

### Task 1: Extract PIT Daily-Basic Access

**Files:**
- Create: `phase0/data_access/daily_basic_history.py`
- Create: `tests/test_daily_basic_history.py`
- Modify: `phase0/research/diagnostics/factor_effectiveness.py:73-152`

- [ ] **Step 1: Write failing exact-date and as-of tests**

Create `tests/test_daily_basic_history.py` with a temporary SQLite table containing rows on 2024-01-02, 2024-01-03, and 2024-02-01. Configure local history to that database and assert that an end date/as-of date of 2024-01-03 never returns or merges the February row.

```python
from __future__ import annotations

import sqlite3

import pandas as pd

from phase0.data_access.daily_basic_history import (
    load_daily_basic_factor_frame,
    merge_point_in_time_daily_basic,
)
from phase0.data_access.local_history import configure_local_history


def _configure_db(tmp_path):
    db_path = tmp_path / "history.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE market_daily_basic (
                market TEXT, symbol TEXT, date TEXT, market_cap REAL,
                circ_mv REAL, pe_ratio REAL, pb_ratio REAL, turnover_rate REAL
            )
            """
        )
        conn.executemany(
            "INSERT INTO market_daily_basic VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("CN", "AAA", "2024-01-02", 100.0, 80.0, 10.0, 1.0, 0.5),
                ("CN", "AAA", "2024-01-03", 110.0, 90.0, 11.0, 1.1, 0.6),
                ("CN", "AAA", "2024-02-01", 999.0, 999.0, 99.0, 9.9, 9.9),
            ],
        )
    configure_local_history(
        {
            "enabled": True,
            "path": str(db_path),
            "market": "CN",
            "daily_basic_table": "market_daily_basic",
        }
    )
    return db_path


def test_daily_basic_loader_honors_end_and_asof_dates(tmp_path) -> None:
    _configure_db(tmp_path)

    result = load_daily_basic_factor_frame(
        symbols=["AAA"],
        start_date="2024-01-01",
        end_date="2024-01-31",
        as_of_date="2024-01-03",
    )

    assert result["date"].max() == pd.Timestamp("2024-01-03")
    assert result.iloc[-1]["market_cap"] == 110.0
    assert 999.0 not in result["market_cap"].tolist()


def test_daily_basic_merge_is_exact_date_and_preserves_missingness(tmp_path) -> None:
    _configure_db(tmp_path)
    panel = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
            "symbol": ["AAA", "AAA", "AAA"],
            "close": [10.0, 10.1, 10.2],
        }
    )

    result = merge_point_in_time_daily_basic(panel, as_of_date="2024-01-04")

    assert result.loc[result["date"] == pd.Timestamp("2024-01-02"), "pe_ttm"].iloc[0] == 10.0
    assert result.loc[result["date"] == pd.Timestamp("2024-01-03"), "pb"].iloc[0] == 1.1
    assert pd.isna(result.loc[result["date"] == pd.Timestamp("2024-01-04"), "market_cap"].iloc[0])
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
/Users/aj/workspace/stok-mapping/.venv/bin/python -m pytest -q tests/test_daily_basic_history.py
```

Expected: collection fails with `ModuleNotFoundError: phase0.data_access.daily_basic_history`.

- [ ] **Step 3: Implement the reusable loader and exact-date merge**

Create `phase0/data_access/daily_basic_history.py`. Use parameter binding for values, `_safe_identifier` for the configured table, and `min(end_date, as_of_date)` as the upper bound. Normalize output names to `market_cap`, `circ_mv`, `pe_ttm`, `pb`, and `turnover_rate`.

```python
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Iterable

import numpy as np
import pandas as pd

from phase0.data_access.local_history import _safe_identifier, local_history_path


def load_daily_basic_factor_frame(
    *,
    symbols: Iterable[str],
    start_date: date | str | pd.Timestamp,
    end_date: date | str | pd.Timestamp,
    as_of_date: date | str | pd.Timestamp | None = None,
    market: str = "CN",
    table: str = "market_daily_basic",
) -> pd.DataFrame:
    names = sorted({str(item) for item in symbols if str(item)})
    if not names:
        return pd.DataFrame()
    start = pd.Timestamp(start_date).date()
    end = pd.Timestamp(end_date).date()
    if as_of_date is not None:
        end = min(end, pd.Timestamp(as_of_date).date())
    if end < start:
        return pd.DataFrame()
    db_path = local_history_path()
    if not db_path.exists():
        return pd.DataFrame()
    safe_table = _safe_identifier(table)
    placeholders = ",".join("?" for _ in names)
    query = f"""
        SELECT symbol, date, market_cap, circ_mv, pe_ratio, pb_ratio, turnover_rate
        FROM {safe_table}
        WHERE market = ?
          AND symbol IN ({placeholders})
          AND date >= ?
          AND date <= ?
        ORDER BY date, symbol
    """
    params = [market, *names, start.isoformat(), end.isoformat()]
    try:
        with sqlite3.connect(db_path) as conn:
            out = pd.read_sql_query(query, conn, params=params)
    except (sqlite3.Error, ValueError):
        return pd.DataFrame()
    if out.empty:
        return out
    out["symbol"] = out["symbol"].astype(str)
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out = out.rename(columns={"pe_ratio": "pe_ttm", "pb_ratio": "pb"})
    for column in ["market_cap", "circ_mv", "pe_ttm", "pb", "turnover_rate"]:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    return out.dropna(subset=["symbol", "date"]).drop_duplicates(["date", "symbol"], keep="last")


def merge_point_in_time_daily_basic(
    panel: pd.DataFrame,
    *,
    as_of_date: date | str | pd.Timestamp | None = None,
    market: str = "CN",
    table: str = "market_daily_basic",
) -> pd.DataFrame:
    if panel.empty:
        return panel
    out = panel.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out["symbol"] = out["symbol"].astype(str)
    basics = load_daily_basic_factor_frame(
        symbols=out["symbol"].dropna().unique(),
        start_date=out["date"].min(),
        end_date=out["date"].max(),
        as_of_date=as_of_date,
        market=market,
        table=table,
    )
    value_columns = ["market_cap", "circ_mv", "pe_ttm", "pb", "turnover_rate"]
    if basics.empty:
        for column in value_columns:
            if column not in out.columns:
                out[column] = np.nan
        return out
    renamed = basics.rename(columns={column: f"__daily_basic_{column}" for column in value_columns})
    out = out.merge(renamed, on=["date", "symbol"], how="left")
    for column in value_columns:
        source = f"__daily_basic_{column}"
        current = (
            pd.to_numeric(out[column], errors="coerce")
            if column in out.columns
            else pd.Series(np.nan, index=out.index, dtype=float)
        )
        out[column] = current.combine_first(pd.to_numeric(out[source], errors="coerce"))
    return out.drop(columns=[f"__daily_basic_{column}" for column in value_columns])
```

- [ ] **Step 4: Make factor-effectiveness use the shared implementation**

Replace the local `_daily_basic_frame` and `_merge_daily_basic` implementations with:

```python
from phase0.data_access.daily_basic_history import merge_point_in_time_daily_basic


def _merge_daily_basic(panel: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    local_cfg = config.get("local_history", {})
    return merge_point_in_time_daily_basic(
        panel,
        as_of_date=panel["date"].max() if not panel.empty else None,
        market=str(local_cfg.get("market", "CN")),
        table=str(local_cfg.get("daily_basic_table", "market_daily_basic")),
    )
```

- [ ] **Step 5: Run focused tests and commit**

Run:

```bash
/Users/aj/workspace/stok-mapping/.venv/bin/python -m pytest -q tests/test_daily_basic_history.py tests/test_cli_strategy_research_commands.py
git diff --check
git add phase0/data_access/daily_basic_history.py phase0/research/diagnostics/factor_effectiveness.py tests/test_daily_basic_history.py
git commit -m "refactor: share point-in-time daily basic factors"
```

Expected: focused tests pass and the commit contains no report, log, cache, or database files.

### Task 2: Add Shared Slow Multifactor Features

**Files:**
- Create: `phase0/research/factors/__init__.py`
- Create: `phase0/research/factors/slow_multifactor.py`
- Create: `tests/test_slow_multifactor_features.py`

- [ ] **Step 1: Write failing factor-direction, neutrality, and no-lookahead tests**

Create a deterministic panel with at least six symbols, two industries, 140 dates, PIT financial component columns, `market_cap`, `pe_ttm`, `pb`, `vol60`, and `close`. Assert:

```python
from __future__ import annotations

import numpy as np
import pandas as pd

from phase0.research.factors.slow_multifactor import add_slow_multifactor_features


def _panel() -> pd.DataFrame:
    dates = pd.bdate_range("2023-01-02", periods=140)
    definitions = [
        ("QUALITY", "A", 100.0, 12.0, 1.2, 0.10, 0.0010, 0.95, 0.85),
        ("WEAK", "A", 120.0, 20.0, 2.0, 0.20, 0.0002, 0.20, 0.25),
        ("VALUE", "A", 90.0, 8.0, 0.8, 0.16, 0.0007, 0.65, 0.60),
        ("EXPENSIVE", "B", 300.0, 40.0, 5.0, 0.18, 0.0003, 0.55, 0.50),
        ("LOWVOL", "B", 220.0, 15.0, 1.5, 0.08, 0.0005, 0.60, 0.55),
        ("HIGHVOL", "B", 180.0, 18.0, 1.8, 0.35, -0.0002, 0.45, 0.40),
    ]
    rows = []
    for symbol, industry, market_cap, pe, pb, vol, drift, quality, earnings in definitions:
        for index, signal_date in enumerate(dates):
            rows.append(
                {
                    "date": signal_date,
                    "symbol": symbol,
                    "industry": industry,
                    "close": 10.0 * (1.0 + drift) ** index,
                    "market_cap": market_cap,
                    "pe_ttm": pe,
                    "pb": pb,
                    "vol60": vol,
                    "quality_roe_component": quality,
                    "quality_cash_flow_component": quality,
                    "quality_low_debt_component": quality,
                    "quality_profit_growth_component": earnings,
                    "quality_revenue_growth_component": earnings,
                }
            )
    return pd.DataFrame(rows)


def test_slow_factor_directions_and_required_coverage() -> None:
    result = add_slow_multifactor_features(_panel())
    last = result[result["date"] == result["date"].max()].set_index("symbol")
    assert last.loc["QUALITY", "slow_quality_raw"] > last.loc["WEAK", "slow_quality_raw"]
    assert last.loc["VALUE", "slow_value_raw"] > last.loc["EXPENSIVE", "slow_value_raw"]
    assert last.loc["LOWVOL", "slow_low_vol_raw"] > last.loc["HIGHVOL", "slow_low_vol_raw"]
    assert last["slow_factor_available_count"].min() >= 4


def test_slow_features_do_not_change_before_mutated_future_rows() -> None:
    panel = _panel()
    cutoff = panel["date"].sort_values().unique()[-20]
    baseline = add_slow_multifactor_features(panel)
    mutated = panel.copy()
    mutated.loc[mutated["date"] > cutoff, "close"] *= 10.0
    changed = add_slow_multifactor_features(mutated)
    columns = ["date", "symbol", "slow_residual_momentum", "slow_composite_score"]
    pd.testing.assert_frame_equal(
        baseline.loc[baseline["date"] <= cutoff, columns].reset_index(drop=True),
        changed.loc[changed["date"] <= cutoff, columns].reset_index(drop=True),
    )


def test_neutralized_scores_remove_daily_industry_mean_and_size_slope() -> None:
    result = add_slow_multifactor_features(_panel())
    last = result[result["date"] == result["date"].max()].dropna(subset=["slow_value_score"])
    industry_means = last.groupby("industry")["slow_value_neutral"].mean().abs()
    log_size = np.log(last["market_cap"])
    assert float(industry_means.max()) < 1e-10
    assert abs(float(last["slow_value_neutral"].corr(log_size))) < 1e-10
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
/Users/aj/workspace/stok-mapping/.venv/bin/python -m pytest -q tests/test_slow_multifactor_features.py
```

Expected: collection fails because `phase0.research.factors.slow_multifactor` does not exist.

- [ ] **Step 3: Implement deterministic PIT-safe features**

Implement `phase0/research/factors/slow_multifactor.py` with these public APIs:

```python
from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd


DEFAULT_WEIGHTS = {
    "slow_quality_score": 0.30,
    "slow_value_score": 0.20,
    "slow_low_vol_score": 0.20,
    "slow_earnings_score": 0.15,
    "slow_residual_momentum_score": 0.15,
}


def _mean_available(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    available = [column for column in columns if column in frame.columns]
    if not available:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return frame[available].apply(pd.to_numeric, errors="coerce").mean(axis=1)


def _neutralize_one_day(day: pd.DataFrame, raw_column: str) -> pd.Series:
    raw = pd.to_numeric(day[raw_column], errors="coerce")
    industry = day["industry"].fillna("").astype(str)
    centered = raw - raw.groupby(industry).transform("mean")
    size = np.log(pd.to_numeric(day["market_cap"], errors="coerce").where(lambda value: value > 0))
    size_centered = size - size.groupby(industry).transform("mean")
    valid = centered.notna() & size_centered.notna()
    residual = pd.Series(np.nan, index=day.index, dtype=float)
    if valid.sum() >= 3 and float(size_centered[valid].var()) > 0:
        x = size_centered[valid]
        beta = float(centered[valid].cov(x) / x.var())
        residual.loc[valid] = centered[valid] - beta * x
    else:
        residual.loc[centered.notna()] = centered.loc[centered.notna()]
    return residual


def _neutralized_rank(frame: pd.DataFrame, raw_column: str, output_prefix: str) -> pd.DataFrame:
    neutral_parts = []
    for _, day in frame.groupby("date", sort=True):
        neutral = _neutralize_one_day(day, raw_column)
        neutral_parts.append(pd.DataFrame({"index": day.index, "neutral": neutral.values}))
    neutral_frame = pd.concat(neutral_parts, ignore_index=True).set_index("index")
    frame[f"{output_prefix}_neutral"] = neutral_frame["neutral"].reindex(frame.index)
    frame[f"{output_prefix}_score"] = frame.groupby("date")[f"{output_prefix}_neutral"].rank(
        method="average", pct=True
    )
    return frame


def add_slow_multifactor_features(
    panel: pd.DataFrame,
    *,
    weights: Mapping[str, float] | None = None,
    min_available_factors: int = 4,
) -> pd.DataFrame:
    if panel.empty:
        return panel
    out = panel.copy().sort_values(["symbol", "date"]).reset_index(drop=True)
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out["symbol"] = out["symbol"].astype(str)
    if "industry" not in out.columns:
        out["industry"] = ""
    for column in ["close", "market_cap", "pe_ttm", "pb", "vol60"]:
        out[column] = pd.to_numeric(out.get(column, np.nan), errors="coerce")

    out["slow_quality_raw"] = _mean_available(
        out,
        ["quality_roe_component", "quality_cash_flow_component", "quality_low_debt_component"],
    )
    out["slow_earnings_raw"] = _mean_available(
        out,
        ["quality_profit_growth_component", "quality_revenue_growth_component"],
    )
    ep = (1.0 / out["pe_ttm"].where(out["pe_ttm"] > 0)).replace([np.inf, -np.inf], np.nan)
    inverse_pb = (1.0 / out["pb"].where(out["pb"] > 0)).replace([np.inf, -np.inf], np.nan)
    out["slow_value_raw"] = pd.concat([ep, inverse_pb], axis=1).mean(axis=1)
    out["slow_low_vol_raw"] = -out["vol60"]
    close = out["close"]
    close_20 = close.groupby(out["symbol"]).shift(20)
    close_120 = close.groupby(out["symbol"]).shift(120)
    out["slow_residual_momentum_raw"] = close_20 / close_120.replace(0, np.nan) - 1.0

    for prefix in ["slow_quality", "slow_earnings", "slow_value", "slow_low_vol", "slow_residual_momentum"]:
        out = _neutralized_rank(out, f"{prefix}_raw", prefix)

    configured = dict(DEFAULT_WEIGHTS if weights is None else weights)
    positive = {key: max(0.0, float(value)) for key, value in configured.items()}
    total = sum(positive.values())
    if total <= 0:
        raise ValueError("slow multifactor weights must contain a positive value")
    normalized = {key: value / total for key, value in positive.items()}
    score_columns = list(normalized)
    available = out[score_columns].notna()
    out["slow_factor_available_count"] = available.sum(axis=1)
    weighted = sum(out[column].fillna(0.0) * weight for column, weight in normalized.items())
    available_weight = sum(available[column].astype(float) * weight for column, weight in normalized.items())
    composite = weighted / available_weight.replace(0, np.nan)
    required = out["slow_quality_score"].notna() & out["slow_earnings_score"].notna()
    out["slow_composite_score"] = composite.where(
        required & (out["slow_factor_available_count"] >= int(min_available_factors))
    )
    return out
```

Export `DEFAULT_WEIGHTS` and `add_slow_multifactor_features` from `phase0/research/factors/__init__.py`.

- [ ] **Step 4: Run focused tests and commit**

Run:

```bash
/Users/aj/workspace/stok-mapping/.venv/bin/python -m pytest -q tests/test_slow_multifactor_features.py
git diff --check
git add phase0/research/factors tests/test_slow_multifactor_features.py
git commit -m "feat: add neutral slow multifactor features"
```

Expected: direction, neutrality, missing-data, and no-lookahead tests pass.

### Task 3: Extend Factor-Effectiveness Diagnostics

**Files:**
- Modify: `phase0/research/diagnostics/factor_effectiveness.py:43-59,155-179`
- Create: `tests/test_factor_effectiveness_slow_factors.py`

- [ ] **Step 1: Write failing diagnostic integration tests**

Add tests that assert the five slow factors are registered and that `_add_factor_columns` produces them without changing the existing 15 factor specifications.

```python
import pandas as pd
import pytest

from phase0.research.diagnostics.factor_effectiveness import FACTOR_SPECS, _add_factor_columns


@pytest.fixture
def sample_factor_panel() -> pd.DataFrame:
    rows = []
    for symbol_index, symbol in enumerate(["AAA", "BBB", "CCC"]):
        for date_index, signal_date in enumerate(pd.bdate_range("2023-01-02", periods=125)):
            score = 0.3 + symbol_index * 0.2
            rows.append(
                {
                    "date": signal_date,
                    "symbol": symbol,
                    "industry": "A" if symbol != "CCC" else "B",
                    "close": 10.0 * (1.0005 + symbol_index * 0.0001) ** date_index,
                    "ret": 0.0005 + symbol_index * 0.0001,
                    "vol20": 0.10 + symbol_index * 0.02,
                    "vol60": 0.12 + symbol_index * 0.02,
                    "amount_ratio20": 1.0,
                    "turnover_rate": 0.5,
                    "market_cap": 100.0 + symbol_index * 50.0,
                    "pe_ttm": 10.0 + symbol_index,
                    "pb": 1.0 + symbol_index * 0.1,
                    "quality_roe_component": score,
                    "quality_cash_flow_component": score,
                    "quality_low_debt_component": score,
                    "quality_profit_growth_component": score,
                    "quality_revenue_growth_component": score,
                }
            )
    return pd.DataFrame(rows)


def test_factor_diagnostic_registers_slow_multifactor_inputs() -> None:
    names = {factor.name for factor in FACTOR_SPECS}
    assert {
        "slow_quality",
        "slow_earnings",
        "slow_value",
        "slow_low_vol",
        "slow_residual_momentum",
    }.issubset(names)


def test_factor_diagnostic_builds_slow_features(sample_factor_panel) -> None:
    result = _add_factor_columns(sample_factor_panel)
    for column in [
        "slow_quality_score",
        "slow_earnings_score",
        "slow_value_score",
        "slow_low_vol_score",
        "slow_residual_momentum_score",
    ]:
        assert column in result.columns
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
/Users/aj/workspace/stok-mapping/.venv/bin/python -m pytest -q tests/test_factor_effectiveness_slow_factors.py
```

Expected: assertions fail because the five factor specs are absent.

- [ ] **Step 3: Add the shared feature call and factor specs**

Import `add_slow_multifactor_features`, call it at the end of `_add_factor_columns`, and append these exact specifications:

```python
FactorSpec("slow_quality", "slow_quality_score", "PIT quality neutralized by industry and size"),
FactorSpec("slow_earnings", "slow_earnings_score", "PIT earnings improvement neutralized by industry and size"),
FactorSpec("slow_value", "slow_value_score", "positive E/P and inverse P/B neutralized by industry and size"),
FactorSpec("slow_low_vol", "slow_low_vol_score", "60-day low volatility neutralized by industry and size"),
FactorSpec(
    "slow_residual_momentum",
    "slow_residual_momentum_score",
    "120-to-20-day momentum neutralized by industry and size",
),
```

The diagnostic keeps `forward_ret_20d` only as an evaluation label. Do not include that column in any strategy output API.

- [ ] **Step 4: Run focused diagnostic tests and commit**

Run:

```bash
/Users/aj/workspace/stok-mapping/.venv/bin/python -m pytest -q tests/test_factor_effectiveness_slow_factors.py tests/test_cli_strategy_research_commands.py
git diff --check
git add phase0/research/diagnostics/factor_effectiveness.py tests/test_factor_effectiveness_slow_factors.py
git commit -m "feat: diagnose slow multifactor inputs"
```

Expected: tests pass and the existing factor report contract remains backward compatible.

### Task 4: Extract The Low-Churn Allocator Without Changing V1

**Files:**
- Create: `phase0/strategies/low_churn_allocator.py`
- Modify: `phase0/strategies/sleeve_composite.py:327-461,478-540`
- Create: `tests/test_low_churn_allocator.py`
- Modify: `tests/test_sleeve_composite_strategy.py:216-266`

- [ ] **Step 1: Add v1 characterization tests before refactoring**

Extend the existing tests to snapshot selected symbols, `weight_unshifted`, shifted `weight`, `held_days`, `review_reason`, returns, and turnover under non-zero costs. Add a test proving an incumbent remains held inside `hold_top_n` and a test proving it exits only after both `min_hold_days` and the rebalance boundary are satisfied.

```python
def test_low_churn_v1_characterization_with_costs() -> None:
    output = SleeveCompositeLowChurnStrategy().apply(
        _sample_panel(),
        {
            "defensive_quality_weight": 1.0,
            "low_turnover_momentum_weight": 0.0,
            "risk_overlay_weight": 0.0,
            "momentum_window": 20,
            "buy_top_n": 1,
            "hold_top_n": 2,
            "rebalance_days": 3,
            "min_hold_days": 3,
            "max_symbol_weight": 0.10,
            "max_names_per_industry": 1,
        },
        slippage=0.001,
        commission=0.00025,
        stamp_duty_sell=0.0005,
    )
    signal = output.signal_frame.sort_values(["date", "symbol"]).reset_index(drop=True)
    assert signal.loc[signal["date"] == pd.Timestamp("2024-01-02"), "review_reason"].eq("fixed_rebalance").all()
    assert signal.loc[signal["date"] == pd.Timestamp("2024-01-03"), "review_reason"].eq("").all()
    assert output.returns.index.tolist() == sorted(output.returns.index.tolist())
    assert output.returns.notna().all()
```

Create `tests/test_low_churn_allocator.py` with direct state-machine tests:

```python
from __future__ import annotations

import pandas as pd
import pytest

from phase0.strategies.low_churn_allocator import allocate_low_churn


def _scored_panel() -> pd.DataFrame:
    rows = []
    dates = pd.bdate_range("2024-01-02", periods=4)
    scores = {
        dates[0]: {"AAA": 0.9, "BBB": 0.8, "CCC": 0.7},
        dates[1]: {"AAA": 0.6, "BBB": 0.9, "CCC": 0.7},
        dates[2]: {"AAA": 0.5, "BBB": 0.9, "CCC": 0.8},
        dates[3]: {"AAA": 0.5, "BBB": 0.9, "CCC": 0.8},
    }
    for signal_date in dates:
        for symbol, score in scores[signal_date].items():
            rows.append(
                {
                    "date": signal_date,
                    "symbol": symbol,
                    "industry": "A" if symbol != "CCC" else "B",
                    "final_score": score,
                    "score": score,
                    "risk_overlay_scale": 1.0,
                    "ret": 0.0,
                }
            )
    return pd.DataFrame(rows)


def _params() -> dict[str, object]:
    return {
        "buy_top_n": 1,
        "hold_top_n": 1,
        "rebalance_days": 2,
        "min_hold_days": 2,
        "max_symbol_weight": 0.5,
        "max_names_per_industry": 1,
    }


def _allocate(panel: pd.DataFrame, *, slippage: float = 0.0, commission: float = 0.0):
    return allocate_low_churn(
        panel,
        params=_params(),
        slippage=slippage,
        commission=commission,
        stamp_duty_sell=0.0,
        signal_columns=[
            "date", "symbol", "industry", "score", "rank", "selected",
            "weight_unshifted", "weight", "held_days", "review_reason", "ret", "position_ret",
        ],
        metadata={"strategy_id": "test"},
    )


def test_allocator_waits_for_rebalance_and_minimum_hold_before_exit() -> None:
    output = _allocate(_scored_panel())
    targets = output.signal_frame.pivot(index="date", columns="symbol", values="weight_unshifted")
    assert targets.loc[pd.Timestamp("2024-01-02"), "AAA"] == 0.5
    assert targets.loc[pd.Timestamp("2024-01-03"), "AAA"] == 0.5
    assert targets.loc[pd.Timestamp("2024-01-04"), "AAA"] == 0.0
    assert targets.loc[pd.Timestamp("2024-01-04"), "BBB"] == 0.5


def test_allocator_charges_entry_cost_on_shifted_live_weight() -> None:
    output = _allocate(_scored_panel(), slippage=0.001, commission=0.00025)
    assert output.returns.loc[pd.Timestamp("2024-01-03")] == pytest.approx(-0.000625)
```

- [ ] **Step 2: Run v1 characterization tests and verify GREEN before refactoring**

Run:

```bash
/Users/aj/workspace/stok-mapping/.venv/bin/python -m pytest -q tests/test_sleeve_composite_strategy.py
```

Expected: all old and new v1 tests pass before moving code.

- [ ] **Step 3: Extract one allocator API**

Move the state machine currently in `SleeveCompositeLowChurnStrategy.apply` into `allocate_low_churn`. Keep ordering, rank method, rebalance indexing, holding-day increments, next-day shift, and cost equations byte-for-byte equivalent.

```python
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

from phase0.strategies.base import StrategyOutput


def optional_positive_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _clean_industry(value: Any) -> str:
    industry = str(value).strip()
    return industry if industry and industry.lower() != "nan" else "UNKNOWN"


def _industry_slot_available(
    *,
    symbol: str,
    day: pd.DataFrame,
    current_weights: dict[str, float],
    max_names_per_industry: int | None,
) -> bool:
    if max_names_per_industry is None or "industry" not in day.columns:
        return True
    indexed = day.set_index(day["symbol"].astype(str))
    if symbol not in indexed.index:
        return True
    industry = _clean_industry(indexed.loc[symbol, "industry"])
    active_symbols = [active for active in current_weights if active in indexed.index]
    same_industry_count = sum(
        _clean_industry(indexed.loc[active, "industry"]) == industry
        for active in active_symbols
    )
    return same_industry_count < max_names_per_industry


def allocate_low_churn(
    scored_panel: pd.DataFrame,
    *,
    params: dict[str, Any],
    slippage: float,
    commission: float,
    stamp_duty_sell: float,
    signal_columns: Sequence[str],
    metadata: dict[str, Any],
) -> StrategyOutput:
    required = {"date", "symbol", "final_score", "risk_overlay_scale", "ret"}
    if scored_panel.empty or not required.issubset(scored_panel.columns):
        dates = pd.Index(sorted(scored_panel.get("date", pd.Series(dtype=object)).dropna().unique()))
        empty = pd.Series(0.0, index=dates)
        return StrategyOutput(empty, empty, pd.DataFrame(), metadata)

    out = scored_panel.copy().sort_values(["date", "symbol"]).reset_index(drop=True)
    out["rank"] = out.groupby("date")["final_score"].rank(method="first", ascending=False)
    out["rank_score"] = out["final_score"].where(out["final_score"].notna(), np.nan)
    buy_top_n = max(1, int(params.get("buy_top_n", params.get("top_n", 10))))
    hold_top_n = max(buy_top_n, int(params.get("hold_top_n", buy_top_n * 2)))
    rebalance_days = max(1, int(params.get("rebalance_days", 20)))
    min_hold_days = max(0, int(params.get("min_hold_days", 20)))
    max_symbol_weight = max(0.0, float(params.get("max_symbol_weight", 0.10)))
    max_names_per_industry = optional_positive_int(params.get("max_names_per_industry"))

    current_weights: dict[str, float] = {}
    held_days: dict[str, int] = {}
    frames: list[pd.DataFrame] = []
    for index, (_, day) in enumerate(out.groupby("date", sort=True)):
        day = day.copy()
        review_reason = ""
        if index % rebalance_days == 0:
            review_reason = "fixed_rebalance"
            indexed = day.set_index(day["symbol"].astype(str))
            for symbol in list(current_weights):
                if symbol not in indexed.index:
                    rank = np.nan
                    score = np.nan
                else:
                    row = indexed.loc[symbol]
                    rank = row["rank"]
                    score = row["rank_score"]
                old_enough = held_days.get(symbol, 0) >= min_hold_days
                outside_hold_band = pd.isna(rank) or float(rank) > hold_top_n or pd.isna(score)
                if old_enough and outside_hold_band:
                    current_weights.pop(symbol, None)
                    held_days.pop(symbol, None)

            candidates = day[day["rank_score"].notna()].sort_values(["rank", "symbol"])
            for symbol in candidates["symbol"].astype(str):
                if len(current_weights) >= buy_top_n:
                    break
                if not _industry_slot_available(
                    symbol=symbol,
                    day=day,
                    current_weights=current_weights,
                    max_names_per_industry=max_names_per_industry,
                ):
                    continue
                if symbol not in current_weights:
                    current_weights[symbol] = 0.0
                    held_days[symbol] = 0

            active = [symbol for symbol in current_weights if symbol in set(day["symbol"].astype(str))]
            if active:
                indexed = day.set_index(day["symbol"].astype(str))
                raw_weight = min(max_symbol_weight, 1.0 / len(active))
                current_weights = {
                    symbol: raw_weight
                    * float(
                        pd.to_numeric(
                            pd.Series([indexed.loc[symbol, "risk_overlay_scale"]]),
                            errors="coerce",
                        )
                        .fillna(1.0)
                        .iloc[0]
                    )
                    for symbol in active
                }
            else:
                current_weights = {}

        day["review_reason"] = review_reason
        day["raw_weight"] = day["symbol"].astype(str).map(
            lambda symbol: 1.0 if symbol in current_weights else 0.0
        )
        day["weight_unshifted"] = day["symbol"].astype(str).map(
            lambda symbol: current_weights.get(symbol, 0.0)
        )
        day["selected"] = (day["weight_unshifted"] > 0).astype(float)
        day["held_days"] = day["symbol"].astype(str).map(
            lambda symbol: held_days.get(symbol, 0)
        ).fillna(0).astype(int)
        frames.append(day)
        for symbol in list(current_weights):
            held_days[symbol] = held_days.get(symbol, 0) + 1

    out = pd.concat(frames, ignore_index=True).sort_values(["symbol", "date"]).reset_index(drop=True)
    out["weight"] = out.groupby("symbol")["weight_unshifted"].shift(1).fillna(0.0)
    out["position_ret"] = out["weight"] * pd.to_numeric(out["ret"], errors="coerce").fillna(0.0)
    weights = out.pivot(index="date", columns="symbol", values="weight").fillna(0.0)
    turnover = weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1))
    sells = weights.diff().clip(upper=0).abs().sum(axis=1).fillna(0.0)
    gross = out.groupby("date")["position_ret"].sum()
    costs = turnover * (slippage + commission) + sells * stamp_duty_sell
    returns = gross.sub(costs, fill_value=0.0)
    exposure = weights.sum(axis=1)

    selected_columns = [column for column in signal_columns if column in out.columns]
    return StrategyOutput(
        returns=returns,
        exposure=exposure,
        signal_frame=out[selected_columns].copy(),
        metadata=metadata,
)
```

Move `_optional_positive_int` and `_industry_slot_available` into the allocator module under the names shown above, keep `_attach_panel_metadata` in `sleeve_composite.py`, and import the public allocator/helpers from `sleeve_composite.py`.

The v1 call must be exactly:

```python
return allocate_low_churn(
    d,
    params=params,
    slippage=slippage,
    commission=commission,
    stamp_duty_sell=stamp_duty_sell,
    signal_columns=columns,
    metadata=self.build_metadata(params),
)
```

- [ ] **Step 4: Verify no v1 behavioral diff**

Run:

```bash
/Users/aj/workspace/stok-mapping/.venv/bin/python -m pytest -q tests/test_sleeve_composite_strategy.py tests/test_low_churn_allocator.py
git diff --check
```

Expected: all v1 tests pass with unchanged expected symbols, weights, returns, and costs.

- [ ] **Step 5: Commit the mechanical refactor**

```bash
git add phase0/strategies/low_churn_allocator.py phase0/strategies/sleeve_composite.py tests/test_low_churn_allocator.py tests/test_sleeve_composite_strategy.py
git commit -m "refactor: extract low churn allocation engine"
```

### Task 5: Implement The V2 Research Candidate

**Files:**
- Create: `phase0/strategies/sleeve_composite_low_churn_v2.py`
- Create: `tests/test_sleeve_composite_low_churn_v2.py`

- [ ] **Step 1: Write failing strategy tests**

Cover registration separately in Task 6. Factor direction/no-lookahead is already covered by Task 2 and allocation mechanics by Task 4; this task tests their v2 integration, fixed parameters, mandatory quality/earnings presence, delayed weights, financial diagnostics, and empty input.

```python
import pandas as pd

from phase0.research.factors.slow_multifactor import add_slow_multifactor_features
from phase0.strategies.sleeve_composite_low_churn_v2 import SleeveCompositeLowChurnV2Strategy


def _sample_v2_panel() -> pd.DataFrame:
    rows = []
    dates = pd.bdate_range("2023-01-02", periods=140)
    for symbol_index, symbol in enumerate(["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]):
        for date_index, signal_date in enumerate(dates):
            score = 0.9 - symbol_index * 0.1
            rows.append(
                {
                    "date": signal_date,
                    "symbol": symbol,
                    "ts_code": f"{symbol}.SZ",
                    "industry": "A" if symbol_index < 3 else "B",
                    "ret": 0.0005,
                    "close": 10.0 * (1.0008 - symbol_index * 0.00005) ** date_index,
                    "market_cap": 100.0 + symbol_index * 20.0,
                    "pe_ttm": 8.0 + symbol_index * 2.0,
                    "pb": 0.8 + symbol_index * 0.2,
                    "vol60": 0.10 + symbol_index * 0.02,
                    "risk_scale": 1.0,
                    "quality_roe_component": score,
                    "quality_cash_flow_component": score,
                    "quality_low_debt_component": score,
                    "quality_profit_growth_component": score,
                    "quality_revenue_growth_component": score,
                    "financial_available_fields": 5,
                    "financial_announce_date": "2022-12-31",
                }
            )
    return pd.DataFrame(rows)


def _apply(panel: pd.DataFrame):
    strategy = SleeveCompositeLowChurnV2Strategy()
    prepared = add_slow_multifactor_features(panel)
    params = strategy.select_params(
        prepared,
        {"sleeve_composite_low_churn_v2": {"enabled": True}},
        slippage=0.0,
        commission=0.0,
        stamp_duty_sell=0.0,
    )
    assert sum(params["factor_weights"].values()) == 1.0
    assert params["buy_top_n"] == 30
    assert params["hold_top_n"] == 50
    assert params["rebalance_days"] == 20
    assert params["min_hold_days"] == 20
    return strategy.apply(prepared, params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)


def test_v2_scores_fixed_factors_and_delays_weights() -> None:
    strategy = SleeveCompositeLowChurnV2Strategy()
    panel = _sample_v2_panel()
    prepared = add_slow_multifactor_features(panel)
    params = strategy.select_params(
        prepared,
        {"sleeve_composite_low_churn_v2": {"enabled": True}},
        slippage=0.0,
        commission=0.0,
        stamp_duty_sell=0.0,
    )
    output = strategy.apply(prepared, params, slippage=0.0, commission=0.0, stamp_duty_sell=0.0)
    first_date = output.signal_frame["date"].min()
    first = output.signal_frame[output.signal_frame["date"] == first_date]
    second = output.signal_frame[output.signal_frame["date"] > first_date].groupby("date").head(len(first))
    assert first["weight"].eq(0.0).all()
    assert second["weight"].gt(0.0).any()
    assert output.signal_frame["slow_factor_available_count"].ge(4).any()
    assert "quality_cash_flow_component" in output.signal_frame.columns


def test_v2_missing_quality_or_earnings_cannot_enter_portfolio() -> None:
    panel = _sample_v2_panel()
    panel.loc[panel["symbol"] == "AAA", [
        "quality_roe_component",
        "quality_cash_flow_component",
        "quality_low_debt_component",
    ]] = pd.NA
    panel.loc[panel["symbol"] == "BBB", [
        "quality_profit_growth_component",
        "quality_revenue_growth_component",
    ]] = pd.NA
    output = _apply(panel)
    aaa = output.signal_frame[output.signal_frame["symbol"] == "AAA"]
    bbb = output.signal_frame[output.signal_frame["symbol"] == "BBB"]
    assert aaa["slow_composite_score"].isna().all()
    assert aaa["weight_unshifted"].eq(0.0).all()
    assert bbb["slow_composite_score"].isna().all()
    assert bbb["weight_unshifted"].eq(0.0).all()


def test_v2_empty_input_returns_empty_output() -> None:
    output = SleeveCompositeLowChurnV2Strategy().apply(
        pd.DataFrame(),
        {"eligible": True},
        slippage=0.0,
        commission=0.0,
        stamp_duty_sell=0.0,
    )
    assert output.returns.empty
    assert output.exposure.empty
    assert output.signal_frame.empty
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
/Users/aj/workspace/stok-mapping/.venv/bin/python -m pytest -q tests/test_sleeve_composite_low_churn_v2.py
```

Expected: collection fails because `SleeveCompositeLowChurnV2Strategy` does not exist.

- [ ] **Step 3: Implement the strategy as a thin composition layer**

Create the class with no parameter search. `prepare_panel` enables existing PIT quality features on a copied config, calls the existing sleeve preparation, merges exact-date daily-basic fields, and adds shared slow factors. `apply` delegates allocation.

```python
from __future__ import annotations

import copy
from typing import Any

import pandas as pd

from phase0.data_access.daily_basic_history import merge_point_in_time_daily_basic
from phase0.research.factors.slow_multifactor import DEFAULT_WEIGHTS, add_slow_multifactor_features
from phase0.strategies.base import BaseStrategy, StrategyOutput
from phase0.strategies.low_churn_allocator import allocate_low_churn
from phase0.strategies.registry import register
from phase0.strategies.sleeve_composite import QUALITY_COMPONENT_COLUMNS, SleeveCompositeStrategy


@register
class SleeveCompositeLowChurnV2Strategy(BaseStrategy):
    name = "sleeve_composite_low_churn_v2"
    candidate_name = "sleeve_composite_low_churn_v2"
    display_name = "Sleeve Composite Low Churn V2"
    category = "sleeve_composite_low_churn_v2"
    panel_scope = "portfolio"
    supports_brief = False
    supports_paper_trade = False

    def is_enabled(self, strategy_cfg: dict[str, Any]) -> bool:
        return bool(strategy_cfg.get("sleeve_composite_low_churn_v2", {}).get("enabled", False))

    def prepare_panel(self, panel: pd.DataFrame, strategy_cfg: dict[str, Any]) -> pd.DataFrame:
        if panel.empty:
            return panel
        prepared_cfg = copy.deepcopy(strategy_cfg)
        prepared_cfg.setdefault("local_factor", {}).setdefault("quality_growth", {})["enabled"] = True
        prepared = SleeveCompositeStrategy().prepare_panel(panel, prepared_cfg)
        cfg = strategy_cfg.get("sleeve_composite_low_churn_v2", {})
        prepared = merge_point_in_time_daily_basic(
            prepared,
            as_of_date=prepared["date"].max(),
            market=str(cfg.get("market", "CN")),
            table=str(cfg.get("daily_basic_table", "market_daily_basic")),
        )
        return add_slow_multifactor_features(
            prepared,
            weights=cfg.get("factor_weights", DEFAULT_WEIGHTS),
            min_available_factors=int(cfg.get("min_available_factors", 4)),
        )

    def select_params(
        self,
        train: pd.DataFrame,
        strategy_cfg: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> dict[str, Any]:
        cfg = strategy_cfg.get("sleeve_composite_low_churn_v2", {})
        raw = {key: max(0.0, float(value)) for key, value in cfg.get("factor_weights", DEFAULT_WEIGHTS).items()}
        total = sum(raw.values())
        if total <= 0:
            raise ValueError("sleeve_composite_low_churn_v2 requires positive factor weights")
        top_n = max(1, int(cfg.get("top_n", 30)))
        return {
            "eligible": True,
            "factor_weights": {key: value / total for key, value in raw.items()},
            "min_available_factors": max(1, int(cfg.get("min_available_factors", 4))),
            "buy_top_n": top_n,
            "hold_top_n": max(top_n, int(cfg.get("hold_top_n", 50))),
            "rebalance_days": max(20, int(cfg.get("rebalance_days", 20))),
            "min_hold_days": max(20, int(cfg.get("min_hold_days", 20))),
            "max_symbol_weight": min(1.0, max(0.0, float(cfg.get("max_symbol_weight", 0.04)))),
            "max_names_per_industry": max(1, int(cfg.get("max_names_per_industry", 3))),
            "train_score": 0.0,
            "train_sharpe": 0.0,
            "train_trades": 0,
        }

    def apply(
        self,
        panel: pd.DataFrame,
        params: dict[str, Any],
        *,
        slippage: float,
        commission: float,
        stamp_duty_sell: float,
    ) -> StrategyOutput:
        if panel.empty or not bool(params.get("eligible", True)):
            return StrategyOutput(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame(), self.build_metadata(params))
        scored = panel.copy()
        required_scores = {
            "slow_composite_score",
            "slow_factor_available_count",
            "slow_quality_score",
            "slow_earnings_score",
            "slow_value_score",
            "slow_low_vol_score",
            "slow_residual_momentum_score",
        }
        if not required_scores.issubset(scored.columns):
            dates = pd.Index(sorted(scored.get("date", pd.Series(dtype=object)).dropna().unique()))
            empty = pd.Series(0.0, index=dates)
            return StrategyOutput(empty, empty, pd.DataFrame(), self.build_metadata(params))
        scored["final_score"] = scored["slow_composite_score"]
        scored["score"] = scored["slow_composite_score"]
        risk_scale = scored["risk_scale"] if "risk_scale" in scored.columns else pd.Series(1.0, index=scored.index)
        scored["risk_overlay_scale"] = pd.to_numeric(risk_scale, errors="coerce").fillna(1.0).clip(0.0, 1.0)
        columns = [
            "date", "symbol", "ts_code", "industry", "name", "final_score", "score",
            "slow_composite_score", "slow_factor_available_count",
            "slow_quality_score", "slow_earnings_score", "slow_value_score",
            "slow_low_vol_score", "slow_residual_momentum_score",
            "risk_overlay_scale", "rank", "selected", "raw_weight", "weight_unshifted",
            "weight", "held_days", "review_reason", "ret", "position_ret",
            *QUALITY_COMPONENT_COLUMNS,
        ]
        return allocate_low_churn(
            scored,
            params=params,
            slippage=slippage,
            commission=commission,
            stamp_duty_sell=stamp_duty_sell,
            signal_columns=columns,
            metadata=self.build_metadata(params),
        )

    def format_params(self, params: dict[str, Any]) -> str:
        weights = params.get("factor_weights", {})
        return (
            "sleeve_composite_low_churn_v2:"
            f"w={weights},buy_top={params.get('buy_top_n')},hold_top={params.get('hold_top_n')},"
            f"rebalance={params.get('rebalance_days')}d,min_hold={params.get('min_hold_days')}d,"
            f"max_w={params.get('max_symbol_weight')},max_industry_names={params.get('max_names_per_industry')}"
        )
```

- [ ] **Step 4: Run strategy tests and commit**

Run:

```bash
/Users/aj/workspace/stok-mapping/.venv/bin/python -m pytest -q tests/test_sleeve_composite_low_churn_v2.py tests/test_sleeve_composite_strategy.py
git diff --check
git add phase0/strategies/sleeve_composite_low_churn_v2.py tests/test_sleeve_composite_low_churn_v2.py
git commit -m "feat: add low churn multifactor v2 candidate"
```

Expected: v2 tests pass and all v1 characterization tests remain green.

### Task 6: Register And Isolate The Research Candidate

**Files:**
- Modify: `phase0/strategies/__init__.py:1-25`
- Modify: `phase0/research/admission/strategy_scope.py:48-116`
- Modify: `phase0/walk_forward.py:57-65`
- Modify: `config.yaml:367-395,437-495`
- Modify: `tests/test_strategy_admission_config.py:1034-1039`
- Modify: `tests/test_sleeve_composite_low_churn_v2.py`
- Create: `docs/strategy_explanations/sleeve_composite_low_churn_v2.md`
- Modify: `docs/strategy_explanations/INDEX.md`

- [ ] **Step 1: Write failing registry and admission-enable tests**

```python
def test_v2_is_registered_but_not_paper_enabled() -> None:
    strategy = get_strategy("sleeve_composite_low_churn_v2")
    assert isinstance(strategy, SleeveCompositeLowChurnV2Strategy)
    assert strategy.supports_paper_trade is False
    assert strategy.supports_brief is False


def test_force_strategy_set_enabled_supports_low_churn_v2() -> None:
    strategy_cfg = {"sleeve_composite_low_churn_v2": {"enabled": False}}
    _force_strategy_set_enabled_for_admission(strategy_cfg, ["sleeve_composite_low_churn_v2"])
    assert strategy_cfg["sleeve_composite_low_churn_v2"]["enabled"] is True
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
/Users/aj/workspace/stok-mapping/.venv/bin/python -m pytest -q tests/test_sleeve_composite_low_churn_v2.py tests/test_strategy_admission_config.py -k "low_churn_v2"
```

Expected: registry and force-enable assertions fail.

- [ ] **Step 3: Wire registration, diagnostics, and force-enable mapping**

Import `SleeveCompositeLowChurnV2Strategy` in `phase0/strategies/__init__.py`; add the strategy ID to `FINANCIAL_DIAGNOSTIC_STRATEGIES`; and add this exact mapping in `_force_strategy_set_enabled_for_admission`:

```python
"sleeve_composite_low_churn_v2": ("sleeve_composite_low_churn_v2",),
```

- [ ] **Step 4: Add research-only configuration**

Add this strategy set without changing `default_strategy_set`:

```yaml
        sleeve_low_churn_v2_research_v1:
          description: "低换手慢因子 v2 专项研究；不代表准入、模拟或实盘资格。"
          strategies:
            - "sleeve_composite_low_churn_v1"
            - "sleeve_composite_low_churn_v2"
```

Add this disabled candidate config:

```yaml
      sleeve_composite_low_churn_v2:
        enabled: false
        market: "CN"
        daily_basic_table: "market_daily_basic"
        min_available_factors: 4
        top_n: 30
        hold_top_n: 50
        rebalance_days: 20
        min_hold_days: 20
        max_symbol_weight: 0.04
        max_names_per_industry: 3
        factor_weights:
          slow_quality_score: 0.30
          slow_value_score: 0.20
          slow_low_vol_score: 0.20
          slow_earnings_score: 0.15
          slow_residual_momentum_score: 0.15
```

Do not add the v2 strategy to `baseline_admission_all_v1` or `strategy_v2.compare_strategies`. Keep generic constraints in audit mode for existing candidates; v2 enforces the three-name industry slot inside its allocator, so this task must not silently change results for the 13 existing strategies.

- [ ] **Step 5: Document exact trading behavior and limitations**

The strategy explanation must state: PIT financial announcement lag, exact-date valuation fields, 120-to-20-day momentum, industry/size neutralization, 30-name target, 50-rank hold band, 20-day rebalance/minimum hold, 4% symbol cap, three names per industry, next-day execution, current transaction costs, and `supports_paper_trade=False`.

- [ ] **Step 6: Verify configuration isolation and commit**

Run:

```bash
/Users/aj/workspace/stok-mapping/.venv/bin/python -m pytest -q tests/test_sleeve_composite_low_churn_v2.py tests/test_strategy_admission_config.py
/Users/aj/workspace/stok-mapping/.venv/bin/python -m phase0.cli strategy-admission --help
git diff --check
git add phase0/strategies/__init__.py phase0/research/admission/strategy_scope.py phase0/walk_forward.py config.yaml tests/test_strategy_admission_config.py tests/test_sleeve_composite_low_churn_v2.py docs/strategy_explanations/sleeve_composite_low_churn_v2.md docs/strategy_explanations/INDEX.md
git commit -m "config: isolate low churn v2 research candidate"
```

Expected: the v2 strategy is addressable by explicit CLI scope, remains absent from default pools, and remains ineligible for paper/brief output.

### Task 7: Add Reproducible Cost-Sensitivity Admission

**Files:**
- Modify: `phase0/cli_commands/strategy_research.py:82-104,135-180`
- Modify: `phase0/research/admission/runner.py:36-80,108-230`
- Modify: `phase0/research/admission/reports.py:240-330`
- Modify: `tests/test_cli_strategy_research_commands.py:16-69,116-195`
- Modify: `tests/test_strategy_admission_config.py`

- [ ] **Step 1: Write failing CLI and runner tests**

Assert the parser accepts a positive multiplier, rejects zero/negative values, forwards it to the runner, multiplies only `commission`, `stamp_duty_sell`, and `slippage`, and records the multiplier in folds/matrix outputs.

```python
def test_strategy_admission_parser_accepts_cost_multiplier() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd")
    register_strategy_research_commands(subparsers)
    args = parser.parse_args(["strategy-admission", "--cost-multiplier", "1.5"])
    assert args.cost_multiplier == 1.5


def test_admission_cost_multiplier_scales_execution_costs_only(monkeypatch, tmp_path) -> None:
    captured = []

    def fake_run_walk_forward(config, trace_callback=None, runtime=None):
        captured.append(config["walk_forward"])
        return {
            "summary": {
                "walk_forward_train_years": 2,
                "walk_forward_validate_years": 1,
                "walk_forward_expected_folds": 1,
                "walk_forward_actual_folds": 1,
            },
            "candidate_folds": pd.DataFrame(
                [
                    {
                        "strategy_id": "demo_strategy",
                        "candidate": "demo_strategy",
                        "fold": 1,
                        "annualized_return": 0.05,
                        "sharpe": 0.7,
                        "max_drawdown": -0.10,
                        "turnover_annual": 1.0,
                        "trades": 3,
                        "selected_params": "fixed",
                        "supports_paper_trade": False,
                    }
                ]
            ),
        }

    def fake_overfit(*, config, root, candidates_path, folds_path, output_dir, standard_names=False):
        output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = output_dir / "strategy_overfit_diagnostic.csv"
        pd.DataFrame(
            [{"strategy_id": "demo_strategy", "overfit_risk_level": "low", "overfit_score": 0}]
        ).to_csv(csv_path, index=False)
        return SimpleNamespace(csv_path=csv_path)

    monkeypatch.setattr(admission_runner, "create_walk_forward_runtime", lambda config, root: object())
    monkeypatch.setattr(admission_runner, "run_walk_forward", fake_run_walk_forward)
    monkeypatch.setattr(admission_runner, "run_overfit_diagnostic", fake_overfit)
    result = admission_runner.run_strategy_admission(
        config={
            "local_history": {"price_adjustment_for_backtest": "qfq_asof"},
            "walk_forward": {
                "commission": 0.00025,
                "stamp_duty_sell": 0.0005,
                "slippage": 0.00246,
                "presets": {"baseline": {"train_years": 2, "validate_years": 1}},
                "admission": {},
                "strategy_v2": {"compare_strategies": ["demo_strategy"]},
            },
        },
        root=tmp_path,
        presets=["baseline"],
        strategies=["demo_strategy"],
        output_dir=tmp_path / "out",
        cost_multiplier=1.5,
    )
    assert captured[0]["commission"] == pytest.approx(0.000375)
    assert captured[0]["stamp_duty_sell"] == pytest.approx(0.00075)
    assert captured[0]["slippage"] == pytest.approx(0.00369)
    assert pd.read_csv(result.folds_csv)["research_cost_multiplier"].tolist() == [1.5]
    assert pd.read_csv(result.matrix_csv)["research_cost_multiplier"].tolist() == [1.5]
```

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
/Users/aj/workspace/stok-mapping/.venv/bin/python -m pytest -q tests/test_cli_strategy_research_commands.py tests/test_strategy_admission_config.py -k "cost_multiplier"
```

Expected: parser or runner signature assertions fail.

- [ ] **Step 3: Implement explicit cost scaling and reporting**

Add `--cost-multiplier` with `type=float`, default `1.0`, and a parser error when the value is not finite or is `<= 0`. Import NumPy as `np` in `runner.py`. Add `cost_multiplier: float = 1.0` to `run_strategy_admission` and `admission_command_hint` so existing callers remain compatible. In `run_strategy_admission`, deep-copy the config before mutation:

```python
effective_config = copy.deepcopy(config)
multiplier = float(cost_multiplier)
if not np.isfinite(multiplier) or multiplier <= 0:
    raise ValueError("cost_multiplier must be finite and positive")
effective_walk_forward = effective_config.setdefault("walk_forward", {})
for field in ["commission", "stamp_duty_sell", "slippage"]:
    effective_walk_forward[field] = float(effective_walk_forward.get(field, 0.0)) * multiplier
```

Use `effective_config` for runtime creation, walk-forward calls, price-adjustment status, and diagnostics. Add `research_cost_multiplier` to `folds_df`, `matrix_df`, and the governance run context. Update `admission_command_hint` so non-default runs render `--cost-multiplier 1.5` or `2.0`.

- [ ] **Step 4: Verify and commit**

Run:

```bash
/Users/aj/workspace/stok-mapping/.venv/bin/python -m pytest -q tests/test_cli_strategy_research_commands.py tests/test_strategy_admission_config.py
git diff --check
git add phase0/cli_commands/strategy_research.py phase0/research/admission/runner.py phase0/research/admission/reports.py tests/test_cli_strategy_research_commands.py tests/test_strategy_admission_config.py
git commit -m "feat: add admission cost sensitivity multiplier"
```

Expected: default multiplier 1.0 preserves existing output; 1.5 and 2.0 are explicit and auditable.

### Task 8: Full Engineering Verification And Main Integration

**Files:**
- Review all files changed by Tasks 1-7.

- [ ] **Step 1: Run focused strategy and research tests**

```bash
/Users/aj/workspace/stok-mapping/.venv/bin/python -m pytest -q \
  tests/test_daily_basic_history.py \
  tests/test_slow_multifactor_features.py \
  tests/test_factor_effectiveness_slow_factors.py \
  tests/test_low_churn_allocator.py \
  tests/test_sleeve_composite_strategy.py \
  tests/test_sleeve_composite_low_churn_v2.py \
  tests/test_strategy_admission_config.py \
  tests/test_cli_strategy_research_commands.py
```

Expected: all focused tests pass.

- [ ] **Step 2: Run the full suite and static diff checks**

```bash
/Users/aj/workspace/stok-mapping/.venv/bin/python -m pytest -q
git diff --check
git status --short
```

Expected baseline: at least `490 passed`, zero failures, and only intentional source/config/test/doc changes. Generated reports, logs, caches, SQLite files, and the pre-existing unrelated markdown line-ending change must not enter any commit.

- [ ] **Step 3: Review correctness and governance invariants**

Confirm from tests and diff that:

- No forward-return column is available to strategy scoring.
- Financial rows become usable only after `announce_date + financial_lag_days`.
- Daily-basic rows match the same signal date and respect fold as-of bounds.
- Both v1 strategies keep their prior selected symbols, weights, costs, and returns.
- V2 uses fixed weights and has no train-window parameter grid.
- V2 is absent from default candidate pools and remains paper/brief disabled.

- [ ] **Step 4: Merge the code branch into a clean main worktree**

Use `superpowers:finishing-a-development-branch`. Merge only after focused/full verification and a clean review. Do not merge local research outputs. Record the resulting main commit hash in the research run log.

### Task 9: Run The Factor Gate In A Clean Research Worktree

**Files:**
- Generate only: `reports/factor_effectiveness/2026-07-22/low_churn_multifactor_v2/**`
- Generate only: `logs/2026-07-22-low-churn-multifactor-v2-factor-gate.md`

- [ ] **Step 1: Create the research worktree after main integration**

Use `superpowers:using-git-worktrees` and create branch `codex/research-low-churn-multifactor-v2-20260722` from the verified main commit. Verify `git status --short` is empty before adding the local database symlink or running research.

- [ ] **Step 2: Run the existing data-health gate**

Run:

```bash
env PYTHONPATH=. /Users/aj/workspace/stok-mapping/.venv/bin/python -m phase0.cli db-health \
  --config config.yaml \
  --scope cn \
  --fail-on error \
  --output-dir reports/db_health/2026-07-22/low_churn_multifactor_v2
```

Expected: exit code 0 and no error-severity failure for CN daily bars, daily-basic fields, qfq-asof, or PIT financial announce dates. If the command exits non-zero, stop; record the failing check IDs and do not interpret factor results.

- [ ] **Step 3: Run factor effectiveness**

```bash
env PYTHONPATH=. /Users/aj/workspace/stok-mapping/.venv/bin/python -m phase0.cli factor-effectiveness \
  --config config.yaml \
  --output-dir reports/factor_effectiveness/2026-07-22/low_churn_multifactor_v2
```

Expected non-empty artifacts:

```text
factor_effectiveness_summary.csv
factor_effectiveness_report.md
factor_group_returns.csv
factor_ic_by_year.csv
factor_correlation.csv
```

- [ ] **Step 4: Apply the factor gate**

Proceed to formal strategy admission only when all conditions hold:

- Every included slow factor has coverage ratio `>= 0.20`.
- At least two of the five slow factors have recommendation `use`.
- No included slow factor has recommendation `missing` or `reject`.
- Each included factor has either positive mean Rank IC or positive top-minus-bottom forward return.
- Absolute pairwise correlation between included factor scores is `< 0.75`.
- IC sign does not reverse in more than one reported calendar year.

If the gate fails, write the exact failing factors and metrics to the local log and stop the v2 admission run. That is a valid research result, not an engineering failure.

### Task 10: Run Formal Admission And Cost Sensitivity

**Files:**
- Generate only: `reports/strategy_admission/2026-07-22/low_churn_multifactor_v2/**`
- Generate only: `logs/2026-07-22-low-churn-multifactor-v2-admission.md`

- [ ] **Step 1: Run the base-cost two-window admission**

```bash
env PYTHONPATH=. /Users/aj/workspace/stok-mapping/.venv/bin/python -m phase0.cli strategy-admission \
  --config config.yaml \
  --presets baseline_2y_1y_5fold quality_3y_1y_4fold \
  --strategies sleeve_composite_low_churn_v1 sleeve_composite_low_churn_v2 \
  --cost-multiplier 1.0 \
  --output-dir reports/strategy_admission/2026-07-22/low_churn_multifactor_v2/base_cost \
  --profile
```

Expected: 18 fold rows, four window-matrix rows, two constraint-review rows, and standard admission/governance/overfit artifacts.

- [ ] **Step 2: Run 1.5x and 2.0x cost sensitivity sequentially**

Run the same command twice, changing only multiplier/output directory:

```bash
--cost-multiplier 1.5 --output-dir reports/strategy_admission/2026-07-22/low_churn_multifactor_v2/cost_1_5x
--cost-multiplier 2.0 --output-dir reports/strategy_admission/2026-07-22/low_churn_multifactor_v2/cost_2x
```

Do not run the three admissions concurrently against the shared 6.9 GB history database. Validate each run's completion marker and artifacts before starting the next.

- [ ] **Step 3: Apply the strategy gate**

V2 is eligible only if the base-cost run satisfies all existing admission conditions in both presets:

- `annualized_return_mean > 0`
- `sharpe_mean > 0.5`
- `max_drawdown_worst > -0.25`
- `positive_fold_ratio >= 0.75`
- `turnover_annual_mean <= 3.0`
- `turnover_annual_max <= 5.0`
- `overfit_risk_level <= medium`
- parameter stability, industry concentration, factor diagnostics, qfq-asof, and account execution checks pass

In addition, require:

- Base-cost annual turnover mean `< 2.0` as the v2 design target.
- 1.5x-cost annualized return remains positive in both windows.
- 2.0x-cost Sharpe does not decline by more than 30% from base cost in either window.
- V2 improves base-cost Sharpe or maximum drawdown over v1 in both presets; a single lucky window is insufficient.

- [ ] **Step 4: Record one of three decisions**

Use exactly one decision label in the local report:

- `STOP_SIGNAL`: factor gate failed; do not tune portfolio parameters.
- `REVISE_PORTFOLIO`: factor gate passed, but admission failed on drawdown/concentration/turnover while returns remained positive.
- `ELIGIBLE_FOR_PAPER_REVIEW`: all factor, admission, cost, execution, and governance gates passed.

Do not change `supports_paper_trade`, simulated account configuration, Daily Brief, or default strategy sets in this task.

### Task 11: Interpret And Archive The Research Result

**Files:**
- Generate only: `logs/2026-07-22-strategy-experiment-interpretation.md`

- [ ] **Step 1: Use the project `策略实验解读` skill**

Write the final Chinese interpretation with:

- base/1.5x/2.0x annualized return, Sharpe, maximum drawdown, positive-fold ratio, and turnover;
- v1 versus v2 comparison by preset;
- how the 30-name monthly rank-buffer strategy buys, holds, and sells;
- PIT, qfq-asof, suspension, limit-up/down, liquidity, and next-open execution constraints;
- the selected decision label and exact failed/passed gates;
- explicit language that historical results are not future-return promises.

- [ ] **Step 2: Verify research worktree cleanliness**

```bash
git status --short
```

Expected: no tracked research output changes. If only the known unrelated line-ending modification appears, record it without staging or altering it.

## Final Acceptance Checklist

- [ ] Existing v1 output is behaviorally unchanged.
- [ ] V2 has no future-data path and no parameter grid search.
- [ ] PIT value and financial fields are covered and auditable.
- [ ] Industry and size neutrality are tested numerically.
- [ ] Full engineering suite has zero failures.
- [ ] Factor gate is applied before strategy admission.
- [ ] Admission uses exactly the two formal presets.
- [ ] Cost multipliers are explicit in command hints and artifacts.
- [ ] Reports/logs/databases remain local-only.
- [ ] Paper-review promotion is a separate, evidence-triggered change.
