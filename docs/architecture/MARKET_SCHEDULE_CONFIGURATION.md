# 市场日历与会话时间配置化设计

> 状态：设计已定，待实施
> 日期：2026-08-14
> 关联：`PROJECT_ARCHITECTURE_OVERVIEW.md`（架构）、`DEVELOPMENT_PLAN.md`（主线）

## 1. 目标

把"各市场（cn/us/hk）的交易日历 + 会话时间表 + 调度触发时间"收敛到
`config.yaml` 单一事实源，并引入**时区归一化**，让跨市场时序对齐不再依赖
运行机器时区或散落的硬编码。

## 2. 现状盘点（实施前的事实）

| 项 | 现状 | 问题 |
|---|---|---|
| CN 交易日 | `a_share_history.sqlite` 的 `trading_calendar` 表 | 已配置化，OK |
| US/HK 交易日 | `quant/data_governance/market_calendar.py` 从行情库反推 | 已配置化，OK |
| `default_timezone` | `config.yaml` 写了 `Asia/Shanghai` | **未被任何代码消费** |
| `now` 来源 | `maintenance_orchestrator.py` `datetime.now()`（naive） | 依赖运行机器时区 |
| 尾盘 `14:55` | 策略 + `single_etf_intraday` 默认值，config 可覆盖 | 分散，无市场语义 |
| 开盘 `09:30` | `single_etf_intraday.py:319` | **纯硬编码** |
| 调度时间 | orchestrator `_env_value(NAME, default)` | 默认值散落，无市场语义 |
| 竞价/午休/收盘 | 未建模 | 无 |

## 3. Schema（`config.yaml` 新增段）

```yaml
market_schedules:
  default_timezone: "Asia/Shanghai"     # 系统基准时区（调度、A股、盘前都以此为准）
  markets:
    cn:
      timezone: "Asia/Shanghai"
      sessions:                          # 市场本地时间表达
        call_auction: "09:15-09:25"      # 开盘集合竞价
        open: "09:30"
        morning_close: "11:30"
        afternoon_open: "13:00"
        close: "15:00"
      calendar:                          # 交易日来源
        source: "local_db"
        database_path: "data/a_share_history.sqlite"
        table: "trading_calendar"
    us:
      timezone: "America/New_York"       # 自动处理夏令时
      sessions:
        open: "09:30"
        close: "16:00"
      calendar:
        source: "local_db"
        database_path: "data/us_market_history.sqlite"
        table: "us_daily_bars"
        anchor_symbol: "^SOX"
    hk:
      timezone: "Asia/Hong_Kong"
      sessions:
        open: "09:30"
        close: "16:00"
      calendar:
        source: "local_db"
        database_path: "data/hk_market_history.sqlite"
        table: "hk_daily_bars"
  scheduler:                             # 调度触发时间（基准时区=default_timezone）
    us_market_history: "05:15"           # 美股收盘后动态锚定（16:00 ET + 15min）
    daily_brief: "07:20"
    etf_opening_snapshot: "09:25"
    etf_5min_window: "09:35-15:00"
    cn_finance_flash_window: "09:15-15:05"
    intraday_bill_window: "09:35-15:00"
    core_index_daily_tail: "15:05"       # 收盘后快速刷新 4 个核心指数（看板优先）
    china_options_ho: "15:10"
    index_daily_tail: "16:35"            # 全量指数尾部补数（保留）
    account_bill_confirm: "16:45"
```

`core_index_daily_tail` 与 `index_daily_tail` 的分工：前者在 A 股 15:00 收盘后
立即用 `update-index-history --symbols SH.000001 SZ.399001 SH.000300 SZ.399006`
只刷新四个看板核心指数，几秒到几十秒内即可让看板拿到当日数据；后者仍在收盘后
较晚时段按原逻辑补齐全量（约 995 个）指数。个股日线 `a_share_history` 仍保留在
收盘后较晚时段，因为其 `daily_basic`（估值）字段通常要到盘后更晚才可用。


## 4. 时区归一化方案

- 引入标准库 `zoneinfo`（Python 3.9+，无新依赖）。
- **存储/配置层**：会话时间用**各市场本地时间**（人类可读）；调度时间用
  `default_timezone`（Asia/Shanghai）表达。
- **比较层**：新增 `quant/market_schedule.py`，提供
  `resolve_schedule(config, market)` 把会话时间转成**带时区的 aware datetime**，
  跨市场对齐时先统一到 `default_timezone`（或 UTC）再比较。
- **`now` 修复**：`maintenance_orchestrator.maintenance_tick` 的
  `datetime.now()` 改为 `datetime.now(ZoneInfo(default_timezone))`，日志/判定
  全部基于 aware 时间。
- 夏令时由 `zoneinfo` 自动处理（如 `America/New_York` 的 EDT/EST 切换），
  代码不做手工偏移。

### 4.1 硬约束：禁止 naive 时间跨时区比较（必须遵守）

**反例（必须杜绝的错误）**：拿"美国时间 2026-08-13 17:00"（naive）与
"北京时间 2026-08-14 09:30"（naive）直接相减，会得到"早 16 小时 30 分钟"的
错误结论。实际上 `2026-08-13 17:00 America/New_York`（EDT）换算成北京是
`2026-08-14 05:00`，比 `09:30` 只早 **4 小时 30 分钟**。

**规则**：
1. 任何跨市场、跨时区的时间比较，双方都必须先转成 **aware datetime**，且
   **先归一化到同一时区**（统一用 `default_timezone` 或 UTC）后再比较。
2. `datetime` 对象只要参与比较/相减/排序，就必须带 `tzinfo`；naive 时间只
   允许出现在"该市场本地时钟的纯展示/纯解析"场景，禁止进入比较逻辑。
3. 校验：`market_schedule` 模块暴露的会话时间接口一律返回 aware datetime；
   naive 返回值的函数需在名字里标注 `_naive` 或文档明确"仅本地展示"。

## 5. 消费点清单（实施顺序）

1. 新增 `quant/market_schedule.py`：加载/校验 `market_schedules`，提供
   `session_time(market, key) -> time`、`market_timezone(market) -> ZoneInfo`、
   `scheduler_time(name) -> str`、`aware_now() -> datetime`。
2. `maintenance_orchestrator.py`：
   - `_default_registry` 的调度默认值改为从 `market_schedules.scheduler` 读
     （`_env_value` 仍保留为最高优先级覆盖，向后兼容）。
   - `maintenance_tick` 的 `now` 改为 aware。
   - `_trading_day_decision` 复用 `market_calendar.py`（已做）。
3. `single_etf_intraday.py:319` 的 `09:30` 改为读 `market_schedules.markets.cn.sessions.open`。
4. `cross_market_semiconductor_timing.py` 的 `14:55` 默认值改为读
   `market_schedules.markets.cn.sessions.close` 前一个 5 分钟 bar 的语义
   （保守：仍保留 config 的 `fallback_time` 覆盖为最高优先级）。
5. `config.yaml`：新增 `market_schedules` 段，值=当前硬编码的等价值（行为不变）。

## 6. 边界（明确不做）

- 不引入第三方假日表或新数据源（继续用本地库推导）。
- 不改动各策略的**信号逻辑**，只改时间/日历的取值来源。
- 不把调度器重写成通用 DSL；`market_schedules.scheduler` 只是把现有
  `_env_value` 默认值搬进配置，覆盖优先级不变。
- 半日市（如美股 7/3 提前收盘）不在本期建模，仍按有行情记录=交易日处理。

## 7. 兼容性约束

- 所有调度默认值在配置里写成与当前硬编码**相同的值**，测试断言
  （如 `us_market_news.schedule_value == "06:30"`）不应被破坏。
- `_env_value` 环境变量覆盖优先级必须保持最高，避免破坏既有部署的
  `.env` 定制。
