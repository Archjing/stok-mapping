# Session Incremental Archive - 2026-06-25 11:15 - I37 Harness

## 本轮目标

- 将 I36 预注册的 `strong_market_effective_participation_v1` 落成最小 research-only 策略。
- 跑 scoped admission。
- 立即补 holdings exposure 与 CSI300 attribution，验证是否真的达成强市场有效参与。

## 关键实现

- 新增策略：`phase0/strategies/strong_market_effective_participation.py`
- 注册策略：`phase0/strategies/__init__.py`
- admission 强制启用映射：`phase0/strategy_admission.py`
- 新增测试：`tests/test_strong_market_effective_participation_strategy.py`
- 新增实验配置：`config.main_strategy_i37_strong_market_effective_participation_20260625.yaml`

策略要点：

- research-only，`supports_paper_trade=False`
- 使用 T-1 可见强沪深300状态。
- 在 `prepare_panel` 中接入本地 `cn_index_weights_asof`，默认用 `date - 1 day` 以前最近权重。
- 强状态下构造目标参与仓位，但仍受候选可用性、行业约束和单票权重限制。

## 运行命令

```bash
./.venv/bin/python -m phase0.cli strategy-admission \
  --config config.main_strategy_i37_strong_market_effective_participation_20260625.yaml \
  --presets baseline_2y_1y_5fold \
  --strategies strong_market_effective_participation_v1 \
  --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/admission
```

后续补跑：

- `strategy-failure-attribution`
- `strategy-market-context`
- `strategy-holdings-exposure`
- `strategy-csi300-attribution --context-label mixed_or_unresolved_context`

## 关键结果

Admission：

| 指标 | 结果 |
| ---- | ---: |
| annualized_return_mean | -6.77% |
| sharpe_mean | -0.65 |
| max_drawdown_worst | -34.85% |
| positive_fold_ratio | 20% |
| turnover_annual_mean | 4.25 |
| turnover_annual_max | 16.91 |
| admission_action | reject |
| overfit_risk_level | critical |

CSI300 attribution：

| fold | context | avg_live_exposure | avg_benchmark_weight_held | avg_top_n_coverage_ratio | excess_total_return |
| ---: | ------- | ----------------: | ------------------------: | -----------------------: | ------------------: |
| 4 | mixed_or_unresolved_context | 0.00% | 0.00% | 0.00% | -9.89% |
| 5 | mixed_or_unresolved_context | 16.26% | 2.13% | 2.79% | -36.86% |

## 结论

`strong_market_effective_participation_v1` 首版停止。它没有达成 I36 定义的有效参与：

- 目标强市场折平均仓位 `>= 60%`，实际第 5 折只有 `16.26%`。
- 目标持有沪深300权重 `>= 12%`，实际只有 `2.13%`。
- 目标 top20 覆盖 `>= 25%`，实际只有 `2.79%`。

同时，第 5 折收益、回撤、换手和行业审计都明显失败，不应继续小参数调优。

## 产物

- admission：`reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/admission/`
- failure attribution：`reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/failure_attribution/`
- market context：`reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/market_context/`
- holdings exposure：`reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/holdings_exposure/`
- CSI300 attribution：`reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/csi300_attribution_mixed_context/`
- 用户简报：`reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/briefings/iter_37__strong_market_effective_participation_brief.md`

## 下一步

不要继续调 I37 的权重倍数、top_n 或单票上限。下一轮应做强市场候选池可达性诊断：按日统计强指数状态下有多少沪深300成分股同时满足 PIT、流动性、趋势、行业和权重可见性约束，先判断低参与度来自候选池不足还是组合构造器不足。
