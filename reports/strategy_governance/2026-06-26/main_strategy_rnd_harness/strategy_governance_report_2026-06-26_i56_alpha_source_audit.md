# Strategy Governance Report - I56 Alpha Source Audit

生成日期：2026-06-26

## 报告背景

本报告是 2026-06-26 主线策略研发 Harness 的 I56 专项审计报告。前几轮结论已经显示：

- I51 `strong_market_benchmark_aware_core_v1` 解决了一部分“候选池触达沪深300核心股”的问题，但 admission 仍为 `reject`。
- I55 `benchmark_core_alpha_overlay_v1` 在核心持仓上叠加行业中性价格/波动/流动性 alpha，但 admission 仍为 `reject`。
- 两者共同的问题集中在 `relative_lag_in_strong_benchmark_context`，也就是“沪深300明显强，但策略相对落后”的窗口。

本轮不新增交易策略，先补一个可复用的 alpha 来源审计模块，用实际持仓和 CSI300 归因产物回答：I55 到底有没有改善强基准阶段的损失来源。

## 本轮代码变更

| 文件 | 作用 |
| --- | --- |
| `phase0/strategy_alpha_source_audit.py` | 新增只读审计 API，合并 fold、持仓贡献、行业贡献、漏持头部成分四类证据 |
| `tests/test_strategy_alpha_source_audit.py` | 覆盖 fold delta、个股贡献 delta、行业贡献 delta、漏持头部成分对比 |

本轮没有修改 `phase0/cli.py`，因为该文件当前已有其他未提交改动。为避免混入无关 diff，I56 先提供可复用 API 和报告产物，后续可在工作区干净时再接入 CLI。

## 输入数据

| 类别 | 路径 |
| --- | --- |
| I51 CSI300 fold attribution | `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/csi300_attribution_all/strategy_csi300_fold_attribution.csv` |
| I51 daily holdings | `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/holdings_exposure/strategy_daily_holdings.csv` |
| I51 missed top weights | `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_51__strong_market_benchmark_aware_core/csi300_attribution_all/strategy_csi300_missed_top_weights.csv` |
| I55 CSI300 fold attribution | `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/csi300_attribution_all/strategy_csi300_fold_attribution.csv` |
| I55 daily holdings | `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/holdings_exposure/strategy_daily_holdings.csv` |
| I55 missed top weights | `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/csi300_attribution_all/strategy_csi300_missed_top_weights.csv` |

过滤口径：`market_context_label = relative_lag_in_strong_benchmark_context`。

## 输出产物

| 产物 | 行数 | 用途 |
| --- | ---: | --- |
| `evidence/iter_56__alpha_source_audit/strategy_alpha_source_fold_comparison.csv` | 2 | 对比 fold 4、fold 5 的强基准窗口指标 |
| `evidence/iter_56__alpha_source_audit/strategy_alpha_source_symbol_contribution.csv` | 133 | 找出 I55 相比 I51 改善或恶化最多的个股贡献 |
| `evidence/iter_56__alpha_source_audit/strategy_alpha_source_industry_contribution.csv` | 48 | 找出 I55 相比 I51 改善或恶化最多的行业贡献 |
| `evidence/iter_56__alpha_source_audit/strategy_alpha_source_missed_top_comparison.csv` | 23 | 对比头部沪深300成分漏持情况 |
| `evidence/iter_56__alpha_source_audit/strategy_alpha_source_audit.md` | 1 | 自动生成的审计说明 |
| `briefings/iter_56__alpha_source_audit_brief.md` | 1 | 面向人工复盘的简报 |

## 关键结论

| 问题 | 结论 |
| --- | --- |
| 是否因为没覆盖沪深300前20？ | 不是主要原因。I55 在强基准 fold 的前20覆盖率约 99.59%，名义覆盖已经很高。 |
| 是否因为参与仓位太低？ | 是主要原因。I55 在 fold 4 实际仓位约 14.90%，fold 5 约 34.86%，没有充分吃到沪深300上涨。 |
| I55 是否改善强基准超额？ | 没有。fold 4 几乎持平但略差，fold 5 比 I51 差约 0.89pct。 |
| I55 alpha overlay 有什么副作用？ | 削弱了元器件、通信设备等强市场正贡献来源。 |
| 下一步是否继续调 I55 参数？ | 不建议。应改为验证“强市场提高参与仓位”的新策略假设。 |

## Fold 级结果

| Fold | I51 excess total return | I55 excess total return | I55 - I51 | I55 live exposure | I55 top20 coverage | dominant gap |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 4 | -7.78% | -7.79% | -0.01pct | 14.90% | 99.59% | low_participation |
| 5 | -9.75% | -10.64% | -0.89pct | 34.86% | 99.59% | low_participation |

解释：I55 不是因为完全漏掉核心成分而失败，而是核心参与权重偏低。持有名单看起来覆盖了很多核心股，但总仓位和相对基准权重都不足。

## 行业与个股归因

I55 相比 I51 明显削弱的正贡献来源：

| 来源 | I51 贡献 | I55 贡献 | 变化 |
| --- | ---: | ---: | ---: |
| 元器件 | +1.30% | +0.15% | -1.15pct |
| 通信设备 | +2.27% | +1.49% | -0.78pct |
| 染料涂料 | +0.46% | 0.00% | -0.46pct |
| 其他建材 | +0.19% | 0.00% | -0.19pct |

代表性个股：

| 个股 | 行业 | I51 贡献 | I55 贡献 | 变化 |
| --- | --- | ---: | ---: | ---: |
| 信维通信 | 元器件 | +1.15% | 0.00% | -1.15pct |
| 海格通信 | 通信设备 | +0.74% | 0.00% | -0.74pct |
| 浙江龙盛 | 染料涂料 | +0.46% | 0.00% | -0.46pct |
| 宁德时代 | 电气设备 | +0.75% | +0.66% | -0.09pct |

这说明 I55 的行业中性 alpha overlay 没有抓住强市场中真正有贡献的风格/行业，反而削掉了一些已经有效的强势贡献来源。

## 对北极星目标的影响

项目北极星目标是形成能指导实盘操作的策略池，并形成不同市场环境下的策略选择方法论。I56 对方法论的贡献是：

1. 强基准行情下，不能只看“是否覆盖沪深300头部股票”，还要看实际参与仓位和持有基准权重。
2. 简单价格/波动/流动性 alpha overlay 不足以解决强市场落后问题。
3. 策略池需要一个“强市场参与型”候选，而不是继续把防守型或低波动逻辑硬套到强市场。

## 下一步策略假设

建议 I57 设计 `strong_benchmark_participation_boost_v1`：

- 当沪深300处于强趋势且风险压力不高时，提高核心仓位参与。
- 保留沪深300核心权重锚，避免名义覆盖高但实际仓位低。
- 行业/风格上不要简单追求中性，要允许强势行业获得更高参与。
- 仍需用 walk-forward admission 检查：fold 4/5 是否改善，其他弱市/risk context 是否出现明显损伤。

## 验证记录

已执行：

```bash
./.venv/bin/python -m pytest tests/test_strategy_alpha_source_audit.py -q -s
```

结果：`1 passed`。

待执行：

- 在 I57 新策略落地后，跑同样的 alpha source audit，对比 I51、I55、I57。
- 在工作区干净后考虑把该审计能力接入 `phase0.cli`。
