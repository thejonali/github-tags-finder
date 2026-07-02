"""Small standard-library client for GitHub's issue search endpoint."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_VERSION = "2022-11-28"
DEFAULT_API_URL = "https://api.github.com"
MAX_SEARCH_RESULTS = 1_000
TRANSIENT_ERROR_CODES = {500, 502, 503, 504}

logger = logging.getLogger(__name__)


class GitHubError(RuntimeError):
    """A GitHub API request failed."""


@dataclass(frozen=True)
class SearchResult:
    query: str
    total_count: int
    incomplete_results: bool
    items: list[dict[str, Any]]
    rate_limit_remaining: int | None = None
    rate_limit_reset: int | None = None


class GitHubClient:
    def __init__(
        self,
        *,
        token: str | None = None,
        api_url: str = DEFAULT_API_URL,
        timeout: float = 20.0,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        self.token = token
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self._opener = opener

    def search_issues(
        self,
        query: str,
        *,
        limit: int = 20,
        sort: str = "updated",
        direction: str = "desc",
    ) -> SearchResult:
        logger.debug(f"Searching issues with query: {query}")
        if not query or not query.strip():
            raise ValueError("query cannot be empty")
        if not 1 <= limit <= MAX_SEARCH_RESULTS:
            raise ValueError(f"limit must be between 1 and {MAX_SEARCH_RESULTS}")

        items: list[dict[str, Any]] = []
        total_count = 0
        incomplete = False
        page = 1
        rate_limit_remaining = None
        rate_limit_reset = None

        while len(items) < limit:
            per_page = min(100, limit - len(items))
            params = {
                "q": query,
                "sort": sort,
                "order": direction,
                "per_page": per_page,
                "page": page,
            }
            payload, rate_limits = self._get_json(f"/search/issues?{urlencode(params)}")
            rate_limit_remaining = rate_limits["remaining"]
            rate_limit_reset = rate_limits["reset"]

            page_items = payload.get("items")
            if not isinstance(page_items, list):
                raise GitHubError("GitHub returned an invalid issue search response")

            if page == 1:
                raw_total = payload.get("total_count", 0)
                total_count = raw_total if isinstance(raw_total, int) else 0
            incomplete = incomplete or bool(payload.get("incomplete_results", False))
            items.extend(item for item in page_items if isinstance(item, dict))

            if (
                not page_items
                or len(page_items) < per_page
                or len(items) >= total_count
            ):
                break
            page += 1

        return SearchResult(
            query=query,
            total_count=total_count,
            incomplete_results=incomplete,
            items=items[:limit],
            rate_limit_remaining=rate_limit_remaining,
            rate_limit_reset=rate_limit_reset,
        )

    def _get_json(self, path: str) -> tuple[dict[str, Any], dict[str, int | None]]:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                headers = {
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": API_VERSION,
                    "User-Agent": "github-tags-finder",
                }
                if self.token:
                    headers["Authorization"] = f"Bearer {self.token}"
                request = Request(f"{self.api_url}{path}", headers=headers)

                try:
                    with self._opener(request, timeout=self.timeout) as response:
                        payload = json.load(response)
                        # Extract rate limit information
                        rate_limit_remaining = response.headers.get("X-RateLimit-Remaining")
                        rate_limit_reset = response.headers.get("X-RateLimit-Reset")
                        rate_limits = {
                            "remaining": int(rate_limit_remaining) if rate_limit_remaining else None,
                            "reset": int(rate_limit_reset) if rate_limit_reset else None,
                        }
                except HTTPError as error:
                    # Check if error is transient before converting to GitHubError
                    if error.code in TRANSIENT_ERROR_CODES and attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.info(f"Transient error {error.code}. Retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    raise self._http_error(error) from error
                except URLError as error:
                    reason = getattr(error, "reason", error)
                    raise GitHubError(f"Could not reach GitHub: {reason}") from error
                except (json.JSONDecodeError, UnicodeDecodeError) as error:
                    raise GitHubError(
                        "GitHub returned a response that was not valid JSON"
                    ) from error

                if not isinstance(payload, dict):
                    raise GitHubError("GitHub returned an unexpected response")
                return payload, rate_limits
            except (GitHubError, URLError):
                # Non-transient errors or after max retries reached
                raise

    @staticmethod
    def _http_error(error: HTTPError) -> GitHubError:
        message = ""

        try:
            payload = json.loads(error.read().decode("utf-8"))
            if isinstance(payload, dict):
                message = str(payload.get("message", ""))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

        detail = f": {message}" if message else ""
        hint = ""

    # Authentication failure
        if error.code == 401:
            hint = " Check GITHUB_TOKEN/GH_TOKEN."

    # GitHub API rate limit exceeded
        elif error.code in {403, 429}:
            reset_time = error.headers.get("X-RateLimit-Reset")

            if reset_time:
                hint = (
                f" GitHub API rate limit exceeded. "
                f"Retry after {reset_time} (Unix timestamp)."
                )
            else:
                hint = (
                " GitHub API rate limit exceeded. "
                "Please wait before retrying."
                )

    # Invalid search query
        elif error.code == 422:
            hint = " Check the generated search query with --query-only."

        return GitHubError(
            f"GitHub API request failed ({error.code}){detail}.{hint}".rstrip()
    )