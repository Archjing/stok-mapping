/** 按缩放级别把日线聚合为 周/月/年K 的纯函数（日历桶，OHLC 正确聚合）。 */

export type Timeframe = '1D' | '1W' | '1M' | '1Y';

export interface IndexBar {
  /** 交易日 YYYY-MM-DD */
  d: string;
  o: number;
  h: number;
  l: number;
  c: number;
}

export interface Aggregated {
  bars: IndexBar[];
  /** 每个聚合 bar 对应的原始日线索引区间 [start, end] */
  spans: Array<[number, number]>;
}

/** 桶起点：1M=当月1日，1Y=当年1月1日，1W=当周周一。全部用 UTC 运算避免时区偏移。 */
function bucketStart(dateStr: string, tf: Exclude<Timeframe, '1D'>): string {
  if (tf === '1M') return `${dateStr.slice(0, 7)}-01`;
  if (tf === '1Y') return `${dateStr.slice(0, 4)}-01-01`;
  const d = new Date(`${dateStr}T00:00:00Z`);
  const day = (d.getUTCDay() + 6) % 7; // 周一=0
  d.setUTCDate(d.getUTCDate() - day);
  return d.toISOString().slice(0, 10);
}

export function aggregateDaily(bars: IndexBar[], tf: Timeframe): Aggregated {
  if (tf === '1D') {
    return {
      bars,
      spans: bars.map((_, i) => [i, i] as [number, number]),
    };
  }

  const out: IndexBar[] = [];
  const spans: Array<[number, number]> = [];
  let cur: IndexBar | null = null;
  let curKey = '';
  let startIdx = 0;

  for (let i = 0; i < bars.length; i++) {
    const b = bars[i];
    const key = bucketStart(b.d, tf);
    if (cur && key === curKey) {
      cur.h = Math.max(cur.h, b.h);
      cur.l = Math.min(cur.l, b.l);
      cur.c = b.c; // 桶内最后一根日线的收盘
    } else {
      if (cur) {
        out.push(cur);
        spans.push([startIdx, i - 1]);
      }
      cur = { d: key, o: b.o, h: b.h, l: b.l, c: b.c };
      curKey = key;
      startIdx = i;
    }
  }
  if (cur) {
    out.push(cur);
    spans.push([startIdx, bars.length - 1]);
  }
  return { bars: out, spans };
}

/** 按钮/程序化跳转用的确定性映射。 */
export function tfForDays(visibleDays: number): Timeframe {
  if (visibleDays <= 365) return '1D';
  if (visibleDays <= 1500) return '1W';
  if (visibleDays <= 4800) return '1M';
  return '1Y';
}

/** 滚轮连续缩放用的迟滞映射，避免在边界反复横跳。 */
export function timeframeForVisibleDays(
  visibleDays: number,
  current: Timeframe,
): Timeframe {
  switch (current) {
    case '1D':
      return visibleDays > 420 ? '1W' : '1D';
    case '1W':
      return visibleDays > 1650 ? '1M' : visibleDays < 330 ? '1D' : '1W';
    case '1M':
      return visibleDays > 5100 ? '1Y' : visibleDays < 1400 ? '1W' : '1M';
    default:
      return visibleDays < 4500 ? '1M' : '1Y';
  }
}

export const TF_LABEL: Record<Timeframe, string> = {
  '1D': '日K',
  '1W': '周K',
  '1M': '月K',
  '1Y': '年K',
};
