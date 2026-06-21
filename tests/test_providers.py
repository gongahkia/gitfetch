import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from gitfetch.cache import CacheStore
from gitfetch.config import ConfigError, get_token, preset_config
from gitfetch.providers import BitbucketClient, CodebergClient, ForgejoClient, GiteaClient, GitLabClient, create_provider_client


def _cache() -> CacheStore:
    return CacheStore(Path(tempfile.mkdtemp()), enabled=False, ttl_seconds=0)


class ProviderTests(unittest.TestCase):
    def test_factory_selects_provider_and_base_url(self) -> None:
        config = preset_config("minimal")
        config["profile"]["provider"] = "gitlab"
        config["providers"]["gitlab"]["base_url"] = "https://gitlab.example/api/v4"
        client = create_provider_client(config, token="", cache=_cache(), offline=False)
        self.assertIsInstance(client, GitLabClient)
        self.assertEqual(client.base_url, "https://gitlab.example/api/v4")

    def test_cache_key_is_provider_scoped(self) -> None:
        gitlab = GitLabClient("", _cache(), False, "https://gitlab.com/api/v4")
        bitbucket = BitbucketClient("", _cache(), False, "https://api.bitbucket.org/2.0")
        self.assertNotEqual(gitlab._cache_key("user", "alice"), bitbucket._cache_key("user", "alice"))

    def test_gitlab_project_normalization_matches_module_shape(self) -> None:
        client = GitLabClient("", _cache(), False, "https://gitlab.com/api/v4")
        project = client._normalize_project(
            {
                "id": 42,
                "path": "repo",
                "path_with_namespace": "group/repo",
                "web_url": "https://gitlab.com/group/repo",
                "star_count": 3,
                "forks_count": 2,
                "last_activity_at": "2024-01-01T00:00:00Z",
                "namespace": {"path": "group"},
                "topics": ["cli"],
            }
        )
        self.assertEqual(project["full_name"], "group/repo")
        self.assertEqual(project["stargazers_count"], 3)
        self.assertEqual(project["languages_url"], "gitlab://project/42")
        self.assertEqual(project["topics"], ["cli"])

    def test_bitbucket_repo_normalization_matches_module_shape(self) -> None:
        client = BitbucketClient("", _cache(), False, "https://api.bitbucket.org/2.0")
        repo = client._normalize_repo(
            {
                "slug": "repo",
                "full_name": "workspace/repo",
                "language": "Python",
                "links": {"html": {"href": "https://bitbucket.org/workspace/repo"}},
                "workspace": {"slug": "workspace"},
                "updated_on": "2024-01-01T00:00:00Z",
            }
        )
        self.assertEqual(repo["full_name"], "workspace/repo")
        self.assertEqual(repo["language"], "Python")
        self.assertEqual(repo["languages_url"], "bitbucket://language/Python")

    def test_unsupported_builtin_but_not_plugin_modules(self) -> None:
        client = BitbucketClient("", _cache(), False, "https://api.bitbucket.org/2.0")
        self.assertFalse(client.supports_module("contributions"))
        self.assertTrue(client.supports_module("custom_plugin_metric"))

    def test_provider_specific_token_env_precedes_github_fallback(self) -> None:
        config = preset_config("minimal")
        config["profile"]["provider"] = "gitlab"
        with mock.patch.dict("os.environ", {"GITLAB_TOKEN": "gl-token", "GITHUB_TOKEN": "gh-token"}, clear=True):
            self.assertEqual(get_token(None, config), "gl-token")

    def test_gitea_family_factory_selects_provider_and_base_url(self) -> None:
        config = preset_config("minimal")
        config["profile"]["provider"] = "codeberg"
        client = create_provider_client(config, token="", cache=_cache(), offline=False)
        self.assertIsInstance(client, CodebergClient)
        self.assertEqual(client.base_url, "https://codeberg.org/api/v1")

        config["profile"]["provider"] = "forgejo"
        config["providers"]["forgejo"]["base_url"] = "https://forgejo.example/api/v1"
        client = create_provider_client(config, token="", cache=_cache(), offline=False)
        self.assertIsInstance(client, ForgejoClient)
        self.assertEqual(client.base_url, "https://forgejo.example/api/v1")

    def test_forgejo_requires_base_url(self) -> None:
        config = preset_config("minimal")
        config["profile"]["provider"] = "forgejo"
        with self.assertRaises(ConfigError):
            create_provider_client(config, token="", cache=_cache(), offline=False)

    def test_gitea_repo_normalization_matches_module_shape(self) -> None:
        client = GiteaClient("", _cache(), False, "https://gitea.com/api/v1")
        repo = client._normalize_repo(
            {
                "name": "repo",
                "full_name": "owner/repo",
                "html_url": "https://gitea.com/owner/repo",
                "stars_count": 7,
                "forks_count": 2,
                "watchers_count": 4,
                "open_issues_count": 5,
                "language": "Go",
                "languages_url": "https://gitea.com/api/v1/repos/owner/repo/languages",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z",
                "default_branch": "main",
                "topics": ["cli"],
                "owner": {"login": "owner", "avatar_url": "https://example/avatar.png"},
                "license": {"spdx_id": "MIT"},
            }
        )
        self.assertEqual(repo["full_name"], "owner/repo")
        self.assertEqual(repo["stargazers_count"], 7)
        self.assertEqual(repo["languages_url"], "https://gitea.com/api/v1/repos/owner/repo/languages")
        self.assertEqual(repo["topics"], ["cli"])
        self.assertEqual(repo["license"]["spdx_id"], "MIT")

    def test_gitea_user_normalization_matches_module_shape(self) -> None:
        client = GiteaClient("", _cache(), False, "https://gitea.com/api/v1")
        user = client._normalize_user(
            {
                "login": "alice",
                "full_name": "Alice",
                "description": "builder",
                "website": "https://alice.example",
                "created": "2024-01-01T00:00:00Z",
                "followers_count": 3,
                "following_count": 4,
            }
        )
        self.assertEqual(user["login"], "alice")
        self.assertEqual(user["name"], "Alice")
        self.assertEqual(user["bio"], "builder")
        self.assertEqual(user["blog"], "https://alice.example")
        self.assertEqual(user["followers"], 3)
        self.assertEqual(user["following"], 4)

    def test_gitea_heatmap_contributes_graphql_shape(self) -> None:
        client = GiteaClient("", _cache(), True, "https://gitea.com/api/v1")
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        graphql = client._graphql_like_bundle("alice", [{"timestamp": int(today.timestamp()), "contributions": 2}])
        self.assertEqual(graphql["contributionsCollection"]["contributionCalendar"]["totalContributions"], 2)

    def test_gitea_family_cache_key_is_provider_scoped(self) -> None:
        gitea = GiteaClient("", _cache(), False, "https://gitea.com/api/v1")
        codeberg = CodebergClient("", _cache(), False, "https://codeberg.org/api/v1")
        self.assertNotEqual(gitea._cache_key("user", "alice"), codeberg._cache_key("user", "alice"))

    def test_codeberg_token_env_precedes_github_fallback(self) -> None:
        config = preset_config("minimal")
        config["profile"]["provider"] = "codeberg"
        with mock.patch.dict("os.environ", {"CODEBERG_TOKEN": "cb-token", "GITHUB_TOKEN": "gh-token"}, clear=True):
            self.assertEqual(get_token(None, config), "cb-token")


if __name__ == "__main__":
    unittest.main()
