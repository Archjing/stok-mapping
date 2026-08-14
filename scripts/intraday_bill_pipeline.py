"""盘中流水线 (调度器 intraday 任务): 回放落库 → 检测新增成交 → 账单+建站+同步.

由 maintenance_orchestrator 的 intraday_bill_publish 任务每分钟调用
(窗口 09:35-15:00)。遍历所有 enabled 的 single_etf_intraday 账户,
无新增成交时秒退；买入或卖出成交都会重建账单、站点并 rsync。

用法:
  .venv/bin/python3 scripts/intraday_bill_pipeline.py --config config.yaml
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quant.config import load_config
from quant.execution.accounts import load_simulated_accounts
from quant.execution.intraday_account_runner import run_configured_intraday_account
from quant.reporting.quant_static_site import (
    build_quant_static_site,
    sync_quant_static_site,
)

from scripts.gen_account_bill import generate_account_bill


def _today_filled_trades(db_path: Path, account_id: str, trade_date: str) -> list[sqlite3.Row]:
    """Read executed trades; T+1 exits are recorded here even without an order event."""
    if not db_path.exists():
        return []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return list(
            conn.execute(
                "SELECT * FROM single_etf_intraday_trades "
                "WHERE account_id=? AND trade_date=? ORDER BY trade_time, symbol, side",
                (account_id, trade_date),
            )
        )


def _trade_watermark(trades: list[sqlite3.Row]) -> str:
    """Stable fingerprint of the day's executed-trade ledger for one account."""
    rows = [dict(trade) for trade in trades]
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _needs_bill_refresh(trades: list[sqlite3.Row], *, prior_stamp: str) -> bool:
    """Refresh for any new or repaired buy/sell ledger state, but not idle sessions."""
    return bool(trades) and _trade_watermark(trades) != prior_stamp


def _stamp_path(account_id: str, trade_date: str) -> Path:
    return Path("data/simulated_trading") / f"bill_stamp_{account_id}_{trade_date}.txt"


def _enabled_single_etf_accounts(config_path: Path) -> list[str]:
    config = load_config(config_path)
    accounts = load_simulated_accounts(config, config_path.parent)
    return [
        account.account_id
        for account in accounts
        if account.execution_model == "single_etf_intraday" and account.enabled
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--as-of", default=None, help="as-of date (default today)")
    parser.add_argument("--force", action="store_true", help="rebuild bill+site even without new executed trades")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    root = config_path.parent
    today = args.as_of or date.today().isoformat()
    db_path = root / "data/simulated_trading/simulated_accounts.sqlite"

    account_ids = _enabled_single_etf_accounts(config_path)
    if not account_ids:
        print("[pipeline] 无 enabled 的 single_etf_intraday 账户")
        return 0

    rebuild = args.force
    for account_id in account_ids:
        # 1. 盘中回放 + 落库 (保护机制冲突时降级: 已有实时状态则以 DB 为准)
        try:
            run_configured_intraday_account(
                config_path=config_path,
                account_id=account_id,
                as_of_date=today,
                recover_missing=True,
            )
        except Exception as exc:
            print(f"[pipeline] {account_id} 盘中回放跳过: {exc} (以 DB 已落库状态为准)")

        # 2. 增量检测：卖出成交同样必须刷新账单，避免 T+1 退出仍显示为持仓。
        trades = _today_filled_trades(db_path, account_id, today)
        stamp_path = _stamp_path(account_id, today)
        prior_stamp = stamp_path.read_text(encoding="utf-8").strip() if stamp_path.exists() else ""
        needs_refresh = _needs_bill_refresh(trades, prior_stamp=prior_stamp)
        if needs_refresh:
            rebuild = True

        # 3. 有新增或修复后的成交台账 → 生成账单
        if args.force or needs_refresh:
            try:
                bill_path, summary = generate_account_bill(account_id=account_id, bill_date=today)
                print(f"[pipeline] {account_id} 账单: {bill_path} "
                      f"(持仓 {summary['open_shares']:,.0f} 股 / 总资产 {summary['total_asset']:,.2f})")
                stamp_path.write_text(_trade_watermark(trades), encoding="utf-8")
            except FileNotFoundError:
                print(f"[pipeline] {account_id} 账户数据缺失, 跳过账单")
        else:
            print(f"[pipeline] {account_id} 成交台账未变化, 跳过账单")

    if not rebuild:
        print("[pipeline] 全部账户无新增成交, 跳过建站")
        return 0

    # 4. 构建站点 (站点 builder 从 single_etf_intraday_* 表渲染单 ETF 账单页) + 5. 同步
    config = load_config(config_path)
    accounts = load_simulated_accounts(config, root)
    site_result = build_quant_static_site(root=root, config=config, accounts=accounts)
    site_root = Path(site_result["site_root"])
    print(f"[pipeline] 站点构建: {site_root}")
    sync_result = sync_quant_static_site(root=root, site_root=site_root)
    print(f"[pipeline] 同步: {sync_result.get('remote', '')}:{sync_result.get('remote_dir', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
