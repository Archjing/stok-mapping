# stok-mapping

A 股本土因子为主、跨市场风险/情绪 overlay 为辅的量化研究与盘前研判工具。

当前阶段重点是 Phase 0/1：验证数据源、构建离线 fallback 数据库、扩展股票池、做 walk-forward 回测，并为每天 `07:30` 的盘前研判日报做数据底座。

## 当前状态

- 已接入 `yfinance` / `akshare` 数据源连通性检查和数据质量审计。
- 已实现 Phase 0 walk-forward 回测框架和候选策略对比输出。
- 已创建本地离线历史库 `data/manual_history/a_share_history.sqlite`，用于在线抓取失败时的回测与股票池 fallback。
- 已导入 A 股前复权/不复权日线、股票列表、交易日历、退市清单、指数元数据和指数日线。
- 已增加开发期每日增量更新任务，维护 `a_share_history.sqlite` 最近交易日滞后不超过 1 天。
- 已增加 AkShare 请求节流/重试机制，降低反爬和频繁请求导致的失败率。
- 已将运行时间线调整为：`16:00` A 股收盘数据采集，`06:00` 美股收盘数据采集，`07:30` 盘前研报邮件投递。

## 本地数据

默认数据库：

```text
data/manual_history/a_share_history.sqlite
```

数据库不进入 Git。目录说明见：

```text
data/manual_history/README.md
```

`a_share_history.sqlite` 的时效保护只限制“当前股票池 / 当日研判”场景：如果本地最新交易日超过配置允许滞后，系统不会用旧快照生成当前股票池，而是返回空并告警。该限制不等于禁用本地库，历史回测、指定历史区间分析和历史日线 fallback 仍可继续读取。

当前导入结果：

- `market_daily_bars`: qfq `10,462,485` 行 / `5,760` 只，bfq `10,462,385` 行 / `5,748` 只，日期 `2016-05-03` 至 `2026-05-28`。
- `market_stocks`: `5,524` 行。
- `trading_calendar`: `13,162` 行，覆盖 `1990-12-19` 至 `2026-12-31`。
- `delisted_stocks`: `324` 行。
- `market_indices`: `997` 行。
- `market_index_bars`: `1,876,918` 行 / `995` 个指数，日期 `2016-05-03` 至 `2026-05-28`。
- 关键指数 `SH.000001` 已验证可读，`2016-05-03` 至 `2026-05-28` 共 `2,445` 行。

## 常用命令

本项目复用 `stok-quant` 的 Python 虚拟环境，避免重复安装依赖。

运行 Phase 0：

```bash
/home/zj/workspace/stok-quant/.venv/bin/python -m phase0.cli run --config config.yaml
```

完整重建离线历史库：

```bash
/home/zj/workspace/stok-quant/.venv/bin/python -m phase0.cli import-history --config config.yaml
```

只重建指数元数据和指数日线表：

```bash
/home/zj/workspace/stok-quant/.venv/bin/python -m phase0.cli import-index-history --config config.yaml
```

构建本地因子股票池：

```bash
/home/zj/workspace/stok-quant/.venv/bin/python -m phase0.cli build-universe --config config.yaml
```

增量更新本地历史库：

```bash
/home/zj/workspace/stok-quant/.venv/bin/python -m phase0.cli update-history --config config.yaml
```

只检查本地历史库新鲜度：

```bash
/home/zj/workspace/stok-quant/.venv/bin/python -m phase0.cli update-history --config config.yaml --check-only
```

开发期每日定时更新任务：

```bash
bash scripts/install_dev_cron.sh
```

该 cron 任务默认在交易日 `16:30` 运行 `scripts/update_manual_history_daily.sh`，日志写入 `logs/manual_history_update.log`。更新命令会先检查库中最新交易日、覆盖率和交易日历；若已满足 `max_staleness_days=1` 与 `min_latest_coverage=0.80`，不会重复抓取。若在配置的 `min_run_time=16:00` 之前运行，不会把盘中实时快照写成日线收盘数据。

`update-history` 还会刷新 `market_stocks` 中的横截面字段：`market_cap`, `pe_ratio`, `pb_ratio`, `turnover_rate`。该元数据刷新与日线写入分离：即使早于 `16:00`，也允许用全市场快照回填横截面字段；只有日线收盘写入受 `min_run_time` 保护。当前主源为 AkShare 东方财富快照，断连时会尝试新浪原始快照备用源。

## 输出文件

- `reports/phase0_data_source_report.md`
- `reports/phase0_walk_forward_report.md`
- `reports/phase0_walk_forward_folds.csv`
- `reports/phase0_walk_forward_candidates.csv`
- `reports/phase0_effectiveness_report.md`
- `data/universe/local_factor_universe.csv`
- `data/universe/local_factor_universe_report.md`

## 重要约束

- 本工具仅供个人研究和自用决策辅助，不对外提供投资建议或商业服务。
- 所有策略参数变更必须记录理由、参考信息和验证结果。
- 本地 fallback 不会静默使用过期快照：若本地最新交易日超过配置允许滞后，当前股票池 fallback 返回空并告警。
- `yfinance` 和 `akshare` 定位为开发/研究数据源，后续生产化需保留 Tushare Pro / Wind / 聚宽 / Polygon 等适配层。
