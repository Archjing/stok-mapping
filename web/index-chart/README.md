# A股指数走势（交互式蜡烛图）

基于 `data/a_share_history.sqlite` 的三大指数日线蜡烛图：

- 上证指数 `SH.000001`
- 深证成指 `SZ.399001`
- 沪深300 `SH.000300`

功能：蜡烛图（A股红涨绿跌）、**按缩放级别自动切换 K 线粒度**（放大至日K，缩小自动切周K/月K/年K，缩放切换保持同一日期窗口）、明/暗主题切换、滚轮/拖拽缩放 + 底部滑条平移、双击复位、5/10/20/30/60 日均线开关、快速区间（全部/5年/3年/1年）、读数条显示当前粒度/最新收盘/涨跌幅/均线。

**对照看板**（顶栏「单指数 / 对照看板」切换）：指数（上证指数/深证成指/沪深300/创业板指）+ 标的池个股（贵州茅台、五粮液、中国平安、招商银行、平安银行、比亚迪、宁德时代、紫金矿业、长江电力、美的集团）checkbox 多选；同一时间轴**归一化对照**（各标的以可见窗口起点收盘价为基准 100），对比方式可选 **归一化蜡烛 / 归一化收盘 / 归一化均线（MA5~60）**，用于观察谁走势更激烈、谁更平缓。

> 数据口径说明：三大指数均覆盖 **2005-01-04 至今**。沪深300 原有 2005 年起历史；上证指数、深证成指的 2005–2014 区间通过 `stok-quant backfill-index-history`（Tushare index_daily）回补，2005-01-04 起三者对齐。`scripts/extract.ts` 从 `market_index_bars` 抽取日线 OHLC（沪深300 合并 D 与 daily 两种频率），生成内联数据模块 `src/generated/data.ts`。

## 三种使用方式（任选其一）

### 1. 直接双击（无需安装、无需服务器）

```bash
npm install && npm run extract && npm run build
# 然后直接双击打开 dist/index.html
```

`dist/index.html` 是**单文件自包含**产物：数据、样式、ECharts 全部内联，`file://` 双击即可离线查看。

### 2. 开发模式

```bash
npm run dev   # 打开 http://localhost:5180
```

### 3. 本地预览构建产物

```bash
npm run preview
```

## 命令

```bash
npm run extract   # 从 sqlite 抽取 → src/generated/data.ts（数据内联进 bundle）
npm run build     # tsc 校验 + vite 构建 + 内联为单文件 dist/index.html
npm run dev       # 开发服务器
npm run preview   # 预览 dist/
```

数据源路径可用环境变量覆盖：`DATA_SQLITE=/path/to/a_share_history.sqlite npm run extract`。

## 远程发布（share.spidermanread.men）

单文件页已发布到 **https://share.spidermanread.men/index-chart/**（远端 `/var/www/share/index-chart/index.html`）。

每次迭代后一键重新发布（抽取数据 → 构建 → rsync 单文件）：

```bash
./scripts/deploy.sh
```

复用项目 `.env` 中的 `QUANT_SITE_SYNC_PASSWORD`（SSH 密码认证），可用
`QUANT_SITE_SYNC_REMOTE` / `QUANT_INDEX_CHART_REMOTE_DIR` 覆盖目标。

## 结构

```
web/index-chart/
├── index.html
├── scripts/extract.ts      # node:sqlite 抽取脚本（无需原生依赖）
├── scripts/inline-dist.mjs # 构建后把 JS/CSS 内联进单文件
├── scripts/deploy.sh       # 一键构建 + rsync 发布到远端站点
├── scripts/agg-test.ts     # 聚合/粒度单测（npm test）
├── src/main.ts             # ECharts 蜡烛图 + 均线 + dataZoom + 明暗主题
├── src/aggregate.ts        # 按缩放级别聚合 日/周/月/年K 的纯函数
├── src/data-types.ts       # 数据模型
├── src/generated/data.ts   # 抽取产物（gitignored，可重新生成）
└── src/styles.css
```

> 说明：本工具用 **ECharts** 而非 matplotlib。matplotlib 是 Python 库，无法在浏览器内做平滑缩放交互；ECharts 在 TypeScript 生态下提供原生蜡烛图 + dataZoom 缩放/平移，观感已对齐 matplotlib 蜡烛图样式。
