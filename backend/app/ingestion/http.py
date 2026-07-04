"""Shared HTTP helpers for ingestion. SEC etiquette: identify with a
descriptive User-Agent and keep the request rate well under their 10 req/s
guidance."""

import time

import httpx

from ..config import get_settings

MIN_INTERVAL_SECONDS = 0.5
_last_request = 0.0


def client() -> httpx.Client:
    return httpx.Client(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": get_settings().sec_edgar_user_agent},
    )


def throttle() -> None:
    """Global polite throttle for government sites (sec.gov asks <=10 req/s;
    we stay far below for every source)."""
    global _last_request
    wait = MIN_INTERVAL_SECONDS - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


def sec_get(http: httpx.Client, url: str) -> httpx.Response:
    """GET against sec.gov/data.sec.gov with polite throttling."""
    throttle()
    resp = http.get(url)
    resp.raise_for_status()
    return resp
