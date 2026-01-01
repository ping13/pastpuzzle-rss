from src.archive import _merge_records


def test_merge_records_prefers_existing_values():
    existing = {
        "date": "2025-12-31",
        "answer_year": 9,
        "source_url": "https://example.com/source",
        "cover_image": "https://example.com/cover.png",
        "events": ["https://example.com/podcast"],
        "extras": [{"page_url": "https://example.com/extra"}],
    }
    incoming = {
        "date": "2025-12-31",
        "answer_year": 9,
        "source_url": "https://example.com/quiz",
        "cover_image": "https://example.com/cover2.png",
        "events": ["https://example.com/podcast"],
        "extras": [{"page_url": "https://example.com/extra2"}],
        "podcasts": [{"page_url": "https://example.com/podcast2"}],
    }
    merged = _merge_records(existing, incoming)
    assert merged["source_url"] == "https://example.com/source"
    assert merged["cover_image"] == "https://example.com/cover.png"
    assert merged["events"] == ["https://example.com/podcast"]
    assert {"page_url": "https://example.com/extra"} in merged["extras"]
    assert {"page_url": "https://example.com/extra2"} in merged["extras"]
    assert {"page_url": "https://example.com/podcast2"} in merged["podcasts"]
