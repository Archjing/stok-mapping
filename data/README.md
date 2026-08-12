# 本地数据资产

`data/` 存放项目运行所需的本地数据库、受控原始归档和股票池产物。除本说明与必要的目录占位文件外，这些都是 local-only 资产，不进入 Git，也不随静态站点发布。

## 数据库一览

| 文件 | 内容 | 主要读取者 | 关键边界 |
| --- | --- | --- | --- |
| `a_share_history.sqlite` | A 股日线、复权因子、财务因子、股票/指数元数据、交易日历 | 股票池、walk-forward、A 股数据审计 | 研究使用 `qfq_asof`；执行价格不使用复权后价格 |
| `etf_history.sqlite` | ETF catalog、日线、复权因子、5 分钟线、开盘快照与回填任务 | ETF 回测、单 ETF 模拟账户 | 仅允许配置声明的 universe/sector；不是全市场自动下载器 |
| `us_market_history.sqlite` | US 日线和 source audit | 跨市场信号、观察池、比较图 | 策略只读已落库数据；当前 yfinance 限流须显式审计 |
| `hk_market_history.sqlite` | 港股日线和 source audit | 港/A 股映射研究 | 独立交易日历仍待增强 |
| `cross_market_reference_history.sqlite` | FRED 等参考序列 | 宏观与交叉市场背景 | 参考序列不替代 US 主库 |
| `ai_corpus/ai_corpus.sqlite` | 新闻元数据、正文/归档（按 provider） | 盘前观察、研究解释 | 新闻不是自动交易输入 |
| `simulated_trading/simulated_accounts.sqlite` | 模拟账户、资产、成交、订单事件、运行状态 | 模拟执行和静态账户页 | 账本与页面必须可追溯，不进入 Git |
| `custom_indices.sqlite` | `CN_PANIC_HO30` 等研究原型 | 研究脚本 | 尚未纳入正式配置、CLI、调度或治理 |

旧路径 `data/manual_history/a_share_history.sqlite` 已废止；A 股主库在 `data/a_share_history.sqlite`。

## A 股主库

`a_share_history.sqlite` 是 A 股研究底座，保存：

- `market_daily_bars`：原始日线和研究价格读取所需基础数据；
- `market_adj_factors`：逐实际 bar 日期的复权因子；
- `market_daily_basic`、`market_financial_factors`：估值/财务特征与公告日；
- `market_stocks`、`market_indices`、`market_index_bars`：证券与指数元数据；
- `trading_calendar`、`market_data_source_runs`：交易日与来源审计。

价格口径：原始价格用于成交、涨跌停和执行模拟；`qfq_asof` 根据决策日动态构造，仅在 `as_of_date` 前可见的因子下用于历史研究。缺同日因子、未来公告财务数据或过期快照都不得被静默补齐。

常用维护命令：

```bash
./runit import-history --config config.yaml       # 初始化/重建基线
./runit update-history --config config.yaml       # 日常增量
./runit update-financials --config config.yaml    # 最近财务季度
./runit db-health --config config.yaml --scope cn --fail-on error
```

## ETF 历史库

ETF 数据与 A 股个股主库隔离，以避免基金复权、分钟线和个股日线混写。标准流程：

```bash
./runit sync-etf-catalog --config config.yaml
./runit resolve-etf-universe --config config.yaml \
  --universe semiconductor_timing_etfs --start-date 2021-01-01 --end-date 2026-08-12
./runit backfill-etf-history --config config.yaml \
  --universe single_etf --sector semiconductor \
  --start-date 2019-06-12 --end-date 2026-08-12 --dry-run
./runit backfill-etf-history --config config.yaml --resume-run-id <run-id>
./runit audit-etf-history --config config.yaml --run-id <run-id>
```

规则：

- `sync-etf-catalog` 可更新基础目录；真正历史回填只能针对 `config.yaml` 已声明的 universe/sector。
- `single_etf` 是人工显式声明的单标的入口，绝不按名称、通配符或 catalog fallback 扩展为全市场。
- 新长任务先 `--dry-run`，再按不可变 manifest 执行和恢复；任务成功不代表研究可用，必须再通过 audit。
- `raw` 日线服务交易语义；`qfq_asof` 服务研究读取。分钟线和开盘快照用于单 ETF 账户的入场、风控和盘后核验。

## US / HK 与新闻数据

`us_market_history.sqlite` 的标的由配置分为六组：

| 组 | 标的 | 用途 |
| --- | --- | --- |
| `core_signal` | `^SOX`、`^VIX` | 当前半导体 ETF 映射策略的唯一自动输入 |
| `semiconductor_breadth` | AMD、TSM、ASML、AMAT、LRCX、INTC、SMH | 行业广度研究 |
| `mega_tech_beta` | AAPL、MSFT、GOOGL、AMZN、META | 科技 beta 区分 |
| `rates` | `^TNX` | 利率背景 |
| `china_tech_sentiment` | BABA、JD、KWEB | 中国科技情绪 |
| `reference_and_fx` | `^NDX`、NVDA、`CNY=X` | 参考背景 |

除 `core_signal` 外，当前各组均不改变自动仓位或订单。US/HK 更新必须记录标的级结果、覆盖率、共同完成交易日和 OHLC 质量；空响应、权限失败或限流不能被报告为成功更新。

`ai_corpus.sqlite` 中的 `us_market_news` 保存 RSS 新闻元数据，供半导体 ETF 账户盘前页展示来源、发布时间、标题和 URL。新闻用于人工解释，不进入自动信号。

## 数据操作边界

- 不提交数据库、原始数据、日志、报告、账户账本或 token 到 Git。
- 不以 `ffill`、`bfill` 或未来数据填补关键价格、复权、分钟 bar 或公告日缺口。
- 数据源失败时保存失败状态和上下文；当前行情/观察池在数据不新鲜时应明确降级或拒绝输出。
- 删除或重建某类数据只影响对应独立数据库和报告目录，不能顺带删除其他市场库。

详细的数据流、调度和策略边界见 [架构说明](../docs/PROJECT_ARCHITECTURE_OVERVIEW.md)。
