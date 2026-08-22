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
      {data && data.kind === 'market_snapshot' && (
        <>
          <div className="summary-cards">
            {data.snapshot ? (
              <>
                <div className="summary-card">
                  <span>共同交易日</span>
                  <strong>{data.snapshot.date ?? '—'}</strong>
                </div>
                <div className="summary-card">
                  <span>^SOX 收盘</span>
                  <strong>{data.snapshot.sox_close ?? '—'}</strong>
                </div>
                <div className="summary-card">
                  <span>^SOX 单日涨跌</span>
                  <strong>{data.snapshot.sox_change_pct ?? '—'}</strong>
                </div>
                <div className="summary-card">
                  <span>^VIX 收盘</span>
                  <strong>{data.snapshot.vix_close ?? '—'}</strong>
                </div>
              </>
            ) : (
              <p className="dim-text">{data.market_error || '暂无行情快照'}</p>
            )}
          </div>
          {data.research_rows && data.research_rows.length > 0 && (
            <section className="bill-section">
              <h3 className="section-title">研究市场背景</h3>
              <p className="dim-text">仅供研究观察，不参与当前自动交易信号。</p>
              <div className="table-wrap">
                <table className="report-table">
                  <thead>
                    <tr>
                      {['类别', '用途', '共同交易日', '标的', '收盘', '单日涨跌', '来源'].map((h) => (
                        <th key={h}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.research_rows.map((row, i) => (
                      <tr key={i}>
                        <td>{row['类别'] ?? ''}</td>
                        <td>{row['用途'] ?? ''}</td>
                        <td className="num-center">{row['共同交易日'] ?? ''}</td>
                        <td>{row['标的'] ?? ''}</td>
                        <td className="num-right">{row['收盘'] ?? ''}</td>
                        <td className="num-center">{row['单日涨跌'] ?? ''}</td>
                        <td>{row['来源'] ?? ''}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
          {data.news && data.news.length > 0 && (
            <section className="bill-section">
              <h3 className="section-title">
                美股新闻{data.news_ingested_at ? `（入库 ${data.news_ingested_at}）` : ''}
              </h3>
              <div className="table-wrap">
                <table className="report-table">
                  <thead>
                    <tr>
                      <th>标题</th>
                      <th>链接</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.news.map((n, i) => (
                      <tr key={i}>
                        <td>{n.title ?? n['标题'] ?? ''}</td>
                        <td>
                          {n.url ? (
                            <a className="inline-link" href={n.url} target="_blank" rel="noreferrer">
                              {n.url}
                            </a>
                          ) : (
                            (n['链接'] ?? '')
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
          <p className="notice-text">本页为单 ETF 日内账户的市场/新闻观察（与静态站 site build 同源）。</p>
        </>
      )}
      {data && data.kind === 'stock_watchlist' && (
        <>
          <div className="summary-cards">
            {(data.overview_cards ?? []).map((c) => (
              <div key={c.label} className="summary-card">
                <span>{c.label}</span>
                <strong>{c.value}</strong>
              </div>
            ))}
            {(data.account_summary_cards ?? []).map(([label, value]) => (
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
                  {(data.headers ?? []).map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(data.rows ?? []).map((row, i) => (
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
