from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from quant.ai_corpus import fetch_ai_corpus, fetch_cninfo_announcements, parse_cninfo_announcements
from quant.cli_commands.ai_corpus import handle_ai_corpus_command


FIXTURE_DIR = Path("tests/fixtures/ai_corpus/cninfo")


def _write_config(root: Path) -> Path:
    config_path = root / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "quant:",
                "  ai_corpus:",
                "    database_path: data/ai_corpus/ai_corpus.sqlite",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return config_path


def test_parse_cninfo_announcements_classifies_and_filters_events() -> None:
    import pandas as pd

    frame = pd.read_csv(FIXTURE_DIR / "cninfo_announcements.csv")
    rows = parse_cninfo_announcements(frame, event_type="trading_risk_warning", raw_path=Path("raw.json"))

    assert len(rows) == 1
    assert rows[0]["event_type"] == "trading_risk_warning"
    assert rows[0]["source_id"] == "1212345679"
    assert rows[0]["symbols"] == "600519"
    assert "交易风险提示" in rows[0]["title"]
    assert "可转债适当性" not in rows[0]["title"]


def test_parse_cninfo_risk_events_keeps_specific_event_types() -> None:
    import pandas as pd

    frame = pd.read_csv(FIXTURE_DIR / "cninfo_announcements.csv")
    rows = parse_cninfo_announcements(frame, event_type="risk_events", raw_path=Path("raw.json"))

    assert [row["event_type"] for row in rows] == ["abnormal_trading", "trading_risk_warning"]
    assert [row["source_id"] for row in rows] == ["1212345678", "1212345679"]


def test_fetch_cninfo_announcements_fixture_outputs_ai_corpus_documents(tmp_path: Path) -> None:
    frame = fetch_cninfo_announcements(
        root=tmp_path,
        fixture_dir=Path.cwd() / FIXTURE_DIR,
        raw_archive_dir="raw/cninfo",
        event_type="abnormal_trading",
        limit=10,
    )

    assert len(frame) == 1
    row = frame.iloc[0].to_dict()
    assert row["provider"] == "cninfo"
    assert row["corpus_type"] == "announcement"
    assert row["event_type"] == "abnormal_trading"
    assert row["published_at"] == "2026-07-02"
    assert row["parse_status"] == "ok"
    assert Path(row["raw_path"]).exists()


def test_fetch_ai_corpus_routes_cninfo_provider(tmp_path: Path) -> None:
    frame = fetch_ai_corpus(
        provider="cninfo",
        root=tmp_path,
        fixture_dir=Path.cwd() / FIXTURE_DIR,
        raw_archive_dir="raw/cninfo",
        event_type="earnings_forecast",
        limit=10,
    )

    assert len(frame) == 1
    assert frame.iloc[0]["event_type"] == "earnings_forecast"
    assert frame.iloc[0]["symbols"] == "300750"


def test_ai_corpus_fetch_cli_accepts_cninfo_fixture_provider(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    output_csv = tmp_path / "out/cninfo.csv"

    exit_code = handle_ai_corpus_command(
        argparse.Namespace(
            cmd="ai-corpus",
            ai_corpus_cmd="fetch",
            config=str(config_path),
            provider="cninfo",
            event_type="abnormal_trading",
            org=None,
            ptype=None,
            keyword=None,
            symbols=None,
            date=None,
            start_date="2026-07-02",
            end_date="2026-07-03",
            limit=10,
            min_rows=1,
            fields="published_at,title,event_type,provider,source_id,symbols,url",
            fixture_dir=str(Path.cwd() / FIXTURE_DIR),
            database_path=None,
            raw_archive_dir=None,
            reference_dir=None,
            refresh_reference=False,
            output_csv=str(output_csv),
            no_content=False,
            full_program_only=False,
            probe_before_fetch=False,
        ),
        parser=argparse.ArgumentParser(),
    )

    assert exit_code == 0
    assert "异常波动" in output_csv.read_text(encoding="utf-8-sig")
    db_path = tmp_path / "data/ai_corpus/ai_corpus.sqlite"
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM ai_corpus_documents").fetchone()[0]
    assert count == 1

    second_exit_code = handle_ai_corpus_command(
        argparse.Namespace(
            cmd="ai-corpus",
            ai_corpus_cmd="fetch",
            config=str(config_path),
            provider="cninfo",
            event_type="abnormal_trading",
            org=None,
            ptype=None,
            keyword=None,
            symbols=None,
            date=None,
            start_date="2026-07-02",
            end_date="2026-07-03",
            limit=10,
            min_rows=1,
            fields=None,
            fixture_dir=str(Path.cwd() / FIXTURE_DIR),
            database_path=None,
            raw_archive_dir=None,
            reference_dir=None,
            refresh_reference=False,
            output_csv=None,
            no_content=False,
            full_program_only=False,
            probe_before_fetch=False,
        ),
        parser=argparse.ArgumentParser(),
    )

    assert second_exit_code == 0
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM ai_corpus_documents").fetchone()[0]
    assert count == 1
