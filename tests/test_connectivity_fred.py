from __future__ import annotations

import pytest
import requests
import traceback

from quant.data_access import connectivity


def test_fetch_fred_series_redacts_api_key_from_http_failure(monkeypatch) -> None:
    api_key = "test-fred-api-key"

    class FailedResponse:
        status_code = 400
        url = f"https://api.stlouisfed.org/fred/series/observations?api_key={api_key}"

        def raise_for_status(self) -> None:
            raise requests.HTTPError(f"400 Client Error: Bad Request for url: {self.url}")

    monkeypatch.setenv("FRED_API_KEY", api_key)
    monkeypatch.setattr(connectivity.requests, "get", lambda *args, **kwargs: FailedResponse())

    with pytest.raises(RuntimeError, match="fred_request_failed:status=400") as exc_info:
        connectivity.fetch_fred_series("INVALID", years=1, cache_enabled=False)

    assert api_key not in str(exc_info.value)
    assert api_key not in "".join(traceback.format_exception(exc_info.value))
    assert exc_info.value.__context__ is None
