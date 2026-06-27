import asyncio
import importlib.util
import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from github_tags_finder.client import SearchResult
from github_tags_finder.mcp_server import main, search_github_issues


class McpToolTests(unittest.TestCase):
    @patch("github_tags_finder.mcp_server.GitHubClient.search_issues")
    def test_search_uses_beginner_labels_by_default(self, search) -> None:
        search.return_value = SearchResult(
            query="ignored",
            total_count=0,
            incomplete_results=False,
            items=[],
        )

        result = search_github_issues(language="Python", limit=5)

        query = search.call_args.args[0]
        self.assertIn('language:"Python"', query)
        self.assertIn('label:"good first issue","help wanted"', query)
        self.assertEqual(search.call_args.kwargs["limit"], 5)
        self.assertEqual(result["returned_count"], 0)

    @patch("github_tags_finder.mcp_server.GitHubClient.search_issues")
    def test_empty_labels_disable_label_filter(self, search) -> None:
        search.return_value = SearchResult("ignored", 0, False, [])

        search_github_issues(labels=[])

        self.assertNotIn("label:", search.call_args.args[0])

    @patch("github_tags_finder.mcp_server.GitHubClient.search_issues")
    def test_raw_query_bypasses_structured_filters(self, search) -> None:
        search.return_value = SearchResult("is:issue label:docs", 0, False, [])

        result = search_github_issues(
            raw_query="is:issue label:docs",
            language="Python",
        )

        self.assertEqual(search.call_args.args[0], "is:issue label:docs")
        self.assertEqual(result["query"], "is:issue label:docs")

    def test_empty_raw_query_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            search_github_issues(raw_query="  ")

    def test_conflicting_owner_filters_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be combined"):
            search_github_issues(organization="acme", owner_user="octocat")

    @unittest.skipUnless(importlib.util.find_spec("mcp"), "MCP extra is not installed")
    def test_server_exposes_search_tool(self) -> None:
        from github_tags_finder.mcp_server import create_server

        tools = asyncio.run(create_server().list_tools())

        self.assertEqual([tool.name for tool in tools], ["search_github_issues"])

    @patch("github_tags_finder.mcp_server.load_github_environment")
    @patch("github_tags_finder.mcp_server.create_server")
    def test_interrupt_stops_server_cleanly(
        self, create_server, _load_environment
    ) -> None:
        create_server.return_value.run.side_effect = KeyboardInterrupt

        self.assertEqual(main([]), 130)

    @patch(
        "github_tags_finder.mcp_server.load_github_environment",
        side_effect=ValueError("invalid file"),
    )
    def test_configuration_error_uses_stderr(self, _load_environment) -> None:
        error = io.StringIO()

        with redirect_stderr(error):
            status = main([])

        self.assertEqual(status, 1)
        self.assertIn("invalid file", error.getvalue())


if __name__ == "__main__":
    unittest.main()
