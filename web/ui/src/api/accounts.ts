/** 账户域 API（P2：复用 quant.reporting 只读端点）。 */

export interface AccountMeta {
  account_id: string;
  name: string;
  latest_bill_date: string;
  position_start_date: string;
  total_asset: string;
  cash_asset: string;
  stock_asset: string;
  target_exposure: string;
  slug: string;
  strategy_id?: string;
}

export interface WatchCell {
  value: string;
  title: string;
  cls: string;
}

export interface WatchRow {
  class: string;
  cells: WatchCell[];
}

export interface BriefData {
  accounts: AccountMeta[];
  account_count: number;
  ready_accounts: number;
  latest_bill_date: string;
}

export interface BillTable {
  title: string;
  columns: [string, string][];
  rows: Record<string, string>[];
}

export interface BillData {
  account_id: string;
  name: string;
  bill_date: string;
  tables: BillTable[];
}

export interface LedgerSection {
  title: string;
  columns: [string, string][];
  rows: Record<string, string>[];
}

export interface LedgerData {
  account_id: string;
  name: string;
  sections: LedgerSection[];
}

export interface StrategyData {
  strategy_id: string;
  name: string;
  target_symbol?: string;
  target_name?: string;
  note?: string;
  sections: { heading: string; paragraphs: string[] }[];
  research_example: {
    period: string;
    headers: string[];
    rows: string[][];
    terms: string;
  } | null;
}

export interface MarketSnapshotRow {
  类别?: string;
  用途?: string;
  共同交易日?: string;
  标的?: string;
  收盘?: string;
  单日涨跌?: string;
  来源?: string;
  [key: string]: string | undefined;
}

export interface WatchlistData {
  account_id: string;
  kind: 'stock_watchlist' | 'market_snapshot';
  headers?: string[];
  rows?: WatchRow[];
  overview_cards?: { label: string; value: string }[];
  account_summary_cards?: string[][];
  snapshot?: { date?: string; sox_close?: string; sox_change_pct?: string; vix_close?: string } | null;
  market_error?: string;
  research_rows?: MarketSnapshotRow[];
  research_error?: string;
  news?: { title?: string; url?: string; ingested_at?: string; [key: string]: string | undefined }[];
  news_ingested_at?: string;
  news_error?: string;
}

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

export const fetchAccounts = (): Promise<{ accounts: AccountMeta[] }> => get('/api/accounts');
export const fetchBrief = (): Promise<BriefData> => get('/api/accounts/brief');
export const fetchAccount = (slug: string): Promise<AccountMeta> => get(`/api/accounts/${slug}`);
export const fetchWatchlist = (slug: string): Promise<WatchlistData> =>
  get(`/api/accounts/${slug}/watchlist`);
export const fetchBill = (slug: string): Promise<BillData> => get(`/api/accounts/${slug}/bill`);
export const fetchLedger = (slug: string): Promise<LedgerData> => get(`/api/accounts/${slug}/ledger`);
export const fetchStrategy = (slug: string): Promise<StrategyData> =>
  get(`/api/accounts/${slug}/strategy`);
