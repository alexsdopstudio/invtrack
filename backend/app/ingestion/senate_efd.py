"""Official Senate Periodic Transaction Reports from efdsearch.senate.gov.

This is the primary source for senate trades now that the community Stock
Watcher dataset is defunct — it reads the same legally-mandated STOCK Act
disclosures, directly from the Senate's own search system.

Flow (the site is a Django app with CSRF + a DataTables JSON endpoint):
  1. GET /search/home/ to obtain a csrftoken cookie, then POST the
     prohibition agreement to unlock the search endpoints for the session.
  2. POST /search/report/data/ (paged) filtered to PTRs submitted in the
     lookback window; each row links to a report page.
  3. For each electronically-filed PTR (/search/view/ptr/<uuid>/), parse the
     transactions HTML table. Paper filings are scanned images — skipped.

Every request goes through the shared polite throttle. Markup/endpoint
details can drift; parsing is defensive (header-name based column mapping)
and failures surface in the ingestion_run log rather than crashing.
"""

import logging
import re
from datetime import date, timedelta
from typing import Any

import httpx
from bs4 import BeautifulSoup

from . import http

logger = logging.getLogger(__name__)

BASE_URL = "https://efdsearch.senate.gov"
SEARCH_HOME = f"{BASE_URL}/search/home/"
SEARCH_DATA = f"{BASE_URL}/search/report/data/"

LOOKBACK_DAYS = 120
PAGE_SIZE = 100
MAX_REPORTS = 400  # hard cap on report pages fetched per run

_PTR_LINK_RE = re.compile(r'href="(/search/view/ptr/[^"]+)"')
_PAPER_LINK_RE = re.compile(r"/search/view/paper/")
_DATE_RE = re.compile(r"\d{2}/\d{2}/\d{4}")


def start_session(client: httpx.Client) -> str:
    """Accept the EFD prohibition agreement; returns the CSRF token bound to
    this client's session cookies."""
    http.throttle()
    client.get(SEARCH_HOME).raise_for_status()
    token = client.cookies.get("csrftoken")
    if not token:
        raise RuntimeError("efdsearch did not set a csrftoken cookie")
    http.throttle()
    resp = client.post(
        SEARCH_HOME,
        data={"prohibition_agreement": "1", "csrfmiddlewaretoken": token},
        headers={"Referer": SEARCH_HOME},
    )
    resp.raise_for_status()
    # Django rotates the token after the agreement POST.
    return client.cookies.get("csrftoken") or token


def parse_search_rows(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Normalize the DataTables response: each row holds filer name cells, a
    report-link cell, and a date-received cell (positions have shifted before,
    so scan cells instead of indexing)."""
    reports = []
    for row in payload.get("data", []):
        cells = [str(c) for c in row]
        joined = " ".join(cells)
        link = _PTR_LINK_RE.search(joined)
        if not link:  # paper filing or unrelated report type
            continue
        dates = _DATE_RE.findall(BeautifulSoup(joined, "html.parser").get_text(" "))
        name_cells = [
            BeautifulSoup(c, "html.parser").get_text(" ").strip()
            for c in cells
            if "<a" not in c
        ]
        member = " ".join(w for w in name_cells[:2] if w).strip() or "unknown"
        reports.append(
            {
                "member": member,
                "link": BASE_URL + link.group(1),
                "date_received": dates[-1] if dates else "",
            }
        )
    return reports


def search_ptr_filings(client: httpx.Client, token: str, since: date) -> list[dict[str, str]]:
    reports: list[dict[str, str]] = []
    start = 0
    while len(reports) < MAX_REPORTS:
        http.throttle()
        resp = client.post(
            SEARCH_DATA,
            data={
                "draw": "1",
                "start": str(start),
                "length": str(PAGE_SIZE),
                "report_types": "[11]",  # 11 = Periodic Transaction Report
                "filer_types": "[]",
                "submitted_start_date": since.strftime("%m/%d/%Y") + " 00:00:00",
                "submitted_end_date": "",
                "candidate_state": "",
                "senator_state": "",
                "office_id": "",
                "first_name": "",
                "last_name": "",
                "csrfmiddlewaretoken": token,
            },
            headers={"Referer": SEARCH_HOME, "X-CSRFToken": token},
        )
        resp.raise_for_status()
        payload = resp.json()
        page = payload.get("data", [])
        reports.extend(parse_search_rows({"data": page}))
        start += PAGE_SIZE
        if start >= int(payload.get("recordsTotal", 0)) or not page:
            break
    return reports[:MAX_REPORTS]


def _header_index(
    headers: list[str], *needles: str, exclude: tuple[str, ...] = ()
) -> int | None:
    for i, h in enumerate(headers):
        if any(n in h for n in needles) and not any(x in h for x in exclude):
            return i
    return None


def parse_ptr_html(html: str, member: str, date_received: str) -> list[dict[str, Any]]:
    """Parse the transactions table of an electronically-filed PTR page into
    stock-watcher-shaped raw rows (consumed by congress.parse_stock_watcher_rows)."""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        headers = [th.get_text(" ", strip=True).lower() for th in table.find_all("th")]
        i_date = _header_index(headers, "transaction date")
        i_ticker = _header_index(headers, "ticker")
        i_type = _header_index(headers, "type", exclude=("asset", "filer"))
        i_amount = _header_index(headers, "amount")
        i_owner = _header_index(headers, "owner")
        i_asset = _header_index(headers, "asset name", "asset", exclude=("type",))
        if i_date is None or i_ticker is None or i_type is None or i_amount is None:
            continue  # not the transactions table
        body = table.find("tbody") or table
        for tr in body.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            if len(cells) <= max(i_date, i_ticker, i_type, i_amount):
                continue
            rows.append(
                {
                    "senator": member,
                    "ticker": cells[i_ticker],
                    "type": cells[i_type],
                    "amount": cells[i_amount],
                    "transaction_date": cells[i_date],
                    "disclosure_date": date_received,
                    "owner": cells[i_owner] if i_owner is not None and i_owner < len(cells) else None,
                    "asset_description": cells[i_asset] if i_asset is not None and i_asset < len(cells) else None,
                    "source_link": None,
                }
            )
    return rows


def fetch_rows(client: httpx.Client) -> list[dict[str, Any]]:
    """Entry point used by congress.ingest: raw senate rows in stock-watcher
    shape, for the shared normalizer."""
    since = date.today() - timedelta(days=LOOKBACK_DAYS)
    token = start_session(client)
    reports = search_ptr_filings(client, token, since)
    logger.info("efdsearch: %d electronic PTRs since %s", len(reports), since)
    raw_rows: list[dict[str, Any]] = []
    for report in reports:
        try:
            http.throttle()
            resp = client.get(report["link"], headers={"Referer": SEARCH_HOME})
            resp.raise_for_status()
            rows = parse_ptr_html(resp.text, report["member"], report["date_received"])
            for r in rows:
                r["source_link"] = report["link"]
            raw_rows.extend(rows)
        except Exception as exc:  # noqa: BLE001 - per-report isolation
            logger.warning("efdsearch PTR %s failed: %s", report["link"], exc)
    return raw_rows
