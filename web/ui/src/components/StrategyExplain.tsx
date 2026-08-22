import { useEffect, useState } from 'react';
import { fetchStrategy, type StrategyData } from '../api/accounts';

/** 账户执行的量化策略详细解释（原静态站账户主页"这套策略怎么交易"区）。 */
export function StrategyExplain({ accountId }: { accountId: string }) {
  const [data, setData] = useState<StrategyData | null>(null);

  useEffect(() => {
    let alive = true;
    fetchStrategy(accountId)
      .then((d) => alive && setData(d))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [accountId]);

  if (!data) return null;

  return (
    <section className="bill-section strategy-explain">
      <h3 className="section-title">策略说明 · {data.name}</h3>
      {data.note && <p className="dim-text">{data.note}</p>}
      {data.sections.map((s) => (
        <div key={s.heading}>
          <h4 className="strategy-heading">{s.heading}</h4>
          {s.paragraphs.map((p, i) => (
            <p key={i} className="strategy-body">
              {p}
            </p>
          ))}
        </div>
      ))}
      {data.research_example && (
        <div className="strategy-example">
          <h4 className="strategy-heading">历史研究示例（非模拟账户账单）</h4>
          <p className="strategy-body">
            区间：{data.research_example.period}。一次性独立研究回测，使用当前可执行规则：弱信号限价未触及即撤单、100
            份整手、佣金万分之 2.5（单笔最低 5 元）和 0.01% 滑点；5 分钟 K 线用于判断成交与卖出。站点构建不会重跑回测。
          </p>
          <div className="table-wrap">
            <table className="report-table">
              <thead>
                <tr>
                  {data.research_example.headers.map((h, i) => (
                    <th key={h} className={i > 0 ? 'num-right' : ''}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.research_example.rows.map((row, i) => (
                  <tr key={i}>
                    {row.map((cell, j) => (
                      <td key={j} className={j > 0 ? 'num-right' : ''}>
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="notice-text">{data.research_example.terms}</p>
        </div>
      )}
    </section>
  );
}
