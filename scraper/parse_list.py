"""Parse the USAMLS office-listings pages (paginated grid of summary cards).

Used only to discover which MLS numbers currently exist and which property
type each belongs to (this_format is only exposed as a filter, not as a
per-listing field on the detail page) — full field data comes from
parse_detail.py.
"""

import re

from bs4 import BeautifulSoup

LISTING_OFF_ID = 35  # David A Gardner's office id on this MLS site

PROPERTY_TYPES = {
    1: "Residential",
    2: "Multi-Unit",
    3: "Land",
    4: "Farm",
    5: "Commercial",
}

_TOTAL_RE = re.compile(r"of\s*<span[^>]*>\s*(\d+)\s*</span>\s*Listing Result", re.IGNORECASE)
_MLS_RE = re.compile(r"mls_number=(\d+)")


def list_page_params(this_format: int, page: int = 1, sortby: int = 2) -> dict:
    params = {
        "content": "office_listings",
        "listing_off_id": LISTING_OFF_ID,
        "this_format": this_format,
        "sortby": sortby,
    }
    if page > 1:
        params["page"] = page
    return params


def parse_total_count(html: str) -> int:
    match = _TOTAL_RE.search(html)
    return int(match.group(1)) if match else 0


def parse_mls_numbers(html: str) -> list[str]:
    """Return the MLS numbers appearing on one list page, in page order,
    de-duplicated (each listing links to its detail page from both the photo
    and the "View Details" text, so the raw regex finds each twice)."""
    seen: list[str] = []
    for mls in _MLS_RE.findall(html):
        if mls not in seen:
            seen.append(mls)
    return seen


def fetch_mls_numbers_for_format(session, this_format: int, page_size: int = 9) -> list[str]:
    """Paginate through every page of one property-type filter and return
    every MLS number found, in the order the site presents them."""
    html = session.get("/dgrealestate/default.asp", params=list_page_params(this_format, page=1))
    total = parse_total_count(html)
    mls_numbers = parse_mls_numbers(html)

    page = 2
    while len(mls_numbers) < total:
        html = session.get(
            "/dgrealestate/default.asp", params=list_page_params(this_format, page=page)
        )
        page_mls = parse_mls_numbers(html)
        if not page_mls:
            break  # defensive: stop rather than loop forever if pagination ever disagrees with total
        for mls in page_mls:
            if mls not in mls_numbers:
                mls_numbers.append(mls)
        page += 1

    return mls_numbers


def discover_property_types(session) -> dict[str, str]:
    """Query every this_format filter (1-5) and return {mls_number:
    property_type_label}. A listing should appear under exactly one filter;
    if the source ever disagrees, the last filter checked wins and a warning
    is the caller's responsibility (see scraper/run.py)."""
    mapping: dict[str, str] = {}
    for code, label in PROPERTY_TYPES.items():
        for mls in fetch_mls_numbers_for_format(session, code):
            mapping[mls] = label
    return mapping


def discover_all_mls_numbers(session) -> list[str]:
    """The canonical "All Property Types" view (this_format=0) — the
    authoritative list of what's currently active on the source."""
    return fetch_mls_numbers_for_format(session, 0)
