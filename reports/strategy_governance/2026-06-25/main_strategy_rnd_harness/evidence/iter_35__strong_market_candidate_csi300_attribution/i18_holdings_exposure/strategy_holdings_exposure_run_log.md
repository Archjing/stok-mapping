# Strategy Holdings Exposure Run Log

- generated_at: `2026-06-25T10:35:04`
- iteration_id: `I10`
- diagnostic_type: `daily_holdings_exposure`
- promotion_boundary: `research_only; no admission rerun; no trading rule`
- config_path: `/home/zj/workspace/stok-mapping/config.main_strategy_i18_strong_index_dynamic_trigger_20260625.yaml`
- candidate_folds_path: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-24/main_strategy_admission_breakthrough/evidence/iter_18__strong_index_dynamic_trigger/admission/strategy_admission_candidate_folds.csv`
- market_context_path: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_35__strong_market_candidate_csi300_attribution/i18_market_context/strategy_market_context_diagnostic.csv`
- output_dir: `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_35__strong_market_candidate_csi300_attribution/i18_holdings_exposure`
- benchmark_symbol: `SH.000300`
- command: `/home/zj/workspace/stok-mapping/phase0/cli.py strategy-holdings-exposure --config config.main_strategy_i18_strong_index_dynamic_trigger_20260625.yaml --candidate-folds reports/strategy_governance/2026-06-24/main_strategy_admission_breakthrough/evidence/iter_18__strong_index_dynamic_trigger/admission/strategy_admission_candidate_folds.csv --market-context reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_35__strong_market_candidate_csi300_attribution/i18_market_context/strategy_market_context_diagnostic.csv --strategy strong_index_participation_dynamic_trigger_v1 --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_35__strong_market_candidate_csi300_attribution/i18_holdings_exposure`
- git_head: `2d18a1a`

## Artifact Hashes

- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_35__strong_market_candidate_csi300_attribution/i18_holdings_exposure/strategy_daily_holdings.csv` sha256=`aeb643c5cb8b2ad30f4023233e8f62a02779edaff729a78bc6d9850e96838194`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_35__strong_market_candidate_csi300_attribution/i18_holdings_exposure/strategy_daily_exposure.csv` sha256=`1910a3580cff7750ad897d34810ea0680489225a597318324ee94d47e489bd0a`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_35__strong_market_candidate_csi300_attribution/i18_holdings_exposure/strategy_daily_industry_exposure.csv` sha256=`81dcaf9eff04f5e33a476ee769fb0745ed179d2bc921590f7310a39c8d943874`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_35__strong_market_candidate_csi300_attribution/i18_holdings_exposure/strategy_holdings_exposure_summary.csv` sha256=`adce23d7f58d9e6d01479d3908e7c10384bde60fd3f21b941a52b7bbe8349a35`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_35__strong_market_candidate_csi300_attribution/i18_holdings_exposure/strategy_holdings_exposure_coverage.csv` sha256=`47983974c7ed7a0db628e3fe2612273166ac8421fcc20b0bb339de2bc05b1d1c`
- `/home/zj/workspace/stok-mapping/reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_35__strong_market_candidate_csi300_attribution/i18_holdings_exposure/strategy_holdings_exposure_report.md` sha256=`6090dc4ced7c88b877c32fe7c36943fd00aa73c5caffc2078399b5cfe8264a3e`

## Git Status At Run

```text
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
?? config.main_strategy_i3_quality_stable_20260624.yaml
?? config.main_strategy_i3_recent_winner_20260624.yaml
?? config.main_strategy_i4_quality_stable_overlay_20260624.yaml
?? config.main_strategy_i5_quality_regime_gate_20260624.yaml
?? config.main_strategy_i6_price_volume_low_turnover_20260624.yaml
?? config.main_strategy_i7_price_volume_industry_relative_20260624.yaml
?? docs/tasks/strategy/INTRADAY_SIGNAL_TIMING_EXPLORATION.md
?? docs/templates/
?? phase0/index_asof_audit.py
?? phase0/index_asof_backfill.py
?? phase0/strategies/price_volume_low_turnover.py
?? phase0/strategies/quality_low_turnover_regime_gate.py
?? phase0/strategies/strong_index_participation.py
?? phase0/strategies/strong_market_liquid_breadth_participation.py
?? phase0/strategy_csi300_attribution.py
?? phase0/strategy_exposure_diagnostic.py
?? phase0/strategy_filter_diagnostic.py
?? phase0/strategy_fold_attribution.py
?? phase0/strategy_holdings_exposure.py
?? phase0/strategy_market_context.py
?? phase0/strategy_participation_overlay.py
?? phase0/strategy_role_card.py
?? reports/2026-06-25/
?? reports/runs/2026-06-24/
?? reports/runs/2026-06-25/
?? reports/strategy_governance/2026-06-24/
?? reports/strategy_governance/2026-06-25/
?? tests/test_index_asof_audit.py
?? tests/test_index_asof_backfill.py
?? tests/test_low_vol_low_turnover_quality_strategy.py
?? tests/test_price_volume_low_turnover_strategy.py
?? tests/test_quality_low_turnover_regime_gate_strategy.py
?? tests/test_strategy_csi300_attribution.py
?? tests/test_strategy_exposure_diagnostic.py
?? tests/test_strategy_filter_diagnostic.py
?? tests/test_strategy_fold_attribution.py
?? tests/test_strategy_holdings_exposure.py
?? tests/test_strategy_market_context.py
?? tests/test_strategy_participation_overlay.py
?? tests/test_strategy_role_card.py
?? tests/test_strong_index_participation_strategy.py
?? tests/test_strong_market_liquid_breadth_participation_strategy.py
```
