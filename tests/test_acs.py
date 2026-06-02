import pytest

from census_mcp.acs import (
    ACS_VARIABLES,
    GEO_COLUMN,
    parse_rows,
    resolve_variable,
    sanitize,
)


def test_sanitize_numbers_and_strings() -> None:
    assert sanitize("123", "int") == 123
    assert sanitize("12.5", "float") == 12.5
    assert sanitize("Foo", "str") == "Foo"
    assert sanitize("  spaced  ", "str") == "spaced"


def test_sanitize_missing_and_suppressed() -> None:
    assert sanitize("", "int") is None
    assert sanitize("-", "int") is None
    assert sanitize(None, "int") is None
    assert sanitize("not-a-number", "float") is None
    # Census uses large negative sentinels for suppressed values.
    assert sanitize("-666666666", "int") is None


def test_parse_rows_maps_header_to_columns() -> None:
    header = [*ACS_VARIABLES, GEO_COLUMN]
    values = [
        "ZCTA5 90210",  # NAME
        "21000",  # population
        "45.0",  # median_age
        "150000",  # median_household_income
        "120000",  # per_capita_income
        "9000",  # total_households
        "2500",  # households_200k_plus
        "2000000",  # median_home_value
        "3000",  # median_gross_rent
        "8800",  # occupied_units
        "5000",  # owner_occupied_units
        "16000",  # pop_25_plus
        "7000",  # bachelors
        "3500",  # masters
        "900",  # professional_degree
        "500",  # doctorate
    ]
    assert len(values) == len(ACS_VARIABLES)
    recs = parse_rows([header, [*values, "90210"]])

    assert len(recs) == 1
    r = recs[0]
    assert r["zcta"] == "90210"
    assert r["name"] == "ZCTA5 90210"
    assert r["population"] == 21000
    assert r["median_age"] == 45.0
    assert r["households_200k_plus"] == 2500


def test_parse_rows_handles_empty_and_header_only() -> None:
    assert parse_rows([]) == []
    assert parse_rows([[*ACS_VARIABLES, GEO_COLUMN]]) == []


def test_resolve_variable_by_code_and_column() -> None:
    assert resolve_variable("B19013_001E") == ("B19013_001E", "median_household_income")
    assert resolve_variable("median_household_income") == (
        "B19013_001E",
        "median_household_income",
    )
    # case-insensitive for both forms
    assert resolve_variable("b19013_001e")[1] == "median_household_income"
    assert resolve_variable("MEDIAN_HOUSEHOLD_INCOME")[0] == "B19013_001E"


def test_resolve_variable_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown ACS variable"):
        resolve_variable("B99999_999E")
