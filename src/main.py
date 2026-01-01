import json
import os
from datetime import date as Date
from zoneinfo import ZoneInfo

import click
from dotenv import load_dotenv

from .archive import save_archive, upsert_record
from .generate_feed import write_feed
from .scrape import fetch_puzzle, fetch_quiz


@click.command()
@click.option("--date", "date_value", required=False, help="Fetch a specific date (YYYY-MM-DD)")
@click.option(
    "--check",
    "check_only",
    is_flag=True,
    help="Validate scraping without writing archive/feed outputs.",
)
@click.option("--quiz-id", "quiz_id", required=False, help="Fetch quiz data by ID.")
@click.option(
    "--quiz-date",
    "quiz_date",
    required=False,
    help="Date (YYYY-MM-DD) to associate with --quiz-id.",
)
@click.option(
    "--print-json",
    "print_json",
    is_flag=True,
    help="Print the scraped record as JSON.",
)
@click.option(
    "--pretty-json",
    "pretty_json",
    is_flag=True,
    help="Pretty-print JSON output (implies --print-json).",
)
def main(
    date_value: str | None = None,
    check_only: bool = False,
    quiz_id: str | None = None,
    quiz_date: str | None = None,
    print_json: bool = False,
    pretty_json: bool = False,
) -> None:
    load_dotenv()
    os.environ.setdefault("TIMEZONE", "UTC")
    timezone = ZoneInfo(os.getenv("TIMEZONE", "UTC"))
    if timezone.key != "UTC":
        raise ValueError("Only UTC timezone is supported for feed generation.")
    if date_value:
        _validate_date(date_value, "--date")
    if quiz_date:
        _validate_date(quiz_date, "--quiz-date")

    if quiz_id and date_value:
        raise ValueError("Use --quiz-date instead of --date when fetching a quiz.")

    if quiz_id:
        record = fetch_quiz(quiz_id, date_override=quiz_date)
        merge = True
    else:
        record = fetch_puzzle(date_value)
        merge = False
    if pretty_json:
        print_json = True
    if print_json:
        if pretty_json:
            click.echo(json.dumps(record, indent=2, ensure_ascii=True, sort_keys=True))
        else:
            click.echo(json.dumps(record, ensure_ascii=True, sort_keys=True))
    if check_only:
        click.echo(f"Scrape OK for {record['date']}.")
        return
    records, updated = upsert_record(record, merge=merge)
    save_archive(records)
    write_feed()

    if updated:
        click.echo(f"Updated archive for {record['date']}.")
    else:
        click.echo(f"Archive already contains {record['date']}.")


def _validate_date(value: str, label: str) -> None:
    try:
        Date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be YYYY-MM-DD (got {value}).") from exc


if __name__ == "__main__":
    main()
