import json
from pathlib import Path
from typing import Any


ARCHIVE_PATH = Path("data/archive.json")


def load_archive(path: Path = ARCHIVE_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("Archive data must be a list of records.")
    return data


def upsert_record(
    record: dict[str, Any],
    path: Path = ARCHIVE_PATH,
    merge: bool = False,
) -> tuple[list[dict[str, Any]], bool]:
    records = load_archive(path)
    updated = False
    new_records = []
    matched = False

    for existing in records:
        if existing.get("date") == record["date"]:
            matched = True
            if merge:
                merged = _merge_records(existing, record)
                if merged != existing:
                    updated = True
                new_records.append(merged)
            else:
                if existing != record:
                    new_records.append(record)
                    updated = True
                else:
                    new_records.append(existing)
            break
    else:
        new_records.append(record)
        updated = True

    for existing in records:
        if existing.get("date") != record["date"]:
            new_records.append(existing)

    new_records.sort(key=lambda item: item.get("date", ""))
    return new_records, updated


def save_archive(records: list[dict[str, Any]], path: Path = ARCHIVE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(records, handle, indent=2, sort_keys=False)
        handle.write("\n")


def _merge_records(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if value is None:
            continue
        if key in {"events", "podcasts", "extras"}:
            merged[key] = _merge_list(existing.get(key), value)
            continue
        if key == "source_url" and existing.get("source_url"):
            continue
        if key == "cover_image" and existing.get("cover_image"):
            continue
        if _is_empty(existing.get(key)):
            merged[key] = value
    return merged


def _merge_list(existing: Any, incoming: Any) -> list[Any]:
    merged: list[Any] = []
    if isinstance(existing, list):
        merged.extend(existing)
    if isinstance(incoming, list):
        for item in incoming:
            if item not in merged:
                merged.append(item)
    return merged


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, dict, tuple, set)) and not value:
        return True
    return False
