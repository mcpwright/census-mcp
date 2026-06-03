# census-mcp — MCPB desktop-extension bundle

This directory builds the **[MCPB](https://github.com/modelcontextprotocol/mcpb)**
(`.mcpb`) bundle for one-click install in Claude Desktop / Claude Code, and for
submission to Anthropic's Connectors Directory.

## Why `type: "uv"` (not a vendored bundle)

census depends on `pydantic`, whose `pydantic-core` is a **compiled, platform-specific**
wheel — MCPB explicitly *"cannot portably bundle compiled dependencies."* So this is a
**`uv`-type** bundle: it ships the **source + `pyproject.toml`** (no vendored `server/lib`),
and the host's `uv` installs the correct-platform dependencies at install time. That keeps it
cross-platform (`darwin` / `win32` / `linux`). The API key is collected via `user_config` and
passed to the server as `CENSUS_API_KEY`.

> Note: MCPB's `uv` runtime is officially **experimental**. Some Claude Desktop builds may
> require a system Python to be present even when `uv` is installed
> ([mcpb#84](https://github.com/modelcontextprotocol/mcpb/issues/84)) — verify on the target
> Claude Desktop version before relying on it.

## Build

Requires the `mcpb` CLI: `npm i -g @anthropic-ai/mcpb`.

```bash
./build.sh        # validates manifest.json, stages source + pyproject, packs the .mcpb
```

Output: `../dist/mcpwright-census-<version>.mcpb` (gitignored). The build stages only the files
the bundle needs (`manifest.json`, `icon.png`, `pyproject.toml`, `README.md`, `LICENSE`,
`uv.lock`, `src/`) and strips bytecode caches.

## Install (manual, before Directory listing)

In Claude Desktop: **Settings → Extensions → Install from file…** and pick the `.mcpb`. It will
prompt for your free [Census API key](https://api.census.gov/data/key_signup.html). First run
downloads the ACS dataset into a local store; later lookups are offline.

## Versioning

`manifest.json` `version` tracks the package version (keep it in lockstep with `pyproject.toml`
and `server.json`). Bump all three together on release.
