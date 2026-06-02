"""Shared test fixtures."""

import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest

from census_mcp.census_client import CensusClient
from census_mcp.server import AppContext
from census_mcp.store import Store

# Two seeded ZCTAs — enough to exercise every tool offline, no network.
SEED: list[dict[str, object]] = [
    {
        "zcta": "90069",
        "name": "ZCTA5 90069",
        "population": 22000,
        "median_age": 39.5,
        "median_household_income": 105000,
        "per_capita_income": 98000,
        "total_households": 14000,
        "households_200k_plus": 3500,
        "median_home_value": 1200000,
        "median_gross_rent": 2200,
        "occupied_units": 13800,
        "owner_occupied_units": 4000,
        "pop_25_plus": 19000,
        "bachelors": 6000,
        "masters": 3000,
        "professional_degree": 800,
        "doctorate": 400,
    },
    {
        "zcta": "00601",
        "name": "ZCTA5 00601",
        "population": 17000,
        "median_age": 40.1,
        "median_household_income": 15000,
        "per_capita_income": 8000,
        "total_households": 6000,
        "households_200k_plus": None,  # suppressed → None survives the round-trip
        "median_home_value": 90000,
        "median_gross_rent": 500,
        "occupied_units": 5800,
        "owner_occupied_units": 4200,
        "pop_25_plus": 11000,
        "bachelors": 1200,
        "masters": 400,
        "professional_degree": 60,
        "doctorate": 30,
    },
]

SEED_VINTAGE = 2023

# ZCTA-to-place rows for find_zips. West Hollywood spans two ZCTAs (coverage
# ordering); Cambridge appears in MA and OH (state filter + disambiguation).
SEED_PLACES: list[dict[str, object]] = [
    {
        "zcta": "90069",
        "name_display": "West Hollywood city",
        "name_norm": "west hollywood city",
        "name_key": "west hollywood",
        "state": "CA",
        "coverage": 0.82,
    },
    {
        "zcta": "90046",
        "name_display": "West Hollywood city",
        "name_norm": "west hollywood city",
        "name_key": "west hollywood",
        "state": "CA",
        "coverage": 0.15,
    },
    {
        "zcta": "02138",
        "name_display": "Cambridge city",
        "name_norm": "cambridge city",
        "name_key": "cambridge",
        "state": "MA",
        "coverage": 0.55,
    },
    {
        "zcta": "02139",
        "name_display": "Cambridge city",
        "name_norm": "cambridge city",
        "name_key": "cambridge",
        "state": "MA",
        "coverage": 0.40,
    },
    {
        "zcta": "43725",
        "name_display": "Cambridge city",
        "name_norm": "cambridge city",
        "name_key": "cambridge",
        "state": "OH",
        "coverage": 0.90,
    },
]

SEED_PLACE_VINTAGE = 2020


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    """A Store backed by a temp SQLite file, pre-seeded with ACS + place rows."""
    s = Store(tmp_path / "acs.sqlite3")
    s.replace_all(SEED, SEED_VINTAGE)
    s.replace_places(SEED_PLACES, SEED_PLACE_VINTAGE)
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
async def ctx(store: Store) -> AsyncIterator[SimpleNamespace]:
    """A stand-in for the MCP Context the server injects.

    Tools read app resources via ``ctx.request_context.lifespan_context``; this
    provides exactly that, with the seeded store so no Census API call happens.
    """
    client = CensusClient(api_key=None)
    app = AppContext(store=store, client=client, load_lock=asyncio.Lock())
    try:
        yield SimpleNamespace(request_context=SimpleNamespace(lifespan_context=app))
    finally:
        await client.aclose()
