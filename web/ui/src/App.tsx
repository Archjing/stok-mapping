import { useEffect, useState } from 'react';

interface Instrument {
  symbol: string;
  name: string;
  kind: string;
  start: string;
  end: string;
  count: number;
}

interface BarsResponse {
  symbol: string;
  items: Array<{ d: string; o: number; h: number; l: number; c: number }>;
}

export default function App() {
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [selected, setSelected] = useState<string>('SH.000001');
  const [bars, setBars] = useState<BarsResponse | null>(null);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    fetch('/api/market/instruments')
      .then((r) => r.json())
      .then((d) => setInstruments(d.items))
      .catch((e) => setError(`instruments 加载失败: ${e}`));
  }, []);

  useEffect(() => {
    setBars(null);
    fetch(`/api/market/bars/${selected}?recent=1y`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => setBars(d))
      .catch((e) => setError(`bars 加载失败: ${e}`));
  }, [selected]);

  return (
    <main style={{ fontFamily: 'system-ui', padding: 24 }}>
      <h1>stok-mapping 网站控制台（P0 骨架）</h1>
      {error && <p style={{ color: 'red' }}>{error}</p>}

      <label>指数：</label>
      <select value={selected} onChange={(e) => setSelected(e.target.value)}>
        {instruments.map((i) => (
          <option key={i.symbol} value={i.symbol}>
            {i.name}（{i.symbol}）
          </option>
        ))}
      </select>

      <p>
        共 {instruments.length} 个指数 · 当前选中近一年 bar 数：
        {bars ? bars.items.length : '加载中…'}
      </p>
      {bars && bars.items.length > 0 && (
        <p>
          最新：{bars.items[bars.items.length - 1].d} 收{' '}
          {bars.items[bars.items.length - 1].c.toFixed(2)}
        </p>
      )}
    </main>
  );
}
