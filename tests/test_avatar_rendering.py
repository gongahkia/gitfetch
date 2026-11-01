"""Image encoders and real CLI entrypoints share the optional asset policy."""
import copy
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from xml.etree import ElementTree

import test_contracts as contracts
from avatar_fixtures import CASES, image_bytes
from modern_fixtures import fixture
from PIL import Image
from test_avatar_assets import URL, response

from gitfetch.config import SUPPORTED_PROVIDERS, preset_config, write_config
from gitfetch.formats import _avatar_image, render_card_png, render_summary_card_png
from gitfetch.images import AvatarLoader, avatar_context, prepare_avatar
from gitfetch.modules.builtin import ModuleResult
from gitfetch.presentation import build_profile_document
from gitfetch.render import _BRAILLE_OFFSETS, _render_avatar_image, render_output
from gitfetch.terminal_text import cell_width, sanitize_styled_text, sanitize_text

STYLES = ("ascii", "halfblock", "braille")
RAMP = "BS#&@$%*!:."


class AvatarEncoderTests(unittest.TestCase):
    def encode(self, image, style, color="none", width=16, ramp=RAMP):
        return _render_avatar_image(image, width, style, color, ramp)

    def test_every_style_accepts_all_local_images(self):
        for case in CASES:
            image = prepare_avatar(image_bytes(case)).image
            for style in STYLES:
                for color in ("none", "256", "truecolor"):
                    with self.subTest(case=case, style=style, color=color):
                        lines = self.encode(image, style, color)
                        self.assertTrue(lines)
                        self.assertTrue(all(cell_width(line) == 16 for line in lines))
                        self.assertTrue(all(sanitize_styled_text(line) == line for line in lines))
                        if color == "none":
                            self.assertNotIn("\x1b", "".join(lines))
                        else:
                            self.assertTrue(all(line.endswith("\x1b[0m") for line in lines))
                        if color == "256":
                            self.assertNotIn(";2;", "".join(lines))

    def test_transparent_pixels_are_spaces_and_never_have_background_colors(self):
        image = Image.new("RGBA", (16, 16), (255, 0, 255, 0))
        for style in STYLES:
            for color in ("none", "truecolor"):
                lines = self.encode(image, style, color)
                self.assertTrue(all(sanitize_text(line) == " " * 16 for line in lines))
                self.assertNotIn("48;", "".join(lines))
                self.assertNotIn("38;", "".join(lines))

    def test_halfblock_uses_top_bottom_and_both_block_cases(self):
        image = Image.new("RGBA", (4, 2))
        for x, top, bottom in [(0, True, True), (1, True, False), (2, False, True), (3, False, False)]:
            if top:
                image.putpixel((x, 0), (255, 0, 0, 255))
            if bottom:
                image.putpixel((x, 1), (0, 0, 255, 255))
        line = self.encode(image, "halfblock", "truecolor", 4)[0]
        self.assertEqual(sanitize_text(line), "▀▀▄ ")
        self.assertEqual(line.count("48;"), 1)
        self.assertIn("\x1b[49m\x1b[38;2;255;0;0m▀", line)
        self.assertIn("\x1b[49m\x1b[38;2;0;0;255m▄", line)
        self.assertTrue(line.endswith("\x1b[0m \x1b[0m"))

    def test_halfblock_preserves_opaque_black_in_color(self):
        line = self.encode(Image.new("RGBA", (2, 2), (0, 0, 0, 255)), "halfblock", "truecolor", 2)[0]
        self.assertIn("\x1b[38;2;0;0;0m\x1b[48;2;0;0;0m▀", line)
        self.assertEqual(sanitize_text(line), "▀▀")

    def test_halfblock_monochrome_uses_original_brightness_and_alpha(self):
        image = Image.new("RGBA", (4, 2))
        for x, top, bottom in [(0, True, True), (1, True, False), (2, False, True)]:
            if top:
                image.putpixel((x, 0), (255, 255, 255, 255))
            if bottom:
                image.putpixel((x, 1), (255, 255, 255, 255))
        self.assertEqual(self.encode(image, "halfblock", width=4), ["█▀▄ "])

    def test_partial_alpha_uses_deterministic_coverage_without_black_matte(self):
        image = Image.new("RGBA", (16, 16), (240, 200, 160, 128))
        for style in STYLES:
            first = self.encode(image, style, "truecolor")
            self.assertEqual(first, self.encode(image, style, "truecolor"))
            # Premultiplied-alpha resampling can round a channel by one unit.
            colors = re.findall(r"38;2;(\d+);(\d+);(\d+)m", "".join(first))
            self.assertTrue(colors)
            self.assertTrue(all(abs(int(value) - expected) <= 1
                                for color in colors for value, expected in zip(color, (240, 200, 160))))
            self.assertNotIn("38;2;120;100;80m", "".join(first))
            self.assertNotIn("48;2;0;0;0m", "".join(first))
        ascii_text = "".join(self.encode(image, "ascii"))
        self.assertGreater(ascii_text.count(" "), 0)
        self.assertLess(ascii_text.count(" "), len(ascii_text))

    def test_ascii_custom_ramp_direction_and_opaque_black_remain_compatible(self):
        for brightness, expected in ((0, "B"), (255, ".")):
            image = Image.new("RGB", (2, 2), (brightness,) * 3)
            self.assertEqual(self.encode(image, "ascii", width=2), [expected * 2])
        self.assertEqual(self.encode(Image.new("RGB", (2, 2), "black"), "ascii", width=2, ramp="xy"), ["xx"])

    def test_ascii_untrusted_or_wide_ramp_is_safely_filtered(self):
        for ramp in ("\x1b]0;bad\a🌏", "", "e\u0301."):
            output = self.encode(prepare_avatar(image_bytes()).image, "ascii", ramp=ramp)
            self.assertTrue(all(cell_width(line) == 16 for line in output))
            self.assertNotIn("\x1b", "".join(output))

    def test_braille_dot_orientation_is_unchanged(self):
        for dx, dy, bit in _BRAILLE_OFFSETS:
            image = Image.new("RGBA", (2, 4))
            image.putpixel((dx, dy), (255, 255, 255, 255))
            self.assertEqual(self.encode(image, "braille", width=1), [chr(0x2800 + bit)])

    def test_braille_color_uses_lit_visible_dots_only(self):
        image = Image.new("RGBA", (2, 4), (255, 0, 255, 0))
        image.putpixel((0, 0), (0, 255, 0, 255))
        line = self.encode(image, "braille", "truecolor", 1)[0]
        self.assertEqual(line, "\x1b[38;2;0;255;0m⠁\x1b[0m")

    def test_geometry_preserves_source_aspect_with_cell_rounding(self):
        for case in ("landscape", "portrait"):
            image = prepare_avatar(image_bytes(case)).image
            for style in STYLES:
                factor = 0.55 if style == "ascii" else 0.5
                self.assertEqual(len(self.encode(image, style, width=24)), int(image.height / image.width * 24 * factor))

    def test_ascii_and_braille_resize_source_only_once(self):
        image = prepare_avatar(image_bytes()).image
        for style in STYLES:
            with mock.patch.object(image, "resize", wraps=image.resize) as resize:
                self.encode(image, style, "truecolor")
                resize.assert_called_once()

    def test_encoders_do_not_mutate_rgba_source(self):
        image = prepare_avatar(image_bytes("partial")).image
        before = image.tobytes()
        for style in STYLES:
            self.encode(image, style, "truecolor")
        self.assertEqual(image.tobytes(), before)

    def test_extreme_source_aspect_ratios_cannot_allocate_unbounded_output(self):
        for style in STYLES:
            self.assertEqual(self.encode(Image.new("RGBA", (1, 8192)), style, width=100), [])
            lines = self.encode(Image.new("RGBA", (8, 512)), style, width=10000)
            self.assertLessEqual(len(lines), 256)
            self.assertTrue(all(cell_width(line) <= 256 for line in lines))

    def test_excessive_requested_width_is_bounded_without_distortion(self):
        for style in STYLES:
            lines = self.encode(Image.new("RGBA", (64, 64), "white"), style, width=10000)
            self.assertEqual(cell_width(lines[0]), 256)
            self.assertEqual(len(lines), int(256 * (0.55 if style == "ascii" else 0.5)))

    def test_invalid_geometry_falls_back(self):
        for image, width in ((Image.new("RGBA", (0, 0)), 16), (Image.new("RGBA", (2, 2)), 0)):
            self.assertEqual(self.encode(image, "ascii", width=width), [])


class AvatarExportTests(unittest.TestCase):
    def setUp(self):
        self.config = preset_config("minimal")
        self.config["display"]["avatar"] = True
        self.config["_avatar_loader"] = AvatarLoader()
        self.user = {"login": "alice", "avatar_url": URL, "followers": 0, "following": None, "public_repos": 1}
        self.modules = [ModuleResult("identity", "Identity", ["@alice"], {"user": self.user})]

    def test_terminal_and_both_card_exports_reuse_one_asset(self):
        from gitfetch.images import prepare_avatar
        with (tempfile.TemporaryDirectory() as directory,
              mock.patch("gitfetch.images.urlopen", return_value=response(image_bytes("transparent"))) as http,
              mock.patch("gitfetch.images.prepare_avatar", wraps=prepare_avatar) as decode,
              mock.patch("gitfetch.render.shutil.get_terminal_size", return_value=os.terminal_size((120, 40)))):
            for presentation in ("modern", "classic"):
                self.config["display"]["presentation"] = presentation
                for fmt in ("ansi", "plain", "svg", "card"):
                    output = render_output(self.config, self.user, self.modules, fmt)
                    self.assertTrue(output)
                    if fmt in {"svg", "card"}:
                        ElementTree.fromstring(output)
            render_card_png(self.config, self.user, self.modules, Path(directory) / "card.png")
            render_summary_card_png(self.config, "Summary", "scope", self.modules, URL, Path(directory) / "summary.png")
        self.assertEqual((http.call_count, decode.call_count), (1, 1))

    def test_non_square_card_slot_preserves_geometry_and_transparent_padding(self):
        for case, bounds in (("landscape", (0, 24, 96, 72)), ("portrait", (24, 0, 72, 96))):
            with avatar_context(AvatarLoader()), mock.patch("gitfetch.images.urlopen", return_value=response(image_bytes(case))):
                avatar = _avatar_image(URL, 96)
                self.assertEqual(avatar.size, (96, 96))
                self.assertEqual(avatar.getbbox(), bounds)

    def test_png_composites_alpha_with_existing_card_background(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "card.png"
            with mock.patch("gitfetch.images.urlopen", return_value=response(image_bytes("transparent"))):
                render_card_png(self.config, self.user, self.modules, path)
            with Image.open(path) as image:
                self.assertEqual(image.getpixel((48, 48)), (13, 17, 23))

    def test_invalid_asset_does_not_crash_terminal_or_exports(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch("gitfetch.images.urlopen", return_value=response(b"invalid")) as http:
            for fmt in ("ansi", "plain", "svg", "card"):
                self.assertIn("alice", render_output(self.config, self.user, self.modules, fmt))
            render_card_png(self.config, self.user, self.modules, Path(directory) / "card.png")
            http.assert_called_once()

    def test_json_and_no_avatar_skip_acquisition(self):
        with mock.patch.object(self.config["_avatar_loader"], "load", side_effect=AssertionError("unexpected acquisition")):
            self.assertIn(URL, render_output(self.config, self.user, self.modules, "json"))
            self.config["display"]["avatar"] = False
            for fmt in ("ansi", "plain", "svg", "card"):
                self.assertTrue(render_output(self.config, self.user, self.modules, fmt))
            with tempfile.TemporaryDirectory() as directory:
                render_card_png(self.config, self.user, self.modules, Path(directory) / "card.png")

    def test_text_only_modern_preflight_skips_asset(self):
        self.config["display"]["presentation"] = "modern"
        with mock.patch.object(self.config["_avatar_loader"], "load", side_effect=AssertionError("text only")):
            for size in ((30, 40), (40, 12), (200, 8)):
                with mock.patch("gitfetch.render.shutil.get_terminal_size", return_value=os.terminal_size(size)):
                    self.assertTrue(render_output(self.config, self.user, self.modules, "plain"))

    def test_profile_and_generic_plugin_payloads_remain_raw(self):
        user, modules, _ = fixture(plugin=True)
        user["avatar_url"] = URL
        before_user, before_modules = copy.deepcopy(user), copy.deepcopy(modules)
        document = build_profile_document(user, modules, provider="github")
        self.config["display"].update({"presentation": "modern", "details": True})
        with mock.patch("gitfetch.images.urlopen", return_value=response()):
            output = render_output(self.config, user, modules, "plain", document=document)
        self.assertEqual(user, before_user)
        self.assertEqual(modules, before_modules)
        self.assertNotIn("\x1b", output)
        self.assertIn("Local notes", output)


class AvatarPipelineTests(contracts._ContractFixtures):
    def setUp(self):
        super().setUp()
        self.config["display"].update({"avatar": True, "avatar_width": 20, "layout": "stack"})
        self.config["cache"]["enabled"] = True
        write_config(self.path, self.config)
        self.enterContext(mock.patch("gitfetch.render.shutil.get_terminal_size", return_value=os.terminal_size((100, 30))))

    def avatar_client(self, provider="github"):
        client = self.client(provider)
        def context(username, **_):
            result = contracts.profile_context(username)
            result.user["avatar_url"] = URL
            return result
        client.get_context.side_effect = context
        repo = contracts.repository()
        repo["owner"]["avatar_url"] = URL
        client.get_repo.side_effect = lambda *_: copy.deepcopy(repo)
        client.get_org.return_value["avatar_url"] = URL
        return client

    def test_offline_all_entrypoints_and_formats_do_not_access_avatar_network(self):
        for mode in ([], ["repo", "alice/project"], ["org", "team"], ["compare", "alice", "bob"]):
            for fmt in ("ansi", "plain", "json", "svg", "card", "png"):
                with self.subTest(mode=mode, fmt=fmt):
                    extra = ["--save", str(Path(self.directory) / "output.png")] if fmt == "png" else []
                    result = self.run_cli(["--offline", *extra, *mode], self.avatar_client(), fmt)
                    self.assertTrue(result)

    def test_offline_modern_and_classic_all_styles_missing_asset_remain_useful(self):
        for presentation in ("modern", "classic"):
            for style in STYLES:
                result = self.run_cli(["--offline", "--presentation", presentation, "--avatar-style", style], self.avatar_client(), "plain")
                self.assertIn("alice", result)
                self.assertNotIn("\x1b", result)

    def test_cold_warm_refresh_offline_profile_workflows(self):
        client = self.avatar_client()
        with mock.patch("gitfetch.images.urlopen", return_value=response()) as http:
            first = self.run_cli(["--presentation", "modern"], client, "plain")
            http.assert_called_once()
        with mock.patch("gitfetch.images.urlopen", side_effect=AssertionError("cached/offline network")):
            warm = self.run_cli(["--user", "alice", "--presentation", "modern"], client, "plain")
            offline = self.run_cli(["--offline", "--presentation", "modern"], client, "plain")
        self.assertEqual(first, warm)
        self.assertEqual(first, offline)
        with mock.patch("gitfetch.images.urlopen", return_value=response(image_bytes("partial"))) as http:
            self.run_cli(["--refresh", "--presentation", "modern"], client, "plain")
            http.assert_called_once()

    def test_all_styles_and_formats_use_cached_assets_offline(self):
        client = self.avatar_client()
        with mock.patch("gitfetch.images.urlopen", return_value=response()):
            self.run_cli([], client, "card")
        for fmt in ("ansi", "plain", "svg", "card", "png"):
            for presentation in ("modern", "classic"):
                extra = ["--save", str(Path(self.directory) / "cached.png")] if fmt == "png" else []
                for style in STYLES:
                    with self.subTest(fmt=fmt, presentation=presentation, style=style):
                        output = self.run_cli(["--offline", "--presentation", presentation, "--avatar-style", style, *extra], client, fmt)
                        self.assertTrue(output)
                        if fmt == "card":
                            self.assertIn("data:image/png;base64,", output)

    def test_modes_reuse_cached_asset_and_compare_deduplicates_shared_url(self):
        client = self.avatar_client()
        with mock.patch("gitfetch.images.urlopen", return_value=response()) as http:
            self.run_cli(["compare", "alice", "bob"], client, "plain")
            http.assert_called_once()
        for mode in (["repo", "alice/project"], ["org", "team"], ["compare", "alice", "bob"]):
            for fmt in ("plain", "svg", "card", "png"):
                extra = ["--save", str(Path(self.directory) / "mode.png")] if fmt == "png" else []
                with self.subTest(mode=mode, fmt=fmt):
                    output = self.run_cli(["--offline", *extra, *mode], client, fmt)
                    self.assertTrue(output)
                    if fmt == "card" and mode[0] != "compare":
                        self.assertIn("data:image/png;base64,", output)

    def test_all_six_providers_receive_offline_policy(self):
        for provider in SUPPORTED_PROVIDERS:
            client = self.avatar_client(provider)
            args = ["--provider", provider, "--base-url", client.base_url, "--offline", "--presentation", "modern"]
            self.assertIn("alice", self.run_cli(args, client, "plain"))

    def test_no_avatar_or_json_never_acquires_for_any_mode(self):
        for mode in ([], ["repo", "alice/project"], ["org", "team"], ["compare", "alice", "bob"]):
            with mock.patch("gitfetch.images.AvatarLoader.load", side_effect=AssertionError("unneeded acquisition")):
                self.run_cli(mode, self.avatar_client(), "json")
                for fmt in ("ansi", "plain", "svg", "card", "png"):
                    extra = ["--save", str(Path(self.directory) / "none.png")] if fmt == "png" else []
                    self.run_cli(["--no-avatar", *extra, *mode], self.avatar_client(), fmt)

    def test_offline_profile_api_policy_and_json_values_remain_unchanged(self):
        client = self.avatar_client()
        result = self.run_cli(["--offline"], client)
        self.assertEqual(set(result), {"user", "modules"})
        self.assertEqual(result["modules"]["identity"]["user"]["avatar_url"], URL)
        self.assertEqual(result["modules"]["identity"]["user"]["followers"], 7)
        self.assertNotIn("_avatar_loader", str(result))
        self.assertEqual(client.get_context.call_count, 1)

    def test_watch_frames_share_disk_cache_and_have_fresh_memos(self):
        client = self.avatar_client()
        loaders = []
        def watch(render_once, *_, **__):
            render_once()
            render_once()
        from gitfetch.images import AvatarLoader
        def loader(policy):
            result = AvatarLoader(policy)
            loaders.append(result)
            return result
        with (mock.patch("gitfetch.cli.run_watch_loop", side_effect=watch),
              mock.patch("gitfetch.cli.AvatarLoader", side_effect=loader),
              mock.patch("gitfetch.images.urlopen", return_value=response()) as http):
            self.run_cli(["--watch", "1"], client, "plain")
        self.assertEqual(len(loaders), 2)
        self.assertIsNot(loaders[0], loaders[1])
        self.assertEqual(http.call_count, 1)
        self.assertEqual(client.get_context.call_count, 2)

    def test_no_color_remains_safe_with_cached_asset(self):
        with mock.patch("gitfetch.images.urlopen", return_value=response()):
            self.run_cli([], self.avatar_client(), "card")
        output = self.run_cli(["--offline", "--no-color", "--presentation", "modern"], self.avatar_client(), "ansi")
        self.assertNotRegex(output, re.compile(r"[\x00-\x08\x0b-\x1f\x7f]"))
