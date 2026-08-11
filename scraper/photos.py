# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests>=2.31",
#     "pillow>=10.0",
#     "boto3>=1.34",
#     "pymongo[srv]>=4.6",
#     "python-dotenv>=1.0",
# ]
# ///
"""Download, resize, and upload listing photos to Cloudflare R2.

Run standalone (`uv run scraper/photos.py --all` / `--mls <mls_number>`) or
via the `reupload_listing_photos` MCP tool -- both invoke this script the
same way. Only processes listings with `_source_photo_urls` staged by
scraper/run.py and an empty/missing `photos` array, unless --force is
passed. Verified (2026-08-10) that these source photo URLs are not
session-bound -- a URL captured minutes earlier in a completely separate,
cookie-less request still resolved -- so running this as a separate step
after run.py, rather than inline during the scrape, is safe.
"""

import argparse
import io
import os
import sys
from pathlib import Path

import boto3
from dotenv import load_dotenv
from PIL import Image
from pymongo import MongoClient

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / "scraper" / ".env")
load_dotenv(REPO_ROOT / ".env")

from fetch import RateLimitedSession  # noqa: E402

THUMB_MAX_DIM = 400
FULL_MAX_DIM = 1600
JPEG_QUALITY = 82


def resize_jpeg(raw: bytes, max_dim: int) -> bytes:
    img = Image.open(io.BytesIO(raw))
    img = img.convert("RGB")
    img.thumbnail((max_dim, max_dim), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return out.getvalue()


def r2_client():
    account_id = os.environ["R2_ACCOUNT_ID"]
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def process_listing(session, s3, bucket: str, mls_number: str, source_urls: list[str]):
    photos = []
    downloaded, failed = 0, 0
    for seq, url in enumerate(source_urls):
        try:
            raw = session.get_bytes(url)
            thumb = resize_jpeg(raw, THUMB_MAX_DIM)
            full = resize_jpeg(raw, FULL_MAX_DIM)
            key_thumb = f"listings/{mls_number}/{seq}_thumb.jpg"
            key_full = f"listings/{mls_number}/{seq}_full.jpg"
            s3.put_object(Bucket=bucket, Key=key_thumb, Body=thumb, ContentType="image/jpeg")
            s3.put_object(Bucket=bucket, Key=key_full, Body=full, ContentType="image/jpeg")
            photos.append(
                {"seq": seq, "r2_key_thumb": key_thumb, "r2_key_full": key_full, "is_primary": seq == 0}
            )
            downloaded += 1
        except Exception as exc:  # noqa: BLE001 -- one bad photo must not abort the listing
            print(f"  photo {seq} failed for {mls_number}: {exc}", file=sys.stderr)
            failed += 1
    return photos, downloaded, failed


def run(target_mls: str | None, force: bool) -> None:
    mongo_uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    mongo_db = os.environ.get("MONGODB_DB", "dagrealty")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    listings = client[mongo_db]["listings"]
    bucket = os.environ["R2_BUCKET"]

    query: dict = {"_source_photo_urls": {"$exists": True, "$ne": []}}
    if not force:
        query["$or"] = [{"photos": {"$exists": False}}, {"photos": []}]
    if target_mls:
        query["_id"] = target_mls

    docs = list(listings.find(query, {"_source_photo_urls": 1}))
    if not docs:
        print("no listings need photo processing")
        client.close()
        return

    session = RateLimitedSession()
    s3 = r2_client()
    total_downloaded, total_failed = 0, 0
    for doc in docs:
        mls_number = doc["_id"]
        source_urls = doc.get("_source_photo_urls", [])
        print(f"processing {mls_number}: {len(source_urls)} photos")
        photos, downloaded, failed = process_listing(session, s3, bucket, mls_number, source_urls)
        listings.update_one(
            {"_id": mls_number},
            {"$set": {"photos": photos}, "$unset": {"_source_photo_urls": ""}},
        )
        total_downloaded += downloaded
        total_failed += failed
    client.close()
    print(f"done: {len(docs)} listings, {total_downloaded} photos uploaded, {total_failed} failed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill listing photos into Cloudflare R2.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Process every listing needing photos.")
    group.add_argument("--mls", metavar="MLS_NUMBER", help="Process a single listing.")
    parser.add_argument("--force", action="store_true", help="Reprocess even if photos already exist.")
    args = parser.parse_args()
    run(target_mls=args.mls, force=args.force)


if __name__ == "__main__":
    main()
