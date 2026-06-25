# Session Incremental Archive - 2026-06-25 10:05 - I34 Harness

## 本次用户新增标准

- 后续开发工作标准：在上下文压缩之前，将项目会话记录增量归档到合适位置。
- 执行口径：保留有价值内容，记录关键决策、命令、文件、报告、测试和后续动作；不把临时状态更新和大段工具输出原样堆入归档。

## 本轮 Harness 目标

- 回到策略研发主线，接续 I32/I33 后继续推进北极星目标。
- 当前 I34 目标：在已有 CSI300 成分 / 权重 as-of 数据基础上，补“强沪深300跑输”的权重归因，回答低参与度、行业错配、权重股遗漏和个股选择失败之间的区别。

## 关键实现

- 新增只读归因模块：`phase0/strategy_csi300_attribution.py`
- 新增 CLI：`strategy-csi300-attribution`
- 新增测试：`tests/test_strategy_csi300_attribution.py`
- CLI 接入：`phase0/cli.py`
- 更新 Harness 工作流：`docs/CODEX_MCP_MULTI_AGENT_WORKFLOW.md`
  - 新增上下文压缩前会话增量归档要求。
  - 明确归档路径、文件命名、归档内容和噪音处理原则。
- 更新策略池任务文档：`docs/tasks/strategy/PHASE0_CANDIDATE_STRATEGIES.md`
  - 标记 I34 完成。
  - 新增下一步：把同一归因工具套到 I15/I18/I20 强市场失败样本。

## 运行命令

```bash
./.venv/bin/python -m pytest -s tests/test_strategy_csi300_attribution.py
```

结果：`4 passed`

```bash
./.venv/bin/python -m phase0.cli strategy-csi300-attribution \
  --config config.yaml \
  --holdings reports/strategy_governance/2026-06-24/main_strategy_admission_breakthrough/evidence/iter_10__daily_holdings_exposure/strategy_daily_holdings.csv \
  --daily-exposure reports/strategy_governance/2026-06-24/main_strategy_admission_breakthrough/evidence/iter_10__daily_holdings_exposure/strategy_daily_exposure.csv \
  --output-dir reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_34__csi300_weight_attribution \
  --top-n 20
```

结果：

- 状态：`ok`
- 日度归因行数：`444`
- 折级归因行数：`2`
- 输出目录：`reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_34__csi300_weight_attribution/`
- reviewer 后重跑口径：默认 `weight_date_lag_days=1`，即每个持仓日只使用 `date - 1 day` 以前最近的沪深300权重记录，避免把同日收盘后才可确认的权重当作事前可见。

## I34 结论摘要

对 `price_volume_low_turnover_v1` 的 I10 强沪深300跑输样本：

- 第 4 折：平均实际仓位 `42.57%`，持有的沪深300权重约 `3.64%`，沪深300前 20 大权重股覆盖率 `2.65%`；策略总收益 `8.62%`，沪深300 `9.89%`，超额 `-1.27%`。
- 第 5 折：平均实际仓位 `46.07%`，持有的沪深300权重约 `4.91%`，沪深300前 20 大权重股覆盖率 `9.78%`；策略总收益 `5.16%`，沪深300 `15.23%`，超额 `-10.06%`。
- 主要解释：强指数阶段主要是低参与度和高权重股覆盖不足，不支持把该候选改造成强沪深300参与型策略。
- 重要边界：该结论不是交易建议，不改变 admission；`price_volume_low_turnover_v1` 仍只适合作为防守 / 选择性 research-only 样本。

## 生成报告

- 用户简报：`reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/briefings/iter_34__csi300_weight_attribution_brief.md`
- 技术报告：`reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_34__csi300_weight_attribution/strategy_csi300_attribution_report.md`
- 日度归因：`reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_34__csi300_weight_attribution/strategy_csi300_daily_attribution.csv`
- 折级归因：`reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_34__csi300_weight_attribution/strategy_csi300_fold_attribution.csv`
- 遗漏权重股：`reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_34__csi300_weight_attribution/strategy_csi300_missed_top_weights.csv`
- 行业主动权重：`reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_34__csi300_weight_attribution/strategy_csi300_industry_active_weights.csv`
- 运行日志：`reports/strategy_governance/2026-06-25/main_strategy_rnd_harness/evidence/iter_34__csi300_weight_attribution/strategy_csi300_attribution_run_log.md`

## 后续动作

1. 用 `strategy-csi300-attribution` 继续分析 I15/I18/I20 三个强市场失败样本。
2. 若这些样本仍显示高权重覆盖不足，不继续调触发器，而是预注册一个真正围绕 CSI300 权重和流动性的强市场候选。
3. 后续上下文压缩前继续写入本目录下的 `session_archive/` 增量归档。
