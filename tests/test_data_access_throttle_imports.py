from __future__ import annotations

import phase0.throttle as legacy_throttle
import phase0.data_access.throttle as data_access_throttle


def test_throttle_legacy_import_aliases_data_access_module() -> None:
    assert legacy_throttle is data_access_throttle
    assert legacy_throttle.AkshareThrottleSettings is data_access_throttle.AkshareThrottleSettings
    assert legacy_throttle.AkshareThrottle is data_access_throttle.AkshareThrottle
    assert legacy_throttle.akshare_throttle is data_access_throttle.akshare_throttle
    assert legacy_throttle.configure_akshare_throttle is data_access_throttle.configure_akshare_throttle
    assert legacy_throttle.fetch_with_akshare_retries is data_access_throttle.fetch_with_akshare_retries
