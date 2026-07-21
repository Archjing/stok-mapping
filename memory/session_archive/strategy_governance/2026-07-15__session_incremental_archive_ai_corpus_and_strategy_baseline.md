# 2026-07-15 会话增量归档：AI 语料库生产化与策略研发基线复核

## 范围

本轮主要围绕两件事：

1. 推进 `T1.7｜AI 语料库`，把 CNInfo / AkShare 公告列表源从计划状态推进到可生产运行的 MVP。
2. 回到量化策略研发主线前，复核当前项目基线、工作区状态和下一步策略研发优先级。

本轮未直接运行新的策略 admission，也未开始新的策略实验。

## 关键决策

- `CNInfo / AkShare 公告列表` 先按“事件线索层”生产化，不抓取或再分发公告 PDF / 全文。
- CNInfo provider 当前只承诺列表级字段：证券代码、简称、公告标题、公告时间、公告链接、公告 ID 等。
- 事件类型首批支持：
  - `risk_events`
  - `abnormal_trading`
  - `trading_risk_warning`
  - `severe_abnormal_trading`
  - `earnings_forecast`
- `risk_events` 作为生产调度推荐口径：先抓巨潮“风险提示”分类列表，再按标题细分为异常波动、交易风险提示、严重异常波动等。
- 默认调度任务 `cninfo_risk_events` 的 `--min-rows` 设为 `0`，因为某天没有风险公告是正常结果；网络、解析或入库异常仍应失败。
- 策略研发主线仍不应直接扩候选数量。当前优先级是先建立最新严格 admission 基线，再从失败归因中决定下一步策略切口。

## 代码与文档变更

本轮新增或修改的核心文件：

- `phase0/ai_corpus/providers/cninfo.py`
  - 新增 CNInfo provider。
  - 支持 fixture / live 两种入口。
  - 通过 AkShare `stock_zh_a_disclosure_report_cninfo` 访问巨潮公告列表。
  - 写 raw archive。
  - 标准化输出为 `ai_corpus_documents`。
  - 使用公告 ID、URL、证券代码、标题、发布时间和内容 hash 形成去重键。
- `phase0/ai_corpus/registry.py`
  - `cninfo` 状态更新为 `implemented_mvp`。
  - 增加公告类别名和 parser version。
- `phase0/ai_corpus/api.py`
  - `fetch_ai_corpus(...)` 增加 CNInfo 路由。
  - 支持 `event_type` 和 `symbols` 参数。
- `phase0/cli_commands/ai_corpus.py`
  - `ai-corpus fetch` 增加 `--event-type`、`--symbols`。
  - CLI help 中加入 `cninfo` 示例。
- `phase0/maintenance_orchestrator.py`
  - 新增默认调度任务 `cninfo_risk_events`。
  - 默认时间：`20:20`。
  - 默认命令等同于 `ai-corpus fetch --provider cninfo --event-type risk_events --limit 200 --min-rows 0`。
- `tests/test_ai_corpus_cninfo.py`
  - 新增 CNInfo provider、解析、API 路由、CLI upsert 回归测试。
- `tests/fixtures/ai_corpus/cninfo/cninfo_announcements.csv`
  - 新增 CNInfo 离线 fixture。
- `tests/test_maintenance_orchestrator.py`
  - 增加 CNInfo 默认调度任务测试。
- `docs/tasks/data-sources/AI_CORPUS_IMPLEMENTATION_TASKS.md`
  - 更新 T1.7 当前状态、CNInfo MVP 边界和下一步。
- `docs/PHASE0_CLI_USER_GUIDE.md`
  - 增加 CNInfo CLI 使用说明。
- `docs/DEVELOPMENT_PLAN.md`
  - 更新 T1.7 状态：gov.cn、CCTV live、CNInfo 公告列表均已有 MVP 生产入口。

## 验证结果

已运行：

```bash
./.venv/bin/python -m pytest tests/test_ai_corpus_cninfo.py tests/test_ai_corpus_cctv_news.py tests/test_ai_corpus_gov_policy.py tests/test_maintenance_orchestrator.py
```

结果：

```text
52 passed
```

已运行 CNInfo CLI fixture smoke：

```bash
./runit ai-corpus fetch \
  --config config.yaml \
  --provider cninfo \
  --event-type risk_events \
  --fixture-dir tests/fixtures/ai_corpus/cninfo \
  --database-path /tmp/stok_cninfo_test.sqlite \
  --raw-archive-dir /tmp/stok_cninfo_raw \
  --output-csv /tmp/stok_cninfo.csv \
  --fields published_at,title,event_type,provider,source_id,symbols,url \
  --min-rows 2
```

结果：

```text
AI corpus fetch complete
Provider: cninfo
Rows: 2
Database: /tmp/stok_cninfo_test.sqlite
Upsert changes: 2
```

已运行：

```bash
./runit ai-corpus registry --config config.yaml
```

确认：

```text
gov_policy: status=implemented_mvp
cctv: status=implemented_mvp
cninfo: status=implemented_mvp
```

已运行相关文件的 `git diff --check`，无行尾空白错误。

## 当前项目基线复核

时间：2026-07-11 复核，2026-07-15 归档。

当前分支：

```text
main
```

最新远端基线提交：

```text
75179dc Stop tracking runtime assets
```

`main` 与 `origin/main` 未显示 ahead / behind，但工作区不干净。

当前未提交改动大致分为：

- AI 语料库相关代码、测试和文档。
- 多模拟账户、静态站点、账单、执行有效性、调度器等已有未提交改动。
- 本地运行资产：`data/simulated_trading/`、`data/universe/`、`data/reference/`、`reports/runs/` 等。
- 新增未跟踪文件：`phase0/ai_corpus/providers/cninfo.py`、CNInfo fixture/test、若干 ops 文档、`memory/` 等。

风险判断：

- 当前不适合直接开始新的策略实验。
- 应先把代码 / 测试 / 解释文档与本地运行资产分开，避免把研究产物、SQLite、报告和日志混入下一次策略研发提交。

## 策略研发现状

当前严格口径仍是：

- selected candidate：无。
- admission pass candidate：无。
- 全局准入集合：`baseline_admission_all_v1`。
- 默认候选数：13 个。
- 当前主线：以 `qfq_asof`、PIT 股票池、成本后、过拟合、行业集中、因子诊断和 `strategy-admission` 口径，把策略池治理成可复查、可解释、可迭代的研究资产。

当前 13 个默认候选：

```text
legacy_momentum
legacy_momentum_low_turnover_v1
ma_kline_baseline_v1
residual_momentum_reversal_v1
residual_momentum_reversal_v2
quality_growth_price_v1
low_vol_low_turnover_quality_v1
quality_low_turnover_monthly_v1
multifactor_volume_price_filter_v1
core_selection_quality_momentum_v1
theme_exposure_momentum_v1
sleeve_composite_v1
sleeve_composite_low_churn_v1
```

本地标准目录下未发现新的完整 13 候选 admission 基线报告：

- `reports/strategy_admission/` 基本为空。
- `reports/runs/` 近期主要是 db-health、latest watchlist、latest account-bill。

结论：

当前工程链路可用，但还缺一份最新、完整、覆盖 13 个候选的严格 admission 基线报告。

## 推荐下一步

1. 先做工作区收口：
   - 分类当前脏改动。
   - 只提交代码、测试、解释文档。
   - 不提交 reports、logs、SQLite、运行缓存和本地数据资产。
2. 对 AI 语料库和调度器改动再跑一次定向测试。
3. 建立干净策略研发 worktree。
4. 重跑 `baseline_admission_all_v1` 全 13 候选 admission。
5. 落盘治理报告，必须包含日期、背景、命令、数据口径、候选结论和治理动作。
6. 基于最新 admission 结果决定下一步策略研发切口，优先围绕低波、低换手、质量和 sleeve 降 churn 主线做失败归因，不直接堆新高换手价格行为策略。

