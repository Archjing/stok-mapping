# Strategy Holdings Exposure Run Log

- generated_at: `2026-06-26T02:53:16`
- iteration_id: `I10`
- diagnostic_type: `daily_holdings_exposure`
- promotion_boundary: `research_only; no admission rerun; no trading rule`
- config_path: `/home/zj/workspace/stok-mapping/config.main_strategy_i58_strong_exposure_only_20260626.yaml`
- candidate_folds_path: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/admission/strategy_admission_candidate_folds.csv`
- market_context_path: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/market_context/strategy_market_context_diagnostic.csv`
- output_dir: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/holdings_exposure`
- benchmark_symbol: `SH.000300`
- command: `/home/zj/workspace/stok-mapping/phase0/cli.py strategy-holdings-exposure --config config.main_strategy_i58_strong_exposure_only_20260626.yaml --candidate-folds reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/admission/strategy_admission_candidate_folds.csv --market-context reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/market_context/strategy_market_context_diagnostic.csv --strategy strong_benchmark_participation_boost_v1 --presets baseline_2y_1y_5fold --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/holdings_exposure`
- git_head: `6ace1cf`

## Artifact Hashes

- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/holdings_exposure/strategy_daily_holdings.csv` sha256=`b3be872664167ac17689d082771433567aa63e029cc0cd5381d436eec1844570`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/holdings_exposure/strategy_daily_exposure.csv` sha256=`e5cdf0026b5ac6fd0791608570cee1614498d5b9adea355fa8859910b0f77438`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/holdings_exposure/strategy_daily_industry_exposure.csv` sha256=`4a13f998f60bc9f8a2d9c31aa5b754f81c450206476e9f401cf42543568eeffa`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/holdings_exposure/strategy_holdings_exposure_summary.csv` sha256=`0235906444ee7f989607ed3d27c992d97c211451c6d18e603efd187cca44c1de`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/holdings_exposure/strategy_holdings_exposure_coverage.csv` sha256=`de0ac6ddaef8a759bf17aafedceb27e1cc594088eaaac0e7f5854ab1d17b4fbe`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/holdings_exposure/strategy_holdings_exposure_report.md` sha256=`5f411a2ef82aa25b7d7689013b9a80f70bad6ee9717d356d0c93af560f74e295`

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
?? config.main_strategy_i57_strong_benchmark_participation_boost_20260626.yaml
?? config.main_strategy_i58_strong_exposure_only_20260626.yaml
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
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/csi300_attribution_all/strategy_csi300_daily_attribution.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/csi300_attribution_all/strategy_csi300_fold_attribution.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/csi300_attribution_all/strategy_csi300_industry_active_weights.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/csi300_attribution_all/strategy_csi300_missed_top_weights.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/failure_attribution/strategy_failure_attribution.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/failure_attribution/strategy_failure_fold_attribution.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/holdings_exposure/strategy_daily_exposure.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/holdings_exposure/strategy_daily_holdings.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/holdings_exposure/strategy_daily_industry_exposure.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/holdings_exposure/strategy_holdings_exposure_coverage.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/holdings_exposure/strategy_holdings_exposure_summary.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/market_context/strategy_market_context_data_coverage.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/market_context/strategy_market_context_diagnostic.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/market_context/strategy_market_context_label_summary.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/failure_attribution/strategy_failure_attribution.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/failure_attribution/strategy_failure_fold_attribution.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/holdings_exposure/strategy_daily_exposure.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/holdings_exposure/strategy_daily_holdings.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/holdings_exposure/strategy_daily_industry_exposure.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/holdings_exposure/strategy_holdings_exposure_coverage.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/holdings_exposure/strategy_holdings_exposure_summary.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/market_context/strategy_market_context_data_coverage.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/market_context/strategy_market_context_diagnostic.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context/market_context/strategy_market_context_label_summary.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay/
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/csi300_attribution_all/strategy_csi300_daily_attribution.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/csi300_attribution_all/strategy_csi300_industry_active_weights.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/csi300_attribution_all/strategy_csi300_missed_top_weights.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/holdings_exposure/strategy_daily_exposure.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/holdings_exposure/strategy_daily_holdings.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/holdings_exposure/strategy_daily_industry_exposure.csv
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_57__strong_benchmark_participation_boost/
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/
?? tests/test_intelligence.py
```
