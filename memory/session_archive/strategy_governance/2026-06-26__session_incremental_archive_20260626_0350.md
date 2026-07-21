# Session Incremental Archive - 2026-06-26 03:50

范围：I61 Harness 策略研发迭代，主题为 recovery participation strategy。

## 新增策略

- `strong_benchmark_recovery_participation_v1`

定位：research-only。复用 I58 的沪深300核心组合构造，只新增 recovery context。

## 关键结果

- admission action: reject
- annualized_return_mean: -0.009913
- sharpe_mean: -0.380056
- positive_fold_ratio: 0.20
- positive_excess_fold_ratio: 0.40
- turnover_annual_mean: 1.855004

## 对比结论

- fold5 改善：年化从 0.036200 提高到 0.079348，超额从 -0.114863 改善到 -0.071715。
- fold4 变差：年化从 0.021060 降到 -0.000094，超额从 -0.063910 降到 -0.085064。
- fold2、fold3 也变差。
- recovery trigger 增加了参与度，但没有稳定提高收益。

## 变更文件

- `phase0/strategies/strong_market_stable_core_base.py`
- `phase0/strategy_admission.py`
- `phase0/strategy_holdings_exposure.py`
- `tests/test_strong_market_stable_core_base_strategy.py`
- `tests/test_strategy_admission_config.py`
- `tests/test_strategy_holdings_exposure.py`
- `config.main_strategy_i61_recovery_participation_20260626.yaml`
- `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_61__recovery_participation/`
- `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/briefings/iter_61__recovery_participation_brief.md`
- `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/strategy_governance_report_2026-06-26_i61_recovery_participation.md`

## 已执行验证

- `./.venv/bin/python -m pytest tests/test_strong_market_stable_core_base_strategy.py tests/test_strategy_admission_config.py::test_force_strategy_set_enabled_supports_strong_benchmark_recovery_participation_strategy tests/test_strategy_holdings_exposure.py tests/test_strategy_participation_path_audit.py -q -s`
- `./.venv/bin/python -m phase0.cli strategy-admission ... i61_strong_benchmark_recovery_participation_v1`
- `./.venv/bin/python -m phase0.cli strategy-holdings-exposure ... strong_benchmark_recovery_participation_v1`

## 下一步

- I62：恢复触发器分层，降低 recovery 仓位或加入修复质量过滤。
- 不把 I61 加入默认候选策略池。
