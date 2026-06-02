"""Helpers that shape a stored ACS record into the tool return models.

Derived metrics (percentages) are computed here from the raw public ACS
variables — kept simple and transparent (a share of a total), never the private
scoring models that live elsewhere.
"""

from __future__ import annotations

from typing import cast

from .models import Income, ZipInfo


def _int(rec: dict[str, object], key: str) -> int | None:
    v = rec.get(key)
    return v if isinstance(v, int) else None


def _str(rec: dict[str, object], key: str) -> str | None:
    v = rec.get(key)
    return v if isinstance(v, str) else None


def pct(part: object, whole: object, digits: int = 1) -> float | None:
    """``part / whole`` as a 0-100 percentage, or None if either is missing/zero."""
    if not isinstance(part, int | float) or not isinstance(whole, int | float):
        return None
    if not whole:
        return None
    return round(100.0 * part / whole, digits)


def to_zip_info(rec: dict[str, object], vintage: int) -> ZipInfo:
    return ZipInfo(
        zcta=cast("str", rec["zcta"]),
        name=_str(rec, "name"),
        population=_int(rec, "population"),
        vintage=vintage,
    )


def to_income(rec: dict[str, object], vintage: int) -> Income:
    return Income(
        zcta=cast("str", rec["zcta"]),
        name=_str(rec, "name"),
        median_household_income=_int(rec, "median_household_income"),
        per_capita_income=_int(rec, "per_capita_income"),
        total_households=_int(rec, "total_households"),
        households_200k_plus_pct=pct(
            rec.get("households_200k_plus"), rec.get("total_households")
        ),
        vintage=vintage,
    )
