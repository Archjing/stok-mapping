# T1.1｜FRED 接入任务单

适用场景：为 `stok-mapping` 正式引入 FRED 作为**宏观 / 利率 / VIX 主源**，替代当前这部分对 `yfinance` 的依赖。

父级计划：[`DEVELOPMENT_PLAN.md`](../../docs/DEVELOPMENT_PLAN.md)  
任务索引：[`tasks/README.md`](../README.md)

---

## T1.1.0 目标

- [x] 把宏观与利率数据从 `yfinance` 逻辑中拆分出来
- [x] 为 `phase0` 提供稳定、可解释、可维护的 FRED 数据入口
- [x] 不破坏当前正式 A 股链路与回测逻辑

---

## T1.1.1 接入范围

### T1.1.1.1 首批 FRED 序列
- [x] `GDP` → 美国 GDP
- [x] `CPIAUCSL` → 美国 CPI
- [x] `FEDFUNDS` → 联邦基金利率（月）
- [x] `DFF` → 有效联邦基金利率（日）
- [x] `VIXCLS` → VIX 日序列

### T1.1.1.2 当前明确不纳入
- [x] 外汇代理（CNH / CNY）
- [x] 美股个股 / ETF
- [x] A 股数据
- [x] 港股数据

---

## T1.1.2 代码任务

### T1.1.2.1 `phase0/data_sources.py`
- [x] 新增 `fetch_fred_series(series_id, years=None, start=None, end=None)`
- [x] 输出字段统一为：`date`, `value`
- [x] 统一时间列为 `date`
- [x] 对空返回、异常响应做标准化处理

### T1.1.2.2 `check_connectivity()`
- [x] 在 connectivity report 中加入 `fred` 源检查
- [x] 可配置地检查首批 5 个序列
- [x] 输出 `source=fred`, `target=<series_id>`

### T1.1.2.3 新增配置读取
- [x] 从 `config.yaml` 读取 `fred.enabled`
- [x] 从 `config.yaml` 读取 `fred.series`
- [x] 可选读取 `fred.api_key_env`

---

## T1.1.3 配置任务

### T1.1.3.1 `config.yaml`
- [x] 新增 `data_sources.fred.enabled`
- [x] 新增 `data_sources.fred.api_key_env`
- [x] 新增 `data_sources.fred.series.gdp`
- [x] 新增 `data_sources.fred.series.cpi`
- [x] 新增 `data_sources.fred.series.fedfunds`
- [x] 新增 `data_sources.fred.series.fedfunds_daily`
- [x] 新增 `data_sources.fred.series.vix`

建议结构：

```yaml
data_sources:
  fred:
    enabled: true
    api_key_env: "FRED_API_KEY"
    series:
      gdp: "GDP"
      cpi: "CPIAUCSL"
      fedfunds: "FEDFUNDS"
      fedfunds_daily: "DFF"
      vix: "VIXCLS"
```

---

## T1.1.4 使用边界

- [x] FRED 仅负责宏观 / 利率 / VIX
- [x] 不把 FRED 塞进主回测排序逻辑
- [x] 不让 FRED 替代美股个股 / ETF 行情
- [x] 先用于 overlay / 解释层 / 报告摘要输入

---

## T1.1.5 验证任务

### T1.1.5.1 连通性验证
- [x] `GDP` 查询成功
- [x] `CPIAUCSL` 查询成功
- [x] `FEDFUNDS` 查询成功
- [x] `DFF` 查询成功
- [x] `VIXCLS` 查询成功

### T1.1.5.2 数据格式验证
- [x] 时间列统一为 `date`
- [x] 数值列统一为 `value`
- [x] 最近日期可正确读取
- [x] 空结果能安全返回空 DataFrame

### T1.1.5.3 项目集成验证
- [x] 不影响现有 `phase0.cli run`
- [x] 不影响现有 A 股数据主链路
- [x] `phase0_data_source_report.md` 中出现 FRED 源状态

---

## T1.1.6 归档要求

- [x] 更新 `DEVELOPMENT_PLAN.md`
- [x] 更新 `README.md` 的数据源说明（如有必要）
- [x] 更新 `reports/phase0_strategy_change_log.md`
- [x] 记录 FRED 序列与用途映射表

---

## T1.1.7 成功标准

- [x] FRED 在 `phase0/data_sources.py` 中可独立抓取
- [x] 首批 5 个序列可被 connectivity check 覆盖
- [x] 配置层可开关
- [x] 不破坏当前正式链路
- [x] 文档口径与主计划统一

---

## T1.1.8 不做事项

- [x] 不在本轮处理 Tiingo
- [x] 不处理 CNH / FX
- [x] 不把 FRED 接进主 ranker
- [x] 不修改当前 A 股回测逻辑

## T1.1.10 当前完成状态

- 状态：已完成最小接入与连通性验收。
- 验收日期：2026-06-01 / 2026-06-02。
- 验收记录：`reports/phase0_strategy_change_log.md` 与 `reports/phase0_data_source_report.md`。
- 缓存策略：`data/cache/fred/`，默认 TTL `24` 小时。

---

## T1.1.9 一句话提醒

> FRED 接入的目标不是增加一个“更复杂的数据源”，而是**把宏观 / 利率 / VIX 从 `yfinance` 中规范拆分出来，为 overlay 与日报解释层建立更稳定的数据基础**。
