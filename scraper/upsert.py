"""Upsert scraped listings into MongoDB and record scrape-run bookkeeping.

Listings that disappear from the source are never deleted -- they get
`is_active_on_source = False` so the owner can review them (see the
`list_removed_listings` MCP tool) before anything vanishes from the public
site.
"""

from datetime import datetime, timezone

from pymongo.collection import Collection
from pymongo.database import Database

STATUS_LABEL_MAP = {
    "A": "Active",
    "P": "Pending",
    "C": "Contingent",
    "S": "Sold",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_listing_doc(detail: dict, property_type: str | None, source: dict) -> dict:
    """Map a parse_detail.py result (plus the property type discovered from
    parse_list.py) onto the `listings` schema.

    Photos are handled in two stages: the raw (unstable, session-signed)
    source URLs go into `_source_photo_urls` for scraper/photos.py to
    download/resize/upload to R2; the public `photos` field stays `[]` until
    that runs, so we never store a source URL where the frontend/Worker
    might read it.

    Does not set admin/first_seen_at/last_seen_at/created_at -- upsert_listing
    fills those in based on whether the doc already exists.
    """
    doc = {k: v for k, v in detail.items() if k not in ("status_code", "status_label", "photos")}
    doc["status"] = detail.get("status_label") or STATUS_LABEL_MAP.get(detail.get("status_code"))
    doc["property_type"] = property_type
    doc["source"] = source
    doc["photos"] = []
    doc["_source_photo_urls"] = detail.get("photos", [])
    return doc


def upsert_listing(listings: Collection, doc: dict, run_id, seen_at: str | None = None) -> str:
    """Insert or update one listing doc, keyed by mls_number. Returns
    'added' or 'updated'. Preserves any existing `photos` on update (this
    doc's own `photos: []` must not clobber prior photo-pipeline state), and
    reapplies any standing `admin.manual_overrides`/`admin.status_override`
    on top of the freshly-scraped fields -- otherwise a hand correction made
    via the MCP tools would silently get overwritten by the next scrape."""
    seen_at = seen_at or now_iso()
    mls_number = doc["mls_number"]
    existing = listings.find_one({"_id": mls_number}, {"photos": 1, "admin": 1})

    update = dict(doc)
    if existing and existing.get("photos"):
        update["photos"] = existing["photos"]

    admin = (existing or {}).get("admin") or {}
    for field, value in (admin.get("manual_overrides") or {}).items():
        update[field] = value
    if admin.get("status_override"):
        update["status"] = admin["status_override"]

    update["last_seen_at"] = seen_at
    update["last_scrape_run_id"] = run_id
    update["is_active_on_source"] = True
    update["updated_at"] = seen_at

    set_on_insert = {"first_seen_at": seen_at, "created_at": seen_at, "admin": _default_admin()}

    listings.update_one(
        {"_id": mls_number},
        {"$set": update, "$setOnInsert": set_on_insert},
        upsert=True,
    )
    return "updated" if existing else "added"


def mark_removed_listings(listings: Collection, seen_mls_numbers: set[str], run_id) -> list[str]:
    """Flip is_active_on_source=False for any previously-active listing not
    seen in this run. Returns the list of mls_numbers newly marked removed."""
    cursor = listings.find(
        {"is_active_on_source": True, "_id": {"$nin": sorted(seen_mls_numbers)}}, {"_id": 1}
    )
    removed = [doc["_id"] for doc in cursor]
    if removed:
        listings.update_many(
            {"_id": {"$in": removed}},
            {"$set": {"is_active_on_source": False, "last_scrape_run_id": run_id}},
        )
    return removed


def _default_admin() -> dict:
    return {
        "featured": False,
        "hidden": False,
        "internal_notes": None,
        "tags": [],
        "manual_overrides": {},
        "status_override": None,
    }


def start_scrape_run(scrape_runs: Collection, trigger: str):
    run = {
        "started_at": now_iso(),
        "finished_at": None,
        "trigger": trigger,
        "status": "running",
        "listings_seen": [],
        "listings_added": [],
        "listings_updated": [],
        "listings_removed": [],
        "errors": [],
        "photos_downloaded": 0,
        "photos_failed": 0,
    }
    result = scrape_runs.insert_one(run)
    return result.inserted_id


def finish_scrape_run(scrape_runs: Collection, run_id, status: str, **fields) -> None:
    fields["finished_at"] = now_iso()
    fields["status"] = status
    scrape_runs.update_one({"_id": run_id}, {"$set": fields})


def ensure_indexes(db: Database) -> None:
    listings = db["listings"]
    listings.create_index("status")
    listings.create_index("property_type")
    listings.create_index([("is_active_on_source", 1), ("status", 1)])
