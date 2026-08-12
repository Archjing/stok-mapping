"""Render the premarket observation page for the SOX/VIX semiconductor ETF account."""

from __future__ import annotations

import html
import shutil
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SEMICONDUCTOR_TIMING_STRATEGY_ID = "cross_market_semiconductor_timing_etf_v1"
SEMICONDUCTOR_TIMING_EXECUTION_MODEL = "single_etf_intraday"
SOX_SYMBOL = "^SOX"
VIX_SYMBOL = "^VIX"


def supports_semiconductor_timing_watchlist(account: Any) -> bool:
    return (
        str(getattr(account, "strategy_id", "")) == SEMICONDUCTOR_TIMING_STRATEGY_ID
        and str(getattr(account, "execution_model", "")) == SEMICONDUCTOR_TIMING_EXECUTION_MODEL
    )


def _resolve_path(root: Path, value: str, default: str) -> Path:
    path = Path(value or default)
    return path if path.is_absolute() else root / path


def _safe_table_name(value: object, default: str) -> str:
    table = str(value or default)
    if not table.replace("_", "").isalnum():
        raise ValueError(f"invalid SQLite table name: {table!r}")
    return table


def _load_market_snapshot(root: Path, config: dict[str, Any]) -> tuple[dict[str, str] | None, str]:
    history_cfg = config.get("us_market_history", {}) or {}
    db_path = _resolve_path(root, str(history_cfg.get("path", "")), "data/us_market_history.sqlite")
    if not db_path.is_file():
        return None, "美股历史库不存在，无法读取 SOX/VIX 行情。"
    try:
        table = _safe_table_name(history_cfg.get("daily_table"), "us_daily_bars")
        with sqlite3.connect(db_path) as conn:
            exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone()
            if not exists:
                return None, f"美股日线表 {table} 不存在。"
            row = conn.execute(
                f"""
                SELECT sox.date, sox.close, previous_sox.close, vix.close
                FROM {table} AS sox
                JOIN {table} AS vix
                  ON vix.date = sox.date AND vix.symbol = ? AND vix.close IS NOT NULL
                LEFT JOIN {table} AS previous_sox
                  ON previous_sox.symbol = ?
                 AND previous_sox.date = (
                    SELECT MAX(prior.date)
                    FROM {table} AS prior
                    WHERE prior.symbol = ? AND prior.date < sox.date AND prior.close IS NOT NULL
                 )
                WHERE sox.symbol = ? AND sox.close IS NOT NULL
                ORDER BY sox.date DESC
                LIMIT 1
                """,
                (VIX_SYMBOL, SOX_SYMBOL, SOX_SYMBOL, SOX_SYMBOL),
            ).fetchone()
    except sqlite3.Error as exc:
        return None, f"读取 SOX/VIX 行情失败：{exc}"
    except ValueError as exc:
        return None, str(exc)
    if row is None:
        return None, "SOX 与 VIX 没有共同的已完成交易日，无法生成当前信号观察。"
    date_value, sox_close, previous_sox_close, vix_close = row
    change_pct = None
    if previous_sox_close not in (None, 0):
        change_pct = (float(sox_close) / float(previous_sox_close) - 1.0) * 100.0
    return {
        "date": str(date_value),
        "sox_close": f"{float(sox_close):,.2f}",
        "sox_change_pct": "—" if change_pct is None else f"{change_pct:+.2f}%",
        "vix_close": f"{float(vix_close):.2f}",
    }, ""


def _safe_http_url(value: object) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    return url if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def _load_us_market_news(root: Path, config: dict[str, Any], *, limit: int = 10) -> tuple[list[dict[str, str]], str, str]:
    corpus_cfg = config.get("ai_corpus", {}) or {}
    db_path = _resolve_path(root, str(corpus_cfg.get("database_path", "")), "data/ai_corpus/ai_corpus.sqlite")
    if not db_path.is_file():
        return [], "", "AI Corpus 新闻库不存在。"
    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT provider, source, published_at, ingested_at, title, url
                FROM ai_corpus_documents
                WHERE corpus_type = ?
                ORDER BY published_at DESC, title
                LIMIT ?
                """,
                ("us_market_news", limit),
            ).fetchall()
    except sqlite3.Error as exc:
        return [], "", f"读取美股新闻失败：{exc}"
    if not rows:
        return [], "", "暂无可用美股新闻。"
    news = [
        {
            "source": str(source or provider or "未知来源"),
            "published_at": str(published_at or "—"),
            "ingested_at": str(ingested_at or ""),
            "title": str(title or "无标题"),
            "url": _safe_http_url(url),
        }
        for provider, source, published_at, ingested_at, title, url in rows
    ]
    freshest_ingested_at = max((row["ingested_at"] for row in news if row["ingested_at"]), default="")
    return news, freshest_ingested_at, ""


def _news_rows_html(news: list[dict[str, str]]) -> str:
    if not news:
        return '<tr><td colspan="4" class="empty">暂无可用新闻。</td></tr>'
    rows: list[str] = []
    for item in news:
        url = item["url"]
        link = (
            f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(url)}</a>'
            if url
            else "无可用链接"
        )
        rows.append(
            "<tr>"
            f"<td>{html.escape(item['source'])}</td>"
            f"<td>{html.escape(item['published_at'])}</td>"
            f"<td>{html.escape(item['title'])}</td>"
            f"<td>{link}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def write_semiconductor_timing_watchlist(*, root: Path, config: dict[str, Any], account: Any, target_dir: Path) -> None:
    """Write the account-specific market/news observation page for a supported account."""
    if not supports_semiconductor_timing_watchlist(account):
        raise ValueError("account does not use the semiconductor timing execution model")
    snapshot, market_error = _load_market_snapshot(root, config)
    news, latest_ingested_at, news_error = _load_us_market_news(root, config)
    account_name = str(getattr(account, "name", "半导体ETF美股情绪映射择时_v1"))
    title = f"{account_name}｜盘前观察池"
    if snapshot:
        market_html = f"""
        <div class="summary">
          <div class="metric"><span>共同交易日</span><strong>{html.escape(snapshot['date'])}</strong></div>
          <div class="metric"><span>^SOX 收盘</span><strong>{html.escape(snapshot['sox_close'])}</strong></div>
          <div class="metric"><span>^SOX 单日涨跌</span><strong>{html.escape(snapshot['sox_change_pct'])}</strong></div>
          <div class="metric"><span>^VIX 收盘</span><strong>{html.escape(snapshot['vix_close'])}</strong></div>
        </div>
        """
    else:
        market_html = f'<p class="empty">{html.escape(market_error)}</p>'
    news_status = f"最新入库时间：{latest_ingested_at}" if latest_ingested_at else news_error
    target_dir.mkdir(parents=True, exist_ok=True)
    css_source = Path(__file__).with_name("static") / "style.css"
    if css_source.is_file():
        shutil.copyfile(css_source, target_dir / "style.css")
    page = f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
<div class="theme-bar">
  <div class="theme-left"><a class="back-link" href="../../index.html"><span class="back-icon">&larr;</span><span>返回账户主页</span></a></div>
  <button class="theme-btn" id="themeToggle" title="切换配色" aria-label="切换配色"><span class="icon" id="themeIcon">☀️</span><span class="label-light">Belafonte Day</span><span class="label-dark">Belafonte Night</span></button>
</div>
<main class="page account-bill-page">
  <div class="title-row"><h1>{html.escape(title)}</h1></div>
  <section class="bill-section">
    <h2>SOX / VIX 已完成交易日行情</h2>
    {market_html}
    <p>当前执行信号：SOX &gt; 0.5% 且 VIX &lt; 19；SOX &gt; 1.0% 为强信号。</p>
  </section>
  <section class="bill-section">
    <h2>美股市场新闻</h2>
    <p>{html.escape(news_status)}</p>
    <p><strong>新闻仅供人工研判，不参与当前自动交易信号。</strong></p>
    <div class="table-wrap"><table class="watchlist-table"><thead><tr><th>来源</th><th>发布时间</th><th>标题</th><th>URL</th></tr></thead><tbody>
    {_news_rows_html(news)}
    </tbody></table></div>
  </section>
</main>
<script>
(function() {{
  var htmlRoot = document.documentElement, btn = document.getElementById('themeToggle'), icon = document.getElementById('themeIcon');
  var saved = localStorage.getItem('belafonte-theme');
  htmlRoot.setAttribute('data-theme', saved === 'dark' ? 'dark' : 'light');
  if (icon) icon.textContent = saved === 'dark' ? '🌙' : '☀️';
  if (btn) btn.addEventListener('click', function() {{
    var next = htmlRoot.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    htmlRoot.setAttribute('data-theme', next); localStorage.setItem('belafonte-theme', next);
    if (icon) icon.textContent = next === 'dark' ? '🌙' : '☀️';
  }});
}})();
</script>
</body>
</html>
"""
    (target_dir / "index.html").write_text(page, encoding="utf-8")
