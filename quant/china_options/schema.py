from __future__ import annotations

import sqlite3
from pathlib import Path


INDEX_ID = "CN_PANIC_HO30"

_RATES_DDL = """
CREATE TABLE china_option_rates (
    rate_date TEXT NOT NULL,
    tenor TEXT NOT NULL,
    rate REAL NOT NULL,
    observed_at TEXT NOT NULL,
    source TEXT NOT NULL,
    PRIMARY KEY (rate_date, tenor, source, observed_at)
)
"""

_INDEX_VALUES_DDL = """
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
    PRIMARY KEY (index_id, trade_date, available_at)
)
"""


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def _primary_key_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [str(row[1]) for row in sorted(rows, key=lambda row: int(row[5])) if int(row[5]) > 0]


def _migrate_publication_key(
    conn: sqlite3.Connection,
    *,
    table: str,
    expected_primary_key: list[str],
    create_sql: str,
    columns: list[str],
) -> None:
    if not _table_exists(conn, table) or _primary_key_columns(conn, table) == expected_primary_key:
        return
    legacy_table = f"{table}_legacy_v1"
    conn.execute(f"DROP TABLE IF EXISTS {legacy_table}")
    conn.execute(f"ALTER TABLE {table} RENAME TO {legacy_table}")
    conn.execute(create_sql)
    column_list = ", ".join(columns)
    conn.execute(
        f"INSERT INTO {table} ({column_list}) SELECT {column_list} FROM {legacy_table}"
    )
    conn.execute(f"DROP TABLE {legacy_table}")


def initialize_china_options_database(database_path: Path) -> Path:
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as conn:
        _migrate_publication_key(
            conn,
            table="china_option_rates",
            expected_primary_key=["rate_date", "tenor", "source", "observed_at"],
            create_sql=_RATES_DDL,
            columns=["rate_date", "tenor", "rate", "observed_at", "source"],
        )
        _migrate_publication_key(
            conn,
            table="china_option_index_values",
            expected_primary_key=["index_id", "trade_date", "available_at"],
            create_sql=_INDEX_VALUES_DDL,
            columns=[
                "index_id", "trade_date", "value", "available_at", "source",
                "quality_flags_json", "calculation_json", "near_expiry",
                "next_expiry", "quote_count",
            ],
        )
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS china_option_quotes (
                trade_date TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                market TEXT NOT NULL,
                underlying TEXT NOT NULL,
                expiry_month TEXT NOT NULL,
                expiry_date TEXT NOT NULL,
                contract TEXT NOT NULL,
                option_type TEXT NOT NULL CHECK(option_type IN ('C', 'P')),
                strike REAL NOT NULL,
                last_price REAL,
                bid REAL,
                ask REAL,
                bid_volume REAL,
                ask_volume REAL,
                volume REAL,
                open_interest REAL,
                source TEXT NOT NULL,
                PRIMARY KEY (trade_date, contract, observed_at)
            );
            CREATE INDEX IF NOT EXISTS idx_china_option_quotes_chain
                ON china_option_quotes(trade_date, underlying, expiry_date, strike, option_type);

            CREATE TABLE IF NOT EXISTS china_option_rates (
                rate_date TEXT NOT NULL, tenor TEXT NOT NULL, rate REAL NOT NULL,
                observed_at TEXT NOT NULL, source TEXT NOT NULL,
                PRIMARY KEY (rate_date, tenor, source, observed_at)
            );

            CREATE TABLE IF NOT EXISTS china_option_index_meta (
                index_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                methodology TEXT NOT NULL,
                underlying TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS china_option_index_values (
                index_id TEXT NOT NULL, trade_date TEXT NOT NULL, value REAL NOT NULL,
                available_at TEXT NOT NULL, source TEXT NOT NULL,
                quality_flags_json TEXT NOT NULL, calculation_json TEXT NOT NULL,
                near_expiry TEXT NOT NULL, next_expiry TEXT NOT NULL,
                quote_count INTEGER NOT NULL,
                PRIMARY KEY (index_id, trade_date, available_at)
            );
            CREATE INDEX IF NOT EXISTS idx_china_option_index_visible
                ON china_option_index_values(index_id, available_at);

            CREATE TABLE IF NOT EXISTS china_option_ingestion_runs (
                run_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                trade_date TEXT NOT NULL,
                status TEXT NOT NULL,
                source TEXT NOT NULL,
                fetched_months INTEGER NOT NULL DEFAULT 0,
                fetched_quotes INTEGER NOT NULL DEFAULT 0,
                index_value REAL,
                error_summary TEXT NOT NULL DEFAULT '',
                details_json TEXT NOT NULL DEFAULT '{}'
            );
            """
        )
        conn.execute("PRAGMA user_version=2")
        conn.execute(
            """
            INSERT INTO china_option_index_meta (
                index_id, name, description, methodology, underlying
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(index_id) DO UPDATE SET
                name=excluded.name,
                description=excluded.description,
                methodology=excluded.methodology,
                underlying=excluded.underlying,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                INDEX_ID,
                "A股恐慌指数（HO 30日隐含波动率）",
                "基于上证50股指期权（HO）可执行报价计算的30日预期波动率。",
                "CBOE VIX离散方差公式、K0双边均价、OTM报价筛选及30日分钟加权插值。",
                "HO（上证50股指期权）",
            ),
        )
        conn.commit()
    return database_path
