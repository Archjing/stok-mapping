# T1.4｜A 股历史 as-of 前复权与复权因子治理任务单

适用场景：为 `stok-mapping` 补齐 A 股历史价格复权的 point-in-time 治理，避免“全历史前复权”把未来分红送转信息折回过去，污染动量、均线、波动率、突破等价格特征。

父级计划：[`DEVELOPMENT_PLAN.md`](../../DEVELOPMENT_PLAN.md)  
任务索引：[`docs/tasks/README.md`](../README.md)

---

## T1.4.0 目标

- [x] 在本地历史库中正式保存每日复权因子
- [x] 明确区分不复权真实交易价格、当前全历史前复权价格、历史 as-of 前复权价格
- [x] 为 walk-forward 回测提供 `qfq_asof` 价格读取能力
- [x] 输出复权未来函数风险审计报告
- [x] 策略研究回测默认价格口径已切到 `qfq_asof`；`qfq_current` 仅保留为兼容和审计对照

当前核验状态（2026-06-23）：

- `config.yaml` 当前为 `local_history.price_adjustment_for_backtest: "qfq_asof"`。
- `market_adj_factors` 已覆盖 `2016-01-04` 至 `2026-06-22`，共 `11,197,436` 行。
- `market_daily_basic` 已覆盖 `2016-01-04` 至 `2026-06-22`，共 `10,699,948` 行。
- `market_financial_factors` 已覆盖 `2016-03-31` 至 `2026-03-31`，共 `193,817` 行。
- 仍待增强：验证期按信号日滚动 `as_of_date`、缺因子 / 停牌 / 退市边界覆盖、HTML 审计报告。

---

## T1.4.1 数据治理意义

普通全历史前复权通常用截至今天的复权因子调整过去所有价格。这样会导致：

- 2021 年的历史价格可能已经包含 2023 / 2024 年分红送转影响
- 动量、均线、波动率、突破等价格特征被未来公司行为污染
- 回测收益可能看起来更平滑、更稳定，但并非当时真实可见

本任务目标是保证：

> 回测某个历史时点时，只能看到该时点之前已经可见的价格和复权因子。

---

## T1.4.2 数据层设计

### T1.4.2.1 价格口径

后续本地库需要支持三类口径：

- [x] `bfq_raw`：不复权 OHLCV，真实交易价格，用于执行、涨跌停、成交价和账户仿真
- [x] `qfq_current`：当前全历史前复权，仅保留为兼容和审计对照
- [x] `qfq_asof`：按历史 `as_of_date` 动态计算的点时前复权价格，用于策略特征

### T1.4.2.2 新增复权因子表

建议新增：

```sql
CREATE TABLE IF NOT EXISTS market_adj_factors (
    market TEXT NOT NULL,
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    adj_factor REAL NOT NULL,
    source TEXT,
    updated_at TEXT,
    PRIMARY KEY (market, symbol, date)
);
```

索引：

```sql
CREATE INDEX IF NOT EXISTS idx_adj_factors_symbol_date
ON market_adj_factors(market, symbol, date);
```

---

## T1.4.3 as-of 前复权计算规则

对某个历史观察日 `as_of_date`：

- 只允许读取 `date <= as_of_date` 的 `adj_factor`
- `as_of_factor = adj_factor(as_of_date)`，若当天无因子，取 `<= as_of_date` 最近交易日因子
- 对任意历史日 `t <= as_of_date`：

```text
qfq_open_asof(t, as_of)  = bfq_open(t)  * adj_factor(t) / as_of_factor
qfq_high_asof(t, as_of)  = bfq_high(t)  * adj_factor(t) / as_of_factor
qfq_low_asof(t, as_of)   = bfq_low(t)   * adj_factor(t) / as_of_factor
qfq_close_asof(t, as_of) = bfq_close(t) * adj_factor(t) / as_of_factor
```

交易执行仍然使用 `bfq_raw`，不能用复权价成交。

---

## T1.4.4 代码任务

### T1.4.4.1 新增 `phase0/adjustment.py`

- [x] `ensure_adj_factor_table(conn, table="market_adj_factors")`
- [x] `load_bfq_bars(symbol, start, end)`
- [x] `load_adj_factors(symbol, start, as_of_date)`
- [x] `build_qfq_asof_bars(symbol, start, end, as_of_date)`
- [x] `compare_qfq_current_vs_qfq_asof(symbols, start, end, as_of_date)`

### T1.4.4.2 扩展 `phase0/local_history.py`

将当前：

```python
load_daily_from_local_history(symbol, start, end)
```

扩展为：

```python
load_daily_from_local_history(
    symbol,
    start,
    end,
    price_adjustment="qfq_current",
    as_of_date=None,
)
```

支持：

- [x] `price_adjustment="qfq_current"`
- [x] `price_adjustment="bfq"`
- [x] `price_adjustment="qfq_asof"`

### T1.4.4.3 扩展 Tushare / 导入链路

- [x] 将 Tushare `adj_factor` 正式落入 `market_adj_factors`
- [ ] 历史 zip 导入后补齐 `bfq` 日线完整性审计
- [ ] 若只有 `qfq` 而无 `bfq` 或 `adj_factor`，报告必须标记为无法进行 as-of 复权

### T1.4.4.4 扩展 walk-forward

- [x] 新增配置 `local_history.price_adjustment_for_backtest`
- [x] 默认策略研究口径已切换为 `qfq_asof`
- [x] 保留对照模式 `qfq_current`
- [x] 在每个 fold 中将训练窗口 `as_of_date` 设为 `train_end`
- [ ] 后续增强为验证期按信号日滚动 `as_of_date`，默认不启用以避免运行时间大幅增加

---

## T1.4.5 配置任务

建议新增：

```yaml
local_history:
  price_adjustment_for_backtest: "qfq_asof"
  price_adjustment_audit:
    enabled: true
    compare_modes: ["qfq_current", "qfq_asof", "bfq_raw"]
    feature_checks: ["mom20", "ma20", "vol20", "breakout20"]
```

兼容对照口径：

```yaml
local_history:
  price_adjustment_for_backtest: "qfq_current"
```

---

## T1.4.6 审计任务

新增命令：

```bash
python -m phase0.cli adjustment-audit --config config.yaml
```

输出：

- [x] `reports/price_adjustment_audit.csv`
- [x] `reports/price_adjustment_audit.md`
- [ ] 后续增强：`reports/price_adjustment_audit.html`

审计内容：

- [x] 是否存在 `bfq` 日线
- [x] 是否存在 `market_adj_factors`
- [x] `qfq_current` 与 `qfq_asof` 的价格差异
- [x] `mom20`、`ma20`、`vol20`、`breakout20` 差异最大的股票和日期
- [x] 当前 `phase0 run` 使用的价格口径
- [x] 是否存在无法 as-of 复权的股票

---

## T1.4.7 分阶段实施

### T1.4.7.1 P0：数据可用性审计

- [x] 检查当前库是否有完整 `bfq` 日线
- [x] 检查当前库是否有每日 `adj_factor`
- [x] 输出缺口报告
- [x] 不改变任何回测结果

### T1.4.7.2 P1：复权因子落表

- [x] 新建 `market_adj_factors`
- [x] Tushare 增量更新时写入因子表
- [x] 历史区间补齐因子表
- [x] 记录来源与更新时间

### T1.4.7.3 P2：`qfq_asof` loader

- [x] 实现按 `as_of_date` 动态构造前复权 OHLC
- [x] 与当前 `qfq` 输出做对照
- [ ] 覆盖缺因子、停牌日、退市股票等边界

### T1.4.7.4 P3：审计报告

- [x] 输出价格差异报告
- [x] 输出特征差异报告
- [ ] 若差异影响策略信号，标记当前回测污染风险

### T1.4.7.5 P4：walk-forward 对照运行

- [x] 新增 `qfq_asof` research profile 对照
- [x] 与当前 `qfq_current` 结果比较
- [x] 若结果差异显著，当前 `qfq_current` 报告降级为兼容口径
- [x] 运行最新版本全候选策略池 `qfq_asof` compare，确认当前无合格 candidate

---

## T1.4.8 验收标准

- [x] 本地库可查询每只股票每日复权因子
- [x] `qfq_asof` 计算不读取 `as_of_date` 之后的因子
- [x] 交易执行价格仍使用不复权价格
- [x] 审计报告能列出当前回测价格口径
- [x] 审计报告能列出 `qfq_current` 与 `qfq_asof` 的主要差异
- [x] `phase0 run` 默认行为已通过配置显式切到 `qfq_asof`，不是代码静默切换
- [x] 切回 `qfq_current` 必须通过配置显式开启，仅用于兼容和审计对照

---

## T1.4.9 不做事项

- [ ] 不用复权价模拟成交
- [ ] 不在未审计前直接替换当前主报告口径
- [ ] 不把 current qfq 结果继续解释为严格 point-in-time 价格结果
- [ ] 不忽略缺失 `bfq` / `adj_factor` 的股票

---

## T1.4.10 一句话提醒

> 这项治理的目标不是让价格更“顺”，而是确保历史回测中的价格特征只使用当时可见的信息，避免未来分红送转信息污染策略信号。
