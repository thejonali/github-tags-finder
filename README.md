# GitHub Tags Finder

`github-tags` is a dependency-free Python CLI for finding approachable GitHub issues. It searches open issues labeled **good first issue** or **help wanted** by default, then lets you narrow the results by programming language, repository, owner, dates, assignment status, or any raw qualifier accepted by GitHub's issue search API.

Despite the project name, this tool searches issue labels and metadata—not Git release tags.

## Install

Python 3.10 or newer is required.

```bash
uv tool install .
github-tags --help
```

For development without installing the command:

```bash
PYTHONPATH=src python -m github_tags_finder --help
```

## MCP server

An optional MCP server exposes the same search engine to MCP clients. Codex is
the currently verified client:

```bash
uv sync --extra mcp
uv run --extra mcp github-tags-mcp
```

It provides one read-only `search_github_issues` tool over STDIO by default,
with Streamable HTTP available for future hosted deployment. See the
[general MCP guide](docs/mcp/mcp.md) and the verified
[Codex setup](docs/mcp/codex.md).

## Examples

Find the default beginner-friendly issues in Python repositories:

```bash
github-tags --language Python
```

Search for unassigned Rust parser work:

```bash
github-tags parser --language Rust --no-assignee
```

Replace the default labels with project-specific labels. Repeating `--label` matches any label by default:

```bash
github-tags --language Go --label beginner --label mentorship
```

Require every supplied label:

```bash
github-tags --label bug --label confirmed --match-labels all
```

Limit the search to repositories or an organization:

```bash
github-tags --repo pallets/flask --repo pallets/click
github-tags --org apache --language Java
```

Use any GitHub-supported qualifier that does not have a dedicated option:

```bash
github-tags --qualifier 'comments:<5' --qualifier 'created:>=2026-01-01'
```

Bypass all structured defaults with a complete query:

```bash
github-tags --raw-query 'is:issue is:open label:documentation no:assignee'
```

Inspect a generated query without making a request:

```bash
github-tags --language TypeScript --no-assignee --query-only
```

Produce machine-readable output:

```bash
github-tags --language Python --limit 100 --json
```

## Authentication

Unauthenticated searches work for public repositories but have a low API rate limit. Set either `GITHUB_TOKEN` or `GH_TOKEN` for authenticated requests:

```bash
cp .env.example .env
# Edit .env and replace the placeholder. The CLI and MCP server load it.
github-tags --language Python
```

The token is read only from the environment so it does not appear in shell process arguments. `.env` files are ignored by Git; only the placeholder `.env.example` is tracked. No repository permissions are needed to search public resources. Accessing private resources requires a token that can read those repositories.

GitHub Enterprise Server can be selected with `GITHUB_API_URL` or `--api-url`:

```bash
export GITHUB_API_URL=https://github.example.com/api/v3
github-tags --org my-company
```

## Search behavior

The generated default query is:

```text
is:issue is:open archived:false label:"good first issue","help wanted"
```

The comma between labels is GitHub's OR syntax. Supplying one or more `--label` options replaces both defaults. Use `--no-labels` to search without a label filter. Archived repositories are excluded unless `--include-archived` is supplied.

The GitHub Search API exposes at most the first 1,000 results for a query, so `--limit` is capped at 1,000. See GitHub's [issue search documentation](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/filtering-and-searching-issues-and-pull-requests) for supported qualifiers.

## Development

The test suite uses only Python's standard library:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## License

Copyright 2026 thejonali. Licensed under the [Apache License 2.0](LICENSE).
