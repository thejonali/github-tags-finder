import io
import json
import unittest
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

from github_tags_finder.client import GitHubClient, GitHubError


class FakeResponse(io.BytesIO):
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
            return FakeResponse(json.dumps(payload).encode())

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
            return FakeResponse(json.dumps(payload).encode())

        result = GitHubClient(opener=opener).search_issues("is:issue", limit=120)

        self.assertEqual(calls, [1, 2])
        self.assertEqual(len(result.items), 120)

    def test_http_error_has_actionable_hint(self) -> None:
        def opener(request, timeout):
            body = io.BytesIO(b'{"message":"Bad credentials"}')
            raise HTTPError(request.full_url, 401, "Unauthorized", {}, body)

        with self.assertRaisesRegex(GitHubError, "GITHUB_TOKEN/GH_TOKEN"):
            GitHubClient(opener=opener).search_issues("is:issue")


if __name__ == "__main__":
    unittest.main()
