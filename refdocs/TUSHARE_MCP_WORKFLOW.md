# Tushare MCP 查询工作流（适配 `stok-mapping`）

## 1. 目标定位

`stok-mapping` 当前的数据主链路是：

- **A 股盘后主源**：Tushare Pro
- **开发/研究辅助与 fallback**：AkShare / 新浪原始快照 / 本地历史库
- **正式批处理入口**：`phase0.cli`
- **正式产物**：`reports/*.md`、`data/universe/*.csv`、本地 SQLite

在这个前提下，`tushareMcp` 的正确角色不是替代正式批处理链路，而是：

> **查询层 / 核对层 / 解释层**

也就是说：
- 正式回测、正式股票池、正式历史落库仍由 `phase0.cli` 和本地库负责
- `tushareMcp` 只用于少量、交互式、按需查询
- 最终服务的是盘前分析、数据核对、研究补问，而不是直接产出交易信号

---

## 2. 适合承担的任务

### 2.1 盘前补查
适合在候选观察池出来后，针对少量标的补查：
- 最新日线或实时截面
- 最新 PE / PB / 总市值 / 换手
- 停复牌状态
- 最近公告
- 两融标的状态
- 资金异动

### 2.2 数据一致性核对
适合在怀疑数据异常时做单点核查：
- 某只股票某交易日的 OHLCV
- 某只股票最近横截面字段
- 某一财务字段最近一次披露值
- 某交易日是否为有效交易日

### 2.3 策略研究辅助
适合小样本验证，不适合代替批量回测：
- 候选池最近一期财务分布
- 某类风格股票的横截面对比
- 某个假设是否值得进入下一轮 walk-forward

### 2.4 盘后复盘补查
适合盘后解释层：
- 资金流
- 涨跌停 / 炸板
- 龙虎榜
- 公告 / 研报
- 北向 / 南向 / 板块热度

---

## 3. 不适合承担的任务

### 3.1 不要替代正式批处理
不要把 MCP 当成：
- `update-history` 的替代
- `update-financials` 的替代
- walk-forward 回测主数据源
- universe 构建主数据源

### 3.2 不要让 LLM 直接自由发挥选股
不要让工作流变成：

```text
Tushare MCP 拉一些数据 → LLM 自由判断 → 直接给买卖建议
```

当前阶段正确的顺序应该是：

```text
phase0.cli / 本地 SQLite / 正式报告
    ↓
Tushare MCP 做少量补查
    ↓
LLM 输出解释层 / 风险层 / 观察池说明
```

---

## 4. 推荐工作流

## 工作流 A：盘前观察池补查

### 触发条件
已经有候选标的，例如来自：
- `local_factor_universe.csv`
- walk-forward 当前优胜候选
- 人工指定观察池

### 查询目标
对每只候选补查：
- 最近走势
- 估值快照
- 是否停牌
- 是否有公告
- 是否存在明显风险标记

### 输出目标
生成结构化结果：

```json
{
  "symbol": "SH.600519",
  "price_snapshot": {...},
  "valuation_snapshot": {...},
  "trading_status": {...},
  "recent_notice": {...},
  "risk_flags": [...],
  "note": "适合继续观察，但不建议追高"
}
```

---

## 工作流 B：本地数据核对

### 触发条件
当你怀疑：
- 本地库与主源不一致
- 某只股票数据异常
- 某日 universe 结果异常
- 某字段可能有未来函数污染

### 查询目标
单点核查：
- 某股票某交易日的日线
- 某股票最近的 `daily_basic`
- 某报告期财务字段
- 公告日期 / 披露日期

### 输出目标
形成审计结果：

```json
{
  "symbol": "SZ.300750",
  "check_type": "daily_bar_consistency",
  "local_value": {...},
  "tushare_value": {...},
  "status": "match / mismatch",
  "possible_reason": "adjustment / stale snapshot / source lag"
}
```

---

## 工作流 C：候选池财务快照

### 触发条件
你准备研究：
- 质量成长因子
- 多因子 + 量价筛选
- 候选池里谁的基本面更健康

### 查询目标
对少量候选股做财务截面对比：
- ROE
- 营收增速
- 利润增速
- 现金流质量
- 负债率

### 输出目标
生成研究快照：

```json
{
  "snapshot_date": "...",
  "rows": [
    {"symbol": "SH.600519", "roe": ..., "revenue_growth": ..., "profit_growth": ...}
  ]
}
```

---

## 工作流 D：盘后复盘补查

### 触发条件
当天：
- 市场大幅波动
- 观察池有异常走势
- 某候选表现显著背离

### 查询目标
补查：
- 资金流
- 龙虎榜
- 涨跌停情况
- 公告
- 研究报告

### 输出目标
生成盘后复盘 JSON 或 Markdown：

```json
{
  "trade_date": "20260529",
  "market_events": [...],
  "watchlist_review": [...],
  "tomorrow_risk_flags": [...]
}
```

---

## 5. 推荐查询优先级

### Level 1：最实用，先纳入
- 日线 / 实时：`daily`、`rt_k`
- 截面：`daily_basic`
- 停复牌：`suspend_d`
- 公告：`anns_d`
- 资金流：`moneyflow_dc`
- 交易日历：`trade_cal`

### Level 2：研究增强
- 财务指标：`fina_indicator`
- 利润表：`income`
- 资产负债表：`balancesheet`
- 现金流：`cashflow`
- 披露计划：`disclosure_date`

### Level 3：短线复盘增强
- 涨跌停：`limit_list_d`
- 龙虎榜：`top_list`、`top_inst`
- 北向资金：`moneyflow_hsgt`

---

## 6. 与 `stok-mapping` 的接法

## 6.1 不推荐的接法

不要这样用：

```text
walk_forward.py -> 每次循环都调 Tushare MCP
```

这样会导致：
- 慢
- 不可复现
- 不利于批量回测
- 容易把交互式查询层和正式批处理层混在一起

## 6.2 推荐的接法

```text
phase0.cli 跑正式结果
    ↓
本地 SQLite / reports / universe 产出
    ↓
Tushare MCP 做小范围补查
    ↓
LLM 生成解释层 / 研判层 / 风险层
```

---

## 7. 输出文件建议

如果后续要把 MCP 查询正式纳入项目留痕，建议生成这些中间产物：

- `reports/mcp_pre_market_snapshot.json`
- `reports/mcp_data_consistency_checks.json`
- `reports/mcp_research_notes.md`
- `reports/mcp_post_market_review.json`

这样 MCP 查询结果不会只停留在对话里。

---

## 8. 安全建议

- `.mcp.json` 只使用环境变量，不要写明文 token
- 当前推荐写法：

```json
{
  "mcpServers": {
    "tushareMcp": {
      "url": "https://api.tushare.pro/mcp/?token=${TUSHARE_TOKEN}"
    }
  }
}
```

- `.mcp.json` 已建议加入 `.gitignore`
- MCP 查询结果不能直接等于交易信号

---

## 9. 提示词模板

以下模板用于 Claude / 本地研究代理配合 `tushareMcp` 工作。

---

## 模板 1：盘前补查提示词

### 用途
在观察池已产生后，对少量标的做盘前补充查询和解释。

### 模板

```text
你现在是 `stok-mapping` 的盘前补查助手。

任务目标：
- 仅对我给出的少量候选标的做 Tushare MCP 补查
- 不自由扩展到全市场
- 不直接给买卖指令
- 只输出：走势快照、估值快照、风险标记、观察说明

工作约束：
1. 优先使用 `tushareMcp`
2. 只查询我给出的 symbols
3. 如果 MCP 数据不足，再明确说明“查询不足”，不要猜测
4. 输出语言使用中文
5. 不使用“买入/卖出/清仓/满仓/荐股”措辞
6. 输出必须结构化

输入：
- trade_date: {{trade_date}}
- symbols: {{symbols}}
- lookback_days: {{lookback_days}}
- focus: {{focus}}

查询建议：
- 先查最近日线/实时截面
- 再查 daily_basic
- 如有必要，再查 suspend_d / anns_d / moneyflow_dc

输出 JSON 结构：
{
  "trade_date": "...",
  "symbols": [
    {
      "symbol": "...",
      "trend_snapshot": "...",
      "valuation_snapshot": {
        "pe": null,
        "pb": null,
        "market_cap": null,
        "turnover": null
      },
      "risk_flags": [],
      "note": "..."
    }
  ],
  "overall_note": "..."
}
```

---

## 模板 2：数据一致性核对提示词

### 用途
核对本地结果与 Tushare 查询结果是否一致，辅助审计。

### 模板

```text
你现在是 `stok-mapping` 的数据一致性核对助手。

任务目标：
- 使用 `tushareMcp` 核对指定股票/日期/字段
- 只做核对，不做投资结论
- 如果发现不一致，优先解释可能原因

工作约束：
1. 只查询我指定的 symbol / date / field
2. 不自由扩展查询范围
3. 如果查询不到，就明确返回 not_found
4. 输出必须是审计格式，不写投资建议
5. 输出语言使用中文

输入：
- check_type: {{check_type}}
- symbol: {{symbol}}
- trade_date: {{trade_date}}
- local_value: {{local_value}}
- fields_to_check: {{fields_to_check}}

查询建议：
- 日线核查优先：daily / rt_k
- 横截面核查优先：daily_basic
- 财务字段核查优先：fina_indicator / income / balancesheet / cashflow
- 交易日核查优先：trade_cal

输出 JSON 结构：
{
  "symbol": "...",
  "trade_date": "...",
  "check_type": "...",
  "status": "match / mismatch / not_found",
  "checked_fields": [
    {
      "field": "close",
      "local_value": "...",
      "tushare_value": "...",
      "result": "match / mismatch / not_found"
    }
  ],
  "possible_reason": "...",
  "next_action": "..."
}
```

---

## 10. 一句话结论

> `tushareMcp` 在 `stok-mapping` 中最适合做：**查询层 / 核对层 / 解释层**。  
> 不适合做：**正式批处理回测主链路**。  
> 正确用法是：**先由 `phase0.cli` 和本地 SQLite 产出正式结果，再由 Tushare MCP 做少量补查与解释增强。**
