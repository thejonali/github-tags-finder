import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from github_tags_finder.environment import load_github_environment


class EnvironmentTests(unittest.TestCase):
    def test_loads_only_github_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, ".env")
            path.write_text(
                "# local credentials\n"
                "GITHUB_TOKEN='github-token'\n"
                "GITHUB_API_URL=https://github.example.com/api/v3\n"
                "UNRELATED_SECRET=do-not-load\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                loaded = load_github_environment(path)

                self.assertTrue(loaded)
                self.assertEqual(os.environ["GITHUB_TOKEN"], "github-token")
                self.assertEqual(
                    os.environ["GITHUB_API_URL"],
                    "https://github.example.com/api/v3",
                )
                self.assertNotIn("UNRELATED_SECRET", os.environ)

    def test_does_not_override_process_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, ".env")
            path.write_text("GITHUB_TOKEN=file-token\n", encoding="utf-8")
            with patch.dict(os.environ, {"GITHUB_TOKEN": "process-token"}, clear=True):
                load_github_environment(path)
                self.assertEqual(os.environ["GITHUB_TOKEN"], "process-token")

    def test_missing_file_is_allowed(self) -> None:
        self.assertFalse(load_github_environment("does-not-exist.env"))


if __name__ == "__main__":
    unittest.main()
