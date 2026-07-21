# 会话增量归档 - 2026-06-25 16:20

## 本段目标

延续主线 Harness：围绕策略池北极星目标推进 I49，解释 `strong_market_stable_core_base_v1` 为什么在提高参与度和降低换手后仍跑输强沪深300，并修正 I48 拆分对象容易被误解为候选策略的问题。

## 已完成

1. 回答用户关于 `strong_index_participation_dynamic_trigger_v1` 的问题：
   - 该策略是 I18 的强沪深300动态触发实验备选，不是当前可用候选。
   - admission 结果为 `reject`。
   - 主要失败原因是强势状态触发太少；真正开仓时也没有持到足够多的沪深300核心权重。

2. 完成 I49 归因证据补齐：
   - `holdings_core_base/`
   - `failure_attribution_short/`
   - `market_context_short/`
   - `csi300_core_base_all_context/`

3. 形成 I49 结论：
   - `strong_market_stable_core_base_v1` 在强沪深300跑输环境中，平均实盘仓位约 `39.18%`。
   - 平均持有沪深300权重约 `22.33%`，平均漏掉沪深300权重约 `77.67%`。
   - Top20 覆盖率约 `59.14%`，Top20 漏配权重约 `13.39%`。
   - 行业 L1 偏离约 `1.1456`。
   - 策略强基准折平均年化约 `8.27%`，沪深300约 `12.74%`，超额总收益约 `-4.27%`。

4. 收紧治理边界：
   - `strong_market_stable_core_only_v1` 和 `strong_market_stable_satellite_only_v1` 只作为 attribution-only 归因变体。
   - `core+satellite` 只是 I47 `strong_market_stable_core_base_v1` 在 I48 拆分实验中的对照口径，不是新策略 id。
   - 三者均不得进入 `baseline_admission_all_v1`、paper review、模拟账户、日报或 watchlist。

## 本段文件变更

- `phase0/strategies/base.py`
- `phase0/strategies/strong_market_stable_core_base.py`
- `phase0/strategy_admission.py`
- `tests/test_strong_market_stable_core_base_strategy.py`
- `tests/test_strategy_admission_config.py`
- `config.main_strategy_i48_stable_core_attribution_20260625.yaml`
- `docs/tasks/strategy/PHASE0_CANDIDATE_STRATEGIES.md`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/briefings/iter_49__stable_core_lag_attribution_brief.md`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/briefings/strategy_role_cards_snapshot_20260625.md`

## 后续建议

下一轮不要继续调卫星仓参数。更合理的方向是预注册 `benchmark-aware core weight closeness` 设计：让强市场核心底仓在不简单复制沪深300的前提下，更明确地约束沪深300权重、Top20 权重和行业权重贴近度。
