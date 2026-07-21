# Session Incremental Archive - 2026-06-26 04:50

范围：I67 Harness 策略研发迭代，主题为 recovery tradable filter。

## 变更文件

- `phase0/strategies/strong_market_stable_core_base.py`：新增 `strong_benchmark_recovery_tradable_v1`，新增 recovery breadth 特征和 tradable context。
- `phase0/strategy_admission.py`：新增 scoped admission force-enable 映射。
- `tests/test_strong_market_stable_core_base_strategy.py`：新增 research-only 注册、breadth shift、仓位降级测试。
- `tests/test_strategy_admission_config.py`：新增 admission 启用映射测试。
- `config.main_strategy_i67_recovery_tradable_20260626.yaml`：新增 I67 research-only 配置。

## 验证

- `./.venv/bin/python -m pytest tests/test_strong_market_stable_core_base_strategy.py tests/test_strategy_admission_config.py::test_force_strategy_set_enabled_supports_strong_benchmark_recovery_tradable_strategy -q -s` -> 28 passed, 1 warning。
- scoped admission 完成，结论 reject。
- holdings exposure 完成，原始 holdings 44MB，保留本地，不建议提交。

## 关键发现

- I67 年化均值 -0.0067，Sharpe -0.3168，正收益 fold 比例 0.40，相对沪深300正超额 fold 比例 0.40。
- fold4 相比 I63 改善明显，年化从 -0.0010 到 0.0127。
- fold2 基本没有改善，说明 breadth filter 还没有识别出假 recovery。

## 决策

I67 不进入默认候选池。下一步应做 negative recovery classifier 审计，重点解释 fold2 假 recovery。
