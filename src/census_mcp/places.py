"""2020 Census ZCTA-to-Place relationship — the data layer behind ``find_zips``.

Reverse lookup (place name -> candidate ZIPs) needs a mapping the ACS dataset
doesn't carry: the ACS store is keyed by ZCTA and has no place/city names. The
Census publishes exactly that mapping as a public-domain flat file — the **2020
ZCTA5-to-Place relationship file** — listing every (ZCTA, place) pair whose
geographies intersect, with the land area of the intersection.

This module parses that pipe-delimited file, normalizes place names for matching
(Census appends a legal/statistical descriptor, e.g. "Cambridge city"), and
derives the state from the place GEOID (its first two digits are the state FIPS;
the file has no state column).

The relationship is **2020 decennial geography** — effectively static, unlike
the annual ACS vintage. ZCTAs do not nest inside places: one place spans many
ZCTAs and one ZCTA can span many places, so place->ZIP is inherently a ranked
list of *candidates* (we rank by how much of each ZCTA's land lies in the place).
"""

from __future__ import annotations

# 2020 ZCTA5-to-Place national relationship file (pipe-delimited, public domain).
ZCTA_PLACE_REL_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/"
    "tab20_zcta520_place20_natl.txt"
)

# Geography vintage of the relationship file (2020 decennial geography), distinct
# from the ACS 5-year vintage the other tools report.
PLACE_REL_VINTAGE = 2020

# Columns we read from the relationship file (see the file's header row).
_F_ZCTA = "GEOID_ZCTA5_20"  # 5-digit ZCTA
_F_PLACE_GEOID = "GEOID_PLACE_20"  # 7-digit place GEOID; first 2 = state FIPS
_F_PLACE_NAME = "NAMELSAD_PLACE_20"  # place name + descriptor, e.g. "Cambridge city"
_F_AREALAND_ZCTA = "AREALAND_ZCTA5_20"  # land area of the whole ZCTA
_F_AREALAND_PART = "AREALAND_PART"  # land area of the ZCTA-in-place intersection

# Trailing legal/statistical-area descriptors Census appends to a place name.
# Ordered most-specific (multi-word) first so they strip before single words.
_LSAD_SUFFIXES = (
    "metropolitan government",
    "consolidated government",
    "unified government",
    "metro government",
    "zona urbana",
    "comunidad",
    "municipality",
    "borough",
    "village",
    "township",
    "city",
    "town",
    "cdp",
)

# 2-digit state FIPS -> USPS abbreviation (50 states, DC, and the island areas).
STATE_FIPS: dict[str, str] = {
    "01": "AL",
    "02": "AK",
    "04": "AZ",
    "05": "AR",
    "06": "CA",
    "08": "CO",
    "09": "CT",
    "10": "DE",
    "11": "DC",
    "12": "FL",
    "13": "GA",
    "15": "HI",
    "16": "ID",
    "17": "IL",
    "18": "IN",
    "19": "IA",
    "20": "KS",
    "21": "KY",
    "22": "LA",
    "23": "ME",
    "24": "MD",
    "25": "MA",
    "26": "MI",
    "27": "MN",
    "28": "MS",
    "29": "MO",
    "30": "MT",
    "31": "NE",
    "32": "NV",
    "33": "NH",
    "34": "NJ",
    "35": "NM",
    "36": "NY",
    "37": "NC",
    "38": "ND",
    "39": "OH",
    "40": "OK",
    "41": "OR",
    "42": "PA",
    "44": "RI",
    "45": "SC",
    "46": "SD",
    "47": "TN",
    "48": "TX",
    "49": "UT",
    "50": "VT",
    "51": "VA",
    "53": "WA",
    "54": "WV",
    "55": "WI",
    "56": "WY",
    "60": "AS",
    "66": "GU",
    "69": "MP",
    "72": "PR",
    "78": "VI",
}

# Full state/territory name (lowercased) -> USPS abbreviation, for the filter.
STATE_NAMES: dict[str, str] = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "district of columbia": "DC",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
    "american samoa": "AS",
    "guam": "GU",
    "northern mariana islands": "MP",
    "puerto rico": "PR",
    "virgin islands": "VI",
    "u.s. virgin islands": "VI",
}

_STATE_ABBRS = set(STATE_FIPS.values())


def normalize_name(name: str) -> str:
    """Lowercase a place name and collapse internal whitespace."""
    return " ".join(name.lower().split())


def place_name_key(name: str) -> str:
    """Match key for a place: normalized, with a trailing Census descriptor removed.

    ``"Cambridge city"`` -> ``"cambridge"``, ``"Langley CDP"`` -> ``"langley"``,
    ``"Indianapolis city (balance)"`` -> ``"indianapolis"``. Names without a known
    descriptor are returned normalized but otherwise unchanged.
    """
    key = normalize_name(name)
    # Drop a trailing parenthetical such as "(balance)".
    if key.endswith(")") and "(" in key:
        key = key[: key.rindex("(")].strip()
    for suffix in _LSAD_SUFFIXES:
        if key.endswith(" " + suffix):
            return key[: -(len(suffix) + 1)].strip()
    return key


def state_for_geoid(place_geoid: str) -> str | None:
    """USPS state abbreviation for a place GEOID (first two digits are the FIPS)."""
    return STATE_FIPS.get(place_geoid[:2]) if len(place_geoid) >= 2 else None


def resolve_state(state: str) -> str:
    """Resolve a 2-letter USPS code or full state name to a USPS abbreviation.

    Both match case-insensitively. Raises ``ValueError`` for an unknown state.
    """
    s = state.strip()
    if len(s) == 2 and s.upper() in _STATE_ABBRS:
        return s.upper()
    name = normalize_name(s)
    if name in STATE_NAMES:
        return STATE_NAMES[name]
    raise ValueError(
        f"Unknown state {state!r}. Use a 2-letter USPS code (e.g. 'MA') or a "
        "full state name (e.g. 'Massachusetts')."
    )


def _land_fraction(part: str, whole: str) -> float | None:
    """Share of a ZCTA's land that lies in a place: ``AREALAND_PART / AREALAND_ZCTA``.

    Returns a 0-1 fraction (clamped — the intersection can't exceed the whole),
    or None if either area is unparseable or the ZCTA has no land area (a
    water-only ZCTA). Tolerant of a decimal form should Census ever ship one.
    """
    try:
        p, w = float(part), float(whole)
    except ValueError:
        return None
    if w <= 0:
        return None
    return min(p / w, 1.0)


def parse_place_rows(text: str) -> list[dict[str, object]]:
    """Parse the relationship file into one record per (ZCTA, place) intersection.

    The file is pipe-delimited with a header row (and a UTF-8 BOM). Rows where a
    ZCTA covers unincorporated land (no place) or a place has no ZCTA are skipped
    — we keep only rows with both a ZCTA and a place. Each kept record carries the
    ZCTA, the Census place name, the derived state, and ``coverage`` (the 0-1
    share of the ZCTA's land within the place).
    """
    lines = text.splitlines()
    if not lines:
        return []
    header = lines[0].lstrip("﻿").split("|")
    idx = {name: i for i, name in enumerate(header)}
    try:
        i_zcta = idx[_F_ZCTA]
        i_geoid = idx[_F_PLACE_GEOID]
        i_name = idx[_F_PLACE_NAME]
        i_az = idx[_F_AREALAND_ZCTA]
        i_part = idx[_F_AREALAND_PART]
    except KeyError as exc:
        raise ValueError(
            f"Unexpected relationship-file layout: missing column {exc}."
        ) from None

    records: list[dict[str, object]] = []
    for line in lines[1:]:
        if not line:
            continue
        f = line.split("|")
        if len(f) <= i_part:
            continue
        zcta, place_geoid = f[i_zcta].strip(), f[i_geoid].strip()
        if not zcta or not place_geoid:  # place-only or ZCTA-only row
            continue
        name_display = f[i_name].strip()
        records.append(
            {
                "zcta": zcta,
                "name_display": name_display,
                "name_norm": normalize_name(name_display),
                "name_key": place_name_key(name_display),
                "state": state_for_geoid(place_geoid),
                "coverage": _land_fraction(f[i_part], f[i_az]),
            }
        )
    return records
