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
