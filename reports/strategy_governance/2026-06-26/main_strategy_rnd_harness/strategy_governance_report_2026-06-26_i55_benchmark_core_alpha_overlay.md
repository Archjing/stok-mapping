# Strategy Governance Report - 2026-06-26 - I55 Benchmark Core Alpha Overlay

## 背景

本报告由 2026-06-26 凌晨 Harness 策略研发流程生成。目标仍是项目北极星目标：

- 找到至少一个适合当前市场环境、可指导实盘操作并具备较可观盈利潜力的量化策略。
- 形成覆盖不同市场环境和市场风格的策略池。
- 形成可复查的策略选择方法论。

I51-I54 的结论是：`strong_market_benchmark_aware_core_v1` 已经把沪深300核心股覆盖做上去，但收益没有出来；继续扩大强市场参与度或强制状态切换调仓无效。因此 I55 验证一个更小的问题：

> 在不牺牲沪深300核心覆盖的前提下，核心股内部的有限 alpha overlay 能否改善超额收益？

## 代码与配置变更

新增或修改：

- `phase0/strategies/strong_market_stable_core_base.py`
  - 新增 `benchmark_core_alpha_overlay_v1`。
  - 使用 `85%` benchmark anchor + `15%` alpha overlay。
  - alpha overlay 只在沪深300核心成分内部排序，不把非核心股提升为主要持仓。
  - alpha 信号使用行业内相对 `mom60`、`mom20`、低 `vol20`、`amount_ratio20`。
  - 修正行业中性 rank 方向，确保高动量给高分、低波给高分。
- `phase0/strategies/__init__.py`
  - 注册新策略类。
- `phase0/strategy_admission.py`
  - scoped admission 指定 `benchmark_core_alpha_overlay_v1` 时自动启用 `local_factor.benchmark_core_alpha_overlay`。
- `tests/test_strong_market_stable_core_base_strategy.py`
  - 覆盖新策略注册、research-only 边界、overlay 权重倾斜、行业中性 rank 方向。
- `tests/test_strategy_admission_config.py`
  - 覆盖 admission 启用映射。
- `config.main_strategy_i55_benchmark_core_alpha_overlay_20260626.yaml`
  - I55 专用 research-only 配置。

默认 `baseline_admission_all_v1` 未变；新策略没有进入默认 12 个候选池。

## 执行命令

```bash
./.venv/bin/python -m pytest tests/test_strong_market_stable_core_base_strategy.py tests/test_strategy_admission_config.py -q -s
```

```bash
./.venv/bin/python -m phase0.cli strategy-admission --config config.main_strategy_i55_benchmark_core_alpha_overlay_20260626.yaml --presets baseline_2y_1y_5fold --strategy-set i55_benchmark_core_alpha_overlay_v1 --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/admission
```

```bash
./.venv/bin/python -m phase0.cli strategy-failure-attribution --config config.main_strategy_i55_benchmark_core_alpha_overlay_20260626.yaml --admission-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/admission --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/failure_attribution
```

```bash
./.venv/bin/python -m phase0.cli strategy-market-context --config config.main_strategy_i55_benchmark_core_alpha_overlay_20260626.yaml --fold-attribution reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/failure_attribution/strategy_failure_fold_attribution.csv --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/market_context
```

```bash
./.venv/bin/python -m phase0.cli strategy-holdings-exposure --config config.main_strategy_i55_benchmark_core_alpha_overlay_20260626.yaml --candidate-folds reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/admission/strategy_admission_candidate_folds.csv --market-context reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/market_context/strategy_market_context_diagnostic.csv --strategy benchmark_core_alpha_overlay_v1 --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/holdings_exposure
```

```bash
./.venv/bin/python -m phase0.cli strategy-csi300-attribution --config config.main_strategy_i55_benchmark_core_alpha_overlay_20260626.yaml --holdings reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/holdings_exposure/strategy_daily_holdings.csv --daily-exposure reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/holdings_exposure/strategy_daily_exposure.csv --candidate-folds reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/admission/strategy_admission_candidate_folds.csv --market-context reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/market_context/strategy_market_context_diagnostic.csv --context-label all --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/csi300_attribution_all --top-n 20
```

## 验证结果

定向测试：

- `52 passed, 1 warning`

Admission 摘要：

| 策略 | action | 年化收益 | Sharpe | 正收益折 | 正超额折 | 平均超额年化 | 年化换手 |
| ---- | ---- | ---: | ---: | ---: | ---: | ---: | ---: |
| `benchmark_core_alpha_overlay_v1` | `reject` | `-0.0019` | `-0.0999` | `0.40` | `0.60` | `0.0260` | `0.58` |

覆盖归因摘要：

| 指标 | I55 修正版 |
| ---- | ---: |
| 平均 live exposure | `0.2015` |
| 平均持有沪深300权重 | `0.6370` |
| 平均 Top20 覆盖率 | `0.9932` |
| 平均行业 L1 偏离 | `0.3425` |
| 强基准阶段平均超额年化 | `-0.0907` |

## 阶段判断

`benchmark_core_alpha_overlay_v1` 运行正确，但没有形成有效策略突破。

它证明了一个负面结论：在当前数据和日线因子口径下，简单的核心股内部动量、低波和成交活跃度倾斜，不能显著改善 I51 的收益质量。

本轮不能把该策略加入默认候选池，不能进入 paper review、模拟账户、日报或 watchlist。

## 下一步

下一轮不建议继续调 I55 的 overlay 参数。建议做 `I56 alpha source audit`：

- 拆解 I51/I55 在强基准阶段跑输的持仓贡献。
- 找出实际贡献负超额的是哪些核心股、行业和风格。
- 再判断是否需要引入新的 alpha 来源，例如 PIT 财务质量、公告/情报、指数权重变化、行业景气，而不是继续扩大日线价格因子的参数空间。

## 工程备注

I55 admission 和 holdings exposure 都需要重放 CSI300 core seed panel，单次运行耗时偏高。后续可以考虑为 fold-local seed panel 增加缓存，降低 Harness 迭代成本。
