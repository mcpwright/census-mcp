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
