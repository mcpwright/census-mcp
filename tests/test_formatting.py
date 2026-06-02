from census_mcp.formatting import pct, to_income, to_zip_info


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
