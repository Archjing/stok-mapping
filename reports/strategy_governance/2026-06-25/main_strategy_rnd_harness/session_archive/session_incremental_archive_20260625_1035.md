# Session Incremental Archive - 2026-06-25 10:35 - I35 Harness

## 本轮目标

- 接续 I34 的 `strategy-csi300-attribution` 工具，分析 I15/I18/I20 三个强市场失败候选。
- 目标不是调参，而是补齐证据链：admission 失败事实 -> 折级失败归因 -> 市场状态 -> 日度持仓 -> 沪深300权重归因。
- 保持 research-only，不改变 admission，不生成交易建议。

## 关键代码修正

- `phase0/strategy_csi300_attribution.py`
  - 默认 `weight_date_lag_days=1`，每个持仓日使用 `date - 1 day` 以前最近的沪深300权重，避免同日收盘后权重被误当作事前可见。
  - 当未提供 daily exposure 时，可从本地 `market_index_bars` 补沪深300日收益，避免把基准收益误算为 0。
- `phase0/cli.py`
  - `strategy-csi300-attribution` 支持可选 `--candidate-folds`、`--market-context`、`--weight-date-lag-days`。
- `phase0/strategy_holdings_exposure.py`
  - coverage 摘要新增检查 `cn_index_weights_asof`，不再误报本地沪深300权重表不可用。
- 测试：
  - `tests/test_strategy_csi300_attribution.py`
  - `tests/test_strategy_holdings_exposure.py`

## 主要命令链

```bash
./.venv/bin/python -m phase0.cli strategy-failure-attribution \
  --config config.main_strategy_i15_strong_index_participation_20260625.yaml \
  --admission-dir reports/strategy_governance/2026-06-24/main_strategy_admission_breakthrough/evidence/iter_15__strong_index_participation_minimal/admission \
  --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_35__strong_market_candidate_csi300_attribution/i15_failure_attribution
```

同类命令分别用于 I18、I20。

```bash
./.venv/bin/python -m phase0.cli strategy-market-context ...
./.venv/bin/python -m phase0.cli strategy-holdings-exposure ...
./.venv/bin/python -m phase0.cli strategy-csi300-attribution ...
```

I18 默认 `relative_lag_in_strong_benchmark_context` 没有匹配样本，补跑：

```bash
./.venv/bin/python -m phase0.cli strategy-csi300-attribution \
  --context-label mixed_or_unresolved_context \
  --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_35__strong_market_candidate_csi300_attribution/i18_csi300_attribution_mixed_context
```

## 输出产物

- I15:
  - `.../i15_failure_attribution/`
  - `.../i15_market_context/`
  - `.../i15_holdings_exposure/`
  - `.../i15_csi300_attribution/`
- I18:
  - `.../i18_failure_attribution/`
  - `.../i18_market_context/`
  - `.../i18_holdings_exposure/`
  - `.../i18_csi300_attribution/`，默认强滞后标签下 status 为 `blocked_no_matching_holdings`
  - `.../i18_csi300_attribution_mixed_context/`，mixed context 下 status 为 `ok`
- I20:
  - `.../i20_failure_attribution/`
  - `.../i20_market_context/`
  - `.../i20_holdings_exposure/`
  - `.../i20_csi300_attribution/`
- 用户简报：
  - `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/briefings/iter_35__strong_market_candidate_csi300_attribution_brief.md`

## 关键结论

| 候选 | 折 | 状态 | 平均仓位 | 持有沪深300权重 | 前20权重股覆盖率 | 超额 | 主因 |
| ---- | -: | ---- | -------: | --------------: | ----------------: | ---: | ---- |
| I15 `strong_index_participation_v1` | 5 | 强沪深300但策略落后 | 8.26% | 0.93% | 0.91% | -13.07% | 低参与度 |
| I18 `strong_index_participation_dynamic_trigger_v1` | 4 | mixed / unresolved | 0.00% | 0.00% | 0.00% | -9.89% | 空仓 |
| I18 `strong_index_participation_dynamic_trigger_v1` | 5 | mixed / unresolved | 27.09% | 3.54% | 5.83% | -6.14% | 参与不足 |
| I20 `strong_market_liquid_breadth_participation_v1` | 5 | 强沪深300但策略落后 | 13.55% | 1.68% | 1.79% | -10.28% | 低参与度 |

简明结论：三个强市场候选都没有证明自己能承担“强沪深300参与型”角色。当前问题不是缺基准数据，而是强市场中实际仓位和沪深300权重覆盖太低。

## 验证

```bash
./.venv/bin/python -m py_compile phase0/strategy_csi300_attribution.py phase0/cli.py
./.venv/bin/python -m py_compile phase0/strategy_holdings_exposure.py
./.venv/bin/python -m pytest -s tests/test_index_asof_audit.py tests/test_strategy_holdings_exposure.py tests/test_strategy_csi300_attribution.py
```

结果：`11 passed, 1 warning`。

```bash
git diff --check -- phase0/strategy_holdings_exposure.py phase0/strategy_csi300_attribution.py phase0/cli.py tests/test_strategy_holdings_exposure.py tests/test_strategy_csi300_attribution.py reports/strategy_governance/2026-06-25/main_strategy_rnd_harness
```

结果：通过。

## 下一步

1. 暂停继续微调 I15/I18/I20。
2. 预注册一个真正以强市场有效参与度为核心的新候选，候选应显式约束最低仓位、指数权重覆盖或流动性权重覆盖。
3. 在策略池方法论中记录：强市场策略必须证明在强市场折里确实有足够参与度和权重覆盖，不能只靠策略命名或触发器叙事。
