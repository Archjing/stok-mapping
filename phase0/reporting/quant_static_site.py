from __future__ import annotations

import html
import json
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from phase0.reporting.account_bill import export_account_bill_html, format_money, format_num, format_pct
from phase0.reporting.paths import latest_dir, report_root, slug
from phase0.reporting.semiconductor_timing_watchlist import (
    supports_semiconductor_timing_watchlist,
    write_semiconductor_timing_watchlist,
)


DEFAULT_QUANT_SITE_DIR = "static_site/quant"
DEFAULT_QUANT_REMOTE = "linuxuser@108.61.182.91"
DEFAULT_QUANT_REMOTE_DIR = "/var/www/share/quant/"
STATIC_ASSETS = ("style.css",)


def quant_site_root(*, root: Path, config: dict[str, Any] | None = None) -> Path:
    return report_root(root=root, config=config) / DEFAULT_QUANT_SITE_DIR


def _source_css_path() -> Path:
    return Path(__file__).with_name("static") / "style.css"


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
        from phase0.execution.accounts import ensure_account_tables

        with sqlite3.connect(db_path) as conn:
            ensure_account_tables(conn)
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


def _account_index_html(*, account: Any, meta: dict[str, str], generated_at: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(str(account.name))} 模拟账户</title>
  <link rel="stylesheet" href="../../assets/style.css">
</head>
<body>
{_theme_bar_html(back_href="../../index.html")}<div class="page account-bill-page">
  <div class="title-row"><h1>{html.escape(str(account.name))}</h1><span class="generated-at">生成时间：{html.escape(generated_at)}</span></div>
  <div class="summary">
    <div><span>账户 ID</span><strong>{html.escape(str(account.account_id))}</strong></div>
    <div><span>最新账单日</span><strong>{html.escape(meta.get("latest_bill_date") or "暂无")}</strong></div>
    <div><span>总资产</span><strong>{html.escape(meta.get("total_asset") or "暂无")}</strong></div>
    <div><span>当前仓位</span><strong>{html.escape(meta.get("target_exposure") or "暂无")}</strong></div>
  </div>
  <section class="bill-section quick-section"><h2>快捷入口</h2>
    <div class="quick-links">
      <a class="quick-card" href="latest/watchlist/index.html"><span>WATCHLIST</span><strong>最新盘前观察池</strong></a>
      <a class="quick-card" href="latest/account-bill/index.html"><span>BILL</span><strong>最新模拟交易账单</strong></a>
      <a class="quick-card" href="ledger/index.html"><span>LEDGER</span><strong>完整交易台账</strong></a>
      <a class="quick-card" href="../../index.html"><span>CONSOLE</span><strong>控制台首页</strong></a>
    </div>
  </section>
</div>
{_theme_script_html()}
</body>
</html>
"""


def _site_index_html(*, accounts_meta: list[dict[str, str]], generated_at: str, wiki_path: str) -> str:
    rows = []
    for item in accounts_meta:
        rows.append(
            "<tr>"
            f"<td>{html.escape(item['account_id'])}</td>"
            f"<td>{html.escape(item['name'])}</td>"
            f"<td>{html.escape(item.get('latest_bill_date') or '暂无')}</td>"
            f"<td>{html.escape(item.get('position_start_date') or '暂无')}</td>"
            f"<td>{html.escape(item.get('total_asset') or '暂无')}</td>"
            f"<td>{html.escape(item.get('target_exposure') or '暂无')}</td>"
            f"<td><a href=\"{html.escape(item['account_path'])}\">账户</a> ｜ <a href=\"{html.escape(item['watchlist_path'])}\">观察池</a> ｜ <a href=\"{html.escape(item['account_bill_path'])}\">账单</a> ｜ <a href=\"{html.escape(item['ledger_path'])}\">台账</a></td>"
            "</tr>"
        )
    rows_html = "".join(rows) if rows else '<tr><td colspan="7">暂无启用的模拟账户</td></tr>'
    wiki_link = '<a class="quick-card" href="wiki/index.html"><span>WIKI</span><strong>A股影响因子全景图</strong></a>' if wiki_path else ""
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
    total_asset = "" if assets.empty else format_money(latest.get("total_asset"))
    target_exposure = "" if assets.empty else format_pct(latest.get("target_exposure"))
    return {
        "account_id": str(account.account_id),
        "name": str(account.name),
        "latest_bill_date": latest_bill_date,
        "position_start_date": position_start_date,
        "total_asset": total_asset,
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

    accounts_meta: list[dict[str, str]] = []
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
        if supports_semiconductor_timing_watchlist(account):
            write_semiconductor_timing_watchlist(
                root=root,
                config=config,
                account=account,
                target_dir=account_dir / "latest" / "watchlist",
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
        (account_dir / "index.html").write_text(_account_index_html(account=account, meta=meta, generated_at=generated_at), encoding="utf-8")
        (account_dir / "ledger").mkdir(parents=True, exist_ok=True)
        (account_dir / "ledger" / "index.html").write_text(_ledger_html(account=account, frames=frames, generated_at=generated_at), encoding="utf-8")
        _write_csvs(account_dir, frames)

    wiki_path = _copy_wiki_index(site_root=site_root, config=config)
    manifest = {
        "generated_at": generated_at,
        "entry": "/quant/",
        "brief_path": "brief/index.html",
        "accounts": accounts_meta,
        "wiki_path": wiki_path,
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
    subprocess.run(["rsync", "-avz", "--delete", f"{site_root}/", f"{remote}:{remote_dir}"], check=True)
    return {"remote": remote, "remote_dir": remote_dir}
