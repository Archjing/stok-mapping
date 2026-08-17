"""Daily data-governance pass: freshness check + automatic repair.

Runs once per trading day (after all per-market post-close jobs) and answers a
single question per local database: is its latest data as fresh as its source's
own update cadence requires, and if not, can the scheduler repair it?

Repair is implemented by shelling out to the same ``quant.cli`` update/backfill
commands the scheduler already uses, so the governance pass never duplicates
data-movement logic — it only *detects* staleness and *dispatches* the existing
repair command.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import sqlite3


@dataclass(frozen=True)
class FreshnessTarget:
    """One table's expected latest date vs its actual latest date."""

    label: str
    db_path: Path
    table: str
    date_column: str
    cadence: str  # "trading" | "daily" | "weekly"
    calendar_db: Path | None = None  # 交易日历库；None 时回退工作日
    calendar_table: str = "trading_calendar"
    extra_where: str = ""
    repair_command: list[str] = field(default_factory=list)
    # 相对 as_of 的目标交易日偏移：0=当天（A股，15:00 收盘当日入库），
    # 1=前一个交易日（美/港/欧，当地收盘时北京已进入次日）。
    lag_trading_days: int = 0

    def sql(self) -> str:
        where = f"WHERE {self.extra_where}" if self.extra_where else ""
        return f"SELECT MAX({self.date_column}) FROM {self.table} {where}".strip()


@dataclass
class FreshnessFinding:
    target: FreshnessTarget
    latest: str
    expected: str
    status: str  # "fresh" | "stale" | "empty" | "missing_table" | "error"
    detail: str = ""


@dataclass
class GovernanceResult:
    checked: int
    fresh: int
    stale: int
    empty: int
    errors: int
    repaired: int
    repair_failed: int
    findings: list[FreshnessFinding] = field(default_factory=list)
    journal: Any = None

    @property
    def ok(self) -> bool:
        return self.repair_failed == 0


def _scalar(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> Any:
    try:
        return conn.execute(sql, params).fetchone()
    except sqlite3.Error:
        return None


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    if not table or not table.replace("_", "").isalnum():
        return False
    return bool(
        _scalar(conn, "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (table,))
    )


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except sqlite3.Error:
        return set()


def _prev_day(d: date) -> date:
    return date.fromordinal(d.toordinal() - 1)


def _expected_date(target: FreshnessTarget, as_of: date) -> str:
    """Latest date the table should have reached under its cadence.

    ``trading`` uses the target's own open-day calendar when available (each
    market has a different holiday set), falling back to the previous weekday.
    ``lag_trading_days`` shifts the expectation back N trading days for markets
    that close after Beijing's date rollover (US/HK/EU).
    """
    if target.cadence == "trading":
        # A股：is_open 日历表；美/港/欧：从行情库本身推导交易日（无 is_open 列）。
        cal_db = target.calendar_db
        if cal_db is not None and cal_db.exists():
            days: list[str] = []
            try:
                with sqlite3.connect(f"file:{cal_db}?mode=ro", uri=True) as conn:
                    if _table_exists(conn, target.calendar_table):
                        cols = _table_columns(conn, target.calendar_table)
                        if {"date", "is_open"}.issubset(cols):
                            rows = conn.execute(
                                f"SELECT date FROM {target.calendar_table} WHERE is_open = 1 AND date <= ? ORDER BY date",
                                (as_of.isoformat(),),
                            ).fetchall()
                            days = [str(r[0]) for r in rows]
                        elif "date" in cols and "symbol" in cols:
                            from quant.data_governance.market_calendar import load_market_trading_days

                            market = "us" if "us" in str(cal_db) else ("hk" if "hk" in str(cal_db) else "eu")
                            days = load_market_trading_days(
                                database_path=cal_db,
                                daily_table=target.calendar_table,
                                market=market,
                            )
            except sqlite3.Error:
                days = []
            if days:
                cutoff = [d for d in days if d <= as_of.isoformat()]
                if len(cutoff) > target.lag_trading_days:
                    return cutoff[-1 - target.lag_trading_days]
                if cutoff:
                    return cutoff[0]
        # 回退：最近一个工作日，再按 lag 回退 N 个工作日。
        d = as_of
        while d.isoweekday() > 5:  # 周六=6 周日=7 → 回退到周五
            d = _prev_day(d)
        for _ in range(target.lag_trading_days):
            d = _prev_day(d)
            while d.isoweekday() > 5:
                d = _prev_day(d)
        return d.isoformat()
    if target.cadence == "daily":
        return as_of.isoformat()
    if target.cadence == "weekly":
        d = as_of
        while d.isoweekday() != 1:
            d = _prev_day(d)
        return d.isoformat()
    return as_of.isoformat()


def _resolve(root: Path, value: Any) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def _build_targets(root: Path, cfg: dict[str, Any]) -> list[FreshnessTarget]:
    local_cfg = cfg.get("local_history", {})
    a_share_db = _resolve(root, local_cfg.get("path", "data/a_share_history.sqlite"))
    cn_calendar_db = _resolve(root, local_cfg.get("calendar_db", a_share_db))
    cn_calendar_table = str(local_cfg.get("calendar_table", "trading_calendar"))

    us_db = _resolve(root, cfg.get("us_market_history", {}).get("path", "data/us_market_history.sqlite"))
    hk_db = _resolve(root, cfg.get("hk_market_history", {}).get("path", "data/hk_market_history.sqlite"))
    eu_db = _resolve(root, cfg.get("europe_market_history", {}).get("path", "data/euro_market_history.sqlite"))
    cross_db = _resolve(root, cfg.get("cross_market_reference_history", {}).get("path", "data/cross_market_reference_history.sqlite"))
    etf_db = _resolve(root, cfg.get("etf_history", {}).get("path", "data/etf_history.sqlite"))

    py = str(root / ".venv" / "bin" / "python")
    cfg_arg = str(root / "config.yaml")

    targets: list[FreshnessTarget] = []
    targets.append(
        FreshnessTarget(
            label="A股指数日线",
            db_path=a_share_db,
            table="market_index_bars",
            date_column="date",
            cadence="trading",
            calendar_db=cn_calendar_db,
            calendar_table=cn_calendar_table,
            extra_where="market = 'CN'",
            repair_command=[py, "-m", "quant.cli", "update-index-history", "--config", cfg_arg],
        )
    )
    targets.append(
        FreshnessTarget(
            label="A股个股日线(bfq)",
            db_path=a_share_db,
            table="market_daily_bars",
            date_column="date",
            cadence="trading",
            calendar_db=cn_calendar_db,
            calendar_table=cn_calendar_table,
            extra_where="market = 'CN' AND adjust_type = 'bfq'",
            repair_command=[py, "-m", "quant.cli", "update-history", "--config", cfg_arg],
        )
    )
    targets.append(
        FreshnessTarget(
            label="A股复权因子",
            db_path=a_share_db,
            table="market_adj_factors",
            date_column="date",
            cadence="trading",
            calendar_db=cn_calendar_db,
            calendar_table=cn_calendar_table,
            repair_command=[
                py, "-m", "quant.cli", "backfill-adjustment-factors",
                "--config", cfg_arg,
                "--start-date", "__LATEST__", "--end-date", "__END__", "--no-dividends",
            ],
        )
    )
    targets.append(
        FreshnessTarget(
            label="美股日线",
            db_path=us_db,
            table="us_daily_bars",
            date_column="date",
            cadence="trading",
            calendar_db=us_db,
            calendar_table="us_daily_bars",
            lag_trading_days=1,
            repair_command=[py, "-m", "quant.cli", "update-us-market-history", "--config", cfg_arg],
        )
    )
    targets.append(
        FreshnessTarget(
            label="港股日线",
            db_path=hk_db,
            table="hk_daily_bars",
            date_column="date",
            cadence="trading",
            calendar_db=hk_db,
            calendar_table="hk_daily_bars",
            lag_trading_days=1,
            repair_command=[py, "-m", "quant.cli", "update-hk-market-history", "--config", cfg_arg],
        )
    )
    targets.append(
        FreshnessTarget(
            label="欧股日线",
            db_path=eu_db,
            table="euro_daily_bars",
            date_column="date",
            cadence="trading",
            calendar_db=eu_db,
            calendar_table="euro_daily_bars",
            lag_trading_days=1,
            repair_command=[py, "-m", "quant.cli", "update-europe-market-history", "--config", cfg_arg],
        )
    )
    targets.append(
        FreshnessTarget(
            label="ETF历史",
            db_path=etf_db,
            table="market_etf_daily_bars",
            date_column="date",
            cadence="trading",
            calendar_db=cn_calendar_db,
            calendar_table=cn_calendar_table,
            repair_command=[py, "-m", "quant.cli", "backfill-etf-history", "--config", cfg_arg],
        )
    )
    targets.append(
        FreshnessTarget(
            label="跨市场参考",
            db_path=cross_db,
            table="cross_market_reference_daily",
            date_column="date",
            cadence="daily",
            repair_command=[py, "-m", "quant.cli", "update-cross-market-reference-history", "--config", cfg_arg],
        )
    )
    return targets


def run_governance_pass(
    *,
    root: Path,
    cfg: dict[str, Any],
    as_of: date | None = None,
    repair: bool = True,
    check_only: bool = False,
) -> GovernanceResult:
    as_of = as_of or date.today()
    targets = _build_targets(root, cfg)
    findings: list[FreshnessFinding] = []
    repaired = 0
    repair_failed = 0

    for target in targets:
        latest = ""
        status = "error"
        detail = ""
        if not target.db_path.exists():
            status = "missing_table"
            detail = f"db missing: {target.db_path}"
        else:
            try:
                with sqlite3.connect(f"file:{target.db_path}?mode=ro", uri=True) as conn:
                    if not _table_exists(conn, target.table):
                        status = "missing_table"
                        detail = f"table missing: {target.table}"
                    else:
                        row = _scalar(conn, target.sql())
                        latest = str(row[0]) if row and row[0] else ""
                        status = "ok"  # 读到了数据（latest 可能为空 → 下面判 empty）
            except sqlite3.Error as exc:
                status = "error"
                detail = f"{type(exc).__name__}: {exc}"

        expected = _expected_date(target, as_of)
        if status in {"missing_table", "error"}:
            pass
        elif not latest:
            status = "empty"
        elif latest >= expected:
            status = "fresh"
        else:
            status = "stale"

        finding = FreshnessFinding(target=target, latest=latest, expected=expected, status=status, detail=detail)
        findings.append(finding)

        if status == "stale" and not check_only and repair and target.repair_command:
            # __LATEST__ → 该表本地最新日期；__END__ → as_of（skip_existing 只补缺失段）。
            command = [
                part.replace("__LATEST__", latest or as_of.isoformat()).replace("__END__", as_of.isoformat())
                for part in target.repair_command
            ]
            rc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if rc.returncode == 0:
                repaired += 1
            else:
                repair_failed += 1
                finding.detail += f" repair_exit={rc.returncode}"

    checked = len(findings)
    fresh = sum(1 for f in findings if f.status == "fresh")
    stale = sum(1 for f in findings if f.status == "stale")
    empty = sum(1 for f in findings if f.status == "empty")
    errors = sum(1 for f in findings if f.status in {"missing_table", "error"})

    from quant.data_governance.db_journal import migrate_journal_modes

    journal = migrate_journal_modes(root / "data")

    return GovernanceResult(
        checked=checked,
        fresh=fresh,
        stale=stale,
        empty=empty,
        errors=errors,
        repaired=repaired,
        repair_failed=repair_failed,
        findings=findings,
        journal=journal,
    )