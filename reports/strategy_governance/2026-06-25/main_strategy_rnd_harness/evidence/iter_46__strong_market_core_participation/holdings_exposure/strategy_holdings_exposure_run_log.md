# Strategy Holdings Exposure Run Log

- generated_at: `2026-06-25T13:42:48`
- iteration_id: `I10`
- diagnostic_type: `daily_holdings_exposure`
- promotion_boundary: `research_only; no admission rerun; no trading rule`
- config_path: `/home/zj/workspace/stok-mapping/config.main_strategy_i46_strong_market_core_participation_20260625.yaml`
- candidate_folds_path: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/admission/strategy_admission_candidate_folds.csv`
- market_context_path: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/market_context/strategy_market_context_diagnostic.csv`
- output_dir: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/holdings_exposure`
- benchmark_symbol: `SH.000300`
- command: `/home/zj/workspace/stok-mapping/phase0/cli.py strategy-holdings-exposure --config config.main_strategy_i46_strong_market_core_participation_20260625.yaml --candidate-folds reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/admission/strategy_admission_candidate_folds.csv --market-context reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/market_context/strategy_market_context_diagnostic.csv --strategy strong_market_core_participation_v1 --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/holdings_exposure`
- git_head: `2d18a1a`

## Artifact Hashes

- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/holdings_exposure/strategy_daily_holdings.csv` sha256=`7cf69a20870a043ff313f37c38e19834489a1f84943c22bcd3871160886882bb`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/holdings_exposure/strategy_daily_exposure.csv` sha256=`a375eb76c41a3e79faa7005aaa23634937da93295c5de553aa52275d4ed4319f`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/holdings_exposure/strategy_daily_industry_exposure.csv` sha256=`94077cbc6d024c4db072386e32dad3582a062c00b9361b1e2685ef05024a6c06`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/holdings_exposure/strategy_holdings_exposure_summary.csv` sha256=`a817e3364ea13f62f0aaa909b326d4c2400abc604e8a81ceebfe00642efbde01`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/holdings_exposure/strategy_holdings_exposure_coverage.csv` sha256=`5f92132a8d335e0dc12cb6c18daaebba130cc3851b6d0929cf5cc0ca5cbc833d`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_46__strong_market_core_participation/holdings_exposure/strategy_holdings_exposure_report.md` sha256=`6772c75653cd00bcccd5b0666db6b5000951566e3e3d9356e0475b5013fb0f0d`

## Git Status At Run

```text
M AGENTS.md
 M config.yaml
 M data/maintenance/maintenance.sqlite
 M data/manual_history/README.md
 M data/universe/a_share_snapshot.csv
 M data/universe/local_factor_universe.csv
 M data/universe/local_factor_universe_report.md
 M docs/CODEX_MCP_MULTI_AGENT_WORKFLOW.md
 M docs/DEVELOPMENT_PLAN.md
 M docs/STRATEGY_DEVELOPMENT_GUIDELINES.md
 M docs/tasks/README.md
 M docs/tasks/strategy/PHASE0_CANDIDATE_STRATEGIES.md
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
 M phase0/intelligence.py
 M phase0/strategies/__init__.py
 M phase0/strategies/low_vol_low_turnover_quality.py
 M phase0/strategies/sleeve_composite.py
 M phase0/strategy_admission.py
 M phase0/strategy_failure_attribution.py
 M phase0/walk_forward.py
 D reports/a_share_best10_pe_pb_price_v2.png
 D reports/a_share_worst10_pe_pb_price.png
 D reports/a_share_worst10_pe_pb_price_v2.png
 M tests/test_sleeve_composite_strategy.py
 M tests/test_strategy_admission_config.py
 M tests/test_strategy_failure_attribution.py
?? config.main_strategy_i15_strong_index_participation_20260625.yaml
?? config.main_strategy_i18_strong_index_dynamic_trigger_20260625.yaml
?? config.main_strategy_i20_strong_market_liquid_breadth_20260625.yaml
?? config.main_strategy_i37_strong_market_effective_participation_20260625.yaml
?? config.main_strategy_i3_quality_stable_20260624.yaml
?? config.main_strategy_i3_recent_winner_20260624.yaml
?? config.main_strategy_i43_panel_limit_200_20260625.yaml
?? config.main_strategy_i43_panel_limit_300_20260625.yaml
?? config.main_strategy_i46_strong_market_core_participation_20260625.yaml
?? config.main_strategy_i4_quality_stable_overlay_20260624.yaml
?? config.main_strategy_i5_quality_regime_gate_20260624.yaml
?? config.main_strategy_i6_price_volume_low_turnover_20260624.yaml
?? config.main_strategy_i7_price_volume_industry_relative_20260624.yaml
?? data/intelligence/inbox/intelligence_collect_2026-06-25_t52_run.csv
?? data/intelligence/inbox/intelligence_import_local_2026-06-25_t52_run.csv
?? docs/tasks/strategy/INTRADAY_SIGNAL_TIMING_EXPLORATION.md
?? docs/templates/
?? phase0/index_asof_audit.py
?? phase0/index_asof_backfill.py
?? phase0/strategies/price_volume_low_turnover.py
?? phase0/strategies/quality_low_turnover_regime_gate.py
?? phase0/strategies/strong_index_participation.py
?? phase0/strategies/strong_market_core_participation.py
?? phase0/strategies/strong_market_effective_participation.py
?? phase0/strategies/strong_market_liquid_breadth_participation.py
?? phase0/strategy_core_reachability.py
?? phase0/strategy_csi300_attribution.py
?? phase0/strategy_exposure_diagnostic.py
?? phase0/strategy_filter_diagnostic.py
?? phase0/strategy_fold_attribution.py
?? phase0/strategy_holdings_exposure.py
?? phase0/strategy_market_context.py
?? phase0/strategy_missing_core_audit.py
?? phase0/strategy_participation_overlay.py
?? phase0/strategy_role_card.py
?? reports/2026-06-25/
?? reports/intelligence/intelligence_collect_report_2026-06-25_t52_run.md
?? reports/intelligence/intelligence_import_local_report_2026-06-25_t52_run.md
?? reports/intelligence/intelligence_validate_report_2026-06-25_t52_run.md
?? reports/runs/2026-06-24/
?? reports/runs/2026-06-25/
?? reports/strategy_governance/2026-06-24/
?? reports/strategy_governance/2026-06-25/
?? tests/test_index_asof_audit.py
?? tests/test_index_asof_backfill.py
?? tests/test_intelligence.py
?? tests/test_low_vol_low_turnover_quality_strategy.py
?? tests/test_price_volume_low_turnover_strategy.py
?? tests/test_quality_low_turnover_regime_gate_strategy.py
?? tests/test_strategy_core_reachability.py
?? tests/test_strategy_csi300_attribution.py
?? tests/test_strategy_exposure_diagnostic.py
?? tests/test_strategy_filter_diagnostic.py
?? tests/test_strategy_fold_attribution.py
?? tests/test_strategy_holdings_exposure.py
?? tests/test_strategy_market_context.py
?? tests/test_strategy_missing_core_audit.py
?? tests/test_strategy_participation_overlay.py
?? tests/test_strategy_role_card.py
?? tests/test_strong_index_participation_strategy.py
?? tests/test_strong_market_core_participation_strategy.py
?? tests/test_strong_market_effective_participation_strategy.py
?? tests/test_strong_market_liquid_breadth_participation_strategy.py
```
