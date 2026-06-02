"""Census MCP server — U.S. Census (ACS) data by ZIP, inside your agent.

Built on the official MCP Python SDK (``mcp.server.fastmcp``). All tools are
read-only. Data is the American Community Survey (ACS) 5-year release, bulk-
downloaded once into a local SQLite store and served offline thereafter; only
the one-time download needs the network and a free Census API key.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import cast

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations

from .census_client import CensusClient, MissingKeyError
from .formatting import to_income, to_zip_info
from .models import Income, ZipInfo
from .store import Store, load_store

_INSTRUCTIONS = """\
Read-only access to U.S. Census American Community Survey (ACS) data by ZIP code.

Typical flow:
- `lookup_zip` confirms a ZIP maps to a Census ZCTA and gives its name and
  population — a good first call to validate a ZIP.
- `get_income` returns median household income, per-capita income, and the share
  of households earning $200k+.

Notes:
- ZIP ≈ ZCTA (ZIP Code Tabulation Area). They mostly coincide, but ~2% of ZIPs
  (often PO-box-only or non-residential) have no ZCTA and won't be found.
- All values are ACS 5-year *estimates*, not exact counts. Each result carries
  its `vintage` (the ACS 5-year end year).
- The first call downloads the dataset into a local store (needs CENSUS_API_KEY);
  every call after that is served locally.
"""


@dataclass
class AppContext:
    """Resources shared across requests for the lifetime of the server."""

    store: Store
    client: CensusClient
    load_lock: asyncio.Lock


@asynccontextmanager
async def _lifespan(_server: FastMCP) -> AsyncIterator[AppContext]:
    """Own the local store + Census client: open on startup, close on shutdown."""
    store = Store()
    client = CensusClient()
    try:
        yield AppContext(store=store, client=client, load_lock=asyncio.Lock())
    finally:
        await client.aclose()
        store.close()


mcp = FastMCP("census", instructions=_INSTRUCTIONS, lifespan=_lifespan)

# Tools read a local store; the one-time load reaches the Census API.
_READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=True)


def _app(ctx: Context) -> AppContext:
    """The shared app resources from the lifespan context."""
    return cast(AppContext, ctx.request_context.lifespan_context)


def _normalize_zip(zip_code: str) -> str:
    """Validate and normalize a ZIP to a 5-digit string (ZCTA key).

    Accepts a bare 5-digit ZIP or a ZIP+4 (the +4 is dropped — ZCTAs are 5-digit).
    """
    digits = "".join(c for c in zip_code if c.isdigit())
    if len(digits) not in (5, 9):
        raise ValueError(f"Not a 5-digit US ZIP code: {zip_code!r}")
    return digits[:5]


async def _ensure_loaded(app: AppContext) -> int:
    """Make sure the local store is populated; return the loaded ACS vintage.

    Lazily bulk-downloads on first use if the store is empty. Serialized so
    concurrent first calls don't each kick off a download.
    """
    if app.store.is_loaded():
        return cast(int, app.store.vintage())
    async with app.load_lock:
        if not app.store.is_loaded():  # re-check inside the lock
            if not app.client.has_key:
                raise MissingKeyError()
            await load_store(app.store, app.client)
    return cast(int, app.store.vintage())


async def _record(app: AppContext, zip_code: str) -> tuple[dict[str, object], int]:
    """Resolve a ZIP to its stored ACS record + the data vintage, or raise."""
    vintage = await _ensure_loaded(app)
    zcta = _normalize_zip(zip_code)
    rec = app.store.get(zcta)
    if rec is None:
        raise ValueError(
            f"No Census ZCTA data for ZIP {zcta} — it may be a PO-box-only or "
            "non-residential ZIP with no ZIP Code Tabulation Area."
        )
    return rec, vintage


@mcp.tool(annotations=_READ_ONLY)
async def lookup_zip(zip_code: str, ctx: Context) -> ZipInfo:
    """Confirm a ZIP maps to a Census ZCTA and return its name and population.

    `zip_code`: a 5-digit US ZIP. A good first call to validate a ZIP before
    asking for more detail. Returns the ZCTA, Census area name, total population,
    and the ACS data vintage. ZIP ≈ ZCTA; ~2% of ZIPs have no ZCTA and error.
    """
    rec, vintage = await _record(_app(ctx), zip_code)
    return to_zip_info(rec, vintage)


@mcp.tool(annotations=_READ_ONLY)
async def get_income(zip_code: str, ctx: Context) -> Income:
    """Income measures for a ZIP: median household, per-capita, and % $200k+.

    `zip_code`: a 5-digit US ZIP. Returns median household income, per-capita
    income, the number of households, and the percent of households earning
    $200k+ — all ACS 5-year estimates in USD.
    """
    rec, vintage = await _record(_app(ctx), zip_code)
    return to_income(rec, vintage)


async def _run_load() -> None:
    """`setup` / `refresh`: bulk-download the ACS dataset into the local store."""
    store = Store()
    client = CensusClient()
    try:
        if not client.has_key:
            raise MissingKeyError()
        print(f"Downloading ACS 5-year data into {store.path} …", file=sys.stderr)
        count = await load_store(store, client)
        print(f"Done: {count} ZCTAs, ACS {store.vintage()} 5-year.", file=sys.stderr)
    finally:
        await client.aclose()
        store.close()


def main() -> None:
    """Console entry point.

    `mcpwright-census` runs the MCP server over stdio (for Claude Desktop /
    Claude Code). `mcpwright-census setup` / `refresh` bulk-downloads (or
    re-pulls) the ACS dataset into the local store.
    """
    if len(sys.argv) > 1 and sys.argv[1] in {"setup", "refresh"}:
        try:
            asyncio.run(_run_load())
        except MissingKeyError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)
        return
    mcp.run()
