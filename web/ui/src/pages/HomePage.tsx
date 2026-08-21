import { Link } from 'react-router-dom';

/** 功能卡：标题 + 简述 + 目标路由 + 图标。 */
const CARDS: Array<{ to: string; title: string; desc: string; icon: string }> = [
  {
    to: '/market/cn',
    title: 'A股单标的',
    desc: '上证指数 / 深证成指 / 沪深300 / 创业板指 / A股恐慌 · 单指数蜡烛图 + 个股搜索',
    icon: '📈',
  },
  {
    to: '/market/dash',
    title: 'A股对照看板',
    desc: '多标的归一化对照（窗口/首日/波动率/z-score）· 蜡烛/收盘/均线 · 支持个股搜索',
    icon: '📊',
  },
  {
    to: '/market/us',
    title: '美股单标的',
    desc: '纳斯达克 / 纽约指数 / VIX恐慌 / 费城半导体 · 单指数蜡烛图',
    icon: '🇺🇸',
  },
];

export function HomePage() {
  return (
    <div className="home">
      <section className="hero">
        <h1>stok-mapping 网站控制台</h1>
        <p>
          A股 / 美股 指数与个股走势 · 归一化对照看板
        </p>
        <p className="hero-sub">
          数据来自本地 SQLite，实时查询；盘后（15:05 起）每分钟自动刷新核心指数。
        </p>
      </section>

      <section className="cards">
        {CARDS.map((c) => (
          <Link key={c.to} to={c.to} className="card">
            <div className="card-icon">{c.icon}</div>
            <h2>{c.title}</h2>
            <p>{c.desc}</p>
            <span className="card-arrow">进入 →</span>
          </Link>
        ))}
      </section>

      <section className="home-meta">
        <small>
          提示：图表可滚轮缩放 / 拖拽平移 / 双击复位；个股搜索“近一年先行渲染 + 后台补全量”。
        </small>
      </section>
    </div>
  );
}
