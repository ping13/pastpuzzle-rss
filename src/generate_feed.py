import os
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from .archive import load_archive


FEED_PATH = Path("docs/feed.xml")


def generate_feed(archive_path: Path = Path("data/archive.json")) -> str:
    feed_days = int(os.getenv("FEED_DAYS", "30"))
    base_url = os.getenv("PASTPUZZLE_URL", "https://www.pastpuzzle.de/")

    records = load_archive(archive_path)
    selected = records[-feed_days:] if feed_days > 0 else records

    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "PastPuzzle"
    ET.SubElement(channel, "link").text = base_url
    ET.SubElement(channel, "description").text = "Daily PastPuzzle feed"
    ET.SubElement(channel, "lastBuildDate").text = _format_rfc822(datetime.now(timezone.utc))

    for record in selected:
        date_value = record["date"]
        podcasts = _select_podcasts(record)
        for index, podcast in enumerate(podcasts, start=1):
            enclosure_url = podcast.get("audio_url")
            if not enclosure_url:
                continue
            item = ET.SubElement(channel, "item")
            title_suffix = f" Podcast {index}" if len(podcasts) > 1 else ""
            item_title = podcast.get("title") or f"PastPuzzle – {date_value}{title_suffix}"
            ET.SubElement(item, "title").text = item_title
            ET.SubElement(item, "link").text = (
                podcast.get("page_url") or record.get("source_url") or base_url
            )
            guid_suffix = f":{index}" if len(podcasts) > 1 else ""
            ET.SubElement(item, "guid").text = f"pastpuzzle:{date_value}{guid_suffix}"
            pub_date_value = podcast.get("pub_date") or date_value
            pub_date = datetime.fromisoformat(pub_date_value).replace(tzinfo=timezone.utc)
            ET.SubElement(item, "pubDate").text = _format_rfc822(pub_date)

            enclosure = ET.SubElement(item, "enclosure")
            enclosure.set("url", enclosure_url)
            enclosure.set("length", str(podcast.get("length", 0)))
            enclosure.set("type", podcast.get("content_type", "audio/mpeg"))

            description_text = _format_description(record, podcast)
            description_element = ET.SubElement(item, "description")
            description_element.text = f"<![CDATA[{description_text}]]>"

    xml_bytes = ET.tostring(rss, encoding="utf-8", xml_declaration=True)
    xml_text = xml_bytes.decode("utf-8")
    xml_text = xml_text.replace("&lt;![CDATA[", "<![CDATA[")
    xml_text = xml_text.replace("]]>&gt;", "]]>")
    xml_text = xml_text.replace("]]&gt;", "]]>")
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


def _format_description(record: dict[str, Any], podcast: dict[str, Any]) -> str:
    lines = []
    page_url = podcast.get("page_url")
    if page_url:
        lines.append(page_url)
    answer_year = record.get("answer_year")
    if answer_year:
        lines.append(f"Answer year: {answer_year}")
    return "\n".join(lines)
