import os
from zoneinfo import ZoneInfo

import click
from dotenv import load_dotenv

from .archive import save_archive, upsert_record
from .generate_feed import write_feed
from .scrape import fetch_puzzle


@click.command()
@click.option("--date", "date_value", required=False, help="Fetch a specific date (YYYY-MM-DD)")
def main(date_value: str | None = None) -> None:
    load_dotenv()
    os.environ.setdefault("TIMEZONE", "UTC")
    timezone = ZoneInfo(os.getenv("TIMEZONE", "UTC"))
    if timezone.key != "UTC":
        raise ValueError("Only UTC timezone is supported for feed generation.")

    record = fetch_puzzle(date_value)
    records, updated = upsert_record(record)
    save_archive(records)
    write_feed()

    if updated:
        click.echo(f"Updated archive for {record['date']}.")
    else:
        click.echo(f"Archive already contains {record['date']}.")


if __name__ == "__main__":
    main()
