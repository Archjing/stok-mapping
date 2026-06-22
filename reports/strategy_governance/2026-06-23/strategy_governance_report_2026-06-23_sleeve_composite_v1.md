# Strategy Governance Report - 2026-06-23 - sleeve_composite_v1

## Background

- Task: T2.10.1 rules-based sleeve composite V1 validation.
- Reason: `sleeve_composite_v1` was newly added as a research-only compare/admission candidate and needed a first scoped admission result.
- Code changes under validation: new `sleeve_composite_v1` strategy, registry/config admission wiring, financial diagnostics wiring, research-only admission boundary, and unit tests.
- Backtest/admission scope: scoped `strategy-admission` run for `sleeve_composite_v1` only.

## Run Context

- Command:

```bash
./.venv/bin/python -m phase0.cli strategy-admission \
  --presets baseline_2y_1y_5fold quality_3y_1y_4fold \
  --strategies sleeve_composite_v1 \
  --output-dir reports/strategy_admission_sleeve_composite_v1_20260623
```

- Price mode: `qfq_asof`.
- Universe: point-in-time A-share universe from the current project config.
- Presets:
  - `baseline_2y_1y_5fold`: 2-year train, 1-year validation, fixed window `2019-04-01` to `2026-03-31`, expected 5 folds.
  - `quality_3y_1y_4fold`: 3-year train, 1-year validation, fixed window `2019-04-01` to `2026-03-31`, expected 4 folds.
- Strategy set / strategies: explicit CLI strategy list, `sleeve_composite_v1`.
- Cost assumptions: current `config.yaml` Phase 0 transaction-cost settings.
- Data as-of: local project data available during the run on 2026-06-23.

## Output Artifacts

- Admission report: `reports/strategy_admission_sleeve_composite_v1_20260623/strategy_admission_report.md`
- Window matrix: `reports/strategy_admission_sleeve_composite_v1_20260623/strategy_admission_window_matrix.csv`
- Constraint review: `reports/strategy_admission_sleeve_composite_v1_20260623/strategy_admission_constraint_review.csv`
- Candidate folds: `reports/strategy_admission_sleeve_composite_v1_20260623/strategy_admission_candidate_folds.csv`
- Overfit diagnostic: `reports/strategy_admission_sleeve_composite_v1_20260623/overfit_diagnostic/strategy_overfit_diagnostic.csv`

## Code Verification

- Tests before admission:
  - `./.venv/bin/python -m pytest -s tests/test_sleeve_composite_strategy.py tests/test_strategy_admission_config.py`: passed, `23 passed`.
  - `./.venv/bin/python -m pytest -s`: passed, `44 passed`.
- Static checks:
  - scoped `git diff --check` passed for touched strategy, config, test, and task-document files.
- Known warnings:
  - Existing third-party `py_mini_racer` deprecation warning; not related to `sleeve_composite_v1`.

## Results

- Selected candidate: none. This was a scoped one-strategy admission run, not a multi-candidate selection run.
- Overall admission action: `reject`.
- Window pass count: `0/2`.
- Overfit risk: `critical`.
- Overfit score: `85`.
- `supports_paper_trade`: candidate folds report `False`; the strategy remains research-only and must not enter paper review, simulated account, or daily brief.

| preset | folds | annualized_return_mean | sharpe_mean | max_drawdown_worst | turnover_annual_mean | turnover_annual_max | positive_fold_ratio | pass |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `baseline_2y_1y_5fold` | 5 | -42.74% | -3.3133 | -53.14% | 33.23 | 44.96 | 0.00 | false |
| `quality_3y_1y_4fold` | 4 | -39.97% | -3.1695 | -49.38% | 35.06 | 44.96 | 0.00 | false |

## Diagnostics

- Return: failed. Both windows have negative annualized return and negative Sharpe.
- Execution / turnover: failed. Annual turnover is far above the gate (`turnover_annual_mean_max = 3.0`, `turnover_annual_max_max = 5.0`).
- Construction / industry: failed. Industry concentration exceeded audit threshold in both windows.
- Factor / PIT: available. Financial PIT announce coverage is `1.00`, field coverage is `1.00`, and selected field coverage is `1.00` in both windows.
- Parameter stability: no failure in this run; `parameter_unstable_window_count = 0`.
- Regime / overfit: failed. Overfit risk is `critical`, score `85`, and positive fold ratio is `0.0`.
- Data quality: no missing financial diagnostic or qfq_asof price adjustment failure was reported.

## Decision

- Decision: `reject`.
- Boundary: keep `sleeve_composite_v1` as a research-only diagnostic candidate. Do not promote it to paper review, simulated account, daily brief, or watchlist generation.
- Next action:
  - Do not tune this version directly for returns.
  - First reduce construction and execution failures: rebalance cadence, turnover controls, hold band, and max new names per rebalance.
  - Rework risk overlay semantics so risk scaling reduces churn and exposure instead of increasing daily reshuffling.
  - After construction changes, rerun scoped admission and regenerate this governance report.
