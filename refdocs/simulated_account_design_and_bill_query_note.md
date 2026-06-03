# 模拟账户设计与账单查询备忘

记录日期：2026-06-03

## 一、账户设计定位

当前项目中的模拟账户不是实盘交易账户，也不是自动下单模块。它的定位是：

- 把 `watchlist` 中的策略观察/计划信号，转成可复盘的模拟账户资产、成交和持仓记录。
- 为后续用户模拟交易、用户确认买卖、多个账户配置和风险约束管理预留结构。
- 用 SQLite 维护连续账户状态，避免只靠单次 HTML/CSV 页面展示。

当前默认账户为：

```yaml
account_id: default
name: 默认模拟账户
initial_cash: 1000000
strategy_scope: current_selected
execution_price_mode: next_open
lot_size: 100
max_participation_rate: 0.05
```

账户分类原则另见：

```text
refdocs/simulated_account_classification_note.md
```

## 二、watchlist 与正式账单的边界

已确认的设计口径：

- `watchlist` 页面是计划层 / 观察层，用于展示当前策略观察池、交易动作计划、风险提示和模拟账户最近状态。
- 正式模拟账单是确认执行层，只记录本地日线库已有对应执行日 OHLCV 的交易日。
- `watchlist` 当天页面不等于当天已经成交；如果尚未取得对应交易日 OHLCV，则不应把该日交易写入正式账单。
- 页面中的账户快照默认只展示最近一个已确认模拟账单日，不展示多日流水；连续多日记录保存在 SQLite 中。

例如当前本地日线库最新为 `2026-06-02`，则 `2026-06-03` 生成的 watchlist 是计划层页面，正式模拟账单仍只确认到 `2026-06-02`。

## 三、执行价格与时间口径

已确认的口径：

- `price_mode = next_open`：使用执行日开盘价，模拟成交时间记为执行日 `09:30`。
- `price_mode = conservative`：使用执行日开盘价叠加保守缓冲，模拟成交时间记为执行日 `09:30`。
- `price_mode = close`：使用执行日收盘价，模拟成交时间记为执行日 `15:00`。
- 持仓估值使用执行日收盘价。
- 买入和卖出在当前批处理内使用同一个 `price_mode`；先卖后买只是现金处理顺序，不代表同一批中买卖一定使用不同价格时点。

当前设计不在账单中记录尚未取得价格数据、因而不能确认模拟的未来交易行为。

## 四、交易约束

当前模拟账户执行层已接入：

- A 股 `100` 股整数手约束。
- 买入现金约束。
- 卖出回款与现金联动。
- 佣金。
- 卖出印花税。
- 滑点。
- 停牌 / 缺价格 / 零成交量基础检查。
- 涨跌停基础检查。
- 最大成交参与率。

`lot_size = 100` 表示一手为 100 股。模拟买入数量必须向下取整到 100 股整数倍。例如：

```text
SZ.000725 buy price=5.36 shares=11156.72 lots=111.57 lot_size=100
```

该含义是：若按目标仓位计算，理论上应买入约 `11156.72` 股，也就是 `111.57` 手；但 A 股实盘不能买入非整数手，所以实际模拟应向下取整为 `111` 手，即 `11100` 股。

当前实现应以实际成交股数和实际成交后的仓位权重为准，不能直接把计划权重抄成已成交后的真实仓位。

## 五、SQLite 账本结构

当前模拟账户主库：

```text
data/simulated_trading/simulated_accounts.sqlite
```

当前表结构：

- `simulated_accounts`：模拟账户配置。
- `account_daily_assets`：每日账户资产快照，记录总资产、股票资产、现金资产、当日收益、目标暴露、成交额等。
- `account_trades`：每笔模拟成交明细，记录买卖方向、成交价、金额、股数、手数、权重变化、交易时间、信号日期、交易成本等。
- `account_positions`：每日持仓快照，记录证券、名称、收盘价、实际持股、市值、手数等。

当前另保留 CSV 兼容导出：

```text
data/simulated_trading/phase0_daily_brief_ledger.csv
data/simulated_trading/phase0_daily_account_ledger.csv
```

SQLite 是后续正式连续账户维护的主存储；CSV 主要用于兼容查看和导出。

## 六、当前已确认账单状态

截至本备忘记录时，当前库中只有一个已确认账单日：

```text
brief_date: 2026-06-02
account_id: default
initial_cash: 1,000,000.00
total_asset: 1,003,587.26
stock_asset: 158,524.00
cash_asset: 845,063.26
daily_pnl: 3,587.26
execution_price_mode: next_open
```

已确认成交包括：

```text
2026-06-02 09:30 买入 SH.603986 兆易创新 100 股
2026-06-02 09:30 买入 SH.688012 DR中微公 100 股
2026-06-02 09:30 买入 SZ.000725 京东方Ａ 11200 股
2026-06-02 09:30 买入 SZ.002281 光迅科技 100 股
```

## 七、后续自然语言查询约定

后续用户说：

- “查看账单”
- “查看模拟账单”
- “查看某某账户账单”
- “展开账户账单”

默认执行只读查询：

```text
data/simulated_trading/simulated_accounts.sqlite
```

并展示对应账户的：

- 表结构与行数。
- `simulated_accounts`。
- `account_daily_assets`。
- `account_trades`。
- `account_positions`。

如果用户没有指定账户，默认展示：

```text
default / 默认模拟账户
```

如果用户指定账户名，应按 `account_id` 或账户名称匹配后展示。

## 八、后续待增强项

- 将未成交 / 部分成交原因结构化写入交易表，而不只是跳过或在 HTML 中解释。
- 为多账户配置增加清晰的配置层，支持不同资金规模、执行约束和风险偏好。
- 将 watchlist 页面中的计划层仓位与 SQLite 已确认账户持仓进一步解耦，避免计划权重与实际成交权重混淆。
- 增加账户查询 CLI，例如 `phase0.cli account show` 或 `phase0.cli brief account-bill --summary`。
- 增加按日期区间查看账户资产曲线、成交流水和持仓变化的 HTML 报告。
