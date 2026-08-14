from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from quant.china_options.ho_provider import (
    AkshareHoProvider,
    ChinaOptionsProviderError,
    HoQuoteRow,
    expiry_date_for_month,
)
from quant.china_options.ho_vix import (
    Ho30IndexResult,
    InsufficientOptionDataError,
    OptionQuote,
    calculate_30_day_index,
)
from quant.china_options.schema import INDEX_ID, initialize_china_options_database


CHINA_TZ = ZoneInfo("Asia/Shanghai")
CN_MARKET_CLOSE = time(15, 0)


@dataclass(frozen=True)
class ChinaOptionsUpdateResult:
    status: str
    database_path: Path
    trade_date: date
    fetched_months: int
    fetched_quotes: int
    index_value: float | None
    near_expiry: date | None
    next_expiry: date | None
    source: str
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status == "complete"


@dataclass(frozen=True)
class PanicObservation:
    value: float | None
    trade_date: date | None
    available_at: datetime | None
    fresh: bool
    staleness_days: int | None
    threshold: float
    would_block: bool
    unavailable_reason: str = ""


def _resolve_database_path(config: dict[str, Any], project_root: Path) -> Path:
    cfg = dict(config.get("china_options", {}) or {})
    path = Path(str(cfg.get("path", "data/china_options.sqlite")))
    return path if path.is_absolute() else project_root / path


def _resolve_cn_open_date_checker(
    config: dict[str, Any],
    project_root: Path,
    *,
    required: bool,
):
    cfg = dict(config.get("local_history", {}) or {})
    path = Path(str(cfg.get("path", "data/a_share_history.sqlite")))
    database_path = path if path.is_absolute() else project_root / path
    table = str(cfg.get("calendar_table", "trading_calendar"))
    if not table.replace("_", "").isalnum():
        raise ChinaOptionsProviderError(f"invalid CN trading calendar table: {table}")
    if not database_path.exists() or database_path.stat().st_size == 0:
        if required:
            raise ChinaOptionsProviderError(
                f"CN trading calendar is required for live HO expiry dates: {database_path}"
            )
        return None
    with sqlite3.connect(database_path) as conn:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
    if exists is None:
        if required:
            raise ChinaOptionsProviderError(
                f"CN trading calendar table is missing: {database_path}:{table}"
            )
        return None

    def is_open_date(day: date) -> bool:
        with sqlite3.connect(database_path) as conn:
            row = conn.execute(
                f"SELECT MAX(is_open) FROM {table} WHERE date=?",
                (day.isoformat(),),
            ).fetchone()
        if row is None or row[0] is None:
            raise ChinaOptionsProviderError(
                f"CN trading calendar has no row for HO expiry candidate {day.isoformat()}"
            )
        return int(row[0]) == 1

    return is_open_date


def _insert_quotes(conn: sqlite3.Connection, rows: list[HoQuoteRow]) -> None:
    conn.executemany(
        """
        INSERT OR REPLACE INTO china_option_quotes (
            trade_date, observed_at, market, underlying, expiry_month, expiry_date,
            contract, option_type, strike, last_price, bid, ask, bid_volume,
            ask_volume, volume, open_interest, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row.trade_date.isoformat(),
                row.observed_at.isoformat(),
                row.market,
                row.underlying,
                row.expiry_month,
                row.expiry_date.isoformat(),
                row.contract,
                row.option_type,
                row.strike,
                row.last_price,
                row.bid,
                row.ask,
                row.bid_volume,
                row.ask_volume,
                row.volume,
                row.open_interest,
                row.source,
            )
            for row in rows
        ],
    )


def _as_calculation_quotes(rows: list[HoQuoteRow]) -> list[OptionQuote]:
    return [
        OptionQuote(
            trade_date=row.trade_date,
            expiry_date=row.expiry_date,
            contract=row.contract,
            option_type=row.option_type,
            strike=row.strike,
            bid=row.bid,
            ask=row.ask,
            last_price=row.last_price,
        )
        for row in rows
    ]


def update_ho_options_from_config(
    config: dict[str, Any],
    project_root: Path,
    *,
    as_of: date | None = None,
    provider: Any | None = None,
    observed_at: datetime | None = None,
) -> ChinaOptionsUpdateResult:
    cfg = dict(config.get("china_options", {}) or {})
    now = observed_at or datetime.now(CHINA_TZ)
    if now.tzinfo is None:
        now = now.replace(tzinfo=CHINA_TZ)
    else:
        now = now.astimezone(CHINA_TZ)
    provider_injected = provider is not None
    trade_date = as_of or now.date()
    if not provider_injected and trade_date != now.date():
        raise ChinaOptionsProviderError(
            "the live HO endpoint only exposes the current snapshot; "
            "--as-of cannot be used for historical backfill"
        )
    if not provider_injected and now.time() < CN_MARKET_CLOSE:
        raise ChinaOptionsProviderError(
            "live HO collection is only allowed after the CN market close at 15:00 Asia/Shanghai"
        )
    database_path = _resolve_database_path(config, project_root)
    initialize_china_options_database(database_path)
    provider = provider or AkshareHoProvider()
    run_id = str(uuid.uuid4())
    source = str(getattr(provider, "source", "unknown"))
    overrides = dict(cfg.get("expiry_overrides", {}) or {})
    is_open_date = _resolve_cn_open_date_checker(
        config,
        project_root,
        required=not provider_injected,
    )
    max_terms = max(2, int(cfg.get("max_terms", 4)))
    target_days = max(1, int(cfg.get("target_days", 30)))
    if target_days != 30:
        raise ChinaOptionsProviderError(
            "CN_PANIC_HO30 requires china_options.target_days to remain 30"
        )
    started_at = now.isoformat()

    with sqlite3.connect(database_path) as conn:
        conn.execute(
            """
            INSERT INTO china_option_ingestion_runs (
                run_id, started_at, trade_date, status, source
            ) VALUES (?, ?, ?, 'running', ?)
            """,
            (run_id, started_at, trade_date.isoformat(), source),
        )
        conn.commit()

    successful_months: list[str] = []
    rows: list[HoQuoteRow] = []
    failure_stage = "list_months"
    try:
        months = provider.list_months()
        candidates: list[tuple[str, date]] = []
        failure_stage = "resolve_expiry_dates"
        for month in months:
            expiry = expiry_date_for_month(
                month,
                overrides,
                is_open_date=is_open_date,
            )
            if expiry >= trade_date:
                candidates.append((month, expiry))
        candidates = sorted(candidates, key=lambda item: item[1])[:max_terms]
        if len(candidates) < 2:
            raise ChinaOptionsProviderError("fewer than two future HO terms are available")

        failure_stage = "fetch_chains"
        for month, expiry in candidates:
            month_rows = provider.fetch_chain(
                month,
                trade_date=trade_date,
                expiry_date=expiry,
                observed_at=now,
            )
            rows.extend(month_rows)
            successful_months.append(month)
            with sqlite3.connect(database_path) as conn:
                _insert_quotes(conn, month_rows)
                conn.execute(
                    """
                    UPDATE china_option_ingestion_runs
                    SET fetched_months=?, fetched_quotes=?, details_json=?
                    WHERE run_id=?
                    """,
                    (
                        len(successful_months),
                        len(rows),
                        json.dumps(
                            {
                                "stage": "fetch_chains",
                                "successful_months": successful_months,
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        run_id,
                    ),
                )
                conn.commit()
        failure_stage = "fetch_rate"
        risk_free_rate = float(provider.fetch_shibor_3m())
        # Preserve the raw snapshot even when the derived index cannot be
        # calculated. This keeps provider and calculation failures auditable.
        with sqlite3.connect(database_path) as conn:
            conn.execute(
                """
                INSERT INTO china_option_rates (
                    rate_date, tenor, rate, observed_at, source
                ) VALUES (?, '3M', ?, ?, ?)
                """,
                (trade_date.isoformat(), risk_free_rate, now.isoformat(), source),
            )
            conn.commit()
        failure_stage = "calculate_index"
        settlement_times = {
            expiry: datetime.combine(expiry, time(15, 0), tzinfo=CHINA_TZ)
            for _, expiry in candidates
        }
        result = calculate_30_day_index(
            _as_calculation_quotes(rows),
            valuation_at=now,
            settlement_times=settlement_times,
            risk_free_rate=risk_free_rate,
            target_days=target_days,
        )

        published_at = datetime.now(CHINA_TZ)
        with sqlite3.connect(database_path) as conn:
            conn.execute(
                """
                INSERT INTO china_option_index_values (
                    index_id, trade_date, value, available_at, source,
                    quality_flags_json, calculation_json, near_expiry,
                    next_expiry, quote_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    INDEX_ID,
                    trade_date.isoformat(),
                    result.value,
                    published_at.isoformat(),
                    source,
                    json.dumps(result.quality_flags, ensure_ascii=False),
                    json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True),
                    result.near.expiry_date.isoformat(),
                    result.next.expiry_date.isoformat(),
                    result.near.quote_count + result.next.quote_count,
                ),
            )
            conn.execute(
                """
                UPDATE china_option_ingestion_runs
                SET finished_at=?, status='complete', fetched_months=?, fetched_quotes=?,
                    index_value=?, details_json=?
                WHERE run_id=?
                """,
                (
                    published_at.isoformat(),
                    len(candidates),
                    len(rows),
                    result.value,
                    json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True),
                    run_id,
                ),
            )
            conn.commit()
        return ChinaOptionsUpdateResult(
            status="complete",
            database_path=database_path,
            trade_date=trade_date,
            fetched_months=len(candidates),
            fetched_quotes=len(rows),
            index_value=result.value,
            near_expiry=result.near.expiry_date,
            next_expiry=result.next.expiry_date,
            source=source,
        )
    except Exception as exc:
        details = {
            "failure_stage": failure_stage,
            "successful_months": successful_months,
        }
        with sqlite3.connect(database_path) as conn:
            conn.execute(
                """
                UPDATE china_option_ingestion_runs
                SET finished_at=?, status='failed', fetched_months=?, fetched_quotes=?,
                    error_summary=?, details_json=?
                WHERE run_id=?
                """,
                (
                    datetime.now(CHINA_TZ).isoformat(),
                    len(successful_months),
                    len(rows),
                    str(exc)[:1000],
                    json.dumps(details, ensure_ascii=False, sort_keys=True),
                    run_id,
                ),
            )
            conn.commit()
        if isinstance(exc, (ChinaOptionsProviderError, InsufficientOptionDataError)):
            raise
        raise ChinaOptionsProviderError(f"HO update failed: {exc}") from exc


def load_panic_observation(
    database_path: Path,
    *,
    decision_at: datetime,
    threshold: float = 25.0,
    max_staleness_days: int = 3,
) -> PanicObservation:
    database_path = Path(database_path)
    if not database_path.exists():
        return PanicObservation(None, None, None, False, None, threshold, False, "database_missing")
    if decision_at.tzinfo is None:
        decision_at = decision_at.replace(tzinfo=CHINA_TZ)
    with sqlite3.connect(database_path) as conn:
        row = conn.execute(
            """
            SELECT trade_date, value, available_at
            FROM china_option_index_values
            WHERE index_id=? AND available_at <= ?
            ORDER BY available_at DESC
            LIMIT 1
            """,
            (INDEX_ID, decision_at.isoformat()),
        ).fetchone()
    if row is None:
        return PanicObservation(None, None, None, False, None, threshold, False, "no_visible_observation")
    trade_date = date.fromisoformat(str(row[0]))
    available_at = datetime.fromisoformat(str(row[2]))
    staleness_days = (decision_at.date() - trade_date).days
    fresh = 0 <= staleness_days <= max_staleness_days
    value = float(row[1])
    return PanicObservation(
        value=value,
        trade_date=trade_date,
        available_at=available_at,
        fresh=fresh,
        staleness_days=staleness_days,
        threshold=threshold,
        would_block=fresh and value > threshold,
        unavailable_reason="" if fresh else "stale",
    )
