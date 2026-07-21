from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

from phase0.execution.accounts import ensure_account_tables
from phase0.reporting.account_bill import export_account_bill_html, export_account_bill_placeholder_html


def test_account_bill_html_uses_belafonte_bundle(tmp_path: Path) -> None:
    account = SimpleNamespace(
        account_id="default",
        name="默认模拟账户",
        database_path=tmp_path / "simulated_accounts.sqlite",
    )
    with sqlite3.connect(account.database_path) as conn:
        ensure_account_tables(conn)
        conn.execute(
            """
            INSERT INTO simulated_accounts
            (account_id, name, initial_cash, simulation_start_date, enabled, execution_price_mode, max_participation_rate, lot_size, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            ("default", "默认模拟账户", 1_000_000.0, "2026-06-27", 1, "next_open", 0.05, 100),
        )
        conn.execute(
            """
            INSERT INTO account_daily_assets
            (account_id, brief_date, start_date, total_asset, stock_asset, cash_asset, daily_pnl, daily_return,
             target_exposure, estimated_trade_amount, estimated_volume, execution_price_mode, max_participation_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("default", "2026-06-29", "2026-06-27", 1_001_234.5, 200_000.0, 801_234.5, 1_234.5, 0.0012345, 0.19975, 50_000.0, 4_000, "next_open", 0.05),
        )
        conn.execute(
            """
            INSERT INTO account_trades
            (account_id, brief_date, signal_date, symbol, name, side, trade_time, price_mode, price, amount, cost, shares,
             lots, lot_size, raw_shares, rounding_rule, weight_before, weight_after, weight_change, is_estimated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "default",
                "2026-06-29",
                "2026-06-28",
                "000001.SZ",
                "平安银行",
                "buy",
                "2026-06-29 09:30",
                "next_open",
                12.34,
                12_340.0,
                6.17,
                1_000.0,
                10.0,
                100,
                1_023.5,
                "floor_to_lot_size",
                0.0,
                0.05,
                0.05,
                1,
            ),
        )
        conn.execute(
            """
            INSERT INTO account_positions
            (account_id, brief_date, symbol, name, close, target_weight, market_value, shares, lots, lot_size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("default", "2026-06-29", "000001.SZ", "平安银行", 12.4, 0.05, 12_400.0, 1_000.0, 10.0, 100),
        )

    output_path = export_account_bill_html(
        account=account,
        brief_date="2026-06-29",
        output_path=tmp_path / "reports" / "account_bill__report.html",
    )
    html = output_path.read_text(encoding="utf-8")
    css = (output_path.parent / "style.css").read_text(encoding="utf-8")

    assert '<html lang="zh-CN" data-theme="light">' in html
    assert '<link rel="stylesheet" href="style.css">' in html
    assert "<style>" not in html
    assert 'id="themeToggle"' in html
    assert 'id="backToTop"' in html
    assert 'class="report-table account-bill-table"' in html
    assert "账户总览" in html
    assert "<th>建仓日</th>" in html
    assert '<td class="num-center">2026-06-27</td>' in html
    assert '<td class="num-right">1,001,234.50</td>' in html
    assert '<td class="num-center">000001.SZ</td>' in html
    assert "--amber:      #eaa549;" in css
    assert "--text:       #b88f55;" in css


def test_account_bill_placeholder_uses_same_bundle(tmp_path: Path) -> None:
    account = SimpleNamespace(
        account_id="default",
        name="默认模拟账户",
        database_path=tmp_path / "simulated_accounts.sqlite",
    )

    output_path = export_account_bill_placeholder_html(
        account=account,
        output_path=tmp_path / "reports" / "account_bill__report.html",
    )
    html = output_path.read_text(encoding="utf-8")

    assert '<link rel="stylesheet" href="style.css">' in html
    assert "<style>" not in html
    assert "暂无确认账单" in html
    assert 'id="themeToggle"' in html
    assert (output_path.parent / "style.css").exists()


def test_account_bill_for_missing_requested_date_is_pending_not_previous_bill(tmp_path: Path) -> None:
    account = SimpleNamespace(
        account_id="default",
        name="默认模拟账户",
        execution_price_mode="next_open",
        database_path=tmp_path / "simulated_accounts.sqlite",
    )
    with sqlite3.connect(account.database_path) as conn:
        ensure_account_tables(conn)
        conn.execute(
            """
            INSERT INTO simulated_accounts
            (account_id, name, initial_cash, simulation_start_date, enabled, execution_price_mode, max_participation_rate, lot_size, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            ("default", "默认模拟账户", 1_000_000.0, "2026-06-30", 1, "next_open", 0.05, 100),
        )
        conn.execute(
            """
            INSERT INTO account_daily_assets
            (account_id, brief_date, start_date, total_asset, stock_asset, cash_asset, daily_pnl, daily_return,
             target_exposure, estimated_trade_amount, estimated_volume, execution_price_mode, max_participation_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("default", "2026-06-30", "2026-06-30", 1_001_234.5, 200_000.0, 801_234.5, 1_234.5, 0.0012345, 0.19975, 50_000.0, 4_000, "next_open", 0.05),
        )

    output_path = export_account_bill_html(
        account=account,
        brief_date="2026-07-02",
        output_path=tmp_path / "reports" / "account_bill__report.html",
    )
    html = output_path.read_text(encoding="utf-8")

    assert "模拟交易账单 2026-07-02" in html
    assert "2026-07-02 模拟交易账单待确认" in html
    assert "最近已确认账单日：2026-06-30" in html
    assert "1,001,234.50" not in html
    assert '<link rel="stylesheet" href="style.css">' in html
