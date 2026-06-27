"""Command-line interface for github-tags-finder."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

from . import __version__
from .client import DEFAULT_API_URL, GitHubClient, GitHubError, MAX_SEARCH_RESULTS
from .environment import load_github_environment
from .output import write_json, write_text
from .query import DEFAULT_LABELS, SearchFilters


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="github-tags",
        description=(
            "Find GitHub issues by programming language and labels. By default, "
            "open issues labeled 'good first issue' OR 'help wanted' are returned."
        ),
    )
    parser.add_argument("terms", nargs="*", help="free-text terms to search for")
    parser.add_argument("--language", "-L", help="repository programming language")
    parser.add_argument(
        "--label",
        "-l",
        action="append",
        help="label to match; first use replaces the default labels (repeatable)",
    )
    parser.add_argument(
        "--match-labels",
        choices=("any", "all"),
        default="any",
        help="match any or all supplied labels (default: any)",
    )
    parser.add_argument(
        "--no-labels",
        action="store_true",
        help="disable the default label filter",
    )
    parser.add_argument(
        "--repo", action="append", default=[], help="owner/repository (repeatable)"
    )
    owner = parser.add_mutually_exclusive_group()
    owner.add_argument("--org", help="limit results to an organization")
    owner.add_argument("--user", help="limit results to repositories owned by a user")
    parser.add_argument("--state", choices=("open", "closed", "all"), default="open")
    assignee = parser.add_mutually_exclusive_group()
    assignee.add_argument("--assignee", help="limit results to an assignee")
    assignee.add_argument(
        "--no-assignee", action="store_true", help="only unassigned issues"
    )
    parser.add_argument("--created", help="GitHub date/range, for example >=2026-01-01")
    parser.add_argument(
        "--updated", help="GitHub date/range, for example 2026-01-01..2026-06-01"
    )
    parser.add_argument(
        "--include-archived", action="store_true", help="include archived repositories"
    )
    parser.add_argument(
        "--qualifier",
        "-q",
        action="append",
        default=[],
        help="append a raw GitHub search qualifier (repeatable)",
    )
    parser.add_argument(
        "--raw-query",
        help="use a complete GitHub search query instead of all structured filters",
    )
    parser.add_argument(
        "--sort",
        choices=("comments", "reactions", "interactions", "created", "updated"),
        default="updated",
    )
    parser.add_argument("--direction", choices=("asc", "desc"), default="desc")
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help=f"results to return, 1-{MAX_SEARCH_RESULTS} (default: 20)",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit stable JSON for scripts"
    )
    parser.add_argument(
        "--query-only",
        action="store_true",
        help="print the generated query without calling GitHub",
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("GITHUB_API_URL", DEFAULT_API_URL),
        help="GitHub API base URL (or set GITHUB_API_URL)",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    return parser


def _query_from_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> str:
    if args.raw_query:
        return args.raw_query
    if args.no_labels and args.label:
        parser.error("--no-labels cannot be combined with --label")

    labels: tuple[str, ...]
    if args.no_labels:
        labels = ()
    elif args.label:
        labels = tuple(args.label)
    else:
        labels = DEFAULT_LABELS

    return SearchFilters(
        terms=tuple(args.terms),
        state=args.state,
        language=args.language,
        labels=labels,
        match_labels=args.match_labels,
        repositories=tuple(args.repo),
        organization=args.org,
        user=args.user,
        assignee=args.assignee,
        no_assignee=args.no_assignee,
        created=args.created,
        updated=args.updated,
        include_archived=args.include_archived,
        qualifiers=tuple(args.qualifier),
    ).build()


def main(argv: Sequence[str] | None = None) -> int:
    try:
        load_github_environment()
    except (OSError, UnicodeError, ValueError) as error:
        print(f"error: could not load .env: {error}", file=sys.stderr)
        return 1

    parser = build_parser()
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= MAX_SEARCH_RESULTS:
        parser.error(f"--limit must be between 1 and {MAX_SEARCH_RESULTS}")

    query = _query_from_args(args, parser)
    if args.query_only:
        print(query)
        return 0

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    client = GitHubClient(token=token, api_url=args.api_url)
    try:
        result = client.search_issues(
            query,
            limit=args.limit,
            sort=args.sort,
            direction=args.direction,
        )
    except (GitHubError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if args.json:
        write_json(result, sys.stdout)
    else:
        write_text(result, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
