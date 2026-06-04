"""Local SQLite store for ACS data — bulk-download-once, then serve offline.

The Census ACS 5-year dataset is small and static-annual (~33k ZCTAs, a few
dozen variables, a few MB, refreshed once a year). Rather than hit the API per
query, we download it once into a SQLite file under the OS cache dir and serve
every lookup locally — instant, offline, and rate-limit-proof. Refresh annually
when a new ACS vintage drops.

Reads are synchronous (a local SQLite point-lookup is microseconds); only the
one-time bulk *load* touches the network, via the async ``CensusClient``. The
store plumbing (connection, ``meta`` table, load-state) lives in
``mcpwright_core.BaseStore``; this adds the ACS + ZCTA-place schema and queries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mcpwright_core import BaseStore

from .acs import ACS_FIELDS, ACS_VARIABLES, parse_rows
from .places import PLACE_REL_VINTAGE, parse_place_rows

if TYPE_CHECKING:
    from .census_client import CensusClient

# SQLite column type per ACS field kind.
_SQL_TYPE = {"str": "TEXT", "int": "INTEGER", "float": "REAL"}

# Data columns (everything but the zcta primary key), derived from ACS_FIELDS so
# the schema can never drift from what we fetch.
_DATA_COLUMNS: list[str] = [col for _code, col, _kind in ACS_FIELDS]

# Columns of the ZCTA-to-place table (populated from the relationship file).
_PLACE_COLUMNS: list[str] = [
    "zcta",
    "name_display",
    "name_norm",
    "name_key",
    "state",
    "coverage",
]


class Store(BaseStore):
    """A SQLite-backed local store of ACS data, keyed by ZCTA."""

    APP_DIR = "mcpwright-census"
    DB_NAME = "acs.sqlite3"
    STORE_ENV_VAR = "CENSUS_MCP_STORE"
    DATA_TABLE = "zcta"

    # --- state -------------------------------------------------------------
    def vintage(self) -> int | None:
        """The ACS 5-year vintage currently loaded, if any."""
        return self._int_meta("vintage")

    def places_loaded(self) -> bool:
        """True once the ZCTA-to-place table exists and holds at least one row."""
        conn = self.connect()
        if not self._table_exists("zcta_place"):
            return False
        count = conn.execute("SELECT COUNT(*) FROM zcta_place").fetchone()[0]
        return bool(count)

    def place_vintage(self) -> int | None:
        """The geography vintage of the loaded ZCTA-to-place relationship, if any."""
        return self._int_meta("place_rel_vintage")

    # --- reads -------------------------------------------------------------
    def get(self, zcta: str) -> dict[str, object] | None:
        """The full record for one ZCTA, or None if it isn't in the store."""
        conn = self.connect()
        if not self._table_exists("zcta"):
            return None
        row = conn.execute("SELECT * FROM zcta WHERE zcta = ?", (zcta,)).fetchone()
        return self._row_dict(row) if row is not None else None

    def find_places(
        self, name_norm: str, name_key: str, state: str | None = None
    ) -> list[dict[str, object]]:
        """ZCTA-to-place rows matching a place name, best land coverage first.

        ``name_norm`` is the normalized query, ``name_key`` is the query with a
        trailing Census descriptor stripped (see ``places.place_name_key``).

        - If the query carried a descriptor (``name_key != name_norm``, e.g.
          "Cambridge city"), only an exact full-name match counts.
        - If it didn't (a bare "Cambridge"), it also matches any row whose
          descriptor-stripped key equals it — so "Cambridge" finds "Cambridge
          city".

        The two arms are deliberately not crossed: a stripped query is never
        matched against a row's full name (nor vice versa), so "Carson City"
        won't collide with the unrelated "Carson city". Optionally filters to a
        USPS state abbreviation; rows are sorted by ``coverage`` descending (no-
        coverage rows last).
        """
        conn = self.connect()
        if not self._table_exists("zcta_place"):
            return []
        if name_key != name_norm:  # query already had a descriptor
            clause, params = "name_norm = ?", [name_norm]
        else:  # bare query — also match rows whose stripped key equals it
            clause, params = "(name_norm = ? OR name_key = ?)", [name_norm, name_norm]
        sql = (
            f"SELECT zcta, name_display, state, coverage FROM zcta_place WHERE {clause}"
        )
        if state:
            sql += " AND state = ?"
            params.append(state)
        sql += " ORDER BY coverage IS NULL, coverage DESC"
        return [self._row_dict(row) for row in conn.execute(sql, params)]

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
            self._write_meta(conn, {"vintage": vintage, "row_count": len(records)})
        return len(records)

    def replace_places(self, rows: list[dict[str, object]], vintage: int) -> int:
        """Atomically rebuild the ZCTA-to-place table from ``rows``."""
        conn = self.connect()
        placeholders = ", ".join("?" for _ in _PLACE_COLUMNS)
        with conn:  # one transaction
            conn.execute("DROP TABLE IF EXISTS zcta_place")
            conn.execute(
                "CREATE TABLE zcta_place ("
                "zcta TEXT, name_display TEXT, name_norm TEXT, "
                "name_key TEXT, state TEXT, coverage REAL)"
            )
            conn.executemany(
                f"INSERT INTO zcta_place ({', '.join(_PLACE_COLUMNS)}) "
                f"VALUES ({placeholders})",
                [tuple(rec.get(c) for c in _PLACE_COLUMNS) for rec in rows],
            )
            # Name lookups drive every find_zips query.
            conn.execute("CREATE INDEX idx_place_norm ON zcta_place (name_norm)")
            conn.execute("CREATE INDEX idx_place_key ON zcta_place (name_key)")
            self._write_meta(conn, {"place_rel_vintage": vintage})
        return len(rows)


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


async def load_places(store: Store, client: CensusClient) -> int:
    """Download the 2020 ZCTA-to-Place relationship file and (re)build its table.

    Independent of the ACS load and needs no API key (the relationship file is a
    public static download). Returns the number of (ZCTA, place) rows stored.
    """
    text = await client.fetch_zcta_place_rel()
    rows = parse_place_rows(text)
    return store.replace_places(rows, PLACE_REL_VINTAGE)
