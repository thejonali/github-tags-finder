"""MCP adapter for the GitHub issue finder."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from typing import Any, Literal

from .client import DEFAULT_API_URL, GitHubClient
from .environment import load_github_environment
from .output import normalized_issue
from .query import DEFAULT_LABELS, SearchFilters


SERVER_INSTRUCTIONS = (
    "Use search_github_issues to find open-source contribution opportunities. "
    "It searches open, non-archived issues labeled 'good first issue' OR "
    "'help wanted' by default. Add a language or owner filter when the user "
    "provides one. Supplying labels replaces the defaults; an empty labels list "
    "disables label filtering. Results are read-only and may be incomplete when "
    "GitHub reports an incomplete search."
)


def search_github_issues(
    terms: list[str] | None = None,
    language: str | None = None,
    labels: list[str] | None = None,
    match_labels: Literal["any", "all"] = "any",
    repositories: list[str] | None = None,
    organization: str | None = None,
    owner_user: str | None = None,
    state: Literal["open", "closed", "all"] = "open",
    assignee: str | None = None,
    unassigned: bool = False,
    created: str | None = None,
    updated: str | None = None,
    include_archived: bool = False,
    qualifiers: list[str] | None = None,
    raw_query: str | None = None,
    limit: int = 20,
    sort: Literal[
        "comments", "reactions", "interactions", "created", "updated"
    ] = "updated",
    direction: Literal["asc", "desc"] = "desc",
) -> dict[str, Any]:
    """Search GitHub issues using contribution-friendly defaults.

    Args:
        terms: Free-text search terms, such as "parser" or "documentation".
        language: Repository programming language, such as Python, Rust, or Go.
        labels: Labels to match. Omit for good first issue/help wanted; pass an
            empty list for no label filter.
        match_labels: Match any label (OR) or all labels (AND).
        repositories: Optional owner/repository names to search.
        organization: Limit results to repositories owned by this organization.
        owner_user: Limit results to repositories owned by this GitHub user.
        state: Issue state; defaults to open.
        assignee: Limit results to this GitHub assignee.
        unassigned: Return only issues with no assignee.
        created: GitHub date or range, for example ">=2026-01-01".
        updated: GitHub date or range, for example "2026-01-01..2026-06-01".
        include_archived: Include issues from archived repositories.
        qualifiers: Additional raw GitHub search qualifiers.
        raw_query: Complete GitHub query that bypasses all structured filters.
        limit: Number of results to return, from 1 to 1000.
        sort: GitHub result sort field.
        direction: Ascending or descending sort direction.
    """
    if raw_query is not None:
        query = raw_query.strip()
        if not query:
            raise ValueError("raw_query cannot be empty")
    else:
        if organization and owner_user:
            raise ValueError("organization and owner_user cannot be combined")
        selected_labels = DEFAULT_LABELS if labels is None else tuple(labels)
        query = SearchFilters(
            terms=tuple(terms or ()),
            state=state,
            language=language,
            labels=selected_labels,
            match_labels=match_labels,
            repositories=tuple(repositories or ()),
            organization=organization,
            user=owner_user,
            assignee=assignee,
            no_assignee=unassigned,
            created=created,
            updated=updated,
            include_archived=include_archived,
            qualifiers=tuple(qualifiers or ()),
        ).build()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    api_url = os.environ.get("GITHUB_API_URL", DEFAULT_API_URL)
    result = GitHubClient(token=token, api_url=api_url).search_issues(
        query,
        limit=limit,
        sort=sort,
        direction=direction,
    )
    return {
        "query": result.query,
        "total_count": result.total_count,
        "returned_count": len(result.items),
        "incomplete_results": result.incomplete_results,
        "items": [normalized_issue(item) for item in result.items],
    }


def create_server(*, host: str = "127.0.0.1", port: int = 8000) -> Any:
    """Create the FastMCP server while keeping MCP an optional dependency."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as error:
        raise RuntimeError(
            "MCP support is not installed; run `uv sync --extra mcp` or "
            "`uv tool install '.[mcp]'`"
        ) from error

    server = FastMCP(
        name="github-tags-finder",
        instructions=SERVER_INSTRUCTIONS,
        host=host,
        port=port,
        stateless_http=True,
        json_response=True,
    )
    server.tool()(search_github_issues)
    return server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="github-tags-mcp",
        description="Expose GitHub issue discovery as an MCP tool.",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="MCP transport (default: stdio)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind address")
    parser.add_argument("--port", type=int, default=8000, help="HTTP bind port")
    parser.add_argument(
        "--env-file",
        default=".env",
        help="GitHub environment file to load if present (default: .env)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        load_github_environment(args.env_file)
        server = create_server(host=args.host, port=args.port)
    except (OSError, UnicodeError, ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    try:
        server.run(transport=args.transport)
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
