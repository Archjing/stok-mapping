from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from phase0.execution.accounts import ensure_account_tables
from phase0.reporting.market_comparison_chart import (
    ComparisonChartConfig,
    ComparisonSeriesConfig,
    build_comparison_chart_data_from_frames,
    find_consecutive_move_runs,
    project_daily_mapping_signals,
)
from phase0.reporting.quant_static_site import (
    build_quant_static_site,
    sync_quant_static_site,
)


def _account(account_id: str, name: str, db_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        account_id=account_id,
        name=name,
        database_path=db_path,
        initial_cash=1_000_000.0,
        simulation_start_date="2026-06-30",
    )


def _write_account_db(path: Path, *, account_id: str, name: str, with_trade: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        ensure_account_tables(conn)
        conn.execute(
            """
            INSERT INTO simulated_accounts
            (account_id, name, initial_cash, simulation_start_date, enabled, execution_price_mode, max_participation_rate, lot_size, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (account_id, name, 1_000_000.0, "2026-06-30", 1, "next_open", 0.05, 100),
        )
        if not with_trade:
            return
        conn.execute(
            """
            INSERT INTO account_daily_assets
            (account_id, brief_date, start_date, total_asset, stock_asset, cash_asset, daily_pnl, daily_return,
             target_exposure, estimated_trade_amount, estimated_volume, execution_price_mode, max_participation_rate,
             unfilled_orders, partial_fill_orders, block_reason_counts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (account_id, "2026-06-30", "2026-06-30", 1_000_120.0, 69_722.0, 930_398.0, 120.0, 0.00012, 0.0697, 69_408.0, 900.0, "next_open", 0.05, 0, 0, "{}"),
        )
        conn.execute(
            """
            INSERT INTO account_trades
            (account_id, brief_date, signal_date, symbol, name, side, trade_time, price_mode, price, amount, cost,
             shares, lots, lot_size, raw_shares, rounding_rule, trade_status, block_reasons, weight_before, weight_after,
             weight_change, is_estimated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (account_id, "2026-06-30", "2026-06-29", "SZ.000636", "风华高科", "buy", "2026-06-30 09:30", "next_open", 72.24, 28_896.0, 5.0, 400.0, 4.0, 100, 474.8, "floor_to_lot_size", "全部成交", "", 0.0, 0.0343, 0.0343, 1),
        )
        conn.execute(
            """
            INSERT INTO account_positions
            (account_id, brief_date, symbol, name, close, target_weight, market_value, shares, lots, lot_size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (account_id, "2026-06-30", "SZ.000636", "风华高科", 72.24, 0.0289, 28_896.0, 400.0, 4.0, 100),
        )
        conn.execute(
            """
            INSERT INTO account_order_events
            (account_id, brief_date, signal_date, symbol, name, side, trade_time, price_mode, price, target_weight,
             weight_before, weight_change, requested_shares, filled_shares, shares, lots, amount, trade_status,
             block_reasons, event_type, is_estimated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account_id,
                "2026-06-30",
                "2026-06-29",
                "SZ.000636",
                "风华高科",
                "sell",
                "2026-06-30 09:30",
                "next_open",
                72.24,
                0.0,
                0.0289,
                -0.0289,
                400.0,
                0.0,
                0.0,
                0.0,
                0.0,
                "未成交",
                "T+1可卖库存不足",
                "unfilled",
                1,
            ),
        )


def _write_sox_512480_history(root: Path) -> None:
    us_db = root / "data" / "us_market_history.sqlite"
    etf_db = root / "data" / "etf_history.sqlite"
    us_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(us_db) as conn:
        conn.execute("CREATE TABLE us_daily_bars (symbol TEXT, date TEXT, close REAL)")
        conn.executemany(
            "INSERT INTO us_daily_bars (symbol, date, close) VALUES (?, ?, ?)",
            [
                ("^SOX", "2025-11-03", 7270.9702),
                ("^SOX", "2026-08-11", 12098.4697),
            ],
        )
    with sqlite3.connect(etf_db) as conn:
        conn.execute(
            """
            CREATE TABLE market_etf_daily_bars (
                symbol TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL,
                pre_close REAL, change_amount REAL, change_pct REAL, volume REAL,
                amount REAL, source TEXT, fetched_at TEXT
            )
            """
        )
        conn.execute("CREATE TABLE market_etf_adj_factors (symbol TEXT, date TEXT, adj_factor REAL, source TEXT, fetched_at TEXT)")
        conn.executemany(
            """
            INSERT INTO market_etf_daily_bars
            (symbol, date, open, high, low, close, pre_close, change_amount, change_pct, volume, amount, source, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("SH.512480", "2025-11-03", 0.726, 0.726, 0.726, 0.726, 0.726, 0, 0, 0, 0, "test", "2026-08-11"),
                ("SH.512480", "2026-08-11", 1.07, 1.07, 1.07, 1.07, 1.07, 0, 0, 0, 0, "test", "2026-08-11"),
            ],
        )
        conn.executemany(
            "INSERT INTO market_etf_adj_factors (symbol, date, adj_factor, source, fetched_at) VALUES (?, ?, ?, ?, ?)",
            [
                ("SH.512480", "2025-11-03", 1.0, "test", "2026-08-11"),
                ("SH.512480", "2026-08-11", 1.0, "test", "2026-08-11"),
            ],
        )


def test_consecutive_move_runs_require_three_qualifying_same_direction_days() -> None:
    sox = pd.DataFrame(
        {
            "date": pd.to_datetime(
                [
                    "2026-01-01",
                    "2026-01-02",
                    "2026-01-03",
                    "2026-01-04",
                    "2026-01-05",
                    "2026-01-06",
                    "2026-01-07",
                    "2026-01-08",
                ]
            ),
            "close": [100.0, 103.0, 106.09, 109.2727, 110.0, 106.7, 103.499, 100.394],
        }
    )

    assert find_consecutive_move_runs(sox, direction=1, consecutive_days=3, daily_change_pct=0.0) == [
        {"start": "2026-01-01", "end": "2026-01-05", "moveDays": 4, "change": 10.0}
    ]
    assert find_consecutive_move_runs(sox, direction=-1, consecutive_days=3, daily_change_pct=0.0) == [
        {"start": "2026-01-05", "end": "2026-01-08", "moveDays": 3, "change": -8.7327}
    ]


def test_daily_mapping_signals_project_source_close_to_next_target_date() -> None:
    sox = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-05", "2026-01-06"]),
            "close": [100.0, 100.6, 100.0, 100.4],
        }
    )
    signals = project_daily_mapping_signals(
        sox,
        target_dates=pd.Series(pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"])),
        daily_mapping_pct=0.5,
    )

    assert signals == [
        {"sourceDate": "2026-01-02", "targetDate": "2026-01-05", "change": 0.6, "direction": "up"},
        {"sourceDate": "2026-01-05", "targetDate": "2026-01-06", "change": -0.5964, "direction": "down"},
    ]


def test_generic_comparison_chart_uses_configurable_series_dates_band_and_move_rules() -> None:
    config = ComparisonChartConfig(
        slug="source-vs-target",
        title="Source 与 Target 对照图",
        source=ComparisonSeriesConfig(symbol="SRC", label="源指数"),
        target=ComparisonSeriesConfig(symbol="TGT", label="目标指数"),
        start_date="2026-01-01",
        observation_band=(90.0, 120.0),
        daily_mapping_pct=0.5,
        consecutive_days=3,
        consecutive_daily_change_pct=1.0,
    )
    source = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"]),
            "close": [100.0, 101.1, 102.2121, 103.3364, 102.2],
        }
    )
    target = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05", "2026-01-06"]),
            "close": [10.0, 10.2, 10.3, 10.1, 10.0],
        }
    )

    chart_data = build_comparison_chart_data_from_frames(source, target, config=config)

    assert chart_data is not None
    assert chart_data["source"] == {"symbol": "SRC", "label": "源指数"}
    assert chart_data["target"] == {"symbol": "TGT", "label": "目标指数"}
    assert chart_data["startDate"] == "2026-01-02"
    assert chart_data["observationBand"] == {"low": 90.0, "high": 120.0}
    assert chart_data["dailyMappingPct"] == 0.5
    assert chart_data["consecutiveMove"] == {"days": 3, "dailyPct": 1.0}
    assert chart_data["upRuns"] == [
        {"start": "2026-01-01", "end": "2026-01-04", "moveDays": 3, "change": 3.3364}
    ]
    assert chart_data["downRuns"] == []
    assert chart_data["dailyMappingSignals"][:3] == [
        {"sourceDate": "2026-01-02", "targetDate": "2026-01-03", "change": 1.1, "direction": "up"},
        {"sourceDate": "2026-01-03", "targetDate": "2026-01-04", "change": 1.1, "direction": "up"},
        {"sourceDate": "2026-01-04", "targetDate": "2026-01-05", "change": 1.1, "direction": "up"},
    ]


def test_build_quant_static_site_generates_multi_account_manifest_and_pages(tmp_path: Path) -> None:
    default_db = tmp_path / "data" / "default.sqlite"
    test2_db = tmp_path / "data" / "test2.sqlite"
    _write_account_db(default_db, account_id="default", name="默认模拟账户")
    _write_account_db(test2_db, account_id="test2", name="测试账户", with_trade=False)
    for account_id in ["default", "test2"]:
        watchlist_dir = tmp_path / "reports" / "runs" / "latest" / "accounts" / account_id / "watchlist"
        bill_dir = tmp_path / "reports" / "runs" / "latest" / "accounts" / account_id / "account_bill"
        watchlist_dir.mkdir(parents=True)
        bill_dir.mkdir(parents=True)
        (watchlist_dir / "index.html").write_text(f"<html>{account_id} watchlist</html>", encoding="utf-8")
        (watchlist_dir / "style.css").write_text("old css must be replaced", encoding="utf-8")
        (bill_dir / "index.html").write_text(f"<html>{account_id} bill</html>", encoding="utf-8")
        (bill_dir / "style.css").write_text("old css must be replaced", encoding="utf-8")
    global_watchlist_dir = tmp_path / "reports" / "runs" / "latest" / "watchlist"
    global_bill_dir = tmp_path / "reports" / "runs" / "latest" / "account_bill"
    global_watchlist_dir.mkdir(parents=True)
    global_bill_dir.mkdir(parents=True)
    (global_watchlist_dir / "index.html").write_text("<html>global watchlist must not be copied</html>", encoding="utf-8")
    (global_bill_dir / "index.html").write_text("<html>global bill must not be copied</html>", encoding="utf-8")
    wiki_source = tmp_path / "fixtures" / "wiki" / "index.html"
    wiki_source.parent.mkdir(parents=True)
    wiki_source.write_text(
        '<html><body><nav class="sb"><div class="sh">nav</div><a class="nc ni topni">A股影响因子全景图</a><details class="ng" open>group</details></nav><main class="mn">project wiki</main><script>window.MARKLOGSEQ_DEFAULT_PAGE="cn_gdp";</script></body></html>',
        encoding="utf-8",
    )
    _write_sox_512480_history(tmp_path)

    result = build_quant_static_site(
        root=tmp_path,
        config={"reporting": {"wiki_index_source": str(wiki_source)}},
        accounts=[
            _account("default", "默认模拟账户", default_db),
            _account("test2", "测试账户", test2_db),
        ],
    )

    site_root = tmp_path / "reports" / "static_site" / "quant"
    manifest = json.loads((site_root / "data" / "site_manifest.json").read_text(encoding="utf-8"))
    assert result["site_root"] == site_root
    assert [account["account_id"] for account in manifest["accounts"]] == ["default", "test2"]
    assert manifest["accounts"][0]["latest_bill_date"] == "2026-06-30"
    assert manifest["accounts"][0]["position_start_date"] == "2026-06-30"
    assert manifest["accounts"][1]["position_start_date"] == "2026-06-30"
    assert manifest["accounts"][0]["account_path"] == "accounts/default/index.html"
    assert manifest["accounts"][0]["watchlist_path"] == "accounts/default/latest/watchlist/index.html"
    assert manifest["accounts"][0]["account_bill_path"] == "accounts/default/latest/account-bill/index.html"
    assert manifest["accounts"][0]["ledger_path"] == "accounts/default/ledger/index.html"
    assert manifest["brief_path"] == "brief/index.html"
    assert manifest["wiki_path"] == "wiki/index.html"
    assert manifest["research_path"] == "research/vix-vs-512480/index.html"
    assert manifest["sox_research_path"] == "research/sox-vs-512480/index.html"
    wiki_html = (site_root / "wiki" / "index.html").read_text(encoding="utf-8")
    assert "project wiki" in wiki_html
    assert 'class="quant-wiki-back-wrap"' in wiki_html
    assert 'class="quant-wiki-back-link"' in wiki_html
    assert 'href="../index.html"' in wiki_html
    assert "border-bottom:0" in wiki_html
    assert 'class="quant-wiki-nav-scroll"' in wiki_html
    assert "scrollbar-width:none" in wiki_html
    assert ".quant-wiki-nav-scroll::-webkit-scrollbar" in wiki_html
    assert "height:42vh" in wiki_html
    assert "max-height:18vh" not in wiki_html
    assert "min-height:96px" in wiki_html
    assert 'window.MARKLOGSEQ_DEFAULT_PAGE="a_share_factor_overview"' in wiki_html
    assert '<details class="ng" open>' not in wiki_html
    assert '<details class="ng">group</details>' in wiki_html
    assert 'class="mn quant-wiki-main"' not in wiki_html
    assert wiki_html.index('<nav class="sb">') < wiki_html.index('class="quant-wiki-back-link"') < wiki_html.index('class="sh"')
    assert wiki_html.index("A股影响因子全景图</a>") < wiki_html.index('class="quant-wiki-nav-scroll"') < wiki_html.index('<details class="ng">')
    assert (site_root / "index.html").is_file()
    site_index_html = (site_root / "index.html").read_text(encoding="utf-8")
    assert 'id="themeToggle"' in site_index_html
    assert 'class="back-link"' in site_index_html
    assert 'href="index.html"' in site_index_html
    assert 'href="brief/index.html"' in site_index_html
    assert "每日简报" in site_index_html
    assert 'href="research/vix-vs-512480/index.html"' in site_index_html
    assert "VIX 与半导体 ETF 对照图" in site_index_html
    assert 'href="research/sox-vs-512480/index.html"' in site_index_html
    assert "SOX 与半导体 ETF 对照图" in site_index_html
    assert 'href="wiki/index.html"' in site_index_html
    assert "A股影响因子全景图" in site_index_html
    assert 'href="accounts/default/index.html"' in site_index_html
    assert 'href="accounts/default/latest/watchlist/index.html"' in site_index_html
    assert '<section class="bill-section"><div class="section-title-frame"><h2>账户总览</h2></div>' in site_index_html
    assert 'section-title-card' not in site_index_html
    assert 'section-title-links' not in site_index_html
    assert "<th>建仓日</th>" in site_index_html
    assert "<td>2026-06-30</td><td>2026-06-30</td><td>1,000,120.00</td>" in site_index_html
    brief_html = (site_root / "brief" / "index.html").read_text(encoding="utf-8")
    assert "量化每日简报" in brief_html
    assert 'class="page account-bill-page brief-page"' in brief_html
    assert 'href="../assets/style.css"' in brief_html
    assert 'href="/quant/assets/style.css"' in brief_html
    assert 'href="/quant/index.html"' in brief_html
    assert 'href="/quant/accounts/default/latest/watchlist/index.html"' in brief_html
    assert 'href="/quant/accounts/default/latest/account-bill/index.html"' in brief_html
    assert 'href="/quant/accounts/default/ledger/index.html"' in brief_html
    assert not (site_root.parent / "brief").exists()
    assert "部分账户暂无确认账单，简报只展示可用证据" in brief_html
    assert "页面不直接生成交易信号" in brief_html
    assert "不生成新的买卖建议" in brief_html
    asset_css = (site_root / "assets" / "style.css").read_text(encoding="utf-8")
    assert ".brief-page .brief-hero" in asset_css
    assert ".brief-grid" in asset_css
    assert ".asset-history-wrap" in asset_css
    assert ".trade-history-wrap" in asset_css
    assert ".position-history-wrap" in asset_css
    assert "5 * 34px" in asset_css
    assert "9 * 34px" in asset_css
    research_html = (site_root / "research" / "vix-vs-512480" / "index.html").read_text(encoding="utf-8")
    assert "^VIX 与半导体 ETF（512480）" in research_html
    assert "2025-11-03 至 2026-08-11" in research_html
    assert '"etfLastDate":"2026-08-11"' in research_html
    assert "^VIX 原值 14–19 区间" in research_html
    assert "连续至少 3 个相邻美股交易日收跌" in research_html
    assert "绿色阴影为连续至少 3 日收涨" in research_html
    sox_research_html = (site_root / "research" / "sox-vs-512480" / "index.html").read_text(encoding="utf-8")
    assert "^SOX 与半导体 ETF（512480）" in sox_research_html
    assert "2025-11-03 至 2026-08-11" in sox_research_html
    assert '"source":{"symbol":"^SOX","label":"^SOX（费城半导体指数）"}' in sox_research_html
    assert '"target":{"symbol":"SH.512480","label":"SH.512480 前复权收盘价（实际交易标的）"}' in sox_research_html
    assert "SH.512480 前复权收盘价" in sox_research_html
    assert "source.observationBand.low.toLocaleString('en-US')" in sox_research_html
    assert '"observationBand":{"low":8000.0,"high":12000.0}' in sox_research_html
    assert '"dailyMappingPct":0.5' in sox_research_html
    assert '"dailyMappingSignals"' in sox_research_html
    assert "投影至下一可对照目标交易日" in sox_research_html
    assert '"consecutiveMove":{"days":3,"dailyPct":0.0}' in sox_research_html
    assert 'id="market-comparison"' in sox_research_html
    assert "红色阴影为连续上涨，绿色阴影为连续下跌" in sox_research_html
    assert '"upRuns"' in sox_research_html
    assert '"downRuns"' in sox_research_html
    assert (site_root / "accounts" / "default" / "index.html").is_file()
    account_index_html = (site_root / "accounts" / "default" / "index.html").read_text(encoding="utf-8")
    assert 'id="themeToggle"' in account_index_html
    assert 'class="back-link"' in account_index_html
    assert 'href="../../index.html"' in account_index_html
    assert 'class="quick-card"' in account_index_html
    assert 'href="latest/watchlist/index.html"' in account_index_html
    assert 'href="ledger/index.html"' in account_index_html
    ledger_html = (site_root / "accounts" / "default" / "ledger" / "index.html").read_text(encoding="utf-8")
    assert "完整交易台账" in ledger_html
    assert "买入" in ledger_html
    assert "卖出" in ledger_html
    assert "未成交" in ledger_html
    assert "T+1可卖库存不足" in ledger_html
    assert "计划股数" in ledger_html
    assert "成交股数" in ledger_html
    assert 'class="table-wrap asset-history-wrap"' in ledger_html
    assert 'class="table-wrap trade-history-wrap"' in ledger_html
    assert 'class="table-wrap position-history-wrap"' in ledger_html
    assert "<td>buy</td>" not in ledger_html
    assert "<td>sell</td>" not in ledger_html
    assert 'id="themeToggle"' in ledger_html
    assert 'class="back-link"' in ledger_html
    assert 'href="../index.html"' in ledger_html
    latest_watchlist_html = (site_root / "accounts" / "default" / "latest" / "watchlist" / "index.html").read_text(encoding="utf-8")
    assert "default watchlist" in latest_watchlist_html
    assert 'class="back-link"' in latest_watchlist_html
    assert 'href="../../index.html"' in latest_watchlist_html
    assert "watchlist.css" not in latest_watchlist_html
    assert "style.css" in latest_watchlist_html
    latest_account_bill_html = (site_root / "accounts" / "default" / "latest" / "account-bill" / "index.html").read_text(encoding="utf-8")
    assert "模拟交易账单 2026-06-30" in latest_account_bill_html
    today = datetime.now().date().isoformat()
    assert f"当前展示最近已确认交易日 2026-06-30 的账单" in latest_account_bill_html
    assert today in latest_account_bill_html
    assert "default bill" not in latest_account_bill_html
    assert 'class="back-link"' in latest_account_bill_html
    assert "old css must be replaced" not in (site_root / "accounts" / "default" / "latest" / "watchlist" / "style.css").read_text(
        encoding="utf-8"
    )
    assert ".theme-btn" in (site_root / "accounts" / "default" / "latest" / "watchlist" / "style.css").read_text(encoding="utf-8")
    latest_watchlist_test2_html = (site_root / "accounts" / "test2" / "latest" / "watchlist" / "index.html").read_text(encoding="utf-8")
    assert "test2 watchlist" in latest_watchlist_test2_html
    assert 'class="back-link"' in latest_watchlist_test2_html
    latest_account_bill_test2_html = (site_root / "accounts" / "test2" / "latest" / "account-bill" / "index.html").read_text(encoding="utf-8")
    assert "暂无最新模拟交易账单" in latest_account_bill_test2_html
    assert 'class="back-link"' in latest_account_bill_test2_html
    assert (site_root / "accounts" / "default" / "dates" / "2026-06-30" / "daily-assets.csv").is_file()
    assert (site_root / "accounts" / "default" / "dates" / "2026-06-30" / "trades.csv").is_file()
    assert (site_root / "accounts" / "default" / "dates" / "2026-06-30" / "positions.csv").is_file()


def test_build_quant_static_site_handles_empty_ledger_and_missing_order_events(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "empty.sqlite"
    _write_account_db(db_path, account_id="empty", name="空账户", with_trade=False)

    build_quant_static_site(
        root=tmp_path,
        config={"reporting": {}},
        accounts=[_account("empty", "空账户", db_path)],
    )

    html = (tmp_path / "reports" / "static_site" / "quant" / "accounts" / "empty" / "ledger" / "index.html").read_text(encoding="utf-8")
    assert "暂无资产记录" in html
    assert "暂无逐笔未成交事件" in html
    watchlist_html = (
        tmp_path / "reports" / "static_site" / "quant" / "accounts" / "empty" / "latest" / "watchlist" / "index.html"
    ).read_text(encoding="utf-8")
    account_bill_html = (
        tmp_path / "reports" / "static_site" / "quant" / "accounts" / "empty" / "latest" / "account-bill" / "index.html"
    ).read_text(encoding="utf-8")
    assert "暂无最新盘前观察池" in watchlist_html
    assert "暂无最新模拟交易账单" in account_bill_html


def test_build_quant_static_site_omits_wiki_when_no_source_is_configured(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "empty.sqlite"
    _write_account_db(db_path, account_id="empty", name="空账户", with_trade=False)

    result = build_quant_static_site(
        root=tmp_path,
        config={"reporting": {}},
        accounts=[_account("empty", "空账户", db_path)],
    )

    site_root = tmp_path / "reports" / "static_site" / "quant"
    assert result["manifest"]["wiki_path"] == ""
    assert not (site_root / "wiki" / "index.html").exists()
    assert 'href="wiki/index.html"' not in (site_root / "index.html").read_text(encoding="utf-8")
    assert 'href="/quant/wiki/index.html"' not in (site_root / "brief" / "index.html").read_text(encoding="utf-8")


def test_ledger_page_keeps_full_assets_and_trades_but_limits_snapshots(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / "default.sqlite"
    _write_account_db(db_path, account_id="default", name="默认模拟账户")
    with sqlite3.connect(db_path) as conn:
        for offset, date_value in enumerate(["2026-07-01", "2026-07-02", "2026-07-03", "2026-07-04"], start=1):
            conn.execute(
                """
                INSERT INTO account_daily_assets
                (account_id, brief_date, start_date, total_asset, stock_asset, cash_asset, daily_pnl, daily_return,
                 target_exposure, estimated_trade_amount, estimated_volume, execution_price_mode, max_participation_rate,
                 unfilled_orders, partial_fill_orders, block_reason_counts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "default",
                    date_value,
                    "2026-06-30",
                    1_000_000.0 + offset,
                    50_000.0 + offset,
                    950_000.0,
                    float(offset),
                    0.0001,
                    0.05,
                    10_000.0,
                    100.0,
                    "next_open",
                    0.05,
                    0,
                    0,
                    "{}",
                ),
            )
            conn.execute(
                """
                INSERT INTO account_trades
                (account_id, brief_date, signal_date, symbol, name, side, trade_time, price_mode, price, amount, cost,
                 shares, lots, lot_size, raw_shares, rounding_rule, trade_status, block_reasons, weight_before, weight_after,
                 weight_change, is_estimated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "default",
                    date_value,
                    date_value,
                    f"SZ.00000{offset}",
                    "旧成交应保留" if date_value == "2026-07-01" else f"成交{offset}",
                    "buy",
                    f"{date_value} 09:30",
                    "next_open",
                    10.0,
                    1_000.0,
                    1.0,
                    100.0,
                    1.0,
                    100,
                    100.0,
                    "floor_to_lot_size",
                    "全部成交",
                    "",
                    0.0,
                    0.01,
                    0.01,
                    1,
                ),
            )
            conn.execute(
                """
                INSERT INTO account_positions
                (account_id, brief_date, symbol, name, close, target_weight, market_value, shares, lots, lot_size)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "default",
                    date_value,
                    f"SZ.10000{offset}",
                    "旧持仓不应显示" if date_value == "2026-07-01" else f"近期持仓{offset}",
                    10.0,
                    0.01,
                    1_000.0,
                    100.0,
                    1.0,
                    100,
                ),
            )
            conn.execute(
                """
                INSERT INTO account_order_events
                (account_id, brief_date, signal_date, symbol, name, side, trade_time, price_mode, price, target_weight,
                 weight_before, weight_change, requested_shares, filled_shares, shares, lots, amount, trade_status,
                 block_reasons, event_type, is_estimated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "default",
                    date_value,
                    date_value,
                    f"SZ.20000{offset}",
                    f"事件{offset}",
                    "buy",
                    f"{date_value} 09:30",
                    "next_open",
                    10.0,
                    0.01,
                    0.0,
                    0.01,
                    100.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    "未成交",
                    "旧事件不应显示" if date_value == "2026-07-01" else "近期事件应显示",
                    "unfilled",
                    1,
                ),
            )

    build_quant_static_site(
        root=tmp_path,
        config={"reporting": {}},
        accounts=[_account("default", "默认模拟账户", db_path)],
    )

    html = (tmp_path / "reports" / "static_site" / "quant" / "accounts" / "default" / "ledger" / "index.html").read_text(
        encoding="utf-8"
    )
    manifest = json.loads(
        (tmp_path / "reports" / "static_site" / "quant" / "data" / "site_manifest.json").read_text(encoding="utf-8")
    )
    site_index_html = (tmp_path / "reports" / "static_site" / "quant" / "index.html").read_text(encoding="utf-8")
    assert "每日资产（全部账单日）" in html
    assert "成交明细（全部历史成交）" in html
    assert "持仓快照（最近3个账单日）" in html
    assert "执行事件（最近3个账单日）" in html
    assert 'class="table-wrap asset-history-wrap"' in html
    assert 'class="table-wrap trade-history-wrap"' in html
    assert 'class="table-wrap position-history-wrap"' in html
    assert manifest["accounts"][0]["latest_bill_date"] == "2026-07-04"
    assert "<td>2026-07-04</td><td>2026-06-30</td>" in site_index_html
    assert "最近账单日：2026-07-04" in html
    assert "2026-06-30" in html
    assert "旧成交应保留" in html
    assert "旧持仓不应显示" not in html
    assert "旧事件不应显示" not in html
    assert "近期持仓2" in html
    assert "近期持仓4" in html
    assert "近期事件应显示" in html
    assert html.index("2026-07-04") < html.index("2026-07-03") < html.index("2026-07-02") < html.index("2026-07-01")


def test_sync_quant_static_site_targets_only_quant_directory(monkeypatch, tmp_path: Path) -> None:
    site_root = tmp_path / "reports" / "static_site" / "quant"
    site_root.mkdir(parents=True)
    (site_root / "index.html").write_text("<html></html>", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(cmd, *, check: bool):
        calls.append(cmd)

    monkeypatch.setattr("phase0.reporting.quant_static_site.subprocess.run", fake_run)

    result = sync_quant_static_site(root=tmp_path, site_root=site_root, remote="deploy@example", remote_dir="/var/www/share/quant/")

    assert calls
    assert calls[0][-1] == "deploy@example:/var/www/share/quant/"
    assert len(calls) == 1
    assert "deploy@example:/var/www/share/" not in calls[0]


def test_sync_quant_static_site_uses_env_password_without_exposing_it_in_command(monkeypatch, tmp_path: Path) -> None:
    site_root = tmp_path / "reports" / "static_site" / "quant"
    site_root.mkdir(parents=True)
    (site_root / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setenv("QUANT_SITE_SYNC_PASSWORD", "not-for-command-line")
    calls: list[tuple[list[str], dict[str, str]]] = []

    def fake_run(cmd, *, check: bool, env: dict[str, str]):
        calls.append((cmd, env))

    monkeypatch.setattr("phase0.reporting.quant_static_site.subprocess.run", fake_run)

    sync_quant_static_site(root=tmp_path, site_root=site_root, remote="deploy@example", remote_dir="/var/www/share/quant/")

    assert len(calls) == 1
    command, environment = calls[0]
    assert "not-for-command-line" not in command
    assert "-e" in command
    assert "PasswordAuthentication=yes" in command[command.index("-e") + 1]
    assert environment["QUANT_SITE_SYNC_PASSWORD"] == "not-for-command-line"
    assert environment["SSH_ASKPASS_REQUIRE"] == "force"
    assert not Path(environment["SSH_ASKPASS"]).exists()


def test_sync_quant_static_site_rejects_spidermanread_root(tmp_path: Path) -> None:
    site_root = tmp_path / "reports" / "static_site" / "quant"
    site_root.mkdir(parents=True)
    (site_root / "index.html").write_text("<html></html>", encoding="utf-8")

    with pytest.raises(ValueError, match="quant"):
        sync_quant_static_site(root=tmp_path, site_root=site_root, remote="deploy@example", remote_dir="/var/www/spidermanread/")


def test_build_quant_static_site_generates_semiconductor_timing_premarket_watchlist(tmp_path: Path) -> None:
    account_db = tmp_path / "data" / "simulated_accounts.sqlite"
    _write_account_db(account_db, account_id="semiconductor_timing", name="半导体ETF美股情绪映射择时_v1", with_trade=False)
    us_db = tmp_path / "data" / "us_market_history.sqlite"
    us_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(us_db) as conn:
        conn.execute(
            """
            CREATE TABLE us_daily_bars (
                market TEXT NOT NULL,
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                adjusted_close REAL,
                volume REAL,
                source TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                PRIMARY KEY (symbol, date)
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO us_daily_bars
            (market, symbol, date, open, high, low, close, adjusted_close, volume, source, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("US", "^SOX", "2026-08-10", 11800.0, 12100.0, 11700.0, 12000.0, 12000.0, 0.0, "test", "2026-08-11T08:00:00+08:00"),
                ("US", "^SOX", "2026-08-09", 11700.0, 11900.0, 11600.0, 11800.0, 11800.0, 0.0, "test", "2026-08-10T08:00:00+08:00"),
                ("US", "^VIX", "2026-08-10", 15.0, 16.0, 14.0, 15.46, 15.46, 0.0, "test", "2026-08-11T08:00:00+08:00"),
                ("US", "AMD", "2026-08-10", 180.0, 184.0, 179.0, 182.0, 182.0, 1.0, "test", "2026-08-11T08:00:00+08:00"),
                ("US", "AMD", "2026-08-09", 178.0, 181.0, 177.0, 180.0, 180.0, 1.0, "test", "2026-08-10T08:00:00+08:00"),
            ],
        )
    corpus_db = tmp_path / "data" / "ai_corpus" / "ai_corpus.sqlite"
    corpus_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(corpus_db) as conn:
        conn.execute(
            """
            CREATE TABLE ai_corpus_documents (
                document_id TEXT PRIMARY KEY,
                corpus_type TEXT,
                provider TEXT,
                source TEXT,
                published_at TEXT,
                ingested_at TEXT,
                title TEXT,
                url TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO ai_corpus_documents
            (document_id, corpus_type, provider, source, published_at, ingested_at, title, url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "news-1",
                "us_market_news",
                "us_market_news",
                "CNBC Technology",
                "2026-08-11T22:15:30+00:00",
                "2026-08-12T11:18:49+08:00",
                "Nvidia lines up $500 billion in financing",
                "https://www.cnbc.com/example/nvidia-financing.html",
            ),
        )

    account = SimpleNamespace(
        account_id="semiconductor_timing",
        name="半导体ETF美股情绪映射择时_v1",
        database_path=account_db,
        initial_cash=200_000.0,
        simulation_start_date="2026-08-12",
        strategy_id="cross_market_semiconductor_timing_etf_v1",
        execution_model="single_etf_intraday",
    )
    build_quant_static_site(
        root=tmp_path,
        config={
            "reporting": {},
            "us_market_history": {
                "path": "data/us_market_history.sqlite",
                "daily_table": "us_daily_bars",
                "instrument_groups": {
                    "core_signal": {"symbols": ["^SOX", "^VIX"], "critical": True},
                    "semiconductor_breadth": {"symbols": ["AMD"], "purpose": "半导体广度"},
                },
            },
            "ai_corpus": {"database_path": "data/ai_corpus/ai_corpus.sqlite"},
        },
        accounts=[account],
    )

    watchlist_html = (
        tmp_path / "reports" / "static_site" / "quant" / "accounts" / "semiconductor_timing" / "latest" / "watchlist" / "index.html"
    ).read_text(encoding="utf-8")
    assert "半导体ETF美股情绪映射择时_v1｜盘前观察池" in watchlist_html
    assert "^SOX" in watchlist_html
    assert "12,000.00" in watchlist_html
    assert "2026-08-10" in watchlist_html
    assert "15.46" in watchlist_html
    assert "SOX &gt; 0.5%" in watchlist_html
    assert "VIX &lt; 19" in watchlist_html
    assert "研究市场背景" in watchlist_html
    assert "半导体广度" in watchlist_html
    assert "AMD" in watchlist_html
    assert "仅供研究观察，不参与当前自动交易信号" in watchlist_html
    assert "CNBC Technology" in watchlist_html
    assert "Nvidia lines up $500 billion in financing" in watchlist_html
    assert "https://www.cnbc.com/example/nvidia-financing.html" in watchlist_html
    assert "新闻仅供人工研判，不参与当前自动交易信号" in watchlist_html

    account_html = (
        tmp_path / "reports" / "static_site" / "quant" / "accounts" / "semiconductor_timing" / "index.html"
    ).read_text(encoding="utf-8")
    assert "总资产</span><strong>200,000.00" in account_html
    assert "现金资产</span><strong>200,000.00" in account_html
    assert "股票资产</span><strong>0.00" in account_html
    assert "当前仓位</span><strong>0.00%" in account_html
    assert "总资产</span><strong>暂无" not in account_html
