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

export interface WatchlistData {
  account_id: string;
  headers: string[];
  rows: WatchRow[];
  overview_cards: { label: string; value: string }[];
  account_summary_cards: string[][];
}

export interface BriefData {
  accounts: AccountMeta[];
  account_count: number;
  ready_accounts: number;
  latest_bill_date: string;
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
