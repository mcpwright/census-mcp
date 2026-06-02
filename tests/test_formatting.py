import pytest

from census_mcp.formatting import (
    _sum,
    available_metrics,
    metric_value,
    pct,
    to_acs_value,
    to_comparison,
    to_demographics,
    to_education,
    to_housing,
    to_income,
    to_zip_info,
)


def test_pct() -> None:
    assert pct(25, 100) == 25.0
    assert pct(1, 3) == 33.3  # rounded to 1 decimal
    assert pct(5, 0) is None  # divide by zero → None
    assert pct(None, 10) is None
    assert pct(10, None) is None


def test_to_zip_info_handles_missing() -> None:
    z = to_zip_info({"zcta": "00601", "name": None, "population": None}, 2023)
    assert z.zcta == "00601"
    assert z.population is None
    assert z.vintage == 2023


def test_to_demographics() -> None:
    rec: dict[str, object] = {
        "zcta": "90069",
        "name": "ZCTA5 90069",
        "population": 22000,
        "median_age": 39.5,
    }
    d = to_demographics(rec, 2023)
    assert d.population == 22000
    assert d.median_age == 39.5
    assert d.vintage == 2023


def test_to_demographics_handles_missing_age() -> None:
    d = to_demographics({"zcta": "00601", "population": None, "median_age": None}, 2023)
    assert d.population is None
    assert d.median_age is None


def test_to_housing_computes_owner_pct() -> None:
    rec: dict[str, object] = {
        "zcta": "90069",
        "name": "ZCTA5 90069",
        "median_home_value": 1200000,
        "median_gross_rent": 2200,
        "occupied_units": 13800,
        "owner_occupied_units": 4000,
    }
    h = to_housing(rec, 2023)
    assert h.median_home_value == 1200000
    assert h.median_gross_rent == 2200
    assert h.occupied_units == 13800
    assert h.owner_occupied_pct == 29.0  # 4000 / 13800
    assert h.vintage == 2023


def test_to_housing_none_when_units_unknown() -> None:
    h = to_housing({"zcta": "00601", "owner_occupied_units": 100}, 2023)
    assert h.owner_occupied_pct is None  # no occupied_units denominator


def test_sum_returns_none_if_any_component_missing() -> None:
    rec: dict[str, object] = {"a": 1, "b": 2, "c": None}
    assert _sum(rec, ("a", "b")) == 3
    assert _sum(rec, ("a", "c")) is None  # suppressed component → None, not partial


def test_to_education_computes_shares() -> None:
    rec: dict[str, object] = {
        "zcta": "90069",
        "name": "ZCTA5 90069",
        "pop_25_plus": 19000,
        "bachelors": 6000,
        "masters": 3000,
        "professional_degree": 800,
        "doctorate": 400,
    }
    e = to_education(rec, 2023)
    assert e.population_25_plus == 19000
    assert e.bachelors_plus_pct == 53.7  # (6000+3000+800+400) / 19000
    assert e.graduate_or_professional_pct == 22.1  # (3000+800+400) / 19000
    assert e.vintage == 2023


def test_to_education_none_when_component_suppressed() -> None:
    rec: dict[str, object] = {
        "zcta": "00601",
        "pop_25_plus": 11000,
        "bachelors": 1200,
        "masters": None,  # suppressed
        "professional_degree": 60,
        "doctorate": 30,
    }
    e = to_education(rec, 2023)
    assert e.bachelors_plus_pct is None
    assert e.graduate_or_professional_pct is None


def test_to_income_computes_derived_pct() -> None:
    rec: dict[str, object] = {
        "zcta": "90069",
        "name": "ZCTA5 90069",
        "median_household_income": 105000,
        "per_capita_income": 98000,
        "total_households": 14000,
        "households_200k_plus": 3500,
    }
    inc = to_income(rec, 2023)
    assert inc.median_household_income == 105000
    assert inc.households_200k_plus_pct == 25.0  # 3500 / 14000
    assert inc.vintage == 2023


def test_to_income_none_when_share_unknown() -> None:
    rec: dict[str, object] = {
        "zcta": "00601",
        "name": "ZCTA5 00601",
        "median_household_income": 15000,
        "total_households": 6000,
        "households_200k_plus": None,
    }
    inc = to_income(rec, 2023)
    assert inc.households_200k_plus_pct is None


def test_to_acs_value_numeric_string_and_missing() -> None:
    rec: dict[str, object] = {
        "zcta": "90069",
        "name": "ZCTA5 90069",
        "median_household_income": 105000,
        "median_age": 39.5,
    }
    num = to_acs_value(rec, "B19013_001E", "median_household_income", 2023)
    assert num.value == 105000
    assert num.variable == "B19013_001E"
    assert num.column == "median_household_income"

    # the 'name' variable is a string
    name = to_acs_value(rec, "NAME", "name", 2023)
    assert name.value == "ZCTA5 90069"

    # a column absent from the record → None
    missing = to_acs_value(rec, "B25077_001E", "median_home_value", 2023)
    assert missing.value is None


def test_metric_value_direct_and_derived() -> None:
    rec: dict[str, object] = {
        "median_household_income": 105000,
        "owner_occupied_units": 4000,
        "occupied_units": 13800,
    }
    assert metric_value(rec, "median_household_income") == 105000.0
    assert metric_value(rec, "owner_occupied_pct") == 29.0


def test_metric_value_unknown_lists_choices() -> None:
    with pytest.raises(ValueError, match="Unknown metric"):
        metric_value({}, "not_a_metric")
    assert "median_household_income" in available_metrics()


def test_to_comparison_ranks_desc_missing_last() -> None:
    rows: list[tuple[str, dict[str, object] | None]] = [
        ("00601", {"zcta": "00601", "name": "B", "median_household_income": 15000}),
        ("90069", {"zcta": "90069", "name": "A", "median_household_income": 105000}),
        ("99999", None),  # not in the store → value None, ranked last
    ]
    comp = to_comparison(rows, "median_household_income", 2023)
    assert [r.zcta for r in comp.results] == ["90069", "00601", "99999"]
    assert comp.results[0].value == 105000.0
    assert comp.results[-1].value is None
    assert comp.metric == "median_household_income"
    assert comp.vintage == 2023
