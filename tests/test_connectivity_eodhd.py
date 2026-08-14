from __future__ import annotations

import traceback

import pandas as pd
import pytest
import requests

from quant.data_access import connectivity


def test_fetch_eodhd_daily_normalizes_price_index_without_volume(monkeypatch) -> None:
    class Response:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return [
                {"date": "2026-08-07", "open": "100", "high": "102", "low": "99", "close": "101"},
                {"date": "2026-08-10", "open": "101", "high": "103", "low": "100", "close": "102"},
            ]

    calls: list[dict] = []

    def fake_get(url: str, **kwargs):
        calls.append({"url": url, **kwargs})
        return Response()

    monkeypatch.setenv("EODHD_API_TOKEN", "test-eodhd-api-key")
    monkeypatch.setattr(connectivity.requests, "get", fake_get)

    result = connectivity.fetch_eodhd_daily("GDAXI.INDX", years=5)

    assert result.drop(columns="volume").to_dict("records") == [
        {"date": pd.Timestamp("2026-08-07"), "open": 100, "high": 102, "low": 99, "close": 101, "adjusted_close": 101},
        {"date": pd.Timestamp("2026-08-10"), "open": 101, "high": 103, "low": 100, "close": 102, "adjusted_close": 102},
    ]
    assert result["volume"].isna().all()
    assert calls[0]["url"].endswith("/GDAXI.INDX")
    assert calls[0]["params"]["period"] == "d"


def test_fetch_eodhd_daily_redacts_api_key_from_http_failure(monkeypatch) -> None:
    api_key = "test-eodhd-api-key"

    class FailedResponse:
        status_code = 401
        url = f"https://eodhd.com/api/eod/GDAXI.INDX?api_token={api_key}"

        def raise_for_status(self) -> None:
            raise requests.HTTPError(f"401 Client Error: Unauthorized for url: {self.url}")

    monkeypatch.setenv("EODHD_API_TOKEN", api_key)
    monkeypatch.setattr(connectivity.requests, "get", lambda *args, **kwargs: FailedResponse())

    with pytest.raises(RuntimeError, match="eodhd_request_failed:status=401") as exc_info:
        connectivity.fetch_eodhd_daily("GDAXI.INDX", years=1)

    assert api_key not in str(exc_info.value)
    assert api_key not in "".join(traceback.format_exception(exc_info.value))
    assert exc_info.value.__context__ is None


def test_fetch_eodhd_daily_surfaces_provider_warning(monkeypatch) -> None:
    class Response:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return [{"warning": "Data is limited by one year as you have free subscription"}]

    monkeypatch.setenv("EODHD_API_TOKEN", "test-eodhd-api-key")
    monkeypatch.setattr(connectivity.requests, "get", lambda *args, **kwargs: Response())

    with pytest.raises(RuntimeError, match="eodhd_api_warning:Data is limited by one year"):
        connectivity.fetch_eodhd_daily("GDAXI.INDX", years=5)
