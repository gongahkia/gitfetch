"""Terminal format integration, compatibility and reviewed visual fixtures."""
import json
import os
import re
import unittest
from pathlib import Path
from unittest import mock

import test_presentation_pipeline as legacy_pipeline
from modern_fixtures import CASES, DIMENSIONS, REFERENCE, avatar_image, fixture, preview

from gitfetch.completions import script_for
from gitfetch.config import ConfigError, normalize_config, preset_config
from gitfetch.layout import AvatarGeometry, Preferences, Viewport, plan_profile
from gitfetch.modules.builtin import MODULE_HANDLERS, ModuleResult
from gitfetch.presentation import build_profile_document
from gitfetch.render import THEMES, modern_enabled, render_output
from gitfetch.terminal_text import cell_width, sanitize_styled_text, sanitize_text


class ModernRenderTests(unittest.TestCase):
    def setUp(self):
        self.user, self.modules, self.document = fixture()
        self.config = preset_config("minimal")
        self.config["display"].update({"presentation": "modern", "avatar": False, "layout": "split"})
        self.config["_color_force"] = "on"
        self.terminal = mock.patch("gitfetch.render.shutil.get_terminal_size", return_value=os.terminal_size((80, 24)))
        self.terminal.start()
        self.addCleanup(self.terminal.stop)
        self.network = mock.patch("requests.Session.request", side_effect=AssertionError("unexpected network"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def render(self, output_format="plain", **kwargs):
        return render_output(self.config, self.user, self.modules, output_format, document=self.document, **kwargs)

    def test_golden_previews(self):
        for name in CASES:
            with self.subTest(name=name):
                expected = (Path(__file__).parent / "fixtures" / "modern" / f"{name}.txt").read_text(encoding="utf-8")
                self.assertEqual(preview(name) + "\n", expected)

    def test_ansi_and_plain_have_identical_visible_text(self):
        for name in CASES:
            with self.subTest(name=name):
                ansi = preview(name, ansi=True)
                self.assertEqual([sanitize_styled_text(line) for line in ansi.splitlines()], ansi.splitlines())
                self.assertEqual(re.sub(r"\x1b\[[0-9;]*m", "", ansi), preview(name))
                for line in ansi.splitlines():
                    sequences = re.findall(r"\x1b\[([0-9;]*)m", line)
                    if sequences:
                        self.assertIn(sequences[-1], ("0", "00"))

    def test_plain_has_no_controls_and_monochrome_has_no_sgr(self):
        self.assertNotIn("\x1b", self.render())
        self.assertNotIn("\x1b", preview("monochrome", ansi=True))

    def test_all_theme_palettes_keep_same_visible_geometry(self):
        expected = preview("no-avatar")
        for theme in THEMES:
            with self.subTest(theme=theme):
                result = preview("no-avatar", ansi=True, theme=theme)
                self.assertEqual(re.sub(r"\x1b\[[0-9;]*m", "", result), expected)

    def test_reduced_palette_does_not_emit_truecolor(self):
        self.config["display"].update({"theme": "catppuccin-mocha", "avatar_color": "256"})
        result = self.render("ansi")
        self.assertIn("\x1b[38;5;", result)
        self.assertNotIn("38;2;", result)

    def test_modern_uses_structured_values_not_english_lines(self):
        self.modules[1].lines[:] = ["99999 followers"]
        self.modules[2].lines[:] = ["Languages: fake 100%"]
        self.document = build_profile_document(self.user, self.modules, provider="github")
        result = self.render()
        self.assertIn("1,280 followers", result)
        self.assertIn("73.0%", result)
        self.assertNotIn("99999", result)
        self.assertNotIn("fake", result)

    def test_all_six_provider_fixtures_use_modern_ui(self):
        self.config["display"]["details"] = True
        for provider in ("github", "gitlab", "bitbucket", "gitea", "forgejo", "codeberg"):
            with self.subTest(provider=provider):
                user, modules, document = fixture(provider, partial=True)
                output = render_output(self.config, user, modules, "plain", document=document)
                self.assertIn("Alex Rivera", output)
                self.assertNotIn("legacy calendar", output)
                if provider in {"gitlab", "bitbucket"}:
                    self.assertIn("repos", output)
                    self.assertIn("unsupported", output)
                else:
                    self.assertIn("?", output)
                    self.assertIn("73.0%", output)

    def test_avatar_download_and_encoding_once_per_frame(self):
        self.config["display"]["avatar"] = True
        from gitfetch.render import _render_avatar_image
        with (mock.patch("gitfetch.render._load_avatar", return_value=avatar_image()) as download,
              mock.patch("gitfetch.render._render_avatar_image", wraps=_render_avatar_image) as encode):
            self.render()
        download.assert_called_once_with(self.document.avatar_reference)
        encode.assert_called_once()

    def test_small_viewport_and_no_avatar_do_not_download(self):
        with mock.patch("gitfetch.render._load_avatar", side_effect=AssertionError("unexpected download")):
            self.render()
            self.config["display"]["avatar"] = True
            with mock.patch("gitfetch.render.shutil.get_terminal_size", return_value=os.terminal_size((40, 12))):
                self.render()

    def test_failed_avatar_load_falls_back_to_full_width_text(self):
        self.config["display"]["avatar"] = True
        with mock.patch("gitfetch.render._load_avatar", return_value=None) as download:
            output = self.render()
        download.assert_called_once()
        self.assertTrue(output.startswith("Alex Rivera"))
        self.assertTrue(all(cell_width(line) <= 80 for line in output.splitlines()))

    def test_real_encoder_and_planner_agree_for_all_styles_and_aspects(self):
        self.config["display"]["avatar"] = True
        for style in ("ascii", "halfblock", "braille"):
            for size in ((96, 96), (160, 80), (80, 160)):
                image = avatar_image().resize(size)
                self.config["display"]["avatar_style"] = style
                with mock.patch("gitfetch.render._load_avatar", return_value=image):
                    output = self.render()
                plan = plan_profile(self.document, Viewport(80, 24), Preferences(avatar_style=style), AvatarGeometry(*size), reference_date=REFERENCE)
                self.assertEqual(len(output.splitlines()), plan.height)
                self.assertTrue(all(cell_width(line) <= 80 for line in output.splitlines()))

    def test_no_color_forces_both_avatar_and_text_to_monochrome(self):
        self.config["display"]["avatar"] = True
        self.config["_color_force"] = "off"
        with mock.patch("gitfetch.render._load_avatar", return_value=avatar_image()):
            self.assertNotIn("\x1b", self.render("ansi"))

    def test_unsafe_remote_and_plugin_text_are_sanitized(self):
        payload = "世界 e\u0301 👩🏽‍💻 مرحبا\tline\nnext\rINJECT\x1b[2J\x1b]8;;https://evil\x1b\\click\x1b]8;;\x1b\\\x1bPsecret\x1b\\"
        user = {**self.user, "name": payload, "bio": payload, "blog": payload}
        modules = [ModuleResult("identity", "Identity", [], {"user": user}), ModuleResult("plugin", payload, [payload], {})]
        document = build_profile_document(user, modules, provider="github")
        self.config["display"]["details"] = True
        for output_format in ("plain", "ansi"):
            output = render_output(self.config, user, modules, output_format, document=document)
            stripped = re.sub(r"\x1b\[[0-9;]*m", "", output)
            self.assertNotIn("\x1b", stripped)
            self.assertNotIn("\r", stripped)
            self.assertNotIn("https://evil", stripped)
            self.assertNotIn("secret", stripped)
            self.assertIn("👩🏽‍💻", stripped)
            self.assertIn("e\u0301", stripped)
            self.assertEqual(stripped.splitlines(), [sanitize_text(line) for line in stripped.splitlines()])

    def test_json_raw_nullable_values_and_envelope_are_presentation_independent(self):
        raw = "raw\r\x1b]0;title\a"
        modules = [ModuleResult("plugin", "Plugin", [raw], {"text": raw, "numeric": None})]
        self.config["display"]["details"] = True
        result = json.loads(render_output(self.config, self.user, modules, "json", document=object()))
        self.assertEqual(result, {"user": "alex-dev", "modules": {"plugin": {"text": raw, "numeric": None}}})

    def test_classic_ansi_plain_and_exports_ignore_modern_details(self):
        self.config["display"]["export_style"] = "legacy"
        for output_format in ("plain", "ansi", "json", "svg", "card"):
            with self.subTest(output_format=output_format):
                self.config["display"]["presentation"] = "classic"
                original = self.render(output_format)
                self.config["display"].update({"presentation": "modern", "details": True})
                if output_format in {"plain", "ansi"}:
                    self.config["display"]["presentation"] = "classic"
                self.assertEqual(original, self.render(output_format))

    def test_auto_policy_is_modern_only_for_interactive_ansi(self):
        self.config["display"]["presentation"] = "auto"
        with mock.patch("gitfetch.render.sys.stdout", new=mock.Mock(isatty=lambda: True)):
            self.assertTrue(modern_enabled(self.config, "ansi"))
            self.assertFalse(modern_enabled(self.config, "plain"))
            self.config["_captured_output"] = True
            self.assertFalse(modern_enabled(self.config, "ansi"))
        self.config.pop("_captured_output")
        with mock.patch("gitfetch.render.sys.stdout", new=mock.Mock(isatty=lambda: False)):
            self.assertFalse(modern_enabled(self.config, "ansi"))
        self.config["display"]["presentation"] = "modern"
        self.assertTrue(modern_enabled(self.config, "plain"))

    def test_automatic_interactive_output_has_modern_identity(self):
        self.config["display"]["presentation"] = "auto"
        with mock.patch("gitfetch.render.sys.stdout", new=mock.Mock(isatty=lambda: True)):
            output = self.render("ansi")
        self.assertIn("Alex Rivera", output)
        self.assertNotIn("Identity\n", output)

    def test_output_dimensions_include_margins_and_avatar(self):
        self.config["display"]["avatar"] = True
        for columns, rows in DIMENSIONS:
            for margin in (0, 3, 1000000):
                self.config["display"]["margin"] = margin
                with (mock.patch("gitfetch.render._load_avatar", return_value=avatar_image()),
                      mock.patch("gitfetch.render.shutil.get_terminal_size", return_value=os.terminal_size((columns, rows)))):
                    output = self.render("ansi")
                self.assertLessEqual(len(output.splitlines()), rows - 2)
                self.assertTrue(all(cell_width(line) <= columns for line in output.splitlines()), (columns, rows, margin))

    def test_config_validation_and_presets_keep_legacy_layout_meanings(self):
        for preset in ("minimal", "compact", "full", "showcase"):
            config = preset_config(preset)
            self.assertEqual(config["display"]["presentation"], "auto")
            self.assertFalse(config["display"]["details"])
            normalize_config(config)
        for invalid in ("unknown", 42, None):
            config = preset_config("minimal")
            config["display"]["presentation"] = invalid
            with self.assertRaises(ConfigError):
                normalize_config(config)
        config = preset_config("minimal")
        config["display"]["details"] = "yes"
        with self.assertRaises(ConfigError):
            normalize_config(config)

    def test_new_flags_are_completed_in_all_supported_shells(self):
        for shell in ("bash", "zsh", "fish"):
            script = script_for(shell)
            self.assertIn("presentation", script)
            self.assertIn("details", script)
            self.assertIn("modern classic", script)


class ModernPipelineTests(unittest.TestCase):
    # Reuse setup/helpers without rediscovering inherited legacy tests.
    setUp = legacy_pipeline.PresentationPipelineTests.setUp
    select = legacy_pipeline.PresentationPipelineTests.select
    run_cli = legacy_pipeline.PresentationPipelineTests.run_cli

    def test_modern_configured_and_explicit_external_profiles(self):
        self.config["display"]["presentation"] = "modern"
        first, _ = self.run_cli()
        second, _ = self.run_cli("--user", "alice")
        self.assertEqual(first, second)
        self.context.user["login"] = "bob"
        output, documents = self.run_cli("--user", "bob")
        self.assertIn("@bob", output)
        self.assertEqual(len(documents), 1)
        self.assertEqual(self.client.get_context.call_count, 3)

    def test_details_does_not_expand_collection_or_repeat_handlers(self):
        self.select("identity", "stats", "languages")
        self.context.repos = [{"languages_url": "https://example.test/one"}, {"languages_url": "https://example.test/two"}]
        for details in (False, True):
            self.client.reset_mock()
            handlers = {name: mock.Mock(wraps=MODULE_HANDLERS[name]) for name in ("identity", "stats", "languages")}
            with mock.patch.dict(MODULE_HANDLERS, handlers):
                _, documents = self.run_cli("--presentation", "modern", *(["--details"] if details else []))
            for handler in handlers.values():
                handler.assert_called_once()
            self.client.get_context.assert_called_once()
            self.assertFalse(self.client.get_context.call_args.kwargs["include_graphql"])
            self.assertEqual(self.client.get_languages.call_count, 2)
            self.assertEqual(len(documents), 1)

    def test_flags_override_set_values_and_config(self):
        self.config["display"]["presentation"] = "classic"
        output, _ = self.run_cli("--set", "display.presentation=classic", "--set", "display.details=false", "--presentation", "modern", "--details")
        self.assertIn("@alice · GitHub", output)
        self.assertNotIn("Identity\n--------", output)
        output, _ = self.run_cli("--set", "display.presentation=modern", "--presentation", "classic")
        self.assertIn("Identity\n--------", output)

    def test_modern_preserves_module_order_and_exclusions(self):
        self.select("stats", "identity")
        output, documents = self.run_cli("--presentation", "modern", "--details")
        self.assertLess(output.index("public repos"), output.index("@alice"))
        self.assertEqual([s.name for s in documents[0].sections], ["stats", "identity"])
        self.config["modules"]["identity"]["enabled"] = False
        output, _ = self.run_cli("--presentation", "modern", "--details")
        self.assertNotIn("@alice", output)

    def test_actual_line_only_plugin_runs_once_and_is_safe(self):
        plugin = self.root / "plugin.py"
        plugin.write_text("calls = []\ndef handler(config, context, client):\n    calls.append(1)\n    return ['plugin invoked', 'calls: ' + str(len(calls)), '\\x1b]0;unsafe\\a世界']\nMODULES = {'plugin': handler}\n")
        self.config["plugins"] = {"paths": [str(plugin)], "modules": ["plugin"], "allow_unsafe": True}
        self.select("plugin")
        output, documents = self.run_cli("--presentation", "modern", "--details")
        self.assertIn("plugin invoked", output)
        self.assertIn("世界", output)
        self.assertNotIn("\x1b", output)
        self.assertEqual(len(documents), 1)
        self.assertIn("calls: 1", output)
        self.assertNotIn("calls: 2", output)

    def test_modern_watch_builds_once_per_frame(self):
        from gitfetch.cli import run_watch_loop
        calls = []
        def run(render_once, interval, **kwargs):
            for _ in range(2):
                render_once()
                calls.append(1)
        with mock.patch("gitfetch.cli.run_watch_loop", side_effect=run):
            _, documents = self.run_cli("--presentation", "modern", "--watch", "1")
        self.assertEqual(len(documents), 2)
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.client.get_context.call_count, 2)
        self.assertTrue(callable(run_watch_loop))

    def test_save_auto_policy_preserves_classic_capture(self):
        output = self.root / "capture.txt"
        with mock.patch("gitfetch.render.modern_enabled", wraps=modern_enabled) as policy:
            self.run_cli("--save", str(output), output_format="ansi")
        self.assertTrue(policy.call_args.args[0]["_captured_output"])
        self.assertIn("Identity\n", output.read_text())

    def test_png_bytes_ignore_presentation_and_details(self):
        self.config["display"]["export_style"] = "legacy"
        output = self.root / "profile.png"
        self.run_cli("--presentation", "classic", "--save", str(output), output_format="png")
        original = output.read_bytes()
        self.run_cli("--presentation", "modern", "--details", "--save", str(output), output_format="png")
        self.assertEqual(output.read_bytes(), original)

    def test_auth_and_unsupported_notices_remain_actionable(self):
        self.select("pinned")
        output, _ = self.run_cli("--presentation", "modern", "--details")
        self.assertIn("GITHUB_TOKEN", output)
        self.client.supports_module.return_value = False
        self.client.unsupported_reason.return_value = "no calendar endpoint"
        output, _ = self.run_cli("--presentation", "modern", "--details")
        self.assertIn("unsupported", output)
        self.assertIn("no calendar endpoint", output)
