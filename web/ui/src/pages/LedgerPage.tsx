import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { fetchLedger, type LedgerData } from '../api/accounts';

/** 完整交易台账：每日资产 / 成交明细 / 持仓快照 / 执行事件（移植自原静态站 ledger）。 */
export function LedgerPage() {
  const { accountId = '' } = useParams();
  const [data, setData] = useState<LedgerData | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    setData(null);
    setError('');
    fetchLedger(accountId)
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(`台账加载失败：${e}`));
    return () => {
      alive = false;
    };
  }, [accountId]);

  return (
    <div className="page-view">
      <div className="view-head">
        <h2 className="view-title">
          完整交易台账
          {data?.name && <span className="view-code">{data.name}</span>}
        </h2>
      </div>
      {error && <p className="error">{error}</p>}
      {!data && !error && <p className="dim-text">加载中……</p>}
      {data &&
        data.sections.map((s) => (
          <section key={s.title} className="bill-section">
            <h3 className="section-title">{s.title}</h3>
            <div className="table-wrap">
              <table className="report-table">
                <thead>
                  <tr>
                    {s.columns.map(([, label]) => (
                      <th key={label}>{label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {s.rows.length === 0 && (
                    <tr>
                      <td colSpan={s.columns.length}>暂无记录</td>
                    </tr>
                  )}
                  {s.rows.map((row, i) => (
                    <tr key={i}>
                      {s.columns.map(([key]) => (
                        <td key={key}>{row[key] ?? ''}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ))}
    </div>
  );
}
