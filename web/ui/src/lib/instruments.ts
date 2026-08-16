export const CORE_INDICES = [
  { symbol: 'SH.000001', name: '上证指数' },
  { symbol: 'SZ.399001', name: '深证成指' },
  { symbol: 'SH.000300', name: '沪深300' },
  { symbol: 'SZ.399006', name: '创业板指' },
] as const;

export function coreIndexName(symbol: string): string | undefined {
  return CORE_INDICES.find((i) => i.symbol === symbol)?.name;
}
