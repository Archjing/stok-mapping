import { useEffect, useRef, useState } from 'react';
import { searchInstruments, type SearchHit } from '../api/market';

interface Props {
  placeholder?: string;
  onSelect: (hit: SearchHit) => void;
}

export function SearchBox({ placeholder = '搜索代码/名称', onSelect }: Props) {
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
        setHits(await searchInstruments(query));
        setOpen(true);
      } catch {
        setHits([]);
      }
    }, 250);
    return () => clearTimeout(timer.current);
  }, [q]);

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
              <span className={`sb-kind ${h.kind}`}>{h.kind === 'index' ? '指数' : '个股'}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
