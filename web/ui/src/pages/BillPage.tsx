import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { fetchBill, type BillData } from '../api/accounts';

/** 最新模拟交易账单：账户总览 / 每日资产 / 交易明细 / 持仓明细（移植自原静态站 account-bill）。 */
export function BillPage() {
  const { accountId = '' } = useParams();
  const [data, setData] = useState<BillData | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    setData(null);
    setError('');
    fetchBill(accountId)
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(`账单加载失败：${e}`));
    return () => {
      alive = false;
    };
  }, [accountId]);

  return (
    <div className="page-view">
      <div className="view-head">
        <h2 className="view-title">
          模拟交易账单
          {data?.name && <span className="view-code">{data.name}</span>}
        </h2>
      </div>
      {error && <p className="error">{error}</p>}
      {!data && !error && <p className="dim-text">加载中……</p>}
      {data && (
        <>
          {data.bill_date && (
            <div className="summary-cards">
              <div className="summary-card">
                <span>账单日</span>
                <strong>{data.bill_date}</strong>
              </div>
            </div>
          )}
          {data.tables.length === 0 && <p className="dim-text">该账户暂无已确认账单。</p>}
          {data.tables.map((t) => (
            <section key={t.title} className="bill-section">
              <h3 className="section-title">{t.title}</h3>
              <div className="table-wrap">
                <table className="report-table">
                  <thead>
                    <tr>
                      {t.columns.map(([, label]) => (
                        <th key={label}>{label}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {t.rows.length === 0 && (
                      <tr>
                        <td colSpan={t.columns.length}>暂无记录</td>
                      </tr>
                    )}
                    {t.rows.map((row, i) => (
                      <tr key={i}>
                        {t.columns.map(([key]) => (
                          <td key={key} className={key === 'side' ? 'num-center' : ''}>
                            {row[key] ?? ''}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ))}
        </>
      )}
    </div>
  );
}
