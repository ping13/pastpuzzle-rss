import os
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from dotenv import load_dotenv

from .archive import load_archive


FEED_PATH = Path("data/feed.xml")
ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
PODCAST_NS = "https://podcastindex.org/namespace/1.0"
ATOM_NS = "http://www.w3.org/2005/Atom"

ET.register_namespace("itunes", ITUNES_NS)
ET.register_namespace("podcast", PODCAST_NS)
ET.register_namespace("atom", ATOM_NS)


def generate_feed(archive_path: Path = Path("data/archive.json")) -> str:
    load_dotenv()
    feed_days = int(os.getenv("FEED_DAYS", "30"))
    base_url = os.getenv("PASTPUZZLE_URL", "https://www.pastpuzzle.de/")
    feed_url = os.getenv("FEED_URL", "")
    include_non_audio = os.getenv("INCLUDE_NON_AUDIO", "0") in {"1", "true", "yes"}
    author = os.getenv("PODCAST_AUTHOR", "PastPuzzle")
    summary = os.getenv(
        "PODCAST_SUMMARY",
        "Daily PastPuzzle podcast feed with historical clues and audio highlights.",
    )
    language = os.getenv("PODCAST_LANGUAGE", "de")
    category = os.getenv("PODCAST_CATEGORY", "History")
    explicit = os.getenv("PODCAST_EXPLICIT", "no")
    image_url = os.getenv("PODCAST_IMAGE_URL", "")

    records = load_archive(archive_path)
    selected = records[-feed_days:] if feed_days > 0 else records
    if not image_url and selected:
        image_url = selected[-1].get("cover_image") or ""

    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "PastPuzzle"
    ET.SubElement(channel, "link").text = base_url
    ET.SubElement(channel, "description").text = summary
    ET.SubElement(channel, "language").text = language
    if feed_url:
        atom_link = ET.SubElement(channel, f"{{{ATOM_NS}}}link")
        atom_link.set("href", feed_url)
        atom_link.set("rel", "self")
        atom_link.set("type", "application/rss+xml")
    ET.SubElement(channel, f"{{{ITUNES_NS}}}summary").text = summary
    ET.SubElement(channel, f"{{{ITUNES_NS}}}author").text = author
    ET.SubElement(channel, f"{{{ITUNES_NS}}}explicit").text = explicit
    if image_url:
        image = ET.SubElement(channel, f"{{{ITUNES_NS}}}image")
        image.set("href", image_url)
    category_element = ET.SubElement(channel, f"{{{ITUNES_NS}}}category")
    category_element.set("text", category)
    ET.SubElement(channel, f"{{{PODCAST_NS}}}locked").text = "no"
    if feed_url:
        ET.SubElement(channel, f"{{{PODCAST_NS}}}guid").text = feed_url
    ET.SubElement(channel, "lastBuildDate").text = _format_rfc822(datetime.now(timezone.utc))

    for record in selected:
        date_value = record["date"]
        podcasts = _select_podcasts(record)
        extras = _select_extras(record) if include_non_audio else []
        item_counter = 0
        for podcast in podcasts:
            enclosure_url = podcast.get("audio_url")
            if not enclosure_url and not include_non_audio:
                continue
            item_counter += 1
            item = ET.SubElement(channel, "item")
            title_suffix = f" Podcast {item_counter}" if len(podcasts) + len(extras) > 1 else ""
            item_title = podcast.get("title") or f"PastPuzzle – {date_value}{title_suffix}"
            ET.SubElement(item, "title").text = item_title
            ET.SubElement(item, "link").text = (
                podcast.get("page_url") or record.get("source_url") or base_url
            )
            guid_suffix = f":{item_counter}" if len(podcasts) + len(extras) > 1 else ""
            ET.SubElement(item, "guid").text = f"pastpuzzle:{date_value}{guid_suffix}"
            pub_date_value = podcast.get("pub_date") or date_value
            pub_date = datetime.fromisoformat(pub_date_value).replace(tzinfo=timezone.utc)
            ET.SubElement(item, "pubDate").text = _format_rfc822(pub_date)

            if enclosure_url:
                enclosure = ET.SubElement(item, "enclosure")
                enclosure.set("url", enclosure_url)
                enclosure.set("length", str(podcast.get("length", 0)))
                enclosure.set("type", podcast.get("content_type", "audio/mpeg"))

            description_text = _format_description(record, podcast)
            description_element = ET.SubElement(item, "description")
            description_element.text = description_text
            ET.SubElement(item, f"{{{ITUNES_NS}}}summary").text = description_text
            ET.SubElement(item, f"{{{ITUNES_NS}}}author").text = author
            ET.SubElement(item, f"{{{ITUNES_NS}}}explicit").text = explicit

        for extra in extras:
            item_counter += 1
            item = ET.SubElement(channel, "item")
            title_suffix = f" Item {item_counter}" if len(podcasts) + len(extras) > 1 else ""
            extra_title = extra.get("title") or f"PastPuzzle – {date_value}{title_suffix}"
            ET.SubElement(item, "title").text = extra_title
            ET.SubElement(item, "link").text = (
                extra.get("page_url") or record.get("source_url") or base_url
            )
            guid_suffix = f":{item_counter}" if len(podcasts) + len(extras) > 1 else ""
            ET.SubElement(item, "guid").text = f"pastpuzzle:{date_value}{guid_suffix}"
            pub_date = datetime.fromisoformat(date_value).replace(tzinfo=timezone.utc)
            ET.SubElement(item, "pubDate").text = _format_rfc822(pub_date)

            description_text = _format_description(record, extra)
            description_element = ET.SubElement(item, "description")
            description_element.text = description_text
            ET.SubElement(item, f"{{{ITUNES_NS}}}summary").text = description_text
            ET.SubElement(item, f"{{{ITUNES_NS}}}author").text = author
            ET.SubElement(item, f"{{{ITUNES_NS}}}explicit").text = explicit

    xml_bytes = ET.tostring(rss, encoding="utf-8", xml_declaration=True)
    xml_text = xml_bytes.decode("utf-8")
    xml_text = xml_text + "\n"
    return xml_text


def write_feed(feed_path: Path = FEED_PATH, archive_path: Path = Path("data/archive.json")) -> bool:
    content = generate_feed(archive_path)
    if feed_path.exists():
        existing = feed_path.read_text(encoding="utf-8")
        if existing == content:
            return False
    feed_path.parent.mkdir(parents=True, exist_ok=True)
    feed_path.write_text(content, encoding="utf-8")
    return True


def _format_rfc822(value: datetime) -> str:
    return format_datetime(value, usegmt=True)


def _select_podcasts(record: dict[str, Any]) -> list[dict[str, Any]]:
    podcasts = record.get("podcasts")
    if isinstance(podcasts, list) and podcasts:
        return [podcast for podcast in podcasts if isinstance(podcast, dict)]
    events = record.get("events", [])
    return [{"page_url": event} for event in events if isinstance(event, str)]


def _select_extras(record: dict[str, Any]) -> list[dict[str, Any]]:
    extras = record.get("extras")
    if isinstance(extras, list) and extras:
        return [extra for extra in extras if isinstance(extra, dict)]
    return []


def _format_description(record: dict[str, Any], podcast: dict[str, Any]) -> str:
    lines = []
    tip_type = podcast.get("tip_type")
    if tip_type:
        lines.append(f"Type: {tip_type}")
    page_url = podcast.get("page_url")
    if page_url:
        lines.append(page_url)
    answer_year = record.get("answer_year")
    if answer_year:
        lines.append(f"Answer year: {answer_year}")
    return "\n".join(lines)
