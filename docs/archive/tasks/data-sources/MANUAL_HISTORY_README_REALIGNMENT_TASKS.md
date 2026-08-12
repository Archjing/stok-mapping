# T1.6｜`data/manual_history/README.md` 定义重整任务单

适用场景：当前 `data/manual_history/README.md` 对 `a_share_history.sqlite` 的说明仍停留在“离线缓存 / fallback”阶段，已经明显落后于当前代码、数据流和运维方式。需要把文档重整为当前真实定义，避免误导后续研发、运维和策略解释。

父级计划：[`DEVELOPMENT_PLAN.md`](../../DEVELOPMENT_PLAN.md)  
任务索引：[`docs/tasks/README.md`](../README.md)

---

## T1.6.0 目标

- [x] 将 `a_share_history.sqlite` 的定义从“离线缓存 / fallback”改为“A 股研究主库”
- [x] 明确当前数据库在研究、回测、股票池、日报和数据审计中的职责
- [x] 明确当前维护命令与职责边界，避免“重建 / 增量 / 回填 / 财务更新”混写
- [x] 让文档与 `phase0/local_history.py`、`update-history`、`backfill-*`、`update-financials`、`db-health` 的现状一致

---

## T1.6.1 当前问题

- [x] 旧文档仍将 `a_share_history.sqlite` 描述为“离线 A 股数据缓存”
- [x] 旧文档低估了本地库在回测、股票池、审计和调度中的正式角色
- [x] 旧文档未完整覆盖 `market_adj_factors`、`market_daily_basic`、`market_financial_factors`、`market_data_source_runs`
- [x] 旧文档未清晰区分 `import-history`、`update-history`、`backfill-tushare-history`、`backfill-tushare-financials`、`update-financials`
- [x] 旧文档未准确表达 `bfq_raw / qfq_current / qfq_asof` 的边界和使用场景

---

## T1.6.2 需要重定义的核心内容

### T1.6.2.1 数据库角色

- [x] 明确 `data/manual_history/a_share_history.sqlite` 是 A 股研究主库
- [x] 明确它不是临时缓存，也不是仅在在线失败时才使用的 fallback
- [x] 明确它是回测、股票池、PIT 审计、日报前置检查和数据治理的基础资产

### T1.6.2.2 表职责边界

- [x] `market_daily_bars`：研究与回测主行情表，含 `bfq/qfq`
- [x] `market_adj_factors`：复权因子表，服务 `qfq_asof`
- [x] `market_daily_basic`：日度估值/市值/换手因子表
- [x] `market_financial_factors`：季度财务因子表
- [x] `market_stocks`：股票元数据与横截面基础字段
- [x] `trading_calendar`：交易日历
- [x] `market_data_source_runs`：A 股数据更新审计表

### T1.6.2.3 价格与 PIT 口径

- [x] `bfq_raw`：真实交易价格口径，用于执行、涨跌停、停牌判断
- [x] `qfq_current`：兼容 / 审计对照口径
- [x] `qfq_asof`：历史研究主特征口径
- [x] 明确 `qfq_asof` 依赖 `market_adj_factors`
- [x] 明确财务因子必须结合 `announce_date` 使用

### T1.6.2.4 维护命令分工

- [x] `import-history`：重建 / 初始化主库
- [x] `import-index-history`：只重建指数相关表
- [x] `update-history`：A 股日线与横截面增量维护
- [x] `backfill-tushare-history`：补齐历史 `daily_basic / adj_factor / dividend / financial` 缺口
- [x] `backfill-tushare-financials`：按 `period + symbol` 长任务补齐历史财务因子
- [x] `update-financials`：低频更新最近财务因子，不替代长历史回填

### T1.6.2.5 审计与时间线保护

- [x] 明确 source audit 的作用
- [x] 明确 `db-health`、`financial-pti`、`adjustment-audit`、`universe-pti` 与主库的关系
- [x] 明确当前股票池与历史回测在“时效保护”上的差异
- [x] 明确哪些场景允许使用旧数据，哪些场景必须阻断

---

## T1.6.3 文档改写要求

- [x] 不再使用“缓存目录”作为主叙述
- [x] 不再使用“只在在线抓取失败时 fallback”作为主定义
- [x] 明确区分“研究主库”“运行产物”“验收报告”“调度状态”
- [x] 文档中所有命令和表名与当前代码一致
- [x] 文档口径与 `docs/PROJECT_ARCHITECTURE_OVERVIEW.md`、`docs/DEVELOPMENT_PLAN.md` 一致

---

## T1.6.4 验收标准

- [x] `data/manual_history/README.md` 能准确回答“这个库现在是什么”
- [x] 能准确回答“哪些命令负责重建、增量、补历史、更新财务”
- [x] 能准确回答“哪些价格口径用于研究、哪些用于执行”
- [x] 能准确回答“哪些表是研究底座，哪些表是审计或辅助表”
- [x] 文档不再保留“离线缓存 / fallback”作为主定义

---

## T1.6.5 不做事项

- [ ] 不在本任务内修改数据库 schema
- [ ] 不在本任务内改动导入、更新或回填代码逻辑
- [ ] 不把 README 重写成数据字典全集，保持面向维护者和研究者的高信息密度说明
- [x] 不在本任务内迁移 `data/manual_history/` 目录名；当前仅纠正文档语义，不执行真实路径迁移

## T1.6.6 目录名语义评估结论

- [x] 当前 `manual_history` 目录名在语义上已经落后于“研究主库”真实角色
- [x] 真实迁移目录名是可行的，但不属于当前低风险小改动
- [x] 当前不建议立刻迁移，原因是代码默认路径、配置、脚本、日志、报告和后台长任务仍深度耦合该路径
- [x] 推荐把目录名迁移作为后续独立任务处理，避免与当前数据治理、回填和调度任务相互干扰
- [x] 当前阶段保留 `data/manual_history/` 作为历史路径名债，通过文档纠偏消除语义误导

推荐后续候选目录名：

- [x] `data/a_share_research/`（推荐）
- [x] `data/a_share_history/`
- [x] `data/cn_research_db/`

---

## T1.6.7 一句话提醒

> 这项任务的目的不是润色 README，而是把 `a_share_history.sqlite` 的真实系统角色重新定义清楚，避免后续开发继续按“缓存”思维误用一个已经演进为研究主库的数据库。
