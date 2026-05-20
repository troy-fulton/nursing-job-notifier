# nursing-job-notifier

Monitors nursing job / residency program pages and sends a single combined email when any watched condition changes.

## Architecture

```
scraper.py    — generic HTTP fetch + BeautifulSoup evaluation; no email, no config
notifier.py   — site predicates, SMTP email, entry point
pyproject.toml — uv project; ruff + mypy config
```

**Data flow:** `main()` iterates `SITES`, calls `scrape(url, predicate)` for each, collects non-`None` return values, then sends one email if any alerts fired.

## Key Type

```python
# scraper.py
AlertPredicate = Callable[[BeautifulSoup], str | None]
```

Every predicate receives a parsed `BeautifulSoup` object and returns either:
- A **non-empty string** — the human-readable alert message to include in the email
- **`None`** — no alert; do nothing

Predicates must never send email, log at WARNING/ERROR, or call `sys.exit`. Side effects belong in `main()`.

## Adding a New Site

1. Define a predicate function in `notifier.py` following the `AlertPredicate` signature.
2. Add a `Final[str]` URL constant near the top of the config block.
3. Append `(URL_CONSTANT, predicate_function)` to the `SITES` list.

```python
MY_SITE_URL: Final[str] = "https://example.com/careers"

def check_my_site(soup: BeautifulSoup) -> str | None:
    ...

SITES: Final[list[tuple[str, AlertPredicate]]] = [
    ...,
    (MY_SITE_URL, check_my_site),
]
```

Do **not** add site-specific logic to `scraper.py`. That file is intentionally generic — it knows nothing about any particular site, URL, or alert condition.

## Environment Variables

All config is injected via environment variables — no `.env` file at runtime.

| Variable | Required | Description |
|---|---|---|
| `SMTP_HOST` | no | Default: `smtp.gmail.com` |
| `SMTP_PORT` | no | Default: `587` |
| `SMTP_USER` | **yes** | SMTP login / sender address |
| `SMTP_PASSWORD` | **yes** | App password (not account password) |
| `EMAIL_FROM` | no | Defaults to `SMTP_USER` |
| `EMAIL_RECIPIENTS` | **yes** | Comma-separated list of recipient addresses |

See `.env.example` for a complete template.

## Commands

```sh
# Install / sync dependencies (creates .venv automatically)
uv sync

# Run the notifier
uv run notifier.py

# Lint
uv run ruff check notifier.py scraper.py

# Format
uv run ruff format notifier.py scraper.py

# Type-check (strict mode)
uv run mypy notifier.py scraper.py
```

## Verifying Changes

All three checks must pass before a change is considered correct:

```sh
uv run ruff check notifier.py scraper.py
uv run mypy notifier.py scraper.py
```

If ruff reports fixable errors (`[*]`), run `uv run ruff check --fix` and verify the result. Do not suppress mypy errors with `# type: ignore` without a comment explaining why.

## Conventions

- **No dotenv** — environment variables are set by the caller (shell, scheduler, or CI). Do not add `python-dotenv` back as a dependency.
- **HTTP errors are non-fatal per site** — `main()` logs the error and continues to the next site rather than aborting.
- **One email per run** — all alerts are batched into a single message; never send one email per site.
- **Predicate scope** — predicates may inspect any part of the parsed HTML but must not make additional HTTP requests.
- Use `soup.find` / `soup.find_all` / `soup.select` with specific selectors rather than full-text `get_text()` searches where the page structure is known.
