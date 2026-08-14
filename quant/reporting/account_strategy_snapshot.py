"""Read-only example-backtest snapshots for account home pages."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def snapshot_path(*, root: Path, account_id: str) -> Path:
    return root / "reports" / "strategy_snapshots" / str(account_id) / "example_backtest.json"


def _effective_payload(*, account: Any, strategy_cfg: dict[str, Any]) -> dict[str, Any]:
    base = dict(strategy_cfg.get("cross_market_semiconductor_timing", {}) or {})
    base.update(dict(getattr(account, "strategy_params", {}) or {}))
    costs = {
        key: getattr(account, key, None)
        for key in ("commission", "min_commission", "slippage", "stamp_duty_sell", "transfer_fee_rate", "price_tick", "lot_size")
    }
    return {"strategy_id": str(getattr(account, "strategy_id", "")), "account_id": str(account.account_id), "params": base, "costs": costs, "window": "latest_complete_common_five_years"}


def snapshot_fingerprint(*, account: Any, strategy_cfg: dict[str, Any]) -> str:
    encoded = json.dumps(_effective_payload(account=account, strategy_cfg=strategy_cfg), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def load_snapshot(*, root: Path, account: Any, strategy_cfg: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    path = snapshot_path(root=root, account_id=str(account.account_id))
    if not path.is_file():
        return "missing", None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "invalid", None
    if not isinstance(payload, dict) or not isinstance(payload.get("rows"), list):
        return "invalid", None
    if payload.get("fingerprint") != snapshot_fingerprint(account=account, strategy_cfg=strategy_cfg):
        return "stale", None
    return "ready", payload
