# 手动预下载历史数据目录

此目录存放本项目的离线 A 股数据缓存，用于在线抓取失败时的回测和股票池 fallback。数据库文件较大，不进入 Git；仓库只保留本说明文件和 `.gitkeep`。

默认数据库：

```text
data/manual_history/a_share_history.sqlite
```

当前数据库状态：

- 文件大小约 `3.8G`。
- 股票日线：qfq `10,462,485` 行 / `5,760` 只，bfq `10,462,385` 行 / `5,748` 只。
- 股票元数据：`5,524` 行。
- 交易日历：`13,162` 行。
- 退市股票：`324` 行。
- 指数元数据：`997` 行。
- 指数日线：`1,876,918` 行 / `995` 个指数。
- 日期区间：股票和指数日线均裁剪为 `2016-05-03` 至 `2026-05-28`。

## 数据来源

当前导入脚本读取 `~/workspace/tmp/A股数据_zip/` 下的预下载文件，并裁剪最近 10 年数据。10 年裁剪的目的是覆盖当前 5 年 Phase 0 回测、技术指标预热、后续扩展回测，同时避免把 30 年全量日线直接放进项目库。

使用的数据文件：

- `daily_qfq.zip`：A 股日线前复权数据，作为回测收益和技术指标的主数据。
- `daily.zip`：A 股日线不复权数据，作为辅助校验和未来停复牌/异常价格检查数据。
- `股票列表.csv`：股票基础信息，包含名称、行业、地域、上市状态、上市日期等。
- `交易日历.csv`：交易所交易日历，用于判断最近应有交易日和防止使用过期本地快照。
- `退市股票列表.csv`：退市股票清单，用于标记/排除退市标的，降低幸存者偏差。
- `指数/指数列表.csv`、`指数/中证指数列表.csv`：指数元数据。
- `指数/指数_日_kline.zip`、`指数/中证指数_日_kline.zip`：指数日线行情，用于本地基准、市场状态和未来本土风险因子。

暂不导入周线/月线指数，原因是当前 Phase 0 回测以日线为主，先保持单一频率，避免同一含义的多频数据增加时点对齐复杂度。

## 表结构与用途

- `market_daily_bars`：股票日线行情。字段包括 `market`, `symbol`, `date`, `adjust_type`, `open`, `high`, `low`, `close`, `volume`, `amount`, `adjusted_close`, `turnover_rate` 等。`adjust_type=qfq` 是主回测数据，`adjust_type=bfq` 用于辅助校验。
- `market_stocks`：股票元数据。字段包括 `symbol`, `name`, `exchange`, `board`, `industry`, `area`, `list_status`, `list_date`, `delist_date` 等。当前股票列表不含实时市值/估值，`market_cap`, `pe_ratio`, `pb_ratio` 可后续补充。
- `trading_calendar`：交易日历。字段包括 `exchange`, `date`, `is_open`, `previous_trade_date`。本地 fallback 会用它判断“期望最近交易日”。
- `delisted_stocks`：退市股票清单。用于审查样本是否有幸存者偏差，并防止退市标的进入当前选股池。
- `market_indices`：指数元数据。字段包括 `symbol`, `name`, `exchange`, `publisher`, `category`, `base_date`, `base_point`, `list_date`。
- `market_index_bars`：指数日线行情。字段包括 `symbol`, `date`, `frequency`, `open`, `high`, `low`, `close`, `volume`, `amount`, `advances`, `declines`。

## 重建命令

完整重建全部离线历史库：

```bash
/home/zj/workspace/stok-quant/.venv/bin/python -m phase0.cli import-history --config config.yaml
```

只重建指数元数据和指数日线表：

```bash
/home/zj/workspace/stok-quant/.venv/bin/python -m phase0.cli import-index-history --config config.yaml
```

`import-index-history` 用于修复或刷新 `market_indices` / `market_index_bars`，不会改动股票日线、股票列表、交易日历和退市表。

## 符号规范

股票符号使用：

```text
SH.600519
SZ.000001
BJ.430047
```

指数符号使用：

```text
SH.000001
SZ.399001
CSI.000300
```

`market` 统一使用 `CN`。

指数导入已处理 CSV 代码前导零丢失问题。例如 `指数_日_kline.zip` 中 `000001_日.csv` 的 `代码` 字段可能被 pandas 读取为整数 `1`，导入脚本会使用文件名 fallback，正确归一化为 `SH.000001`。当前已验证 `SH.000001` 可读，区间 `2016-05-03` 至 `2026-05-28`。

## 时间线保护

本地股票池 fallback 不会把旧数据静默当作当天数据使用。系统会比较：

- `latest_trade_date`：本地日线库中最新交易日。
- `expected_trade_date`：交易日历中不晚于今天的最近开市日。
- `staleness_days`：两者相差的交易日数；周末和节假日不计入滞后。

默认 `max_snapshot_staleness_days=1`，允许离线包只更新到上一交易日，以支持盘前/盘中分析；超过 1 个交易日时，当前股票池 fallback 会返回空并写出告警，避免把旧快照用于当日交易研判。该限制不等于禁用本地库，历史回测、指定历史区间分析和历史日线 fallback 仍可继续读取。

## 开发期增量更新

开发期间使用以下命令维护本地库新鲜度：

```bash
/home/zj/workspace/stok-quant/.venv/bin/python -m phase0.cli update-history --config config.yaml
```

增量更新先按交易日历判断目标交易日，再检查 `market_daily_bars` 的最新日期和覆盖率。默认阈值来自 `config.yaml`：

- `manual_history_update.max_staleness_days=1`：当前研判允许最多滞后 1 天。
- `manual_history_update.min_latest_coverage=0.80`：最新交易日覆盖率低于 80% 时拒绝写入，避免半截快照污染库。
- `manual_history_update.refresh_metadata=true`：刷新 `market_stocks` 的 `market_cap`, `pe_ratio`, `pb_ratio`, `turnover_rate`。
- `manual_history_update.min_metadata_coverage=0.80`：横截面字段最低覆盖率低于 80% 时继续提示元数据覆盖不足。
- `manual_history_update.min_run_time=16:00`：交易日 16:00 前不把 AkShare 实时快照写成日线收盘数据。

每日开发期 cron 可通过以下脚本安装：

```bash
bash scripts/install_dev_cron.sh
```

默认任务为交易日 `16:30` 执行 `scripts/update_manual_history_daily.sh`，日志写入 `logs/manual_history_update.log`。当前增量源使用 AkShare 全市场实时快照补当日 qfq 日线；前复权历史在除权除息后可能整体回调，因此后续仍应周期性用预下载历史包或更稳定的数据源做完整重建校准。

横截面元数据刷新与日线写入分离：`16:00` 前仍禁止写入当日日线收盘，但允许刷新 `market_stocks` 的市值、估值和换手率字段。这样不会污染日线时间线，同时能让股票池筛选与报告尽早获得 `market_cap / pe / pb / turnover` 字段。当前优先使用 AkShare 东方财富全市场快照；若东方财富远端断开连接，则尝试新浪原始快照备用源，并保留其 `mktcap/per/pb/turnoverratio` 字段用于回填。
