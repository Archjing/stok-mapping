export interface Instrument {
  symbol: string;
  name: string;
  kind: 'index' | 'stock';
  start: string;
  end: string;
  count: number;
}

export interface Bar {
  d: string;
  o: number;
  h: number;
  l: number;
  c: number;
}

export interface SearchHit {
  symbol: string;
  name: string;
  kind: 'index' | 'stock';
}

async function json<T>(url: string): Promise<T> {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`${url} -> HTTP ${resp.status}`);
  return (await resp.json()) as T;
}

export function fetchInstruments(): Promise<Instrument[]> {
  return json<{ items: Instrument[] }>('/api/market/instruments').then((d) => d.items);
}

export function fetchBars(symbol: string, opts?: { recent?: '1y'; start?: string; end?: string }): Promise<Bar[]> {
  const q = new URLSearchParams();
  if (opts?.recent) q.set('recent', opts.recent);
  if (opts?.start) q.set('start', opts.start);
  if (opts?.end) q.set('end', opts.end);
  const qs = q.toString();
  return json<{ items: Bar[] }>(`/api/market/bars/${encodeURIComponent(symbol)}${qs ? `?${qs}` : ''}`).then((d) => d.items);
}

export function searchInstruments(q: string): Promise<SearchHit[]> {
  return json<{ items: SearchHit[] }>(`/api/market/search?q=${encodeURIComponent(q)}`).then((d) => d.items);
}
