from __future__ import annotations

import html
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from quant.reporting.account_bill import export_account_bill_html, format_money, format_num, format_pct
from quant.reporting.market_comparison_chart import (
    ComparisonChartConfig,
    ComparisonSeriesConfig,
    build_comparison_chart_data,
    render_comparison_chart_fragment,
)
from quant.reporting.paths import latest_dir, report_root, slug
from quant.reporting.semiconductor_timing_watchlist import (
    supports_semiconductor_timing_watchlist,
    write_semiconductor_timing_watchlist,
)
from quant.strategies import get_strategy


DEFAULT_QUANT_SITE_DIR = "static_site/quant"
DEFAULT_QUANT_REMOTE = "linuxuser@108.61.182.91"
DEFAULT_QUANT_REMOTE_DIR = "/var/www/share/quant/"
QUANT_SITE_SYNC_PASSWORD_ENV = "QUANT_SITE_SYNC_PASSWORD"
STATIC_ASSETS = ("style.css",)
KATEX_SOURCE_DIR = Path("/usr/local/texlive/2026/texmf-dist/doc/support/ketcindy/ketcindyjs/katex")
VIX_512480_RESEARCH_PATH = "research/vix-vs-512480/index.html"
SOX_512480_RESEARCH_PATH = "research/sox-vs-512480/index.html"
SOX_512480_COMPARISON_CONFIG = ComparisonChartConfig(
    slug="sox-vs-512480",
    title="^SOX 与半导体 ETF（512480）对照图",
    source=ComparisonSeriesConfig(
        symbol="^SOX",
        label="^SOX（费城半导体指数）",
        storage="us_daily_bars",
    ),
    target=ComparisonSeriesConfig(
        symbol="SH.512480",
        label="SH.512480 前复权收盘价（实际交易标的）",
        storage="etf_qfq",
    ),
    start_date=date(2025, 11, 3),
    observation_band=(8_000.0, 12_000.0),
    daily_mapping_pct=0.5,
    consecutive_days=3,
    consecutive_daily_change_pct=0.0,
)


def quant_site_root(*, root: Path, config: dict[str, Any] | None = None) -> Path:
    return report_root(root=root, config=config) / DEFAULT_QUANT_SITE_DIR


def _source_css_path() -> Path:
    return Path(__file__).with_name("static") / "style.css"


def _copy_katex_assets(*, assets_dir: Path) -> None:
    """Bundle the local KaTeX runtime so account-page formulas need no CDN."""
    required = ("katex.min.css", "katex.min.js")
    if not all((KATEX_SOURCE_DIR / name).is_file() for name in required):
        return
    destination = assets_dir / "katex"
    destination.mkdir(parents=True, exist_ok=True)
    for name in required:
        shutil.copyfile(KATEX_SOURCE_DIR / name, destination / name)
    fonts = KATEX_SOURCE_DIR / "fonts"
    if fonts.is_dir():
        shutil.copytree(fonts, destination / "fonts", dirs_exist_ok=True)


def _vix_512480_research_source_path() -> Path:
    return Path(__file__).with_name("static") / "research" / "vix-vs-512480.html"


def _write_vix_512480_research_page(*, site_root: Path) -> str:
    source_path = _vix_512480_research_source_path()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    chart_html = source_path.read_text(encoding="utf-8")
    destination = site_root / VIX_512480_RESEARCH_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="^VIX 与 A 股半导体 ETF 512480 的历史对照研究图。">
  <title>^VIX 与半导体 ETF（512480）对照图</title>
  <link rel="stylesheet" href="../../assets/style.css">
  <style>
    #vix-vs-512480 {{
      --foreground: var(--text);
      --muted-foreground: var(--text-muted);
      --viz-series-1: var(--accent);
      --viz-series-2: var(--focus-strong);
      --red: var(--red-text);
      --green: #4e8b57;
      --background: var(--bg);
      --popover: var(--bg-card);
      --popover-foreground: var(--text);
      --font-size-base: 12px;
    }}
    .research-chart-page {{ max-width: 1340px; }}
    .research-chart-page .research-meta {{ margin-bottom: 14px; }}
    .research-chart-page .research-meta strong {{ color: var(--text); }}
    @media (max-width: 680px) {{
      body {{ padding: 14px; }}
      .research-chart-page .vix-chart-legend {{ font-size: 11px; }}
      .research-chart-page .vix-tooltip {{ max-width: calc(100vw - 32px); white-space: normal; }}
    }}
  </style>
</head>
<body>
{_theme_bar_html(back_href="../../index.html")}<main class="page account-bill-page research-chart-page">
  <div class="title-row"><h1>^VIX 与半导体 ETF（512480）对照图</h1><span class="generated-at">静态研究快照</span></div>
  <p class="research-meta"><strong>数据区间：</strong>2025-11-03 至 2026-08-11。^VIX 使用日收盘，SH.512480 使用前复权日收盘；两者按首日归一化为 100。本图用于历史对照，不构成交易信号或投资建议。</p>
  <section class="bill-section">
{chart_html}
  </section>
</main>
{_theme_script_html()}
</body>
</html>
""",
        encoding="utf-8",
    )
    return VIX_512480_RESEARCH_PATH


def _write_market_comparison_research_page(
    *,
    site_root: Path,
    root: Path,
    config: ComparisonChartConfig,
    research_path: str,
    back_href: str = "../../index.html",
    stylesheet_href: str = "../../assets/style.css",
) -> str:
    """Write one reusable two-series market-comparison research page."""
    chart_data = build_comparison_chart_data(root=root, config=config)
    chart_html = render_comparison_chart_fragment(data=chart_data)
    destination = site_root / research_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{html.escape(config.title)}。">
  <title>{html.escape(config.title)}</title>
  <link rel="stylesheet" href="{html.escape(stylesheet_href)}">
  <style>
    #market-comparison {{
      --foreground: var(--text);
      --muted-foreground: var(--text-muted);
      --viz-series-1: var(--accent);
      --viz-series-2: var(--focus-strong);
      --red: var(--red-text);
      --green: #4e8b57;
      --background: var(--bg);
      --popover: var(--bg-card);
      --popover-foreground: var(--text);
      --font-size-base: 12px;
    }}
    .research-chart-page {{ max-width: 1340px; }}
    .research-chart-page .research-meta {{ margin-bottom: 14px; }}
    .research-chart-page .research-meta strong {{ color: var(--text); }}
    @media (max-width: 680px) {{
      body {{ padding: 14px; }}
      .research-chart-page .market-comparison-legend {{ font-size: 11px; }}
      .research-chart-page .market-comparison-tooltip {{ max-width: calc(100vw - 32px); white-space: normal; }}
    }}
  </style>
</head>
<body>
{_theme_bar_html(back_href=back_href)}<main class="page account-bill-page research-chart-page">
  <div class="title-row"><h1>{html.escape(config.title)}</h1><span class="generated-at">静态研究快照</span></div>
  <p class="research-meta">{_comparison_research_meta_html(chart_data)}</p>
  <section class="bill-section">
{chart_html}
  </section>
</main>
{_theme_script_html()}
</body>
</html>
""",
        encoding="utf-8",
    )
    return research_path


def _comparison_research_meta_html(chart_data: dict[str, Any] | None) -> str:
    if chart_data is None:
        return "本次构建未找到同时覆盖源序列与目标序列的本地历史数据；页面保留，但暂不展示图表。"
    return (
        f"<strong>数据区间：</strong>{chart_data['startDate']} 至 {chart_data['endDate']}。"
        f"{html.escape(str(chart_data['source']['label']))} 与 {html.escape(str(chart_data['target']['label']))}使用日收盘；"
        "仅保留双方均有收盘价的共同交易日，并按首日归一化为 100。"
        "本图用于历史对照，不构成交易信号或投资建议。"
    )


def _wiki_index_source(config: dict[str, Any]) -> Path | None:
    reporting_cfg = config.get("reporting", {}) if isinstance(config, dict) else {}
    raw_source = reporting_cfg.get("wiki_index_source")
    return Path(str(raw_source)) if raw_source else None


def _copy_wiki_index(*, site_root: Path, config: dict[str, Any]) -> str:
    source = _wiki_index_source(config)
    if source is None:
        return ""
    if not source.is_file():
        raise FileNotFoundError(f"wiki index source not found: {source}")
    wiki_dir = site_root / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    html_text = source.read_text(encoding="utf-8")
    html_text = html_text.replace('window.MARKLOGSEQ_DEFAULT_PAGE="cn_gdp"', 'window.MARKLOGSEQ_DEFAULT_PAGE="a_share_factor_overview"')
    html_text = html_text.replace('<details class="ng" open>', '<details class="ng">')
    html_text = html_text.replace("<details class='ng' open>", "<details class='ng'>")
    html_text = html_text.replace("<details open class=\"ng\">", '<details class="ng">')
    html_text = html_text.replace("<details open class='ng'>", "<details class='ng'>")
    if 'class="quant-wiki-back-link"' not in html_text:
        back_html = """<style>
.sb{display:flex;flex-direction:column;overflow:hidden}
.quant-wiki-back-wrap{flex:0 0 auto;padding:0 24px 10px;border-bottom:0;margin-bottom:8px}
.quant-wiki-back-link{display:inline-flex;align-items:center;gap:5px;padding:5px 8px;border:1px solid var(--bd);border-radius:5px;background:#f4efe6;color:var(--tx);text-decoration:none;font:600 12px/1.2 "Microsoft YaHei","PingFang SC",sans-serif}
.quant-wiki-back-link:hover{background:var(--ho);color:var(--tx);text-decoration:none}
.quant-wiki-nav-scroll{flex:1 1 auto;min-height:0;overflow-y:auto;padding-bottom:12px;scrollbar-width:none;-ms-overflow-style:none}
.quant-wiki-nav-scroll::-webkit-scrollbar{width:0;height:0}
@media(max-width:1100px){.sb{height:42vh;max-height:42vh;overflow:hidden}.quant-wiki-back-wrap{padding:10px 16px 8px;margin-bottom:0}.quant-wiki-nav-scroll{flex:1 1 auto;max-height:none;min-height:96px}}
</style>"""
        link_html = '<div class="quant-wiki-back-wrap"><a class="quant-wiki-back-link" href="../index.html"><span>&larr;</span><span>返回上一级</span></a></div>'
        if '<nav class="sb">' in html_text:
            html_text = html_text.replace('<nav class="sb">', f'{back_html}<nav class="sb">{link_html}', 1)
            top_link = 'class="nc ni topni">A股影响因子全景图</a>'
            if top_link in html_text and "</nav>" in html_text:
                html_text = html_text.replace(top_link, f'{top_link}\n<div class="quant-wiki-nav-scroll">', 1)
                nav_end = html_text.find("</nav>")
                html_text = html_text[:nav_end] + "</div>\n" + html_text[nav_end:]
        elif "<body>" in html_text:
            html_text = html_text.replace("<body>", f"<body>{back_html}{link_html}", 1)
        else:
            html_text = back_html + link_html + html_text
    (wiki_dir / "index.html").write_text(html_text, encoding="utf-8")
    return "wiki/index.html"


def _back_link_html(back_href: str) -> str:
    return f'<a class="back-link" href="{html.escape(back_href)}"><span class="back-icon">&larr;</span><span>返回上一级</span></a>'


def _theme_bar_html(*, back_href: str | None = None) -> str:
    back_link = f'<div class="theme-left">{_back_link_html(back_href)}</div>' if back_href else '<div class="theme-left"></div>'
    return """<div class="theme-bar">
  {back_link}
  <button class="theme-btn" id="themeToggle" title="切换配色" aria-label="切换配色">
    <span class="icon" id="themeIcon">☀️</span>
    <span class="label-light">Belafonte Day</span>
    <span class="label-dark">Belafonte Night</span>
  </button>
</div>
""".format(back_link=back_link)


def _with_back_link(html_text: str, *, back_href: str) -> str:
    if 'class="back-link"' in html_text:
        return html_text
    marker = '<div class="theme-bar">'
    if marker in html_text:
        return html_text.replace(marker, f'{marker}\n  <div class="theme-left">{_back_link_html(back_href)}</div>', 1)
    body_start = html_text.find("<body>")
    if body_start >= 0:
        insert_at = body_start + len("<body>")
        return html_text[:insert_at] + "\n" + _theme_bar_html(back_href=back_href) + html_text[insert_at:]
    return f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="style.css">
</head>
<body>
{_theme_bar_html(back_href=back_href)}<div class="page account-bill-page">
  <section class="bill-section">{html_text}</section>
</div>
{_theme_script_html()}
</body>
</html>
"""


def _theme_script_html() -> str:
    return """<script>
(function() {
  var STORAGE_KEY = 'belafonte-theme';
  var html = document.documentElement;
  var btn = document.getElementById('themeToggle');
  var icon = document.getElementById('themeIcon');
  var saved = localStorage.getItem(STORAGE_KEY);
  if (saved === 'dark') {
    html.setAttribute('data-theme', 'dark');
    if (icon) icon.textContent = '🌙';
  } else {
    html.setAttribute('data-theme', 'light');
    if (icon) icon.textContent = '☀️';
  }
  if (btn) {
    btn.addEventListener('click', function() {
      var next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      html.setAttribute('data-theme', next);
      localStorage.setItem(STORAGE_KEY, next);
      if (icon) icon.textContent = next === 'dark' ? '🌙' : '☀️';
    });
  }
})();
</script>
"""


def _placeholder_html(*, title: str, message: str, account_href: str = "../../index.html") -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="../../../../assets/style.css">
</head>
<body>
{_theme_bar_html(back_href=account_href)}<div class="page account-bill-page">
  <div class="title-row"><h1>{html.escape(title)}</h1></div>
  <section class="bill-section">
    <p class="empty">{html.escape(message)}</p>
    <p><a class="helper-link" href="{html.escape(account_href)}">返回账户主页</a><a class="helper-link" href="../../../../index.html">返回控制台首页</a></p>
  </section>
</div>
{_theme_script_html()}
</body>
</html>
"""


def _copy_bundle(source_dir: Path, target_dir: Path, *, back_href: str, missing_title: str, missing_message: str) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    if not (source_dir / "index.html").is_file():
        (target_dir / "index.html").write_text(
            _placeholder_html(title=missing_title, message=missing_message),
            encoding="utf-8",
        )
        return
    source_html = (source_dir / "index.html").read_text(encoding="utf-8")
    source_html = source_html.replace("watchlist.css", "style.css")
    (target_dir / "index.html").write_text(_with_back_link(source_html, back_href=back_href), encoding="utf-8")
    for asset_name in STATIC_ASSETS:
        asset = source_dir / asset_name
        if asset_name == "style.css" and _source_css_path().exists():
            asset = _source_css_path()
        if asset.exists():
            shutil.copyfile(asset, target_dir / asset_name)


def _latest_confirmed_bill_date_for_today(*, frames: dict[str, pd.DataFrame], today: str) -> str:
    assets = frames.get("assets", pd.DataFrame())
    if assets.empty or "brief_date" not in assets.columns:
        return ""
    dates = sorted(str(value) for value in assets["brief_date"].dropna().astype(str) if str(value) <= today)
    return dates[-1] if dates else ""


def _execution_price_status(*, root: Path, config: dict[str, Any], date_value: str) -> tuple[bool, str]:
    local_cfg = config.get("local_history", {}) if isinstance(config, dict) else {}
    db_path = Path(str(local_cfg.get("path", "data/a_share_history.sqlite")))
    if not db_path.is_absolute():
        db_path = root / db_path
    if not db_path.exists():
        return False, f"A 股本地历史库不存在，无法确认 {date_value} 执行价是否入库。"
    daily_table = str(local_cfg.get("daily_table", "market_daily_bars"))
    market = str(local_cfg.get("market", "CN"))
    adjust_type = str(local_cfg.get("execution_adjust_type", "bfq"))
    if not daily_table.replace("_", "").isalnum():
        return False, "A 股日线表名无效，无法检查执行价。"
    try:
        with sqlite3.connect(db_path) as conn:
            table_exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (daily_table,)).fetchone()
            if not table_exists:
                return False, f"A 股日线表 {daily_table} 不存在，无法检查执行价。"
            row = conn.execute(
                f"""
                SELECT COUNT(DISTINCT symbol) AS symbols
                FROM {daily_table}
                WHERE market = ?
                  AND adjust_type = ?
                  AND date = ?
                  AND open IS NOT NULL
                  AND close IS NOT NULL
                """,
                (market, adjust_type, date_value),
            ).fetchone()
    except sqlite3.Error as exc:
        return False, f"检查 {date_value} 执行价失败：{exc}"
    symbol_count = int(row[0] or 0) if row else 0
    if symbol_count <= 0:
        return False, f"{date_value} 的 {adjust_type} 执行价尚未入库。"
    return True, f"{date_value} 的 {adjust_type} 执行价已入库，覆盖股票数 {symbol_count}。"


def _write_latest_confirmed_account_bill(
    account: Any,
    target_dir: Path,
    *,
    root: Path,
    config: dict[str, Any],
    frames: dict[str, pd.DataFrame],
    today: str,
) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    if getattr(account, "execution_model", "") == "single_etf_intraday":
        # 单 ETF 账户从 single_etf_intraday_* 表渲染账单 (与通用账本渲染同模板同主题)
        from quant.reporting.account_bill import export_single_etf_account_bill

        latest_asset = frames["assets"].iloc[0]["brief_date"] if not frames["assets"].empty else ""
        bill_date = str(latest_asset or today)
        if latest_asset:
            try:
                export_single_etf_account_bill(
                    account=account,
                    brief_date=bill_date,
                    output_path=target_dir / "index.html",
                    status_message=f"当前展示最近已确认交易日 {bill_date} 的账单。",
                )
                index_path = target_dir / "index.html"
                index_path.write_text(
                    _with_back_link(index_path.read_text(encoding="utf-8"), back_href="../../index.html"),
                    encoding="utf-8",
                )
                return
            except Exception:
                pass
        (target_dir / "index.html").write_text(
            _placeholder_html(
                title="暂无最新模拟交易账单",
                message="模拟账户还没有当日账单。请先运行 intraday_bill_pipeline 执行盘中回放。",
            ),
            encoding="utf-8",
        )
        return
    latest_bill_date = _latest_confirmed_bill_date_for_today(frames=frames, today=today)
    if not latest_bill_date:
        (target_dir / "index.html").write_text(
            _placeholder_html(
                title="暂无最新模拟交易账单",
                message="模拟账户还没有已确认账单。请先生成包含执行价的模拟账户账本。",
            ),
            encoding="utf-8",
        )
        return
    execution_price_ready, execution_price_note = _execution_price_status(root=root, config=config, date_value=today)
    if latest_bill_date == today:
        status_message = f"{today} 执行价已入库，当前展示 {today} 已确认模拟交易账单。"
    elif execution_price_ready:
        status_message = (
            f"{execution_price_note} 但账户账本尚未生成 {today} 的确认记录，"
            f"当前展示最近已确认交易日 {latest_bill_date} 的账单。"
        )
    else:
        status_message = f"{execution_price_note} 当前展示最近已确认交易日 {latest_bill_date} 的账单。"
    export_account_bill_html(
        account=account,
        brief_date=latest_bill_date,
        output_path=target_dir / "index.html",
        status_message=status_message,
    )
    index_path = target_dir / "index.html"
    index_path.write_text(_with_back_link(index_path.read_text(encoding="utf-8"), back_href="../../index.html"), encoding="utf-8")


def _read_account_frames(account: Any) -> dict[str, pd.DataFrame]:
    empty = {
        "assets": pd.DataFrame(),
        "trades": pd.DataFrame(),
        "positions": pd.DataFrame(),
        "order_events": pd.DataFrame(),
    }
    db_path = Path(account.database_path)
    if not db_path.exists():
        return empty
    try:
        from quant.execution.accounts import ensure_account_tables

        with sqlite3.connect(db_path) as conn:
            ensure_account_tables(conn)
            # 单 ETF 日内账户: 执行数据在 single_etf_intraday_* 表, 映射列名到通用账本语义
            if getattr(account, "execution_model", "") == "single_etf_intraday":
                from quant.execution.single_etf_intraday import ensure_single_etf_intraday_tables

                ensure_single_etf_intraday_tables(conn)
                frames = {
                    "assets": pd.read_sql_query(
                        "SELECT trade_date AS brief_date, trade_date AS start_date, "
                        "total_asset, stock_asset, cash_asset, "
                        "0.0 AS daily_pnl, daily_return, "
                        "exposure AS target_exposure, 0.0 AS estimated_trade_amount, "
                        "0 AS unfilled_orders, '' AS block_reason_counts "
                        "FROM single_etf_intraday_daily_assets "
                        "WHERE account_id = ? ORDER BY trade_date DESC",
                        conn,
                        params=(account.account_id,),
                    ),
                    "trades": pd.read_sql_query(
                        "SELECT trade_date AS brief_date, signal_date, symbol, symbol AS name, "
                        "side, order_type, reason, trade_time, price, shares, amount, cost, "
                        "shares / 100.0 AS lots, '全部成交' AS trade_status, reason AS block_reasons "
                        "FROM single_etf_intraday_trades "
                        "WHERE account_id = ? ORDER BY trade_date DESC, side, trade_time",
                        conn,
                        params=(account.account_id,),
                    ),
                    "positions": pd.DataFrame(columns=["brief_date", "symbol", "shares", "entry_price"]),
                    "order_events": pd.read_sql_query(
                        "SELECT trade_date AS brief_date, signal_date, symbol, symbol AS name, "
                        "side, order_type AS event_type, 0.0 AS target_weight, "
                        "requested_shares, filled_shares, status AS trade_status, reason "
                        "FROM single_etf_intraday_order_events "
                        "WHERE account_id = ? ORDER BY trade_date DESC",
                        conn,
                        params=(account.account_id,),
                    ),
                }
                return frames
            frames = {
                "assets": pd.read_sql_query(
                    "SELECT * FROM account_daily_assets WHERE account_id = ? ORDER BY brief_date DESC",
                    conn,
                    params=(account.account_id,),
                ),
                "trades": pd.read_sql_query(
                    "SELECT * FROM account_trades WHERE account_id = ? ORDER BY brief_date DESC, side, symbol",
                    conn,
                    params=(account.account_id,),
                ),
                "positions": pd.read_sql_query(
                    "SELECT * FROM account_positions WHERE account_id = ? ORDER BY brief_date DESC, symbol",
                    conn,
                    params=(account.account_id,),
                ),
            }
            has_order_events = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='account_order_events'"
            ).fetchone()
            frames["order_events"] = (
                pd.read_sql_query(
                    "SELECT * FROM account_order_events WHERE account_id = ? ORDER BY brief_date DESC, symbol",
                    conn,
                    params=(account.account_id,),
                )
                if has_order_events
                else pd.DataFrame()
            )
            return frames
    except sqlite3.Error:
        return empty


def _latest_value(df: pd.DataFrame, column: str) -> str:
    if df.empty or column not in df.columns:
        return ""
    value = df.iloc[0].get(column, "")
    return "" if pd.isna(value) else str(value)


def _fmt_cell(column: str, value: Any) -> str:
    if pd.isna(value):
        return ""
    if column == "side":
        labels = {"buy": "买入", "sell": "卖出"}
        return labels.get(str(value).strip().lower(), str(value))
    if column == "event_type":
        labels = {"unfilled": "未成交", "partial_fill": "部分成交"}
        return labels.get(str(value).strip().lower(), str(value))
    if column in {"total_asset", "stock_asset", "cash_asset", "daily_pnl", "estimated_trade_amount", "amount", "cost", "price", "close", "market_value"}:
        return format_money(value)
    if column in {"daily_return", "target_exposure", "weight_before", "weight_after", "weight_change", "target_weight", "max_participation_rate"}:
        return format_pct(value)
    if column in {"estimated_volume", "shares", "lots", "raw_shares", "requested_shares", "filled_shares"}:
        return format_num(value, 2)
    return str(value)


def _recent_bill_dates(*frames: pd.DataFrame, limit: int) -> set[str]:
    dates: set[str] = set()
    for frame in frames:
        if frame.empty or "brief_date" not in frame.columns:
            continue
        dates.update(str(value) for value in frame["brief_date"].dropna().astype(str) if str(value))
    return set(sorted(dates)[-limit:])


def _filter_bill_dates(df: pd.DataFrame, dates: set[str]) -> pd.DataFrame:
    if df.empty or "brief_date" not in df.columns or not dates:
        return df.iloc[0:0].copy()
    return df[df["brief_date"].astype(str).isin(dates)].copy()


def _table_html(df: pd.DataFrame, columns: list[tuple[str, str]], empty_text: str, *, wrap_class: str = "table-wrap") -> str:
    if df.empty:
        return f'<p class="empty">{html.escape(empty_text)}</p>'
    header = "".join(f"<th>{html.escape(label)}</th>" for _col, label in columns)
    rows: list[str] = []
    for _, row in df.iterrows():
        cells = "".join(f"<td>{html.escape(_fmt_cell(col, row.get(col, '')))}</td>" for col, _label in columns)
        rows.append(f"<tr>{cells}</tr>")
    return f'<div class="{html.escape(wrap_class)}"><table class="report-table account-bill-table"><thead><tr>{header}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def _ledger_html(*, account: Any, frames: dict[str, pd.DataFrame], generated_at: str) -> str:
    assets = frames["assets"].copy()
    trades = frames["trades"].copy()
    positions = frames["positions"].copy()
    order_events = frames["order_events"].copy()
    recent_dates = _recent_bill_dates(assets, positions, order_events, limit=3)
    recent_positions = _filter_bill_dates(positions, recent_dates)
    recent_order_events = _filter_bill_dates(order_events, recent_dates)
    title = f"{account.name} 完整交易台账"
    sections = [
        (
            "每日资产（全部账单日）",
            _table_html(
                assets,
                [
                    ("brief_date", "账单日"),
                    ("total_asset", "总资产"),
                    ("stock_asset", "股票资产"),
                    ("cash_asset", "现金资产"),
                    ("daily_pnl", "当日收益"),
                    ("daily_return", "当日收益率"),
                    ("target_exposure", "仓位"),
                    ("estimated_trade_amount", "成交金额"),
                    ("unfilled_orders", "未成交数"),
                    ("block_reason_counts", "拦截原因"),
                ],
                "暂无资产记录",
                wrap_class="table-wrap asset-history-wrap",
            ),
        ),
        (
            "成交明细（全部历史成交）",
            _table_html(
                trades,
                [
                    ("brief_date", "账单日"),
                    ("symbol", "股票代码"),
                    ("name", "股票名称"),
                    ("side", "方向"),
                    ("trade_time", "成交时间"),
                    ("price", "价格"),
                    ("amount", "金额"),
                    ("shares", "股数"),
                    ("lots", "手数"),
                    ("trade_status", "成交状态"),
                    ("block_reasons", "说明"),
                ],
                "暂无成交记录",
                wrap_class="table-wrap trade-history-wrap",
            ),
        ),
        (
            "持仓快照（最近3个账单日）",
            _table_html(
                recent_positions,
                [
                    ("brief_date", "账单日"),
                    ("symbol", "股票代码"),
                    ("name", "股票名称"),
                    ("close", "收盘价"),
                    ("target_weight", "权重"),
                    ("market_value", "市值"),
                    ("shares", "股数"),
                    ("lots", "手数"),
                ],
                "暂无持仓记录",
                wrap_class="table-wrap position-history-wrap",
            ),
        ),
        (
            "执行事件（最近3个账单日）",
            _table_html(
                recent_order_events,
                [
                    ("brief_date", "账单日"),
                    ("symbol", "股票代码"),
                    ("name", "股票名称"),
                    ("side", "方向"),
                    ("event_type", "事件类型"),
                    ("target_weight", "目标权重"),
                    ("requested_shares", "计划股数"),
                    ("filled_shares", "成交股数"),
                    ("trade_status", "状态"),
                    ("block_reasons", "原因"),
                ],
                "暂无逐笔未成交事件",
            ),
        ),
    ]
    section_html = "".join(f"<section class=\"bill-section\"><h2>{html.escape(name)}</h2>{body}</section>" for name, body in sections)
    return f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="../../../assets/style.css">
</head>
<body>
{_theme_bar_html(back_href="../index.html")}<div class="page account-bill-page">
  <div class="title-row">
    <h1>完整交易台账</h1>
    <span class="generated-at">生成时间：{html.escape(generated_at)}</span>
  </div>
  <p class="bill-meta">账户：{html.escape(str(account.name))} ｜ 最近账单日：{html.escape(_latest_value(assets, "brief_date") or "暂无")}</p>
  <p><a class="helper-link" href="../latest/watchlist/index.html">最新观察池</a><a class="helper-link" href="../latest/account-bill/index.html">最新账单</a><a class="helper-link" href="../index.html">账户主页</a></p>
  {section_html}
  <div class="notice"><strong>说明：</strong>本页为模拟账户静态台账，覆盖资产、成交、持仓和逐笔执行事件。执行事件来自 account_order_events，用于解释未成交和部分成交原因。</div>
</div>
{_theme_script_html()}
</body>
</html>
"""


def _account_index_html(
    *,
    account: Any,
    meta: dict[str, str],
    generated_at: str,
    mapping_chart_links: list[dict[str, str]] | tuple[dict[str, str], ...] = (),
    strategy_cfg: dict[str, Any] | None = None,
) -> str:
    mapping_links_html = "\n      ".join(
        f'<a class="quick-card" href="{html.escape(item["href"])}"><span>{html.escape(item["kicker"])}</span><strong>{html.escape(item["label"])}</strong></a>'
        for item in mapping_chart_links
    )
    strategy_html = _mapping_strategy_home_html(
        account=account,
        strategy_cfg=strategy_cfg or {},
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(str(account.name))} 模拟账户</title>
  <link rel="stylesheet" href="../../assets/style.css">
  <link rel="stylesheet" href="../../assets/katex/katex.min.css">
</head>
<body>
{_theme_bar_html(back_href="../../index.html")}<div class="page account-bill-page">
  <div class="title-row"><h1>{html.escape(str(account.name))}</h1><span class="generated-at">生成时间：{html.escape(generated_at)}</span></div>
  <div class="summary">
    <div><span>账户 ID</span><strong>{html.escape(str(account.account_id))}</strong></div>
    <div><span>最新账单日</span><strong>{html.escape(meta.get("latest_bill_date") or "暂无")}</strong></div>
    <div><span>总资产</span><strong>{html.escape(meta.get("total_asset") or "暂无")}</strong></div>
    <div><span>现金资产</span><strong>{html.escape(meta.get("cash_asset") or "暂无")}</strong></div>
    <div><span>股票资产</span><strong>{html.escape(meta.get("stock_asset") or "暂无")}</strong></div>
    <div><span>当前仓位</span><strong>{html.escape(meta.get("target_exposure") or "暂无")}</strong></div>
  </div>
  <section class="bill-section quick-section"><h2>快捷入口</h2>
    <div class="quick-links">
      <a class="quick-card" href="latest/watchlist/index.html"><span>WATCHLIST</span><strong>最新盘前观察池</strong></a>
      <a class="quick-card" href="latest/account-bill/index.html"><span>BILL</span><strong>最新模拟交易账单</strong></a>
      <a class="quick-card" href="ledger/index.html"><span>LEDGER</span><strong>完整交易台账</strong></a>
      {mapping_links_html}
      <a class="quick-card" href="../../index.html"><span>CONSOLE</span><strong>控制台首页</strong></a>
    </div>
  </section>
{strategy_html}
</div>
<script defer src="../../assets/katex/katex.min.js"></script>
<script>
window.addEventListener("DOMContentLoaded", function () {{
  if (!window.katex) return;
  document.querySelectorAll("[data-katex]").forEach(function (element) {{
    window.katex.render(element.dataset.katex, element, {{ throwOnError: false }});
  }});
}});
</script>
{_theme_script_html()}
</body>
</html>
"""


def _mapping_strategy_home_html(
    *, account: Any, strategy_cfg: dict[str, Any]
) -> str:
    if str(getattr(account, "strategy_id", "")) != "cross_market_semiconductor_timing_etf_v1":
        return ""
    base = dict(strategy_cfg.get("cross_market_semiconductor_timing", {}) or {})
    base.update(dict(getattr(account, "strategy_params", {}) or {}))
    target = str(base.get("target_symbol", "SH.512480"))
    is_scheduled_close = target == "SH.588200"
    vix = 20 if is_scheduled_close else 19
    target_name = "科创芯片ETF（588200）" if is_scheduled_close else "国联安半导体ETF（512480）"
    exit_rule = "不设盘中追踪止损，在 T+1 日 14:55 清仓。" if is_scheduled_close else "从日内高点回落 2% 时卖出；未触发则 14:55 清仓。"
    discount = float(base.get("limit_order_discount", 0.012))
    sox_return_formula = r"r_{\mathrm{SOX}} = \frac{\mathrm{SOX}_{\mathrm{close}}(D)}{\mathrm{SOX}_{\mathrm{close}}(D-1)} - 1"
    research_example_html = _strategy_research_example_html(target=target)
    return f"""
  <section class="bill-section strategy-explanation"><h2>这套策略怎么交易</h2>
    <p class="strategy-body">它用上一交易日美股费城半导体指数（^SOX）的涨跌和恐慌指数（^VIX）筛选次日 A 股的 <strong>{target_name}（{html.escape(target)}）</strong>。美股收盘后，信号在下一次 A 股开盘时才可执行。</p>
    <p class="strategy-body"><strong>开仓条件：</strong><span class="strategy-formula" data-katex="{html.escape(sox_return_formula, quote=True)}">r_SOX = SOX_close(D) / SOX_close(D−1) − 1</span>；当 <code>r_SOX &gt; 0.5%</code> 且 <code>VIX &lt; {vix}</code> 时才考虑买入。SOX 涨幅超过 1% 是强信号，按开盘价买入，目标仓位 60%；0.5% 至 1% 是弱信号，按 <code>开盘价 × (1 − {discount:.1%})</code> 挂限价单，目标仓位 50%。</p>
    <p class="strategy-body"><strong>弱信号未成交：</strong>当天价格没有触及限价就撤单，不追价；因此不会使用当天未来价格来决定成交。</p>
    <p class="strategy-body"><strong>卖出规则：</strong>{exit_rule} 买入后遵守 ETF 的 T+1 规则，不留隔夜仓位。</p>
    <p class="strategy-body"><strong>交易口径：</strong>使用 5 分钟 K 线判断限价成交和盘中止损；按 100 份整手、账户佣金、最低佣金与滑点计算。回测和模拟账户采用同一套撮合规则。</p>
    <p class="strategy-body"><strong>跨市场映射风险：</strong>SOX 上涨不等于 A 股半导体 ETF 必然上涨。汇率、国内政策、行业供需、开盘跳空和流动性都可能使映射失效；策略结果不构成收益承诺或投资建议。</p>
    {research_example_html}
  </section>"""


def _strategy_research_example_html(*, target: str) -> str:
    """Render fixed, independently generated research results; builds do not replay."""
    if target == "SH.588200":
        period = "2022-10-26 至 2026-08-07"
        rows = (
            ("策略：SOX + VIX 映射择时", "+53.1%", "+12.4%", "0.77", "-14.8%", "26.0%", "+204.2%"),
            ("SH.588200 买入持有", "+256.6%", "+40.4%", "1.00", "-48.1%", "100.0%", "+256.6%"),
            ("沪深 300 买入持有", "+28.4%", "+7.1%", "0.48", "-24.8%", "100.0%", "+28.4%"),
        )
    else:
        period = "2021-05-13 至 2026-08-07"
        rows = (
            ("策略：SOX + VIX 映射择时", "+67.5%", "+10.8%", "0.87", "-13.6%", "23.0%", "+293.6%"),
            ("SH.512480 买入持有", "+129.0%", "+17.5%", "0.62", "-62.5%", "100.0%", "+129.0%"),
            ("沪深 300 买入持有", "-6.0%", "-1.2%", "0.02", "-40.9%", "100.0%", "-6.0%"),
        )
    table_rows = "".join(
        "<tr>" + "".join(f"<td>{html.escape(value)}</td>" for value in row) + "</tr>" for row in rows
    )
    return f"""<section class="strategy-example"><h3>历史研究示例（非模拟账户账单）</h3>
      <p class="strategy-body">区间：{period}。一次性独立研究回测，使用当前可执行规则：弱信号限价未触及即撤单、100 份整手、佣金万分之 2.5（单笔最低 5 元）和 0.01% 滑点；5 分钟 K 线用于判断成交与卖出。站点构建不会重跑回测。</p>
      <div class="table-wrap"><table class="report-table"><thead><tr><th>对象</th><th>总收益</th><th>年化收益率</th><th>夏普比率</th><th>最大回撤</th><th>平均资金占用</th><th>已投入资本回报率</th></tr></thead><tbody>{table_rows}</tbody></table></div>
      <p class="strategy-terms">总收益和年化收益率均以账户总资产为分母。平均资金占用是每日目标仓位的平均值，也可理解为资金利用率；已投入资本回报率 = 总收益 ÷ 平均资金占用，用于观察策略在实际占用资金上的回报。夏普比率衡量单位波动对应的历史收益；最大回撤是历史峰值至谷底的最大跌幅。历史研究结果不代表当前模拟账户业绩，也不构成未来收益承诺。</p>
    </section>"""


def _site_index_html(*, accounts_meta: list[dict[str, str]], generated_at: str, wiki_path: str) -> str:
    rows = []
    for item in accounts_meta:
        rows.append(
            "<tr>"
            f"<td>{html.escape(item['account_id'])}</td>"
            f"<td><a href=\"{html.escape(item['account_path'])}\">{html.escape(item['name'])}</a></td>"
            f"<td>{html.escape(item.get('latest_bill_date') or '暂无')}</td>"
            f"<td>{html.escape(item.get('position_start_date') or '暂无')}</td>"
            f"<td>{html.escape(item.get('total_asset') or '暂无')}</td>"
            f"<td>{html.escape(item.get('target_exposure') or '暂无')}</td>"
            f"<td><a href=\"{html.escape(item['account_path'])}\">账户</a> ｜ <a href=\"{html.escape(item['watchlist_path'])}\">观察池</a> ｜ <a href=\"{html.escape(item['account_bill_path'])}\">账单</a> ｜ <a href=\"{html.escape(item['ledger_path'])}\">台账</a></td>"
            "</tr>"
        )
    rows_html = "".join(rows) if rows else '<tr><td colspan="7">暂无启用的模拟账户</td></tr>'
    wiki_link = '<a class="quick-card" href="wiki/index.html"><span>WIKI</span><strong>A股影响因子全景图</strong></a>' if wiki_path else ""
    research_link = """<a class="quick-card" href="research/vix-vs-512480/index.html"><span>RESEARCH</span><strong>VIX 与半导体 ETF 对照图</strong></a>
      <a class="quick-card" href="research/sox-vs-512480/index.html"><span>RESEARCH</span><strong>SOX 与半导体 ETF 对照图</strong></a>"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>量化模拟账户控制台</title>
  <link rel="stylesheet" href="assets/style.css">
</head>
<body>
{_theme_bar_html(back_href="index.html")}<div class="page account-bill-page">
  <div class="title-row"><h1>量化模拟账户控制台</h1><span class="generated-at">生成时间：{html.escape(generated_at)}</span></div>
  <p class="bill-meta">入口：/quant/ ｜ 每日简报入口：/quant/brief/。</p>
  <section class="bill-section quick-section"><h2>核心入口</h2>
    <div class="quick-links">
      <a class="quick-card" href="brief/index.html"><span>BRIEF</span><strong>每日简报</strong></a>
      {wiki_link}
      {research_link}
    </div>
  </section>
  <section class="bill-section"><div class="section-title-frame"><h2>账户总览</h2></div>
    <div class="table-wrap"><table class="report-table account-bill-table">
      <thead><tr><th>账户 ID</th><th>账户名称</th><th>最新账单日</th><th>建仓日</th><th>总资产</th><th>仓位</th><th>入口</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table></div>
  </section>
  <div class="notice"><strong>说明：</strong>本控制台只发布静态 HTML/CSS/JSON/CSV，不上传 SQLite。每个模拟账户独立展示观察池、账单与完整台账。</div>
</div>
{_theme_script_html()}
</body>
</html>
"""


def _brief_index_html(*, accounts_meta: list[dict[str, str]], generated_at: str, wiki_path: str) -> str:
    latest_bill_dates = sorted(item.get("latest_bill_date", "") for item in accounts_meta if item.get("latest_bill_date"))
    latest_bill_date = latest_bill_dates[-1] if latest_bill_dates else "暂无"
    account_count = len(accounts_meta)
    ready_accounts = sum(1 for item in accounts_meta if item.get("latest_bill_date"))
    rows = []
    for item in accounts_meta:
        rows.append(
            "<tr>"
            f"<td>{html.escape(item['account_id'])}</td>"
            f"<td>{html.escape(item['name'])}</td>"
            f"<td>{html.escape(item.get('latest_bill_date') or '暂无')}</td>"
            f"<td>{html.escape(item.get('total_asset') or '暂无')}</td>"
            f"<td>{html.escape(item.get('target_exposure') or '暂无')}</td>"
            f"<td><a href=\"/quant/{html.escape(item['watchlist_path'])}\">观察池</a> ｜ "
            f"<a href=\"/quant/{html.escape(item['account_bill_path'])}\">账单</a> ｜ "
            f"<a href=\"/quant/{html.escape(item['ledger_path'])}\">台账</a></td>"
            "</tr>"
        )
    rows_html = "".join(rows) if rows else '<tr><td colspan="6">暂无启用的模拟账户</td></tr>'
    readiness = "ready" if account_count and ready_accounts == account_count else "warning"
    readiness_text = "全部启用账户已有确认账单" if readiness == "ready" else "部分账户暂无确认账单，简报只展示可用证据"
    wiki_link = '<a class="helper-link" href="/quant/wiki/index.html">A股影响因子全景图</a>' if wiki_path else ""
    return f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>量化每日简报</title>
  <link rel="stylesheet" href="../assets/style.css">
  <link rel="stylesheet" href="/quant/assets/style.css">
</head>
<body>
{_theme_bar_html(back_href="/quant/index.html")}<div class="page account-bill-page brief-page">
  <div class="title-row"><h1>量化每日简报</h1><span class="generated-at">生成时间：{html.escape(generated_at)}</span></div>
  <section class="brief-hero">
    <div>
      <span class="brief-kicker">DAILY BRIEF</span>
      <h2>账户、观察池与证据入口</h2>
      <p>本页汇总当前启用模拟账户的最新确认账单、盘前观察池、完整交易台账和知识入口。页面不直接生成交易信号，也不替代 strategy-admission 或人工复核。</p>
    </div>
    <div class="brief-status {html.escape(readiness)}">{html.escape(readiness_text)}</div>
  </section>
  <div class="summary brief-summary">
    <div><span>启用账户</span><strong>{account_count}</strong></div>
    <div><span>有确认账单账户</span><strong>{ready_accounts}</strong></div>
    <div><span>最新确认账单日</span><strong>{html.escape(latest_bill_date)}</strong></div>
    <div><span>简报边界</span><strong>研究辅助</strong></div>
  </div>
  <section class="bill-section brief-grid">
    <article class="brief-card">
      <h2>盘前复核顺序</h2>
      <ol>
        <li>先确认数据和账单日期是否符合预期。</li>
        <li>再查看各账户观察池与目标仓位变化。</li>
        <li>最后进入账单和台账核对成交、未成交与持仓。</li>
      </ol>
    </article>
    <article class="brief-card">
      <h2>执行边界</h2>
      <p>未通过正式准入的策略只能作为 research-only 或观察池解释材料；模拟账单只展示本地执行价已确认后的记录。</p>
    </article>
    <article class="brief-card">
      <h2>下钻入口</h2>
      <p><a class="helper-link" href="/quant/index.html">控制台首页</a>{wiki_link}</p>
    </article>
  </section>
  <section class="bill-section"><div class="section-title-frame"><h2>账户简报</h2></div>
    <div class="table-wrap"><table class="report-table account-bill-table">
      <thead><tr><th>账户 ID</th><th>账户名称</th><th>最新账单日</th><th>总资产</th><th>仓位</th><th>证据链接</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table></div>
  </section>
  <div class="notice"><strong>说明：</strong>本页由静态站点构建器生成，发布路径为 <code>/quant/brief/index.html</code>。它只聚合已有本地证据，不上传 SQLite，不生成新的买卖建议。</div>
</div>
{_theme_script_html()}
</body>
</html>
"""


def _write_csvs(account_dir: Path, frames: dict[str, pd.DataFrame]) -> None:
    dates = sorted(set(frames["assets"].get("brief_date", pd.Series(dtype=str)).astype(str)))
    for date_value in dates:
        date_dir = account_dir / "dates" / date_value
        date_dir.mkdir(parents=True, exist_ok=True)
        for key, filename in [
            ("assets", "daily-assets.csv"),
            ("trades", "trades.csv"),
            ("positions", "positions.csv"),
        ]:
            df = frames[key]
            day = df[df["brief_date"].astype(str) == date_value] if not df.empty and "brief_date" in df.columns else pd.DataFrame()
            day.to_csv(date_dir / filename, index=False, encoding="utf-8-sig")


def _meta_for_account(account: Any, frames: dict[str, pd.DataFrame]) -> dict[str, str]:
    assets = frames["assets"]
    latest = assets.iloc[0] if not assets.empty else {}
    latest_bill_date = "" if assets.empty else str(latest.get("brief_date", ""))
    position_start_date = str(getattr(account, "simulation_start_date", "") or "")
    if assets.empty:
        try:
            initial_cash = float(getattr(account, "initial_cash"))
        except (TypeError, ValueError):
            initial_cash = None
        if initial_cash is not None and initial_cash >= 0:
            total_asset = format_money(initial_cash)
            cash_asset = format_money(initial_cash)
            stock_asset = format_money(0.0)
            target_exposure = format_pct(0.0)
        else:
            total_asset = ""
            cash_asset = ""
            stock_asset = ""
            target_exposure = ""
    else:
        total_asset = format_money(latest.get("total_asset"))
        cash_asset = format_money(latest.get("cash_asset"))
        stock_asset = format_money(latest.get("stock_asset"))
        target_exposure = format_pct(latest.get("target_exposure"))
    return {
        "account_id": str(account.account_id),
        "name": str(account.name),
        "latest_bill_date": latest_bill_date,
        "position_start_date": position_start_date,
        "total_asset": total_asset,
        "cash_asset": cash_asset,
        "stock_asset": stock_asset,
        "target_exposure": target_exposure,
    }


def build_quant_static_site(*, root: Path, config: dict[str, Any], accounts: list[Any]) -> dict[str, Any]:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    today = datetime.now().date().isoformat()
    site_root = quant_site_root(root=root, config=config)
    if site_root.exists():
        shutil.rmtree(site_root)
    site_root.mkdir(parents=True, exist_ok=True)

    assets_dir = site_root / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    source_css = _source_css_path()
    if source_css.exists():
        shutil.copyfile(source_css, assets_dir / "style.css")
    _copy_katex_assets(assets_dir=assets_dir)

    accounts_meta: list[dict[str, str]] = []
    global_strategy_cfg = dict(config.get("walk_forward", {}).get("strategy_v2", {}) or {})
    for account in accounts:
        account_slug = slug(str(account.account_id))
        account_dir = site_root / "accounts" / account_slug
        account_dir.mkdir(parents=True, exist_ok=True)
        latest_account_dir = latest_dir(root=root, config=config, channel="accounts") / account_slug
        latest_watchlist_dir = latest_account_dir / "watchlist"
        latest_bill_dir = latest_account_dir / "account_bill"
        frames = _read_account_frames(account)
        meta = _meta_for_account(account, frames)
        meta.update(
            {
                "account_path": f"accounts/{account_slug}/index.html",
                "watchlist_path": f"accounts/{account_slug}/latest/watchlist/index.html",
                "account_bill_path": f"accounts/{account_slug}/latest/account-bill/index.html",
                "ledger_path": f"accounts/{account_slug}/ledger/index.html",
            }
        )
        accounts_meta.append(meta)
        mapping_chart_links: list[dict[str, str]] = []
        mapping_chart_paths: list[str] = []
        mapping_charts = []
        strategy_id = str(getattr(account, "strategy_id", "") or "")
        if strategy_id:
            try:
                strategy = get_strategy(strategy_id)
            except KeyError:
                strategy = None
            if strategy is not None:
                mapping_charts = strategy.account_mapping_charts(
                    global_strategy_cfg,
                    dict(getattr(account, "strategy_params", {}) or {}),
                )
        if supports_semiconductor_timing_watchlist(account):
            write_semiconductor_timing_watchlist(
                root=root,
                config=config,
                account=account,
                target_dir=account_dir / "latest" / "watchlist",
                mapping_charts=mapping_charts,
            )
        else:
            _copy_bundle(
                latest_watchlist_dir,
                account_dir / "latest" / "watchlist",
                back_href="../../index.html",
                missing_title="暂无最新盘前观察池",
                missing_message="未找到账户级 latest watchlist。请先运行 ./runit brief watchlist --config config.yaml --all-accounts。",
            )
        _copy_bundle(
            latest_bill_dir,
            account_dir / "latest" / "account-bill",
            back_href="../../index.html",
            missing_title="暂无最新模拟交易账单",
            missing_message="未找到账户级 latest account-bill。请先运行 ./runit brief watchlist --config config.yaml --all-accounts。",
        )
        _write_latest_confirmed_account_bill(
            account,
            account_dir / "latest" / "account-bill",
            root=root,
            config=config,
            frames=frames,
            today=today,
        )
        for item in mapping_charts:
            relative_path = f"research/{item.chart.slug}/index.html"
            _write_market_comparison_research_page(
                site_root=account_dir,
                root=root,
                config=item.chart,
                research_path=relative_path,
                back_href="../../index.html",
                stylesheet_href="../../../../assets/style.css",
            )
            mapping_chart_links.append(
                {
                    "href": relative_path,
                    "kicker": item.button_kicker,
                    "label": item.button_label,
                }
            )
            mapping_chart_paths.append(f"accounts/{account_slug}/{relative_path}")
        if mapping_chart_paths:
            meta["mapping_chart_paths"] = mapping_chart_paths
        (account_dir / "index.html").write_text(
            _account_index_html(
                account=account,
                meta=meta,
                generated_at=generated_at,
                mapping_chart_links=mapping_chart_links,
                strategy_cfg=global_strategy_cfg,
            ),
            encoding="utf-8",
        )
        (account_dir / "ledger").mkdir(parents=True, exist_ok=True)
        (account_dir / "ledger" / "index.html").write_text(_ledger_html(account=account, frames=frames, generated_at=generated_at), encoding="utf-8")
        _write_csvs(account_dir, frames)

    wiki_path = _copy_wiki_index(site_root=site_root, config=config)
    research_path = _write_vix_512480_research_page(site_root=site_root)
    sox_research_path = _write_market_comparison_research_page(
        site_root=site_root,
        root=root,
        config=SOX_512480_COMPARISON_CONFIG,
        research_path=SOX_512480_RESEARCH_PATH,
    )
    manifest = {
        "generated_at": generated_at,
        "entry": "/quant/",
        "brief_path": "brief/index.html",
        "accounts": accounts_meta,
        "wiki_path": wiki_path,
        "research_path": research_path,
        "sox_research_path": sox_research_path,
    }
    (site_root / "data").mkdir(parents=True, exist_ok=True)
    (site_root / "data" / "site_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (site_root / "index.html").write_text(
        _site_index_html(accounts_meta=accounts_meta, generated_at=generated_at, wiki_path=wiki_path), encoding="utf-8"
    )
    (site_root / "brief").mkdir(parents=True, exist_ok=True)
    (site_root / "brief" / "index.html").write_text(
        _brief_index_html(accounts_meta=accounts_meta, generated_at=generated_at, wiki_path=wiki_path), encoding="utf-8"
    )
    return {"site_root": site_root, "manifest": manifest, "accounts": len(accounts_meta)}


def sync_quant_static_site(*, root: Path, site_root: Path, remote: str | None = None, remote_dir: str | None = None) -> dict[str, str]:
    remote = remote or os.environ.get("QUANT_SITE_SYNC_REMOTE") or DEFAULT_QUANT_REMOTE
    remote_dir = remote_dir or os.environ.get("QUANT_SITE_SYNC_REMOTE_DIR") or DEFAULT_QUANT_REMOTE_DIR
    if not remote_dir.rstrip("/").endswith("/quant"):
        raise ValueError("quant static site sync target must end with /quant/")
    if not (site_root / "index.html").is_file():
        raise FileNotFoundError(site_root / "index.html")
    command = ["rsync", "-avz", "--delete", f"{site_root}/", f"{remote}:{remote_dir}"]
    password = os.environ.get(QUANT_SITE_SYNC_PASSWORD_ENV)
    if not password:
        subprocess.run(command, check=True)
        return {"remote": remote, "remote_dir": remote_dir}

    askpass_fd, askpass_name = tempfile.mkstemp(prefix="quant-site-askpass-")
    askpass_path = Path(askpass_name)
    try:
        with os.fdopen(askpass_fd, "w", encoding="utf-8") as askpass_file:
            askpass_file.write('#!/bin/sh\nprintf "%s\\n" "$QUANT_SITE_SYNC_PASSWORD"\n')
        askpass_path.chmod(0o700)
        environment = os.environ.copy()
        environment.update(
            {
                "SSH_ASKPASS": str(askpass_path),
                "SSH_ASKPASS_REQUIRE": "force",
            }
        )
        ssh_command = (
            "ssh -o BatchMode=no -o PasswordAuthentication=yes "
            "-o PreferredAuthentications=password,keyboard-interactive -o NumberOfPasswordPrompts=1"
        )
        command[1:1] = ["-e", ssh_command]
        subprocess.run(command, check=True, env=environment)
    finally:
        askpass_path.unlink(missing_ok=True)
    return {"remote": remote, "remote_dir": remote_dir}
