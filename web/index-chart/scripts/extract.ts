/**
 * 从 a_share_history.sqlite 抽取「指数 + 看板标的池」日线 OHLC，生成前端数据模块
 * src/generated/data.ts。
 *
 * 数据直接内联进 bundle（不依赖运行时 fetch），因此构建产物 dist/index.html
 * 是单文件自包含，双击即可离线打开，无需启动服务器。
 *
 * 数据口径：
 * - 指数来自 market_index_bars：上证指数/深证成指/沪深300（2005 起，Tushare 回补后对齐），
 *   创业板指（2010 起）
 * - 个股来自 market_daily_bars（adjust_type='qfq' 前复权，本库自 2011 起），
 *   当前为看板对照用的固定标的池；任意代码动态加载属后续 API 功能
 *
 * 运行：npm run extract
 * 可用环境变量 DATA_SQLITE 覆盖数据库路径。
 */
import { DatabaseSync } from 'node:sqlite';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));

const DB_PATH =
  process.env.DATA_SQLITE ??
  resolve(here, '../../../data/a_share_history.sqlite');
const OUT_PATH = resolve(here, '../src/generated/data.ts');

const INDEX_TARGETS = [
  { symbol: 'SH.000001', name: '上证指数' },
  { symbol: 'SZ.399001', name: '深证成指' },
  { symbol: 'SH.000300', name: '沪深300' },
  { symbol: 'SZ.399006', name: '创业板指' },
] as const;

const STOCK_TARGETS = [
  { symbol: 'SH.600519', name: '贵州茅台' },
  { symbol: 'SZ.000858', name: '五粮液' },
  { symbol: 'SH.601318', name: '中国平安' },
  { symbol: 'SH.600036', name: '招商银行' },
  { symbol: 'SZ.000001', name: '平安银行' },
  { symbol: 'SZ.002594', name: '比亚迪' },
  { symbol: 'SZ.300750', name: '宁德时代' },
  { symbol: 'SH.601899', name: '紫金矿业' },
  { symbol: 'SH.600900', name: '长江电力' },
  { symbol: 'SZ.000333', name: '美的集团' },
] as const;

interface Bar {
  d: string;
  o: number;
  h: number;
  l: number;
  c: number;
}

interface InstrumentMeta {
  symbol: string;
  name: string;
  kind: 'index' | 'stock';
  start: string;
  end: string;
  count: number;
}

function round4(n: number): number {
  return Math.round(n * 10000) / 10000;
}

function dedupeByDate(rows: Array<{ date: string; open: number; high: number; low: number; close: number }>): Bar[] {
  const byDate = new Map<string, Bar>();
  for (const r of rows) {
    if (byDate.has(r.date)) continue;
    byDate.set(r.date, {
      d: r.date,
      o: round4(r.open),
      h: round4(r.high),
      l: round4(r.low),
      c: round4(r.close),
    });
  }
  return [...byDate.values()];
}

/** 指数：market_index_bars（D 与 daily 两种频率按 symbol 合并，按日期去重）。 */
function loadIndexBars(db: DatabaseSync, symbol: string): Bar[] {
  const rows = db
    .prepare(
      `SELECT date, open, high, low, close
         FROM market_index_bars
        WHERE symbol = ?
          AND open IS NOT NULL AND high IS NOT NULL
          AND low IS NOT NULL AND close IS NOT NULL
        ORDER BY date ASC`,
    )
    .all(symbol) as Array<{ date: string; open: number; high: number; low: number; close: number }>;
  return dedupeByDate(rows);
}

/** 个股：market_daily_bars 前复权（qfq）。 */
function loadStockBars(db: DatabaseSync, symbol: string): Bar[] {
  const rows = db
    .prepare(
      `SELECT date, open, high, low, close
         FROM market_daily_bars
        WHERE symbol = ? AND adjust_type = 'qfq'
          AND open IS NOT NULL AND high IS NOT NULL
          AND low IS NOT NULL AND close IS NOT NULL
        ORDER BY date ASC`,
    )
    .all(symbol) as Array<{ date: string; open: number; high: number; low: number; close: number }>;
  return dedupeByDate(rows);
}

function main(): void {
  const db = new DatabaseSync(DB_PATH, { readOnly: true });

  const series: Record<string, Bar[]> = {};
  const instruments: InstrumentMeta[] = [];

  const collect = (
    t: { symbol: string; name: string },
    kind: 'index' | 'stock',
    loader: (db: DatabaseSync, symbol: string) => Bar[],
  ): void => {
    const bars = loader(db, t.symbol);
    if (bars.length === 0) {
      console.warn(`[warn] 未找到 ${t.symbol}(${t.name}) 的数据，已跳过`);
      return;
    }
    series[t.symbol] = bars;
    instruments.push({
      symbol: t.symbol,
      name: t.name.replace(/\s+/g, ''),
      kind,
      start: bars[0].d,
      end: bars[bars.length - 1].d,
      count: bars.length,
    });
    console.log(
      `${kind.padEnd(5)} ${t.name.padEnd(5)} ${t.symbol}  ${bars[0].d} ~ ${bars[bars.length - 1].d}  (${bars.length} 根)`,
    );
  };

  for (const t of INDEX_TARGETS) collect(t, 'index', loadIndexBars);
  for (const t of STOCK_TARGETS) collect(t, 'stock', loadStockBars);

  db.close();

  const payload = {
    meta: {
      generatedAt: new Date().toISOString(),
      // 只写通用名，避免在页面/公开部署中泄露本地绝对路径
      source: 'a_share_history.sqlite',
      instruments,
    },
    series,
  };

  const ts = [
    '// 由 scripts/extract.ts 自动生成，请勿手改；重新生成：npm run extract',
    "import type { IndexDataFile } from '../data-types';",
    '',
    `export const INDEX_DATA: IndexDataFile = ${JSON.stringify(payload)};`,
    '',
  ].join('\n');

  mkdirSync(dirname(OUT_PATH), { recursive: true });
  writeFileSync(OUT_PATH, ts, 'utf8');
  console.log(`已写入 ${OUT_PATH} (${(ts.length / 1024 / 1024).toFixed(2)} MB)`);
}

main();
