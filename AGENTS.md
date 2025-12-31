Implement a GitHub Actions–driven podcast RSS feed generator
for `https://www.pastpuzzle.de/` in **Python**, using **Astral `uv`**for dependency
management and execution. The workflow scrapes the daily puzzle once per day, updates an
on-repo JSON archive, resolves podcast audio enclosures from linked pages, regenerates
`feed.xml`, and commits changes back to the repo.

## Goal

Generate a static RSS 2.0 feed (`feed.xml`) where each item is one day’s PastPuzzle
podcast entry and includes:

* `title`: `PastPuzzle – YYYY-MM-DD`
* `link`: the podcast page URL
* `guid`: deterministic `pastpuzzle:YYYY-MM-DD[:index]`
* `pubDate`: correct date (UTC)
* `description`: podcast page URL and solution year if discoverable
* `enclosure`: direct audio URL (scraped from podcast pages)

## Architecture

* No server.
* Run locally or via your own scheduler.
* Workflow steps:

  1. scrape “today’s” puzzle from the Supabase RPC endpoint
  2. extract podcast page links and resolve direct audio URLs (WDR Zeitzeichen pages)
  3. update `data/archive.json` (authoritative storage)
  4. regenerate `feed.xml` from the most recent N days (default 30)

## Deliverables

### 1) Scraper + normalizer

* Implement `src/scrape.py` with:

  + `discover_source()` that prefers `PASTPUZZLE_JSON_URL` and falls back to HTML discovery
  + `fetch_puzzle(date: Optional[str] = None) -> dict` returning:

    ```
    {
      "date": "YYYY-MM-DD",
      "events": ["podcast_page_url", "..."],
      "answer_year": 1234,
      "podcasts": [{"page_url": "...", "audio_url": "...", "content_type": "audio/mpeg"}],
      "source_url": "https://www.pastpuzzle.de/..."
    }
    ```

    `answer_year` may be `null` if not available without user interaction.
  + Robust parsing with explicit error messages if structure changes.
  + Resolve WDR Zeitzeichen audio download links by matching `Audio Download` or
    `wdrmedien-a.akamaihd.net` URLs in the podcast page HTML.
  + Save raw HTML/JSON samples to `tests/fixtures/` (at least one HTML fixture and one JSON
    fixture if discovered).

### 2) Archive storage

* `data/archive.json` is a list of day records.
* Implement `src/archive.py`:

  + load/create archive
  + upsert record for the scraped date
  + keep sorted by date ascending
  + idempotent: re-running same day should not churn files if unchanged

### 3) RSS generation

* Implement `src/generate_feed.py`:

  + Read archive and select last N days (configurable via env `FEED_DAYS`, default 30).
  + Generate RSS 2.0 XML to `feed.xml` using `xml.etree.ElementTree` (avoid heavy deps).
  + Ensure CDATA-safe description and valid RFC-822 `pubDate`.
  + Emit `<enclosure>` entries for direct audio URLs; skip items without audio URLs.
  + Set channel fields: title/link/description/lastBuildDate.

### 4) CLI entrypoint

* Provide `src/main.py`:

  + `python -m src.main` runs scrape → archive update → feed generation
  + Config via env:

    - `FEED_DAYS` (default 30)
    - `PASTPUZZLE_URL` (default `https://www.pastpuzzle.de/`)
    - `TIMEZONE` (use UTC internally)

### 5) Dependency management with `uv`

* Provide `pyproject.toml` (PEP 621) and/or `requirements.txt` compatible with `uv`.
* Use `uv` in CI:

  + `uv python install` (or setup-python) + `uv sync`
  + `uv run python -m src.main`
* Minimal deps (suggested):

  + `requests`
  + `beautifulsoup4`
  + `lxml` (optional but often stabilizes parsing)
  + `pytest` for tests

### 6) Scheduling

Use your preferred scheduler (cron, launchd, CI) to run:

* `uv run python -m src.main`

### 7) Tests + fixtures

* `tests/test_parser.py` loads fixture HTML/JSON and asserts extraction yields 4 events and
  a date.
* Ensure tests do not hit the network.

### 8) Docs

* `README.md` includes:

  + setup (local): `uv sync` then `uv run python -m src.main`
  + enabling scheduled workflow
  + GitHub Pages setup (feed is generated under `docs/`)
  + how to adjust `FEED_DAYS`

## Repo layout

* `src/`

  + `main.py`
  + `scrape.py`
  + `archive.py`
  + `generate_feed.py`
* `data/archive.json`
* `feed.xml`
* `tests/fixtures/`
* `tests/test_parser.py`
* `pyproject.toml`
* `README.md`

## Output format

Return:

* complete file tree
* full contents of every file (including workflow YAML and `pyproject.toml`)
* an example `feed.xml` generated from fixtures (not live-scraped)
