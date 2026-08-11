from __future__ import annotations

import pandas as pd
import pytest

from phase0.data_access import symbols
from phase0.data_access.providers import tushare as provider
from phase0.data_access.providers.tushare import TushareConfig, TusharePermissionError


def test_suffix_qualified_symbols_do_not_guess_exchange_from_prefix() -> None:
    assert symbols.from_tushare_symbol("510300.SH") == "SH.510300"
    assert symbols.from_tushare_symbol("159915.SZ") == "SZ.159915"
    assert symbols.from_tushare_symbol("931865.CSI") == "CSI.931865"
    assert symbols.from_tushare_symbol("510300") == ""
    assert symbols.to_tushare_symbol("SH.512480") == "512480.SH"
    assert symbols.normalize_etf_symbol("SH.510300") == "SH.510300"
    assert symbols.normalize_etf_symbol("510300.SH") == "SH.510300"
    with pytest.raises(ValueError, match="exchange-qualified"):
        symbols.normalize_etf_symbol("510300")
    with pytest.raises(ValueError, match="SH or SZ"):
        symbols.normalize_etf_symbol("CSI.931865")


def test_fetch_etf_basic_preserves_observed_tracking_mapping(monkeypatch) -> None:
    def fake_call(api_name, *, params, fields, cfg):
        assert api_name == "etf_basic"
        assert params == {"list_status": "L"}
        return pd.DataFrame([{
            "ts_code": "510300.SH", "csname": "300ETF", "extname": "沪深300ETF",
            "cname": "华泰柏瑞沪深300ETF", "index_code": "000300.SH",
            "index_name": "沪深300", "setup_date": "20120504", "list_date": "20120528",
            "delist_date": None, "list_status": "L", "exchange": "SH",
            "mgt_name": "华泰柏瑞基金", "custod_name": "工商银行",
            "mgt_fee": "0.50", "etf_type": "股票型",
        }])

    monkeypatch.setattr(provider, "_call", fake_call)
    frame = provider.fetch_tushare_etf_basic(list_status="L", cfg=TushareConfig(enabled=True))
    assert frame.loc[0, "symbol"] == "SH.510300"
    assert frame.loc[0, "index_code_raw"] == "000300.SH"
    assert frame.loc[0, "tracking_index_symbol"] == "SH.000300"
    assert frame.loc[0, "list_date"] == "2012-05-28"
    assert frame.loc[0, "management_fee"] == 0.5


def test_fetch_etf_daily_converts_provider_units(monkeypatch) -> None:
    monkeypatch.setattr(provider, "_call", lambda *args, **kwargs: pd.DataFrame([{
        "ts_code": "510300.SH", "trade_date": "20260105", "open": 4.0,
        "high": 4.1, "low": 3.9, "close": 4.05, "pre_close": 3.98,
        "change": 0.07, "pct_chg": 1.7588, "vol": 123.0, "amount": 456.0,
    }]))
    frame = provider.fetch_tushare_etf_daily(
        "510300.SH", start_date="2026-01-01", end_date="2026-01-05", cfg=TushareConfig(enabled=True)
    )
    assert frame.loc[0, "symbol"] == "SH.510300"
    assert frame.loc[0, "volume"] == 12300.0
    assert frame.loc[0, "amount"] == 456000.0
    assert frame.loc[0, "price_mode"] == "raw"


def test_fetch_etf_adj_factors_has_fixed_contract(monkeypatch) -> None:
    monkeypatch.setattr(provider, "_call", lambda *args, **kwargs: pd.DataFrame([{
        "ts_code": "512480.SH", "trade_date": "20260105", "adj_factor": "1.25",
    }]))
    frame = provider.fetch_tushare_etf_adj_factors(
        "512480.SH", start_date="2026-01-01", end_date="2026-01-05", cfg=TushareConfig(enabled=True)
    )
    assert list(frame.columns) == provider.ETF_FACTOR_COLUMNS
    assert frame.loc[0, "symbol"] == "SH.512480"
    assert frame.loc[0, "adj_factor"] == 1.25


def test_permission_error_is_not_normalized_to_empty(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"code": 40203, "msg": "permission denied", "data": {"fields": [], "items": []}}

    monkeypatch.setenv("TUSHARE_TOKEN", "test-token")
    monkeypatch.setattr(provider.requests, "post", lambda *args, **kwargs: FakeResponse())
    with pytest.raises(TusharePermissionError, match="permission denied"):
        provider._call("etf_basic", params={"list_status": "L"}, fields=["ts_code"], cfg=TushareConfig(enabled=True, max_retries=1))
