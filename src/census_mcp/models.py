"""Typed models returned by the Census MCP tools.

These are the tool *return* types — the MCP SDK derives an output schema from them,
so agents receive structured data, not just text. All values are American
Community Survey (ACS) 5-year *estimates*, not exact counts.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ZipInfo(BaseModel):
    """Basic identity and size for a ZIP / ZCTA."""

    zcta: str = Field(description="5-digit ZIP Code Tabulation Area")
    name: str | None = Field(
        default=None, description="Census name for the area, e.g. 'ZCTA5 90069'"
    )
    population: int | None = Field(
        default=None, description="Total population (ACS 5-year estimate)"
    )
    vintage: int = Field(description="ACS 5-year data vintage (end year)")


class Demographics(BaseModel):
    """Population and age for a ZIP / ZCTA."""

    zcta: str = Field(description="5-digit ZIP Code Tabulation Area")
    name: str | None = Field(default=None, description="Census name for the area")
    population: int | None = Field(
        default=None, description="Total population (ACS 5-year estimate)"
    )
    median_age: float | None = Field(
        default=None, description="Median age of the population, in years"
    )
    vintage: int = Field(description="ACS 5-year data vintage (end year)")


class Income(BaseModel):
    """Income measures for a ZIP / ZCTA (all dollar amounts in USD)."""

    zcta: str = Field(description="5-digit ZIP Code Tabulation Area")
    name: str | None = Field(default=None, description="Census name for the area")
    median_household_income: int | None = Field(
        default=None, description="Median household income"
    )
    per_capita_income: int | None = Field(default=None, description="Per-capita income")
    total_households: int | None = Field(
        default=None, description="Total number of households"
    )
    households_200k_plus_pct: float | None = Field(
        default=None,
        description="Percent of households with income $200k+ (0-100)",
    )
    vintage: int = Field(description="ACS 5-year data vintage (end year)")


class Housing(BaseModel):
    """Housing measures for a ZIP / ZCTA (all dollar amounts in USD)."""

    zcta: str = Field(description="5-digit ZIP Code Tabulation Area")
    name: str | None = Field(default=None, description="Census name for the area")
    median_home_value: int | None = Field(
        default=None, description="Median value of owner-occupied homes"
    )
    median_gross_rent: int | None = Field(
        default=None, description="Median gross rent (rent + utilities), monthly"
    )
    occupied_units: int | None = Field(
        default=None, description="Total occupied housing units"
    )
    owner_occupied_pct: float | None = Field(
        default=None,
        description="Percent of occupied units that are owner-occupied (0-100)",
    )
    vintage: int = Field(description="ACS 5-year data vintage (end year)")


class Education(BaseModel):
    """Educational attainment among the 25-and-older population of a ZIP / ZCTA."""

    zcta: str = Field(description="5-digit ZIP Code Tabulation Area")
    name: str | None = Field(default=None, description="Census name for the area")
    population_25_plus: int | None = Field(
        default=None, description="Population aged 25 and over (the attainment base)"
    )
    bachelors_plus_pct: float | None = Field(
        default=None,
        description="Percent of those 25+ with a bachelor's degree or higher (0-100)",
    )
    graduate_or_professional_pct: float | None = Field(
        default=None,
        description="Percent of those 25+ with a graduate or professional degree "
        "(master's, professional, or doctorate) (0-100)",
    )
    vintage: int = Field(description="ACS 5-year data vintage (end year)")


class AcsValue(BaseModel):
    """The raw value of a single ACS variable for a ZIP / ZCTA."""

    zcta: str = Field(description="5-digit ZIP Code Tabulation Area")
    name: str | None = Field(default=None, description="Census name for the area")
    variable: str = Field(description="ACS variable code, e.g. 'B19013_001E'")
    column: str = Field(
        description="Friendly store-column name, e.g. 'median_household_income'"
    )
    value: int | float | str | None = Field(
        default=None,
        description="The variable's value for this ZIP, or null if "
        "missing/suppressed (a string only for the 'name' variable)",
    )
    vintage: int = Field(description="ACS 5-year data vintage (end year)")


class ZipMatch(BaseModel):
    """One ZIP (ZCTA) that intersects a queried place."""

    zcta: str = Field(description="5-digit ZIP Code Tabulation Area")
    place_name: str | None = Field(
        default=None,
        description="Census place the ZIP falls within, e.g. 'Cambridge city'",
    )
    state: str | None = Field(
        default=None, description="2-letter USPS state code of the place"
    )
    coverage_pct: float | None = Field(
        default=None,
        description="Percent of this ZCTA's land area that lies within the place "
        "(0-100); higher means the ZIP sits more fully inside the place",
    )


class FindZips(BaseModel):
    """ZIPs intersecting a named place, best land coverage first."""

    query: str = Field(description="The place name searched for")
    state: str | None = Field(
        default=None, description="The 2-letter USPS state filter applied, if any"
    )
    matches: list[ZipMatch] = Field(
        description="ZCTAs intersecting the place, sorted by coverage_pct "
        "descending. Empty places (no match) raise an error instead."
    )
    vintage: int = Field(
        description="Census geography year of the ZCTA-to-place relationship (2020)"
    )


class ZipMetric(BaseModel):
    """One ZIP's value for a single metric, used in a ranked comparison."""

    zcta: str = Field(description="5-digit ZIP Code Tabulation Area")
    name: str | None = Field(default=None, description="Census name for the area")
    value: float | None = Field(
        default=None,
        description="The metric's value for this ZIP, or null if unavailable "
        "(suppressed, or the ZIP has no ZCTA in the local store)",
    )


class Comparison(BaseModel):
    """Several ZIPs ranked by one metric, highest value first."""

    metric: str = Field(description="The compared metric's name")
    vintage: int = Field(description="ACS 5-year data vintage (end year)")
    results: list[ZipMetric] = Field(
        description="One entry per requested ZIP, sorted by value descending; "
        "ZIPs with no value are listed last"
    )
