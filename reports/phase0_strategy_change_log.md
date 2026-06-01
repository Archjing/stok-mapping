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

## 2026-06-02｜Tiingo 港股可用性与 News API 探测

### 变更原因

为确认 Tiingo 是否可扩展承担港股历史库与新闻流能力，需要做一次脱离文档猜测的实测验证。

### 验证结果

- 直接调用 Tiingo 日线 API 探测以下港股 ticker 格式：
  - `HK.00700`
  - `HK.09988`
  - `00700`
  - `09988`
  - `700`
  - `9988`
  - `0700.HK`
  - `9988.HK`
- 上述格式在 2026-06-02 的 API 实测中均返回 `404 Ticker not found`。
- 对照组 `TCEHY`、`BABA` 返回 `200` 且可取得连续日线，说明 Tiingo 可作为美股 / ADR 数据源，但不能满足项目当前 `HK.*` 港股历史库需求。
- 进一步探测 `/tiingo/news` 时，项目当前 token 对以下组合全部返回 `403 You do not have permission to access the News API`：
  - ticker 列表
  - 主题标签
  - 时间窗口
  - 三者组合过滤

### 代码与脚本补充

- `phase0/data_sources.py` 新增 `fetch_tiingo_news()` 最小实现，参数支持：
  - `tickers`
  - `tags`
  - `start`
  - `end`
  - `limit`
- 新增 `scripts/tiingo_news_probe.py`，用于独立验证：
  - ticker 列表过滤
  - 主题标签过滤
  - 时间窗口过滤
  - 三者组合过滤

### 结论

- Tiingo 当前不适合作为 `hk_market_history.sqlite` 的正式数据源。
- Tiingo 当前可继续保留为美股 / ETF / ADR 数据源候选。
- Tiingo News API 在当前 token 权限下不可用，新闻链路不能接入主流程。

## 2026-06-02｜FRED 缓存策略补全

### 变更原因

Week 2 任务清单中 `W2.4.2` 仍缺“明确 FRED 数据缓存策略”。为避免重复请求 FRED API、降低外部波动对研究流程的影响，需要补齐最小可用缓存方案。

### 主要变更

- `phase0/data_sources.py` 的 `fetch_fred_series()` 新增可配置缓存参数：
  - `cache_enabled`
  - `cache_dir`
  - `cache_ttl_hours`
- 缓存命中策略：
  - 按 `series_id + start + end` 生成独立 CSV 缓存键
  - 缓存文件位于 `data/cache/fred/`
  - 默认 TTL 为 `24` 小时，超时自动回源
- `config.yaml` 新增 `data_sources.fred.cache` 配置块：
  - `enabled: true`
  - `dir: "data/cache/fred"`
  - `ttl_hours: 24`
- `check_connectivity()` 已接入上述配置，FRED 连通性检查走统一缓存策略。
- 缓存位置已按数据层边界归入 `data/cache/fred`。

### 边界说明

- 缓存仅用于 FRED 宏观 / 利率 / VIX 查询，不改变主回测逻辑和选股排序逻辑。
- 缓存读写异常会自动降级为在线请求，不中断流程。

## 2026-06-02｜港股观察池批量落库与验收报告

### 变更原因

为推进港股映射策略前置数据验证，需要把港股观察池从最小样本扩到可研究规模，并完成一次可复盘的批量落库与验收报告输出。

### 主要变更

- `config.yaml` 中 `hk_market_history.symbols` 从 2 只扩展为 30 只初始港股观察池。
- 保持 `hk_market_history.provider = yfinance`，执行批量日线更新。
- 新增 `scripts/export_hk_market_history_report.py`，从 `hk_daily_bars` 和 `hk_data_source_runs` 生成验收报告。
- 新增报告 `reports/hk_market_history_batch_load_report.md`，包含：
  - 30 标的覆盖表
  - 最近审计记录
  - 前 10 行 / 最后 10 行样本
  - 中文名称字段 `name_zh`

### 验收结果

- 本次批量更新状态：`updated`
- 覆盖率：`1.0000 (30/30)`
- 最新交易日：`2026-06-01`
- 批量抓取行数：`37044`
- 新增行数：`34568`
- 更新行数：`2476`
- 缺失标的：`None`
- 过期标的：`None`
- `hk` 字段已统一写入 `HK`

### 边界说明

- 本次完成的是港股历史库数据层验证与报告化，不代表港股数据已接入策略主链路。
- `hk_market_history` 仍作为独立数据资产，后续需通过解释力与策略回测验证后再决定是否挂载。
