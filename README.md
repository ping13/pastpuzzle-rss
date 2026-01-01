# PastPuzzle RSS

## Experimental

This project is experimental and may change or break without notice.

## Getting API credentials

The Supabase RPC endpoint requires headers that are easiest to capture from your browser:

1) Log in to https://www.pastpuzzle.de/ and solve the daily puzzle.
2) Open your browser DevTools (Network tab) and filter for `get_puzzle_of_the_day`.
3) Select the request and copy the values for `apikey` and `authorization` (Bearer token),
   plus any required headers like `Origin`, `Referer`, and `content-profile`.
4) Put those values into your `.env` (or GitHub Actions secrets) as `PASTPUZZLE_API_KEY`,
   `PASTPUZZLE_AUTHORIZATION`, and optionally `PASTPUZZLE_HEADERS`.

Do not commit these values; treat them as secrets.

## About 

Generates a static RSS 2.0 feed for https://www.pastpuzzle.de/ by scraping the daily puzzle,
storing the results in a local archive, and emitting `feed.xml` with podcast enclosures
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
make publish
```

The `publish` target copies `feed.xml` to `PUBLISH_DIR` (read from the environment
or `.env`).

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
- `PASTPUZZLE_API_KEY`: API key for endpoints that require `apikey`
- `PASTPUZZLE_AUTHORIZATION`: bearer token for endpoints that require `authorization` (defaults to API key in CI)
- `PASTPUZZLE_RESOLVE_AUDIO`: set to `0` to skip resolving podcast pages to audio URLs
- `PASTPUZZLE_AUDIO_REQUIRED`: set to `1` to fail when audio URLs are missing
- `FEED_URL`: public URL to `feed.xml` for atom:link self
- `PODCAST_AUTHOR`: author name for iTunes metadata
- `PODCAST_SUMMARY`: podcast summary/description (keep > 50 characters)
- `PODCAST_LANGUAGE`: language code (default: de)
- `PODCAST_CATEGORY`: iTunes category (default: History)
- `PODCAST_EXPLICIT`: iTunes explicit flag (default: no)
- `PODCAST_IMAGE_URL`: square cover art URL (1400-3000 px)
- `TIMEZONE`: only UTC is supported (default: UTC)

The repo includes a placeholder image at `docs/cover.png`. Host your cover art somewhere
public and set `PODCAST_IMAGE_URL` to that URL.

Example:

```bash
FEED_DAYS=14 uv run python -m src.main
```
