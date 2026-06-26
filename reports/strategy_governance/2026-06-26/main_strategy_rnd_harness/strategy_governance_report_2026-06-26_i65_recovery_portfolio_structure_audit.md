# Strategy Governance Report - I65 Recovery Portfolio Structure Audit

日期：2026-06-26

报告性质：Harness 策略研发专项审计报告。本报告只审计 recovery 期间组合结构，不新增策略、不改变 admission。

## 背景

I64 说明单一的 `drawdown_delta_20d` 无法可靠区分有效 recovery 和错误 recovery。下一步需要判断：错误是否来自市场状态识别，还是来自 recovery 期间的组合行业结构。

I65 使用 I63 的本地 holdings/industry 产物做组合结构审计。

## 输入

- `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_63__recovery_quality/holdings_exposure/strategy_daily_exposure.csv`
- `reports/strategy_governance/2026-06-26/main_strategy_rnd_harness/evidence/iter_63__recovery_quality/holdings_exposure/strategy_daily_industry_exposure.csv`

## 产物

- `recovery_top_industry_daily.csv`
- `recovery_industry_exposure_summary.csv`
- `recovery_portfolio_structure_fold_summary.csv`
- `recovery_portfolio_structure_audit.md`

## 关键结果

| fold | recovery 天数 | quality 天数 | recovery 期间沪深300收益 | 平均头部行业权重 | 头部行业出现次数 |
| --- | ---: | ---: | ---: | ---: | --- |
| 2 | 56 | 34 | -0.041549 | 0.060802 | 白酒=55; 电气设备=1 |
| 3 | 22 | 11 | 0.014722 | 0.032370 | 银行=16; 白酒=5; IT设备=1 |
| 4 | 49 | 17 | -0.022057 | 0.057802 | 银行=48; IT设备=1 |
| 5 | 46 | 41 | 0.143221 | 0.097012 | 银行=46 |

## 判断

fold2、fold4、fold5 的 recovery 期间组合都存在明显头部行业暴露，但收益表现不同。fold5 的银行暴露在强修复期有效；fold4 的银行暴露没有带来收益；fold2 的白酒暴露明显拖累。

因此，问题不能简单归因于“recovery trigger 错”。更准确的说法是：

- recovery trigger 找到了一些可参与窗口；
- 但 recovery 状态下的行业/权重配置还没有方法论；
- 当前组合可能在某些 recovery 阶段承担了错误行业暴露。

## 下一步

I66 应做相对沪深300行业偏离审计：

1. 用 as-of 沪深300权重构建 benchmark industry exposure；
2. 对 recovery 日期计算策略行业权重 - benchmark 行业权重；
3. 比较 fold2/fold4/fold5 的主要 active industry；
4. 决定 recovery 状态下是否要降低 alpha tilt，改为更贴近 benchmark 行业权重。

不建议立刻再加新策略。先把行业偏离证据补完整。
