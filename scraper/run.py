# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests>=2.31",
#     "beautifulsoup4>=4.12",
#     "pymongo[srv]>=4.6",
#     "python-dotenv>=1.0",
# ]
# ///
"""Scraper CLI entrypoint. Shared by the GitHub Actions cron workflow and the
`resync_listing`/`resync_all_listings` MCP tools (both invoke this exact
script as a subprocess, so scheduled and on-demand runs behave identically).

Usage:
    uv run scraper/run.py --all
    uv run scraper/run.py --mls 2819457
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / "scraper" / ".env")
load_dotenv(REPO_ROOT / ".env")

from fetch import RateLimitedSession, ScraperBlockedError  # noqa: E402
from parse_detail import parse_detail_page  # noqa: E402
from parse_list import discover_all_mls_numbers, discover_property_types  # noqa: E402
from upsert import (  # noqa: E402
    build_listing_doc,
    ensure_indexes,
    finish_scrape_run,
    mark_removed_listings,
    now_iso,
    start_scrape_run,
    upsert_listing,
)

DETAIL_PATH = "/dgrealestate/default.asp"
LIST_URL = "https://www.usamls.net/dgrealestate/default.asp?content=office_listings&listing_off_id=35&this_format=0"


def detail_page_url(mls_number: str) -> str:
    return (
        f"https://www.usamls.net{DETAIL_PATH}?content=expanded&search_content=office_listings"
        f"&this_format=0&mls_number={mls_number}&page=1&sortby=2"
    )


def scrape_one(session, listings, run_id, mls_number: str, property_type: str | None) -> tuple[str, str | None]:
    """Returns (added|updated, error_message_or_None)."""
    try:
        html = session.get(
            DETAIL_PATH,
            params={
                "content": "expanded",
                "search_content": "office_listings",
                "this_format": 0,
                "mls_number": mls_number,
                "page": 1,
                "sortby": 2,
            },
        )
        detail = parse_detail_page(html, detail_page_url(mls_number))
        if not detail.get("mls_number"):
            return "error", f"{mls_number}: detail page had no parseable MLS Number field"

        doc = build_listing_doc(
            detail,
            property_type,
            source={
                "site": "usamls",
                "list_url": LIST_URL,
                "detail_url": detail_page_url(mls_number),
            },
        )
        result = upsert_listing(listings, doc, run_id)
        return result, None
    except Exception as exc:  # noqa: BLE001 -- one bad listing must not abort the whole run
        return "error", f"{mls_number}: {exc}"


def run(target_mls: str | None, trigger: str) -> dict:
    mongo_uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    mongo_db = os.environ.get("MONGODB_DB", "dagrealty")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    db = client[mongo_db]
    listings = db["listings"]
    scrape_runs = db["scrape_runs"]
    ensure_indexes(db)

    session = RateLimitedSession()
    run_id = start_scrape_run(scrape_runs, trigger)

    added, updated, errors = [], [], []

    try:
        if target_mls:
            existing = listings.find_one({"_id": target_mls}, {"property_type": 1})
            property_type = existing.get("property_type") if existing else None
            if property_type is None:
                property_type = discover_property_types(session).get(target_mls)
            targets = [target_mls]
            seen_this_run = None  # single-listing runs never mark others removed
        else:
            type_map = discover_property_types(session)
            targets = discover_all_mls_numbers(session)
            seen_this_run = set(targets)

        for mls_number in targets:
            property_type = type_map.get(mls_number) if not target_mls else property_type
            result, error = scrape_one(session, listings, run_id, mls_number, property_type)
            if error:
                errors.append({"mls_number": mls_number, "message": error})
            elif result == "added":
                added.append(mls_number)
            else:
                updated.append(mls_number)

        removed = []
        if seen_this_run is not None:
            removed = mark_removed_listings(listings, seen_this_run, run_id)

        finish_scrape_run(
            scrape_runs,
            run_id,
            status="failed" if errors and not (added or updated) else ("partial" if errors else "success"),
            listings_seen=targets,
            listings_added=added,
            listings_updated=updated,
            listings_removed=removed,
            errors=errors,
        )

        summary = {
            "run_id": str(run_id),
            "added": added,
            "updated": updated,
            "removed": removed,
            "errors": errors,
        }
        return summary
    except ScraperBlockedError as exc:
        finish_scrape_run(scrape_runs, run_id, status="failed", errors=[{"mls_number": None, "message": str(exc)}])
        raise
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape USAMLS office listings into MongoDB.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Resync every currently-listed property.")
    group.add_argument("--mls", metavar="MLS_NUMBER", help="Resync a single listing by MLS number.")
    parser.add_argument(
        "--trigger",
        default="scheduled",
        choices=["scheduled", "manual", "mcp-resync-one", "mcp-resync-all"],
        help="Recorded on the scrape_runs document (default: scheduled).",
    )
    args = parser.parse_args()

    summary = run(target_mls=args.mls, trigger=args.trigger)
    print(f"added={len(summary['added'])} updated={len(summary['updated'])} "
          f"removed={len(summary['removed'])} errors={len(summary['errors'])}")
    for err in summary["errors"]:
        print(f"  ERROR {err['mls_number']}: {err['message']}", file=sys.stderr)

    if summary["errors"] and not (summary["added"] or summary["updated"]):
        sys.exit(1)


if __name__ == "__main__":
    main()
