# Python And Shell Architecture Consolidation Plan

Last revised: 2026-06-26

## Purpose

This plan defines the KISS-oriented path for consolidating Python code and shell entrypoints by the project's actual functional architecture. The goal is to group related code, reduce duplicated helpers, and keep behavior stable while the strategy-research system continues to run.

The current branch starts with narrow, verifiable slices. It does not claim the full codebase consolidation is finished.

## Migration Scope Guardrails

Structural migration is not valuable by itself. A module should move only when the move produces a clear engineering benefit: lower coupling, cleaner dependency direction, better reuse, simpler tests, or less duplicate code. Modules with stable callers and high behavioral risk should stay in place until a concrete problem justifies moving them.

Current decisions:

- Keep `phase0/universe.py` in place for this branch. It sits on the boundary between current-market snapshot construction, point-in-time universe loading, and walk-forward research. Moving it now would add import churn without improving correctness or reducing meaningful duplication.
- Do not move `phase0/update_history.py` or `phase0/tushare_history_backfill.py` just to satisfy package shape. They are write-side data-governance jobs and should move only if we first extract shared helpers with tests and can preserve CLI/data-write behavior.
- `phase0/tushare_source.py` has been moved as a provider-only slice because it produces a cleaner dependency direction: write-side jobs now depend on `phase0.data_access.providers.tushare`, while the old root path remains a compatibility shim.

## Current Functional Layers

| Layer | Responsibility | Current modules |
| --- | --- | --- |
| `reporting` | Report output paths, run directories, artifact registry, Markdown/HTML/CSV writers | `phase0/reporting/paths.py`, `phase0/reporting/registry.py`, `phase0/reporting/writers.py`, compatibility shims `phase0/report_paths.py`, `phase0/report_registry.py` |
| `data_governance` | Data quality checks, governance audits, as-of coverage validation, bounded maintenance helpers | `phase0/data_governance/quality.py`, `phase0/data_governance/db_health.py`, `phase0/data_governance/index_asof_audit.py`, `phase0/data_governance/index_asof_backfill.py`, compatibility shims in `phase0/quality.py`, `phase0/db_health.py`, `phase0/index_asof_*.py` |
| `data_access/providers` | Local history reads and external provider adapters; it should not own write-side governance jobs | `phase0/data_access/providers/tushare.py`, compatibility shim `phase0/tushare_source.py`; other provider/read modules still in `phase0/local_history.py`, `phase0/data_sources.py`, `phase0/external_market_history.py`; possible future provider-only extraction from `phase0/adjustment*.py`, `phase0/daily_basic_backfill.py`, `phase0/financial_factors.py`, and `phase0/import_history.py` |
| `universe` | Current universe construction and point-in-time universe loading | Stable root module `phase0/universe.py`; no migration planned in this branch |
| `domain/strategies` | Strategy interfaces, strategy implementations, portfolio constraints, execution assumptions that are part of strategy behavior | `phase0/strategies/*`, `phase0/strategies/constraints.py`, compatibility shim `phase0/strategy_constraints.py`, parts of `phase0/accounts.py` |
| `research` | Walk-forward, admission, overfit checks, factor effectiveness, attribution, diagnostics, holdings exposure rebuilds, participation diagnostics, core coverage audits, research summaries/role cards | `phase0/research/admission/*`, `phase0/research/diagnostics/*`, `phase0/research/attribution/*`, `phase0/research/core_coverage/*`, `phase0/research/holdings/*`, `phase0/research/participation/*`, `phase0/research/summaries/*`, root compatibility shims for migrated research modules, `phase0/walk_forward.py`, `phase0/strategy_admission.py`, `phase0/overfit.py`, `phase0/factor_effectiveness.py`, remaining heavy `phase0/strategy_*` research modules |
| `intelligence` | Strategy intelligence collection, import, validation, review, external probe scripts | `phase0/intelligence.py`, `scripts/tiingo_news_probe.py`, LLM/integration scripts |
| `cli` | Argument parsing and command routing | `phase0/cli.py`, thin wrappers under `scripts/` |
| `orchestration` | Scheduled maintenance, long-task control, process coordination, runtime status | `phase0/maintenance_orchestrator.py`, scheduler shell entrypoints, shared shell environment helpers |
| `core` | Config/env/path helpers and small shared utilities that do not own business behavior | `phase0/config.py`, `phase0/env.py`, future shared helpers |

## First Slice In This Branch

The first slice consolidates report path and report artifact responsibilities:

- Move report path logic into `phase0.reporting.paths`.
- Move report artifact scanning/manifest logic into `phase0.reporting.registry`.
- Move report writer helpers into `phase0.reporting.writers`.
- Keep `phase0.report_paths` and `phase0.report_registry` as compatibility shims.
- Make new report outputs read `phase0.reporting.root_dir/categories` from `config.yaml`.
- Preserve explicit CLI path semantics: user-provided relative paths remain project-root relative unless a function explicitly documents report-config path behavior.

This slice is intentionally small because report paths are a cross-cutting dependency. Stabilizing it first lowers risk for later data-governance and research-module moves.

## Second Slice In This Branch

The second slice starts the data-governance package with modules whose responsibilities are already audit/governance shaped:

- Move `quality.py` into `phase0.data_governance.quality`.
- Move `db_health.py` into `phase0.data_governance.db_health`.
- Move `index_asof_audit.py` into `phase0.data_governance.index_asof_audit`.
- Move `index_asof_backfill.py` into `phase0.data_governance.index_asof_backfill`.
- Keep root-level shims for old imports, including tests that still depend on selected private helper imports.

This slice intentionally does not move `local_history.py`, `universe.py`, `update_history.py`, broad Tushare/AkShare backfill flows, or adjustment/financial production jobs. Those modules carry current-market, point-in-time, write-side, or third-party provider coupling. They should move only when a later slice proves a concrete benefit and has compatibility tests ready.

## Third Slice In This Branch

The third slice starts the research package with leaf strategy diagnostics that read existing artifacts and write research-only reports:

- Move `strategy_market_context.py` into `phase0.research.diagnostics.market_context`.
- Move `strategy_exposure_diagnostic.py` into `phase0.research.diagnostics.exposure`.
- Move `strategy_filter_diagnostic.py` into `phase0.research.diagnostics.filter`.
- Keep root-level modules as alias shims so old imports and monkeypatch-based tests still target the same module objects.

This slice intentionally does not move `walk_forward.py`, `strategy_admission.py`, attribution modules, holdings exposure, CSI300 attribution, strategy constraints, strategy implementations, or export scripts. Those carry broader execution or domain behavior and need separate compatibility gates.

## Fourth Slice In This Branch

The fourth slice adds a research attribution package for low-coupling modules that read existing CSV artifacts and write attribution outputs:

- Move `strategy_alpha_source_audit.py` into `phase0.research.attribution.alpha_source`.
- Move `strategy_fold_attribution.py` into `phase0.research.attribution.fold`.
- Keep root-level modules as alias shims so old imports and module-level monkeypatches remain compatible.

This slice intentionally does not move `strategy_failure_attribution.py`, because it imports admission gate helpers and is closer to the admission workflow. It also does not move participation overlays, participation-path audits, role cards, holdings exposure, CSI300 attribution, core reachability, or missing-core audit because those belong to separate research subpackages or depend on heavier execution/data internals. A later slice moves failure attribution with its own admission-focused compatibility gate.

## Fifth Slice In This Branch

The fifth slice starts shell-entrypoint consolidation with a small shared environment helper:

- Add `scripts/lib/project_env.sh` for project-root, Python interpreter, log directory, `.env` loading, and timestamp helpers.
- Update `run_daily_brief_pipeline.sh`, `update_manual_history_daily.sh`, and `update_financial_factors_weekly.sh` to use the shared helper.
- Keep each script's task command, logging destination, and lock behavior unchanged.

This slice intentionally does not move or rewrite `run_project_scheduler.sh`, `install_dev_cron.sh`, Cloe/acpx agent wrappers, `openclaw_agent.sh`, or `.codex/run_claude_agent.sh`. Those scripts affect cron installation, the every-minute scheduler entrypoint, external agent session semantics, or `.codex` runner behavior and need separate review.

## Sixth Slice In This Branch

The sixth slice consolidates Cloe/acpx shell wrapper behavior while preserving the external agent contract:

- Add `scripts/lib/acpx_agent.sh` for role/global/OpenClaw environment fallback and common `acpx openclaw` invocation.
- Update `cloe_agent.sh`, `cloe_premarket_agent.sh`, `cloe_research_agent.sh`, and `cloe_risk_agent.sh` to keep only usage text, defaults, and role selection.
- Preserve `openclaw_agent.sh` as the compatibility entrypoint over `cloe_agent.sh`.
- Add `tests/test_acpx_agent_wrappers.py` with a fake `acpx` command so session names, timeout, format, TTL, argument joining, usage exit code, and compatibility behavior are verified without touching external agents.

This slice intentionally does not move or rewrite `run_project_scheduler.sh`, `install_dev_cron.sh`, or `.codex/run_claude_agent.sh`. Those scripts carry cron installation, every-minute scheduler, or Codex runner behavior and need separate review.

## Seventh Slice In This Branch

The seventh slice starts retiring old Python import paths inside the project:

- Update ordinary data-governance, research diagnostic, and research attribution tests to import from `phase0.data_governance.*` and `phase0.research.*`.
- Keep `tests/test_data_governance_imports.py`, `tests/test_research_diagnostics_imports.py`, and `tests/test_research_attribution_imports.py` as explicit compatibility tests for old root-level shims.
- Confirm an `rg` audit leaves old Python import paths only in those compatibility tests and historical/planning documentation.

This slice does not remove any root-level compatibility shim. Wrapper deletion is deferred until after main-branch merge and the complete validation cycle described below.

## Eighth Slice In This Branch

The eighth slice adds a participation research package for low-coupling exposure diagnostics:

- Move `strategy_participation_overlay.py` into `phase0.research.participation.overlay`.
- Move `strategy_participation_path_audit.py` into `phase0.research.participation.path_audit`.
- Update `phase0.cli` and ordinary participation tests to import from the new package paths.
- Keep root-level alias shims and `tests/test_research_participation_imports.py` so old imports and private-helper imports remain compatible during the transition.

This slice intentionally does not move holdings exposure, CSI300 attribution, core reachability, missing-core audit, role cards, or failure attribution. Those modules either rebuild historical holdings, read local benchmark as-of tables, or depend on admission internals and need separate gates.

## Ninth Slice In This Branch

The ninth slice adds a research summaries package for read-only strategy summary artifacts:

- Move `strategy_role_card.py` into `phase0.research.summaries.role_card`.
- Update `phase0.cli` and ordinary role-card tests to import from the new package path.
- Keep a root-level alias shim and `tests/test_research_summaries_imports.py` so old imports remain compatible during the transition.

This slice intentionally does not move failure attribution, holdings exposure, CSI300 attribution, core reachability, or missing-core audit. Those modules have admission-internal, holdings-rebuild, or benchmark-as-of/data-access coupling and need separate migration gates.

## Tenth Slice In This Branch

The tenth slice adds a research admission package for admission-result diagnostics:

- Move `strategy_failure_attribution.py` into `phase0.research.admission.failure_attribution`.
- Update `phase0.cli` and ordinary failure-attribution tests to import from the new package path.
- Keep a root-level alias shim and `tests/test_research_admission_imports.py` so old imports remain compatible during the transition.

This slice intentionally does not move `strategy_admission.py` itself. Failure attribution still depends on selected admission gate helper functions, but it remains a read-only diagnostic that consumes existing admission/overfit CSV artifacts and writes attribution reports.

## Eleventh Slice In This Branch

The eleventh slice folds benchmark attribution into the research attribution package:

- Move `strategy_csi300_attribution.py` into `phase0.research.attribution.csi300`.
- Update `phase0.cli` and ordinary CSI300 attribution tests to import from the new package path.
- Keep a root-level alias shim and extend `tests/test_research_attribution_imports.py` so old imports remain compatible during the transition.

This slice intentionally does not move holdings exposure, core reachability, or missing-core audit. CSI300 attribution still reads local SQLite benchmark as-of tables, but it is a read-only attribution diagnostic and does not write database state or rerun strategies.

## Twelfth Slice In This Branch

The twelfth slice adds a core coverage research package for core reachability and post-diagnostic missing-core audits:

- Move `strategy_core_reachability.py` into `phase0.research.core_coverage.core_reachability`.
- Move `strategy_missing_core_audit.py` into `phase0.research.core_coverage.missing_core_audit`.
- Update `phase0.cli` and ordinary core-coverage tests to import from the new package paths.
- Keep root-level alias shims and add `tests/test_research_core_coverage_imports.py` so old imports remain compatible during the transition.

Core reachability checks benchmark core-weight reachability through existing PIT universe folds and optional read-only panel seeding; missing-core audit consumes existing core-reachability/admission CSV artifacts, checks point-in-time universe membership and local-history coverage, and writes audit CSV/Markdown. These modules do not rebuild holdings, change strategy algorithms, or write database state.

## Thirteenth Slice In This Branch

The thirteenth slice adds a holdings research package for research-only historical holdings exposure rebuilds:

- Move `strategy_holdings_exposure.py` into `phase0.research.holdings.exposure`.
- Update `phase0.cli` and ordinary holdings exposure tests to import from the new package path.
- Keep a root-level alias shim and add `tests/test_research_holdings_imports.py` so old imports remain compatible during the transition.

This slice keeps the existing diagnostic boundary: holdings exposure replays selected historical strategy folds to rebuild daily holdings, industry exposure, summary, coverage, report, and run-log artifacts. It does not write SQLite state, rerun strategy admission, change strategy algorithms, or create trading signals.

## Fourteenth Slice In This Branch

The fourteenth slice moves portfolio constraint logic into the strategy domain package:

- Move `strategy_constraints.py` into `phase0.strategies.constraints`.
- Update effective project imports in `phase0.walk_forward`, holdings exposure, and ordinary constraint tests to use the new domain path.
- Keep a root-level alias shim and add `tests/test_strategy_constraints_imports.py` so old imports remain compatible during the transition.

This slice does not change constraint behavior, cost recomputation, strategy parameters, admission thresholds, or execution assumptions. The constraints module remains the shared post-strategy portfolio constraint engine used by walk-forward and research holdings replay.

## Fifteenth Slice In This Branch

The fifteenth slice starts decomposing the large admission runner with low-risk configuration helpers:

- Add `phase0.research.admission.strategy_scope` for admission strategy-scope resolution and scoped strategy enablement helpers.
- Keep `phase0.strategy_admission` as the admission runner module and re-export the moved helper names for old imports.
- Update holdings exposure and ordinary admission tests to use the new helper path where they do not need the admission runner itself.
- Extend `tests/test_research_admission_imports.py` so new helper paths and old-path compatibility are both covered.

This slice intentionally does not move `run_strategy_admission`, admission window-matrix construction, constraint review, report writers, or governance report generation. It only moves pure config parsing / strategy-enable helpers and does not change admission outputs, strategy parameters, report paths, thresholds, or walk-forward execution.

## Sixteenth Slice In This Branch

The sixteenth slice starts the data-access provider package with the Tushare adapter:

- Move `phase0/tushare_source.py` into `phase0.data_access.providers.tushare`.
- Keep `phase0.tushare_source` as a module alias shim so old imports and monkeypatches still hit the provider module.
- Update effective project imports in daily basic backfill, adjustment backfill, manual history update, Tushare history backfill, data-source connectivity, and index as-of backfill to use the new provider path.
- Add `tests/test_data_access_provider_imports.py` so new provider imports and old-path compatibility are both covered.

This slice does not move `phase0/update_history.py`, `phase0/tushare_history_backfill.py`, `phase0/daily_basic_backfill.py`, `phase0/adjustment_backfill.py`, or index as-of backfill. Those remain write-side data-governance jobs that call the provider. It also does not change Tushare payloads, normalization rules, retry behavior, request throttling, database writes, report paths, or CLI command names.

## Later Migration Stages

| Stage | Scope | Acceptance gate |
| --- | --- | --- |
| P1 Reporting foundation | Finish `phase0.reporting.*` and config-driven output defaults | Report path tests, registry tests, targeted CLI path tests, `python -m phase0.cli --help` |
| P2 Data governance package | Move audit/quality/as-of governance modules first; keep write-heavy providers and broad backfills in place until helper extraction | Existing data-health/as-of tests, import compatibility tests, CLI help for related commands, no table/schema changes |
| P3 Domain strategies and research | Start with leaf research diagnostics and attribution helpers, then separate strategy implementations from walk-forward/admission/diagnostics | Research diagnostic/attribution import tests, strategy registry tests, walk-forward/admission targeted tests, no strategy parameter or cost-model changes |
| P4 CLI and orchestration | Split `phase0.cli` into command modules and move scheduler orchestration | All CLI help paths pass, scheduler command names and env vars remain compatible |
| P5 Intelligence | Split collection/import/validate/review code and keep scripts thin | Intelligence CLI help, ledger/candidate schema tests, no required external API calls in tests |
| P6 Scripts cleanup | Convert heavy Python scripts and repeated shell entrypoints into wrappers over packaged functions/shared shell helpers | Thin script smoke tests, bash syntax checks, import compatibility tests |

## Compatibility Shim Retirement Policy

Compatibility wrappers and import shims are temporary migration aids, not the final architecture. They can be removed only after the new package paths have become the project-internal default.

Required sequence:

1. Migrate effective project code and normal tests to new package paths.
2. Keep explicit compatibility tests for old paths during the transition period so downstream/manual commands fail loudly if behavior changes.
3. After this branch is merged back to `main`, run one complete validation cycle:
   - one data maintenance flow,
   - one strategy compare/admission flow or equivalent research diagnostic flow,
   - and an `rg` audit proving no effective project code still imports the old paths.
4. Remove compatibility wrappers/import shims in a separate cleanup commit, after the validation evidence is recorded.

Historical plans and compatibility tests may still mention old paths until the cleanup commit. That is acceptable; production code and ordinary tests should not keep depending on them.

## KISS Cleanup Backlog

These are real redundancy candidates, but each should be cleaned only when its owning layer is migrated:

| Redundancy | Current locations | KISS action |
| --- | --- | --- |
| `_resolve_path` variants | Multiple `phase0/` modules and `scripts/` | Centralize into a small core path helper after reporting and data-governance shims are stable |
| SQL identifier validation | Data governance modules | Centralize into a single helper when moving data modules |
| Annualized return / Sharpe / drawdown helpers | `walk_forward.py`, OOS/report scripts, market-regime scripts | Move to `research.metrics` only after matching NaN and annualization behavior with tests |
| Markdown/HTML table writers | Several strategy/report scripts | Add small `reporting.tables` helpers; do not introduce a large templating framework |
| Large CLI file | `phase0/cli.py` | Split by command group after output paths are stable |
| Large strategy bill script | `scripts/export_strategy_bill.py` | Extract reusable research/execution functions later; keep CLI wrapper compatibility |
| Similar low-turnover wrappers | `scripts/export_low_turnover_*` | Consolidate to strategy-id based wrappers after current users are mapped |
| Provider/update coupling | `local_history.py`, `data_sources.py`, `external_market_history.py`, `update_history.py`, Tushare write-side jobs | Move only where it improves dependency direction or reuse; keep write-side jobs in place until helper extraction is tested |
| Universe boundary | `universe.py` | Keep in place in this branch; revisit only if current snapshot construction and point-in-time loading are split into separately tested units |
| Shell environment bootstrap | Maintenance shell scripts | Keep one small `scripts/lib/project_env.sh`; do not hide cron, lock, or external agent semantics in broad shell frameworks |

## Non-Goals

- Do not rewrite strategy algorithms during structural migration.
- Do not change data tables, as-of rules, adjustment modes, costs, or admission thresholds as part of package cleanup.
- Do not commit `reports/`, `logs/`, SQLite databases, or generated research artifacts.
- Do not make Harness or `codex-harness-runner` a runtime dependency of the product code.

## Harness Working Rule

Team Lead owns git boundaries, scope control, and final integration. Planner, implementer, reviewer, verifier, and memory-steward style agents can be used for bounded reviews or disjoint work. Completed subagents should be closed. Parallel write work must use separate git worktrees or disjoint file ownership.
