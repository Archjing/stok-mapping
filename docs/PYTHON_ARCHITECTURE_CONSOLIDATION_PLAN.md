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
| `reporting` | Report output paths, run directories, artifact registry, report-export helpers, Markdown/HTML/CSV writers | `phase0/reporting/paths.py`, `phase0/reporting/registry.py`, `phase0/reporting/writers.py`, `phase0/reporting/exports.py`, compatibility shims `phase0/report_paths.py`, `phase0/report_registry.py`, report-export helper aliases in `phase0/cli.py` |
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
