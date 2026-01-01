import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


DEFAULT_BASE_URL = "https://www.pastpuzzle.de/"
DEFAULT_QUIZ_URL = "https://shktoswxcezxdkncmskf.supabase.co/rest/v1/rpc/get_quiz"


@dataclass
class SourceInfo:
    kind: str
    url: str
    html: Optional[str] = None


def discover_source(base_url: str) -> SourceInfo:
    """Discover whether the page embeds data or loads JSON from an endpoint."""
    explicit_json_url = os.getenv("PASTPUZZLE_JSON_URL")
    if explicit_json_url:
        return SourceInfo(kind="json", url=explicit_json_url)

    response = httpx.get(base_url, timeout=30)
    response.raise_for_status()
    html = response.text

    json_url = _discover_json_url(html, base_url)
    if json_url:
        return SourceInfo(kind="json", url=json_url, html=html)

    try:
        _extract_puzzle_from_html(html, base_url)
        return SourceInfo(kind="html", url=base_url, html=html)
    except ValueError:
        pass

    raise ValueError(
        "Unable to discover puzzle source: no JSON endpoint and no parseable embedded data found."
    )


def fetch_puzzle(date: Optional[str] = None) -> dict:
    base_url = os.getenv("PASTPUZZLE_URL", DEFAULT_BASE_URL)
    source = discover_source(base_url)

    if source.kind == "json":
        request_url = _apply_date_to_url(source.url, date)
        payload = _fetch_json_payload(request_url, date)
        record = _parse_json_payload(payload, source_url=request_url)
    else:
        if source.html is None:
            raise ValueError("HTML source was not available after discovery.")
        record = _extract_puzzle_from_html(source.html, source_url=source.url)

    _resolve_podcast_audio(record)

    if date and record["date"] != date:
        raise ValueError(
            f"Requested date {date} but scraped {record['date']} from {record['source_url']}."
        )

    return record


def fetch_quiz(quiz_id: str, date_override: Optional[str] = None) -> dict:
    quiz_url = os.getenv("PASTPUZZLE_QUIZ_URL", DEFAULT_QUIZ_URL)
    if not quiz_url:
        raise ValueError("PASTPUZZLE_QUIZ_URL must be set to fetch quiz data.")
    payload = _fetch_quiz_payload(quiz_url, quiz_id)
    record = _parse_json_payload(
        payload,
        source_url=quiz_url,
        date_override=date_override,
        quiz_id=quiz_id,
        require_date=date_override is None,
    )
    _resolve_podcast_audio(record)
    return record


def _apply_date_to_url(url: str, date: Optional[str]) -> str:
    if not date:
        return url
    if "{date}" in url:
        return url.format(date=date)
    return url


def _fetch_json_payload(url: str, date: Optional[str]) -> Any:
    headers = _build_headers()
    method = os.getenv("PASTPUZZLE_JSON_METHOD", "GET").upper()
    body = _build_body(date)
    return _fetch_payload(url, method, headers, body)


def _fetch_quiz_payload(url: str, quiz_id: str) -> Any:
    headers = _build_headers()
    method = os.getenv("PASTPUZZLE_QUIZ_METHOD", "POST").upper()
    body = _build_quiz_body(quiz_id)
    return _fetch_payload(url, method, headers, body)


def _fetch_payload(url: str, method: str, headers: dict[str, str], body: dict[str, Any]) -> Any:
    if os.getenv("PASTPUZZLE_DEBUG", "").lower() in {"1", "true", "yes"}:
        print(
            f"DEBUG request method={method} url={url}"
        )
        print(f"DEBUG headers keys={sorted(headers.keys())}")
        print(
            f"DEBUG apikey length={len(headers.get('apikey',''))} authorization length={len(headers.get('authorization',''))}"
        )
    if method not in {"GET", "POST"}:
        raise ValueError("Request method must be GET or POST.")
    response = _send_request(method, url, headers, body)
    if response.status_code == 401:
        api_key = headers.get("apikey")
        auth_header = headers.get("authorization", "")
        if api_key and auth_header != f"Bearer {api_key}":
            retry_headers = dict(headers)
            retry_headers["authorization"] = f"Bearer {api_key}"
            response = _send_request(method, url, retry_headers, body)
    response.raise_for_status()
    return response.json()


def _send_request(method: str, url: str, headers: dict[str, str], body: dict[str, Any]) -> httpx.Response:
    if method == "POST":
        return httpx.post(url, json=body, headers=headers, timeout=30)
    return httpx.get(url, headers=headers, timeout=30)


def _build_headers() -> dict[str, str]:
    headers: dict[str, str] = {"accept": "application/json"}
    raw_headers = os.getenv("PASTPUZZLE_HEADERS")
    if raw_headers:
        extra_headers = _parse_header_env(raw_headers)
        had_raw_auth = "authorization" in extra_headers
        had_raw_apikey = "apikey" in extra_headers
        api_key = os.getenv("PASTPUZZLE_API_KEY")
        authorization = os.getenv("PASTPUZZLE_AUTHORIZATION")
        if api_key or authorization:
            extra_headers.pop("authorization", None)
            extra_headers.pop("apikey", None)
        headers.update(extra_headers)
        if os.getenv("PASTPUZZLE_DEBUG", "").lower() in {"1", "true", "yes"}:
            print(
                "DEBUG header overrides: "
                f"raw_auth={had_raw_auth} "
                f"raw_apikey={had_raw_apikey} "
                f"env_auth={ bool(authorization) } env_apikey={ bool(api_key) }"
            )
    api_key = api_key.strip().strip("\"'") if api_key else None
    authorization = authorization.strip().strip("\"'") if authorization else None
    if api_key:
        headers["apikey"] = api_key
        if not authorization:
            headers["authorization"] = f"Bearer {api_key}"
    if authorization:
        if authorization.lower().startswith("bearer "):
            headers["authorization"] = authorization
        else:
            headers["authorization"] = f"Bearer {authorization}"
    return headers


def _build_body(date: Optional[str]) -> dict[str, Any]:
    raw_body = os.getenv("PASTPUZZLE_JSON_BODY")
    if raw_body:
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise ValueError("PASTPUZZLE_JSON_BODY must be valid JSON.") from exc
        if not isinstance(body, dict):
            raise ValueError("PASTPUZZLE_JSON_BODY must be a JSON object.")
        return body
    return {"date": date} if date else {}


def _build_quiz_body(quiz_id: str) -> dict[str, Any]:
    raw_body = os.getenv("PASTPUZZLE_QUIZ_BODY")
    if raw_body:
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise ValueError("PASTPUZZLE_QUIZ_BODY must be valid JSON.") from exc
        if not isinstance(body, dict):
            raise ValueError("PASTPUZZLE_QUIZ_BODY must be a JSON object.")
    else:
        body = {}
    body.setdefault("id", str(quiz_id))
    return body


def _parse_header_env(raw_headers: str) -> dict[str, str]:
    raw = raw_headers.strip()
    if not raw:
        return {}
    candidates = [raw]
    if raw.startswith(("\"", "'")) and raw.endswith(("\"", "'")):
        candidates.append(raw[1:-1])
    try:
        candidates.append(raw.encode("utf-8").decode("unicode_escape"))
    except UnicodeDecodeError:
        pass

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, str):
            try:
                parsed = json.loads(parsed)
            except json.JSONDecodeError:
                continue
        if isinstance(parsed, dict):
            return {_normalize_header_name(str(k)): str(v) for k, v in parsed.items()}

    parsed_pairs: dict[str, str] = {}
    for part in re.split(r",\s*|\n+", raw):
        if not part.strip() or ":" not in part:
            continue
        key, value = part.split(":", 1)
        parsed_pairs[_normalize_header_name(key.strip())] = value.strip().strip("\"'")
    if parsed_pairs:
        return parsed_pairs

    raise ValueError(
        "PASTPUZZLE_HEADERS must be valid JSON or key:value pairs."
    )


def _normalize_header_name(name: str) -> str:
    return name.strip().strip("\"'").lower()


def _discover_json_url(html: str, base_url: str) -> Optional[str]:
    patterns = [
        r"fetch\(\s*[\"']([^\"']+)[\"']",
        r"axios\.get\(\s*[\"']([^\"']+)[\"']",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, html):
            if "json" in match or "api" in match:
                return urljoin(base_url, match)
    return None


def _extract_puzzle_from_html(html: str, source_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    for script in soup.find_all("script"):
        if script.get("type") == "application/json" or "puzzle" in (script.get("id") or ""):
            try:
                payload = json.loads(script.get_text(strip=True))
            except json.JSONDecodeError:
                continue
            record = _parse_json_payload(payload, source_url=source_url)
            if record:
                return record

        text = script.get_text(" ")
        embedded_match = re.search(r"__PASTPUZZLE__\s*=\s*(\{.*?\})\s*;", text, re.S)
        if embedded_match:
            payload = json.loads(embedded_match.group(1))
            return _parse_json_payload(payload, source_url=source_url)

    events = _extract_events_from_dom(soup)
    date = _extract_date_from_dom(soup)
    if events and date:
        return {
            "date": date,
            "events": events,
            "answer_year": None,
            "source_url": source_url,
        }

    raise ValueError("HTML parsing failed: unable to locate events/date in DOM.")


def _extract_events_from_dom(soup: BeautifulSoup) -> Optional[list[str]]:
    containers = [
        soup.select_one("#events"),
        soup.select_one(".events"),
        soup.select_one(".pastpuzzle-events"),
    ]
    for container in containers:
        if not container:
            continue
        items = [item.get_text(strip=True) for item in container.find_all("li")]
        if len(items) == 4:
            return items
    return None


def _extract_date_from_dom(soup: BeautifulSoup) -> Optional[str]:
    time_tag = soup.find("time", attrs={"datetime": True})
    if time_tag:
        return time_tag["datetime"][:10]
    date_text = None
    for selector in [".date", ".pastpuzzle-date", "#date"]:
        element = soup.select_one(selector)
        if element:
            date_text = element.get_text(strip=True)
            break
    if date_text:
        match = re.search(r"(\d{4}-\d{2}-\d{2})", date_text)
        if match:
            return match.group(1)
    return None


def _parse_json_payload(
    payload: Any,
    source_url: str,
    date_override: Optional[str] = None,
    quiz_id: Optional[str] = None,
    require_date: bool = False,
) -> dict:
    supabase_record = _parse_supabase_payload(
        payload,
        source_url,
        date_override=date_override,
        quiz_id=quiz_id,
        require_date=require_date,
    )
    if supabase_record:
        return supabase_record

    record = _find_record(payload)
    if not record:
        raise ValueError("JSON parsing failed: unable to locate puzzle record structure.")

    date_value = record.get("date")
    events = record.get("events")
    answer_year = record.get("answer_year")

    if not date_value:
        raise ValueError("JSON parsing failed: missing date field.")
    if not events or not isinstance(events, list):
        raise ValueError("JSON parsing failed: missing events list.")
    if len(events) != 4:
        raise ValueError(f"JSON parsing failed: expected 4 events, got {len(events)}.")

    parsed_answer = None
    if isinstance(answer_year, int):
        parsed_answer = answer_year
    elif isinstance(answer_year, str) and answer_year.isdigit():
        parsed_answer = int(answer_year)

    return {
        "date": date_value,
        "events": [str(item) for item in events],
        "answer_year": parsed_answer,
        "source_url": record.get("source_url") or source_url,
    }


def _parse_supabase_payload(
    payload: Any,
    source_url: str,
    date_override: Optional[str] = None,
    quiz_id: Optional[str] = None,
    require_date: bool = False,
) -> Optional[dict]:
    if not isinstance(payload, dict):
        return None
    if "tips" not in payload or "year" not in payload:
        return None
    tips = payload.get("tips")
    if not isinstance(tips, list):
        raise ValueError("JSON parsing failed: expected tips to be a list.")
    podcast_links = []
    extras = []
    cover_image = None
    for tip in tips:
        if not isinstance(tip, dict):
            continue
        if not cover_image:
            image_url = tip.get("image")
            if image_url:
                cover_image = image_url
        if tip.get("type") != "podcast":
            link = tip.get("link")
            if link:
                extras.append(
                    {
                        "page_url": link,
                        "title": tip.get("title"),
                        "tip_type": tip.get("type"),
                    }
                )
            continue
        link = tip.get("link")
        if link:
            podcast_links.append(link)
    if not podcast_links and not extras:
        types = [
            tip.get("type")
            for tip in tips
            if isinstance(tip, dict) and tip.get("type") is not None
        ]
        raise ValueError(
            "JSON parsing failed: no podcast tips with links found. "
            f"Tip types: {types}"
        )

    date_value = None
    payload_date = payload.get("date")
    if isinstance(payload_date, str):
        date_value = payload_date[:10]
    if date_override:
        date_value = date_override
    if require_date and not date_value:
        raise ValueError("Quiz payload missing date; pass --quiz-date.")
    if not date_value:
        date_value = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    answer_year = payload.get("year")
    parsed_answer = answer_year if isinstance(answer_year, int) else None

    record = {
        "date": date_value,
        "events": podcast_links,
        "answer_year": parsed_answer,
        "podcasts": [{"page_url": link} for link in podcast_links],
        "extras": extras,
        "cover_image": cover_image,
        "source_url": source_url,
    }
    if quiz_id:
        record["quiz_id"] = quiz_id
        record["quiz_source_url"] = source_url
    return record


def _resolve_podcast_audio(record: dict[str, Any]) -> None:
    if not os.getenv("PASTPUZZLE_RESOLVE_AUDIO", "1").strip() in {"1", "true", "yes"}:
        return
    podcasts = record.get("podcasts")
    if not isinstance(podcasts, list):
        return
    require_audio = os.getenv("PASTPUZZLE_AUDIO_REQUIRED", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    for podcast in podcasts:
        if not isinstance(podcast, dict):
            continue
        page_url = podcast.get("page_url")
        if not page_url or podcast.get("audio_url"):
            continue
        response = httpx.get(page_url, timeout=30)
        response.raise_for_status()
        parsed = _parse_podcast_page(response.text, page_url)
        audio_url = parsed.get("audio_url")
        if not audio_url:
            if require_audio:
                raise ValueError(
                    f"Unable to locate audio URL for podcast page {page_url}."
                )
            continue
        podcast["audio_url"] = audio_url
        podcast["content_type"] = _infer_mime_type(audio_url)
        podcast["length"] = _fetch_content_length(audio_url)
        if parsed.get("title"):
            podcast["title"] = parsed["title"]
        if parsed.get("pub_date"):
            podcast["pub_date"] = parsed["pub_date"]


def _extract_audio_url(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "lxml")
    for selector in ["audio source", "audio"]:
        for element in soup.select(selector):
            src = element.get("src")
            if src:
                return src
    for selector in [
        ("meta", {"property": "og:audio"}),
        ("meta", {"property": "og:audio:secure_url"}),
        ("meta", {"property": "og:audio:url"}),
        ("meta", {"name": "twitter:player:stream"}),
    ]:
        element = soup.find(selector[0], attrs=selector[1])
        if element and element.get("content"):
            return element["content"]
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            payload = json.loads(script.get_text(strip=True))
        except json.JSONDecodeError:
            continue
        audio_url = _find_audio_url_in_json(payload)
        if audio_url:
            return audio_url
    link = soup.find("link", attrs={"rel": "alternate", "type": "audio/mpeg"})
    if link and link.get("href"):
        return link["href"]
    link = soup.find("link", rel="audio")
    if link and link.get("href"):
        return link["href"]
    audio_link = _extract_audio_url_from_links(soup)
    if audio_link:
        return audio_link
    match = re.search(r"https?://[^\"'\\s>]+\\.(mp3|m4a|aac|ogg|wav)", html)
    if match:
        return match.group(0)
    return None


def _parse_podcast_page(html: str, page_url: str) -> dict[str, Any]:
    audio_url = _extract_audio_url(html)
    if not audio_url:
        audio_url = _extract_wdr_audio_url(html)
    if audio_url:
        audio_url = _normalize_audio_url(audio_url, page_url)
    title = _extract_title(html)
    pub_date = _extract_pub_date(html)
    return {
        "page_url": page_url,
        "audio_url": audio_url,
        "title": title,
        "pub_date": pub_date,
    }


def _extract_wdr_audio_url(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "lxml")
    for link in soup.find_all("a"):
        href = link.get("href", "")
        text = link.get_text(" ", strip=True).lower()
        if "audio download" in text:
            return href or None
        if "wdrmedien-a.akamaihd.net" in href:
            return href
    match = re.search(r"https?://wdrmedien-a\\.akamaihd\\.net/[^\"'\\s>]+", html)
    return match.group(0) if match else None


def _extract_audio_url_from_links(soup: BeautifulSoup) -> Optional[str]:
    keywords = ("audio", "download", "herunterladen", "podcast")
    for link in soup.find_all("a"):
        href = link.get("href", "")
        if not href:
            continue
        if not _looks_like_audio_url(href):
            continue
        text = link.get_text(" ", strip=True).lower()
        if any(keyword in text for keyword in keywords):
            return href
    return None


def _normalize_audio_url(url: str, page_url: str) -> str:
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("/"):
        return urljoin(page_url, url)
    return url


def _extract_title(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "lxml")
    headline = soup.find("h1")
    if headline:
        text = headline.get_text(" ", strip=True)
        return text or None
    return None


def _extract_pub_date(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "lxml")
    meta = soup.find("meta", attrs={"property": "article:published_time"})
    if meta and meta.get("content"):
        match = re.search(r"(\d{4}-\d{2}-\d{2})", meta["content"])
        if match:
            return match.group(1)
    time_tag = soup.find("time")
    if time_tag:
        text = time_tag.get("datetime") or time_tag.get_text(" ", strip=True)
        if text:
            match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
            if match:
                return match.group(1)
    return None


def _find_audio_url_in_json(payload: Any) -> Optional[str]:
    if isinstance(payload, dict):
        for key in ("contentUrl", "embedUrl", "url", "audio"):
            value = payload.get(key)
            if isinstance(value, str) and _looks_like_audio_url(value):
                return value
        for value in payload.values():
            found = _find_audio_url_in_json(value)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_audio_url_in_json(item)
            if found:
                return found
    return None


def _looks_like_audio_url(value: str) -> bool:
    lowered = value.lower()
    return lowered.endswith((".mp3", ".m4a", ".aac", ".ogg", ".wav"))


def _infer_mime_type(url: str) -> str:
    extension = urlparse(url).path.lower().rsplit(".", 1)[-1]
    mapping = {
        "mp3": "audio/mpeg",
        "m4a": "audio/mp4",
        "aac": "audio/aac",
        "ogg": "audio/ogg",
        "wav": "audio/wav",
    }
    return mapping.get(extension, "audio/mpeg")


def _fetch_content_length(url: str) -> int:
    try:
        response = httpx.head(url, timeout=30)
        response.raise_for_status()
        length = response.headers.get("content-length")
        return int(length) if length and length.isdigit() else 0
    except httpx.HTTPError:
        return 0


def _find_record(payload: Any) -> Optional[dict[str, Any]]:
    if isinstance(payload, dict):
        if "events" in payload and "date" in payload:
            return payload
        for value in payload.values():
            found = _find_record(value)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_record(item)
            if found:
                return found
    return None
