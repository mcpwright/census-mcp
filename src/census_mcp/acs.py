"""ACS 5-year variable definitions.

Maps the Census ACS variable codes we pull to local store columns. Kept tight
(one bulk API call, well under the 50-variable limit). Detailed age brackets
(table B01001) are a planned follow-up; v1 ships population + median age.
"""

from __future__ import annotations

# (ACS variable code, store column, kind) — kind in {"str", "int", "float"}
ACS_FIELDS: list[tuple[str, str, str]] = [
    ("NAME", "name", "str"),
    ("B01003_001E", "population", "int"),
    ("B01002_001E", "median_age", "float"),
    ("B19013_001E", "median_household_income", "int"),
    ("B19301_001E", "per_capita_income", "int"),
    ("B19001_001E", "total_households", "int"),
    ("B19001_017E", "households_200k_plus", "int"),
    ("B25077_001E", "median_home_value", "int"),
    ("B25064_001E", "median_gross_rent", "int"),
    ("B25003_001E", "occupied_units", "int"),
    ("B25003_002E", "owner_occupied_units", "int"),
    ("B15003_001E", "pop_25_plus", "int"),
    ("B15003_022E", "bachelors", "int"),
    ("B15003_023E", "masters", "int"),
    ("B15003_024E", "professional_degree", "int"),
    ("B15003_025E", "doctorate", "int"),
]

# The codes to request from the API (in ACS_FIELDS order).
ACS_VARIABLES: list[str] = [code for code, _col, _kind in ACS_FIELDS]

# Lookups between ACS variable codes and local store columns.
_CODE_TO_COLUMN: dict[str, str] = {code: col for code, col, _kind in ACS_FIELDS}
_COLUMN_TO_CODE: dict[str, str] = {col: code for code, col, _kind in ACS_FIELDS}


def available_variables() -> list[str]:
    """Friendly store-column names available for direct lookup."""
    return [col for _code, col, _kind in ACS_FIELDS]


def resolve_variable(variable: str) -> tuple[str, str]:
    """Resolve an ACS code or store-column name to ``(code, column)``.

    Accepts either the ACS variable code (e.g. ``B19013_001E``) or the friendly
    store column (e.g. ``median_household_income``); both match
    case-insensitively. Raises ``ValueError`` listing the options if unknown.
    Limited to the variables held in the local store.
    """
    key = variable.strip()
    if key.upper() in _CODE_TO_COLUMN:
        return key.upper(), _CODE_TO_COLUMN[key.upper()]
    if key.lower() in _COLUMN_TO_CODE:
        return _COLUMN_TO_CODE[key.lower()], key.lower()
    raise ValueError(
        f"Unknown ACS variable {variable!r}. Available columns: "
        f"{', '.join(available_variables())} (or their ACS codes)."
    )


# The Census geography column for a ZCTA query (the response's last column).
GEO_COLUMN = "zip code tabulation area"

# Census annotation/suppression sentinels that mean "no data".
_MISSING = {"", "-", "N", "(X)", "*", "**", "null", "NaN", "-999999999"}


def sanitize(value: str | None, kind: str) -> object:
    """Coerce a raw Census cell to str/int/float, or None when missing/suppressed."""
    if value is None:
        return None
    v = value.strip()
    if v in _MISSING:
        return None
    if kind == "str":
        return v
    try:
        num = float(v)
    except ValueError:
        return None
    # Census uses large negative sentinels (e.g. -666666666) for suppressed values.
    if num <= -100_000_000:
        return None
    return int(num) if kind == "int" else num


def parse_rows(raw: list[list[str]]) -> list[dict[str, object]]:
    """Map a raw ACS API response (header row + data rows) to per-ZCTA records.

    The Census API returns a JSON matrix: the first row is column headers (the
    requested variable codes plus the geography column), each later row a ZCTA.
    Returns one ``{"zcta": ..., <store column>: <sanitized value>}`` dict per row.
    """
    if len(raw) < 2:
        return []
    header = raw[0]
    idx = {name: i for i, name in enumerate(header)}
    geo_i = idx.get(GEO_COLUMN, len(header) - 1)

    records: list[dict[str, object]] = []
    for row in raw[1:]:
        rec: dict[str, object] = {"zcta": row[geo_i]}
        for code, col, kind in ACS_FIELDS:
            i = idx.get(code)
            rec[col] = sanitize(row[i], kind) if i is not None else None
        records.append(rec)
    return records
