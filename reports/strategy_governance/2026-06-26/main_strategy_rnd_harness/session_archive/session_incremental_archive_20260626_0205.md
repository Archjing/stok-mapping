# Session Incremental Archive - 2026-06-26 02:05

## 新增标准和关键决策

- 本轮继续遵守：策略结论必须区分 research-only、admission、paper review、模拟账户、日报和 watchlist。
- I55 新策略 `benchmark_core_alpha_overlay_v1` 只作为 scoped research-only 候选，不加入默认 12 个候选池。
- I55 的最小验证变量固定为 `85%` benchmark anchor + `15%` alpha overlay，不做参数网格搜索。
- 发现并修正行业中性 rank 方向错误；最终结论以 `iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix` 为准。
- I55 结论：覆盖没有退化，但收益没有改善；不继续调 overlay 参数，下一步转向 alpha source audit。

## 执行摘要

- 启动 Planner 和 Explorer 两个子智能体：
  - Planner 建议 I55 固定为受约束的核心股内部 alpha overlay，不做新一轮参数搜索。
  - Explorer 确认现有代码已具备动量、低波、流动性、质量成长、行业相对强弱等因子；显式资金流字段不存在。
- 实现 `benchmark_core_alpha_overlay_v1`：
  - 复用 I51 的 benchmark-aware core 框架。
  - 新增行业中性 alpha rank。
  - 权重结构为 `85%` 沪深300核心权重锚 + `15%` alpha overlay。
- 跑 scoped admission、failure attribution、market context、holdings exposure、CSI300 attribution。

## 变更文件

- `phase0/strategies/strong_market_stable_core_base.py`
- `phase0/strategies/__init__.py`
- `phase0/strategy_admission.py`
- `tests/test_strong_market_stable_core_base_strategy.py`
- `tests/test_strategy_admission_config.py`
- `config.main_strategy_i55_benchmark_core_alpha_overlay_20260626.yaml`

## 生成报告

- `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/briefings/iter_55__benchmark_core_alpha_overlay_brief.md`
- `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/strategy_governance_report_2026-06-26_i55_benchmark_core_alpha_overlay.md`

## 权威证据目录

- `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/admission/`
- `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/failure_attribution/`
- `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/market_context/`
- `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/holdings_exposure/`
- `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_55__benchmark_core_alpha_overlay_rerun_after_rank_direction_fix/csi300_attribution_all/`

## 验证结果

- `./.venv/bin/python -m pytest tests/test_strong_market_stable_core_base_strategy.py tests/test_strategy_admission_config.py -q -s`
- 结果：`52 passed, 1 warning`
- `git diff --check` 在本轮核心代码、测试和 I55 配置上通过。

## I55 关键指标

| 指标 | 结果 |
| ---- | ---: |
| admission action | `reject` |
| 年化收益均值 | `-0.0019` |
| Sharpe 均值 | `-0.0999` |
| 正收益折比例 | `0.40` |
| 正超额折比例 | `0.60` |
| 平均超额年化 | `0.0260` |
| 年化换手均值 | `0.58` |
| 平均持有沪深300权重 | `0.6370` |
| 平均 Top20 覆盖率 | `0.9932` |
| 平均行业 L1 偏离 | `0.3425` |

## 下一步

- 不继续微调 I55 的 `anchor_sleeve_ratio`、`overlay_sleeve_ratio`、`alpha_tilt_strength`。
- 做 `I56 alpha source audit`，拆解 I51/I55 强基准阶段跑输来自哪些核心股、行业、风格或信息源不足。
- 评估是否需要引入新的 alpha 来源，例如 PIT 财务质量、公告/情报、指数权重变化、行业景气。
