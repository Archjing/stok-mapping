# Strategy Holdings Exposure Run Log

- generated_at: `2026-06-26T02:03:08`
- iteration_id: `I10`
- diagnostic_type: `daily_holdings_exposure`
- promotion_boundary: `research_only; no admission rerun; no trading rule`
- config_path: `/home/zj/workspace/stok-mapping/config.main_strategy_i55_benchmark_core_alpha_overlay_20260626.yaml`
- candidate_folds_path: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/admission/strategy_admission_candidate_folds.csv`
- market_context_path: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/market_context/strategy_market_context_diagnostic.csv`
- output_dir: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/holdings_exposure`
- benchmark_symbol: `SH.000300`
- command: `/home/zj/workspace/stok-mapping/phase0/cli.py strategy-holdings-exposure --config config.main_strategy_i55_benchmark_core_alpha_overlay_20260626.yaml --candidate-folds reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/admission/strategy_admission_candidate_folds.csv --market-context reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/market_context/strategy_market_context_diagnostic.csv --strategy benchmark_core_alpha_overlay_v1 --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/holdings_exposure`
- git_head: `92128e6`

## Artifact Hashes

- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/holdings_exposure/strategy_daily_holdings.csv` sha256=`dd3d4e6c648a37ae60d4b72cfb332f4920e4423e456f0dcb574719529e573bb8`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/holdings_exposure/strategy_daily_exposure.csv` sha256=`e7373f7f093181acb22246c6a8c235800e3cc9e60ee005d0bd9eddfd4fc3ddd2`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/holdings_exposure/strategy_daily_industry_exposure.csv` sha256=`add2c82d254abf4b2e48499087bc90edf24442fd9d711e38b0c4d17b4e222ead`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/holdings_exposure/strategy_holdings_exposure_summary.csv` sha256=`2bca2e1721f14a3d31f5dfef7183238ed10e893cd5b74becf7bb276cbd7812e8`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/holdings_exposure/strategy_holdings_exposure_coverage.csv` sha256=`de0ac6ddaef8a759bf17aafedceb27e1cc594088eaaac0e7f5854ab1d17b4fbe`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/holdings_exposure/strategy_holdings_exposure_report.md` sha256=`6aa3380907c6fbcd4c41ac1b67bafb5133a3f1db4206ec2643503981574decc0`

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
?? config.main_strategy_i55_benchmark_core_alpha_overlay_20260626.yaml
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
?? reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/
?? tests/test_intelligence.py
```
