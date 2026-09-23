"""Retry decorator using tenacity for HTTP requests."""
from __future__ import annotations

import time
from typing import Callable, TypeVar

import requests
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import SCRAPER

T = TypeVar("T")

_RETRYABLE = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)


def http_retry(max_attempts: int | None = None) -> Callable:
    attempts = max_attempts or SCRAPER.max_retries

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        return retry(
            retry=retry_if_exception_type(_RETRYABLE),
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            reraise=True,
        )(func)

    return decorator


def throttle() -> None:
    """Polite delay between requests."""
    time.sleep(SCRAPER.delay)
