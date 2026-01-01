import json
import os
from zoneinfo import ZoneInfo

import click
from dotenv import load_dotenv

from .archive import save_archive, upsert_record
from .generate_feed import write_feed
from .scrape import fetch_puzzle


@click.command()
@click.option("--date", "date_value", required=False, help="Fetch a specific date (YYYY-MM-DD)")
@click.option(
    "--check",
    "check_only",
    is_flag=True,
    help="Validate scraping without writing archive/feed outputs.",
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
    print_json: bool = False,
    pretty_json: bool = False,
) -> None:
    load_dotenv()
    os.environ.setdefault("TIMEZONE", "UTC")
    timezone = ZoneInfo(os.getenv("TIMEZONE", "UTC"))
    if timezone.key != "UTC":
        raise ValueError("Only UTC timezone is supported for feed generation.")

    record = fetch_puzzle(date_value)
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
    records, updated = upsert_record(record)
    save_archive(records)
    write_feed()

    if updated:
        click.echo(f"Updated archive for {record['date']}.")
    else:
        click.echo(f"Archive already contains {record['date']}.")


if __name__ == "__main__":
    main()
