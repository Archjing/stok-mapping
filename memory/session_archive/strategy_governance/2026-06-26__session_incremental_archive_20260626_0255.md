# Session Incremental Archive - 2026-06-26 02:55 CST

## Scope

本归档记录主线策略研发 Harness 的 I57/I58 阶段。目标是基于 I56 的 `low_participation` 结论，验证强沪深300阶段提高核心参与仓位是否能改善策略表现。

## Key Decisions

- 新增 research-only 策略 `strong_benchmark_participation_boost_v1`，继承 benchmark-aware core。
- 不加入 `baseline_admission_all_v1`，仅 scoped admission。
- I57a 使用 `strong_target_exposure=0.85` 和 `rebalance_on_context_change=true`。
- I58 关闭 `rebalance_on_context_change`，只验证强市场目标仓位提高。

## Bug / Lesson

I57 配置初版曾把 `strong_benchmark_participation_boost` 放到 `phase0.local_factor`，而不是 `phase0.walk_forward.strategy_v2.local_factor`。Admission 因为 strategy-set force-enable 还能跑，但 holdings exposure 不能启用策略并报错：

```text
ValueError: strategy is not enabled: strong_benchmark_participation_boost_v1
```

修正后重跑 admission。这个问题说明：后续生成实验配置时必须用 YAML 解析校验关键路径，而不是只用 grep。

## Results

I57a：

- admission: `reject`
- annualized_return_mean: -2.86%
- sharpe_mean: -0.56
- positive_fold_ratio: 20%
- positive_excess_fold_ratio: 60%
- turnover_annual_mean: 4.30
- 主要失败：fold 1 和 fold 5 换手失控，fold 5 年化换手 12.32。

I58：

- admission: `reject`
- annualized_return_mean: -0.22%
- sharpe_mean: -0.12
- positive_fold_ratio: 40%
- positive_excess_fold_ratio: 60%
- turnover_annual_mean: 0.70
- fold 4 / fold 5 为正收益，但仍跑输强沪深300。

## Strong Benchmark Attribution

I58 与 I51/I55 对比：

- fold 4 实际仓位仍约 14.91%，几乎没有提升；
- fold 5 实际仓位从约 34.84% 提升到约 38.57%，提升不足；
- strong benchmark context 主因仍是 `low_participation`；
- `strong_target_exposure=0.85` 没有有效转化为高 live exposure。

## Changed Files

代码/测试：

- `phase0/strategies/strong_market_stable_core_base.py`
- `phase0/strategies/__init__.py`
- `phase0/strategy_admission.py`
- `tests/test_strong_market_stable_core_base_strategy.py`
- `tests/test_strategy_admission_config.py`

配置：

- `config.main_strategy_i57_strong_benchmark_participation_boost_20260626.yaml`
- `config.main_strategy_i58_strong_exposure_only_20260626.yaml`

报告：

- `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/briefings/iter_57_58__strong_benchmark_participation_brief.md`
- `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/strategy_governance_report_2026-06-26_i57_i58_strong_benchmark_participation.md`

## Verification

```bash
./.venv/bin/python -m pytest tests/test_strong_market_stable_core_base_strategy.py tests/test_strategy_admission_config.py -q -s
./.venv/bin/python -m phase0.cli strategy-admission --config config.main_strategy_i57_strong_benchmark_participation_boost_20260626.yaml --presets baseline_2y_1y_5fold --strategy-set i57_strong_benchmark_participation_boost_v1 --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_57__strong_benchmark_participation_boost/admission --trace-run
./.venv/bin/python -m phase0.cli strategy-admission --config config.main_strategy_i58_strong_exposure_only_20260626.yaml --presets baseline_2y_1y_5fold --strategy-set i58_strong_exposure_only_v1 --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/admission --trace-run
./.venv/bin/python -m phase0.cli strategy-csi300-attribution --config config.main_strategy_i58_strong_exposure_only_20260626.yaml --holdings reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/holdings_exposure/strategy_daily_holdings.csv --daily-exposure reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/holdings_exposure/strategy_daily_exposure.csv --candidate-folds reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/admission/strategy_admission_candidate_folds.csv --market-context reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/market_context/strategy_market_context_diagnostic.csv --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_58__strong_exposure_only/csi300_attribution_all --context-label all --top-n 20
```

## Large Artifact Policy

不建议提交：

- `iter_58__strong_exposure_only/holdings_exposure/strategy_daily_holdings.csv`，约 32M。
- `iter_58__strong_exposure_only/csi300_attribution_all/strategy_csi300_industry_active_weights.csv`，约 20M。
- `iter_58__strong_exposure_only/holdings_exposure/strategy_daily_industry_exposure.csv`，约 7.2M。

## Next Step

I59 应先做“强市场参与链路审计”，而不是继续调仓位参数：

- 比较 `strong_index_context`、`market_context_label`、`review_day`、`target_exposure`、`live_exposure`；
- 找出为什么目标 85% 没有在 strong benchmark context 中变成高实际仓位；
- 再决定是否设计更早触发器、渐进加仓，或修改强市场状态定义。
