import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchAccounts, type AccountMeta } from '../api/accounts';

/** 半导体跨市场映射策略 id：其账户点击后直达映射对照图页（原站点账户主页的对照图）。 */
const SEMI_STRATEGY = 'cross_market_semiconductor_timing_etf_v1';

/** 顶栏"模拟账户"下拉菜单：动态列出已启用账户；半导体策略账户→映射图页，其余→账户主页。 */
export function AccountsMenu() {
  const [open, setOpen] = useState(false);
  const [accounts, setAccounts] = useState<AccountMeta[]>([]);
  const rootRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!open) return;
    let alive = true;
    fetchAccounts()
      .then((d) => alive && setAccounts(d.accounts))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const go = (a: AccountMeta) => {
    setOpen(false);
    const isSemi = a.strategy_id === SEMI_STRATEGY;
    navigate(isSemi ? `/accounts/${a.slug}/charts` : `/accounts/${a.slug}`);
  };

  return (
    <div className="nav-menu" ref={rootRef}>
      <button
        className={`nav-menu-btn${open ? ' active' : ''}`}
        onClick={() => setOpen((v) => !v)}
        title="已启用的模拟账户"
      >
        模拟账户
        <span className="nav-menu-caret">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="nav-menu-panel">
          {accounts.length === 0 && <div className="nav-menu-empty">加载中……</div>}
          {accounts.map((a) => (
            <button key={a.slug} className="nav-menu-item" onClick={() => go(a)}>
              <span>{a.name}</span>
              {a.strategy_id === SEMI_STRATEGY && <span className="nav-menu-tag">映射图</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
