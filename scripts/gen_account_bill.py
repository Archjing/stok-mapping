"""生成模拟账户当日账单 (HTML, 站点同主题).

薄封装: 账单渲染在 quant.reporting.account_bill.export_single_etf_account_bill。

用法: .venv/bin/python3 scripts/gen_account_bill.py [--account-id ID] [--date YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quant.config import load_config
from quant.execution.accounts import load_simulated_accounts
from quant.reporting.account_bill import export_single_etf_account_bill

DB_PATH = Path("data/simulated_trading/simulated_accounts.sqlite")
OUTPUT_DIR = Path("reports/simulated_bills")


def generate_account_bill(
    *,
    account_id: str,
    bill_date: str,
    config_path: Path = Path("config.yaml"),
    output_dir: Path = OUTPUT_DIR,
) -> tuple[Path, dict[str, float]]:
    """Generate one account bill HTML. Returns (path, summary).

    summary keys: total_asset, stock_asset, cash_asset, daily_return, open_shares.
    """
    config = load_config(config_path)
    account = next(
        account for account in load_simulated_accounts(config, config_path.parent)
        if account.account_id == account_id
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / f"{account_id}_bill_{bill_date}.html"
    export_single_etf_account_bill(account=account, brief_date=bill_date, output_path=out)

    import sqlite3

    with sqlite3.connect(account.database_path) as conn:
        asset = conn.execute(
            "SELECT total_asset, stock_asset, cash_asset, daily_return "
            "FROM single_etf_intraday_daily_assets WHERE account_id=? AND trade_date=?",
            (account_id, bill_date),
        ).fetchone()
        shares = conn.execute(
            "SELECT open_position_shares FROM single_etf_intraday_accounts WHERE account_id=?",
            (account_id,),
        ).fetchone()
    summary = {
        "total_asset": float(asset[0]) if asset else 0.0,
        "stock_asset": float(asset[1]) if asset else 0.0,
        "cash_asset": float(asset[2]) if asset else 0.0,
        "daily_return": float(asset[3]) if asset else 0.0,
        "open_shares": float(shares[0] or 0.0) if shares else 0.0,
    }
    return out, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-id", default="semiconductor_timing")
    parser.add_argument("--date", default=date.today().isoformat())
    args = parser.parse_args()
    out, summary = generate_account_bill(account_id=args.account_id, bill_date=args.date)
    print(f"账单: {out}")
    print(
        f"持仓 {summary['open_shares']:,.0f} 股 | 现金 {summary['cash_asset']:,.2f} | "
        f"总资产 {summary['total_asset']:,.2f} | 当日 {summary['daily_return']:+.2%}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
