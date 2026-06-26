# Strategy Holdings Exposure Run Log

- generated_at: `2026-06-26T00:48:08`
- iteration_id: `I10`
- diagnostic_type: `daily_holdings_exposure`
- promotion_boundary: `research_only; no admission rerun; no trading rule`
- config_path: `/home/zj/workspace/stok-mapping/config.main_strategy_i52_benchmark_aware_relaxed_context_20260626.yaml`
- candidate_folds_path: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/admission/strategy_admission_candidate_folds.csv`
- market_context_path: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/market_context/strategy_market_context_diagnostic.csv`
- output_dir: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/holdings_exposure`
- benchmark_symbol: `SH.000300`
- command: `/home/zj/workspace/stok-mapping/phase0/cli.py strategy-holdings-exposure --config config.main_strategy_i52_benchmark_aware_relaxed_context_20260626.yaml --candidate-folds reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/admission/strategy_admission_candidate_folds.csv --market-context reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/market_context/strategy_market_context_diagnostic.csv --strategy strong_market_benchmark_aware_core_v1 --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/holdings_exposure`
- git_head: `39e50eb`

## Artifact Hashes

- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/holdings_exposure/strategy_daily_holdings.csv` sha256=`b1e900abd55ab6b9fd9830826d724e505fc8559a080337188aa75af590332982`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/holdings_exposure/strategy_daily_exposure.csv` sha256=`57dbf859a6ad81ee169508a5315445b061e03f579c80d8556e19e3e3048a4f16`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/holdings_exposure/strategy_daily_industry_exposure.csv` sha256=`04ee5c33eaadf945b189ecdc6c15325bf4d13e888605d233cd1fb49d271f1b99`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/holdings_exposure/strategy_holdings_exposure_summary.csv` sha256=`85c30aac774cdff8efecb00fc7a9d3815d92e02e838aa2d5a2f9fc1573cbdc2d`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/holdings_exposure/strategy_holdings_exposure_coverage.csv` sha256=`fb940954656eed4da1d9434e5f0c5d837ebc9efceacfc390166a95e3bd4bba19`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/holdings_exposure/strategy_holdings_exposure_report.md` sha256=`652c11e52d2c80321968b3165d9cabf38e8c69805c97cd1059644f662cfc888c`

## Git Status At Run

```text
M config.yaml
 M data/maintenance/maintenance.sqlite
 M data/manual_history/README.md
 M data/universe/a_share_snapshot.csv
 M data/universe/local_factor_universe.csv
 M data/universe/local_factor_universe_report.md
 M knowledge/intelligence/README.md
 M logs/daily_brief_pipeline.log
 M logs/hk_market_history_update.log
 M logs/manual_history_update.log
 M logs/project_scheduler.log
 M logs/scheduler/a_share_history.state
 M logs/scheduler/daily_brief.state
 M logs/scheduler/hk_market_history.state
 M logs/scheduler/us_market_history.state
 M logs/us_market_history_update.log
 M phase0/cli.py
 M phase0/index_asof_audit.py
 M phase0/intelligence.py
 M phase0/strategies/__init__.py
 M phase0/strategies/strong_market_stable_core_base.py
 M phase0/strategy_admission.py
 D reports/a_share_best10_pe_pb_price_v2.png
 D reports/a_share_worst10_pe_pb_price.png
 D reports/a_share_worst10_pe_pb_price_v2.png
 D reports/strategy_backtest_flowchart.html
 M tests/test_index_asof_audit.py
 M tests/test_strategy_admission_config.py
 M tests/test_strong_market_stable_core_base_strategy.py
?? 7
?? 9
?? config.main_strategy_i51_strong_market_benchmark_aware_core_20260626.yaml
?? config.main_strategy_i52_benchmark_aware_relaxed_context_20260626.yaml
?? data/intelligence/inbox/intelligence_collect_2026-06-25_t52_run.csv
?? data/intelligence/inbox/intelligence_import_local_2026-06-25_t52_run.csv
?? data/intelligence/inbox/intelligence_review_suggestions_2026-06-25_t52_run.csv
?? data/intelligence/inbox/intelligence_review_suggestions_2026-06-25_t52_run_sample.csv
?? docs/tasks/research/STRATEGY_INTELLIGENCE_WORKFLOW.md
?? logs/index.html
?? logs/strategy_backtest_flowchart.html
?? prompts/strategy_intelligence_workflow.prompt.md
?? reports/2026-06-25/daily_market_data_maintenance_status_before.md
?? reports/2026-06-25/index_asof_audit_SH_000852_post_backfill/
?? reports/2026-06-25/index_asof_audit_SH_000852_pre_backfill/
?? reports/2026-06-25/index_asof_audit_SH_000905_post_backfill/
?? reports/2026-06-25/index_asof_audit_SH_000905_pre_backfill/
?? reports/2026-06-25/index_asof_backfill_audit_SH_000852_20160101_20260624.csv
?? reports/2026-06-25/index_asof_backfill_audit_SH_000852_20160101_20260624.md
?? reports/2026-06-25/index_asof_backfill_audit_SH_000905_20160101_20260624.csv
?? reports/2026-06-25/index_asof_backfill_audit_SH_000905_20160101_20260624.md
?? reports/intelligence/intelligence_collect_report_2026-06-25_t52_run.md
?? reports/intelligence/intelligence_import_local_report_2026-06-25_t52_run.md
?? reports/intelligence/intelligence_review_report_2026-06-25_t52_run.md
?? reports/intelligence/intelligence_review_report_2026-06-25_t52_run_sample.md
?? reports/intelligence/intelligence_validate_report_2026-06-25_t52_run.md
?? reports/intelligence/intelligence_validate_report_2026-06-25_t52_run_after_review.md
?? reports/runs/2026-06-24/
?? reports/runs/2026-06-25/
?? reports/strategy_governance/2026-06-24/
?? reports/strategy_governance/2026-06-25/csi300_index_asof_backfill_report.md
?? reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_47__strong_market_stable_core_base/
?? reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_48__stable_core_attribution/
?? reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_48__stable_core_attribution_final_rerun/
?? reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_48__stable_core_attribution_long_window/
?? reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_48__stable_core_attribution_rerun_after_rebalance_retry_fix/
?? reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_49__stable_core_lag_attribution/
?? reports/strategy_governance/2026-06-26/
?? tests/test_intelligence.py
```
