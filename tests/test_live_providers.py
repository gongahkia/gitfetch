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
                    if provider == "bitbucket":
                        config["providers"][provider]["auth_mode"] = os.environ.get(
                            "GITFETCH_LIVE_BITBUCKET_AUTH_MODE", "bearer"
                        )
                        config["providers"][provider]["auth_username"] = os.environ.get(
                            "GITFETCH_LIVE_BITBUCKET_AUTH_USERNAME", ""
                        )
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

    def test_gitlab_authenticated_viewer_context(self) -> None:
        token = os.environ.get("GITFETCH_LIVE_GITLAB_TOKEN")
        username = os.environ.get("GITFETCH_LIVE_GITLAB_USER")
        if not token or not username:
            self.skipTest("set GITFETCH_LIVE_GITLAB_USER and GITFETCH_LIVE_GITLAB_TOKEN")
        with tempfile.TemporaryDirectory() as tmpdir:
            config = preset_config("minimal")
            config["profile"]["provider"] = "gitlab"
            client = create_provider_client(
                config,
                token=token,
                cache=CacheStore(Path(tmpdir), enabled=False, ttl_seconds=0),
            )
            context = client.get_context(username, "viewer", config["repo_filters"], include_graphql=False)
        self.assertTrue(context.viewer_mode)
        self.assertEqual(context.authenticated_login.lower(), username.lower())

    def test_forgejo_compatible_context(self) -> None:
        base_url = os.environ.get("GITFETCH_LIVE_FORGEJO_BASE_URL", "https://codeberg.org/api/v1")
        username = os.environ.get("GITFETCH_LIVE_FORGEJO_USER", "forgejo")
        with tempfile.TemporaryDirectory() as tmpdir:
            config = preset_config("minimal")
            config["profile"]["provider"] = "forgejo"
            config["providers"]["forgejo"]["base_url"] = base_url
            client = create_provider_client(
                config,
                token=os.environ.get("GITFETCH_LIVE_FORGEJO_TOKEN", ""),
                cache=CacheStore(Path(tmpdir), enabled=False, ttl_seconds=0),
            )
            context = client.get_context(username, "public", config["repo_filters"], include_graphql=False)
        self.assertTrue(context.user.get("login"))
        self.assertIsInstance(context.repos, list)

    def test_gitea_authenticated_viewer_context(self) -> None:
        token = os.environ.get("GITFETCH_LIVE_GITEA_TOKEN")
        username = os.environ.get("GITFETCH_LIVE_GITEA_USER")
        if not token or not username:
            self.skipTest("set GITFETCH_LIVE_GITEA_USER and GITFETCH_LIVE_GITEA_TOKEN")
        with tempfile.TemporaryDirectory() as tmpdir:
            config = preset_config("minimal")
            config["profile"]["provider"] = "gitea"
            client = create_provider_client(
                config,
                token=token,
                cache=CacheStore(Path(tmpdir), enabled=False, ttl_seconds=0),
            )
            context = client.get_context(username, "viewer", config["repo_filters"], include_graphql=False)
        self.assertTrue(context.viewer_mode)
        self.assertEqual(context.authenticated_login.lower(), username.lower())

    def test_bitbucket_authenticated_workspace_context(self) -> None:
        token = os.environ.get("GITFETCH_LIVE_BITBUCKET_TOKEN")
        workspace = os.environ.get("GITFETCH_LIVE_BITBUCKET_USER")
        auth_username = os.environ.get("GITFETCH_LIVE_BITBUCKET_AUTH_USERNAME")
        if not token or not workspace or not auth_username:
            self.skipTest("set Bitbucket token, workspace, and Basic-auth username variables")
        with tempfile.TemporaryDirectory() as tmpdir:
            config = preset_config("minimal")
            config["profile"]["provider"] = "bitbucket"
            config["providers"]["bitbucket"]["auth_mode"] = os.environ.get(
                "GITFETCH_LIVE_BITBUCKET_AUTH_MODE", "basic"
            )
            config["providers"]["bitbucket"]["auth_username"] = auth_username
            client = create_provider_client(
                config,
                token=token,
                cache=CacheStore(Path(tmpdir), enabled=False, ttl_seconds=0),
            )
            context = client.get_context(workspace, "public", config["repo_filters"], include_graphql=False)
        self.assertEqual(context.user.get("login"), workspace)
        self.assertIsInstance(context.repos, list)
