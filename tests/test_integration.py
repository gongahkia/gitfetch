import os
import tempfile
import unittest
from pathlib import Path

from gitfetch.cache import CacheStore
from gitfetch.github_api import GitHubClient


@unittest.skipUnless(
    os.environ.get("GITFETCH_INTEGRATION_TOKEN"),
    "set GITFETCH_INTEGRATION_TOKEN to run authenticated integration coverage",
)
class GitHubIntegrationTests(unittest.TestCase):
    def test_authenticated_context_and_graphql(self) -> None:
        token = os.environ["GITFETCH_INTEGRATION_TOKEN"]
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = CacheStore(Path(tmpdir), enabled=False, ttl_seconds=0)
            client = GitHubClient(token=token, cache=cache)
            viewer = client.get_authenticated_user()
            context = client.get_context(
                username=viewer["login"],
                mode="viewer",
                repo_filters={
                    "exclude_forks": False,
                    "exclude_archived": False,
                    "exclude_templates": False,
                },
            )

        self.assertTrue(context.viewer_mode)
        self.assertEqual(context.user["login"].lower(), viewer["login"].lower())
        self.assertEqual(context.graphql.get("login", "").lower(), viewer["login"].lower())
        self.assertIn("contributionsCollection", context.graphql)
