# Python And Shell Architecture Consolidation Plan

Last revised: 2026-06-26

## Purpose

This plan defines the KISS-oriented path for consolidating Python code and shell entrypoints by the project's actual functional architecture. The goal is to group related code, reduce duplicated helpers, and keep behavior stable while the strategy-research system continues to run.

The current branch starts with narrow, verifiable slices. It does not claim the full codebase consolidation is finished.

## Migration Scope Guardrails

Structural migration is not valuable by itself. A module should move only when the move produces a clear engineering benefit: lower coupling, cleaner dependency direction, better reuse, simpler tests, or less duplicate code. Modules with stable callers and high behavioral risk should stay in place until a concrete problem justifies moving them.

Current decisions:

- Keep `phase0/universe.py` in place for this branch. It sits on the boundary between current-market snapshot construction, point-in-time universe loading, and walk-forward research. Moving it now would add import churn without improving correctness or reducing meaningful duplication.
- Keep `phase0/walk_forward.py` in place for this branch. It is the high-coupling research orchestration core for data loading, factor construction, portfolio simulation, candidate comparison, and metric aggregation. Moving it as a whole would create broad import churn and behavioral risk; only split bounded leaf helpers when tests prove the extracted responsibility is stable.
- `phase0/local_history.py` has been moved to `phase0.data_access.local_history`. It is the SQLite-backed local history read/configuration layer; the old root path remains a compatibility shim.
- `phase0/overfit.py` has been moved to `phase0.research.diagnostics.overfit`. It is a research diagnostic consumed by the admission runner and strategy-research CLI; the old root path remains a compatibility shim.
- `phase0/factor_effectiveness.py` has been moved to `phase0.research.diagnostics.factor_effectiveness`. It is a strategy research diagnostic; the old root path remains a compatibility shim.
- `phase0/update_history.py` has been moved to `phase0.data_governance.update_history` after shared SQL and daily-basic table helpers were extracted and compatibility tests were added. The old root path remains a compatibility shim.
- `phase0/adjustment.py` has been moved to `phase0.data_governance.adjustment`. It owns price-adjustment factor table helpers, qfq_asof construction, and adjustment audit reporting; the old root path remains a compatibility shim.
- `phase0/import_history.py` has been moved to `phase0.data_governance.import_history`. It is a write-side local history initialization and index-history rebuild job; the old root path remains a compatibility shim.
- `phase0/financial_factors.py` has been moved to `phase0.data_governance.financial_factors`. It is a write-side quarterly financial factor maintenance job and table helper; the old root path remains a compatibility shim.
- `phase0/tushare_history_backfill.py` has been moved to `phase0.data_governance.backfills.tushare_history` after shared SQL and daily-basic table helpers were extracted and compatibility tests were added. The old root path remains a compatibility shim.
- `phase0/external_market_history.py` has been moved to `phase0.data_governance.external_market_history`. It owns US/HK history update orchestration, SQLite writes, source audit rows, and local history reads; raw external provider fetching now lives in `phase0.data_access.providers.external_market`.
- `phase0/tushare_source.py` has been moved as a provider-only slice because it produces a cleaner dependency direction: write-side jobs now depend on `phase0.data_access.providers.tushare`, while the old root path remains a compatibility shim.
- `phase0/data_sources.py` has been moved to `phase0.data_access.connectivity`. It is an external-provider read/connectivity layer, not a write-side governance job. The old root path remains a compatibility shim.
- `phase0/throttle.py` has been moved to `phase0.data_access.throttle`. It owns external-provider request throttling and retry pacing, so it belongs beside provider access code; the old root path remains a compatibility shim.
- Financial factor point-in-time audit implementation now lives in `phase0.data_governance.financial_pti`; `scripts/audit_financial_pti.py` is a direct-execution-compatible shim.
- Local history external-snapshot consistency audit implementation now lives in `phase0.data_governance.local_history_consistency`; `scripts/check_local_history_consistency.py` is a direct-execution-compatible shim.
- Universe point-in-time audit implementation now lives in `phase0.data_governance.universe_pit`; `scripts/audit_universe_pit.py` is a compatibility shim for legacy imports.
- Strategy intelligence implementation now lives in the `phase0.intelligence` package. The original collection/import/review/validation API remains exported from `phase0.intelligence`; schema/common helpers, candidate CSV I/O, candidate collection/import, candidate review, and ledger validation now live in dedicated submodules, and Tiingo news probing now lives in `phase0.intelligence.tiingo_news_probe`; `scripts/tiingo_news_probe.py` is a direct-execution-compatible shim.
- `phase0/accounts.py` has been moved to `phase0.execution.accounts`. It owns simulated-account configuration, signal execution simulation, account ledgers, and account database writes; the old root path remains a compatibility shim.
- Account bill HTML and latest-snapshot presentation helpers now live in `phase0.reporting.account_bill`, with execution-layer re-exports kept for compatibility during the transition.
- Strategy bill export implementation now lives in `phase0.reporting.strategy_bill`; `scripts/export_strategy_bill.py` is a direct-execution-compatible shim.
- Strategy bill execution matching and ledger helpers now live in `phase0.execution.strategy_ledger`; `phase0.reporting.strategy_bill` keeps old private-name aliases only for compatibility during the transition.
- Execution effectiveness gate report implementation now lives in `phase0.reporting.execution_effectiveness`; `scripts/export_execution_effectiveness_report.py` is a direct-execution-compatible shim.
- Strategy OOS report implementation now lives in `phase0.reporting.strategy_oos`; `scripts/export_strategy_oos_report.py` is a direct-execution-compatible shim.
- Premarket watchlist/report implementation now lives in `phase0.reporting.premarket_watchlist`; `scripts/export_premarket_watchlist.py` is a direct-execution-compatible shim.
- Strategy period-compare report implementation now lives in `phase0.reporting.strategy_period_compare`; `scripts/export_strategy_period_compare.py` is a direct-execution-compatible shim.
- Market-regime report implementation now lives in `phase0.reporting.market_regime`; `scripts/export_market_regime_report.py` is a direct-execution-compatible shim.
- HK market-history batch-load report implementation now lives in `phase0.reporting.hk_market_history`; `scripts/export_hk_market_history_report.py` is a direct-execution-compatible shim.

## Current Functional Layers

| Layer | Responsibility | Current modules |
| --- | --- | --- |
| `reporting` | Report output paths, run directories, artifact registry, report-export helpers, account bill presentation, strategy bill export orchestration, execution effectiveness gate reporting, continuous OOS reporting, period comparison reporting, market-regime reporting, premarket watchlist/report generation, HK market-history batch-load reporting, Markdown/HTML/CSV writers | `phase0/reporting/paths.py`, `phase0/reporting/registry.py`, `phase0/reporting/writers.py`, `phase0/reporting/exports.py`, `phase0/reporting/account_bill.py`, `phase0/reporting/strategy_bill.py`, `phase0/reporting/execution_effectiveness.py`, `phase0/reporting/strategy_oos.py`, `phase0/reporting/strategy_period_compare.py`, `phase0/reporting/market_regime.py`, `phase0/reporting/premarket_watchlist.py`, `phase0/reporting/hk_market_history.py`, compatibility shims `phase0/report_paths.py`, `phase0/report_registry.py`, `scripts/export_strategy_bill.py`, `scripts/export_execution_effectiveness_report.py`, `scripts/export_strategy_oos_report.py`, `scripts/export_strategy_period_compare.py`, `scripts/export_market_regime_report.py`, `scripts/export_premarket_watchlist.py`, `scripts/export_hk_market_history_report.py`, report-export helper aliases in `phase0/cli.py` |
| `data_governance` | Data quality checks, governance audits, as-of coverage validation, price-adjustment governance, bounded maintenance helpers, write-side backfills, local history maintenance jobs | `phase0/data_governance/quality.py`, `phase0/data_governance/db_health.py`, `phase0/data_governance/index_asof_audit.py`, `phase0/data_governance/index_asof_backfill.py`, `phase0/data_governance/financial_pti.py`, `phase0/data_governance/local_history_consistency.py`, `phase0/data_governance/universe_pit.py`, `phase0/data_governance/adjustment.py`, `phase0/data_governance/import_history.py`, `phase0/data_governance/update_history.py`, `phase0/data_governance/financial_factors.py`, `phase0/data_governance/external_market_history.py`, `phase0/data_governance/backfills/*`, compatibility shims in `phase0/quality.py`, `phase0/db_health.py`, `phase0/index_asof_*.py`, `phase0/adjustment.py`, `phase0/*_backfill.py`, `phase0/import_history.py`, `phase0/financial_factors.py`, `phase0/external_market_history.py`, `scripts/audit_financial_pti.py`, `scripts/audit_universe_pit.py`, `scripts/check_local_history_consistency.py` |
| `data_access/providers` | Local history reads, external provider adapters, and request pacing; it should not own write-side governance jobs | `phase0/data_access/local_history.py`, `phase0/data_access/connectivity.py`, `phase0/data_access/throttle.py`, `phase0/data_access/providers/tushare.py`, `phase0/data_access/providers/external_market.py`, compatibility shims `phase0/local_history.py`, `phase0/data_sources.py`, `phase0/throttle.py`, and `phase0/tushare_source.py` |
| `universe` | Current universe construction and point-in-time universe loading | Stable root module `phase0/universe.py`; no migration planned in this branch |
| `domain/strategies` | Strategy interfaces, strategy implementations, portfolio constraints, execution assumptions that are part of strategy behavior | `phase0/strategies/*`, `phase0/strategies/constraints.py`, compatibility shim `phase0/strategy_constraints.py` |
| `execution` | Simulated accounts, account-level execution simulation, strategy-ledger execution matching, ledgers, account database tables, and execution assumptions | `phase0/execution/accounts.py`, `phase0/execution/strategy_ledger.py`, compatibility shim `phase0/accounts.py` |
| `research` | Walk-forward, admission, overfit checks, factor effectiveness, attribution, diagnostics, holdings exposure rebuilds, participation diagnostics, core coverage audits, research summaries/role cards | `phase0/research/admission/*`, `phase0/research/diagnostics/*`, `phase0/research/attribution/*`, `phase0/research/core_coverage/*`, `phase0/research/holdings/*`, `phase0/research/participation/*`, `phase0/research/summaries/*`, root compatibility shims for migrated research modules, `phase0/walk_forward.py`, `phase0/strategy_admission.py` compatibility shim, remaining heavy `phase0/strategy_*` research modules |
| `intelligence` | Strategy intelligence collection, import, validation, review, external signal/probe scripts | `phase0/intelligence/__init__.py`, `phase0/intelligence/schema.py`, `phase0/intelligence/common.py`, `phase0/intelligence/candidates.py`, `phase0/intelligence/collection.py`, `phase0/intelligence/review.py`, `phase0/intelligence/validation.py`, `phase0/intelligence/tiingo_news_probe.py`, `phase0/intelligence/hk_a_mapping_factors.py`, compatibility shims `scripts/tiingo_news_probe.py` and `scripts/export_hk_a_mapping_factors.py`, LLM/integration scripts |
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

## Seventeenth Slice In This Branch

The seventeenth slice reduces shell bootstrap duplication in the scheduler entrypoints:

- Update `scripts/run_project_scheduler.sh` to reuse `scripts/lib/project_env.sh` for project-root resolution, Python interpreter path, logs directory creation, and `.env` loading.
- Update `scripts/install_dev_cron.sh` to reuse `scripts/lib/project_env.sh` for project-root resolution and logs directory creation.
- Add `tests/test_scheduler_shell_wrappers.py` with fake Python and fake crontab binaries so the scheduler wrapper and cron installer are verified without running real maintenance tasks or changing the user's crontab.

This slice preserves the single cron line, the `maintain status` schema warm-up, the `maintain tick` execution command, `.env` loading, and log-directory behavior. It does not change scheduler task timing, maintenance orchestration, Python business logic, or data writes.

## Eighteenth Slice In This Branch

The eighteenth slice starts splitting the large top-level CLI with a low-risk dashboard command group:

- Add `phase0.cli_commands.dashboard` for `dashboard scan` parser registration and command handling.
- Update `phase0.cli` to delegate dashboard parser setup and execution to the new command module.
- Keep the public command unchanged: `python -m phase0.cli dashboard scan`.
- Update dashboard tests so the existing `cli.main()` smoke path remains covered, while registry monkeypatches target the new command module.

This slice only moves report-dashboard command routing. It does not change report registry scanning, manifest schema, report path policy, strategy commands, maintenance commands, data writes, or generated report artifacts.

## Nineteenth Slice In This Branch

The nineteenth slice continues CLI decomposition with the strategy-intelligence command group:

- Add `phase0.cli_commands.intelligence` for `intelligence collect`, `intelligence import-local`, `intelligence review-candidates`, and `intelligence validate` parser registration and command handling.
- Update `phase0.cli` to delegate intelligence parser setup and execution to the new command module.
- Keep the public commands unchanged: `python -m phase0.cli intelligence ...`.
- Add a handler-level regression test that monkeypatches the new command module and verifies `intelligence validate` argument forwarding plus the error exit code.

This slice only moves strategy-intelligence command routing. It does not change intelligence collection sources, candidate CSV schema, ledger validation rules, review heuristics, report path policy, external API behavior, or generated intelligence artifacts.

## Twentieth Slice In This Branch

The twentieth slice extracts the read-only system status command from the large top-level CLI:

- Add `phase0.cli_commands.system` for `system status` parser registration, system command handling, and maintenance-status summarization.
- Update `phase0.cli` to delegate system parser setup and execution to the new command module.
- Keep `phase0.cli.summarize_system_maintenance_status` available as a compatibility import during the transition.
- Update maintenance-orchestrator CLI tests so monkeypatches target the new command module while still checking the old summary import path.

This slice only moves the read-only system-status route. It does not change `maintain` task execution, maintenance state refresh behavior, status database schema, scheduler timing, long-task controls, report writing, or generated maintenance artifacts.

## Twenty-First Slice In This Branch

The twenty-first slice extracts the maintenance command group from the large top-level CLI:

- Add `phase0.cli_commands.maintenance` for `maintain tick`, `maintain status`, `maintain supervise`, `maintain run`, `maintain stop`, and `maintain resume` parser registration and command handling.
- Update `phase0.cli` to delegate maintenance parser setup and execution to the new command module.
- Update maintenance-orchestrator CLI tests so monkeypatches target the new command module.
- Add a `maintain tick --dry-run` regression test to verify dry-run argument forwarding without starting real tasks.

This slice only moves maintenance command routing. It does not change scheduler timing, maintenance state refresh defaults, long-task process control, shard state transitions, state database schema, generated maintenance reports, or external command names such as `python -m phase0.cli maintain ...`.

## Twenty-Second Slice In This Branch

The twenty-second slice starts extracting report-export command registration from the large top-level CLI:

- Add `phase0.cli_commands.reports` for `bill`, `market-regime`, `oos-report`, `financial-pti`, `universe-pti`, `premarket`, and `execution-gate` parser registration.
- Update `phase0.cli` to delegate those parser definitions to `register_report_export_commands`.
- Keep the command handlers and `_export_phase0_*` helper functions in `phase0.cli` for this slice to avoid a circular import and to preserve existing report-path monkeypatch tests.

This slice only moves argparse registration for report-export commands. It does not change report path generation, report helper implementations, execution profile defaults, generated artifacts, or public command names.

## Twenty-Third Slice In This Branch

The twenty-third slice moves report-export helper implementations into the reporting package:

- Add `phase0.reporting.exports` for `bill`, `market-regime`, `oos-report`, `financial-pti`, `universe-pti`, `premarket`, `brief-account-bill`, and `execution-gate` export helpers.
- Update `phase0.cli` so old `_export_phase0_*` and `_export_brief_account_bill` names remain compatibility aliases over the new reporting functions.
- Update report-output-path tests to call the new reporting module directly, with a narrow compatibility test for the old CLI helper names.

This slice only moves helper ownership. It does not change public CLI commands, report path generation, output filenames, script-level export behavior, or generated artifacts.

## Twenty-Fourth Slice In This Branch

The twenty-fourth slice finishes the top-level report-export command boundary:

- Add `phase0.cli_commands.reports.REPORT_EXPORT_COMMANDS` and `handle_report_export_command`.
- Move top-level handling for `bill`, `market-regime`, `oos-report`, `financial-pti`, `universe-pti`, `premarket`, and `execution-gate` from `phase0.cli` into `phase0.cli_commands.reports`.
- Keep `phase0.cli` as the parser owner and compatibility alias owner for `_export_phase0_*` helper names during the migration.
- Add handler-level tests for argument forwarding and CLI-main delegation.

This slice intentionally does not move `brief premarket`, `brief account-bill`, `daily-brief`, `run_phase0`, watchlist ECS sync, report path generation, or export helper behavior. Those flows still cross delivery, scheduler, and reporting concerns and need separate gates.

## Twenty-Fifth Slice In This Branch

The twenty-fifth slice extracts read-only data-governance audit command routing:

- Add `phase0.cli_commands.data_governance` for `adjustment-audit`, `db-health`, and `index-asof-audit` parser registration and command handling.
- Keep `phase0.cli` as the top-level parser owner and delegate these commands through `DATA_GOVERNANCE_COMMANDS`.
- Add handler-level tests for argument forwarding, `db-health --fail-on` exit-code behavior, and CLI-main delegation.

This slice intentionally does not move write-side commands such as `backfill-index-asof`, `update-history`, `backfill-daily-basic`, or Tushare backfills. It also leaves the shared `_run_db_health_gate` in `phase0.cli` for `run` and `factor-effectiveness` until those command groups get their own migration gates.

## Twenty-Sixth Slice In This Branch

The twenty-sixth slice extracts research-diagnostic command routing for already-migrated strategy research modules:

- Add `phase0.cli_commands.research` for parser registration and command handling for the migrated `strategy-*` research diagnostics:
  `strategy-failure-attribution`, `strategy-market-context`, `strategy-exposure-diagnostic`, `strategy-filter-diagnostic`,
  `strategy-core-reachability-diagnostic`, `strategy-missing-core-audit`, `strategy-holdings-exposure`,
  `strategy-fold-attribution`, `strategy-participation-overlay`, `strategy-csi300-attribution`, and `strategy-role-card`.
- Keep `phase0.cli` as the top-level parser owner and delegate these commands through `RESEARCH_COMMANDS`.
- Add handler-level tests for parser registration, local-history setup, path forwarding, run-log command forwarding, and CLI-main delegation.

This slice intentionally does not move `strategy-admission`, `factor-effectiveness`, or `overfit-diagnostic`. It also does not change research algorithms, strategy parameters, report path policy, generated artifact names, or legacy root import shims.

## Twenty-Seventh Slice In This Branch

The twenty-seventh slice extracts delivery/watchlist command routing from the large top-level CLI:

- Add `phase0.cli_commands.delivery` for `brief daily`, `brief daily-brief`, `brief watchlist`, `brief premarket`, `brief account-bill`, and the legacy top-level `daily-brief` parser/handler.
- Move the watchlist/daily-brief pipeline and ECS watchlist mirror helper into the delivery command module.
- Add `phase0.cli_commands.output.print_manual_history_update_result` so delivery and `update-history` can share the same console rendering without creating a reverse dependency.
- Keep `phase0.cli.run_watchlist_pipeline`, `phase0.cli.run_daily_brief_pipeline`, and old `_export_*` helper names available as compatibility imports during the transition.
- Add delivery CLI tests for parser registration, watchlist path copying, check-only behavior, premarket/account-bill forwarding, and CLI-main delegation.

This slice does not change watchlist selection logic, simulated account behavior, report path policy, ECS sync environment variables, public command names, or generated artifact names. It also keeps the top-level `premarket` report-export command in `phase0.cli_commands.reports`; only the nested `brief premarket` route moves here.

## Twenty-Eighth Slice In This Branch

The twenty-eighth slice extracts write-side data update/import/backfill command routing from the large top-level CLI:

- Add `phase0.cli_commands.data_update` for `update-history`, `update-financials`, `update-us-market-history`, `update-hk-market-history`, `import-history`, `import-index-history`, `build-universe`, `backfill-daily-basic`, `backfill-adjustment-factors`, `backfill-index-asof`, `backfill-tushare-history`, and `backfill-tushare-financials`.
- Move parser registration, console output, argument forwarding, progress rendering, and exit-code mapping into the data-update command module.
- Keep `phase0.cli` as the top-level parser owner and delegate these commands through `DATA_UPDATE_COMMANDS`.
- Keep `phase0.cli._format_duration`, `phase0.cli._print_tushare_financial_progress`, and `phase0.cli._print_manual_history_update_result` available as compatibility imports during the transition.
- Add handler-level tests for parser registration, update-history/update-financials universe rebuild behavior, backfill argument forwarding, missing-token exit codes, progress callback forwarding, external market updates, imports, build-universe, and CLI-main delegation.

This slice does not move `phase0/update_history.py`, `phase0/tushare_history_backfill.py`, `phase0/daily_basic_backfill.py`, `phase0/adjustment_backfill.py`, `phase0/financial_factors.py`, `phase0/import_history.py`, `phase0/external_market_history.py`, or `phase0/universe.py`. It is a CLI adapter move only and does not change database write behavior, Tushare payloads, report paths, command names, or generated artifact names.

## Twenty-Ninth Slice In This Branch

The twenty-ninth slice extracts strategy research run command routing from the large top-level CLI:

- Add `phase0.cli_commands.strategy_research` for `overfit-diagnostic`, `strategy-admission`, and `factor-effectiveness` parser registration and command handling.
- Move the walk-forward trace printer into that command module and add `phase0.cli_commands.gates` for the shared database-health gate used by both `run` and factor-effectiveness.
- Keep `phase0.cli._print_walk_forward_trace` and `phase0.cli._run_db_health_gate` available as compatibility imports during the transition.
- Keep `phase0.cli` as the top-level parser owner and delegate these commands through `STRATEGY_RESEARCH_COMMANDS`.
- Add handler-level tests for parser registration, overfit path forwarding, admission preset/strategy/trace forwarding, factor-effectiveness health gating, CLI-main delegation, and old helper-name compatibility.

This slice does not move `phase0/strategy_admission.py`, `phase0/overfit.py`, `phase0/factor_effectiveness.py`, `phase0/walk_forward.py`, or any strategy implementation. It is a CLI adapter move only and does not change walk-forward/admission algorithms, thresholds, report paths, command names, generated artifact names, or data-write behavior.

## Thirtieth Slice In This Branch

The thirtieth slice prepares data-governance module migration by extracting shared table helpers that were previously borrowed from `phase0.update_history`:

- Add `phase0.data_governance.sql.safe_identifier` and `to_sql_value`.
- Add `phase0.data_governance.daily_basic.ensure_daily_basic_table` and `upsert_daily_basic_rows`.
- Keep `phase0.update_history._safe_identifier`, `_to_sql_value`, `_ensure_daily_basic_table`, and `_upsert_daily_basic_rows` as compatibility aliases during the transition.
- Update effective project imports in daily-basic backfill, adjustment backfill, Tushare history backfill, and index as-of backfill so they no longer depend on `phase0.update_history` private helpers.
- Add helper tests for identifier validation, missing-value conversion, daily-basic table upsert behavior, and old private-name compatibility.

This slice does not move `phase0/update_history.py`, `phase0/daily_basic_backfill.py`, `phase0/adjustment_backfill.py`, or `phase0/tushare_history_backfill.py` yet. It only creates the shared helper layer needed to move those write-side data-governance jobs safely in later slices.

## Thirty-First Slice In This Branch

The thirty-first slice moves the first write-side backfill jobs into the data-governance package:

- Move `phase0/daily_basic_backfill.py` to `phase0.data_governance.backfills.daily_basic`.
- Move `phase0/adjustment_backfill.py` to `phase0.data_governance.backfills.adjustment`.
- Keep root-level `phase0.daily_basic_backfill` and `phase0.adjustment_backfill` as module alias shims so old imports and monkeypatches remain compatible during the transition.
- Update effective project imports in the data-update CLI and Tushare history backfill to use the new package paths.
- Add import compatibility tests for new backfill paths and old root-path aliases.

This slice does not change backfill algorithms, database schemas, Tushare payloads, throttling behavior, CLI command names, or generated artifact paths. It also does not move the larger `phase0/tushare_history_backfill.py` or `phase0/update_history.py` jobs yet.

## Thirty-Second Slice In This Branch

The thirty-second slice moves external data connectivity helpers into the data-access layer:

- Move `phase0/data_sources.py` to `phase0.data_access.connectivity`.
- Keep root-level `phase0.data_sources` as a module alias shim so old imports and monkeypatches remain compatible during the transition.
- Update effective project imports in CLI, walk-forward, external market history, report writers, and Tiingo probe script to use `phase0.data_access.connectivity`.
- Add import compatibility tests for the new connectivity path and old root-path alias.

This slice does not change provider request payloads, fallback order, cache behavior, CLI command names, report paths, data writes, or strategy research behavior. It also does not move `phase0/update_history.py` or `phase0/tushare_history_backfill.py`; those are write-side jobs and need further helper extraction before a safe package move.

## Thirty-Third Slice In This Branch

The thirty-third slice moves the remaining Phase 0 run command group out of the top-level CLI module:

- Add `phase0.cli_commands.phase0_run` for `run` and `cost-sensitivity` parser registration and command handling.
- Move `run_phase0`, `run_phase0_cost_sensitivity`, `_parse_cost_scenario`, and `_configured_cost_scenarios` into the command module.
- Keep `phase0.cli.run_phase0`, `phase0.cli.run_phase0_cost_sensitivity`, `phase0.cli._parse_cost_scenario`, and `phase0.cli._configured_cost_scenarios` as compatibility imports during the transition.
- Keep the CN database health gate before `phase0 run` with the same `scope="cn"`, `fail_on="error"`, and `label="Phase 0 run"` settings.
- Update targeted tests so ordinary Phase 0 run behavior monkeypatches the new command module, while a small compatibility test checks the old names.

This slice does not change command names, console messages, output report paths, cost scenario parsing semantics, db-health gate policy, walk-forward behavior, strategy bill export behavior, data-source connectivity behavior, or generated artifact names.

## Thirty-Fourth Slice In This Branch

The thirty-fourth slice starts reducing research metric duplication and strategy-to-walk-forward coupling:

- Add `phase0.research.metrics` for the shared walk-forward-compatible `annualized_return`, `sharpe`, `max_drawdown`, and `calc_metrics` helpers.
- Update `phase0.walk_forward` so old private helper names remain compatibility aliases over `phase0.research.metrics`.
- Update strategy implementations and the premarket export script to import `_calc_metrics` from `phase0.research.metrics` instead of the large `phase0.walk_forward` module.
- Add compatibility and formula tests for the metrics helpers.

This slice does not change metric formulas, annualization assumptions, strategy algorithms, training parameter search behavior, report paths, or generated artifact names. Other metric implementations with intentionally different missing-value or `ddof` semantics remain in place until their owning report flow gets a separate compatibility gate.

## Thirty-Fifth Slice In This Branch

The thirty-fifth slice moves the broad Tushare history and financial backfill job into the data-governance package:

- Move `phase0/tushare_history_backfill.py` to `phase0.data_governance.backfills.tushare_history`.
- Keep root-level `phase0.tushare_history_backfill` as a module alias shim so old imports and monkeypatches remain compatible during the transition.
- Update the data-update CLI to import `backfill_tushare_history_from_config` and `backfill_tushare_financials_from_config` from the new package path.
- Extend backfill import compatibility tests to cover `TushareHistoryBackfillResult`, `TushareFinancialBackfillResult`, and both CLI-callable backfill functions.

This slice does not change Tushare request payloads, throttling, retry behavior, database schemas, upsert behavior, audit report paths, CLI command names, generated artifact names, or financial-factor normalization logic.

## Thirty-Sixth Slice In This Branch

The thirty-sixth slice moves the A-share manual history incremental update job into the data-governance package:

- Move `phase0/update_history.py` to `phase0.data_governance.update_history`.
- Keep root-level `phase0.update_history` as a module alias shim so old imports and monkeypatches remain compatible during the transition.
- Update effective project imports in data-update CLI, Phase 0 run CLI, delivery CLI, and daily coverage eligibility tests to use the new package path.
- Extend data-governance compatibility tests so `ManualHistoryUpdateResult`, `update_manual_history_from_config`, and the old private helper names remain available through the old root path.

This slice does not change data-source fallback order, AkShare/Tushare request behavior, SQLite schemas, upsert behavior, universe rebuild policy, CLI command names, console output, generated artifact paths, or freshness/coverage thresholds.

## Thirty-Seventh Slice In This Branch

The thirty-seventh slice moves the US/HK external market history maintenance module into the data-governance package:

- Move `phase0/external_market_history.py` to `phase0.data_governance.external_market_history`.
- Keep root-level `phase0.external_market_history` as a module alias shim so old imports and monkeypatches remain compatible during the transition.
- Update effective project imports in data-update CLI, Phase 0 run CLI, walk-forward, factor effectiveness, research diagnostics, and report scripts to use the new package path.
- Add an import compatibility test covering `MarketHistoryUpdateResult`, US/HK configure/update functions, and `load_us_daily_from_history`.

This slice does not change US/HK provider selection, yfinance/Tushare-HK fallback behavior, SQLite schemas, upsert behavior, runtime fallback policy, CLI command names, generated artifact paths, or cross-market signal construction.

## Thirty-Eighth Slice In This Branch

The thirty-eighth slice moves the local manual history import job into the data-governance package:

- Move `phase0/import_history.py` to `phase0.data_governance.import_history`.
- Keep root-level `phase0.import_history` as a module alias shim so old imports and monkeypatches remain compatible during the transition.
- Update the data-update CLI to import `import_from_config` and `import_index_history_from_config` from the new package path.
- Add an import compatibility test covering `ImportResult`, `IndexImportResult`, and both CLI-callable import functions.

This slice does not change zip parsing, local-history database schemas, table rebuild behavior, symbol normalization, CLI command names, generated artifact paths, or import filtering by start date.

## Thirty-Ninth Slice In This Branch

The thirty-ninth slice moves the quarterly financial factor maintenance module into the data-governance package:

- Move `phase0/financial_factors.py` to `phase0.data_governance.financial_factors`.
- Keep root-level `phase0.financial_factors` as a module alias shim so old imports and monkeypatches remain compatible during the transition.
- Update the data-update CLI and Tushare financial backfill job to import update/table helpers from the new package path.
- Add an import compatibility test covering `FinancialFactorUpdateResult`, `update_financial_factors_from_config`, `ensure_financial_factor_table`, and `financial_factor_coverage`.

This slice does not change EastMoney request behavior, AkShare throttling, financial factor normalization, SQLite schemas, upsert behavior, CLI command names, generated artifact paths, or coverage thresholds.

## Fortieth Slice In This Branch

The fortieth slice moves the SQLite-backed local history read layer into the data-access package:

- Move `phase0/local_history.py` to `phase0.data_access.local_history`.
- Keep root-level `phase0.local_history` as a module alias shim so old imports and monkeypatches remain compatible during the transition.
- Update effective imports in CLI command modules, walk-forward, universe construction, strategy implementations, data-governance jobs, provider adapters, research diagnostics, report scripts, and ordinary tests to use the new package path.
- Add an import compatibility test covering `LocalHistorySettings`, symbol normalization, configuration, local DB path resolution, daily/index history reads, and point-in-time snapshot loading.

This slice does not change local SQLite schemas, price-adjustment modes, point-in-time snapshot logic, symbol normalization behavior, runtime fallback policy, CLI command names, generated artifact paths, or strategy algorithms.

## Forty-First Slice In This Branch

The forty-first slice moves the strategy overfit diagnostic into the research diagnostics package:

- Move `phase0/overfit.py` to `phase0.research.diagnostics.overfit`.
- Keep root-level `phase0.overfit` as a module alias shim so old imports and monkeypatches remain compatible during the transition.
- Update effective imports in the admission runner, strategy-research CLI command module, and ordinary admission tests to use the new package path.
- Add an import compatibility test covering `OverfitDiagnosticResult`, `run_overfit_diagnostic`, and selected scoring helpers.

This slice does not change overfit scoring rules, last-fold lift detection, report filenames, report paths, admission thresholds, CLI command names, generated artifacts, or strategy algorithms.

## Forty-Second Slice In This Branch

The forty-second slice moves the AkShare request pacing helper into the data-access package:

- Move `phase0/throttle.py` to `phase0.data_access.throttle`.
- Keep root-level `phase0.throttle` as a module alias shim so old imports and monkeypatches remain compatible during the transition.
- Update effective imports in data-access connectivity, data-governance jobs, universe construction, walk-forward, core-coverage diagnostics, holdings exposure, Phase 0 run CLI commands, and the HK/A mapping export script.
- Add an import compatibility test proving the old and new paths share the same `akshare_throttle` singleton.

This slice does not change throttle defaults, retry behavior, sleep timing formulas, AkShare/Tushare fallback logic, CLI command names, generated artifacts, database writes, or strategy algorithms.

## Forty-Third Slice In This Branch

The forty-third slice moves the factor-effectiveness diagnostic into the research diagnostics package:

- Move `phase0/factor_effectiveness.py` to `phase0.research.diagnostics.factor_effectiveness`.
- Keep root-level `phase0.factor_effectiveness` as a module alias shim so old imports and monkeypatches remain compatible during the transition.
- Update the strategy-research CLI command module to import `run_factor_effectiveness_report` from the new package path.
- Add an import compatibility test covering the result dataclass, factor spec dataclass, factor spec list, and CLI-callable report function.

This slice does not change factor formulas, point-in-time financial factor enrichment, daily-basic merging, group return or rank-IC calculations, report filenames, report paths, CLI command names, generated artifacts, or strategy algorithms.

## Forty-Fourth Slice In This Branch

The forty-fourth slice moves price-adjustment governance into the data-governance package:

- Move `phase0/adjustment.py` to `phase0.data_governance.adjustment`.
- Keep root-level `phase0.adjustment` as a module alias shim so old imports and monkeypatches remain compatible during the transition.
- Update effective imports in the data-governance CLI, local-history qfq_asof loader, manual history update job, adjustment backfill job, and broad Tushare history backfill job.
- Add an import compatibility test covering the audit result dataclass, adjustment factor table helpers, qfq_asof construction helpers, and audit entrypoint.

This slice does not change adjustment factor schemas, qfq_asof formulas, qfq_current comparison logic, audit report filenames, report paths, CLI command names, generated artifacts, database writes, or strategy algorithms.

## Forty-Fifth Slice In This Branch

The forty-fifth slice extracts pure admission gate helpers from the admission runner:

- Add `phase0.research.admission.gate` for admission gate resolution, diagnostic suite resolution, and overfit-risk blocking policy.
- Keep `phase0.strategy_admission._resolve_admission_gate`, `_resolve_diagnostic_suites`, and `_overfit_blocks_admission` as compatibility aliases over the new functions.
- Update ordinary strategy-admission tests and failure-attribution code to use the new gate helper path where they do not need the runner itself.
- Add import compatibility tests proving the old runner-private names and new helper names are the same function objects.

This slice does not change admission thresholds, admission actions, window matrix construction, constraint review logic, walk-forward execution, overfit execution, report filenames, report paths, CLI command names, generated artifacts, or strategy algorithms.

## Forty-Sixth Slice In This Branch

The forty-sixth slice extracts admission review calculations from the admission runner:

- Add `phase0.research.admission.review` for price-adjustment status attachment, window-matrix construction, window metrics, constraint review, admission action selection, and related count/numeric helpers.
- Keep `phase0.strategy_admission` as the runner and re-export the old private helper names as compatibility aliases over the new review functions.
- Update failure attribution and ordinary admission tests to import review helpers from the new package path when they do not need the runner itself.
- Add import compatibility tests proving the old runner-private names and new review helper names are the same function objects.

This slice does not change `run_strategy_admission`, strategy scope resolution, walk-forward execution, overfit execution, report writing, governance report writing, report filenames, report paths, CLI command names, generated artifacts, thresholds, or strategy algorithms.

## Forty-Seventh Slice In This Branch

The forty-seventh slice moves simulated-account execution into the execution package:

- Move `phase0/accounts.py` to `phase0.execution.accounts`.
- Keep root-level `phase0.accounts` as a module alias shim so old imports and monkeypatches remain compatible during the transition.
- Update effective imports in walk-forward, report exports, premarket watchlist export, and ordinary strategy-constraint tests to use the new execution package path.
- Add import compatibility tests covering the account config/result API, signal execution entrypoint, simulated-account loading, and account bill export.

This slice intentionally kept account bill HTML generation in `phase0.execution.accounts` during the package move to avoid mixing two behaviorally sensitive edits. It does not change execution price modes, lot rounding, limit/suspension checks, participation-rate logic, ledger/database schemas, report filenames, report paths, CLI command names, generated artifacts, or strategy algorithms.

## Forty-Eighth Slice In This Branch

The forty-eighth slice separates account-bill presentation from simulated-account execution:

- Add `phase0.reporting.account_bill` for money/percentage/number formatting, latest account snapshot loading, HTML table rendering, and account bill HTML export.
- Keep `phase0.execution.accounts` re-exporting the account-bill helpers during the transition, so old callers remain compatible.
- Update report exports and premarket watchlist export to import presentation helpers from the reporting package instead of the execution package.
- Lighten `phase0.reporting.__init__` so importing submodules such as `phase0.reporting.account_bill` does not eagerly import heavy report-export functions and create execution/reporting import cycles.
- Add import compatibility tests proving execution-layer account-bill re-exports point to the reporting functions.

This slice does not change account bill HTML content, ledger/database schemas, latest-snapshot SQL, report filenames, report paths, CLI command names, generated artifacts, execution rules, or strategy algorithms.

## Forty-Ninth Slice In This Branch

The forty-ninth slice moves the strategy bill exporter out of `scripts/` and into the reporting package:

- Move `scripts/export_strategy_bill.py` implementation to `phase0.reporting.strategy_bill`.
- Keep `scripts/export_strategy_bill.py` as a direct-execution-compatible module alias shim; `python scripts/export_strategy_bill.py --help` continues to work.
- Update effective imports in report exports, OOS report export, execution-effectiveness export, premarket watchlist export, period compare, and low-turnover wrappers to use `phase0.reporting.strategy_bill`.
- Preserve existing legacy helper names such as `_execution_settings`, `_panel_cache_key`, `_load_or_build_panel`, `_strategy_report_cfg`, and `_default_report_strategy_id` as compatibility API because other scripts still depend on them.
- Add import and direct-script help tests for the new reporting module and old script shim.

This slice is an implementation move only. It does not change strategy bill calculations, panel cache key semantics, walk-forward folds, execution assumptions, output schemas, report filenames, report paths, CLI arguments, generated artifacts, or strategy algorithms. Later slices can split execution-heavy helpers into `phase0.execution` and research-heavy panel/fold helpers into `phase0.research`.

## Fiftieth Slice In This Branch

The fiftieth slice separates strategy-bill execution matching from report export orchestration:

- Add `phase0.execution.strategy_ledger` for execution settings, limit-up/down bands, lot rounding, execution-frame preparation, trade blocking, order-record construction, and fold ledger simulation.
- Keep `phase0.reporting.strategy_bill` as the strategy bill export orchestrator and re-export the old private helper names as compatibility aliases over the execution package.
- Update execution-effectiveness and premarket watchlist scripts to import execution settings and price-limit helpers from `phase0.execution.strategy_ledger`.
- Add import compatibility tests proving the old strategy-bill private names and new execution helper names are the same function objects.

This slice does not change strategy signal generation, walk-forward fold construction, panel cache keys, bill CSV schemas, daily asset schemas, report filenames, report paths, CLI arguments, generated artifacts, execution assumptions, or strategy algorithms. Research-heavy panel loading and fold orchestration remain in `phase0.reporting.strategy_bill` until a later slice has focused tests for moving them.

## Fifty-First Slice In This Branch

The fifty-first slice moves the execution-effectiveness gate report out of `scripts/` and into the reporting package:

- Move `scripts/export_execution_effectiveness_report.py` implementation to `phase0.reporting.execution_effectiveness`.
- Keep `scripts/export_execution_effectiveness_report.py` as a direct-execution-compatible module alias shim; `python scripts/export_execution_effectiveness_report.py --help` continues to work.
- Update `phase0.reporting.exports` and `scripts/export_strategy_oos_report.py` to import the shared execution-effectiveness helpers from the new reporting module.
- Update execution-effectiveness path tests to patch the new reporting module and add legacy script alias/help compatibility tests.

This slice does not change execution gate metrics, live/research profile semantics, output schemas, report filenames, report paths, CLI arguments, generated artifacts, execution assumptions, or strategy algorithms. The OOS report still reuses profile helper functions from this module; if that reuse grows further, a later slice can extract a small shared profile helper.

## Fifty-Second Slice In This Branch

The fifty-second slice moves the continuous strategy OOS report out of `scripts/` and into the reporting package:

- Move `scripts/export_strategy_oos_report.py` implementation to `phase0.reporting.strategy_oos`.
- Keep `scripts/export_strategy_oos_report.py` as a direct-execution-compatible module alias shim; `python scripts/export_strategy_oos_report.py --help` continues to work.
- Update `phase0.reporting.exports` and the historical low-turnover OOS wrapper to import from `phase0.reporting.strategy_oos`.
- Add legacy script alias/help compatibility tests for the new reporting module.

This slice does not change OOS curve construction, benchmark comparison, output schemas, report filenames, report paths, CLI arguments, generated artifacts, execution assumptions, or strategy algorithms.

## Fifty-Third Slice In This Branch

The fifty-third slice moves the premarket watchlist/report implementation out of `scripts/` and into the reporting package:

- Move `scripts/export_premarket_watchlist.py` implementation to `phase0.reporting.premarket_watchlist`.
- Keep `scripts/export_premarket_watchlist.py` as a direct-execution-compatible module alias shim; `python scripts/export_premarket_watchlist.py --help` continues to work.
- Update `phase0.reporting.exports` and premarket tests to import and monkeypatch the new reporting module.
- Add legacy script alias/help compatibility tests for the new reporting module.

This slice does not change premarket signal construction, simulated-account ledger behavior, latest-report output policy, panel cache semantics, output schemas, report filenames, report paths, CLI arguments, generated artifacts, execution assumptions, or strategy algorithms.

## Fifty-Fourth Slice In This Branch

The fifty-fourth slice moves the strategy period-compare report out of `scripts/` and into the reporting package:

- Move `scripts/export_strategy_period_compare.py` implementation to `phase0.reporting.strategy_period_compare`.
- Keep `scripts/export_strategy_period_compare.py` as a direct-execution-compatible module alias shim; `python scripts/export_strategy_period_compare.py --help` continues to work.
- Update the historical low-turnover period-compare wrapper to call the new reporting module.
- Add legacy script alias/help compatibility tests for the new reporting module.

This slice does not change period comparison metrics, output schemas, report filenames, report paths, CLI arguments, generated artifacts, execution assumptions, or strategy algorithms.

## Fifty-Fifth Slice In This Branch

The fifty-fifth slice moves the market-regime report out of `scripts/` and into the reporting package:

- Move `scripts/export_market_regime_report.py` implementation to `phase0.reporting.market_regime`.
- Keep `scripts/export_market_regime_report.py` as a direct-execution-compatible module alias shim; `python scripts/export_market_regime_report.py --help` continues to work.
- Update `phase0.reporting.exports` and report-path tests to import and monkeypatch the new reporting module.
- Add legacy script alias/help compatibility tests for the new reporting module.

This slice does not change regime classification, metrics, output schemas, report filenames, report paths, CLI arguments, generated artifacts, execution assumptions, or strategy algorithms.

## Fifty-Sixth Slice In This Branch

The fifty-sixth slice moves the universe point-in-time audit into the data-governance package:

- Move `scripts/audit_universe_pit.py` implementation to `phase0.data_governance.universe_pit`.
- Keep `scripts/audit_universe_pit.py` as a module alias shim for legacy imports.
- Update `phase0.reporting.exports` and report-path tests to import and monkeypatch the new data-governance module.
- Add legacy import compatibility tests for the new module.

This slice does not change point-in-time universe loading, listing-boundary checks, HTML output schema, report paths, CLI command names, generated artifacts, or strategy algorithms.

## Fifty-Seventh Slice In This Branch

The fifty-seventh slice moves the financial factor point-in-time audit into the data-governance package:

- Move `scripts/audit_financial_pti.py` implementation to `phase0.data_governance.financial_pti`.
- Keep `scripts/audit_financial_pti.py` as a direct-execution-compatible module alias shim; `python scripts/audit_financial_pti.py --help` continues to work.
- Update `phase0.reporting.exports` and report-path tests to import and monkeypatch the new data-governance module.
- Add legacy import/help compatibility tests for the new module.

This slice does not change financial PIT rules, table reads, summary/sample/html output schemas, report paths, CLI command names, generated artifacts, or strategy algorithms.

## Fifty-Eighth Slice In This Branch

The fifty-eighth slice moves the local-history external snapshot consistency audit into the data-governance package:

- Move `scripts/check_local_history_consistency.py` implementation to `phase0.data_governance.local_history_consistency`.
- Keep `scripts/check_local_history_consistency.py` as a direct-execution-compatible module alias shim; `python scripts/check_local_history_consistency.py --help` continues to work.
- Add legacy import/help compatibility tests for the new module.
- Keep it outside `db-health` for now because it requires a user-supplied external snapshot file and is not a default scheduled gate.

This slice does not change comparison logic, tolerances, CSV/HTML output schemas, report paths, CLI arguments, generated artifacts, or database writes.

## Fifty-Ninth Slice In This Branch

The fifty-ninth slice separates external market provider fetching from external market history governance:

- Add `phase0.data_access.providers.external_market` for yfinance, AkShare-HK, and Tushare-HK daily-bar provider dispatch.
- Update `phase0.data_governance.external_market_history` to call the provider adapter while retaining update orchestration, SQLite schema/upsert, source audit, coverage checks, and local-history reads.
- Keep `update-us-market-history` and `update-hk-market-history` commands routed through `data_governance`, because they read external data and then mutate local SQLite databases.
- Add no-network provider dispatch tests for yfinance HK symbol conversion and HK provider routing.

This slice does not change provider selection, provider request payloads, SQLite schemas, upsert behavior, coverage thresholds, CLI command names, report paths, generated artifacts, or cross-market signal construction.

## Sixtieth Slice In This Branch

The sixtieth slice turns strategy intelligence into a package and moves the Tiingo news probe implementation into it:

- Move `phase0/intelligence.py` to `phase0/intelligence/__init__.py` so existing `from phase0.intelligence import ...` callers keep working.
- Move `scripts/tiingo_news_probe.py` implementation to `phase0.intelligence.tiingo_news_probe`.
- Keep `scripts/tiingo_news_probe.py` as a direct-execution-compatible module alias shim.
- Update tests to exercise the new module path while retaining explicit old-script compatibility tests.

This slice does not change intelligence ledger schemas, collection/review behavior, Tiingo request payloads, report paths, CLI command names, or generated artifacts.

## Sixty-First Slice In This Branch

The sixty-first slice moves the HK market-history batch-load report into the reporting package:

- Move `scripts/export_hk_market_history_report.py` implementation to `phase0.reporting.hk_market_history`.
- Keep `scripts/export_hk_market_history_report.py` as a direct-execution-compatible module alias shim.
- Add import/help compatibility tests plus a SQLite-backed `build_report` behavior test.

This slice does not change HK history table reads, summary calculations, Markdown output schema, default report path, CLI arguments, generated artifacts, or market-history update behavior.

## Sixty-Second Slice In This Branch

The sixty-second slice moves the HK-to-A-share mapping factor probe into the intelligence package:

- Move `scripts/export_hk_a_mapping_factors.py` implementation to `phase0.intelligence.hk_a_mapping_factors`.
- Keep `scripts/export_hk_a_mapping_factors.py` as a direct-execution-compatible module alias shim.
- Add import/help compatibility tests and no-network normalization tests for AH comparison and HSGT history.

This slice does not change AKShare calls, output filenames, report paths, generated CSV/HTML schemas, or whether HK-A mapping is treated as research-only external signal exploration.

## Sixty-Third Slice In This Branch

The sixty-third slice finishes the strategy-bill execution ledger boundary:

- Move `strategy_bill._load_bfq_execution_price_frame` into `phase0.execution.strategy_ledger.load_bfq_execution_price_frame`.
- Keep `phase0.reporting.strategy_bill._load_bfq_execution_price_frame` as a compatibility alias for existing private imports.
- Add execution-ledger tests for raw-price loading, missing required columns, and no-raw-row fallback behavior.

This slice does not change account matching, execution price semantics, bfq_raw lookup behavior, report output paths, generated bill schemas, strategy parameters, or cost assumptions.

## Sixty-Fourth Slice In This Branch

The sixty-fourth slice extracts admission report writing from the admission runner:

- Add `phase0.research.admission.reports` for admission Markdown writers, governance-report writers, command hints, artifact-name helpers, and local formatting helpers.
- Keep `phase0.strategy_admission` as the admission runner and re-export the old private helper names for compatibility.
- Add import compatibility tests for the new report helper path and old runner-private aliases.

This slice does not change `run_strategy_admission`, walk-forward execution, overfit execution, admission gates, matrix/review calculations, report filenames, report paths, CLI command names, generated artifact schemas, or strategy algorithms.

## Sixty-Fifth Slice In This Branch

The sixty-fifth slice moves the strategy-admission runner into the research admission package:

- Add `phase0.research.admission.runner` for `StrategyAdmissionResult` and `run_strategy_admission`.
- Update the strategy-research CLI command module to import the runner from the new package path.
- Turn `phase0.strategy_admission` into a compatibility export module for the runner and the previously migrated private helper aliases.
- Move ordinary runner monkeypatch tests to the new runner path and add explicit old-path compatibility tests.

This slice does not change walk-forward execution, overfit execution, admission gates, matrix/review calculations, report writers, report filenames, report paths, CLI command names, generated artifact schemas, thresholds, or strategy algorithms.

## Sixty-Sixth Slice In This Branch

The sixty-sixth slice splits the strategy-intelligence validation boundary out of the package root:

- Add `phase0.intelligence.schema` for ledger/RAG schema constants and intelligence result dataclasses.
- Add `phase0.intelligence.common` for shared path/date/text helpers used by collection, review, and validation.
- Add `phase0.intelligence.validation` for ledger and RAG manifest validation.
- Keep `phase0.intelligence` exporting the original public validation API and old private validation helper aliases for compatibility.
- Add import compatibility tests for the new validation module and old package-root aliases.

This slice does not change intelligence CLI commands, ledger CSV columns, RAG manifest columns, validation rules, report filenames, report paths, generated artifact schemas, collection behavior, review behavior, or online source fetching.

## Sixty-Seventh Slice In This Branch

The sixty-seventh slice splits candidate review out of the strategy-intelligence package root:

- Add `phase0.intelligence.candidates` for candidate and review CSV read/write helpers.
- Add `phase0.intelligence.review` for rule-based candidate review suggestions and review Markdown generation.
- Keep `phase0.intelligence` exporting `review_intelligence_candidates` plus the old private review/candidate helper aliases for compatibility.
- Add import compatibility tests for candidate CSV helpers and review helpers.

This slice does not change intelligence CLI commands, candidate CSV columns, review CSV columns, review heuristics, review report wording, report filenames, report paths, generated artifact schemas, collection behavior, validation behavior, or online source fetching.

## Sixty-Eighth Slice In This Branch

The sixty-eighth slice splits strategy-intelligence collection and local import out of the package root:

- Add `phase0.intelligence.collection` for candidate row construction, local source scanning, RSS/arXiv/OpenAlex/Crossref metadata collection, and collect/import report writing.
- Keep `phase0.intelligence` as a compatibility export surface for `collect_intelligence`, `import_local_intelligence`, and the old private collection helper aliases.
- Add import compatibility tests for the new collection module and old package-root aliases.

This slice does not change intelligence CLI commands, local import behavior, online source request URLs or parameters, candidate CSV columns, collect/import report wording, report filenames, report paths, generated artifact schemas, review behavior, validation behavior, or Tiingo/HK-A probe behavior.

## Sixty-Ninth Slice In This Branch

The sixty-ninth slice extracts pure Tushare backfill report helpers from the broad write-side backfill job:

- Add `phase0.data_governance.backfills.tushare_history_reports` for Tushare history/financial report column schemas, report-path builders, detail CSV/Markdown writers, summary append rendering, and summary row builders.
- Keep `phase0.data_governance.backfills.tushare_history` as the write-side orchestration module and retain the old private helper aliases for compatibility.
- Add report-helper import compatibility tests and a missing-token behavior test that calls `backfill_tushare_history_from_config` against a temporary SQLite database and verifies audit/summary reports are still written without touching real Tushare or production data.

This slice does not change Tushare API request payloads, provider selection, token checks, SQLite schemas, upsert behavior, task-table state transitions, rate limiting, retry behavior, CLI command names, generated report filenames, generated artifact schemas, or history/financial audit SQL queries.

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
| Annualized return / Sharpe / drawdown helpers | `research.metrics`, selected compatibility aliases in `walk_forward.py`, OOS/report scripts, market-regime scripts | Continue migrating only when matching NaN and annualization behavior with tests |
| Markdown/HTML table writers | Several strategy/report scripts | Add small `reporting.tables` helpers; do not introduce a large templating framework |
| Large CLI file | `phase0/cli.py` | Split by command group after output paths are stable |
| Strategy bill research helpers | `phase0.reporting.strategy_bill` | Execution matching has moved to `phase0.execution.strategy_ledger`; split remaining panel/fold orchestration into `phase0.research` only after focused tests exist |
| Large execution/report scripts | Remaining report and audit scripts under `scripts/` | `scripts/export_execution_effectiveness_report.py`, `scripts/export_strategy_oos_report.py`, `scripts/export_strategy_period_compare.py`, `scripts/export_market_regime_report.py`, and `scripts/export_premarket_watchlist.py` are now thin shims over reporting modules; move remaining large implementations into packages only when ownership and tests are clear |
| Data audit scripts | None with clear immediate migration benefit | `scripts/audit_financial_pti.py`, `scripts/audit_universe_pit.py`, and `scripts/check_local_history_consistency.py` are now shims over data-governance modules; only move future audit scripts when ownership and CLI compatibility are clear |
| Similar low-turnover wrappers | `scripts/export_low_turnover_*` | Consolidate to strategy-id based wrappers after current users are mapped |
| External probe scripts | None with clear immediate migration benefit | `scripts/tiingo_news_probe.py` is now a shim over `phase0.intelligence.tiingo_news_probe`; `scripts/export_hk_market_history_report.py` is now a shim over `phase0.reporting.hk_market_history`; `scripts/export_hk_a_mapping_factors.py` is now a shim over `phase0.intelligence.hk_a_mapping_factors` |
| Developer/agent helpers | `scripts/cloe_*.sh`, `scripts/openclaw_agent.sh`, `scripts/deepseek_agent_mcp.py`, `scripts/install_dev_cron.sh`, `scripts/lib/*` | Keep under `scripts/` as local developer/ops tooling; do not fold into runtime business packages |
| Provider/update coupling | Local history readers, external market history jobs, update jobs, Tushare write-side jobs | Move only where it improves dependency direction or reuse; keep shims until post-merge validation proves old paths are unused by effective project code |
| Universe boundary | `universe.py` | Keep in place in this branch; revisit only if current snapshot construction and point-in-time loading are split into separately tested units |
| Walk-forward orchestration | `walk_forward.py` | Keep in place in this branch; extract only bounded helpers with focused tests, not the orchestrator module itself |
| Shell environment bootstrap | Maintenance shell scripts | Keep one small `scripts/lib/project_env.sh`; do not hide cron, lock, or external agent semantics in broad shell frameworks |

## Non-Goals

- Do not rewrite strategy algorithms during structural migration.
- Do not change data tables, as-of rules, adjustment modes, costs, or admission thresholds as part of package cleanup.
- Do not commit `reports/`, `logs/`, SQLite databases, or generated research artifacts.
- Do not make Harness or `codex-harness-runner` a runtime dependency of the product code.
- Do not migrate `phase0/maintenance_orchestrator.py` in the current branch unless a later task explicitly reopens scheduler/orchestration ownership.
- Do not migrate `phase0/walk_forward.py` as a whole in the current branch. Keep it as the stable research orchestrator while only extracting proven helper boundaries.

## Harness Working Rule

Team Lead owns git boundaries, scope control, and final integration. Planner, implementer, reviewer, verifier, and memory-steward style agents can be used for bounded reviews or disjoint work. Completed subagents should be closed. Parallel write work must use separate git worktrees or disjoint file ownership.
