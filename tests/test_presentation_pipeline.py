"""Profile pipeline invariants and classic/export compatibility."""
import contextlib
import copy
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from xml.etree import ElementTree

from PIL import Image

from gitfetch.cli import main
from gitfetch.config import preset_config, write_config
from gitfetch.github_api import GitHubClient, GitHubContext
from gitfetch.modules.builtin import MODULE_HANDLERS, ModuleResult
from gitfetch.presentation import build_profile_document
from gitfetch.render import module_lines, palette_for, render_output
from gitfetch.semantics import Measurement


class PresentationPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "config.toml"
        self.user = {"login": "alice", "name": "Alice", "bio": "Builds things", "avatar_url": None,
                     "followers": 0, "following": None, "public_repos": 2, "public_gists": 0}
        self.context = GitHubContext("alice", self.user, [], [], False, None, {})
        self.client = mock.Mock(spec=GitHubClient)
        self.client.provider_name = "github"
        self.client.provider_title = "GitHub"
        self.client.token = ""
        self.client.supports_module.return_value = True
        self.client.module_token_required.side_effect = lambda name, default: default
        self.client.get_context.side_effect = lambda **kwargs: copy.deepcopy(self.context)
        self.client.get_languages.return_value = {"Python": 80, "Go": 20}
        for manager in (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch("pathlib.Path.home", return_value=self.root),
            mock.patch("gitfetch.cli.get_token", return_value=""),
            mock.patch("gitfetch.cli.create_provider_client", return_value=self.client),
            mock.patch("requests.Session.request", side_effect=AssertionError("unexpected network")),
            mock.patch("gitfetch.images.urlopen", side_effect=AssertionError("unexpected avatar download")),
        ):
            manager.start()
            self.addCleanup(manager.stop)
        self.config = preset_config("minimal")
        self.config["profile"]["username"] = "alice"
        self.config["cache"]["enabled"] = False
        self.select("identity", "stats")

    def select(self, *names):
        for value in self.config["modules"].values():
            if isinstance(value, dict) and "enabled" in value:
                value["enabled"] = False
        self.config["modules"]["order"] = list(names)
        for name in names:
            self.config["modules"].setdefault(name, {})["enabled"] = True

    def run_cli(self, *args, output_format="plain"):
        write_config(self.path, self.config)
        documents = []
        def build(*positional, **keywords):
            document = build_profile_document(*positional, **keywords)
            documents.append(document)
            return document
        stdout, stderr = io.StringIO(), io.StringIO()
        with (mock.patch("gitfetch.cli.build_profile_document", side_effect=build) as builder,
              mock.patch("gitfetch.render.build_profile_document", side_effect=AssertionError("document built twice")),
              contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr)):
            code = main(["--config", str(self.path), "--format", output_format, *args])
        self.assertEqual((code, stderr.getvalue()), (0, ""))
        self.assertEqual(builder.call_count, len(documents))
        return stdout.getvalue(), documents

    def test_configured_and_explicit_user_workflows_build_once_with_same_output(self):
        configured, first = self.run_cli()
        explicit, second = self.run_cli("--user", "alice")
        self.assertEqual(configured, explicit)
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertEqual(first[0], second[0])
        self.assertEqual(self.client.get_context.call_count, 2)

    def test_explicit_lookup_preserves_target_when_authenticated(self):
        self.config["profile"]["mode"] = "viewer"
        self.client.token = "token"
        self.context.user["login"] = "bob"
        self.context.target_user = "bob"
        self.context.authenticated_login = "alice"
        output, documents = self.run_cli("--user", "bob", output_format="json")
        self.assertEqual(documents[0].username, "bob")
        self.assertFalse(documents[0].viewer_mode)
        self.assertEqual(json.loads(output)["user"], "bob")
        self.client.get_context.assert_called_once_with(username="bob", mode="viewer", repo_filters=self.config["repo_filters"], include_graphql=False)

    def test_provider_and_instance_are_explicit_for_all_six_providers(self):
        for provider in ("github", "gitlab", "bitbucket", "gitea", "forgejo", "codeberg"):
            with self.subTest(provider=provider):
                self.config["profile"]["provider"] = provider
                self.config["providers"][provider]["base_url"] = f"https://{provider}.example/api"
                self.client.provider_name = provider
                self.context.provider = provider
                _, documents = self.run_cli()
                self.assertEqual(documents[0].provider, provider)
                self.assertEqual(documents[0].identity.instance, f"https://{provider}.example/api")

    def test_actual_module_and_plugin_handlers_execute_once(self):
        plugin = self.root / "plugin.py"
        plugin.write_text(
            "from gitfetch.modules.builtin import ModuleResult\n"
            "calls = []\n"
            "def handler(config, context, client):\n"
            "    calls.append(1)\n"
            "    return ModuleResult('plugin', 'Plugin', ['called once'], {'calls': calls})\n"
            "MODULES = {'plugin': handler}\n", encoding="utf-8")
        self.config["plugins"] = {"paths": [str(plugin)], "modules": ["plugin"], "allow_unsafe": True}
        self.select("stats", "plugin", "identity")
        identity, stats = mock.Mock(wraps=MODULE_HANDLERS["identity"]), mock.Mock(wraps=MODULE_HANDLERS["stats"])
        with mock.patch.dict(MODULE_HANDLERS, {"identity": identity, "stats": stats}):
            output, documents = self.run_cli(output_format="json")
        identity.assert_called_once()
        stats.assert_called_once()
        self.assertEqual(json.loads(output)["modules"]["plugin"]["calls"], [1])
        self.assertEqual(next(s for s in documents[0].sections if s.name == "plugin").raw_data["calls"], (1,))
        # Existing configuration normalization appends plugin modules after built-ins.
        self.assertEqual([s.name for s in documents[0].sections], ["stats", "identity", "plugin"])

    def test_line_only_plugin_remains_compatible_and_safe(self):
        plugin = self.root / "plugin.py"
        plugin.write_text("MODULES = {'plugin': lambda config, context, client: ['hello', '\\x1b]0;bad\\a世界']}\n", encoding="utf-8")
        self.config["plugins"] = {"paths": [str(plugin)], "modules": ["plugin"], "allow_unsafe": True}
        self.select("plugin")
        output, documents = self.run_cli()
        self.assertIn("世界", output)
        self.assertNotIn("\x1b", output)
        self.assertEqual(documents[0].sections[0].lines, ("hello", "\x1b]0;bad\a世界"))

    def test_disabled_and_hidden_modules_do_not_reappear(self):
        self.select("stats", "identity")
        self.config["modules"]["identity"]["enabled"] = False
        hidden = ModuleResult("stats", "Stats", ["hidden"], {"metric": None}, hidden=True,
                              measurements={"stats": Measurement(availability="auth_required")})
        with mock.patch.dict(MODULE_HANDLERS, {"stats": mock.Mock(return_value=hidden),
                                             "identity": mock.Mock(side_effect=AssertionError("disabled handler"))}):
            output, documents = self.run_cli(output_format="json")
        self.assertEqual(documents[0].sections, ())
        self.assertEqual(documents[0].notices, ())
        self.assertEqual(json.loads(output)["modules"], {})

    def test_optional_collection_is_not_expanded(self):
        self.select("identity")
        self.context.graphql = {"contributionsCollection": {"contributionCalendar": {"weeks": []}}}
        _, documents = self.run_cli()
        self.client.get_context.assert_called_once_with(username="alice", mode="public", repo_filters=self.config["repo_filters"], include_graphql=False)
        self.client.get_languages.assert_not_called()
        self.assertEqual([s.name for s in documents[0].sections], ["identity"])

    def test_language_request_count_is_unchanged(self):
        self.select("languages")
        self.context.repos = [{"languages_url": "https://example.test/one"}, {"languages_url": "https://example.test/two"}]
        _, documents = self.run_cli()
        self.assertEqual(self.client.get_languages.call_count, 2)
        self.assertEqual(documents[0].sections[0].content.measurement.denominator, 200)
        self.assertEqual(len(documents), 1)
        self.assertFalse(self.client.get_context.call_args.kwargs["include_graphql"])

    def test_selected_token_required_module_retains_notice_without_execution(self):
        self.select("pinned")
        handler = mock.Mock(side_effect=AssertionError("missing token handler executed"))
        with mock.patch.dict(MODULE_HANDLERS, {"pinned": handler}):
            output, documents = self.run_cli()
        handler.assert_not_called()
        self.assertIn("GITHUB_TOKEN", output)
        self.assertEqual(documents[0].notices[0].measurement.availability, "auth_required")

    def test_selected_unsupported_module_retains_notice_without_execution(self):
        self.select("contributions")
        self.client.provider_name = "gitlab"
        self.config["profile"]["provider"] = "gitlab"
        self.client.supports_module.return_value = False
        self.client.unsupported_reason.return_value = "no calendar endpoint"
        _, documents = self.run_cli(output_format="json")
        self.assertIsNone(documents[0].sections[0].content)
        self.assertEqual(documents[0].notices[0].measurement.availability, "unsupported")

    def test_plain_and_ansi_classic_lines_are_preserved(self):
        modules = [ModuleResult("plugin", "Hello 世界", ["name: café", "👩🏽‍💻", "0 stars"], {"value": None})]
        self.config["display"]["avatar"] = False
        self.config["_color_force"] = "on"
        document = build_profile_document(self.user, modules, provider="github")
        for output_format in ("plain", "ansi"):
            expected = "\n".join(module_lines(modules, output_format == "ansi", palette_for(self.config)))
            output = render_output(self.config, self.user, modules, output_format, document=document)
            self.assertEqual(output, expected)

    def test_classic_renderer_consumes_document_not_mutated_module_lines(self):
        module = ModuleResult("plugin", "Original", ["original line"], {"value": None})
        document = build_profile_document(self.user, [module], provider="github")
        module.title = "Changed"
        module.lines[:] = ["changed line"]
        self.config["display"]["avatar"] = False
        visual = render_output(self.config, self.user, [module], "plain", document=document)
        self.assertIn("Original", visual)
        self.assertIn("original line", visual)
        self.assertNotIn("Changed", visual)

    def test_json_keeps_original_envelope_raw_text_and_nullable_values(self):
        self.context.user["bio"] = "raw\x1b[2J biography"
        output, documents = self.run_cli(output_format="json")
        payload = json.loads(output)
        self.assertEqual(set(payload), {"user", "modules"})
        self.assertEqual(payload["modules"]["identity"]["user"]["bio"], "raw\x1b[2J biography")
        self.assertEqual(payload["modules"]["stats"]["user"]["followers"], 0)
        self.assertIsNone(payload["modules"]["stats"]["user"]["following"])
        self.assertNotIn("sections", payload)
        self.assertNotIn("notices", payload)
        self.assertEqual(len(documents), 1)

    def test_json_never_serializes_the_document(self):
        module = ModuleResult("plugin", "Plugin", ["fallback"], {"value": None})
        output = render_output(self.config, self.user, [module], "json", document=object())
        self.assertEqual(json.loads(output), {"user": "alice", "modules": {"plugin": {"value": None}}})

    def test_svg_profile_keeps_classic_text_and_xml_escaping(self):
        self.context.user["name"] = "Alice <&> 世界"
        output, documents = self.run_cli(output_format="svg")
        root = ElementTree.fromstring(output)
        self.assertTrue(root.tag.endswith("svg"))
        self.assertIn("Alice <&> 世界", "".join(root.itertext()))
        self.assertEqual(documents[0].identity.display_name, "Alice <&> 世界")

    def test_card_uses_existing_export_path_with_original_module_objects(self):
        with mock.patch("gitfetch.formats.render_card_svg", return_value="<svg />") as exporter:
            output, documents = self.run_cli(output_format="card")
        self.assertEqual(output, "<svg />\n")
        self.assertEqual(len(documents), 1)
        self.assertIsInstance(exporter.call_args.args[2][0], ModuleResult)
        self.assertEqual(exporter.call_args.args[1]["login"], "alice")

    def test_card_and_png_remain_valid_without_visual_redesign(self):
        svg, documents = self.run_cli(output_format="card")
        self.assertTrue(ElementTree.fromstring(svg).tag.endswith("svg"))
        self.assertEqual(len(documents), 1)
        path = self.root / "profile.png"
        output, documents = self.run_cli("--save", str(path), output_format="png")
        self.assertIn("wrote", output)
        self.assertEqual(len(documents), 1)
        with Image.open(path) as image:
            self.assertEqual(image.format, "PNG")
            self.assertGreater(image.width, 0)

    def test_standalone_render_output_retains_positional_api(self):
        modules = [ModuleResult("plugin", "Plugin", ["ok"], ["ok"])]
        self.config["display"]["avatar"] = False
        output = render_output(self.config, self.user, modules, "plain")
        self.assertEqual(output, "Plugin\n------\nok")

    def test_existing_avatar_layout_and_no_avatar_flag_remain_authoritative(self):
        self.context.user["avatar_url"] = "https://example.test/avatar.png"
        self.config["display"]["avatar"] = True
        self.config["display"]["avatar_width"] = 20
        for layout in ("split", "stack"):
            self.config["display"]["layout"] = layout
            with (mock.patch("gitfetch.render.render_avatar", return_value=["AVATAR"]) as avatar,
                  mock.patch("gitfetch.render.shutil.get_terminal_size", return_value=os.terminal_size((120, 40)))):
                output, _ = self.run_cli()
                self.assertIn("AVATAR", output)
                avatar.assert_called_once()
                self.assertEqual(avatar.call_args.args[0], self.context.user["avatar_url"])
            with mock.patch("gitfetch.render.render_avatar", side_effect=AssertionError("avatar disabled")):
                output, _ = self.run_cli("--no-avatar")
                self.assertNotIn("AVATAR", output)

    def test_watch_builds_once_per_frame_without_repeating_module_evaluation(self):
        self.select("identity")
        handler = mock.Mock(wraps=MODULE_HANDLERS["identity"])
        def watch(render_once, interval, **kwargs):
            render_once()
            render_once()
        with mock.patch("gitfetch.cli.run_watch_loop", side_effect=watch), mock.patch.dict(MODULE_HANDLERS, {"identity": handler}):
            _, documents = self.run_cli("--watch", "1")
        self.assertEqual(len(documents), 2)
        self.assertEqual(handler.call_count, 2)
        self.assertEqual(self.client.get_context.call_count, 2)

    def test_repository_organization_and_comparison_dispatch_are_not_refactored(self):
        for command, args in (("repo", ["alice/project"]), ("org", ["team"]), ("compare", ["alice", "bob"])):
            with mock.patch(f"gitfetch.modes.handle_{command}_command", return_value=0) as handler:
                _, documents = self.run_cli(command, *args)
            handler.assert_called_once()
            self.assertEqual(documents, [])


if __name__ == "__main__":
    unittest.main()
