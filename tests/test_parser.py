import json
from pathlib import Path

from src.scrape import (
    _extract_audio_url,
    _extract_puzzle_from_html,
    _parse_json_payload,
    _parse_podcast_page,
)


FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_html_fixture():
    html = (FIXTURES / "pastpuzzle.html").read_text(encoding="utf-8")
    record = _extract_puzzle_from_html(html, "https://www.pastpuzzle.de/")
    assert record["date"] == "2024-01-02"
    assert len(record["events"]) == 4


def test_parse_json_fixture():
    payload = json.loads((FIXTURES / "pastpuzzle.json").read_text(encoding="utf-8"))
    record = _parse_json_payload(payload, "https://www.pastpuzzle.de/")
    assert record["date"] == "2024-01-03"
    assert len(record["events"]) == 4


def test_parse_supabase_fixture():
    payload = json.loads(
        (FIXTURES / "pastpuzzle_supabase.json").read_text(encoding="utf-8")
    )
    record = _parse_json_payload(payload, "https://www.pastpuzzle.de/")
    assert len(record["events"]) == 2
    assert record["answer_year"] == 9


def test_extract_audio_url():
    html = (FIXTURES / "podcast_page.html").read_text(encoding="utf-8")
    audio_url = _extract_audio_url(html)
    assert audio_url == "https://cdn.example.com/audio/pastpuzzle-episode.mp3"


def test_extract_audio_url_from_download_link():
    html = (FIXTURES / "podcast_page_download.html").read_text(encoding="utf-8")
    audio_url = _extract_audio_url(html)
    assert audio_url == "https://cdn.example.com/audio/secure-episode.mp3"


def test_parse_supabase_non_audio_fixture():
    payload = json.loads(
        (FIXTURES / "pastpuzzle_video.json").read_text(encoding="utf-8")
    )
    record = _parse_json_payload(payload, "https://www.pastpuzzle.de/")
    assert record["events"] == []
    assert len(record["extras"]) == 2


def test_parse_wdr_podcast_page():
    html = (FIXTURES / "wdr_zeitzeichen.html").read_text(encoding="utf-8")
    parsed = _parse_podcast_page(
        html,
        "https://www1.wdr.de/radio/wdr5/sendungen/zeitzeichen/example.html",
    )
    assert parsed["audio_url"] == "https://wdrmedien-a.akamaihd.net/content/audio/test/zeitzeichen.mp3"
    assert parsed["title"] == "Zeitzeichen: Titus Flavius Vespasianus"
    assert parsed["pub_date"] == "2024-06-12"
