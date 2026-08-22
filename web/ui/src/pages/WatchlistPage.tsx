import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { fetchWatchlist, type WatchlistData } from '../api/accounts';

/** 盘前观察池：17 列表格 + 概要卡（移植自原静态站 watchlist/index.html）。 */
export function WatchlistPage() {
  const { accountId = '' } = useParams();
  const [data, setData] = useState<WatchlistData | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    setData(null);
    setError('');
    fetchWatchlist(accountId)
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(`观察池加载失败：${e}`));
    return () => {
      alive = false;
    };
  }, [accountId]);

  return (
    <div className="page-view">
      <div className="view-head">
        <h2 className="view-title">盘前观察池</h2>
      </div>
      {error && <p className="error">{error}</p>}
      {!data && !error && <p className="dim-text">加载中（首次生成观察池可能需要数十秒）……</p>}
      {data && (
        <>
          <div className="summary-cards">
            {data.overview_cards.map((c) => (
              <div key={c.label} className="summary-card">
                <span>{c.label}</span>
                <strong>{c.value}</strong>
              </div>
            ))}
            {data.account_summary_cards.map(([label, value]) => (
              <div key={label} className="summary-card">
                <span>{label}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
          <div className="table-wrap">
            <table className="report-table watchlist-table">
              <thead>
                <tr>
                  {data.headers.map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row, i) => (
                  <tr key={i} className={row.class}>
                    {row.cells.map((cell, j) => (
                      <td key={j} className={cell.cls} title={cell.title}>
                        {cell.value}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="notice-text">
            动作行为当前模拟账户口径（依确认持仓与本期目标计算）；信号动作为策略研究口径，不等同于交易指令。
          </p>
        </>
      )}
    </div>
  );
}
