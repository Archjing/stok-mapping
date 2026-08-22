/** 研究域 API：对照图 + WIKI（原静态站 research/ 内容）。 */
import type { WatchlistData } from './accounts';

export interface ComparisonSignal {
  sourceDate: string;
  targetDate: string;
  change: number;
  direction: 'up' | 'down';
}

export interface ComparisonRun {
  start: string;
  end: string;
  days: number;
  changePct: number;
}

export interface ComparisonData {
  title: string;
  source: { symbol: string; label: string };
  target: { symbol: string; label: string };
  /** [date, srcNorm100, tgtNorm100, srcClose, tgtClose] */
  data: [string, number, number, number, number][];
  startDate: string;
  endDate: string;
  sourceLastDate: string;
  targetLastDate: string;
  tradingDays: number;
  observationBand: { low: number; high: number } | null;
  dailyMappingPct: number | null;
  absoluteThreshold: { value: number; operator: string } | null;
  dailyMappingSignals: ComparisonSignal[];
  consecutiveMove: { days: number; dailyPct: number };
  upRuns: ComparisonRun[];
  downRuns: ComparisonRun[];
}

export interface AccountChartItem {
  slug: string;
  title: string;
  button_label: string;
  button_kicker: string;
  data: ComparisonData | null;
}

export interface CandleSeries {
  symbol: string;
  label: string;
  /** ECharts candlestick 序列（open/high/low/close） */
  data: number[][];
}

export interface CandleData {
  source: CandleSeries;
  target: CandleSeries;
  dates: string[];
  startDate: string;
  endDate: string;
}

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

export const fetchComparison = (slug: string): Promise<ComparisonData> =>
  get(`/api/research/comparison/${slug}`);
export const fetchAccountCharts = (accountId: string): Promise<{ charts: AccountChartItem[] }> =>
  get(`/api/accounts/${accountId}/charts`);

export interface ExploreParams {
  source: string;
  source_storage: string;
  target: string;
  target_storage: string;
  start?: string;
  end?: string;
}

export const fetchCandles = (p: ExploreParams): Promise<CandleData> => {
  const qs = new URLSearchParams({ ...p });
  return get(`/api/research/comparison/candles?${qs.toString()}`);
};

export type { WatchlistData };
