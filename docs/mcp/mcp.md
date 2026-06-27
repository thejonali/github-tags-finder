# MCP server

The optional MCP server exposes the CLI's search behavior as one read-only, structured tool: `search_github_issues`. It uses the same query builder, GitHub client, defaults, pagination, and normalized result shape as the CLI.

STDIO is the default transport for local MCP clients. Streamable HTTP is
available as a deployment path, but authentication must be added before
exposing it beyond localhost.

## Install and run

From this repository:

```bash
uv sync --extra mcp
uv run --extra mcp github-tags-mcp
```

The server writes MCP protocol messages to standard output. Do not wrap it in scripts that print banners or logs to standard output.

For local development with Streamable HTTP:

```bash
uv run --extra mcp github-tags-mcp \
  --transport streamable-http --host 127.0.0.1 --port 8000
```

The endpoint is `http://127.0.0.1:8000/mcp`.

## Authentication

The server loads `GITHUB_TOKEN`, `GH_TOKEN`, and `GITHUB_API_URL` from the process environment. It also loads those three values from `.env` in its working directory without overriding existing environment values.

```bash
cp .env.example .env
# Edit .env and set GITHUB_TOKEN.
```

Only GitHub-specific variables are loaded. The token is never accepted as an MCP tool argument and is not included in tool results.

## Client configuration

Client-specific instructions are documented only after they have been tested
against this server:

- [Codex](codex.md) — verified

Other MCP clients may work with the STDIO command above, but their setup has
not yet been verified for this project.

## Tool behavior

`search_github_issues` defaults to open, non-archived issues carrying either `good first issue` or `help wanted`. Agents can supply structured language, label, repository, owner, date, and assignee filters, append raw qualifiers, or bypass the defaults with `raw_query`.

The tool is intentionally read-only. It does not create issues, comments, assignments, or other GitHub mutations.

## Deployment direction

The current local STDIO server is the correct integration point for desktop coding tools. A future hosted version can run the same server with Streamable HTTP, then add HTTPS, OAuth, per-user GitHub authorization, rate limiting, and deployment health checks without changing the tool contract.
