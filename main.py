"""Webpage scraper with Gmail API notification."""

from __future__ import annotations

import base64
import logging
import os
import sys
from email.message import EmailMessage
from typing import Final
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from scraper import AlertPredicate, scrape

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration — set via environment variables
# ---------------------------------------------------------------------------

# Gmail API OAuth settings
GOOGLE_CLIENT_ID: Final[str] = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET: Final[str] = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN: Final[str] = os.getenv("GOOGLE_REFRESH_TOKEN", "")

# Gmail user for API endpoint. Use "me" for the authenticated account.
GMAIL_USER: Final[str] = os.getenv("GMAIL_USER", "me")
EMAIL_FROM: Final[str] = os.getenv("EMAIL_FROM", "")

# Comma-separated list of recipient addresses
_raw_recipients = os.getenv("EMAIL_RECIPIENTS", "")
EMAIL_RECIPIENTS: Final[list[str]] = [
    addr.strip() for addr in _raw_recipients.split(",") if addr.strip()
]


# ---------------------------------------------------------------------------
# Alert predicates — one per site, return a message string or None
# ---------------------------------------------------------------------------

COOK_CHILDRENS_URL: Final[str] = (
    "https://www.cookchildrens.org/healthcare-professionals/nursing/nurse-residency-program/"
)
TEXAS_HEALTH_URL: Final[str] = "https://jobs.texashealth.org/professions/graduate-nurse/"


_WINTER_2027_PLACEHOLDER = "Start date and open positions to be determined."


def check_texas_health_jobs(soup: BeautifulSoup) -> str | None:
    """Alert when the Winter 2027 Cohort section no longer shows the placeholder text."""
    header = soup.find("h5", string=lambda t: t and "Winter 2027 Cohort" in t)
    if header is None:
        return (
            f"Texas Health: 'Winter 2027 Cohort' heading not found — page may have changed. "
            f"{TEXAS_HEALTH_URL}"
        )
    sibling = header.find_next_sibling("p")
    if sibling is None or _WINTER_2027_PLACEHOLDER not in sibling.get_text(strip=True):
        actual = sibling.get_text(strip=True) if sibling else "<no <p> sibling>"
        return (
            f"Texas Health: Winter 2027 Cohort info has changed!\n"
            f'  Now reads: "{actual}"\n'
            f"  {TEXAS_HEALTH_URL}"
        )
    return None


def check_cook_childrens_jobs(soup: BeautifulSoup) -> str | None:
    """Alert when the October 2026 Cohorts heading is no longer present."""
    h3_tags = soup.find_all("h3")
    texts = [tag.get_text(strip=True) for tag in h3_tags]

    if any("October 2026 Cohorts" in t for t in texts):
        return None

    other_cohort = next((t for t in texts if "cohort" in t.lower()), None)
    if other_cohort:
        return (
            f"Cook Children's: October 2026 Cohorts heading is gone. "
            f'Found instead: "{other_cohort}"\n  {COOK_CHILDRENS_URL}'
        )
    return (
        f"Cook Children's: October 2026 Cohorts heading is gone and no other "
        f"cohort heading was found.\n  {COOK_CHILDRENS_URL}"
    )


# Map each URL to its predicate
SITES: Final[list[tuple[str, AlertPredicate]]] = [
    (COOK_CHILDRENS_URL, check_cook_childrens_jobs),
    (TEXAS_HEALTH_URL, check_texas_health_jobs),
]


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------


def send_notification(recipients: list[str], alerts: list[str]) -> None:
    """Send a combined plain-text email for all triggered alerts."""
    if not recipients:
        log.warning("No recipients configured — skipping email.")
        return

    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET or not GOOGLE_REFRESH_TOKEN:
        raise ValueError(
            "GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN must be set "
            "before sending email."
        )

    subject = f"Job alert: {len(alerts)} new match(es) found!"
    body = "The following alerts were triggered:\n\n" + "\n\n".join(f"• {msg}" for msg in alerts)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM or GMAIL_USER
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)

    creds = Credentials(
        token=None,
        refresh_token=GOOGLE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/gmail.send"],
    )
    creds.refresh(Request())
    if not creds.token:
        raise ValueError("Failed to obtain a Gmail API access token.")

    encoded_message = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    payload = {"raw": encoded_message}
    user_path = quote(GMAIL_USER, safe="")
    api_url = f"https://gmail.googleapis.com/gmail/v1/users/{user_path}/messages/send"

    with httpx.Client(timeout=30) as client:
        response = client.post(
            api_url,
            headers={
                "Authorization": f"Bearer {creds.token}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()

    log.info("Email sent to: %s", ", ".join(recipients))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    alerts: list[str] = []

    for url, predicate in SITES:
        try:
            message = scrape(url, predicate)
        except httpx.HTTPError as exc:
            log.error("HTTP error fetching %s: %s", url, exc)
            continue

        if message is not None:
            log.info("Alert triggered for %s", url)
            alerts.append(message)
        else:
            log.info("No alert for %s", url)

    if alerts:
        try:
            send_notification(EMAIL_RECIPIENTS, alerts)
        except (httpx.HTTPError, ValueError, OSError) as exc:
            log.error("Failed to send email: %s", exc)
            sys.exit(1)
    else:
        log.info("No alerts triggered across all sites. No email sent.")


if __name__ == "__main__":
    main()
