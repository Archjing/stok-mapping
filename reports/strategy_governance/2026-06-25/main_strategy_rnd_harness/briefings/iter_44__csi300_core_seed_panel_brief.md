# Harness Iteration Brief - 2026-06-25 - I44 CSI300 Core Seed Panel

## 一句话结论

I44 通过了。

把 as-of 可见的沪深300核心权重股票显式补进诊断面板后，五个验证折全部达到可达性门槛。说明强市场参与型策略的下一步，可以从“修候选池看不见核心股”推进到“设计如何在强市场里选择和持有这些核心股”。

这不是交易策略通过，也不是要求固定买沪深300前20只。它只说明：策略候选池现在有机会看见这些股票。

## 本轮修正

I43 之后原来把完整 Top20 的 `35%` 绝对权重当成硬门槛。I44 发现这个口径不合理：

- 沪深300 Top20 本身在不同年份的总权重会变。
- 本轮五折里 Top20 平均绝对权重大约只有 `32.84%`。
- 如果要求 Top20 可达绝对权重必须超过 `35%`，即使 Top20 全部覆盖也可能过不了。

所以 I44 把门槛改为：

- 核心成分可达绝对权重仍要高于 `50%`。
- 核心成分覆盖率要高于 `90%`。
- Top20 覆盖率要高于 `98%`。

这样判断的是“能不能覆盖到核心股票”，不是“沪深300当期是否足够集中”。

## 运行命令

```bash
./.venv/bin/python -m phase0.cli strategy-core-reachability-diagnostic --config config.main_strategy_i37_strong_market_effective_participation_20260625.yaml --candidate-folds reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/admission/strategy_admission_candidate_folds.csv --seed-benchmark-core --seed-top-n 20 --seed-core-top-n 60 --seed-core-cumulative-weight 0.60 --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_44__csi300_core_seed_panel/core_seed_panel/core_reachability
```

```bash
./.venv/bin/python -m phase0.cli strategy-missing-core-audit --config config.main_strategy_i37_strong_market_effective_participation_20260625.yaml --missing-reasons reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_44__csi300_core_seed_panel/core_seed_panel/core_reachability/strategy_core_reachability_failure_reasons.csv --candidate-folds reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_37__strong_market_effective_participation/admission/strategy_admission_candidate_folds.csv --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_44__csi300_core_seed_panel/core_seed_panel/missing_core_audit
```

## 核心结果

| 方案 | 平均核心可达权重 | 最低核心可达权重 | 平均核心覆盖率 | 平均 Top20 可达权重 | 平均 Top20 覆盖率 | 状态 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| I40 panel=120 | 55.38% | 52.01% | 92.48% | 32.69% | 99.54% | 失败 |
| I43 panel=200 | 57.72% | 55.20% | 96.40% | 32.73% | 99.66% | 失败 |
| I43 panel=300 | 58.55% | 56.50% | 97.78% | 32.82% | 99.95% | 失败 |
| I44 seed core | 59.45% | 57.25% | 99.28% | 32.82% | 99.95% | 通过 |

解释：

- I44 不是靠放宽策略条件过关。
- 它只是把沪深300核心成分放进只读诊断面板，验证候选池是否有机会覆盖核心股。
- Top20 可达权重仍是约 `32.82%`，这是沪深300当期 Top20 自身权重水平，不是策略漏掉了 Top20。
- 真正重要的是 Top20 覆盖率接近 `100%`。

## 剩余缺口

剩余失败原因仍要记录，但不阻断 I44：

| 原因 | 行数 | 股票数 | 权重合计 |
| --- | ---: | ---: | ---: |
| `missing_industry` | 876 | 1 | 4.3941 |
| `missing_from_pit_panel` | 134 | 11 | 0.8236 |

主要数据治理点：

- `SH.600837` 缺名称和行业，导致大量 `missing_industry`。
- 少数股票仍有短窗口 panel 缺日。
- 这些问题会影响后续策略稳定性，但不改变 I44 的主结论。

## 决策

I44 回答了一个前置问题：

> 如果显式保留沪深300核心成分，候选池是否能覆盖强市场参与型策略需要看的股票？

答案：能。

所以主线可以进入下一步：预注册一个新的强市场核心参与候选。这个候选不应固定买 Top20，而应：

1. 先保证沪深300核心股票可被纳入候选池。
2. 再用趋势、流动性、风险和行业约束决定实际持仓。
3. 最后用 admission、持仓暴露和 CSI300 attribution 验证是否真的改善强市场参与度。

## 下一步

I45 建议做 `strong_market_core_participation_v1` 预注册设计：

- 使用 I44 的 core seed panel 思路。
- 不复制沪深300。
- 不固定买前20只。
- 不绕过 PIT、`qfq_asof`、成本和 admission。
- 明确强市场折最低仓位、持有沪深300权重、Top20 覆盖和换手约束。

只有 I45 设计通过后，才进入实现。

## 产物

- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_44__csi300_core_seed_panel/core_seed_panel/core_reachability/`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_44__csi300_core_seed_panel/core_seed_panel/missing_core_audit/`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_44__csi300_core_seed_panel/core_seed_panel/seed_panel_reachability_summary.csv`
- `reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_44__csi300_core_seed_panel/core_seed_panel/seed_panel_failure_reason_summary.csv`
