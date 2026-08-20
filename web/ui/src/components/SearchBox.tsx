import { useEffect, useRef, useState } from 'react';
import { searchInstruments, type Market, type SearchHit } from '../api/market';

interface Props {
  placeholder?: string;
  market?: Market;
  onSelect: (hit: SearchHit) => void;
}

export function SearchBox({ placeholder = '搜索代码/名称', market = 'cn', onSelect }: Props) {
  const [q, setQ] = useState('');
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [open, setOpen] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    const query = q.trim();
    if (!query) {
      setHits([]);
      setOpen(false);
      return;
    }
    clearTimeout(timer.current);
    timer.current = window.setTimeout(async () => {
      try {
        setHits(await searchInstruments(query, market));
        setOpen(true);
      } catch {
        setHits([]);
      }
    }, 250);
    return () => clearTimeout(timer.current);
  }, [q, market]);

  return (
    <div className="searchbox">
      <input
        value={q}
        placeholder={placeholder}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => {
          if (hits.length) setOpen(true);
        }}
        onBlur={() => window.setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            setOpen(false);
            setQ('');
          } else if (e.key === 'Enter') {
            e.preventDefault();
            // 回车确认：优先用已有候选的第一条；尚无候选则即时查询后取第一条
            if (hits.length > 0) {
              onSelect(hits[0]);
              setQ('');
              setOpen(false);
            } else if (q.trim()) {
              searchInstruments(q.trim(), market)
                .then((r) => {
                  if (r.length > 0) {
                    onSelect(r[0]);
                    setQ('');
                    setOpen(false);
                  }
                })
                .catch(() => {});
            }
          }
        }}
      />
      {open && hits.length > 0 && (
        <ul className="searchbox-menu">
          {hits.map((h) => (
            <li
              key={h.symbol}
              onMouseDown={() => {
                onSelect(h);
                setQ('');
                setOpen(false);
              }}
            >
              <span className="sb-name">{h.name}</span>
              <span className="sb-code">{h.symbol}</span>
              <span className={`sb-kind ${h.kind}`}>
                {h.kind === 'index' ? '指数' : h.kind === 'etf' ? 'ETF' : '个股'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
