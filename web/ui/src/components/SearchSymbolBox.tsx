import { useMemo, useRef, useState } from 'react';

interface SymbolInfo {
  symbol: string;
  label: string;
}

interface Props {
  placeholder?: string;
  options: SymbolInfo[];
  value: string;
  onSelect: (s: SymbolInfo) => void;
}

/** 可搜索标的输入（与行情页 SearchBox 同款交互：输入过滤 + 下拉建议 + 名称/代码/类型）。 */
export function SearchSymbolBox({ placeholder = '搜索代码/名称', options, value, onSelect }: Props) {
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  const list = useMemo(() => {
    const query = q.trim().toLowerCase();
    if (!query) return options;
    return options.filter(
      (o) => o.symbol.toLowerCase().includes(query) || o.label.toLowerCase().includes(query),
    );
  }, [q, options]);

  const current = options.find((o) => o.symbol === value);

  return (
    <div className="searchbox">
      <input
        value={open ? q : current ? `${current.label} ${current.symbol}` : ''}
        placeholder={placeholder}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
          clearTimeout(timer.current);
          timer.current = window.setTimeout(() => {
            if (e.target.value.trim()) setOpen(true);
          }, 120);
        }}
        onFocus={() => {
          setQ('');
          setOpen(true);
        }}
        onBlur={() => window.setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            setOpen(false);
            setQ('');
          } else if (e.key === 'Enter') {
            e.preventDefault();
            if (list.length > 0) {
              onSelect(list[0]);
              setQ('');
              setOpen(false);
            }
          }
        }}
      />
      {open && list.length > 0 && (
        <ul className="searchbox-menu">
          {list.map((o) => (
            <li
              key={o.symbol}
              onMouseDown={() => {
                onSelect(o);
                setQ('');
                setOpen(false);
              }}
            >
              <span className="sb-name">{o.label}</span>
              <span className="sb-code">{o.symbol}</span>
              <span className={`sb-kind ${o.symbol.startsWith('^') ? 'index' : 'etf'}`}>
                {o.symbol.startsWith('^') ? '指数' : '标的'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
