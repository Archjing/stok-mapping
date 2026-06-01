# Phase 0 策略变更日志

## 2026-05-31｜账户级仿真 v2

### 变更原因

原账单已能表达目标权重、整手买入、现金约束和卖出回款，但仍偏研究层模拟：成交价主要使用收盘价近似，且没有显式模拟涨跌停、停牌、流动性不足、部分成交和未成交原因。Week 1.7 的目标是让当前主策略账单更接近普通个人 A 股实盘执行约束，同时仍保持研究工具边界。

### 主要变更

- 新增 `phase0.execution` 配置块，支持 `price_mode`、`lot_size`、`max_participation_rate`、涨跌停检查、停牌检查和板块涨跌停比例。
- `phase0 bill` 导出的账单新增成交价口径、目标成交量、未成交量、交易状态、未成交原因和最大成交参与率。
- 账单撮合逻辑加入 `100` 股整手、现金、涨跌停、停牌、流动性参与率和部分成交约束。
- HTML 账单预览按全部成交、部分成交、未成交显示不同背景色。
- `phase0 premarket` 观察池新增成交价口径、最大成交参与率和执行风险提示。
- 新增 `refdocs/todo/ACCOUNT_RECONCILIATION_CSV_SCHEMA.md`，预留真实持仓 CSV 与券商成交回报 CSV 的对账字段。

### 当前参数

- `walk_forward.slippage = 0.00246`
- `walk_forward.commission = 0.00025`
- `walk_forward.stamp_duty_sell = 0.0005`
- `execution.price_mode = next_open`
- `execution.lot_size = 100`
- `execution.max_participation_rate = 0.05`
- `execution.enable_limit_check = true`
- `execution.enable_suspension_check = true`

### 验证结果

- `python -m py_compile scripts/export_low_turnover_bill.py scripts/export_premarket_watchlist.py`：通过。
- `phase0 bill --config config.yaml`：通过，生成账单 `6369` 行、日资产 `1008` 行。
- `phase0 premarket --config config.yaml`：通过，生成观察池 `20` 行，信号日 `2026-05-29`，盘前检查时间 `2026-06-01 07:30`。
- 已成交记录全部满足 `100` 股整手规则。
- 日资产现金余额无负数，最低现金 `309034.53`。
- 账单交易状态分布：未成交 `4739`，全部成交 `1605`，部分成交 `25`。
- 日资产表记录 `stale_valuation_positions`，本次账单中合计出现 `9` 次持仓沿用上一有效估值价。
- 合成边界校验确认：涨停买入标记为未成交，跌停卖出标记为未成交，低成交量场景按参与率限制部分成交，缺价持仓会沿用上一有效估值价。

### 边界说明

该变更不接券商 API，不自动下单，不做盘中高频撮合，不做逐笔盘口回放。真实账户对账当前只预留本地 CSV 输入格式，后续用于复盘模拟持仓和真实持仓、模拟成交和真实成交的差异。

## 2026-06-01｜FRED 最小接入与连通性验收

### 变更原因

项目进入 Week 2 数据源升级主线，优先把宏观 / 利率 / VIX 从 `yfinance` 逻辑中规范拆分，形成独立且可配置的 FRED 入口，为 overlay 与日报解释层提供更稳定的数据基础。

### 主要变更

- `phase0/data_sources.py` 新增 `fetch_fred_series(series_id, years=None, start=None, end=None, api_key_env="FRED_API_KEY")`。
- `check_connectivity()` 新增 `fred` 分支，按配置检查首批序列并输出 `source=fred`、`target=<series_id>`。
- `config.yaml` 新增 `data_sources.fred` 配置块：
  - `enabled`
  - `api_key_env`
  - `series.gdp/cpi/fedfunds/fedfunds_daily/vix`

### 验收结果

- 使用项目 `.env` 中 `FRED_API_KEY` 完成连通性检查（不在日志中明文输出 key）。
- 首批 5 个序列全部返回 `OK`：
  - `GDP`（latest: `2026-01-01`）
  - `CPIAUCSL`（latest: `2026-04-01`）
  - `FEDFUNDS`（latest: `2026-04-01`）
  - `DFF`（latest: `2026-05-28`）
  - `VIXCLS`（latest: `2026-05-28`）
- 已更新 `reports/phase0_data_source_report.md`，报告中包含 5 条 `fred` 连通性记录。

### 边界说明

- 本次仅完成 FRED 最小接入和连通性验收，不改 `phase0` 主回测逻辑。
- FRED 当前仅承接宏观 / 利率 / VIX，不替代美股个股 / ETF 行情，不接入主 ranker。

## 2026-06-02｜Tiingo 最小接入与 fallback 验收

### 变更原因

按 Week 2 顺序，在 FRED 稳定后推进 Tiingo 最小接入。目标是把关键美股个股 / ETF 的 EOD 抓取入口正规化，同时保留 `yfinance` 作为回退源，避免一次性硬切风险。

### 主要变更

- `phase0/data_sources.py` 新增 `fetch_tiingo_daily(symbol, years=None, start=None, end=None, token_env="TIINGO_API_TOKEN")`。
- `check_connectivity()` 新增 `tiingo` 分支：
  - 覆盖首批标的 `NVDA`、`AAPL`、`TSLA`、`KWEB`。
  - 输出 `source=tiingo`、`target=<ticker>`。
  - Tiingo 失败或空结果时自动回退 `yfinance`，并在 `error` 字段标记 fallback 命中情况。
- `config.yaml` 新增 `data_sources.tiingo` 配置块：
  - `enabled`
  - `token_env`
  - `us_equities`
  - `thematic_etfs`

### 验收结果

- 本次完成 Tiingo 最小接入代码、配置和连通性检查路径。
- 字段口径对齐 `fetch_yf_daily()`：`date/open/high/low/close/adjusted_close/volume`。
- fallback 行为已在 connectivity 逻辑中落地：Tiingo 不可用时可降级到 `yfinance` 并记录状态。

### 边界说明

- 本次不替换 `phase0` 主回测或 `us_market_history` 的当前 provider。
- 不处理 FRED、CNH/FX 代理和全部美股指数一次性替换。
