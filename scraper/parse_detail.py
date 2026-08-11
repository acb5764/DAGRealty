"""Parse a USAMLS "expanded" listing detail page into a flat dict matching
the `listings` Mongo schema, plus rooms[] and photos[] (ordered, absolute
URLs — index 0 is the primary/main photo).

Field layout on the source page is a flat sequence of
`<div class="expanded_field_display"><span class="expanded_field_heading">
Field:</span><span class="expanded_field_value">value</span></div>` blocks,
split arbitrarily across two `<td>` columns for two-column display — document
order (not column) is what keeps "Room 1 Level"/"Room 1 Room"/... together,
so we always read top-to-bottom in document order rather than per-column.
"""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

_ROOM_FIELD_RE = re.compile(r"^Room (\d+) (Level|Room|Size|Description)$")
_STATUS_RE = re.compile(
    r"MLS Number:\s*</span>\s*\d+&nbsp;<span[^>]*>([A-Za-z]+)</span>\s*\(([^)]+)\)"
)
_PHOTO_ARRAY_RE = re.compile(r"new additional_photo_array2\((.*?)\)", re.DOTALL)
_QUOTED_RE = re.compile(r"'([^']*)'")


def _clean(text: str | None) -> str | None:
    if text is None:
        return None
    text = text.replace("\xa0", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text or None


def _to_int(text: str | None) -> int | None:
    text = _clean(text)
    if not text:
        return None
    digits = re.sub(r"[^\d-]", "", text)
    return int(digits) if digits and digits not in ("-",) else None


def _to_float(text: str | None) -> float | None:
    text = _clean(text)
    if not text:
        return None
    cleaned = re.sub(r"[^\d.\-]", "", text)
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _to_bool(text: str | None) -> bool | None:
    text = _clean(text)
    if not text:
        return None
    lowered = text.lower()
    if lowered in ("yes", "y", "true"):
        return True
    if lowered in ("no", "n", "false"):
        return False
    return None


def _to_list(text: str | None) -> list[str]:
    text = _clean(text)
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


_DIRECT_FIELDS = {
    "MLS Number": ("mls_number", _clean),
    "List Price": ("list_price", _to_int),
    "Street #": ("street_number", _clean),
    "Address": ("address", _clean),
    "City": ("city", _clean),
    "State": ("state", _clean),
    "Zip Code": ("zip", _clean),
    "Region": ("region", _clean),
    "County": ("county", _clean),
    "House Style": ("house_style", _clean),
    "Bedrooms": ("bedrooms", _to_int),
    "Full Baths": ("full_baths", _to_int),
    "3/4 Baths": ("three_quarter_baths", _to_int),
    "Half Baths": ("half_baths", _to_int),
    "Total Baths": ("total_baths", _to_float),
    "Total SqFt": ("total_sqft", _to_int),
    "Basement": ("basement", _clean),
    "Walkout Basement": ("walkout_basement", _to_bool),
    "# Fireplaces": ("fireplaces_count", _to_int),
    "Exterior": ("exterior", _clean),
    "Roof Type": ("roof_type", _clean),
    "AC Type": ("ac_type", _clean),
    "Heating Type": ("heating_type", _clean),
    "Apx Year Built": ("year_built", _to_int),
    "Zoning": ("zoning", _clean),
    "Parking": ("parking", _clean),
    "# Garage Spaces": ("garage_spaces", _to_int),
    "Driveway": ("driveway", _clean),
    "Elementary School": ("elementary_school", _clean),
    "Jr High/Middle School": ("middle_school", _clean),
    "High School": ("high_school", _clean),
    "Included": ("included", _clean),
    "Not Included": ("not_included", _clean),
    "Water Type": ("water_type", _clean),
    "Sewer Type": ("sewer_type", _clean),
    "Property Features": ("property_features", _to_list),
    "Mobile Home": ("mobile_home", _to_bool),
    "Tax Year": ("tax_year", _to_int),
    "Total Taxes": ("total_taxes", _to_float),
    "Flood Zone": ("flood_zone", _clean),
    "Apx Acreage": ("acreage", _to_float),
    "Frontage Feet": ("frontage_feet", _to_float),
    "Depth Feet": ("depth_feet", _to_float),
    "Public Comments": ("public_comments", _clean),
    "Amenities": ("amenities", _to_list),
}


def _parse_status(html: str) -> tuple[str | None, str | None]:
    match = _STATUS_RE.search(html)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def _parse_photos(html: str, page_url: str) -> list[str]:
    match = _PHOTO_ARRAY_RE.search(html)
    if not match:
        return []
    return [urljoin(page_url, url) for url in _QUOTED_RE.findall(match.group(1))]


def _parse_virtual_tour(soup: BeautifulSoup) -> str | None:
    tag = soup.find("a", attrs={"target": "virtual_tour"})
    return tag["href"] if tag and tag.has_attr("href") else None


def parse_detail_page(html: str, page_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    fields: dict[str, object] = {}
    rooms: dict[int, dict] = {}

    for heading_span in soup.select("span.expanded_field_heading"):
        heading = _clean(heading_span.get_text())
        if not heading:
            continue
        heading = heading.rstrip(":")
        value_span = heading_span.find_next_sibling("span", class_="expanded_field_value")
        raw_value = value_span.get_text() if value_span else None

        room_match = _ROOM_FIELD_RE.match(heading)
        if room_match:
            room_num = int(room_match.group(1))
            room_field = room_match.group(2).lower()
            rooms.setdefault(room_num, {})[room_field] = _clean(raw_value)
            continue

        if heading in _DIRECT_FIELDS:
            key, converter = _DIRECT_FIELDS[heading]
            fields[key] = converter(raw_value)

    status_code, status_label = _parse_status(html)

    return {
        **fields,
        "status_code": status_code,
        "status_label": status_label,
        "rooms": [
            {"number": num, **rooms[num]}
            for num in sorted(rooms)
            if any(rooms[num].values())
        ],
        "photos": _parse_photos(html, page_url),
        "virtual_tour_url": _parse_virtual_tour(soup),
    }
