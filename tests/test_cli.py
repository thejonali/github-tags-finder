import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from github_tags_finder.cli import main
from github_tags_finder.client import SearchResult


class CliTests(unittest.TestCase):
    def test_query_only_uses_default_labels(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(["--language", "Python", "--query-only"])

        self.assertEqual(status, 0)
        self.assertIn('language:"Python"', output.getvalue())
        self.assertIn('label:"good first issue","help wanted"', output.getvalue())

    def test_supplied_labels_replace_defaults(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(["--label", "beginner", "--query-only"])

        self.assertEqual(status, 0)
        self.assertIn('label:"beginner"', output.getvalue())
        self.assertNotIn("good first issue", output.getvalue())

    @patch("github_tags_finder.cli.GitHubClient.search_issues")
    def test_json_output(self, search_issues) -> None:
        search_issues.return_value = SearchResult(
            query="is:issue",
            total_count=1,
            incomplete_results=False,
            items=[
                {
                    "repository_url": "https://api.github.com/repos/acme/widgets",
                    "number": 42,
                    "title": "Document widgets",
                    "html_url": "https://github.com/acme/widgets/issues/42",
                    "labels": [{"name": "help wanted"}],
                    "assignees": [],
                    "state": "open",
                    "comments": 3,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-02T00:00:00Z",
                }
            ],
        )
        output = io.StringIO()

        with redirect_stdout(output):
            status = main(["--raw-query", "is:issue", "--json"])

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(payload["items"][0]["repository"], "acme/widgets")

    @patch(
        "github_tags_finder.cli.GitHubClient.search_issues",
        side_effect=RuntimeError("boom"),
    )
    def test_unexpected_errors_are_not_hidden(self, _search_issues) -> None:
        with self.assertRaisesRegex(RuntimeError, "boom"):
            main([])


if __name__ == "__main__":
    unittest.main()
