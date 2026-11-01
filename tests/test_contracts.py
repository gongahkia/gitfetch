"""Offline public-contract fixtures; intentionally do not assert disputed metrics."""

import contextlib
import copy
import io
import json
import os
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

from PIL import Image

from gitfetch.cache import CacheStore
from gitfetch.cli import main, run_watch_loop
from gitfetch.config import (
    SUPPORTED_PROVIDERS,
    apply_named_profile,
    load_config,
    normalize_config,
    preset_config,
    set_override,
    write_config,
)
from gitfetch.github_api import GitHubAPIError, GitHubContext
from gitfetch.modules import build_module_list, load_plugin_modules
from gitfetch.modules.builtin import ModuleResult
from gitfetch.providers import create_provider_client
from gitfetch.render import _render_ascii, colorize, combine_split, render_output
from gitfetch.terminal_text import cell_width, sanitize_text


def profile_context(username="alice"):
    return GitHubContext(
        target_user=username,
        user={
            "login": username, "name": "Example Developer", "bio": "Builds useful things",
            "avatar_url": None, "public_repos": 2, "followers": 7, "following": 3,
        },
        repos=[{
            "name": "project", "full_name": f"{username}/project", "language": "Python",
            "languages_url": "https://example.test/languages", "stargazers_count": 11,
            "forks_count": 2, "private": False,
        }],
        events=[], viewer_mode=False, authenticated_login=None, graphql={},
    )


def repository():
    return {
        "name": "project", "full_name": "alice/project", "description": "Example repository",
        "homepage": "https://example.test", "default_branch": "main",
        "stargazers_count": 11, "forks_count": 2, "watchers_count": 3,
        "open_issues_count": 1, "size": 42, "language": "Python",
        "owner": {"login": "alice", "avatar_url": None}, "license": {"spdx_id": "MIT"},
    }


class _ContractFixtures(unittest.TestCase):
    def setUp(self):
        self.directory = self.enterContext(tempfile.TemporaryDirectory())
        self.path = Path(self.directory) / "config.toml"
        self.enterContext(mock.patch("pathlib.Path.home", return_value=Path(self.directory)))
        self.enterContext(mock.patch.dict(os.environ, {}, clear=True))
        self.enterContext(mock.patch("gitfetch.config.get_token", return_value=""))
        self.enterContext(mock.patch("gitfetch.cli.get_token", return_value=""))
        self.enterContext(mock.patch("gitfetch.modes.get_token", return_value=""))
        self.enterContext(mock.patch("requests.Session.request", side_effect=AssertionError("unexpected network")))
        self.enterContext(mock.patch("gitfetch.images.urlopen", side_effect=AssertionError("unexpected avatar")))
        self.config = preset_config("minimal")
        self.config["profile"]["username"] = "alice"
        # Identity and stats avoid encoding known language-normalization bugs as contracts.
        self.config["modules"]["languages"]["enabled"] = False
        self.config["cache"]["enabled"] = False
        write_config(self.path, self.config)

    # TestCase.enterContext was introduced in Python 3.11.
    def enterContext(self, manager):
        value = manager.__enter__()
        self.addCleanup(manager.__exit__, None, None, None)
        return value

    def run_cli(self, arguments, client, output_format="json"):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            mock.patch("gitfetch.cli.create_provider_client", return_value=client) as profile_factory,
            mock.patch("gitfetch.modes.create_provider_client", return_value=client) as mode_factory,
            contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr),
        ):
            code = main(["--config", str(self.path), "--format", output_format, *arguments])
        self.assertEqual((code, stderr.getvalue()), (0, ""))
        factory = profile_factory if profile_factory.called else mode_factory
        self.assertEqual(factory.call_args.args[0]["profile"]["provider"], client.provider_name)
        return json.loads(stdout.getvalue()) if output_format == "json" else stdout.getvalue()

    def client(self, provider="github"):
        config = copy.deepcopy(self.config)
        config["profile"]["provider"] = provider
        config["providers"]["forgejo"]["base_url"] = "https://forgejo.example.test/api/v1"
        client = create_provider_client(
            config, "", CacheStore(Path(self.directory), enabled=False, ttl_seconds=0),
        )
        client.get_context = mock.Mock(side_effect=lambda username, **_: profile_context(username))
        repo = repository()
        if provider == "bitbucket":
            for key in ("stargazers_count", "forks_count", "watchers_count", "open_issues_count"):
                repo[key] = None
        client.get_repo = mock.Mock(side_effect=lambda *_: copy.deepcopy(repo))
        languages = {"Python": 80.5, "Shell": 19.5} if provider == "gitlab" else {"Python": 120, "Shell": 30}
        if provider == "bitbucket":
            languages = {"Python": 1}
        client.get_repo_languages = mock.Mock(return_value=languages)
        client.get_repo_contributors = mock.Mock(return_value=[{"login": "alice", "contributions": 5}])
        client.get_repo_commits = mock.Mock(return_value=[{
            "sha": "abcdef123", "commit": {"message": "Initial commit", "author": {"name": "Alice"}},
        }])
        client.get_org = mock.Mock(return_value={
            "login": "team", "name": "Example Team", "description": "Makes things",
            "public_repos": 2, "followers": 8, "avatar_url": None,
        })
        client.get_org_members = mock.Mock(return_value=[{"login": "alice"}])
        client.get_org_repos = mock.Mock(side_effect=lambda *_: [repository()])
        return client


class PublicContractTests(_ContractFixtures):
    def test_configured_profile_and_explicit_user_share_the_contract(self):
        client = self.client()
        configured = self.run_cli([], client)
        explicit = self.run_cli(["--user", "alice"], client)
        self.assertEqual(configured, explicit)
        self.assertEqual(set(configured), {"user", "modules"})
        self.assertIsInstance(configured["user"], str)
        self.assertEqual(list(configured["modules"]), ["identity", "stats"])
        self.assertIsInstance(configured["modules"]["identity"]["user"], dict)
        self.assertIsInstance(configured["modules"]["stats"]["viewer_mode"], bool)

    def test_user_override_does_not_rewrite_saved_target(self):
        client = self.client()
        result = self.run_cli(["--user", "bob"], client)
        self.assertEqual(result["user"], "bob")
        self.assertEqual(load_config(self.path)["profile"]["username"], "alice")

    def test_each_provider_profile_envelope_and_plain_render(self):
        for provider in SUPPORTED_PROVIDERS:
            with self.subTest(provider=provider):
                client = self.client(provider)
                arguments = ["--provider", provider, "--base-url", client.base_url]
                result = self.run_cli(arguments, client)
                self.assertEqual(set(result), {"user", "modules"})
                self.assertEqual(result["user"], "alice")
                user = result["modules"]["identity"]["user"]
                self.assertEqual(user["name"], "Example Developer")
                self.assertIsInstance(user["followers"], int)
                self.assertIsInstance(result["modules"]["stats"]["viewer_mode"], bool)
                rendered = self.run_cli(arguments, client, "plain")
                self.assertIn("Identity\n--------\n@alice\nExample Developer", rendered)
                self.assertNotIn("\x1b", rendered)

    def test_repository_envelope_for_each_provider(self):
        for provider in SUPPORTED_PROVIDERS:
            with self.subTest(provider=provider):
                client = self.client(provider)
                result = self.run_cli([
                    "--provider", provider, "--base-url", client.base_url, "repo", "alice/project",
                ], client)
                self.assertEqual(set(result), {"type", "title", "subtitle", "target", "provider", "modules"})
                self.assertEqual((result["type"], result["provider"]), ("repository", provider))
                self.assertEqual(result["target"], "alice/project")
                self.assertIsInstance(result["title"], str)
                self.assertIsInstance(result["subtitle"], str)
                modules = result["modules"]
                self.assertIsInstance(modules["identity"], dict)
                if provider == "bitbucket":
                    self.assertIsNone(modules["stats"]["stargazers_count"])
                else:
                    self.assertIsInstance(modules["stats"]["stargazers_count"], int)
                self.assertIsInstance(modules["languages"], dict)
                self.assertEqual(modules["languages"], client.get_repo_languages.return_value)
                self.assertTrue(all(isinstance(n, (int, float)) for n in modules["languages"].values()))
                self.assertIsInstance(modules["contributors"], list)
                self.assertIsInstance(modules["recent_commits"][0]["commit"]["message"], str)

    def test_organization_envelope_for_each_provider(self):
        for provider in SUPPORTED_PROVIDERS:
            with self.subTest(provider=provider):
                client = self.client(provider)
                result = self.run_cli([
                    "--provider", provider, "--base-url", client.base_url, "org", "team",
                ], client)
                self.assertEqual(set(result), {"type", "title", "subtitle", "target", "provider", "modules"})
                self.assertEqual((result["type"], result["provider"]), ("organization", provider))
                self.assertEqual(result["target"], "team")
                modules = result["modules"]
                self.assertEqual(modules["identity"]["login"], "team")
                self.assertIsInstance(modules["stats"]["public_repos"], int)
                self.assertIsInstance(modules["top_repos"], list)
                self.assertIsInstance(modules["members"][0]["login"], str)

    def test_comparison_envelope_for_each_provider(self):
        for provider in SUPPORTED_PROVIDERS:
            with self.subTest(provider=provider):
                client = self.client(provider)
                result = self.run_cli([
                    "--provider", provider, "--base-url", client.base_url, "compare", "alice", "bob",
                ], client)
                self.assertEqual(set(result), {"type", "provider", "users", "summary", "modules"})
                self.assertEqual(result["type"], "compare")
                self.assertEqual(result["users"], ["alice", "bob"])
                self.assertEqual(set(result["modules"]), {"alice", "bob"})
                self.assertIsInstance(result["summary"]["language_overlap"], list)
                self.assertIsInstance(result["summary"]["metrics"], list)
                self.assertEqual([m["login"] for m in result["summary"]["metrics"]], ["alice", "bob"])
                for user in result["users"]:
                    self.assertEqual(result["modules"][user]["identity"]["user"]["login"], user)

    def test_mode_plain_output_still_contains_selected_content(self):
        client = self.client()
        for arguments, expected in (
            (["repo", "alice/project"], ("Repository", "alice/project", "Initial commit")),
            (["org", "team"], ("Organization", "@team", "Members")),
            (["compare", "alice", "bob"], ("Compare Summary", "@alice", "@bob")),
        ):
            with self.subTest(arguments=arguments):
                output = self.run_cli(arguments, client, "plain")
                for value in expected:
                    self.assertIn(value, output)

    def test_selection_order_and_explicit_exclusions(self):
        client = self.client()
        arguments = ["--set", 'modules.order=["stats","identity"]']
        result = self.run_cli(arguments, client)
        self.assertEqual(list(result["modules"]), ["stats", "identity"])
        result = self.run_cli([*arguments, "--set", "modules.identity.enabled=false"], client)
        self.assertEqual(list(result["modules"]), ["stats"])
        plain = self.run_cli(arguments, client, "plain")
        self.assertLess(plain.index("Stats\n"), plain.index("Identity\n"))

    def test_unavailable_and_unsupported_module_shapes(self):
        arguments = ["--set", "modules.contributions.enabled=true"]
        result = self.run_cli(arguments, self.client())
        self.assertEqual(result["modules"]["contributions"], {"requires_token": True})
        client = self.client("gitlab")
        result = self.run_cli(["--provider", "gitlab", *arguments], client)
        unavailable = result["modules"]["contributions"]
        self.assertIs(unavailable["unsupported"], True)
        self.assertEqual(unavailable["provider"], "gitlab")
        self.assertIsInstance(unavailable["reason"], str)

    def test_line_only_legacy_plugin_and_raw_json(self):
        path = Path(self.directory) / "plugin.py"
        path.write_text("MODULES = {'legacy': lambda config, context, client: ['first', 'second']}\n")
        self.config["plugins"] = {"paths": [str(path)], "modules": ["legacy"], "allow_unsafe": True}
        write_config(self.path, self.config)
        self.addCleanup(load_plugin_modules, {"plugins": {}})
        client = self.client()
        result = self.run_cli([], client)
        self.assertEqual(result["modules"]["legacy"], ["first", "second"])
        self.assertIn("Legacy\n------\nfirst\nsecond", self.run_cli([], client, "plain"))

    def test_presets_round_trip_and_keep_composition(self):
        expected = {
            "minimal": (False, "split"), "compact": (True, "stack"),
            "full": (True, "split"), "showcase": (True, "split"),
        }
        for name, (avatar, layout) in expected.items():
            with self.subTest(preset=name):
                config = preset_config(name)
                normalize_config(config)
                self.assertEqual((config["display"]["avatar"], config["display"]["layout"]), (avatar, layout))
                selected = build_module_list(config)
                self.assertEqual(selected[0:2], ["identity", "stats"])
                write_config(self.path, config)
                self.assertEqual(load_config(self.path), config)
        self.assertIn("showcase", build_module_list(preset_config("showcase")))
        self.assertNotIn("contributions", build_module_list(preset_config("minimal")))
        self.assertIn("recent_activity", build_module_list(preset_config("full")))

    def test_named_profile_and_override_precedence(self):
        config = preset_config("minimal")
        config["profile"]["username"] = "saved"
        config["profiles"] = {"work": {"username": "work-user", "provider": "gitlab"}}
        apply_named_profile(config, "work")
        set_override(config, "profile.username", "override")
        set_override(config, "display.layout", "stack")
        set_override(config, "modules.stats.enabled", "false")
        normalize_config(config)
        self.assertEqual(config["profile"]["username"], "override")
        self.assertEqual(config["profile"]["provider"], "gitlab")
        self.assertEqual(config["display"]["layout"], "stack")
        self.assertNotIn("stats", build_module_list(config))
        self.config["profiles"] = {"work": {"username": "work-user"}}
        write_config(self.path, self.config)
        result = self.run_cli([
            "--profile", "work", "--set", "profile.username=override", "--user", "explicit",
        ], self.client())
        self.assertEqual(result["user"], "explicit")

    def test_authenticated_other_user_does_not_become_the_viewer(self):
        for provider in SUPPORTED_PROVIDERS:
            with self.subTest(provider=provider):
                config = copy.deepcopy(self.config)
                config["profile"]["provider"] = provider
                config["providers"]["forgejo"]["base_url"] = "https://forgejo.example.test/api/v1"
                client = create_provider_client(
                    config, "synthetic-token", CacheStore(Path(self.directory), False, 0),
                )
                target = profile_context().user
                client.get_user = mock.Mock(return_value=copy.deepcopy(target))
                client.get_repos = mock.Mock(return_value=profile_context().repos)
                client.get_events = mock.Mock(return_value=[])
                client.get_authenticated_user = mock.Mock(return_value={"login": "owner", "name": "Private Viewer"})
                if provider == "gitlab":
                    client._resolve_user = mock.Mock(return_value={"id": 42, "username": "alice", "name": "Target"})
                context = client.get_context("alice", "viewer", config["repo_filters"], include_graphql=False)
                self.assertEqual(context.user["login"], "alice")
                self.assertFalse(context.viewer_mode)
                client.get_repos.assert_called_once_with("alice", viewer_mode=False)
                # Exercise the CLI with that real adapter result as well.
                client.get_context = mock.Mock(return_value=context)
                self.config["profile"]["mode"] = "viewer"
                write_config(self.path, self.config)
                result = self.run_cli([
                    "--provider", provider, "--base-url", client.base_url, "--user", "alice",
                ], client)
                self.assertEqual(result["user"], "alice")
                self.assertFalse(result["modules"]["stats"]["viewer_mode"])


class DisplaySafetyTests(_ContractFixtures):
    payload = "\x1b[2J\x1b]0;owned\x07漢字 e\u0301👩🏽\u200d💻\r\nname\t\x1b]8;;https://evil.test\x1b\\label\x1b]8;;\x1b\\"

    def assert_safe_lines(self, text, ansi=False):
        plain = re.sub(r"\x1b\[[0-9;]*m", "", text) if ansi else text
        self.assertIsNone(re.search(r"[\x00-\x09\x0b-\x1f\x7f-\x9f]", plain))
        self.assertNotIn("owned", plain)
        self.assertNotIn("evil.test", plain)

    def test_all_identity_fields_are_safe_and_json_remains_raw(self):
        client = self.client()
        context = profile_context()
        for field in ("login", "name", "bio", "company", "location", "blog"):
            context.user[field] = self.payload
        original = copy.deepcopy(context)
        client.get_context.return_value = context
        client.get_context.side_effect = None
        plain = self.run_cli(["--color"], client, "plain")
        self.assert_safe_lines(plain)
        self.assertIn(sanitize_text(self.payload), plain)
        ansi = self.run_cli(["--color"], client, "ansi")
        self.assert_safe_lines(ansi, ansi=True)
        self.assertIn("\x1b[92mIdentity", ansi)
        result = self.run_cli([], client)
        self.assertEqual(result["user"], self.payload)
        self.assertEqual(result["modules"]["identity"]["user"], original.user)
        self.assertEqual(context, original)

    def test_profile_unicode_and_long_biography_are_not_truncated(self):
        client = self.client()
        context = profile_context("漢字")
        context.user["bio"] = "Builds cafe\u0301 tools 👩🏽\u200d💻. " * 100
        client.get_context.side_effect = None
        client.get_context.return_value = context
        plain = self.run_cli([], client, "plain")
        self.assertIn("@漢字", plain)
        self.assertIn(context.user["bio"], plain)

    def test_plain_output_with_colors_disabled(self):
        client = self.client()
        self.assertNotIn("\x1b", self.run_cli(["--no-color"], client, "plain"))
        self.assertNotIn("\x1b", self.run_cli(["--no-color"], client, "ansi"))

    def test_repo_metadata_contributors_and_commit_messages_are_safe(self):
        client = self.client()
        repo = repository()
        for key in ("full_name", "description", "homepage", "default_branch"):
            repo[key] = self.payload
        client.get_repo.side_effect = None
        client.get_repo.return_value = repo
        client.get_repo_contributors.return_value = [{"login": self.payload, "contributions": 5}]
        message = "\x1b[2J\x1b]0;owned\x07commit"
        client.get_repo_commits.return_value = [{
            "sha": "abcdef", "commit": {"message": message, "author": {"name": self.payload}},
        }]
        for output_format in ("plain", "ansi"):
            output = self.run_cli(["--color", "repo", "alice/project"], client, output_format)
            self.assert_safe_lines(output, ansi=output_format == "ansi")
        result = self.run_cli(["repo", "alice/project"], client)
        self.assertEqual(result["title"], self.payload)
        self.assertEqual(result["modules"]["identity"]["description"], self.payload)
        self.assertEqual(result["modules"]["recent_commits"][0]["commit"]["message"], message)

    def test_organization_metadata_and_member_names_are_safe(self):
        client = self.client()
        org = client.get_org.return_value
        for key in ("login", "name", "description", "blog", "location", "email"):
            org[key] = self.payload
        client.get_org_members.return_value = [{"login": self.payload}]
        repo = repository()
        repo["name"] = self.payload
        client.get_org_repos.side_effect = None
        client.get_org_repos.return_value = [repo]
        self.assert_safe_lines(self.run_cli(["org", "team"], client, "plain"))
        result = self.run_cli(["org", "team"], client)
        self.assertEqual(result["modules"]["identity"]["description"], self.payload)
        self.assertEqual(result["modules"]["members"][0]["login"], self.payload)

    def test_comparison_names_and_summaries_are_safe(self):
        client = self.client()
        client.get_context.side_effect = lambda username, **_: profile_context(self.payload + username)
        output = self.run_cli(["--color", "compare", "alice", "bob"], client, "ansi")
        self.assert_safe_lines(output, ansi=True)
        result = self.run_cli(["compare", "alice", "bob"], client)
        self.assertEqual(result["summary"]["metrics"][0]["login"], self.payload + "alice")

    def test_line_only_plugin_is_untrusted_even_when_it_contains_sgr(self):
        path = Path(self.directory) / "plugin.py"
        payload = "\x1b[31m" + self.payload + "\x1b[0m"
        path.write_text(f"MODULES = {{'legacy': lambda config, context, client: [{payload!r}]}}\n")
        self.config["plugins"] = {"paths": [str(path)], "modules": ["legacy"], "allow_unsafe": True}
        write_config(self.path, self.config)
        self.addCleanup(load_plugin_modules, {"plugins": {}})
        client = self.client()
        self.assert_safe_lines(self.run_cli([], client, "plain"))
        output = self.run_cli(["--color"], client, "ansi")
        self.assert_safe_lines(output, ansi=True)
        self.assertNotIn("\x1b[31m", output)
        self.assertEqual(self.run_cli([], client)["modules"]["legacy"], [payload])

    def test_module_titles_and_missing_lines_are_safe(self):
        result = ModuleResult("custom", self.payload, [self.payload, None, ""], {"raw": self.payload})
        original = copy.deepcopy(result)
        rendered = render_output(self.config, {"login": "alice"}, [result], "plain")
        self.assert_safe_lines(rendered)
        self.assertIn("-" * cell_width(self.payload), rendered)
        self.assertEqual(result, original)

    def test_ascii_output_appearance_is_unchanged(self):
        module = ModuleResult("identity", "Identity", ["@alice", "Example Developer", "company: Example"], {})
        self.assertEqual(
            render_output(self.config, {}, [module], "plain"),
            "Identity\n--------\n@alice\nExample Developer\ncompany: Example",
        )

    def test_only_renderer_color_survives(self):
        self.assertEqual(colorize("\x1b[31mred\x1b[0m", 92, True), "\x1b[92mred\x1b[00m")
        self.assertEqual(colorize(self.payload, 92, False), sanitize_text(self.payload))

    def test_cjk_alignment_uses_cells(self):
        self.assertEqual(combine_split(["漢", "ab"], ["x", "y"]), "漢   x\nab   y")
        module = ModuleResult("custom", "漢字", [], {})
        self.assertEqual(render_output(self.config, {}, [module], "plain"), "漢字\n----")

    def test_avatar_ramp_cannot_inject_controls_or_break_cell_width(self):
        image = Image.new("RGB", (2, 2), "white")
        for ramp in ("\x1b[2J.\r", "", "漢", "e\u0301"):
            with self.subTest(ramp=ramp):
                lines = _render_ascii(image, 4, 1, "none", ramp)
                self.assertTrue(all(cell_width(line) == 4 for line in lines))
                self.assert_safe_lines("\n".join(lines))

    def test_hidden_modules_remain_excluded_from_json(self):
        hidden = ModuleResult("hidden", "Hidden", [self.payload], {"raw": self.payload}, hidden=True)
        output = render_output(self.config, {"login": self.payload}, [hidden], "json")
        self.assertNotIn("\x1b", output)
        self.assertEqual(json.loads(output), {"user": self.payload, "modules": {}})

    def test_svg_escaping_is_preserved_and_controls_are_removed(self):
        payload = self.payload + '<tag attr="x">&value</tag>'
        module = ModuleResult("pinned", payload, [payload], [])
        user = {"login": payload, "name": payload, "bio": payload, "public_repos": '<tag>"&'}
        from gitfetch.formats import render_summary_card_svg

        for rendered in (
            render_output(self.config, user, [module], "svg"),
            render_output(self.config, user, [module], "card"),
            render_summary_card_svg(self.config, payload, payload, [module]),
        ):
            with self.subTest(rendered=rendered[:80]):
                root = ET.fromstring(rendered)
                self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
                self.assertFalse(any(element.tag == "tag" for element in root.iter()))
                self.assert_safe_lines(rendered)
        terminal = render_output(self.config, user, [module], "svg")
        self.assertIn("&lt;tag", terminal)
        self.assertIn("&amp;value", terminal)

    def test_png_text_boundaries_are_safe_without_redesign(self):
        from gitfetch.formats import render_card_png, render_summary_card_png

        module = ModuleResult("pinned", self.payload, [self.payload], [])
        user = {"login": self.payload, "name": self.payload, "bio": self.payload, "followers": self.payload}
        with mock.patch("gitfetch.formats.ImageDraw.Draw") as draw:
            path = Path(self.directory) / "card.png"
            render_card_png(self.config, user, [module], path)
            render_summary_card_png(self.config, self.payload, self.payload, [module], None, path)
        self.assertTrue(path.exists())
        for call in draw.return_value.text.call_args_list:
            self.assert_safe_lines(call.args[1])

    def test_provider_error_messages_cannot_inject_terminal_commands(self):
        client = self.client()
        client.get_context.side_effect = GitHubAPIError(self.payload)
        with mock.patch("gitfetch.cli.create_provider_client", return_value=client):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = main(["--config", str(self.path)])
        self.assertEqual(code, 1)
        self.assert_safe_lines(stderr.getvalue())

    def test_watch_never_adds_screen_controls_to_plain_json_or_pipes(self):
        client = self.client()
        for output_format in ("plain", "json", "ansi"):
            with self.subTest(output_format=output_format):
                with mock.patch("gitfetch.cli.run_watch_loop", side_effect=lambda render, *_args, **_kwargs: render()) as loop:
                    self.run_cli(["--watch", "1"], client, output_format)
                self.assertIs(loop.call_args.kwargs["clear_screen"], False)

    def test_watch_loop_without_screen_clearing_is_plain(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), mock.patch("time.sleep", side_effect=KeyboardInterrupt):
            run_watch_loop(lambda: print("snapshot"), 1, clear_screen=False)
        self.assertEqual(stdout.getvalue(), "snapshot\n")
