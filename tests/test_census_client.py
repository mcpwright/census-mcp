from datetime import UTC, datetime

import httpx
import pytest
import respx

from census_mcp.census_client import (
    ACS5_URL,
    CensusClient,
    CensusError,
    MissingKeyError,
)
from census_mcp.places import ZCTA_PLACE_REL_URL


@pytest.mark.asyncio
async def test_no_key_raises_missing_key() -> None:
    client = CensusClient(api_key=None)
    with pytest.raises(MissingKeyError):
        await client.fetch_all_zctas(["NAME"], 2023)
    await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_redirect_is_treated_as_missing_key() -> None:
    client = CensusClient(api_key="x")
    # Census 302-redirects missing/invalid keys to missing_key.html.
    respx.get(ACS5_URL.format(year=2023)).mock(
        return_value=httpx.Response(
            302, headers={"location": "https://api.census.gov/data/missing_key.html"}
        )
    )
    with pytest.raises(MissingKeyError):
        await client.fetch_zctas(["NAME"], 2023, ["90210"])
    await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_fetch_returns_parsed_json() -> None:
    client = CensusClient(api_key="x")
    payload = [["NAME", "zip code tabulation area"], ["ZCTA5 90210", "90210"]]
    respx.get(ACS5_URL.format(year=2023)).mock(
        return_value=httpx.Response(200, json=payload)
    )
    data = await client.fetch_zctas(["NAME"], 2023, ["90210"])
    assert data == payload
    await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_latest_year_returns_first_available() -> None:
    client = CensusClient(api_key="x")
    respx.get(url__regex=r"https://api\.census\.gov/data/\d+/acs/acs5").mock(
        return_value=httpx.Response(
            200, json=[["NAME", "zip code tabulation area"], ["x", "90210"]]
        )
    )
    year = await client.latest_year()
    # latest_year probes newest-first, starting at (current year - 1).
    assert year == datetime.now(UTC).year - 1
    await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_fetch_zcta_place_rel_returns_text_without_key() -> None:
    # The relationship file is a public static download — no API key required.
    client = CensusClient(api_key=None)
    body = "GEOID_ZCTA5_20|GEOID_PLACE_20\n02139|2511000\n"
    respx.get(ZCTA_PLACE_REL_URL).mock(return_value=httpx.Response(200, text=body))
    text = await client.fetch_zcta_place_rel()
    assert text == body
    await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_fetch_zcta_place_rel_retries_then_raises(monkeypatch) -> None:
    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("census_mcp.census_client.asyncio.sleep", _no_sleep)
    client = CensusClient(api_key="x", max_retries=2)
    route = respx.get(ZCTA_PLACE_REL_URL).mock(return_value=httpx.Response(503))
    with pytest.raises(CensusError):
        await client.fetch_zcta_place_rel()
    assert route.call_count == 2
    await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_retries_then_raises_on_persistent_5xx(monkeypatch) -> None:
    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("census_mcp.census_client.asyncio.sleep", _no_sleep)
    client = CensusClient(api_key="x", max_retries=2)
    route = respx.get(ACS5_URL.format(year=2023)).mock(return_value=httpx.Response(503))
    with pytest.raises(CensusError):
        await client.fetch_zctas(["NAME"], 2023, ["90210"])
    assert route.call_count == 2  # honored max_retries
    await client.aclose()
