import pytest

from census_mcp.places import (
    normalize_name,
    parse_place_rows,
    place_name_key,
    resolve_state,
    state_for_geoid,
)

# Header (18 pipe-delimited columns) + a UTF-8 BOM, as the real file ships.
_HEADER = (
    "﻿OID_ZCTA5_20|GEOID_ZCTA5_20|NAMELSAD_ZCTA5_20|AREALAND_ZCTA5_20|"
    "AREAWATER_ZCTA5_20|MTFCC_ZCTA5_20|CLASSFP_ZCTA5_20|FUNCSTAT_ZCTA5_20|"
    "OID_PLACE_20|GEOID_PLACE_20|NAMELSAD_PLACE_20|AREALAND_PLACE_20|"
    "AREAWATER_PLACE_20|MTFCC_PLACE_20|CLASSFP_PLACE_20|FUNCSTAT_PLACE_20|"
    "AREALAND_PART|AREAWATER_PART"
)
# A place with no ZCTA — empty ZCTA columns — must be dropped.
_PLACE_ONLY = "||||||||2789|0101852|Anniston city|118685613|180468|G4110|C1|A|99|35"
# ZCTA 02139 ∩ Cambridge city, MA (FIPS 25): 400 of 1000 sq m land -> 0.40 coverage.
_CAMBRIDGE = (
    "1|02139|ZCTA5 02139|1000|0|G6350|B5|S|7|2511000|Cambridge city|"
    "5000|0|G4110|C1|A|400|0"
)
# ZCTA 98260 ∩ Langley CDP, WA (FIPS 53): wholly within -> 1.0 coverage.
_LANGLEY = (
    "2|98260|ZCTA5 98260|2000|10|G6350|B5|S|8|5340390|Langley CDP|"
    "2000|0|G4210|U1|S|2000|0"
)


def test_parse_drops_unmatched_and_computes_coverage() -> None:
    text = "\n".join([_HEADER, _PLACE_ONLY, _CAMBRIDGE, _LANGLEY])
    rows = parse_place_rows(text)

    assert len(rows) == 2  # the place-only row is filtered out
    by_zcta = {r["zcta"]: r for r in rows}

    cam = by_zcta["02139"]
    assert cam["name_display"] == "Cambridge city"
    assert cam["name_norm"] == "cambridge city"
    assert cam["name_key"] == "cambridge"
    assert cam["state"] == "MA"
    assert cam["coverage"] == pytest.approx(0.40)

    lang = by_zcta["98260"]
    assert lang["name_key"] == "langley"  # CDP descriptor stripped
    assert lang["state"] == "WA"
    assert lang["coverage"] == pytest.approx(1.0)


def test_parse_empty_and_header_only() -> None:
    assert parse_place_rows("") == []
    assert parse_place_rows(_HEADER) == []


def test_parse_clamps_coverage_to_one() -> None:
    # A defensive row where the intersection area exceeds the ZCTA's land area.
    weird = (
        "9|55555|ZCTA5 55555|100|0|G6350|B5|S|7|2511000|Foo city|9|0|G4110|C1|A|250|0"
    )
    rows = parse_place_rows("\n".join([_HEADER, weird]))
    assert rows[0]["coverage"] == pytest.approx(1.0)  # 250/100 clamped


def test_normalize_name_collapses_whitespace() -> None:
    assert normalize_name("  West   Hollywood  ") == "west hollywood"


@pytest.mark.parametrize(
    ("display", "key"),
    [
        ("Cambridge city", "cambridge"),
        ("Langley CDP", "langley"),
        ("Dauphin Island town", "dauphin island"),
        ("Indianapolis city (balance)", "indianapolis"),
        ("Carson City", "carson"),  # no appended descriptor -> trailing word stripped
        ("Lake Village", "lake"),
    ],
)
def test_place_name_key_strips_descriptor(display: str, key: str) -> None:
    assert place_name_key(display) == key


def test_state_for_geoid() -> None:
    assert state_for_geoid("2511000") == "MA"  # FIPS 25
    assert state_for_geoid("0644000") == "CA"  # FIPS 06
    assert state_for_geoid("7212345") == "PR"  # island area
    assert state_for_geoid("9999999") is None  # unknown FIPS


def test_resolve_state_abbrev_name_and_unknown() -> None:
    assert resolve_state("ma") == "MA"
    assert resolve_state("MA") == "MA"
    assert resolve_state("Massachusetts") == "MA"
    assert resolve_state("  new york ") == "NY"
    with pytest.raises(ValueError, match="Unknown state"):
        resolve_state("ZZ")
