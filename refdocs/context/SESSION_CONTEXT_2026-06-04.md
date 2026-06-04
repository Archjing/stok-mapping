# 2026-06-04 Session 上下文与原文归档

本文件合并当前 session 上下文、非代码工作会话原文和策略研发方向问答归档。下方各节保留原文件正文，便于追溯。

## 合并来源

- `refdocs/context/session_context_2026-06-04.md`
- `refdocs/context/session_dialogue_after_1000_non_code_2026-06-04.md`
- `refdocs/context/strategy_research_direction_qa_2026-06-04.md`

---

## 原文件：`refdocs/context/session_context_2026-06-04.md`

# stok-mapping 当前 Session 上下文归档

归档日期：2026-06-04

导航：[`refdocs 索引`](../README.md)

## 项目归属

本轮关于 A 股量化、Tushare 数据回填、as-of 复权治理、策略池诊断、因子有效性与后续研发计划的对话和任务，都属于：

```text
~/workspace/stok-mapping
```

不要误归到 `/home/zj/workspace` 根目录。此前用户一开始进入了错误目录，后续已明确更正。

建议后续从项目目录启动 Codex：

```bash
cd ~/workspace/stok-mapping
codex
```

如果需要参考其他项目代码，应以 `stok-mapping` 为主项目锚点，并显式声明其他项目路径只读或可写。

## 用户偏好

- 默认用中文回答。
- 归档类请求通常要求保留原文或不删内容；若用户说“一字不删”，不得改写原文。
- 当前项目讨论中，用户关注 A 股量化策略从回测到实盘失效、数据治理、未来函数、复权口径和策略研发闭环。

## 当前核心结论

1. 当前 `stok-mapping` 不是“已有可实盘模拟的有效主策略”，而是“Phase 0 工程链路可用，策略需要重建”。
2. 严格策略研究默认可信口径应为：

```text
qfq_asof + point-in-time universe + 成本后验证
```

3. `qfq_current` 只能作为兼容口径参考，不能作为严格 point-in-time 结论。
4. 交易执行、估值、涨跌停、停牌判断必须使用真实未复权价格 `bfq_raw`。
5. `legacy_momentum_low_turnover_v1` 在 `qfq_asof` 下已经失效，不能进入实盘模拟。
6. 最新候选策略池按 `qfq_asof` compare 后没有合格 candidate，策略研发进入重新筛选 candidate 阶段。

## 复权治理状态

已完成 A 股 as-of 前复权治理的关键闭环：

- `market_adj_factors` 历史复权因子已补齐。
- `adjustment-audit` 结论为 `PASS`。
- 本地库可以构造严格的 `qfq_asof`。
- 已建立 `qfq_current` / `qfq_asof` 对照验证思路。

相关任务文件：

```text
docs/tasks/data-sources/ASOF_PRICE_ADJUSTMENT_GOVERNANCE_TASKS.md
```

注意：该文件不在根目录，而在 `docs/tasks/data-sources/` 下。

## 策略对照结论

对 `legacy_momentum_low_turnover_v1` 跑过 `qfq_current` / `qfq_asof` 对照：

- `qfq_asof` 下折均年化约 `-7.51%`
- Sharpe 约 `-0.730`
- OOS Sharpe 从 `qfq_current` 的约 `0.646` 降到约 `0.013`

结论：

- 旧 `qfq_current` 结果降级为兼容口径参考。
- 不能作为严格 point-in-time 结论。
- 不能进入实盘模拟。

按“同一策略族只测最新版本”跑过最新候选池 `qfq_asof` compare：

- 当前无可用于实盘模拟的合格 candidate。
- 相对最好仍是 `legacy_momentum_low_turnover_v1`，但 4 个验证折全部负年化。

## 策略研发方向

已审阅：

```text
docs/STRATEGY_POOL_REVIEW_2026-06-03.md
refdocs/papers/cn/A股有效量化策略报告.md
refdocs/papers/
```

形成的新路线：

```text
因子有效性诊断 -> 低频低换手多因子策略 -> 过拟合准入
```

研发重点：

- 低波
- 低换手
- 质量
- 估值
- 成本后稳定性

动量不再作为默认主策略核心，只能作为 sleeve 或辅助因子。ML / AI / LLM 不应作为首版主交易决策，只能用于二阶段 rerank、解释或研究增强。

已新增实施方案：

```text
docs/EFFECTIVE_QUANT_STRATEGY_RESEARCH_PLAN_2026-06-04.md
```

已新增任务清单：

```text
docs/tasks/strategy/EFFECTIVE_QUANT_STRATEGY_RESEARCH_TASKS.md
```

拆分任务包括：

- `T2.5` 因子有效性诊断报告
- `T2.6` `low_vol_low_turnover_quality_v1`
- `T2.7` `quality_low_turnover_monthly_v1`
- `T2.8` `strategy-admission` 准入报告
- `T2.9` sleeve 组合与二阶段 ML rerank
- `T2.10` PEAD / 文本 / 跨市场 overlay 增强

## 因子有效性诊断

已实现 `T2.5 factor-effectiveness` MVP。

CLI：

```bash
./.venv/bin/python -m phase0.cli factor-effectiveness --config config.yaml
```

主要代码：

```text
phase0/factor_effectiveness.py
phase0/cli.py
```

输出目录：

```text
reports/factor_effectiveness/
```

中文报告：

```text
reports/factor_effectiveness/factor_effectiveness.zh.md
```

报告中已补充“被测因子含义解释”。

诊断结论：

可用于首版候选：

- `low_pb`
- `low_vol60`
- `low_turnover_rate`
- `low_vol20`
- `ep`
- `cash_flow_quality`

观察：

- `reversal_mom3`

暂不采用或 reject：

- `reversal_mom5`
- `low_amount_ratio20`
- `profit_growth`
- `roe`
- `mom20`
- `revenue_growth`
- `mom60`
- `low_debt_to_asset`

建议首版候选权重方向：

```text
defensive_quality_score =
  0.30 * low_vol60_rank
+ 0.25 * low_pb_rank
+ 0.20 * ep_rank
+ 0.15 * low_turnover_rate_rank
+ 0.10 * cash_flow_quality_rank
```

自然语言解释：

首版防御质量评分可以把低波动作为最主要权重，其次是低市净率和较高盈利收益率，再辅以低换手率和现金流质量。整体目标是筛选价格波动较低、估值不贵、盈利相对有支撑、交易拥挤度较低且现金流质量较好的股票。

## Tushare 历史数据回填状态

已实现并运行 Tushare 历史数据回填。

CLI：

```bash
./.venv/bin/python -m phase0.cli backfill-tushare-history \
  --config config.yaml \
  --start-date 2016-01-01 \
  --end-date 2026-06-04 \
  --no-financial \
  --max-requests-per-minute 180
```

主要代码：

```text
phase0/tushare_source.py
phase0/tushare_history_backfill.py
phase0/cli.py
```

结果摘要：

- `daily_basic` fetched `1497/2529` dates，rows `5,459,862`
- `adj_factor` fetched `83/2529` dates，rows `254,458`
- dividends rows `0`
- financial skipped
- 警告：`2026-06-04: daily_basic returned empty`

审计报告：

```text
reports/tushare_history_backfill_audit.csv
reports/tushare_history_backfill_audit.md
```

审计摘要：

- `market_adj_factors`：2016-01-04 到 2026-06-04，11,175,324 rows，`adj_factor` 覆盖率 100%
- `market_daily_basic`：2016-01-04 到 2026-06-03，10,672,387 rows，`pb` 覆盖率约 0.99366，`turnover` 覆盖率 1.0
- `market_financial_factors`：仍主要覆盖 2018-06-30 到 2026-03-31，需要补 2016Q1-2018Q1

## Tushare 财务因子逐股票回填

用户积分是 2000，不是 5000。需要注意接口限额。

已设计并落实任务：

- 2016Q1-2018Q1
- 按 `period + ts_code` 逐股票拉取
- 使用任务表记录状态
- 支持断点续跑、失败重试、限速、分片

开发计划条目：

```text
docs/DEVELOPMENT_PLAN.md
```

周任务清单：

```text
docs/tasks/WEEKLY_EXECUTION_CHECKLIST.md
```

CLI：

```bash
./.venv/bin/python -m phase0.cli backfill-tushare-financials \
  --config config.yaml \
  --period 2016-03-31 \
  --limit-symbols 50 \
  --limit-tasks 50 \
  --max-requests-per-minute 120
```

50 只股票验证结果：

- target 49，因为此前已有 1 条单任务验证成功
- processed 49
- fetched 49
- failed 0
- inserted 49
- 合计 2016-03-31 已 fetched 50

审计报告：

```text
reports/tushare_financial_backfill_audit.csv
reports/tushare_financial_backfill_audit.md
```

当前 50 只验证审计：

- `2016-03-31` target_symbols `50`
- fetched `50`
- empty `0`
- failed `0`
- pending `0`
- factor_rows `50`
- 关键覆盖率均为 `1.0`

无后台 financial backfill 进程正在运行。

## 当前代码与注意事项

主要新增或修改过的代码：

```text
phase0/accounts.py
phase0/adjustment.py
phase0/cli.py
phase0/tushare_source.py
phase0/update_history.py
phase0/walk_forward.py
phase0/adjustment_backfill.py
phase0/factor_effectiveness.py
phase0/tushare_history_backfill.py
scripts/export_low_turnover_bill.py
```

验证过：

```bash
./.venv/bin/python -m compileall phase0
```

通过。

注意事项：

- 当前 git worktree 有大量 dirty / untracked 文件，很多是本轮任务成果或运行生成物，不要随意 revert。
- 不要执行 `git reset --hard` 或 `git checkout --` 之类破坏性命令。
- 网络受限；如需真实调用 Tushare，应申请 escalated network 权限。
- 用户此前指定过 0.3 秒间隔，但后来要求撤销增加 0.3s 参数，按此前方案处理。

## 已知实现细节风险

`backfill-tushare-financials` 的设计文本曾要求“已有有效记录默认跳过，除非显式 replace”。

但当前 CLI 实现里：

```text
replace_existing = not bool(args.no_replace_existing)
```

也就是默认会 replace existing，除非传入：

```bash
--no-replace-existing
```

后续如果严格按计划验收，应考虑把默认行为改成“跳过已有有效记录”，再增加显式 `--replace-existing`。

## 重要 refdocs 归档

此前已经归档过：

```text
refdocs/context/SESSION_CONTEXT_2026-06-04.md
refdocs/context/SESSION_CONTEXT_2026-06-04.md
```

当前文件是恢复上下文用，不是逐字聊天记录。

## 建议下一步

1. 修正 `backfill-tushare-financials` 默认 replace 行为，使其符合原计划：默认跳过已有有效记录，显式参数才替换。
2. 在 50 只验证通过后，按接口限额分批跑 2016Q1-2018Q1 全市场财务因子回填。
3. 回填完成后重新运行 `factor-effectiveness`，确认 `cash_flow_quality`、`ep`、`low_pb` 等因子的 PIT 可用性和覆盖率。
4. 基于诊断结果实现 `T2.6 low_vol_low_turnover_quality_v1`。
5. 对新 candidate 强制跑 `qfq_asof + 成本后 + walk-forward + strategy-admission`，通过前不得进入实盘模拟。

---

## 原文件：`refdocs/context/session_dialogue_after_1000_non_code_2026-06-04.md`

# 2026-06-04 10:00 之后非代码工作会话原文归档

导航：[`refdocs 索引`](../README.md) · [`Session 上下文`](./SESSION_CONTEXT_2026-06-04.md)

归档范围：2026-06-04 10:00 之后，除代码实现、工具执行、补丁、运行日志之外的自然语言问答内容。

---

## 用户

用户级规则：用中文作答

## 助手

好的，之后我会用中文作答。

---

## 用户

翻译Implemented W2.15 / T2.5 factor-effectiveness MVP.

## 助手

已实现 W2.15 / T2.5 的 `factor-effectiveness` MVP。

---

## 用户

翻译上面整段

## 助手

已实现 W2.15 / T2.5 的 `factor-effectiveness` MVP。

变更内容：
- 新增 [phase0/factor_effectiveness.py](/home/zj/workspace/stok-mapping/phase0/factor_effectiveness.py)
- 在 [phase0/cli.py](/home/zj/workspace/stok-mapping/phase0/cli.py) 中新增 CLI 命令：
  `python -m phase0.cli factor-effectiveness --config config.yaml`
- 在 `reports/factor_effectiveness/` 下生成输出：
  - `factor_effectiveness.csv`
  - `factor_effectiveness.md`
  - `factor_group_returns.csv`
  - `factor_ic_by_year.csv`
  - `factor_correlation.csv`
- 更新了 T2.5/W2.15 计划清单：
  - [docs/tasks/strategy/EFFECTIVE_QUANT_STRATEGY_RESEARCH_TASKS.md](../../docs/tasks/strategy/EFFECTIVE_QUANT_STRATEGY_RESEARCH_TASKS.md)
  - [docs/tasks/WEEKLY_EXECUTION_CHECKLIST.md](../../docs/tasks/WEEKLY_EXECUTION_CHECKLIST.md)
  - [docs/DEVELOPMENT_PLAN.md](../../docs/DEVELOPMENT_PLAN.md)

验证：
- `./.venv/bin/python -m compileall phase0` 已通过。
- `./.venv/bin/python -m phase0.cli factor-effectiveness --config config.yaml` 已完成。
- 最终运行结果：15 个因子，4 个有效的 PIT / `qfq_asof` 验证折。

当前因子诊断结论：
- `use`：`low_pb`、`low_vol60`、`low_turnover_rate`、`low_vol20`、`ep`、`cash_flow_quality`
- `observe`：`reversal_mom3`
- `reject`：`reversal_mom5`、`low_amount_ratio20`、`profit_growth`、`roe`、`mom20`、`revenue_growth`、`mom60`、`low_debt_to_asset`
- `missing`：无

我还在最终确认前修复了一个验证折边界问题：未来 20 日收益和补算的 60 日特征现在都按 `fold + symbol` 分组计算，因此不同验证折之间不会互相串联。

---

## 用户

reject的原因，列出

## 助手

`reject` 的因子及原因如下：

| 因子 | 主要原因 | 关键指标 |
|---|---|---|
| `reversal_mom5` | Rank IC 为负，Top-Bottom 未来收益也为负，5 日反转证据不足 | mean_rank_ic = -0.0021，long_short = -0.0002 |
| `low_amount_ratio20` | 低成交额放大比例没有带来正向收益，IC 和分组收益均偏负 | mean_rank_ic = -0.0082，long_short = -0.0025 |
| `profit_growth` | 利润增长因子在当前 PIT/qfq_asof 验证折中方向为负 | mean_rank_ic = -0.0260，long_short = -0.0014 |
| `roe` | ROE 单因子没有体现正向选股效果，高 ROE 组反而弱 | mean_rank_ic = -0.0263，long_short = -0.0123 |
| `mom20` | 20 日动量在验证期表现为反向，追涨效果失败 | mean_rank_ic = -0.0357，long_short = -0.0081 |
| `revenue_growth` | 收入增长因子方向为负，年度稳定性不足 | mean_rank_ic = -0.0498，long_short = -0.0078 |
| `mom60` | 60 日动量明显负向，说明中期动量在当前池子里不适合作为主因子 | mean_rank_ic = -0.0540，long_short = -0.0116 |
| `low_debt_to_asset` | 低资产负债率没有带来正收益，高分组收益低于低分组 | mean_rank_ic = -0.0658，long_short = -0.0137 |

统一判断规则是：这些因子在验证折里没有同时满足“正 Rank IC”和“Top 组收益高于 Bottom 组”。多数是 IC 为负且多空分组收益为负，所以被标记为 `reject`。

---

## 用户

输出了此次因子诊断的中文报告了吗？

## 助手

还没有。当前输出的 `reports/factor_effectiveness/factor_effectiveness.md` 是英文报告，CSV 字段也是英文。

已有内容包括结论、因子汇总、分组收益、年度 IC、相关矩阵和 warning，但报告标题/章节/解释文本是英文。

可以下一步补一个中文报告，例如：

`reports/factor_effectiveness/factor_effectiveness.zh.md`

内容包含：
- 运行口径：`qfq_asof`、PIT 股票池、20 日未来收益
- 总结论：`use / observe / reject / missing`
- 每个因子被接受或拒绝的中文解释
- 分组收益解读
- 年度 IC 稳定性解读
- 数据覆盖和风险提示

---

## 用户

补输出中文报告

## 助手

已补输出中文报告：

[reports/factor_effectiveness/factor_effectiveness.zh.md](/home/zj/workspace/stok-mapping/reports/factor_effectiveness/factor_effectiveness.zh.md)

它基于现有诊断结果生成，没有重跑因子诊断，也没有改英文报告。内容包括运行口径、总论、因子汇总、分组收益、年度稳定性、相关性观察、下一步策略研发建议和风险提示。

---

## 用户

修改中文报告一个细节：加一段被测因子的含义解释。

## 助手

已修改中文报告，新增了“被测因子含义”一节：

[reports/factor_effectiveness/factor_effectiveness.zh.md](/home/zj/workspace/stok-mapping/reports/factor_effectiveness/factor_effectiveness.zh.md)

位置在“总结论”之后、“因子汇总”之前，逐项解释了 15 个被测因子的含义和方向。

---

## 用户

建议首版候选权重方向：

```text
defensive_quality_score =
  0.30 * low_vol60_rank
+ 0.25 * low_pb_rank
+ 0.20 * ep_rank
+ 0.15 * low_turnover_rate_rank
+ 0.10 * cash_flow_quality_rank
```

## 用户

建议首版候选权重方向：

```text
defensive_quality_score =
  0.30 * low_vol60_rank
+ 0.25 * low_pb_rank
+ 0.20 * ep_rank
+ 0.15 * low_turnover_rate_rank
+ 0.10 * cash_flow_quality_rank
```

这段建议，翻译成中文自然语言

## 助手

这段可以翻译成自然语言：

建议首版候选策略采用一个“防御型质量评分”。这个评分主要由 5 类因子组成：

低 60 日波动率占 30%，作为核心防御因子；低 PB 占 25%，用于捕捉低估值股票；盈利收益率 `EP` 占 20%，进一步补充估值维度；低换手率占 15%，用于偏向交易活跃度较低、筹码相对稳定的股票；现金流质量占 10%，作为质量因子的补充。

也就是说，首版策略不是继续以动量为主，而是更偏向“低波动 + 低估值 + 低换手 + 现金流质量”的组合方向。

---

## 用户

检验当前数据源有没有完整以上因子组合的稳定数据来源

---

## 用户

检验Tushare数据源和Akshare数据源是否有当前因子组合数据。

## 助手

结论：**Tushare 数据源可以完整支撑这组首版候选因子；Akshare/东方财富链路可以支撑其中大部分，但不如 Tushare 完整，尤其是历史 daily_basic 估值字段和复权因子治理上。**

当前组合：

```text
0.30 * low_vol60_rank
0.25 * low_pb_rank
0.20 * ep_rank
0.15 * low_turnover_rate_rank
0.10 * cash_flow_quality_rank
```

对应数据源检查如下。

| 因子 | 所需数据 | Tushare | Akshare / 东方财富 | 当前项目实现情况 |
| --- | --- | --- | --- | --- |
| `low_vol60` | OHLCV + 复权价格 | 支持。`daily` + `adj_factor` 可构造 qfq_asof | Akshare `stock_zh_a_hist` 可取日线和换手率，但 qfq_asof 依赖本地复权因子治理 | 已有 |
| `low_pb` | PB | 支持。`daily_basic.pb` | 快照可取 PB；历史稳定性弱于 Tushare | 已有，来自 `market_daily_basic.pb_ratio` |
| `ep` | PE_TTM，计算 `1 / pe_ttm` | 支持。`daily_basic.pe_ttm` | 快照可取动态 PE；历史 daily_basic 不如 Tushare 稳 | 已有，来自 `market_daily_basic.pe_ratio` |
| `low_turnover_rate` | 换手率 | 支持。`daily_basic.turnover_rate`，也可合并进日线 | Akshare 日线和快照都有换手率 | 已有，覆盖率最好 |
| `cash_flow_quality` | 经营现金流 / 净利润，且需要公告日 | Tushare 可通过财务/现金流接口构造，但当前项目未用 Tushare 实现这块 | 当前项目通过东方财富财报接口构造，不是 Akshare 标准日线接口 | 已有，来自 `market_financial_factors.operating_cash_flow_to_net_profit` |

本地数据覆盖率抽查结果：

| 表/字段 | 当前覆盖情况 |
| --- | --- |
| `market_daily_bars` qfq | 2016-05-03 到 2026-06-03，收盘价覆盖率 100%，换手率覆盖率 100% |
| `market_daily_bars` bfq | 2016-05-03 到 2026-05-28，收盘价覆盖率 100%，换手率覆盖率 100% |
| `market_adj_factors` | 2016-05-03 到 2026-05-28，复权因子覆盖率 100% |
| `market_daily_basic.pb_ratio` | 2021-05-06 到 2025-07-31，总体覆盖率约 99.29% |
| `market_daily_basic.pe_ratio` | 2021-05-06 到 2025-07-31，总体覆盖率约 78.83% |
| `market_daily_basic.turnover_rate` | 2021-05-06 到 2025-07-31，覆盖率 100% |
| `market_financial_factors.cash_flow_quality` | 2018-06-30 到 2026-03-31，覆盖率约 93.38% |

需要注意两个风险点：

1. `low_pb` 和 `ep` 的历史 daily_basic 目前主要覆盖 2021-2025，2016-2020 和 2026 的 join 覆盖为 0。这不影响刚才 4 个验证折的诊断结果，但如果要做更长历史的估值因子回测，需要继续补 Tushare `daily_basic` 历史。
2. `cash_flow_quality` 当前是通过东方财富财报接口构造，且有公告日字段，适合 point-in-time 使用；但如果要把上游统一到 Tushare，需要新增 Tushare 财务因子下载/归一化实现。

所以建议是：

- 首选上游：**Tushare**，负责 `daily`、`daily_basic`、`adj_factor`、`dividend`。
- 财务质量因子当前可继续用：**东方财富财报接口链路**。
- Akshare 可作为日线/快照 fallback，但不建议作为这套首版策略的唯一历史因子数据源。

---

## 用户

将今天10:00之后发生的会话记录，除代码工作之外的对话内容原文完整归档

---

## 原文件：`refdocs/context/strategy_research_direction_qa_2026-06-04.md`

# 策略研发方向问答原文归档

归档时间：2026-06-04 02:08:11

导航：[`refdocs 索引`](../README.md) · [`Session 上下文`](./SESSION_CONTEXT_2026-06-04.md)

## 用户问题

查阅 '/home/zj/workspace/stok-mapping/docs/STRATEGY_POOL_REVIEW_2026-06-03.md'、'/home/zj/workspace/stok-mapping/refdocs/papers/cn/A股有效量化策略报告.md'，两篇文档，设计下一步研发有效量化策略的方向。

## 回答原文

读完两篇后，结合刚跑出的 `qfq_asof` 全候选失败结果，下一步方向应该从“调已有动量候选”切换为：

**先验证因子，再构造低换手组合策略。**

当前旧报告里的 `legacy_momentum_low_turnover_v1` 结论已经被 `qfq_asof` 重估推翻，所以 [strategy_pool_review_and_iteration_recommendations_2026-06-03.md](../../docs/STRATEGY_POOL_REVIEW_2026-06-03.md) 中“可进入观察池和模拟账户”的判断需要降级；但它提出的研发方向仍然成立：不要继续堆 K 线、动量、量价过滤，而要转向 [A股有效量化策略报告.md](../papers/cn/A股有效量化策略报告.md) 里强调的 **低波 + 低换手 + 高质量**。

**建议研发主线**
1. **P0：因子有效性诊断先行**
   先做 `factor_effectiveness_report`，不要直接再写复杂策略。  
   必测因子：
   - 低波：`vol20 / vol60 / ivol`
   - 低换手：`turnover_rate`、`amount_ratio20`、换手稳定性
   - 质量：`roe`、现金流质量、利润增长、营收增长、低负债
   - 动量/反转：`mom60 / mom20`、`mom3/mom5` 反转
   - 估值：`pe / ep / pb`，若数据可得

   输出至少包括：覆盖率、缺失率、Rank IC、ICIR、分组收益、年度稳定性、因子相关矩阵、成本后收益、因子换手。

2. **P1：新增核心候选 `low_vol_low_turnover_quality_v1`**
   这是下一轮最重要候选。不要以动量为主 ranker，而以防御型因子为主。

   初始打分：
   ```text
   score =
     0.40 * low_vol_rank
   + 0.25 * low_turnover_rank
   + 0.25 * quality_rank
   + 0.10 * medium_momentum_rank
   ```

   约束：
   - 调仓周期：20 个交易日或月频
   - 年化换手：目标 `<= 3`
   - top_n：优先 `10 / 20`，不要太集中
   - 交易执行仍用 `bfq_raw`
   - 研究价格默认 `qfq_asof`
   - 股票池必须 point-in-time
   - 通过前不得进入实盘模拟

3. **P1：重做质量策略 `quality_low_turnover_monthly_v1`**
   当前 `quality_growth_price_v1` 失败，不代表质量因子无效，而是当前实现太日频、太交易化。  
   新版本应：
   - 月频调仓
   - 取消强短线趋势过滤
   - 质量因子横截面排序
   - 叠加低波、低换手
   - 用公告日 point-in-time 财务数据
   - 输出质量字段贡献拆解

4. **P1：把动量降级为 sleeve**
   `legacy_momentum_low_turnover_v1` 不再是主策略，但可以作为一个动量 sleeve 保留。  
   新组合可以是：
   ```text
   final_score =
     0.55 * defensive_quality_score
   + 0.25 * low_turnover_momentum_score
   + 0.20 * regime_or_risk_overlay
   ```

   重点是让动量只做确认，不再独立决定主排名。

5. **P2：公告事件 / PEAD**
   A 股报告里提到盈余公告后漂移。这个方向比继续调 K 线更有意义。  
   可以先做低频事件候选：
   - 盈利超预期
   - ROE/利润增速改善
   - 公告后 15-60 天漂移
   - 只在低波、低换手、非 ST、流动性合格股票中选

6. **P2：ML 只做二阶段 rerank**
   暂时不要直接上 SVM/XGBoost/LLM 做主策略。  
   前置条件是：因子诊断证明 5-10 个因子稳定有效。  
   模型只做：
   - 月频 rerank
   - 特征重要性输出
   - 分年度 OOS
   - 成本后比较
   - 与线性打分 baseline 对照

**硬性准入标准**
新策略必须同时满足：

- `qfq_asof` 口径为正收益
- Sharpe `> 0.5`
- 最大回撤 `> -0.25`
- 年化换手 `<= 3`
- 正收益折比例至少 `>= 0.75`
- OOS 不靠单折偶然撑起
- 过拟合诊断不是 high/critical
- 执行价、涨跌停、停牌判断全部用 `bfq_raw`

**下一步最合理顺序**
1. 做因子有效性诊断报告。
2. 实现 `low_vol_low_turnover_quality_v1`。
3. 实现 `quality_low_turnover_monthly_v1`。
4. 接入过拟合诊断 gate。
5. 再考虑 sleeve 组合与 ML rerank。

一句话：**不要继续从失败的价格行为策略里调参救火；下一轮应围绕 A 股更稳定的低波、低换手、质量因子，先证明因子有效，再构建低频、低换手、可执行的组合策略。**

---
