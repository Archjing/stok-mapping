from __future__ import annotations

import copy
import sqlite3
from datetime import date, datetime

import pytest

from quant.data_governance.etf_store import ensure_etf_schema
from quant.data_governance import etf_universe as universe
from quant.data_governance.etf_universe import ETFUniverseError, history_config_digest, resolve_etf_universe


@pytest.fixture
def cfg() -> dict[str, object]:
    return {"etf_history": {"catalog_max_age_days": 7, "chunk_years": 1, "max_symbols_per_run": 50, "max_tasks_per_run": 1000, "universes": {"sector_core_v1": {"sectors": {"broad_market": [{"symbol": "SH.510300"}, {"symbol": "SZ.159915"}], "semiconductor": [{"symbol": "SH.512480"}]}}}}}


@pytest.fixture
def conn():
    db = sqlite3.connect(":memory:")
    ensure_etf_schema(db)
    db.execute("INSERT INTO etf_catalog_sync_runs VALUES (?,?,?,?,?,?,?,?,?)", ("snap", "ok", "ok", "ok", 4, 0, "2026-08-10T00:00:00", "2026-08-10T00:01:00", None))
    rows = [
        ("SH.510300", "510300.SH", "L", "2012-05-28", None, "SH.000300"),
        ("SZ.159915", "159915.SZ", "L", "2011-12-09", None, "SZ.399006"),
        ("SH.512480", "512480.SH", "L", "2019-06-12", None, "CSI.931865"),
        ("SH.588000", "588000.SH", "L", "2020-09-28", None, "SH.000688"),
    ]
    for symbol, ts_code, status, listed, delisted, tracking in rows:
        db.execute("INSERT INTO market_etfs(catalog_snapshot_id,symbol,ts_code,exchange,list_status,list_date,delist_date,source,fetched_at) VALUES ('snap',?,?,?,?,?,?,?,?)", (symbol, ts_code, symbol[:2], status, listed, delisted, "test", "now"))
        db.execute("INSERT INTO market_etf_tracking_mappings VALUES ('snap',?,NULL,?,NULL,'provider_observation','test','now',NULL,NULL,0)", (symbol, tracking))
    yield db
    db.close()


def _resolve(conn, cfg, sectors=None):
    return resolve_etf_universe(conn, quant_cfg=cfg, universe_name="sector_core_v1", requested_sectors=sectors, start_date=date(2010, 1, 1), end_date=date(2026, 8, 11), now=datetime(2026, 8, 11))


def test_resolver_returns_only_three_configured_symbols(conn, cfg):
    manifest = _resolve(conn, cfg)
    assert {(row.sector, row.symbol) for row in manifest.members} == {("broad_market", "SH.510300"), ("broad_market", "SZ.159915"), ("semiconductor", "SH.512480")}
    assert "SH.588000" not in {row.symbol for row in manifest.members}


def test_sector_selection_and_lifecycle_clipping(conn, cfg):
    manifest = _resolve(conn, cfg, ["semiconductor"])
    assert [member.symbol for member in manifest.members] == ["SH.512480"]
    assert manifest.members[0].effective_start == date(2019, 6, 12)


def test_tracking_index_mismatch_fails_closed(conn, cfg):
    wrong = copy.deepcopy(cfg)
    wrong["etf_history"]["universes"]["sector_core_v1"]["sectors"]["broad_market"][0]["expected_tracking_index"] = "SH.999999"
    with pytest.raises(ETFUniverseError, match="tracking index mismatch"):
        _resolve(conn, wrong)


def test_same_symbol_in_two_sectors_fails_closed(conn, cfg):
    duplicate = copy.deepcopy(cfg)
    duplicate["etf_history"]["universes"]["sector_core_v1"]["sectors"]["semiconductor"].append({"symbol": "SH.510300"})
    with pytest.raises(ETFUniverseError, match="multiple sectors"):
        _resolve(conn, duplicate)


def test_unknown_repeated_and_unsafe_selectors_fail(conn, cfg):
    with pytest.raises(ETFUniverseError, match="unknown sector"):
        _resolve(conn, cfg, ["all"])
    with pytest.raises(ETFUniverseError, match="repeated sector"):
        _resolve(conn, cfg, ["broad_market", "broad_market"])
    bad = copy.deepcopy(cfg)
    bad["etf_history"]["universes"]["sector_core_v1"]["sectors"]["broad_market"][0]["name_contains"] = "300"
    with pytest.raises(ETFUniverseError, match="selector keys"):
        _resolve(conn, bad)


def test_delisted_without_date_and_invalid_range_fail(conn, cfg):
    conn.execute("UPDATE market_etfs SET list_status='D',delist_date=NULL WHERE symbol='SH.510300'")
    with pytest.raises(ETFUniverseError, match="delist_date"):
        _resolve(conn, cfg)
    with pytest.raises(ETFUniverseError, match="start_date"):
        resolve_etf_universe(conn, quant_cfg=cfg, universe_name="sector_core_v1", requested_sectors=None, start_date=date(2026, 8, 12), end_date=date(2026, 8, 11), now=datetime(2026, 8, 11))


def test_digest_is_stable_for_key_order_and_changes_for_membership(cfg):
    reordered = copy.deepcopy(cfg)
    reordered["etf_history"] = dict(reversed(list(reordered["etf_history"].items())))
    assert history_config_digest(cfg, "sector_core_v1") == history_config_digest(reordered, "sector_core_v1")
    changed = copy.deepcopy(cfg)
    changed["etf_history"]["universes"]["sector_core_v1"]["sectors"]["semiconductor"] = []
    assert history_config_digest(cfg, "sector_core_v1") != history_config_digest(changed, "sector_core_v1")


def test_resolve_from_config_resolves_store_and_iso_dates(tmp_path, monkeypatch, cfg):
    captured: dict[str, object] = {}
    expected = object()
    configured = copy.deepcopy(cfg)
    configured["etf_history"]["path"] = "data/etf.sqlite"
    monkeypatch.setattr(universe, "load_config", lambda path: configured)

    def fake_resolve(conn, **kwargs):
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(universe, "resolve_etf_universe", fake_resolve)
    config_path = tmp_path / "project" / "config.yaml"
    result = universe.resolve_etf_universe_from_config(
        config_path,
        universe_name="sector_core_v1",
        requested_sectors=["semiconductor"],
        start_date="2018-01-01",
        end_date="2026-08-11",
    )

    assert result is expected
    assert (config_path.parent / "data/etf.sqlite").exists()
    assert captured["universe_name"] == "sector_core_v1"
    assert captured["requested_sectors"] == ["semiconductor"]
    assert captured["start_date"] == date(2018, 1, 1)
    assert captured["end_date"] == date(2026, 8, 11)


def test_single_etf_manual_config_resolves_without_catalog_snapshot() -> None:
    cfg = {
        "etf_history": {
            "catalog_max_age_days": 7,
            "chunk_years": 1,
            "max_symbols_per_run": 50,
            "max_tasks_per_run": 1000,
            "universes": {
                "single_etf": {
                    "manifest_source": "manual_config",
                    "sectors": {
                        "semiconductor": [{
                            "symbol": "SH.512480",
                            "ts_code": "512480.SH",
                            "listed_from": "2019-06-12",
                        }],
                    },
                },
            },
        },
    }
    with sqlite3.connect(":memory:") as conn:
        ensure_etf_schema(conn)
        manifest = resolve_etf_universe(
            conn,
            quant_cfg=cfg,
            universe_name="single_etf",
            requested_sectors=None,
            start_date=date(2010, 1, 1),
            end_date=date(2026, 8, 11),
            now=datetime(2026, 8, 11),
        )

    assert manifest.manifest_source == "manual_config"
    assert manifest.catalog_snapshot_id.startswith("manual-config:")
    assert manifest.requested_sectors == ("semiconductor",)
    assert manifest.members == (
        universe.ETFManifestMember(
            "single_etf",
            "semiconductor",
            "SH.512480",
            "512480.SH",
            date(2010, 1, 1),
            date(2026, 8, 11),
            date(2019, 6, 12),
            date(2026, 8, 11),
            None,
            None,
            "not_applicable_manual_config",
        ),
    )


def test_single_etf_manual_config_fails_closed_for_ambiguous_or_invalid_metadata() -> None:
    cfg = {
        "etf_history": {
            "catalog_max_age_days": 7,
            "chunk_years": 1,
            "max_symbols_per_run": 50,
            "max_tasks_per_run": 1000,
            "universes": {
                "single_etf": {
                    "manifest_source": "manual_config",
                    "sectors": {
                        "semiconductor": [{
                            "symbol": "SH.512480",
                            "ts_code": "512480.SH",
                            "listed_from": "2019-06-12",
                        }],
                    },
                },
            },
        },
    }
    with sqlite3.connect(":memory:") as conn:
        ensure_etf_schema(conn)
        duplicate = copy.deepcopy(cfg)
        duplicate["etf_history"]["universes"]["single_etf"]["sectors"]["semiconductor"].append({
            "symbol": "SH.510300", "ts_code": "510300.SH", "listed_from": "2012-05-28",
        })
        with pytest.raises(ETFUniverseError, match="exactly one ETF"):
            resolve_etf_universe(
                conn, quant_cfg=duplicate, universe_name="single_etf", requested_sectors=None,
                start_date=date(2010, 1, 1), end_date=date(2026, 8, 11), now=datetime(2026, 8, 11),
            )

        mismatched = copy.deepcopy(cfg)
        mismatched["etf_history"]["universes"]["single_etf"]["sectors"]["semiconductor"][0]["ts_code"] = "512480.SZ"
        with pytest.raises(ETFUniverseError, match="exchange mismatch"):
            resolve_etf_universe(
                conn, quant_cfg=mismatched, universe_name="single_etf", requested_sectors=None,
                start_date=date(2010, 1, 1), end_date=date(2026, 8, 11), now=datetime(2026, 8, 11),
            )


def test_named_manual_etf_universe_allows_multiple_explicit_members() -> None:
    cfg = {
        "etf_history": {
            "catalog_max_age_days": 7,
            "chunk_years": 1,
            "max_symbols_per_run": 50,
            "max_tasks_per_run": 1000,
            "universes": {
                "semiconductor_timing_etfs": {
                    "manifest_source": "manual_config",
                    "sectors": {
                        "semiconductor": [
                            {"symbol": "SH.512480", "ts_code": "512480.SH", "listed_from": "2019-06-12"},
                            {"symbol": "SH.512760", "ts_code": "512760.SH", "listed_from": "2019-06-12"},
                        ],
                    },
                },
            },
        },
    }
    with sqlite3.connect(":memory:") as conn:
        ensure_etf_schema(conn)
        manifest = resolve_etf_universe(
            conn,
            quant_cfg=cfg,
            universe_name="semiconductor_timing_etfs",
            requested_sectors=None,
            start_date=date(2010, 1, 1),
            end_date=date(2026, 8, 11),
            now=datetime(2026, 8, 11),
        )

    assert [member.symbol for member in manifest.members] == ["SH.512480", "SH.512760"]
