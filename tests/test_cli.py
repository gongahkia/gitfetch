import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests

from gitfetch.cli import main


def _fake_client() -> mock.Mock:
    client = mock.Mock()
    client.token = ""
    client.provider_name = "github"
    client.provider_title = "GitHub"
    client.supports_module.return_value = True
    client.module_token_required.side_effect = lambda _name, default: default
    client.unsupported_reason.return_value = "unsupported"
    return client


class CLITests(unittest.TestCase):
    def test_config_init_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.toml"
            init_stdout = io.StringIO()
            with contextlib.redirect_stdout(init_stdout):
                self.assertEqual(main(["--config", str(path), "config", "init", "--preset", "minimal"]), 0)
            self.assertTrue(path.exists())

            validate_stdout = io.StringIO()
            with contextlib.redirect_stdout(validate_stdout):
                self.assertEqual(main(["--config", str(path), "config", "validate"]), 0)
            self.assertIn("valid:", validate_stdout.getvalue())

    def test_modules_list(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(main(["modules", "list"]), 0)
        self.assertIn("identity", stdout.getvalue())

    @mock.patch("gitfetch.cli.render_output", return_value="ok")
    @mock.patch("gitfetch.cli.build_module_list", return_value=[])
    @mock.patch("gitfetch.cli.create_provider_client")
    def test_render_command_with_config(
        self,
        mock_client_factory,
        _mock_module_list,
        _mock_render,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.toml"
            self.assertEqual(main(["--config", str(path), "config", "init", "--preset", "minimal"]), 0)
            content = path.read_text(encoding="utf-8").replace('username = ""', 'username = "octocat"')
            path.write_text(content, encoding="utf-8")
            client = _fake_client()
            client.get_context.return_value = mock.Mock(user={"login": "octocat"})
            mock_client_factory.return_value = client
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(main(["--config", str(path), "--format", "plain"]), 0)
            self.assertIn("ok", stdout.getvalue())

    @mock.patch("gitfetch.cli.create_provider_client")
    def test_named_profile_can_drive_render(self, mock_client_factory) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.toml"
            self.assertEqual(main(["--config", str(path), "config", "init", "--preset", "minimal"]), 0)
            self.assertEqual(
                main([
                    "--config", str(path),
                    "config", "profiles", "set", "work",
                    "--user", "octocat",
                ]),
                0,
            )
            client = _fake_client()
            client.get_context.return_value = mock.Mock(
                user={
                    "login": "octocat",
                    "created_at": "2010-01-01T00:00:00Z",
                    "public_repos": 0,
                    "public_gists": 0,
                    "followers": 0,
                    "following": 0,
                    "updated_at": "2024-01-01T00:00:00Z",
                    "avatar_url": None,
                },
                repos=[],
                events=[],
                viewer_mode=False,
                graphql={},
            )
            mock_client_factory.return_value = client
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(main(["--config", str(path), "--profile", "work", "--no-avatar", "--no-color"]), 0)
            client.get_context.assert_called_with(
                username="octocat",
                mode="public",
                repo_filters=mock.ANY,
            )

    @mock.patch("gitfetch.cli.create_provider_client")
    def test_token_required_module_shows_actionable_message(self, mock_client_factory) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.toml"
            self.assertEqual(main(["--config", str(path), "config", "init", "--preset", "compact"]), 0)
            content = path.read_text(encoding="utf-8").replace('username = ""', 'username = "octocat"')
            path.write_text(content, encoding="utf-8")
            client = _fake_client()
            client.get_context.return_value = mock.Mock(
                user={
                    "login": "octocat",
                    "created_at": "2010-01-01T00:00:00Z",
                    "public_repos": 0,
                    "public_gists": 0,
                    "followers": 0,
                    "following": 0,
                    "updated_at": "2024-01-01T00:00:00Z",
                    "avatar_url": None,
                },
                repos=[],
                events=[],
                viewer_mode=False,
                graphql={},
            )
            mock_client_factory.return_value = client
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(main(["--config", str(path), "--no-avatar", "--no-color", "--format", "plain"]), 0)
            self.assertIn("requires --token", stdout.getvalue())

    @mock.patch("gitfetch.cli.create_provider_client")
    def test_network_failure_is_reported_without_a_traceback(self, mock_client_factory) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.toml"
            self.assertEqual(main(["--config", str(path), "config", "init", "--preset", "minimal"]), 0)
            path.write_text(path.read_text(encoding="utf-8").replace('username = ""', 'username = "octocat"'), encoding="utf-8")
            client = _fake_client()
            client.get_context.side_effect = requests.ConnectionError("connection refused")
            mock_client_factory.return_value = client
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(main(["--config", str(path), "--no-avatar", "--no-color"]), 1)
            self.assertIn("network error: connection refused", stderr.getvalue())

    @mock.patch("gitfetch.cli.create_provider_client")
    def test_provider_override_reaches_factory(self, mock_client_factory) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.toml"
            self.assertEqual(main(["--config", str(path), "config", "init", "--preset", "minimal"]), 0)
            content = path.read_text(encoding="utf-8").replace('username = ""', 'username = "gitlab-org"')
            path.write_text(content, encoding="utf-8")
            client = _fake_client()
            client.provider_name = "gitlab"
            client.provider_title = "GitLab"
            client.get_context.return_value = mock.Mock(
                user={
                    "login": "gitlab-org",
                    "created_at": "2010-01-01T00:00:00Z",
                    "public_repos": 0,
                    "public_gists": 0,
                    "followers": 0,
                    "following": 0,
                    "updated_at": "2024-01-01T00:00:00Z",
                    "avatar_url": None,
                },
                repos=[],
                events=[],
                viewer_mode=False,
                graphql={},
            )
            mock_client_factory.return_value = client
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(main(["--config", str(path), "--provider", "gitlab", "--no-avatar", "--format", "plain"]), 0)
            config_arg = mock_client_factory.call_args.args[0]
            self.assertEqual(config_arg["profile"]["provider"], "gitlab")
