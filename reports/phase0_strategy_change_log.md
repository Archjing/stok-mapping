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
