/**
 * 从 a_share_history.sqlite 抽取三大指数日线 OHLC，输出为前端静态 JSON。
 *
 * 数据口径：
 * - 上证指数  SH.000001  本库仅有 daily（2015-01-05 起）
 * - 深证成指  SZ.399001  本库仅有 daily（2015-01-05 起）
 * - 沪深300   SH.000300  由 D（2005-01-04 ~ 2014-12-31）与 daily（2015-01-05 起）合并
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
const OUT_PATH = resolve(here, '../public/indices.json');

const TARGETS = [
  { symbol: 'SH.000001', name: '上证指数' },
  { symbol: 'SZ.399001', name: '深证成指' },
  { symbol: 'SH.000300', name: '沪深300' },
] as const;

interface Bar {
  d: string;
  o: number;
  h: number;
  l: number;
  c: number;
}

interface IndexMeta {
  symbol: string;
  name: string;
  start: string;
  end: string;
  count: number;
}

function round4(n: number): number {
  return Math.round(n * 10000) / 10000;
}

function loadBars(db: DatabaseSync, symbol: string): Bar[] {
  // D 与 daily 两种频率都按同一 symbol 取回，再按日期去重（二者区间不重叠）。
  const rows = db
    .prepare(
      `SELECT date, open, high, low, close
         FROM market_index_bars
        WHERE symbol = ?
          AND open IS NOT NULL AND high IS NOT NULL
          AND low IS NOT NULL AND close IS NOT NULL
        ORDER BY date ASC`,
    )
    .all(symbol) as Array<{
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
  }>;

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

function main(): void {
  const db = new DatabaseSync(DB_PATH, { readOnly: true });

  const series: Record<string, Bar[]> = {};
  const indices: IndexMeta[] = [];

  for (const t of TARGETS) {
    const bars = loadBars(db, t.symbol);
    if (bars.length === 0) {
      console.warn(`[warn] 未找到 ${t.symbol}(${t.name}) 的数据，已跳过`);
      continue;
    }
    series[t.symbol] = bars;
    indices.push({
      symbol: t.symbol,
      name: t.name,
      start: bars[0].d,
      end: bars[bars.length - 1].d,
      count: bars.length,
    });
    console.log(
      `${t.name.padEnd(5)} ${t.symbol}  ${bars[0].d} ~ ${bars[bars.length - 1].d}  (${bars.length} 根)`,
    );
  }

  db.close();

  const payload = {
    meta: {
      generatedAt: new Date().toISOString(),
      source: DB_PATH,
      indices,
    },
    series,
  };

  mkdirSync(dirname(OUT_PATH), { recursive: true });
  writeFileSync(OUT_PATH, JSON.stringify(payload), 'utf8');
  console.log(`已写入 ${OUT_PATH}`);
}

main();
