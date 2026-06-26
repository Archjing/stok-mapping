# Strategy Governance Report - 2026-06-26 - I51-I54 Benchmark-Aware Core

## 背景

本报告由 2026-06-26 凌晨 Harness 策略研发流程生成。目标是继续推进项目北极星目标：

- 找到至少一个适合当前市场环境、可指导实盘操作并具备较可观盈利潜力的量化策略。
- 形成覆盖不同市场环境和市场风格的策略池。
- 形成可复查的策略选择方法论。

I49/I50 的前置结论是：`strong_market_stable_core_base_v1` 在强沪深300阶段存在参与不足，平均 live exposure、沪深300权重持有、Top20 覆盖和行业贴近度都不够。因此本轮预注册并实现 `strong_market_benchmark_aware_core_v1`。

## 代码与配置变更

新增或修改：

- `phase0/strategies/strong_market_stable_core_base.py`
  - 新增 `strong_market_benchmark_aware_core_v1`。
  - 复用 PIT core seed、T-1 `cn_index_weights_asof`、`qfq_asof` 价格。
  - 支持 benchmark-aware core 权重、宽松上下文识别、状态切换触发调仓参数。
  - Reviewer 复核后修正：I51 默认 `context_mode=standard`；I52/I54 显式启用 `benchmark_aware_relaxed`；移除未使用的 `relaxed_allow_high_vol` 假开关。
- `phase0/strategies/__init__.py`
  - 注册新策略类。
- `phase0/strategy_admission.py`
  - scoped admission 指定新策略时自动启用 `local_factor.strong_market_benchmark_aware_core`。
- `tests/test_strong_market_stable_core_base_strategy.py`
  - 覆盖新策略注册、research-only 边界、三档仓位、上下文放宽和状态切换调仓。
- `tests/test_strategy_admission_config.py`
  - 覆盖 admission 启用映射。
- `config.main_strategy_i51_strong_market_benchmark_aware_core_20260626.yaml`
- `config.main_strategy_i52_benchmark_aware_relaxed_context_20260626.yaml`
- `config.main_strategy_i53_context_switch_rebalance_20260626.yaml`
- `config.main_strategy_i54_context_switch_rebalance_param_fix_20260626.yaml`

默认 `baseline_admission_all_v1` 未变；新策略没有进入默认 12 个候选池。

## 执行命令

```bash
./.venv/bin/python -m pytest tests/test_strong_market_stable_core_base_strategy.py tests/test_strategy_admission_config.py -q -s
```

```bash
./.venv/bin/python -m phase0.cli strategy-admission --config config.main_strategy_i51_strong_market_benchmark_aware_core_20260626.yaml --presets baseline_2y_1y_5fold --strategy-set i51_strong_market_benchmark_aware_core_v1 --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/admission
```

Reviewer 修正 `context_mode` 默认值后，I51/I52/I54 admission 已重跑。权威 admission 输出目录为：

```bash
./.venv/bin/python -m phase0.cli strategy-admission --config config.main_strategy_i51_strong_market_benchmark_aware_core_20260626.yaml --presets baseline_2y_1y_5fold --strategy-set i51_strong_market_benchmark_aware_core_v1 --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core_rerun_after_context_default_fix/admission
```

```bash
./.venv/bin/python -m phase0.cli strategy-admission --config config.main_strategy_i52_benchmark_aware_relaxed_context_20260626.yaml --presets baseline_2y_1y_5fold --strategy-set i52_benchmark_aware_relaxed_context_v1 --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context_rerun_after_context_default_fix/admission
```

```bash
./.venv/bin/python -m phase0.cli strategy-admission --config config.main_strategy_i54_context_switch_rebalance_param_fix_20260626.yaml --presets baseline_2y_1y_5fold --strategy-set i54_context_switch_rebalance_param_fix_v1 --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_54__context_switch_rebalance_param_fix_rerun_after_context_default_fix/admission
```

```bash
./.venv/bin/python -m phase0.cli strategy-failure-attribution --config config.main_strategy_i51_strong_market_benchmark_aware_core_20260626.yaml --admission-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/admission --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/failure_attribution
```

```bash
./.venv/bin/python -m phase0.cli strategy-market-context --config config.main_strategy_i51_strong_market_benchmark_aware_core_20260626.yaml --fold-attribution reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/failure_attribution/strategy_failure_fold_attribution.csv --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/market_context
```

```bash
./.venv/bin/python -m phase0.cli strategy-holdings-exposure --config config.main_strategy_i51_strong_market_benchmark_aware_core_20260626.yaml --candidate-folds reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/admission/strategy_admission_candidate_folds.csv --market-context reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/market_context/strategy_market_context_diagnostic.csv --strategy strong_market_benchmark_aware_core_v1 --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/holdings_exposure
```

```bash
./.venv/bin/python -m phase0.cli strategy-csi300-attribution --config config.main_strategy_i51_strong_market_benchmark_aware_core_20260626.yaml --holdings reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/holdings_exposure/strategy_daily_holdings.csv --daily-exposure reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/holdings_exposure/strategy_daily_exposure.csv --candidate-folds reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/admission/strategy_admission_candidate_folds.csv --market-context reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/market_context/strategy_market_context_diagnostic.csv --context-label all --output-dir reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/csi300_attribution_all --top-n 20
```

I52、I53/I54 使用同一 scoped admission 口径，输出分别落到：

- `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_52__benchmark_aware_relaxed_context_rerun_after_context_default_fix/`
- `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_53__context_switch_rebalance/`
- `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_54__context_switch_rebalance_param_fix_rerun_after_context_default_fix/`

## 验证结果

定向测试：

- `48 passed, 1 warning`

admission 摘要：

| 迭代 | 策略 | action | 年化收益 | Sharpe | 正收益折 | 正超额折 | 平均超额年化 | 年化换手 |
| ---- | ---- | ---- | ---: | ---: | ---: | ---: | ---: | ---: |
| I51 | `strong_market_benchmark_aware_core_v1` | `reject` | `-0.0009` | `-0.1011` | `0.40` | `0.60` | `0.0269` | `0.59` |
| I52 | `strong_market_benchmark_aware_core_v1` | `reject` | `-0.0070` | `-0.1902` | `0.40` | `0.60` | `0.0208` | `0.59` |
| I54 | `strong_market_benchmark_aware_core_v1` | `reject` | `-0.0264` | `-0.4963` | `0.20` | `0.60` | `0.0014` | `3.67` |

I51 沪深300归因摘要：

- 平均持有沪深300权重：约 `0.62` - `0.66`。
- Top20 覆盖率：约 `0.98` - `0.996`。
- 行业 L1 偏离：约 `0.34` - `0.38`。
- 强基准阶段平均 live exposure：约 `0.249`。
- 强基准阶段平均超额年化：约 `-0.0861`。

I52 持仓暴露：

- 强基准阶段平均 live exposure 提高到约 `0.2737`。
- 强基准阶段平均超额年化下降到约 `-0.1014`。

I54：

- 状态切换触发调仓参数生效后，年化换手升至 `3.67`，超过 admission 换手门槛。
- 年化收益和 Sharpe 明显恶化。

## 阶段判断

`strong_market_benchmark_aware_core_v1` 解决了“核心股覆盖不足”的诊断问题，但没有解决“强市场下取得正超额”的策略问题。

本轮不能把该策略加入默认候选池，不能进入 paper review、模拟账户、日报或 watchlist。

## 下一步

下一轮应停止继续微调 benchmark-aware core 的参与度参数。建议转向：

- `benchmark_core_alpha_overlay_v1`
- 在沪深300核心股内部寻找 alpha：
  - 相对强弱；
  - 盈利质量；
  - 资金流；
  - 波动结构；
  - 行业内相对排名。
- 先固定“核心覆盖不下降”的约束，再验证 alpha overlay 是否改善正超额折比例。
