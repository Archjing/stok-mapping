from __future__ import annotations

import json
import math
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest

from quant.china_options.ho_provider import (
    ChinaOptionsProviderError,
    expiry_date_for_month,
    normalize_ho_chain,
)
from quant.china_options.ho_vix import (
    InsufficientOptionDataError,
    OptionQuote,
    calculate_30_day_index,
    calculate_term_variance,
)
from quant.china_options.schema import initialize_china_options_database
from quant.china_options.service import load_panic_observation
from quant.china_options.service import update_ho_options_from_config


def _quote(expiry: date, option_type: str, strike: float, bid: float, ask: float) -> OptionQuote:
    return OptionQuote(
        trade_date=date(2026, 8, 12),
        expiry_date=expiry,
        contract=f"HO{expiry:%y%m}{option_type}{int(strike)}",
        option_type=option_type,
        strike=strike,
        bid=bid,
        ask=ask,
    )


def _term_quotes(expiry: date) -> list[OptionQuote]:
    return [
        _quote(expiry, "C", 90, 12, 12),
        _quote(expiry, "P", 90, 1, 1),
        _quote(expiry, "C", 100, 6, 6),
        _quote(expiry, "P", 100, 5, 5),
        _quote(expiry, "C", 110, 2, 2),
        _quote(expiry, "P", 110, 10, 10),
    ]


def test_schema_initialization_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "china_options.sqlite"

    initialize_china_options_database(database)
    initialize_china_options_database(database)

    with sqlite3.connect(database) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        meta = conn.execute(
            "SELECT name FROM china_option_index_meta WHERE index_id='CN_PANIC_HO30'"
        ).fetchone()
    assert {
        "china_option_quotes",
        "china_option_rates",
        "china_option_index_meta",
        "china_option_index_values",
        "china_option_ingestion_runs",
    } <= tables
    assert meta == ("A股恐慌指数（HO 30日隐含波动率）",)


def test_schema_initialization_migrates_legacy_publication_keys(tmp_path: Path) -> None:
    database = tmp_path / "china_options.sqlite"
    with sqlite3.connect(database) as conn:
        conn.executescript(
            """
            CREATE TABLE china_option_rates (
                rate_date TEXT NOT NULL,
                tenor TEXT NOT NULL,
                rate REAL NOT NULL,
                observed_at TEXT NOT NULL,
                source TEXT NOT NULL,
                PRIMARY KEY (rate_date, tenor, source)
            );
            CREATE TABLE china_option_index_values (
                index_id TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                value REAL NOT NULL,
                available_at TEXT NOT NULL,
                source TEXT NOT NULL,
                quality_flags_json TEXT NOT NULL,
                calculation_json TEXT NOT NULL,
                near_expiry TEXT NOT NULL,
                next_expiry TEXT NOT NULL,
                quote_count INTEGER NOT NULL,
                PRIMARY KEY (index_id, trade_date)
            );
            INSERT INTO china_option_rates VALUES (
                '2026-08-11', '3M', 0.0143, '2026-08-11T15:10:00+08:00', 'test'
            );
            INSERT INTO china_option_index_values VALUES (
                'CN_PANIC_HO30', '2026-08-11', 24.5,
                '2026-08-11T15:10:00+08:00', 'test', '[]', '{}',
                '2026-08-21', '2026-09-18', 60
            );
            """
        )

    initialize_china_options_database(database)

    with sqlite3.connect(database) as conn:
        rate_pk = [
            row[1]
            for row in sorted(
                conn.execute("PRAGMA table_info(china_option_rates)"),
                key=lambda row: row[5],
            )
            if row[5]
        ]
        index_pk = [
            row[1]
            for row in sorted(
                conn.execute("PRAGMA table_info(china_option_index_values)"),
                key=lambda row: row[5],
            )
            if row[5]
        ]
        assert conn.execute("SELECT COUNT(*) FROM china_option_rates").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM china_option_index_values").fetchone()[0] == 1
    assert rate_pk == ["rate_date", "tenor", "source", "observed_at"]
    assert index_pk == ["index_id", "trade_date", "available_at"]


def test_index_values_keep_same_day_publication_history(tmp_path: Path) -> None:
    database = tmp_path / "china_options.sqlite"
    initialize_china_options_database(database)
    with sqlite3.connect(database) as conn:
        for available_at, value in [
            ("2026-08-11T15:10:00+08:00", 24.0),
            ("2026-08-11T15:20:00+08:00", 26.0),
        ]:
            conn.execute(
                """
                INSERT INTO china_option_index_values (
                    index_id, trade_date, value, available_at, source, quality_flags_json,
                    calculation_json, near_expiry, next_expiry, quote_count
                ) VALUES ('CN_PANIC_HO30', '2026-08-11', ?, ?, 'test', '[]', '{}',
                          '2026-08-21', '2026-09-18', 60)
                """,
                (value, available_at),
            )
        conn.commit()

    early = load_panic_observation(
        database,
        decision_at=datetime.fromisoformat("2026-08-11T15:15:00+08:00"),
    )
    late = load_panic_observation(
        database,
        decision_at=datetime.fromisoformat("2026-08-11T15:25:00+08:00"),
    )

    assert early.value == 24.0
    assert late.value == 26.0


def test_provider_mapping_preserves_bid_ask_volume_semantics() -> None:
    frame = pd.DataFrame(
        {
            "行权价": [2500],
            "看涨合约-最新价": [101.2],
            "看涨合约-买价": [100.8],
            "看涨合约-卖价": [101.6],
            "看涨合约-买量": [12],
            "看涨合约-卖量": [15],
            "看涨合约-成交量": [230],
            "看涨合约-持仓量": [910],
            "看跌合约-最新价": [88.2],
            "看跌合约-买价": [87.8],
            "看跌合约-卖价": [88.6],
            "看跌合约-买量": [21],
            "看跌合约-卖量": [25],
            "看跌合约-成交量": [180],
            "看跌合约-持仓量": [810],
        }
    )

    rows = normalize_ho_chain(
        frame,
        month="ho2609",
        trade_date=date(2026, 8, 12),
        expiry_date=date(2026, 9, 18),
        observed_at=datetime(2026, 8, 12, 15, 5),
    )

    call, put = rows
    assert call.contract == "HO2609C2500"
    assert (call.bid_volume, call.ask_volume, call.volume, call.open_interest) == (12, 15, 230, 910)
    assert put.option_type == "P"
    assert (put.bid_volume, put.ask_volume, put.volume, put.open_interest) == (21, 25, 180, 810)


def test_expiry_date_rolls_forward_to_next_open_session() -> None:
    closed = {date(2026, 9, 18), date(2026, 9, 21)}

    expiry = expiry_date_for_month(
        "2609",
        is_open_date=lambda day: day.weekday() < 5 and day not in closed,
    )

    assert expiry == date(2026, 9, 22)


def test_term_variance_uses_unique_strikes_and_call_put_average_at_k0() -> None:
    expiry = date(2026, 9, 1)
    result = calculate_term_variance(
        _term_quotes(expiry),
        valuation_at=datetime(2026, 8, 12, 15, 0),
        settlement_at=datetime(2026, 9, 1, 15, 0),
        risk_free_rate=0.01,
    )

    assert result.k0 == 100
    assert result.forward == pytest.approx(101.0005480954)
    assert result.variance == pytest.approx(0.3044831010)
    assert result.used_strikes == (90.0, 100.0, 110.0)
    assert result.quote_count == 3


def test_30_day_index_uses_cboe_time_weighted_variance() -> None:
    near_expiry = date(2026, 9, 1)
    next_expiry = date(2026, 9, 21)
    result = calculate_30_day_index(
        _term_quotes(near_expiry) + _term_quotes(next_expiry),
        valuation_at=datetime(2026, 8, 12, 15, 0),
        settlement_times={
            near_expiry: datetime(2026, 9, 1, 15, 0),
            next_expiry: datetime(2026, 9, 21, 15, 0),
        },
        risk_free_rate=0.01,
        target_days=30,
    )

    n1, n2, n30 = 20 * 1440, 40 * 1440, 30 * 1440
    expected_variance = (
        result.near.variance * (n2 - n30) / (n2 - n1) * (n1 / 525600)
        + result.next.variance * (n30 - n1) / (n2 - n1) * (n2 / 525600)
    ) * 525600 / n30
    assert result.value == pytest.approx(100 * math.sqrt(expected_variance))
    assert result.quality_flags == ()


def test_30_day_index_rejects_incomplete_chain() -> None:
    expiry = date(2026, 9, 1)
    with pytest.raises(InsufficientOptionDataError):
        calculate_30_day_index(
            [_quote(expiry, "C", 100, 1, 2)],
            valuation_at=datetime(2026, 8, 12, 15, 0),
            settlement_times={expiry: datetime(2026, 9, 1, 15, 0)},
            risk_free_rate=0.01,
        )


def test_panic_observation_is_strictly_prior_to_cn_open_and_reports_freshness(tmp_path: Path) -> None:
    database = tmp_path / "china_options.sqlite"
    initialize_china_options_database(database)
    with sqlite3.connect(database) as conn:
        conn.execute(
            """
            INSERT INTO china_option_index_values (
                index_id, trade_date, value, available_at, source, quality_flags_json,
                calculation_json, near_expiry, next_expiry, quote_count
            ) VALUES (?, ?, ?, ?, ?, '[]', '{}', ?, ?, ?)
            """,
            (
                "CN_PANIC_HO30",
                "2026-08-11",
                24.5,
                "2026-08-11T15:10:00+08:00",
                "test",
                "2026-08-21",
                "2026-09-18",
                60,
            ),
        )
        conn.execute(
            """
            INSERT INTO china_option_index_values (
                index_id, trade_date, value, available_at, source, quality_flags_json,
                calculation_json, near_expiry, next_expiry, quote_count
            ) VALUES (?, ?, ?, ?, ?, '[]', '{}', ?, ?, ?)
            """,
            (
                "CN_PANIC_HO30",
                "2026-08-12",
                99.0,
                "2026-08-12T15:10:00+08:00",
                "test",
                "2026-08-21",
                "2026-09-18",
                60,
            ),
        )
        conn.commit()

    observation = load_panic_observation(
        database,
        decision_at=datetime.fromisoformat("2026-08-12T09:30:00+08:00"),
        threshold=25.0,
        max_staleness_days=3,
    )

    assert observation.value == 24.5
    assert observation.trade_date == date(2026, 8, 11)
    assert observation.fresh is True
    assert observation.would_block is False


def test_panic_observation_visible_at_exact_publication_time(tmp_path: Path) -> None:
    database = tmp_path / "china_options.sqlite"
    initialize_china_options_database(database)
    with sqlite3.connect(database) as conn:
        conn.execute(
            """
            INSERT INTO china_option_index_values (
                index_id, trade_date, value, available_at, source, quality_flags_json,
                calculation_json, near_expiry, next_expiry, quote_count
            ) VALUES ('CN_PANIC_HO30', '2026-08-11', 25.5,
                      '2026-08-11T15:10:00+08:00', 'test', '[]', '{}',
                      '2026-08-21', '2026-09-18', 60)
            """
        )
        conn.commit()

    observation = load_panic_observation(
        database,
        decision_at=datetime.fromisoformat("2026-08-11T15:10:00+08:00"),
        threshold=25.0,
    )

    assert observation.value == 25.5
    assert observation.would_block is True


def test_successful_update_writes_quotes_rate_index_and_completed_run(tmp_path: Path) -> None:
    class Provider:
        source = "fixture"

        def list_months(self):
            return ["2608", "2609"]

        def fetch_chain(self, month, *, trade_date, expiry_date, observed_at):
            frame = pd.DataFrame(
                {
                    "行权价": [90, 100, 110],
                    "看涨合约-买价": [12, 6, 2],
                    "看涨合约-卖价": [12, 6, 2],
                    "看跌合约-买价": [1, 5, 10],
                    "看跌合约-卖价": [1, 5, 10],
                }
            )
            return normalize_ho_chain(
                frame,
                month=month,
                trade_date=trade_date,
                expiry_date=expiry_date,
                observed_at=observed_at,
            )

        def fetch_shibor_3m(self):
            return 0.015

    result = update_ho_options_from_config(
        {"china_options": {"path": "data/china_options.sqlite", "target_days": 30}},
        tmp_path,
        as_of=date(2026, 8, 12),
        observed_at=datetime.fromisoformat("2026-08-12T15:10:00+08:00"),
        provider=Provider(),
    )

    assert result.ok is True
    assert result.fetched_months == 2
    assert result.fetched_quotes == 12
    assert result.index_value is not None
    with sqlite3.connect(tmp_path / "data/china_options.sqlite") as conn:
        assert conn.execute("SELECT COUNT(*) FROM china_option_quotes").fetchone()[0] == 12
        assert conn.execute("SELECT COUNT(*) FROM china_option_rates").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM china_option_index_values").fetchone()[0] == 1
        run = conn.execute(
            "SELECT status, fetched_months, fetched_quotes, index_value "
            "FROM china_option_ingestion_runs"
        ).fetchone()
    assert run[0:3] == ("complete", 2, 12)
    assert run[3] == pytest.approx(result.index_value)


def test_live_provider_rejects_historical_as_of(monkeypatch, tmp_path: Path) -> None:
    class Provider:
        source = "live-fixture"

    monkeypatch.setattr("quant.china_options.service.AkshareHoProvider", Provider)

    with pytest.raises(ChinaOptionsProviderError, match="cannot be used for historical backfill"):
        update_ho_options_from_config(
            {"china_options": {"path": "data/china_options.sqlite"}},
            tmp_path,
            as_of=date(2026, 8, 11),
            observed_at=datetime.fromisoformat("2026-08-12T15:10:00+08:00"),
        )
    assert not (tmp_path / "data/china_options.sqlite").exists()


def test_live_provider_rejects_collection_before_cn_close(monkeypatch, tmp_path: Path) -> None:
    class Provider:
        source = "live-fixture"

    monkeypatch.setattr("quant.china_options.service.AkshareHoProvider", Provider)

    with pytest.raises(ChinaOptionsProviderError, match="after the CN market close"):
        update_ho_options_from_config(
            {"china_options": {"path": "data/china_options.sqlite"}},
            tmp_path,
            observed_at=datetime.fromisoformat("2026-08-12T09:00:00+08:00"),
        )
    assert not (tmp_path / "data/china_options.sqlite").exists()


def test_ho30_rejects_non_30_day_target(tmp_path: Path) -> None:
    class Provider:
        source = "fixture"

    with pytest.raises(ChinaOptionsProviderError, match="requires.*remain 30"):
        update_ho_options_from_config(
            {
                "china_options": {
                    "path": "data/china_options.sqlite",
                    "target_days": 20,
                }
            },
            tmp_path,
            observed_at=datetime.fromisoformat("2026-08-12T15:10:00+08:00"),
            provider=Provider(),
        )


def test_failed_calculation_preserves_raw_quotes_and_does_not_write_index(tmp_path: Path) -> None:
    class Provider:
        source = "fixture"

        def list_months(self):
            return ["2608", "2609"]

        def fetch_chain(self, month, *, trade_date, expiry_date, observed_at):
            frame = pd.DataFrame(
                {
                    "行权价": [2500],
                    "看涨合约-买价": [10], "看涨合约-卖价": [11],
                    "看跌合约-买价": [9], "看跌合约-卖价": [10],
                }
            )
            return normalize_ho_chain(
                frame,
                month=month,
                trade_date=trade_date,
                expiry_date=expiry_date,
                observed_at=observed_at,
            )

        def fetch_shibor_3m(self):
            return 0.015

    with pytest.raises(InsufficientOptionDataError):
        update_ho_options_from_config(
            {"china_options": {"path": "data/china_options.sqlite"}},
            tmp_path,
            as_of=date(2026, 8, 12),
            observed_at=datetime.fromisoformat("2026-08-12T15:10:00+08:00"),
            provider=Provider(),
        )

    with sqlite3.connect(tmp_path / "data/china_options.sqlite") as conn:
        assert conn.execute("SELECT COUNT(*) FROM china_option_quotes").fetchone()[0] == 4
        assert conn.execute("SELECT COUNT(*) FROM china_option_index_values").fetchone()[0] == 0
        status, months, quotes, details = conn.execute(
            "SELECT status, fetched_months, fetched_quotes, details_json "
            "FROM china_option_ingestion_runs"
        ).fetchone()
    assert status == "failed"
    assert (months, quotes) == (2, 4)
    assert json.loads(details)["failure_stage"] == "calculate_index"
