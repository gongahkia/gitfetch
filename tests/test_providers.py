import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from gitfetch.cache import CacheStore
from gitfetch.config import ConfigError, get_token, preset_config
from gitfetch.github_api import GitHubAPIError, GitHubClient, format_relative_days
from gitfetch.providers import BitbucketClient, CodebergClient, ForgejoClient, GiteaClient, GitLabClient, create_provider_client


def _cache() -> CacheStore:
    return CacheStore(Path(tempfile.mkdtemp()), enabled=False, ttl_seconds=0)


class ProviderTests(unittest.TestCase):
    def test_relative_days_rejects_naive_timestamps_and_clamps_future_dates(self) -> None:
        self.assertIsNone(format_relative_days("2024-01-01T00:00:00"))
        self.assertEqual(format_relative_days("2999-01-01T00:00:00+00:00"), "0 days ago")

    def test_github_enterprise_uses_its_own_graphql_endpoint(self) -> None:
        client = GitHubClient("token", _cache(), False, "https://github.example/api/v3")
        self.assertEqual(client._graphql_url(), "https://github.example/api/graphql")
        self.assertEqual(
            GitHubClient("token", _cache(), False, "https://api.github.com")._graphql_url(),
            "https://api.github.com/graphql",
        )

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

    def test_authenticated_cache_keys_are_token_scoped(self) -> None:
        first = GitLabClient("first-token", _cache(), False, "https://gitlab.com/api/v4")
        second = GitLabClient("second-token", _cache(), False, "https://gitlab.com/api/v4")
        self.assertNotEqual(first._cache_key("viewer", "self"), second._cache_key("viewer", "self"))
        self.assertNotIn("first-token", first._cache_key("viewer", "self"))

    def test_gitlab_group_can_be_rendered_as_a_profile_target(self) -> None:
        client = GitLabClient("", _cache(), False, "https://gitlab.com/api/v4")
        group = {"id": 7, "path": "gitlab-org", "name": "GitLab.org", "projects_count": 1}
        project = {"id": 42, "path": "repo", "path_with_namespace": "gitlab-org/repo"}
        with mock.patch.object(client, "_resolve_user", side_effect=GitHubAPIError("not a user")), mock.patch.object(
            client, "_resolve_group", return_value=group
        ), mock.patch.object(client, "_paginate", return_value=[project]):
            context = client.get_context("gitlab-org", "public", {})
        self.assertEqual(context.user["login"], "gitlab-org")
        self.assertEqual(context.user["public_repos"], 1)
        self.assertEqual(context.repos[0]["full_name"], "gitlab-org/repo")
        self.assertEqual(context.events, [])

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

    def test_bitbucket_snippets_map_to_gists(self) -> None:
        client = BitbucketClient("", _cache(), False, "https://api.bitbucket.org/2.0")
        with mock.patch.object(
            client,
            "_get_json_optional",
            return_value={"values": [{"id": "abc", "title": "note", "links": {"html": {"href": "https://bb/snippet"}}}]},
        ):
            gists = client.get_gists("workspace", 1)
        self.assertEqual(gists[0]["id"], "abc")
        self.assertEqual(gists[0]["description"], "note")

    def test_bitbucket_releases_fall_back_to_tags(self) -> None:
        client = BitbucketClient("", _cache(), False, "https://api.bitbucket.org/2.0")
        with mock.patch.object(
            client,
            "_get_json_optional",
            side_effect=[
                {"values": []},
                {"values": [{"name": "v1", "target": {"date": "2024-01-01T00:00:00Z"}, "links": {"html": {"href": "https://bb/tag"}}}]},
            ],
        ):
            releases = client.get_repo_releases("workspace", "repo", 1)
        self.assertEqual(releases[0]["tag_name"], "v1")
        self.assertEqual(releases[0]["published_at"], "2024-01-01T00:00:00Z")

    def test_bitbucket_profile_readme_uses_same_name_repo(self) -> None:
        client = BitbucketClient("", _cache(), False, "https://api.bitbucket.org/2.0")
        with mock.patch.object(client, "_get_json_optional", return_value={"mainbranch": {"name": "main"}}), mock.patch.object(
            client,
            "_get_text_optional",
            return_value="# hello",
        ):
            self.assertEqual(client.get_profile_readme("workspace"), "# hello")

    def test_provider_specific_token_env_precedes_github_fallback(self) -> None:
        config = preset_config("minimal")
        config["profile"]["provider"] = "gitlab"
        with mock.patch.dict("os.environ", {"GITLAB_TOKEN": "gl-token", "GITHUB_TOKEN": "gh-token"}, clear=True):
            self.assertEqual(get_token(None, config), "gl-token")

    def test_gitlab_dependencies_map_to_sbom_shape(self) -> None:
        client = GitLabClient("", _cache(), False, "https://gitlab.com/api/v4")
        with mock.patch.object(client, "get_repo", return_value={"id": 42}), mock.patch.object(
            client,
            "_get_json_optional",
            return_value=[{"name": "rails", "version": "7", "package_manager": "bundler"}],
        ):
            sbom = client.get_repo_sbom("group", "repo")
        self.assertEqual(sbom["sbom"]["packages"][0]["name"], "rails")
        self.assertEqual(sbom["sbom"]["packages"][0]["package_manager"], "bundler")

    def test_gitlab_security_findings_map_to_advisory_shape(self) -> None:
        client = GitLabClient("", _cache(), False, "https://gitlab.com/api/v4")
        with mock.patch.object(client, "get_repo", return_value={"id": 42}), mock.patch.object(
            client,
            "_get_json_optional",
            return_value=[{"name": "Possible command injection", "severity": "high"}],
        ):
            advisories = client.get_repo_security_advisories("group", "repo", 1)
        self.assertEqual(advisories[0]["summary"], "Possible command injection")
        self.assertEqual(advisories[0]["severity"], "high")

    def test_gitlab_group_packages_are_exposed(self) -> None:
        client = GitLabClient("", _cache(), False, "https://gitlab.com/api/v4")
        with mock.patch.object(
            client,
            "_get_json_optional",
            side_effect=[{"id": 7}, [{"name": "pkg", "package_type": "npm"}]],
        ):
            packages = client.get_user_packages("group", "npm", 1)
        self.assertEqual(packages[0]["name"], "pkg")

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

    def test_gitea_actions_runs_map_to_workflow_shape(self) -> None:
        client = GiteaClient("", _cache(), False, "https://gitea.com/api/v1")
        response = mock.Mock()
        response.ok = True
        response.status_code = 200
        response.json.return_value = {"workflow_runs": [{"name": "ci", "status": "success", "html_url": "https://gitea/run"}]}
        with mock.patch.object(client.session, "get", return_value=response):
            runs = client.get_repo_workflow_runs("owner", "repo", 1)
        self.assertEqual(runs[0]["name"], "ci")
        self.assertEqual(runs[0]["conclusion"], "success")

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
