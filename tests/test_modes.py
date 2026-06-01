import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gitfetch.cli import main


def _write_minimal_config(path: Path) -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        main(["--config", str(path), "config", "init", "--preset", "minimal"])


@mock.patch("gitfetch.modes.GitHubClient")
class ModesTests(unittest.TestCase):
    def test_repo_subcommand_renders(self, mock_client_cls: mock.Mock) -> None:
        instance = mock_client_cls.return_value
        instance.get_repo.return_value = {
            "full_name": "octocat/Hello-World",
            "description": "First repo",
            "default_branch": "master",
            "stargazers_count": 100,
            "forks_count": 50,
            "watchers_count": 25,
            "open_issues_count": 3,
            "size": 12,
            "owner": {"avatar_url": None},
            "license": {"spdx_id": "MIT"},
        }
        instance.get_repo_languages.return_value = {"Python": 1000, "Markdown": 100}
        instance.get_repo_contributors.return_value = [{"login": "alice", "contributions": 42}]
        instance.get_repo_commits.return_value = [
            {"sha": "abc1234567", "commit": {"message": "first commit", "author": {"name": "alice"}}},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "config.toml"
            _write_minimal_config(cfg)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                rc = main([
                    "--config", str(cfg), "--no-avatar", "--no-color",
                    "repo", "octocat/Hello-World",
                ])
            self.assertEqual(rc, 0)
            out = stdout.getvalue()
            self.assertIn("octocat/Hello-World", out)
            self.assertIn("MIT", out)
            self.assertIn("Python", out)
            self.assertIn("alice", out)
            self.assertIn("first commit", out)

    def test_repo_subcommand_json_format(self, mock_client_cls: mock.Mock) -> None:
        instance = mock_client_cls.return_value
        instance.get_repo.return_value = {
            "full_name": "octocat/Hello-World",
            "description": "First repo",
            "default_branch": "master",
            "stargazers_count": 100,
            "forks_count": 50,
            "watchers_count": 25,
            "open_issues_count": 3,
            "size": 12,
            "owner": {"avatar_url": None},
        }
        instance.get_repo_languages.return_value = {"Python": 1000}
        instance.get_repo_contributors.return_value = []
        instance.get_repo_commits.return_value = []

        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "config.toml"
            _write_minimal_config(cfg)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                rc = main([
                    "--config", str(cfg), "--no-avatar", "--format", "json",
                    "repo", "octocat/Hello-World",
                ])
            self.assertEqual(rc, 0)
            out = stdout.getvalue()
            self.assertIn('"type": "repository"', out)
            self.assertIn('"languages"', out)

    def test_org_subcommand_renders(self, mock_client_cls: mock.Mock) -> None:
        instance = mock_client_cls.return_value
        instance.get_org.return_value = {
            "login": "github",
            "name": "GitHub",
            "description": "How people build software",
            "public_repos": 100,
            "followers": 1000,
            "avatar_url": None,
        }
        instance.get_org_members.return_value = [{"login": "alice"}, {"login": "bob"}]
        instance.get_org_repos.return_value = [
            {"name": "spec", "language": "Python", "stargazers_count": 500},
            {"name": "docs", "language": "TypeScript", "stargazers_count": 200},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "config.toml"
            _write_minimal_config(cfg)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                rc = main([
                    "--config", str(cfg), "--no-avatar", "--no-color",
                    "org", "github",
                ])
            self.assertEqual(rc, 0)
            out = stdout.getvalue()
            self.assertIn("@github", out)
            self.assertIn("spec", out)
            self.assertIn("alice", out)
            self.assertIn("total stars: 700", out)

    def test_compare_subcommand_renders_two_users(self, mock_client_cls: mock.Mock) -> None:
        instance = mock_client_cls.return_value

        def fake_context(username, mode, repo_filters):
            ctx = mock.Mock()
            ctx.user = {
                "login": username,
                "name": username.title(),
                "created_at": "2010-01-01T00:00:00Z",
                "public_repos": 5,
                "public_gists": 0,
                "followers": 10,
                "following": 0,
                "updated_at": "2024-01-01T00:00:00Z",
                "avatar_url": None,
            }
            ctx.repos = []
            ctx.events = []
            ctx.viewer_mode = False
            ctx.authenticated_login = None
            ctx.graphql = {}
            return ctx

        instance.get_context.side_effect = fake_context

        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "config.toml"
            _write_minimal_config(cfg)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                rc = main([
                    "--config", str(cfg), "--no-avatar", "--no-color",
                    "compare", "alice", "bob", "--column-width", "40",
                ])
            self.assertEqual(rc, 0)
            out = stdout.getvalue()
            self.assertIn("@alice", out)
            self.assertIn("@bob", out)
