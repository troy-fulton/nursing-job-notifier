"""Page scraping module — fetches a URL and evaluates an alert predicate."""

from __future__ import annotations

import logging
from collections.abc import Callable

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

AlertPredicate = Callable[[BeautifulSoup], str | None]


def scrape(url: str, should_alert: AlertPredicate) -> str | None:
    """Fetch *url*, parse it, and return the alert message from *should_alert*.

    Args:
        url: The page to fetch.
        should_alert: A callable that receives the parsed ``BeautifulSoup``
            object and returns a non-empty string describing the alert
            condition, or ``None`` if no alert should be raised.

    Returns:
        The alert message string, or ``None`` if no alert was triggered.

    Raises:
        httpx.HTTPError: If the HTTP request fails.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; nursing-job-notifier/1.0; "
            "+https://github.com/local/nursing-job-notifier)"
        )
    }
    log.info("Fetching %s …", url)
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        response = client.get(url, headers=headers)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    return should_alert(soup)
