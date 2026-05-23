# nursing-job-notifier

A small Python notifier that checks a set of webpages for changes and sends one combined email when any watched condition is triggered.

## What it does

- Fetches each configured page with `httpx`
- Parses the HTML with `BeautifulSoup`
- Runs a site-specific `should_alert` function for each page
- Collects all alert messages into one email
- Sends the email through SMTP

The scraping logic is intentionally separate from the email logic:

- `scraper.py` handles fetching and parsing a page, then calls a predicate
- `main.py` defines the site-specific predicates and sends email if any alerts fire

## Project layout

```text
main.py   # main entry point, predicates, SMTP email
scraper.py    # generic fetch + parse + predicate runner
pyproject.toml
AGENTS.md
.env.example
```

## Requirements

- Python 3.11 or newer
- `uv`
- SMTP credentials for the account that will send email

## Setup

1. Sync dependencies:

   ```sh
   uv sync
   ```

2. Create your environment file from the example:

   ```sh
   cp .env.example .env
   ```

3. Fill in the values in `.env`.

## Configuration

The script reads configuration from environment variables.

| Variable | Required | Description |
|---|---|---|
| `SMTP_HOST` | no | SMTP server hostname. Default: `smtp.gmail.com` |
| `SMTP_PORT` | no | SMTP server port. Default: `587` |
| `SMTP_USER` | yes | SMTP username / sender address |
| `SMTP_PASSWORD` | yes | SMTP password or app password |
| `EMAIL_FROM` | no | From address. Defaults to `SMTP_USER` |
| `EMAIL_RECIPIENTS` | yes | Comma-separated list of recipients |

## Running

```sh
uv run main.py
```

If any site returns an alert message, the script combines all messages into a single email.

## Adding or changing a site

Each site is represented by a `(url, predicate)` pair in `SITES`.

A predicate must have this shape:

```python
from bs4 import BeautifulSoup

def my_site_predicate(soup: BeautifulSoup) -> str | None:
    ...
```

Return a string when the site should alert. Return `None` when it should not.

Keep site-specific HTML logic in `main.py`. Keep `scraper.py` generic.

## Validation

```sh
uv run ruff check main.py scraper.py
uv run mypy main.py scraper.py
```

## Notes

- The repository uses `uv` dependency groups instead of a `.env`-based package loader.
- The notifier is designed to send one email per run, not one email per site.
- HTTP failures for individual sites are logged and skipped so one bad page does not stop the rest.
