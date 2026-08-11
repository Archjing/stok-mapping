# A 股研究主库说明

本目录当前承载项目的 **A 股研究主库**，而不是临时缓存目录。

默认数据库：

```text
data/a_share_history.sqlite
```

这个库是 `stok-mapping` 当前 A 股研究、回测、股票池、数据审计和日报前置检查的本地底座。它可以在在线主源异常时承担 fallback 角色，但 fallback 已经不是它的主定义。

数据库文件较大，不进入 Git；仓库只保留本说明文件和 `.gitkeep`。

## 当前角色

`a_share_history.sqlite` 当前承担以下职责：

- A 股历史研究主库：为 walk-forward、因子诊断、股票池和账户级仿真提供可复现的数据底座。
- A 股 point-in-time 研究底座：结合 `market_adj_factors`、`trading_calendar` 和 `announce_date` 支撑 `qfq_asof`、财务 PTI 和股票池 PTI 治理。
- 当前观察池与日报前置数据底座：当本地库足够新鲜且覆盖率达标时，当前股票池、brief/watchlist 和相关报告从本地库读取横截面与历史数据。
- A 股数据治理主库：增量更新、历史补齐、复权审计、财务 PTI、数据库健康检查都围绕此库进行。
- 在线源异常时的 fallback：当在线源不稳定时，本地库仍能支撑历史研究、历史区间分析和非当日场景；但“fallback”只是附属能力，不是主角色。

一句话理解：

> `data/a_share_history.sqlite` 现在是 A 股研究主库，本地优先、可复现、可审计；不是一个“抓数失败时才会用”的缓存文件。

## 当前库内对象

当前库中至少包含以下研究核心表：

- `market_daily_bars`
  - A 股日线主行情表。
  - 同时承载 `adjust_type=qfq` 与 `adjust_type=bfq`。
  - `qfq` 保留为兼容/对照口径；`bfq` 是真实交易价格底座。
- `market_adj_factors`
  - 复权因子表。
  - 用于构造 `qfq_asof`，避免全历史前复权把未来分红送转信息折回过去。
- `market_daily_basic`
  - 日度估值/市值/换手因子表。
  - 当前用于横截面筛选、因子诊断和数据健康检查。
- `market_financial_factors`
  - 季度财务因子表。
  - 当前与 `announce_date` 一起使用，服务财务 PTI、因子诊断和后续质量类候选。
- `market_stocks`
  - 股票元数据与横截面基础字段。
  - 包含名称、行业、上市状态、上市日期、退市日期以及部分横截面指标。
- `trading_calendar`
  - 交易日历。
  - 用于时效保护、最近应有交易日判断和增量维护目标日计算。
- `market_data_source_runs`
  - A 股增量更新 source audit 表。
  - 用于记录主源、覆盖率、抓取时间、写入结果和失败信息。
- `delisted_stocks`
  - 退市清单，服务样本治理和退市边界控制。
- `market_indices` / `market_index_bars`
  - 指数元数据与指数日线。
  - 服务基准、市场状态和相关研究输出。

## 价格口径

本库当前需要明确区分三类价格口径：

- `bfq_raw`
  - 真实交易价格口径。
  - 用于执行、涨跌停、停牌、账户级仿真和真实成交语义。
- `qfq_current`
  - 当前全历史前复权口径。
  - 仅保留为兼容、审计对照和旧报告比较使用。
  - 不应再被解释为严格 point-in-time 历史特征口径。
- `qfq_asof`
  - 历史研究主特征口径。
  - 通过 `bfq_raw + market_adj_factors + as_of_date` 动态构造。
  - 当前用于更严格的 walk-forward、因子诊断和复权未来函数治理。

当前原则：

- 研究价格、执行价格、估值判断价格必须分离。
- 历史策略特征优先使用 `qfq_asof`。
- 交易执行仍使用 `bfq_raw`，不使用复权价成交。

## 财务因子口径

`market_financial_factors` 当前不是“最新财报缓存”，而是财务因子研究表。

使用时必须遵守：

- `report_date` 表示报告期。
- `announce_date` 表示市场可见时间。
- 历史回测或因子诊断中，某个 `as_of_date` 只能看到 `announce_date <= as_of_date` 的财务记录。
- 财务因子长历史补齐由 `backfill-tushare-financials` 负责，低频最近季度更新由 `update-financials` 负责，二者不能混写成同一个维护动作。

## 维护命令分工

### 重建 / 初始化

完整重建 A 股研究主库：

```bash
./.venv/bin/python -m phase0.cli import-history --config config.yaml
```

职责：

- 从预下载原始包重建股票、指数、交易日历、退市等基础表。
- 建立本地研究主库的初始结构和历史基线。

只重建指数相关表：

```bash
./.venv/bin/python -m phase0.cli import-index-history --config config.yaml
```

职责：

- 只刷新 `market_indices` / `market_index_bars`。
- 不改动股票日线、股票元数据、交易日历和退市表。

### 日常增量维护

更新 A 股日线、横截面元数据和相关审计记录：

```bash
./.venv/bin/python -m phase0.cli update-history --config config.yaml
```

职责：

- 维护当前 A 股日线新鲜度。
- 刷新 `market_stocks` 中的横截面字段。
- 写入 `market_data_source_runs` source audit。
- 受 `manual_history_update.*` 阈值和 `min_run_time` 保护。

### 历史缺口补齐

补齐历史 `daily_basic / adj_factor / dividend / financial` 缺口：

```bash
./.venv/bin/python -m phase0.cli backfill-tushare-history \
  --config config.yaml \
  --start-date 2016-01-01 \
  --end-date YYYY-MM-DD
```

职责：

- 按日期或按财务期补齐历史缺口。
- 生成历史补齐验收报告。
- 服务研究库完整性，而不是日常最新季度维护。

补齐历史 `market_daily_bars`（bfq + qfq 双复权）缺口，并顺带对齐同窗口 `daily_basic`：

```bash
./.venv/bin/python -m phase0.cli backfill-daily-bars \
  --config config.yaml \
  --start-date 2016-01-04 \
  --end-date 2016-04-29
```

补齐 `market_index_bars` 历史/尾部缺口（Tushare index_daily 主源；Tushare 未收录的指数会在输出中列出，不静默丢弃）：

```bash
./.venv/bin/python -m phase0.cli backfill-index-history \
  --config config.yaml \
  --start-date 2016-01-04 \
  --end-date YYYY-MM-DD
```

职责：

- `backfill-daily-bars`：按交易日抓取 Tushare daily，写入 bfq/qfq 两复权行；同一请求的 daily_basic 顺带 upsert。
- `backfill-index-history`：按指数全窗口抓取 index_daily（覆盖早期缺口和过期尾部），窗口内先删后插；`--limit-symbols` 可分批跑。

按 `period + symbol` 长任务补齐历史财务因子：

```bash
./.venv/bin/python -m phase0.cli backfill-tushare-financials \
  --config config.yaml \
  --start-period 2016-03-31 \
  --end-period 2018-03-31
```

职责：

- 补齐 `market_financial_factors` 的长历史缺口。
- 使用 `tushare_financial_backfill_tasks` 管理断点、分片、重试和进度。
- 不替代 `update-financials` 的低频最近季度更新。

### 最近季度财务更新

更新最近季度财务因子：

```bash
./.venv/bin/python -m phase0.cli update-financials --config config.yaml
```

职责：

- 低频刷新最近财务因子。
- 适合日常 / 每周维护。
- 不负责长历史空白期回填。

## 数据来源与维护方式

当前库的维护已不再是“只依赖手动预下载包”的单一路径，而是多来源协作：

- 预下载原始包
  - 负责初始导入和必要时的全量重建基线。
- Tushare
  - 当前 A 股主源。
  - 负责 `update-history` 的主链路增量、历史 `daily_basic/adj_factor` 补齐、财务长历史回填等。
- 东方财富季度接口
  - 当前 `update-financials` 最近季度更新来源。
- 本地主库自身
  - 通过 `trading_calendar`、覆盖率和 source audit 对时效与可用性做自我保护和审计。

因此，当前维护方式应理解为：

> 预下载包负责“建库基线”，Tushare 与低频财务更新负责“日常维护与历史补齐”，本地主库负责“研究可复现与数据治理”。

## 时间线保护与时效保护

当前库既服务历史研究，也服务当前观察池，但两者时效要求不同。

### 历史研究

- 历史回测、历史区间分析和因子诊断可以继续读取本地主库。
- 即使主库不够“当天新鲜”，也不影响历史区间研究语义。

### 当前股票池 / 当日研判

- 当前股票池、brief/watchlist、盘前观察等场景要求主库足够新鲜。
- 系统会比较：
  - `latest_trade_date`
  - `expected_trade_date`
  - `staleness_days`
  - `latest_coverage`
- 如果本地库明显过期或覆盖率不足，当前股票池 fallback 会返回空并告警，避免把旧快照误当成今日可用数据。

这意味着：

- 主库不会因为“过一天”就失去研究价值。
- 但它也不会在“明显不新鲜”的情况下静默支撑当日观察池。

## 审计与治理关系

本地主库当前已经进入项目的数据治理主线。

相关审计命令：

- `phase0.cli adjustment-audit`
  - 检查 `bfq_raw / qfq_current / qfq_asof` 可用性与复权未来函数风险。
- `phase0.cli financial-pti`
  - 检查财务公告日 point-in-time 有效性。
- `phase0.cli universe-pti`
  - 检查股票池 listing / industry 的 point-in-time 边界。
- `phase0.cli db-health`
  - 检查表结构、覆盖率、时效、OHLC 异常、财务覆盖率和 source audit 状态。

`market_data_source_runs` 当前是 A 股主库的 source audit 记录，不是运行产物缓存。

## 当前状态说明

当前数据库文件体积约 `6.8G`。由于后台 Tushare 财务回填可能正在占写锁，README 中不再把易过期的精确行数和区间统计作为主叙述。若需要查看当前实时状态，应直接查询数据库或查看最近验收报告，例如：

- `reports/tushare_history_backfill_audit.md`
- `reports/tushare_financial_backfill_audit.md`
- `reports/database_health/database_health_report.md`

当前可以确定的事实包括：

- A 股日线已覆盖 `bfq` 与 `qfq`
- `market_adj_factors` 已落表
- `market_daily_basic` 已落表
- `market_financial_factors` 已落表
- `market_data_source_runs` 作为 A 股 source audit 已启用
- 主库已经被 `phase0 run`、`walk_forward`、`factor-effectiveness`、`db-health`、`brief` 等链路当作正式研究底座使用

## 数据目录边界

当前建议按下面理解目录边界：

- `data/a_share_history.sqlite`
  - A 股研究主库
- `data/us_market_history.sqlite`
  - US/FX/ETF/VIX 跨市场库
- `data/hk_market_history.sqlite`
  - HK 跨市场库
- `data/universe/`
  - 股票池与横截面研究产物
- `reports/`
  - 运行报告、验收报告、HTML 预览、CSV 导出和调度相关输出

不要把 `data/` 理解为报告目录，也不要把 `reports/` 理解为研究底库；`data/a_share_history.sqlite` 是 A 股研究底库。

## 一句话提醒

> `a_share_history.sqlite` 当前是 A 股研究主库：它既服务回测和股票池，也服务 PIT/复权/财务/健康检查治理；“在线失败时的 fallback”只是它现在众多职责中的一个附属角色。
