"""Opt-in public-provider smoke tests.

Run locally with:
    GITFETCH_LIVE_PROVIDERS=1 python -m unittest tests.test_live_providers -v

Optional *_USER and *_BASE_URL variables let an account holder test a target
under their control without putting credentials in the test suite.
"""

import os
import tempfile
import unittest
from pathlib import Path

from gitfetch.cache import CacheStore
from gitfetch.config import preset_config
from gitfetch.providers import create_provider_client


@unittest.skipUnless(
    os.environ.get("GITFETCH_LIVE_PROVIDERS") == "1",
    "set GITFETCH_LIVE_PROVIDERS=1 to run live provider smoke tests",
)
class LiveProviderSmokeTests(unittest.TestCase):
    PROVIDERS = {
        "github": ("GITFETCH_LIVE_GITHUB_USER", "octocat"),
        "gitlab": ("GITFETCH_LIVE_GITLAB_USER", "gitlab-org"),
        "bitbucket": ("GITFETCH_LIVE_BITBUCKET_USER", "atlassian"),
        "gitea": ("GITFETCH_LIVE_GITEA_USER", "gitea"),
        "codeberg": ("GITFETCH_LIVE_CODEBERG_USER", "forgejo"),
    }

    def test_public_profile_contexts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            for provider, (env_name, default_user) in self.PROVIDERS.items():
                with self.subTest(provider=provider):
                    config = preset_config("minimal")
                    config["profile"]["provider"] = provider
                    config["profile"]["username"] = os.environ.get(env_name, default_user)
                    base_url = os.environ.get(f"GITFETCH_LIVE_{provider.upper()}_BASE_URL")
                    if base_url:
                        config["providers"][provider]["base_url"] = base_url
                    client = create_provider_client(
                        config,
                        token=os.environ.get(f"GITFETCH_LIVE_{provider.upper()}_TOKEN", ""),
                        cache=CacheStore(Path(tmpdir) / provider, enabled=False, ttl_seconds=0),
                    )
                    context = client.get_context(
                        config["profile"]["username"], "public", config["repo_filters"], include_graphql=False
                    )
                    self.assertTrue(context.user.get("login"))
                    self.assertIsInstance(context.repos, list)
