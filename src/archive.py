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
    record: dict[str, Any], path: Path = ARCHIVE_PATH
) -> tuple[list[dict[str, Any]], bool]:
    records = load_archive(path)
    updated = False
    new_records = []

    for existing in records:
        if existing.get("date") == record["date"]:
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
