# census-mcp — working agreement

`census-mcp` is a server in the **mcpwright** suite (`github.com/mcpwright`): polished,
public MCP servers that bring a real-world data source into any agent. Every server in
the suite meets the **same engineering bar**, set by the reference server **edgar-mcp**.

> **Source of truth: `edgar-mcp`.** When a convention here is unclear, copy edgar
> (`~/github-personal/edgar-mcp`). The full written rubric is
> `~/my-notes/professional-self-improvement/mcpwright/mcp-standards.md`.
> To scaffold/extend to standard, use the `new-mcpwright-server` skill.

## Non-negotiable policies

- **Lots of unit tests.** Every tool and every parser/formatter has tests. **Mock all
  external I/O** (`respx` for HTTP; a seeded temp SQLite store for the local data). A new
  tool ships with its tests **in the same PR**. `pytest -v` must be green before a PR opens.
- **Use the latest patterns.** Official `mcp` Python SDK via `mcp.server.fastmcp` (NOT the
  standalone `fastmcp` package). Python 3.12+ idioms, `from __future__ import annotations`,
  pydantic v2 models with a `Field(description=...)` on **every** field, `uv` for deps +
  build, async `httpx`. Tools return typed pydantic models (structured output) and are
  annotated `readOnlyHint=True`.
- **PR per change, CI-gated.** Standard flow:
  **feature branch → code → code-review subagent → fold in findings → PR → CI green → squash-merge.**
  - *Code-review subagent:* before opening the PR, review the diff (`git diff main...HEAD`) with
    the **`code-reviewer`** subagent (`.claude/agents/code-reviewer.md`) — or just run
    **`/review-pr`**. It runs in a **fresh context with no memory of the coding session** and
    returns severity-tagged findings (**Blocker / High / Medium / Low**). Address Blocker/High
    (and add a regression test for any real bug) before the PR.
  - *Merge:* the `Code Quality & Tests` check green and branch up to date → squash-merge with a
    `(#N)` suffix. `main` is branch-protected; **no direct pushes**.
  - *Commits:* imperative subject + a short body, ending with the dual trailer
    (`Co-authored-by: Devender …` + `Co-authored-by: Claude …`).
  - One focused change per PR — keep process/docs changes (like this one) out of feature PRs.
- **Green locally before pushing:**
  ```bash
  uv run ruff check src/ && uv run ruff format --check src/ && uv run mypy && uv run pytest -v
  ```
  `uv run pre-commit run --all-files` mirrors CI (ruff, ruff-format, mypy, detect-secrets, hygiene).

## Layout (mirrors edgar)

```
src/census_mcp/
  __init__.py        # from .server import main
  census_client.py   # async httpx client: key handling, retry/backoff
  acs.py             # ACS variable map + sanitize + parse_rows
  store.py           # local SQLite store + bulk loader   ← census-specific
  models.py          # pydantic tool RETURN types (Field(description=...) on every field)
  formatting.py      # raw record → model helpers + derived metrics
  server.py          # FastMCP app: instructions + lifespan + @mcp.tool(readOnlyHint)
tests/               # respx-mocked Census + seeded SQLite; one file per module/tool group
```
Errors users/agents see are actionable `ValueError`s with a next step.

## What census-mcp does differently from edgar (data layer ONLY)

Everything above is identical to edgar. Census legitimately differs in *how it gets data*:
- **Bulk-download-once → local SQLite** (`store.py`), not live-per-request calls + a TTL
  cache. The store is the "don't re-fetch" layer; every lookup is served locally.
- **A free Census API key is REQUIRED** (`CENSUS_API_KEY`); fail fast with a clear message.
- **`setup` / `refresh` console commands** download / re-pull a new ACS vintage; the server
  also lazily downloads on first use if the store is empty.
- **Never** put StartEngine's private scoring (accreditation model, evidence weights) in
  here — public ACS facts + simple derived percentages only. See `census-mcp-plan.md`.

## Publishing & the website

- Publish (PyPI `mcpwright-census` + the MCP Registry `io.github.mcpwright/census-mcp`):
  use the **`publish-mcp-server`** skill.
- Each server gets a page at **mcpwright.com/<source>** using the suite typography
  (**Fraunces** serif + **JetBrains Mono**): use the **`add-mcpwright-site-page`** skill.
