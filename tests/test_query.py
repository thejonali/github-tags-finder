import unittest

from github_tags_finder.query import DEFAULT_LABELS, SearchFilters, quote


class SearchFiltersTests(unittest.TestCase):
    def test_default_query_targets_approachable_open_issues(self) -> None:
        query = SearchFilters().build()

        self.assertEqual(
            query,
            'is:issue is:open archived:false label:"good first issue","help wanted"',
        )

    def test_structured_filters_and_any_labels(self) -> None:
        query = SearchFilters(
            terms=("parser",),
            language="C++",
            labels=("beginner", "mentored"),
            repositories=("owner/one", "owner/two"),
            no_assignee=True,
            created=">=2026-01-01",
            qualifiers=("comments:<10",),
        ).build()

        self.assertEqual(
            query,
            'parser is:issue is:open archived:false language:"C++" '
            'label:"beginner","mentored" '
            '(repo:"owner/one" OR repo:"owner/two") no:assignee '
            "created:>=2026-01-01 comments:<10",
        )

    def test_all_labels_use_separate_qualifiers(self) -> None:
        query = SearchFilters(labels=("bug", "confirmed"), match_labels="all").build()
        self.assertIn('label:"bug" label:"confirmed"', query)

    def test_labels_can_be_disabled(self) -> None:
        query = SearchFilters(labels=()).build()
        self.assertNotIn("label:", query)

    def test_all_state_and_archived(self) -> None:
        query = SearchFilters(state="all", include_archived=True, labels=()).build()
        self.assertEqual(query, "is:issue")

    def test_quote_escapes_special_characters(self) -> None:
        self.assertEqual(quote('say "hi"\\now'), '"say \\"hi\\"\\\\now"')

    def test_default_labels_are_stable(self) -> None:
        self.assertEqual(DEFAULT_LABELS, ("good first issue", "help wanted"))


if __name__ == "__main__":
    unittest.main()
