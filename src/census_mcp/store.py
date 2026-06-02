"""Local SQLite store for ACS data — bulk-download-once, then serve offline.

The Census ACS 5-year dataset is small and static-annual (~33k ZCTAs, a few
dozen variables, a few MB, refreshed once a year). Rather than hit the API per
query, we download it once into a SQLite file under the OS cache dir and serve
every lookup locally — instant, offline, and rate-limit-proof. Refresh annually
when a new ACS vintage drops.

Reads are synchronous (a local SQLite point-lookup is microseconds); only the
one-time bulk *load* touches the network, via the async ``CensusClient``.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from .acs import ACS_FIELDS, ACS_VARIABLES, parse_rows

if TYPE_CHECKING:
    from .census_client import CensusClient

_APP_DIR = "mcpwright-census"
_DB_NAME = "acs.sqlite3"

# SQLite column type per ACS field kind.
_SQL_TYPE = {"str": "TEXT", "int": "INTEGER", "float": "REAL"}


def _cache_dir() -> Path:
    """The per-user cache directory for this platform."""
    # Bind to a local so mypy doesn't prune the other branches as unreachable
    # (it narrows direct `sys.platform` comparisons to the checking platform).
    platform = sys.platform
    if platform == "darwin":
        return Path.home() / "Library" / "Caches"
    if platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA")
        return Path(base) if base else Path.home() / "AppData" / "Local"
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")


def default_store_path() -> Path:
    """Where the SQLite store lives (override with ``CENSUS_MCP_STORE``)."""
    override = os.environ.get("CENSUS_MCP_STORE")
    if override:
        return Path(override)
    return _cache_dir() / _APP_DIR / _DB_NAME


# Data columns (everything but the zcta primary key), derived from ACS_FIELDS so
# the schema can never drift from what we fetch.
_DATA_COLUMNS: list[str] = [col for _code, col, _kind in ACS_FIELDS]


class Store:
    """A SQLite-backed local store of ACS data, keyed by ZCTA."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_store_path()
        self._conn: sqlite3.Connection | None = None

    # --- connection lifecycle ----------------------------------------------
    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path)
            conn.row_factory = sqlite3.Row
            self._conn = conn
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # --- state -------------------------------------------------------------
    def is_loaded(self) -> bool:
        """True once the ACS table exists and holds at least one row."""
        conn = self.connect()
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='zcta'"
        ).fetchone()
        if row is None:
            return False
        count = conn.execute("SELECT COUNT(*) FROM zcta").fetchone()[0]
        return bool(count)

    def vintage(self) -> int | None:
        """The ACS 5-year vintage currently loaded, if any."""
        v = self._meta("vintage")
        return int(v) if v is not None else None

    def metadata(self) -> dict[str, str]:
        conn = self.connect()
        if not self._table_exists("meta"):
            return {}
        return {
            str(r["key"]): str(r["value"])
            for r in conn.execute("SELECT key, value FROM meta")
        }

    # --- reads -------------------------------------------------------------
    def get(self, zcta: str) -> dict[str, object] | None:
        """The full record for one ZCTA, or None if it isn't in the store."""
        conn = self.connect()
        if not self._table_exists("zcta"):
            return None
        row = conn.execute("SELECT * FROM zcta WHERE zcta = ?", (zcta,)).fetchone()
        if row is None:
            return None
        # sqlite3.Row iterates VALUES, not column names — .keys() is required here.
        return {key: row[key] for key in row.keys()}  # noqa: SIM118

    # --- writes ------------------------------------------------------------
    def replace_all(self, records: list[dict[str, object]], vintage: int) -> int:
        """Atomically rebuild the store from ``records`` (one dict per ZCTA)."""
        conn = self.connect()
        cols = ", ".join(
            f'"{col}" {_SQL_TYPE[kind]}' for _code, col, kind in ACS_FIELDS
        )
        all_cols = ["zcta", *_DATA_COLUMNS]
        placeholders = ", ".join("?" for _ in all_cols)
        with conn:  # one transaction
            conn.execute("DROP TABLE IF EXISTS zcta")
            conn.execute(f"CREATE TABLE zcta (zcta TEXT PRIMARY KEY, {cols})")
            conn.executemany(
                f"INSERT OR REPLACE INTO zcta ({', '.join(all_cols)}) "
                f"VALUES ({placeholders})",
                [tuple(rec.get(c) for c in all_cols) for rec in records],
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
            )
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('vintage', ?)",
                (str(vintage),),
            )
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('row_count', ?)",
                (str(len(records)),),
            )
        return len(records)

    # --- internals ---------------------------------------------------------
    def _table_exists(self, name: str) -> bool:
        conn = self.connect()
        return (
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
            ).fetchone()
            is not None
        )

    def _meta(self, key: str) -> str | None:
        conn = self.connect()
        if not self._table_exists("meta"):
            return None
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        return str(row["value"])


async def load_store(
    store: Store, client: CensusClient, *, year: int | None = None
) -> int:
    """Bulk-download the full ACS dataset and (re)build the local store.

    Resolves the latest published ACS 5-year vintage (unless ``year`` is given),
    pulls every ZCTA in one request, and writes the parsed rows locally. Returns
    the number of ZCTAs stored. Raises ``MissingKeyError`` if no key is set.
    """
    vintage = year if year is not None else await client.latest_year()
    raw = await client.fetch_all_zctas(ACS_VARIABLES, vintage)
    records = parse_rows(raw)
    return store.replace_all(records, vintage)
