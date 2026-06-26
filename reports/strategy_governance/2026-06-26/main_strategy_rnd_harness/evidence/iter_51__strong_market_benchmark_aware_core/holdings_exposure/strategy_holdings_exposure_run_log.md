# Strategy Holdings Exposure Run Log

- generated_at: `2026-06-26T00:35:49`
- iteration_id: `I10`
- diagnostic_type: `daily_holdings_exposure`
- promotion_boundary: `research_only; no admission rerun; no trading rule`
- config_path: `/home/zj/workspace/stok-mapping/config.main_strategy_i51_strong_market_benchmark_aware_core_20260626.yaml`
- candidate_folds_path: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/admission/strategy_admission_candidate_folds.csv`
- market_context_path: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/market_context/strategy_market_context_diagnostic.csv`
- output_dir: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/holdings_exposure`
- benchmark_symbol: `SH.000300`
- command: `/home/zj/workspace/stok-mapping/phase0/cli.py strategy-holdings-exposure --config config.main_strategy_i51_strong_market_benchmark_aware_core_20260626.yaml --candidate-folds reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/admission/strategy_admission_candidate_folds.csv --market-context reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/market_context/strategy_market_context_diagnostic.csv --strategy strong_market_benchmark_aware_core_v1 --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/holdings_exposure`
- git_head: `39e50eb`

## Artifact Hashes

- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/holdings_exposure/strategy_daily_holdings.csv` sha256=`54b8184abe718958de93054b1e77844dbb82b5b2658f746444c76a830858886f`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/holdings_exposure/strategy_daily_exposure.csv` sha256=`0100097c21627001448d2fe33665502eca00090c6ea34e2913f4271fd102047d`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/holdings_exposure/strategy_daily_industry_exposure.csv` sha256=`7ca83f1425fef1f5300b095027a1fe1d08adff6fc74b5b9736baee4d51f7ace8`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/holdings_exposure/strategy_holdings_exposure_summary.csv` sha256=`43bb2bf7b806f17a7ae09bfed0ac140b3e16bd0d0bc22ef873e22af6e2bec07c`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/holdings_exposure/strategy_holdings_exposure_coverage.csv` sha256=`34a251482dd045bc543ab98fccd3f3dacbd17551579452a2459ac130fe5a3544`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/holdings_exposure/strategy_holdings_exposure_report.md` sha256=`1ebac2c9dee6588e9e7d2348b9ca75aa687e5990ed115dc47e749da36dc7c3d8`

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
