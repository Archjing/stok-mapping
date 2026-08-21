export const CORE_INDICES = [
  { symbol: 'SH.000001', name: '上证指数' },
  { symbol: 'SZ.399001', name: '深证成指' },
  { symbol: 'SH.000300', name: '沪深300' },
  { symbol: 'SZ.399006', name: '创业板指' },
] as const;

/** 自定义恐慌指数（30 日中国期权隐含波动率，收盘值序列）。 */
export const CN_PANIC_INDEX = { symbol: 'CN_PANIC_HO30', name: 'A股恐慌' } as const;

/** A股单标的看板指数预设：4 核心指数 + 自定义恐慌指数。 */
export const CN_SINGLE_INDICES = [...CORE_INDICES, CN_PANIC_INDEX] as const;

/** 美股单标的看板指数预设。 */
export const US_INDICES = [
  { symbol: '^IXIC', name: '纳斯达克' },
  { symbol: '^NYA', name: '纽约' },
  { symbol: '^VIX', name: 'VIX恐慌' },
  { symbol: '^SOX', name: '^SOX' },
] as const;

/** 对照看板默认标的池（与静态 index-chart 保持一致，未勾选=仅作候选 chip）。 */
export const DASHBOARD_STOCKS = [
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

export function coreIndexName(symbol: string): string | undefined {
  // A股单标的/对照看板的指数预设（4 核心 + 自定义恐慌指数），用于区分指数 chip 与个股 chip
  return CN_SINGLE_INDICES.find((i) => i.symbol === symbol)?.name;
}

export function dashboardStockName(symbol: string): string | undefined {
  return DASHBOARD_STOCKS.find((s) => s.symbol === symbol)?.name;
}
