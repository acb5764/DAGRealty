"""Mongo connection + shared helpers for the dagrealty-mongo MCP server."""

import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

REPO_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(Path(__file__).resolve().parent / ".env")

MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.environ.get("MONGODB_DB", "dagrealty")

_client = None


def get_db():
    global _client
    if _client is None:
        # 20s, not the pymongo default of 5s: the poller that runs this tool
        # restarts right after the Mac wakes from sleep, and the very first
        # mongodb+srv:// SRV lookup can land before Wi-Fi/DNS has finished
        # coming back up, otherwise timing out on a perfectly healthy DB.
        _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=20000)
    return _client[MONGODB_DB]


def listings_collection():
    return get_db()["listings"]


def scrape_runs_collection():
    return get_db()["scrape_runs"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


VALID_STATUSES = {"Active", "Pending", "Contingent", "Sold", "Off-Market", "Withdrawn", "Expired"}
VALID_PROPERTY_TYPES = {"Residential", "Multi-Unit", "Land", "Farm", "Commercial"}

# Fields the scraper owns (see scraper/parse_detail.py's _DIRECT_FIELDS) --
# set_manual_override refuses to target admin.*/_id/mls_number directly, since
# those aren't scraped public fields subject to being clobbered by a resync.
NON_OVERRIDABLE_FIELDS = {"_id", "mls_number", "admin", "photos", "_source_photo_urls"}


def strip_internal_id(doc: dict) -> dict:
    doc = dict(doc)
    doc.pop("_id", None)
    return doc
