"""Async client for the U.S. Census ACS 5-year API.

The Census API **requires** a free key (anonymous requests are redirected to a
"missing key" page). Get one at https://api.census.gov/data/key_signup.html and
set ``CENSUS_API_KEY``.
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

import httpx

from .places import ZCTA_PLACE_REL_URL

ACS5_URL = "https://api.census.gov/data/{year}/acs/acs5"
KEY_SIGNUP_URL = "https://api.census.gov/data/key_signup.html"


class CensusError(RuntimeError):
    """A Census API request failed in a way we can't recover from."""


class MissingKeyError(CensusError):
    """Raised when no (or an invalid) Census API key is configured."""

    def __init__(self) -> None:
        super().__init__(
            "A Census API key is required. Get a free one in seconds at "
            f"{KEY_SIGNUP_URL} and set the CENSUS_API_KEY environment variable."
        )


class CensusClient:
    """Thin async wrapper over the ACS 5-year endpoint."""

    def __init__(self, api_key: str | None = None, *, max_retries: int = 3) -> None:
        self._key = api_key or os.environ.get("CENSUS_API_KEY") or None
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(180.0))
        self._max_retries = max_retries

    @property
    def has_key(self) -> bool:
        return bool(self._key)

    async def __aenter__(self) -> CensusClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, year: int, variables: list[str], geo: str) -> list[list[str]]:
        """GET an ACS query, retrying transient errors (429 / 5xx) with backoff."""
        if not self._key:
            raise MissingKeyError()
        params = {"get": ",".join(variables), "for": geo, "key": self._key}
        url = ACS5_URL.format(year=year)
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                resp = await self._client.get(
                    url, params=params, follow_redirects=False
                )
            except httpx.HTTPError as exc:  # network/timeout — retry
                last_exc = exc
                await asyncio.sleep(2**attempt)
                continue

            # Census 302-redirects missing/invalid keys to missing_key.html.
            if resp.status_code in (301, 302):
                raise MissingKeyError()
            if resp.status_code == 404:
                raise CensusError(f"ACS {year} 5-year data is not available")
            if resp.status_code == 429 or resp.status_code >= 500:  # transient
                last_exc = CensusError(f"Census returned {resp.status_code} for {url}")
                await asyncio.sleep(2**attempt)
                continue
            resp.raise_for_status()
            data: list[list[str]] = resp.json()
            return data

        raise CensusError(
            f"Census request failed after {self._max_retries} attempts: {url}"
        ) from last_exc

    async def latest_year(self) -> int:
        """Probe for the most recent published ACS 5-year vintage."""
        now = datetime.now(UTC).year
        for year in range(now - 1, now - 6, -1):
            try:
                await self._get(year, ["NAME"], "zip code tabulation area:90210")
                return year
            except MissingKeyError:
                raise
            except CensusError:
                continue
        raise CensusError("Could not find a recent ACS 5-year vintage")

    async def fetch_all_zctas(self, variables: list[str], year: int) -> list[list[str]]:
        """One bulk call for every ZCTA (~33k rows)."""
        return await self._get(year, variables, "zip code tabulation area:*")

    async def fetch_zctas(
        self, variables: list[str], year: int, zctas: list[str]
    ) -> list[list[str]]:
        return await self._get(
            year, variables, "zip code tabulation area:" + ",".join(zctas)
        )

    async def fetch_zcta_place_rel(self) -> str:
        """Download the 2020 ZCTA-to-Place relationship file as text.

        A static, public-domain Census flat file on ``www2.census.gov`` — no API
        key needed (unlike the ACS endpoint). Retries transient errors (429/5xx)
        with backoff; returns the raw pipe-delimited body.
        """
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                resp = await self._client.get(ZCTA_PLACE_REL_URL, follow_redirects=True)
            except httpx.HTTPError as exc:  # network/timeout — retry
                last_exc = exc
                await asyncio.sleep(2**attempt)
                continue

            if resp.status_code == 404:
                raise CensusError(
                    f"ZCTA-to-Place relationship file not found at {ZCTA_PLACE_REL_URL}"
                )
            if resp.status_code == 429 or resp.status_code >= 500:  # transient
                last_exc = CensusError(
                    f"Census returned {resp.status_code} for {ZCTA_PLACE_REL_URL}"
                )
                await asyncio.sleep(2**attempt)
                continue
            resp.raise_for_status()
            return resp.text

        raise CensusError(
            f"Relationship-file request failed after {self._max_retries} attempts"
        ) from last_exc
