"""Base HTTP session shared by all scrapers."""
from __future__ import annotations

import logging
import time

import requests
from bs4 import BeautifulSoup
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.config import SCRAPER

logger = logging.getLogger(__name__)

_RETRYABLE = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)


class BaseSession:
    """Shared requests.Session with polite rate-limiting and automatic retries."""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": SCRAPER.user_agent,
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        self._last_request: float = 0.0

    def _wait(self) -> None:
        elapsed = time.time() - self._last_request
        if elapsed < SCRAPER.delay:
            time.sleep(SCRAPER.delay - elapsed)

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    def get(self, url: str, **kwargs) -> requests.Response:
        self._wait()
        try:
            resp = self.session.get(url, timeout=SCRAPER.timeout, **kwargs)
            self._last_request = time.time()
            return resp
        except requests.exceptions.RequestException:
            self._last_request = time.time()
            raise

    def get_soup(self, url: str, **kwargs) -> BeautifulSoup | None:
        """Fetch URL and return parsed BeautifulSoup, None on non-200."""
        try:
            resp = self.get(url, **kwargs)
            if resp.status_code == 404:
                logger.debug("404 Not Found: %s", url)
                return None
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except requests.exceptions.HTTPError as e:
            logger.warning("HTTP error %s for %s", e, url)
            return None
        except requests.exceptions.RequestException as e:
            logger.error("Request failed for %s: %s", url, e)
            return None  # Don't propagate - let caller handle gracefully
