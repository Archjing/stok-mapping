# Session Incremental Archive - 2026-06-26 03:35

范围：I60 Harness 策略研发迭代，主题为 daily context state audit。

## 新增判断

- `strategy-holdings-exposure` 必须保留策略日频状态字段，否则无法解释 target exposure 为什么进入某个仓位档。
- `review_day_count` 在 daily exposure 中应是日级 0/1，不应按持仓行数累加。
- 当前强市场触发器的主要漏判风险来自深回撤阈值：恢复型行情可能仍远离历史高点，但已经具备趋势修复特征。

## 关键证据

- fold4：241 天中 `strong_context_days=0`，`high_target_days=0`，但 `close_gt_ma_days=177`，`ret60_pos_days=122`，`vol_ok_days=163`，`drawdown_ok_days=0`。
- fold5：242 天中 `strong_context_days=61`，`high_target_days=60`，说明当 strong 触发时，I58 的高仓位机制可以工作。

## 变更文件

- `phase0/strategy_holdings_exposure.py`
- `tests/test_strategy_holdings_exposure.py`
- `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_60__daily_context_state_audit/daily_context_state_summary.csv`
- `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_60__daily_context_state_audit/daily_context_trigger_failure_summary.csv`
- `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_60__daily_context_state_audit/holdings_exposure/strategy_daily_exposure.csv`
- `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/briefings/iter_60__daily_context_state_audit_brief.md`
- `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/strategy_governance_report_2026-06-26_i60_daily_context_state_audit.md`

## 已执行验证

- `./.venv/bin/python -m pytest tests/test_strategy_holdings_exposure.py tests/test_strategy_participation_path_audit.py -q -s`
- `git diff --check -- phase0/strategy_holdings_exposure.py tests/test_strategy_holdings_exposure.py`

结果：通过。

## 下一步

- I61：设计 `strong_benchmark_recovery_participation_v1` 或等价 research-only 恢复型强市场参与策略。
- 不直接使用事后 `market_context_label`，只用 as-of 指数特征。
