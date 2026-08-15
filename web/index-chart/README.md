# A股指数走势（交互式蜡烛图）

基于 `data/a_share_history.sqlite` 的三大指数日线蜡烛图：

- 上证指数 `SH.000001`
- 深证成指 `SZ.399001`
- 沪深300 `SH.000300`

功能：蜡烛图（A股红涨绿跌）、滚轮/拖拽缩放 + 底部滑条平移、5/10/20/30/60 日均线开关、快速区间（全部/5年/3年/1年）。

> 数据口径说明：三大指数均覆盖 **2005-01-04 至今**。沪深300 原有 2005 年起历史；上证指数、深证成指的 2005–2014 区间通过 `stok-quant backfill-index-history`（Tushare index_daily）回补，2005-01-04 起三者对齐。`scripts/extract.ts` 从 `market_index_bars` 抽取日线 OHLC（沪深300 合并 D 与 daily 两种频率）。

## 运行

```bash
cd web/index-chart
npm install
npm run extract   # 从 sqlite 抽取 → public/indices.json
npm run dev       # 打开 http://localhost:5180
```

## 生产构建

```bash
npm run build     # 产物在 dist/
npm run preview   # 本地预览构建产物
```

数据源路径可用环境变量覆盖：`DATA_SQLITE=/path/to/a_share_history.sqlite npm run extract`。

## 结构

```
web/index-chart/
├── index.html
├── scripts/extract.ts   # node:sqlite 抽取脚本（无需原生依赖）
├── src/main.ts          # ECharts 蜡烛图 + 均线 + dataZoom
├── src/styles.css
└── public/indices.json  # 抽取产物（可重新生成）
```

> 说明：本工具用 **ECharts** 而非 matplotlib。matplotlib 是 Python 库，无法在浏览器内做平滑缩放交互；ECharts 在 TypeScript 生态下提供原生蜡烛图 + dataZoom 缩放/平移，观感已对齐 matplotlib 蜡烛图样式。
