---
name: strategy-admission
description: Use for Stok Mapping strategy admission, walk-forward presets, strategy comparison reports, admission thresholds, overfit diagnostics, and smoke/full backtest review.
---

# Strategy Admission

Use this skill when the task concerns strategy validation, walk-forward windows, strategy comparison, admission criteria, overfit diagnostics, or interpreting generated strategy reports.

## Scope

- Keep research price, execution price, and valuation price separate.
- Default to PIT-safe inputs and explicit price-adjustment mode.
- Treat strategy-specific parameters and global admission thresholds as separate concepts.
- Do not infer strategy quality from one fold, one preset, or pre-cost results.

## Primary Commands

```bash
./.venv/bin/python -m phase0.cli strategy-admission --config config.yaml --preset baseline_2y_1y_5fold
./.venv/bin/python -m phase0.cli strategy-admission --config config.yaml --preset quality_3y_1y_4fold
./.venv/bin/python -m phase0.cli strategy-admission --config config.yaml --preset quality_4y_1y
```

Add task-specific strategy names, date bounds, output directory, and trace flags only after reading the current CLI arguments.

## Key Files

- `phase0/strategy_admission.py`
- `phase0/walk_forward.py`
- `config.yaml`
- `docs/STRATEGY_DEVELOPMENT_GUIDELINES.md`
- `docs/DEVELOPMENT_PLAN.md`
- `docs/PROJECT_ARCHITECTURE_OVERVIEW.md`
- `reports/strategy_admission_*/`

Historical task breakdowns and the 2026-06 research plan live under `docs/archive/`; they are not current admission criteria.

## Review Rules

- Confirm which preset was used and what exact train/validation windows it creates.
- Check coverage diagnostics before interpreting performance.
- Compare annualized return, Sharpe, drawdown, turnover, trade count, live days, holdings, and overfit risk together.
- If a report fails during writing, inspect partial CSV outputs before claiming the backtest is unusable.
