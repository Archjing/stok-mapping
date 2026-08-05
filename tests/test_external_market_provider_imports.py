from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from phase0.data_access.providers import external_market


def test_external_market_provider_dispatches_yfinance_hk_symbol(monkeypatch) -> None:
    calls: list[tuple[str, int]] = []

    def fake_fetch_yf_daily(symbol: str, years: int) -> pd.DataFrame:
        calls.append((symbol, years))
        return pd.DataFrame({"date": ["2024-01-02"], "open": [1], "high": [1], "low": [1], "close": [1]})

    monkeypatch.setattr(external_market, "fetch_yf_daily", fake_fetch_yf_daily)

    result = external_market.fetch_external_market_daily(
        "HK.00700",
        SimpleNamespace(provider="yfinance", years=3),
    )

    assert not result.empty
    assert calls == [("0700.HK", 3)]


def test_external_market_provider_dispatches_tiingo_for_us_symbols(monkeypatch) -> None:
    calls: list[tuple[str, int]] = []

    def fake_fetch_tiingo_daily(symbol: str, years: int) -> pd.DataFrame:
        calls.append((symbol, years))
        return pd.DataFrame({"date": ["2024-01-02"], "open": [1], "high": [1], "low": [1], "close": [1]})

    monkeypatch.setattr(external_market, "fetch_tiingo_daily", fake_fetch_tiingo_daily)

    result = external_market.fetch_external_market_daily(
        "NVDA",
        SimpleNamespace(provider="tiingo", years=5),
    )

    assert not result.empty
    assert calls == [("NVDA", 5)]


def test_external_market_provider_dispatches_supported_hk_providers(monkeypatch) -> None:
    calls: list[tuple[str, str, int]] = []

    def fake_fetch_hk_daily(symbol: str, years: int, adjust: str = "qfq") -> pd.DataFrame:
        calls.append(("akshare", symbol, years))
        assert adjust == "qfq"
        return pd.DataFrame({"date": ["2024-01-02"], "open": [1], "high": [1], "low": [1], "close": [1]})

    def fake_fetch_tushare_hk_daily(symbol: str, years: int) -> pd.DataFrame:
        calls.append(("tushare", symbol, years))
        return pd.DataFrame({"date": ["2024-01-02"], "open": [1], "high": [1], "low": [1], "close": [1]})

    monkeypatch.setattr(external_market, "fetch_hk_daily", fake_fetch_hk_daily)
    monkeypatch.setattr(external_market, "fetch_tushare_hk_daily", fake_fetch_tushare_hk_daily)

    external_market.fetch_external_market_daily("HK.00700", SimpleNamespace(provider="akshare_hk", years=2))
    external_market.fetch_external_market_daily("HK.00700", SimpleNamespace(provider="tushare_hk", years=4))

    assert calls == [("akshare", "HK.00700", 2), ("tushare", "HK.00700", 4)]
