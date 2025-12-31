# PastPuzzle RSS

Generates a static RSS 2.0 feed for https://www.pastpuzzle.de/ by scraping the daily puzzle,
storing the results in a local archive, and emitting `docs/feed.xml` with podcast enclosures
resolved from the podcast tip pages.

## Local setup

```bash
uv sync
uv run python -m src.main
```

Makefile shortcuts:

```bash
make run
make test
```

To run tests directly:

```bash
uv sync --group test
uv run pytest
```

You can also place environment overrides in a `.env` file (loaded automatically via
python-dotenv) for local runs. See `.env.example` for a template.

## Configuration

- `FEED_DAYS`: number of days to include in the feed (default: 30)
- `PASTPUZZLE_URL`: base URL for scraping (default: https://www.pastpuzzle.de/)
- `PASTPUZZLE_JSON_URL`: override JSON endpoint for scraping
- `PASTPUZZLE_JSON_METHOD`: `GET` or `POST` (default: `GET`)
- `PASTPUZZLE_JSON_BODY`: JSON object string for POST bodies
- `PASTPUZZLE_API_KEY`: API key for endpoints that require `apikey`/`authorization`
- `PASTPUZZLE_HEADERS`: JSON object string for extra headers
- `PASTPUZZLE_RESOLVE_AUDIO`: set to `0` to skip resolving podcast pages to audio URLs
- `PASTPUZZLE_AUDIO_REQUIRED`: set to `1` to fail when audio URLs are missing
- `TIMEZONE`: only UTC is supported (default: UTC)

Example:

```bash
FEED_DAYS=14 uv run python -m src.main
```

## GitHub Actions

The workflow runs daily on a UTC schedule and on manual dispatch. It scrapes the puzzle,
updates `data/archive.json`, regenerates `docs/feed.xml`, runs tests, and commits changes if
anything changed.

## GitHub Pages (optional)

The feed is written to `docs/feed.xml` for GitHub Pages. Enable Pages on the `main`
branch and point it at the `/docs` folder. Adjust `PASTPUZZLE_URL` if you need the
published URL in the feed.
