# T1.2｜Tiingo 接入任务单

适用场景：为 `stok-mapping` 引入 Tiingo 作为**美股个股 / ETF / EOD 主源**，并将 `yfinance` 降级为 fallback。

父级计划：[`DEVELOPMENT_PLAN.md`](../../DEVELOPMENT_PLAN.md)  
任务索引：[`tasks/README.md`](../README.md)

---

## T1.2.0 目标

- [ ] 为关键美股个股 / ETF 提供更正式的 EOD 数据主源
- [ ] 保留 `yfinance` 作为备用源，避免一次性替换风险
- [ ] 为后续跨市场解释层和映射触发标的提供更稳定的数据基础

---

## T1.2.1 接入范围

### T1.2.1.1 首批 Tiingo 标的
- [ ] `NVDA`
- [ ] `AAPL`
- [ ] `TSLA`
- [ ] `KWEB`

### T1.2.1.2 当前明确不纳入
- [ ] GDP / CPI / 利率 / VIX（这些交给 FRED）
- [ ] CNH / FX 代理
- [ ] 所有美股指数一次性替换
- [ ] A 股 / 港股正式链路

---

## T1.2.2 代码任务

### T1.2.2.1 `phase0/data_sources.py`
- [ ] 新增 `fetch_tiingo_daily(symbol, years=None, start=None, end=None)`
- [ ] 统一输出字段：`date`, `open`, `high`, `low`, `close`, `adjusted_close`, `volume`
- [ ] 明确与现有 `fetch_yf_daily()` 返回字段口径兼容
- [ ] 对空结果、认证失败、限流失败做标准化处理

### T1.2.2.2 `check_connectivity()`
- [ ] 在 connectivity report 中加入 `tiingo` 源检查
- [ ] 仅检查首批 4 个标的
- [ ] 输出 `source=tiingo`, `target=<ticker>`

### T1.2.2.3 fallback 关系
- [ ] 明确 Tiingo 抓取失败时回退到 `yfinance`
- [ ] 在结果里区分主源 / fallback 命中情况（如后续需要）

---

## T1.2.3 配置任务

### T1.2.3.1 `config.yaml`
- [ ] 新增 `data_sources.tiingo.enabled`
- [ ] 新增 `data_sources.tiingo.token_env`
- [ ] 新增 `data_sources.tiingo.us_equities`
- [ ] 新增 `data_sources.tiingo.thematic_etfs`
- [ ] 可选：新增 `data_sources.yfinance.fallback_only`

建议结构：

```yaml
data_sources:
  tiingo:
    enabled: true
    token_env: "TIINGO_API_TOKEN"
    us_equities:
      - "NVDA"
      - "AAPL"
      - "TSLA"
    thematic_etfs:
      - "KWEB"
  yfinance:
    enabled: true
    fallback_only: true
```

---

## T1.2.4 使用边界

- [ ] Tiingo 只接美股个股 / ETF / EOD
- [ ] 不用 Tiingo 承接宏观 / 利率 / VIX
- [ ] 不用 Tiingo 替代 A 股正式数据主链路
- [ ] 不一次性替换所有指数与外汇代理

---

## T1.2.5 验证任务

### T1.2.5.1 连通性验证
- [ ] `NVDA` 查询成功
- [ ] `AAPL` 查询成功
- [ ] `TSLA` 查询成功
- [ ] `KWEB` 查询成功

### T1.2.5.2 字段一致性验证
- [ ] 输出字段与 `fetch_yf_daily()` 可兼容
- [ ] `date` 列格式正确
- [ ] `adjusted_close` 可正确映射
- [ ] 空结果 / 异常返回安全处理

### T1.2.5.3 项目集成验证
- [ ] 不影响现有 `phase0.cli run`
- [ ] `phase0_data_source_report.md` 中出现 Tiingo 源状态
- [ ] Tiingo 失败时 `yfinance` 仍能回退成功（如可测）

---

## T1.2.6 归档要求

- [ ] 更新 `DEVELOPMENT_PLAN.md`
- [ ] 更新 `README.md` 的美股数据源说明（如有必要）
- [ ] 更新 `reports/phase0_strategy_change_log.md`
- [ ] 记录 Tiingo 首批覆盖标的和 fallback 原则

---

## T1.2.7 成功标准

- [ ] Tiingo 在 `phase0/data_sources.py` 中可独立抓取
- [ ] 首批 4 个标的可被 connectivity check 覆盖
- [ ] 返回字段与现有日线结构兼容
- [ ] `yfinance` 可继续作为 fallback
- [ ] 文档口径统一

---

## T1.2.8 不做事项

- [ ] 不在本轮处理 FRED
- [ ] 不处理 CNH / FX
- [ ] 不替换所有美股指数
- [ ] 不修改当前 A 股回测逻辑

---

## T1.2.9 一句话提醒

> Tiingo 接入的目标不是“替掉所有海外数据源”，而是**先把最关键的美股个股 / ETF EOD 数据正规化，并在过渡期保留 `yfinance` 作为 fallback，降低替换风险**。
