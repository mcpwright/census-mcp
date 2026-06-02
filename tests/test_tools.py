import pytest

from census_mcp import server


@pytest.mark.asyncio
async def test_lookup_zip(ctx) -> None:
    info = await server.lookup_zip("90069", ctx)
    assert info.zcta == "90069"
    assert info.name == "ZCTA5 90069"
    assert info.population == 22000
    assert info.vintage == 2023


@pytest.mark.asyncio
async def test_get_income(ctx) -> None:
    inc = await server.get_income("90069", ctx)
    assert inc.median_household_income == 105000
    assert inc.per_capita_income == 98000
    assert inc.households_200k_plus_pct == 25.0  # 3500 / 14000
    assert inc.vintage == 2023


@pytest.mark.asyncio
async def test_get_demographics(ctx) -> None:
    demo = await server.get_demographics("90069", ctx)
    assert demo.zcta == "90069"
    assert demo.population == 22000
    assert demo.median_age == 39.5
    assert demo.vintage == 2023


@pytest.mark.asyncio
async def test_get_housing(ctx) -> None:
    h = await server.get_housing("90069", ctx)
    assert h.median_home_value == 1200000
    assert h.median_gross_rent == 2200
    assert h.owner_occupied_pct == 29.0  # 4000 / 13800
    assert h.vintage == 2023


@pytest.mark.asyncio
async def test_get_education(ctx) -> None:
    e = await server.get_education("90069", ctx)
    assert e.population_25_plus == 19000
    assert e.bachelors_plus_pct == 53.7  # (6000+3000+800+400) / 19000
    assert e.graduate_or_professional_pct == 22.1  # (3000+800+400) / 19000
    assert e.vintage == 2023


@pytest.mark.asyncio
async def test_compare_zips_ranks_desc(ctx) -> None:
    comp = await server.compare_zips(
        ["00601", "90069", "99999"], "median_household_income", ctx
    )
    # 90069 (105000) > 00601 (15000) > 99999 (not in store → None, last)
    assert [r.zcta for r in comp.results] == ["90069", "00601", "99999"]
    assert comp.results[-1].value is None


@pytest.mark.asyncio
async def test_compare_zips_unknown_metric_raises(ctx) -> None:
    with pytest.raises(ValueError, match="Unknown metric"):
        await server.compare_zips(["90069"], "nope", ctx)


@pytest.mark.asyncio
async def test_compare_zips_empty_raises(ctx) -> None:
    with pytest.raises(ValueError, match="at least one ZIP"):
        await server.compare_zips([], "population", ctx)


@pytest.mark.asyncio
async def test_zip_plus_four_is_accepted(ctx) -> None:
    info = await server.lookup_zip("90069-1234", ctx)
    assert info.zcta == "90069"


@pytest.mark.asyncio
async def test_whitespace_is_tolerated(ctx) -> None:
    info = await server.lookup_zip("  90069  ", ctx)
    assert info.zcta == "90069"


@pytest.mark.asyncio
async def test_invalid_zip_raises(ctx) -> None:
    with pytest.raises(ValueError):
        await server.lookup_zip("abc", ctx)


@pytest.mark.asyncio
async def test_unknown_zip_raises_with_hint(ctx) -> None:
    with pytest.raises(ValueError, match="No Census ZCTA data"):
        await server.lookup_zip("99999", ctx)
