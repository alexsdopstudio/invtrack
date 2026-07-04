"""Shared HTTP helpers for ingestion. SEC etiquette: identify with a
descriptive User-Agent and keep the request rate well under their 10 req/s
guidance."""

import time

import httpx

from ..config import get_settings

SEC_MIN_INTERVAL_SECONDS = 0.5
_last_sec_request = 0.0


def client() -> httpx.Client:
    return httpx.Client(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": get_settings().sec_edgar_user_agent},
    )


def sec_get(http: httpx.Client, url: str) -> httpx.Response:
    """GET against sec.gov/data.sec.gov with polite throttling."""
    global _last_sec_request
    wait = SEC_MIN_INTERVAL_SECONDS - (time.monotonic() - _last_sec_request)
    if wait > 0:
        time.sleep(wait)
    _last_sec_request = time.monotonic()
    resp = http.get(url)
    resp.raise_for_status()
    return resp
