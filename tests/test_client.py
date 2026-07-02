import io
import json
import unittest
from unittest.mock import Mock, MagicMock, patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

from github_tags_finder.client import GitHubClient, GitHubError, SearchResult


class FakeResponse(io.BytesIO):
    def __init__(self, content, headers=None):
        super().__init__(content)
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class GitHubClientTests(unittest.TestCase):
    def test_request_headers_and_query_parameters(self) -> None:
        captured = {}

        def opener(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            payload = {
                "total_count": 1,
                "incomplete_results": False,
                "items": [{"number": 7}],
            }
            headers = {
                "X-RateLimit-Remaining": "59",
                "X-RateLimit-Reset": "1234567890",
            }
            return FakeResponse(json.dumps(payload).encode(), headers)

        client = GitHubClient(token="secret", timeout=4, opener=opener)
        result = client.search_issues("is:issue is:open", limit=1)

        request = captured["request"]
        parsed = urlparse(request.full_url)
        params = parse_qs(parsed.query)
        self.assertEqual(parsed.path, "/search/issues")
        self.assertEqual(params["q"], ["is:issue is:open"])
        self.assertEqual(params["sort"], ["updated"])
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")
        self.assertEqual(request.get_header("X-github-api-version"), "2022-11-28")
        self.assertEqual(captured["timeout"], 4)
        self.assertEqual(result.items, [{"number": 7}])

    def test_paginates_until_limit(self) -> None:
        calls = []

        def opener(request, timeout):
            params = parse_qs(urlparse(request.full_url).query)
            page = int(params["page"][0])
            calls.append(page)
            start = 0 if page == 1 else 100
            count = 100 if page == 1 else 20
            payload = {
                "total_count": 150,
                "incomplete_results": False,
                "items": [{"number": number} for number in range(start, start + count)],
            }
            headers = {
                "X-RateLimit-Remaining": "59",
                "X-RateLimit-Reset": "1234567890",
            }
            return FakeResponse(json.dumps(payload).encode(), headers)

        result = GitHubClient(opener=opener).search_issues("is:issue", limit=120)

        self.assertEqual(calls, [1, 2])
        self.assertEqual(len(result.items), 120)

    def test_http_error_has_actionable_hint(self) -> None:
        def opener(request, timeout):
            body = io.BytesIO(b'{"message":"Bad credentials"}')
            raise HTTPError(request.full_url, 401, "Unauthorized", {}, body)

        with self.assertRaisesRegex(GitHubError, "GITHUB_TOKEN/GH_TOKEN"):
            GitHubClient(opener=opener).search_issues("is:issue")

    # ==================== New Tests for Refinements ====================

    def test_rate_limit_fields_populated(self) -> None:
        """Test that rate_limit_remaining and rate_limit_reset are populated from headers."""
        def opener(request, timeout):
            payload = {
                "total_count": 1,
                "incomplete_results": False,
                "items": [{"number": 1}],
            }
            headers = {
                "X-RateLimit-Remaining": "42",
                "X-RateLimit-Reset": "1609459200",
            }
            return FakeResponse(json.dumps(payload).encode(), headers)

        client = GitHubClient(opener=opener)
        result = client.search_issues("test")

        self.assertEqual(result.rate_limit_remaining, 42)
        self.assertEqual(result.rate_limit_reset, 1609459200)

    def test_rate_limit_fields_none_when_missing(self) -> None:
        """Test that rate_limit fields are None when headers are missing."""
        def opener(request, timeout):
            payload = {
                "total_count": 1,
                "incomplete_results": False,
                "items": [{"number": 1}],
            }
            return FakeResponse(json.dumps(payload).encode(), {})

        client = GitHubClient(opener=opener)
        result = client.search_issues("test")

        self.assertIsNone(result.rate_limit_remaining)
        self.assertIsNone(result.rate_limit_reset)

    def test_retries_on_500_server_error(self) -> None:
        """Test that transient error 500 triggers a retry."""
        attempt_count = {"count": 0}

        def opener(request, timeout):
            attempt_count["count"] += 1
            if attempt_count["count"] == 1:
                # First attempt: 500 Internal Server Error
                body = io.BytesIO(b'{"message":"Internal server error"}')
                raise HTTPError(request.full_url, 500, "Internal Server Error", {}, body)
            else:
                # Second attempt: Success
                payload = {
                    "total_count": 1,
                    "incomplete_results": False,
                    "items": [{"number": 1}],
                }
                headers = {"X-RateLimit-Remaining": "59", "X-RateLimit-Reset": "1234567890"}
                return FakeResponse(json.dumps(payload).encode(), headers)

        client = GitHubClient(opener=opener)
        with patch("time.sleep"):
            result = client.search_issues("test")

        self.assertEqual(attempt_count["count"], 2)
        self.assertEqual(result.items, [{"number": 1}])

    def test_retries_on_502_bad_gateway(self) -> None:
        """Test that transient error 502 triggers a retry."""
        attempt_count = {"count": 0}

        def opener(request, timeout):
            attempt_count["count"] += 1
            if attempt_count["count"] == 1:
                body = io.BytesIO(b'{"message":"Bad gateway"}')
                raise HTTPError(request.full_url, 502, "Bad Gateway", {}, body)
            else:
                payload = {
                    "total_count": 1,
                    "incomplete_results": False,
                    "items": [{"number": 1}],
                }
                headers = {"X-RateLimit-Remaining": "59", "X-RateLimit-Reset": "1234567890"}
                return FakeResponse(json.dumps(payload).encode(), headers)

        client = GitHubClient(opener=opener)
        with patch("time.sleep"):
            result = client.search_issues("test")

        self.assertEqual(attempt_count["count"], 2)

    def test_retries_on_503_service_unavailable(self) -> None:
        """Test that transient error 503 triggers a retry."""
        attempt_count = {"count": 0}

        def opener(request, timeout):
            attempt_count["count"] += 1
            if attempt_count["count"] == 1:
                body = io.BytesIO(b'{"message":"Service unavailable"}')
                raise HTTPError(request.full_url, 503, "Service Unavailable", {}, body)
            else:
                payload = {
                    "total_count": 1,
                    "incomplete_results": False,
                    "items": [{"number": 1}],
                }
                headers = {"X-RateLimit-Remaining": "59", "X-RateLimit-Reset": "1234567890"}
                return FakeResponse(json.dumps(payload).encode(), headers)

        client = GitHubClient(opener=opener)
        with patch("time.sleep"):
            result = client.search_issues("test")

        self.assertEqual(attempt_count["count"], 2)

    def test_retries_on_504_gateway_timeout(self) -> None:
        """Test that transient error 504 triggers a retry."""
        attempt_count = {"count": 0}

        def opener(request, timeout):
            attempt_count["count"] += 1
            if attempt_count["count"] == 1:
                body = io.BytesIO(b'{"message":"Gateway timeout"}')
                raise HTTPError(request.full_url, 504, "Gateway Timeout", {}, body)
            else:
                payload = {
                    "total_count": 1,
                    "incomplete_results": False,
                    "items": [{"number": 1}],
                }
                headers = {"X-RateLimit-Remaining": "59", "X-RateLimit-Reset": "1234567890"}
                return FakeResponse(json.dumps(payload).encode(), headers)

        client = GitHubClient(opener=opener)
        with patch("time.sleep"):
            result = client.search_issues("test")

        self.assertEqual(attempt_count["count"], 2)

    def test_no_retry_on_401_unauthorized(self) -> None:
        """Test that permanent error 401 does NOT retry."""
        attempt_count = {"count": 0}

        def opener(request, timeout):
            attempt_count["count"] += 1
            body = io.BytesIO(b'{"message":"Bad credentials"}')
            raise HTTPError(request.full_url, 401, "Unauthorized", {}, body)

        client = GitHubClient(opener=opener)
        with self.assertRaisesRegex(GitHubError, "GITHUB_TOKEN"):
            client.search_issues("test")

        self.assertEqual(attempt_count["count"], 1)

    def test_no_retry_on_403_forbidden(self) -> None:
        """Test that permanent error 403 does NOT retry."""
        attempt_count = {"count": 0}

        def opener(request, timeout):
            attempt_count["count"] += 1
            body = io.BytesIO(b'{"message":"Forbidden"}')
            raise HTTPError(request.full_url, 403, "Forbidden", {}, body)

        client = GitHubClient(opener=opener)
        with self.assertRaisesRegex(GitHubError, "GitHub API rate limit exceeded"):
            client.search_issues("test")

        self.assertEqual(attempt_count["count"], 1)

    def test_no_retry_on_422_unprocessable_entity(self) -> None:
        """Test that permanent error 422 does NOT retry."""
        attempt_count = {"count": 0}

        def opener(request, timeout):
            attempt_count["count"] += 1
            body = io.BytesIO(b'{"message":"Validation failed"}')
            raise HTTPError(request.full_url, 422, "Unprocessable Entity", {}, body)

        client = GitHubClient(opener=opener)
        with self.assertRaisesRegex(GitHubError, "generated search query"):
            client.search_issues("test")

        self.assertEqual(attempt_count["count"], 1)

    def test_rate_limit_error_message_429(self) -> None:
        """Test that 429 error includes rate limit reset time."""
        def opener(request, timeout):
            body = io.BytesIO(b'{"message":"API rate limit exceeded"}')
            raise HTTPError(
                request.full_url,
                429,
                "Too Many Requests",
                {"X-RateLimit-Reset": "1609459200"},
                body,
            )

        client = GitHubClient(opener=opener)
        with self.assertRaisesRegex(GitHubError, "1609459200"):
            client.search_issues("test")

    def test_rate_limit_error_message_without_reset_time(self) -> None:
        """Test that 429 error has fallback message when reset time is missing."""
        def opener(request, timeout):
            body = io.BytesIO(b'{"message":"API rate limit exceeded"}')
            raise HTTPError(
                request.full_url, 429, "Too Many Requests", {}, body
            )

        client = GitHubClient(opener=opener)
        with self.assertRaisesRegex(GitHubError, "GitHub API rate limit exceeded. Please wait before retrying."):
            client.search_issues("test")

    def test_empty_query_validation(self) -> None:
        """Test that empty query raises ValueError."""
        client = GitHubClient()
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            client.search_issues("")

    def test_whitespace_only_query_validation(self) -> None:
        """Test that whitespace-only query raises ValueError."""
        client = GitHubClient()
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            client.search_issues("   ")

    def test_query_at_256_chars_allowed(self) -> None:
        """Test that query with exactly 256 characters is allowed."""
        def opener(request, timeout):
            payload = {
                "total_count": 0,
                "incomplete_results": False,
                "items": [],
            }
            headers = {"X-RateLimit-Remaining": "59", "X-RateLimit-Reset": "1234567890"}
            return FakeResponse(json.dumps(payload).encode(), headers)

        client = GitHubClient(opener=opener)
        query_256 = "a" * 256
        # Should not raise
        result = client.search_issues(query_256)
        self.assertEqual(result.items, [])

    def test_successful_search_after_retry(self) -> None:
        """Test that search succeeds after transient error and retry."""
        attempt_count = {"count": 0}

        def opener(request, timeout):
            attempt_count["count"] += 1
            if attempt_count["count"] < 3:
                # First two attempts fail with transient errors
                body = io.BytesIO(b'{"message":"Service error"}')
                raise HTTPError(
                    request.full_url,
                    503 if attempt_count["count"] == 1 else 502,
                    "Service Error",
                    {},
                    body,
                )
            else:
                # Third attempt succeeds
                payload = {
                    "total_count": 2,
                    "incomplete_results": False,
                    "items": [{"number": 1}, {"number": 2}],
                }
                headers = {"X-RateLimit-Remaining": "58", "X-RateLimit-Reset": "1234567890"}
                return FakeResponse(json.dumps(payload).encode(), headers)

        client = GitHubClient(opener=opener)
        with patch("time.sleep"):
            result = client.search_issues("test")

        self.assertEqual(attempt_count["count"], 3)
        self.assertEqual(len(result.items), 2)
        self.assertEqual(result.total_count, 2)

    def test_max_retries_exceeded(self) -> None:
        """Test that error is raised after max retries exhausted."""
        def opener(request, timeout):
            body = io.BytesIO(b'{"message":"Service error"}')
            raise HTTPError(request.full_url, 503, "Service Unavailable", {}, body)

        client = GitHubClient(opener=opener)
        with patch("time.sleep"):
            with self.assertRaisesRegex(GitHubError, "Service error"):
                client.search_issues("test")

    def test_exponential_backoff_timing(self) -> None:
        """Test that exponential backoff is applied correctly."""
        sleep_times = []

        def mock_sleep(duration):
            sleep_times.append(duration)

        def opener(request, timeout):
            body = io.BytesIO(b'{"message":"Service error"}')
            raise HTTPError(request.full_url, 503, "Service Unavailable", {}, body)

        client = GitHubClient(opener=opener)
        with patch("time.sleep", side_effect=mock_sleep):
            with self.assertRaises(GitHubError):
                client.search_issues("test")

        # Should attempt exponential backoff: 2^0 = 1, 2^1 = 2
        self.assertEqual(sleep_times, [1, 2])


if __name__ == "__main__":
    unittest.main()
