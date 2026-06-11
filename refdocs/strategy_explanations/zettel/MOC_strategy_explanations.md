# MOC｜策略说明知识卡片

## 来源范围

本 MOC 汇总 `docs/strategy_explanations/` 下除 `INDEX.md` 外的 11 个策略说明文档，作为 Anki 卡片生成前的 zettelkasten 中间产物。

## 策略分类

### 动量与低换手

- [[legacy_momentum]]：经典横截面短动量 baseline。
- [[legacy_momentum_low_turnover_v1]]：通过买入/持有阈值分离、周期调仓和换手惩罚降低交易摩擦。

### 质量与低频基本面

- [[quality_growth_price_v1]]：质量成长 + 价格趋势确认。
- [[quality_low_turnover_monthly_v1]]：质量作为慢变量，低波低换手作为约束，月频调仓。
- [[low_vol_low_turnover_quality_v1]]：低波、低换手、质量三因子候选。
- [[core_selection_quality_momentum_v1]]：核心选股型质量动量对照候选。

### 多因子与过滤器

- [[multifactor_volume_price_filter_v1]]：多层资格过滤 + 综合排序。
- [[residual_momentum_reversal_v1]]：残差动量中避开短期过热。
- [[residual_momentum_reversal_v2]]：在 V1 上增加成交质量和形态过滤。

### 技术与主题对照

- [[ma_kline_baseline_v1]]：低复杂度均线 K 线技术规则 baseline。
- [[theme_exposure_momentum_v1]]：允许行业/主题集中暴露的趋势跟随候选。

## 横向结论

- 低换手约束是当前策略解释中的关键改进线索。
- 增加过滤项并不必然提升策略，可能提高参数维度、压碎信号并增加换手。
- 财务质量策略必须严格依赖 point-in-time 财务数据和公告日可见性。
- 主题暴露策略与核心选股策略不能用同一把尺子解释收益来源。
- 简单技术规则适合作为诊断地板，不适合作为当前主策略答案。

## Provenance

- Created: 2026-06-09
- Source directory: `docs/strategy_explanations/`
- Excluded: `docs/strategy_explanations/INDEX.md`
