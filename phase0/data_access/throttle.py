from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any, Callable, TypeVar


T = TypeVar("T")


@dataclass
class AkshareThrottleSettings:
    enabled: bool = True
    request_delay: float = 0.6
    jitter: float = 0.0
    batch_size: int = 5
    batch_pause: float = 5.0
    max_retries: int = 0
    retry_backoff: float = 3.0


class AkshareThrottle:
    def __init__(self) -> None:
        self.settings = AkshareThrottleSettings()
        self._request_count = 0
        self._last_request_at = 0.0

    def configure(self, cfg: dict[str, Any] | None) -> None:
        raw = cfg or {}
        if "anti_crawler" in raw:
            raw = raw.get("anti_crawler") or {}
        self.settings = AkshareThrottleSettings(
            enabled=bool(raw.get("enabled", True)),
            request_delay=float(raw.get("request_delay", 0.6)),
            jitter=float(raw.get("jitter", 0.0)),
            batch_size=int(raw.get("batch_size", 5)),
            batch_pause=float(raw.get("batch_pause", 5.0)),
            max_retries=int(raw.get("max_retries", 0)),
            retry_backoff=float(raw.get("retry_backoff", 3.0)),
        )
        self._request_count = 0
        self._last_request_at = 0.0

    def wait_before_request(self) -> None:
        if not self.settings.enabled:
            return
        self._request_count += 1
        if self.settings.batch_size > 0 and self._request_count > 1:
            if (self._request_count - 1) % self.settings.batch_size == 0:
                time.sleep(self.settings.batch_pause)

        target_delay = self.settings.request_delay + random.uniform(0.0, max(self.settings.jitter, 0.0))
        elapsed = time.monotonic() - self._last_request_at if self._last_request_at else target_delay
        if elapsed < target_delay:
            time.sleep(target_delay - elapsed)
        self._last_request_at = time.monotonic()

    def wait_before_retry(self, attempt: int) -> None:
        if not self.settings.enabled:
            return
        delay = self.settings.retry_backoff * (attempt + 1)
        if self.settings.jitter > 0:
            delay += random.uniform(0.0, self.settings.jitter)
        time.sleep(delay)


akshare_throttle = AkshareThrottle()


def configure_akshare_throttle(cfg: dict[str, Any] | None) -> None:
    akshare_throttle.configure(cfg)


def fetch_with_akshare_retries(fetcher: Callable[[], T]) -> T:
    last_result: T | None = None
    last_error: Exception | None = None
    for attempt in range(akshare_throttle.settings.max_retries + 1):
        akshare_throttle.wait_before_request()
        try:
            result = fetcher()
        except Exception as exc:
            last_error = exc
            result = None  # type: ignore[assignment]
        if result is not None and not bool(getattr(result, "empty", False)):
            return result
        last_result = result
        if attempt < akshare_throttle.settings.max_retries:
            akshare_throttle.wait_before_retry(attempt)

    if last_result is not None:
        return last_result
    if last_error is not None:
        raise last_error
    return None  # type: ignore[return-value]
