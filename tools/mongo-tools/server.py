# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "mcp[cli]>=1.2.0,<2.0.0",
#     "pymongo[srv]>=4.6",
#     "python-dotenv>=1.0",
# ]
# ///
"""MCP server exposing tools to manage DAGRealty listings in MongoDB.
Run via `uv run tools/mongo-tools/server.py` (see .mcp.json).

This is internal tooling for the site owner's private data (Mongo). It is
separate from the public site, which reads only from the deployed Cloudflare
Worker (see worker/README.md) -- nothing here is exposed publicly.

resync_listing/resync_all_listings/reupload_listing_photos shell out to
scraper/run.py and scraper/photos.py via `uv run` rather than importing the
scraper package directly, so scheduled (GitHub Actions) and on-demand (this
MCP server) runs execute the identical code path.
"""

import subprocess
from typing import Optional

from bson import ObjectId
from mcp.server.fastmcp import FastMCP

from db import (
    NON_OVERRIDABLE_FIELDS,
    REPO_ROOT,
    VALID_PROPERTY_TYPES,
    VALID_STATUSES,
    listings_collection,
    now_iso,
    scrape_runs_collection,
    strip_internal_id,
)

mcp = FastMCP("dagrealty-mongo")


def _clean_listing(doc: dict) -> dict:
    doc = strip_internal_id(doc)
    doc.pop("_source_photo_urls", None)
    if "last_scrape_run_id" in doc:
        doc["last_scrape_run_id"] = str(doc["last_scrape_run_id"])
    return doc


def _run_subprocess(args: list[str], timeout: int) -> dict:
    result = subprocess.run(
        ["uv", "run", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return {
        "exit_code": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


@mcp.tool()
def list_listings(
    status: Optional[str] = None,
    property_type: Optional[str] = None,
    city: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_beds: Optional[int] = None,
) -> list[dict]:
    """Browse listings (includes admin fields -- featured/hidden/notes/etc).
    All filters are optional and AND together. city is a case-insensitive
    exact match."""
    query: dict = {}
    if status:
        query["status"] = status
    if property_type:
        query["property_type"] = property_type
    if city:
        query["city"] = {"$regex": f"^{city}$", "$options": "i"}
    if min_price is not None or max_price is not None:
        price_filter = {}
        if min_price is not None:
            price_filter["$gte"] = min_price
        if max_price is not None:
            price_filter["$lte"] = max_price
        query["list_price"] = price_filter
    if min_beds is not None:
        query["bedrooms"] = {"$gte": min_beds}

    docs = [_clean_listing(d) for d in listings_collection().find(query)]
    docs.sort(key=lambda d: d.get("list_price") or 0)
    return docs


@mcp.tool()
def get_listing(mls_number: str) -> dict:
    """Fetch one listing's full document, including admin fields."""
    doc = listings_collection().find_one({"_id": mls_number})
    if not doc:
        raise ValueError(f"no listing with mls_number '{mls_number}'")
    return _clean_listing(doc)


@mcp.tool()
def resync_listing(mls_number: str) -> dict:
    """Rescrape one listing from USAMLS and upsert it into Mongo right now,
    without waiting for the nightly scheduled scrape. Runs
    `scraper/run.py --mls <mls_number>` as a subprocess."""
    return _run_subprocess(
        ["scraper/run.py", "--mls", mls_number, "--trigger", "mcp-resync-one"], timeout=60
    )


@mcp.tool()
def resync_all_listings() -> dict:
    """Rescrape every currently-listed property from USAMLS right now (same
    work the nightly GitHub Actions cron does). Takes roughly a minute due to
    deliberate rate-limiting against the source site. Runs
    `scraper/run.py --all` as a subprocess."""
    return _run_subprocess(["scraper/run.py", "--all", "--trigger", "mcp-resync-all"], timeout=300)


@mcp.tool()
def reupload_listing_photos(mls_number: str) -> dict:
    """Force re-download/resize/re-upload photos for one listing without a
    full detail rescrape. Runs `scraper/photos.py --mls <mls_number> --force`
    as a subprocess."""
    return _run_subprocess(
        ["scraper/photos.py", "--mls", mls_number, "--force"], timeout=180
    )


@mcp.tool()
def set_manual_override(mls_number: str, field: str, value) -> dict:
    """Hand-correct one scraped field for a listing (e.g. a typo in the
    source's public_comments, or a field the source got wrong). The override
    is recorded in admin.manual_overrides and re-applied automatically after
    every future scrape, so it won't get silently overwritten -- use
    clear_manual_override to let the scraped value take over again.

    field must be a top-level listing field, not _id/mls_number/admin/photos.
    Use mark_status for status changes instead (it has its own persistence
    path)."""
    if field in NON_OVERRIDABLE_FIELDS or field == "status":
        raise ValueError(
            f"field '{field}' cannot be set via set_manual_override "
            f"(use mark_status for status; {sorted(NON_OVERRIDABLE_FIELDS)} are never overridable)"
        )
    listings = listings_collection()
    if not listings.find_one({"_id": mls_number}, {"_id": 1}):
        raise ValueError(f"no listing with mls_number '{mls_number}'")

    listings.update_one(
        {"_id": mls_number},
        {"$set": {field: value, f"admin.manual_overrides.{field}": value, "updated_at": now_iso()}},
    )
    return _clean_listing(listings.find_one({"_id": mls_number}))


@mcp.tool()
def clear_manual_override(mls_number: str, field: str) -> dict:
    """Remove a manual override so the field goes back to whatever the
    source scrapes next time (the current value is left in place until the
    next scrape actually refreshes it)."""
    listings = listings_collection()
    if not listings.find_one({"_id": mls_number}, {"_id": 1}):
        raise ValueError(f"no listing with mls_number '{mls_number}'")

    listings.update_one(
        {"_id": mls_number},
        {"$unset": {f"admin.manual_overrides.{field}": ""}, "$set": {"updated_at": now_iso()}},
    )
    return _clean_listing(listings.find_one({"_id": mls_number}))


@mcp.tool()
def set_featured(mls_number: str, featured: bool) -> dict:
    """Feature/unfeature a listing (surfaced on the homepage)."""
    listings = listings_collection()
    if not listings.find_one({"_id": mls_number}, {"_id": 1}):
        raise ValueError(f"no listing with mls_number '{mls_number}'")
    listings.update_one(
        {"_id": mls_number}, {"$set": {"admin.featured": featured, "updated_at": now_iso()}}
    )
    return _clean_listing(listings.find_one({"_id": mls_number}))


@mcp.tool()
def set_hidden(mls_number: str, hidden: bool) -> dict:
    """Hide/unhide a listing from the public Worker API entirely (e.g. the
    owner wants it off the site temporarily without touching its MLS
    status)."""
    listings = listings_collection()
    if not listings.find_one({"_id": mls_number}, {"_id": 1}):
        raise ValueError(f"no listing with mls_number '{mls_number}'")
    listings.update_one(
        {"_id": mls_number}, {"$set": {"admin.hidden": hidden, "updated_at": now_iso()}}
    )
    return _clean_listing(listings.find_one({"_id": mls_number}))


@mcp.tool()
def set_internal_note(mls_number: str, note: str) -> dict:
    """Set (overwrite) the private internal note for a listing. Never
    exposed by the public Worker."""
    listings = listings_collection()
    if not listings.find_one({"_id": mls_number}, {"_id": 1}):
        raise ValueError(f"no listing with mls_number '{mls_number}'")
    listings.update_one(
        {"_id": mls_number}, {"$set": {"admin.internal_notes": note, "updated_at": now_iso()}}
    )
    return _clean_listing(listings.find_one({"_id": mls_number}))


@mcp.tool()
def mark_status(mls_number: str, status: str) -> dict:
    """Manually set a listing's status (e.g. "Sold" the moment the owner
    hears about it, ahead of the source updating). Stored in
    admin.status_override and reapplied after every future scrape until
    cleared by mark_status(mls_number, None) or another mark_status call."""
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {sorted(VALID_STATUSES)} or None")
    listings = listings_collection()
    if not listings.find_one({"_id": mls_number}, {"_id": 1}):
        raise ValueError(f"no listing with mls_number '{mls_number}'")

    update: dict = {"admin.status_override": status, "updated_at": now_iso()}
    if status is not None:
        update["status"] = status
    listings.update_one({"_id": mls_number}, {"$set": update})
    return _clean_listing(listings.find_one({"_id": mls_number}))


@mcp.tool()
def list_scrape_runs(limit: int = 20) -> list[dict]:
    """Recent scrape_runs, newest first, for reviewing schedule health and
    error counts."""
    docs = list(scrape_runs_collection().find().sort("started_at", -1).limit(limit))
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    return docs


@mcp.tool()
def get_scrape_run(run_id: str) -> dict:
    """Full detail of one scrape run (errors, per-listing counts)."""
    doc = scrape_runs_collection().find_one({"_id": ObjectId(run_id)})
    if not doc:
        raise ValueError(f"no scrape run with id '{run_id}'")
    doc["_id"] = str(doc["_id"])
    return doc


@mcp.tool()
def list_removed_listings() -> list[dict]:
    """Listings that disappeared from the source MLS on the most recent
    scrape (is_active_on_source=False) -- review before they vanish from the
    public site for good, e.g. mark_status(..., "Sold") or leave hidden."""
    docs = [_clean_listing(d) for d in listings_collection().find({"is_active_on_source": False})]
    docs.sort(key=lambda d: d.get("last_seen_at") or "", reverse=True)
    return docs


if __name__ == "__main__":
    mcp.run()
