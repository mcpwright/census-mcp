# census-mcp

<!-- mcp-name: io.github.mcpwright/census-mcp -->

**U.S. Census data by ZIP code, inside your agent.** An [MCP](https://modelcontextprotocol.io)
server that lets an LLM look up income, demographics, housing, and education for any ZIP —
built on Anthropic's official [`mcp` Python SDK](https://github.com/modelcontextprotocol/python-sdk).

All tools are **read-only**. Data is the U.S. Census Bureau's American Community Survey (ACS)
5-year release — **bulk-downloaded once into a local store**, then served offline. A free
Census API key is required for the one-time download.

> Status: published (v0.1.2) — `uvx mcpwright-census` (PyPI) and listed in the official MCP
> Registry as `io.github.mcpwright/census-mcp`. All 8 tools below are live and unit-tested, verified
> end-to-end against the live ACS 5-year release (vintage 2024 at the time of writing — the
> server auto-detects the latest). Part of the
> [**mcpwright**](https://github.com/mcpwright) suite.

## Tools

| Tool | What it does |
|---|---|
| `lookup_zip(zip_code)` | Confirm a ZIP maps to a Census ZCTA; returns name, total population, and the ACS vintage. |
| `get_income(zip_code)` | Median household income, per-capita income, total households, and the % of households earning $200k+. |
| `get_demographics(zip_code)` | Total population and median age. |
| `get_housing(zip_code)` | Median home value, median gross rent, occupied units, and % owner-occupied. |
| `get_education(zip_code)` | Of adults 25+, the % with a bachelor's degree or higher and the % with a graduate/professional degree. |
| `compare_zips(zips, metric)` | Rank several ZIPs by one metric (income, age, home value, attainment, …), highest first. |
| `get_acs_variable(zip_code, variable)` | Escape hatch: the raw value of any stored ACS variable, by code or friendly name. |
| `find_zips(place, state=None)` | Reverse lookup: the ZIPs that fall within a city/town/CDP, ranked by how much of each ZIP's land lies in the place. |

ZIP ≈ ZCTA (ZIP Code Tabulation Area): they mostly coincide, but ~2% of ZIPs (PO-box-only /
non-residential) have no ZCTA and will return an error. All ACS figures are 5-year *estimates*.

`find_zips` is the reverse direction (place → ZIPs). It's approximate: ZCTAs don't nest inside
places, so a ZIP can span several places and vice versa — read each match's `coverage_pct` and
pass a `state` to disambiguate same-named places (e.g. Cambridge, MA vs OH). It's built on the
public 2020 Census ZCTA-to-Place relationship file (2020 geography; no API key needed for it).

## Install

Requires Python 3.12+ and a free [Census API key](https://api.census.gov/data/key_signup.html)
(set `CENSUS_API_KEY`). The PyPI package is `mcpwright-census`; the command, server, and tools
are all "census".

```bash
export CENSUS_API_KEY=your-free-key
uvx mcpwright-census setup     # one-time: bulk-download the ACS dataset into a local store
```

### Claude Code

```bash
claude mcp add census -e CENSUS_API_KEY=your-free-key -- uvx mcpwright-census
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "census": {
      "command": "uvx",
      "args": ["mcpwright-census"],
      "env": { "CENSUS_API_KEY": "your-free-key" }
    }
  }
}
```

> **First run** downloads the full ACS dataset (~33k ZCTAs) into a local SQLite store under
> your OS cache dir, so every later lookup is instant and offline. Run `mcpwright-census setup`
> ahead of time, or let the server download lazily on first use. `mcpwright-census refresh`
> re-pulls when a new ACS vintage is published. Override the store location with
> `CENSUS_MCP_STORE`.

## Develop

```bash
git clone https://github.com/mcpwright/census-mcp && cd census-mcp
uv sync
uv run pytest -v                                     # tests (mocked Census + seeded SQLite)
uv run ruff check src/ && uv run ruff format --check src/   # lint + format
uv run mypy                                          # type checking
uv run mcp dev src/census_mcp/server.py              # poke the tools in the MCP Inspector
```

## Roadmap

- [x] `lookup_zip` — validate a ZIP, name + population
- [x] `get_income` — income measures + % $200k+
- [x] `get_demographics` — population + median age _(age brackets still to come)_
- [x] `get_housing` — median home value, rent, % owner-occupied
- [x] `get_education` — % bachelor's+, % graduate
- [x] `compare_zips` — one metric across several ZIPs, ranked
- [x] `get_acs_variable` — raw value for any stored ACS variable (escape hatch)
- [x] `find_zips` — reverse lookup: place → ZIPs, ranked by land coverage
- [ ] `get_demographics` age brackets (under-18 / 18-34 / 35-64 / 65+)
- [x] Publish to PyPI (`mcpwright-census`) + the official MCP Registry

## Privacy

census-mcp runs entirely **on your machine** and collects, stores, or transmits **no personal
data** — no accounts, no tracking, no telemetry. Its only outbound requests go to the public
**U.S. Census Bureau** to download public data: `api.census.gov` for the ACS dataset (using
**your own** `CENSUS_API_KEY`), and `www2.census.gov` for the place-lookup file used by
`find_zips` (no key needed). The key is read from your environment and is **never logged or sent
anywhere else**. These downloads happen during `setup`/`refresh` (or lazily on first use); after
that, lookups are served from a local store with no further network calls. The downloaded data
lives under your OS cache directory (public reference data only) and can be deleted at any time.

Full policy: **https://mcpwright.com/privacy**

## Questions & feedback

- **Questions, ideas, or "could it do X?"** → [**Discussions**](https://github.com/mcpwright/census-mcp/discussions)
- **Bugs & concrete feature requests** → [**Issues**](https://github.com/mcpwright/census-mcp/issues)

Contributions welcome.

---

Part of [**mcpwright**](https://github.com/mcpwright) · built by [Devender Gollapally](https://github.com/devender)
