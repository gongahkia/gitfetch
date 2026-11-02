"""Passive capabilities, override provenance and bounded Kitty transport."""
import base64
import copy
import json
import random
import tempfile
import unittest
from dataclasses import replace
from io import BytesIO, StringIO
from pathlib import Path
from unittest import mock

from avatar_fixtures import CASES, image_bytes
from PIL import Image

from gitfetch.cli import main
from gitfetch.completions import script_for
from gitfetch.config import ConfigError, load_config, normalize_config, preset_config, write_config
from gitfetch.images import PreparedAvatar, prepare_avatar
from gitfetch.kitty_graphics import CHUNK_SIZE, MAX_PNG_BYTES, chunk_png, encode_avatar
from gitfetch.terminal_capabilities import (
    AvatarPreferences,
    Support,
    classify_terminal,
    discover_terminal,
    resolve_preferences,
    select_avatar_backend,
)

KITTY = {"TERM": "xterm-kitty", "KITTY_WINDOW_ID": "7", "COLORTERM": "truecolor"}
GHOSTTY = {"TERM": "xterm-ghostty", "TERM_PROGRAM": "ghostty"}


def capabilities(env=None, **kwargs):
    return classify_terminal(KITTY if env is None else env, stdout_tty=True, **kwargs)


def decision(caps=None, preferences=None, **kwargs):
    args = {"output_format": "ansi", "modern": True, **kwargs}
    return select_avatar_backend(caps or capabilities(), preferences or AvatarPreferences(), **args)


class CapabilityTests(unittest.TestCase):
    def test_direct_kitty_has_corroborated_support(self):
        caps = capabilities()
        self.assertEqual(caps.kitty, Support.SUPPORTED)
        self.assertEqual(caps.identity, "kitty")
        self.assertTrue(caps.placement_safe)

    def test_direct_ghostty_has_corroborated_support(self):
        self.assertEqual(capabilities(GHOSTTY).kitty, Support.SUPPORTED)

    def test_one_inherited_identity_hint_is_insufficient(self):
        for env in ({"TERM_PROGRAM": "ghostty"}, {"KITTY_WINDOW_ID": "7"}, {"TERM": "xterm-kitty"},
                    {"TERM": "xterm-ghostty"}, {**KITTY, "TERM_PROGRAM": "ghostty"}):
            self.assertEqual(capabilities(env).kitty, Support.UNKNOWN)

    def test_unknown_terminal_is_unknown(self):
        self.assertEqual(capabilities({"TERM": "xterm-256color"}).kitty, Support.UNKNOWN)

    def test_unsupported_terminal_is_not_forced_into_graphics(self):
        for env in ({"TERM": "dumb"}, {"TERM": "linux"}, {"TERM": "xterm-256color", "TERM_PROGRAM": "Apple_Terminal"}):
            caps = capabilities(env)
            self.assertEqual(caps.kitty, Support.UNSUPPORTED)
            self.assertNotEqual(decision(caps, AvatarPreferences("kitty")).backend, "kitty")

    def test_stdout_pipe_and_unwritable_tty_are_restricted(self):
        for kwargs in ({"stdout_tty": False}, {"stdout_tty": True, "writable": False}):
            caps = classify_terminal(KITTY, **kwargs)
            self.assertFalse(caps.interactive)
            self.assertEqual(caps.kitty, Support.UNSUPPORTED)

    def test_ci_is_restricted(self):
        self.assertFalse(capabilities({**KITTY, "CI": "true"}).interactive)

    def test_ssh_uncertainty_and_explicit_confirmation(self):
        caps = capabilities({**KITTY, "SSH_CONNECTION": "private address"})
        self.assertEqual(caps.kitty, Support.UNKNOWN)
        self.assertEqual(decision(caps).backend, "text")
        self.assertEqual(decision(caps, AvatarPreferences("kitty")).backend, "kitty")
        self.assertNotIn("private address", str(caps))

    def test_zellij_does_not_trust_outer_terminal_hints(self):
        caps = capabilities({**KITTY, "ZELLIJ": "0"})
        self.assertEqual(caps.multiplexer, "zellij")
        self.assertEqual(caps.kitty, Support.UNKNOWN)
        self.assertEqual(decision(caps).backend, "text")

    def test_zellij_confirmed_effective_support_can_select_automatically(self):
        caps = capabilities({**GHOSTTY, "ZELLIJ": "0"}, effective_kitty=Support.SUPPORTED)
        self.assertEqual(decision(caps).backend, "kitty")
        self.assertTrue(caps.placement_safe)

    def test_zellij_unknown_support_can_be_explicitly_confirmed(self):
        caps = capabilities({"TERM": "xterm-256color", "ZELLIJ": "0", "COLORTERM": "truecolor"})
        self.assertEqual(decision(caps, AvatarPreferences("kitty")).backend, "kitty")
        self.assertIn("user-confirmed", decision(caps, AvatarPreferences("kitty")).reason)

    def test_zellij_negative_effective_support_is_respected(self):
        caps = capabilities({**KITTY, "ZELLIJ": "0"}, effective_kitty=Support.UNSUPPORTED)
        self.assertEqual(decision(caps, AvatarPreferences("kitty")).backend, "text")

    def test_zellij_known_unsupported_host_stays_text_even_if_forced(self):
        caps = capabilities({"TERM": "xterm-256color", "TERM_PROGRAM": "Apple_Terminal", "ZELLIJ": "0"})
        self.assertEqual(decision(caps, AvatarPreferences("kitty")).backend, "text")

    def test_tmux_never_uses_inherited_hints_or_blind_passthrough(self):
        for env in ({**KITTY, "TMUX": "/secret/socket"}, {"TERM": "tmux-256color", "COLORTERM": "truecolor"}):
            caps = capabilities(env)
            self.assertFalse(caps.placement_safe)
            self.assertEqual(decision(caps, AvatarPreferences("kitty")).backend, "text")
            self.assertNotIn("/secret/socket", str(caps))

    def test_screen_and_nested_multiplexers_are_conservative(self):
        for env in ({**KITTY, "STY": "1"}, {**KITTY, "TMUX": "1", "ZELLIJ": "0"}):
            self.assertFalse(capabilities(env).placement_safe)

    def test_windows_and_windows_terminal_fall_back(self):
        for caps in (capabilities(platform="nt"), capabilities({**KITTY, "WT_SESSION": "secret"})):
            self.assertEqual(decision(caps, AvatarPreferences("kitty")).backend, "text")

    def test_color_levels_and_no_color_presence(self):
        for env, expected in ((KITTY, "truecolor"), ({"TERM": "xterm-256color"}, "256"),
                              ({"TERM": "vt100"}, "none"), ({**KITTY, "NO_COLOR": ""}, "none")):
            self.assertEqual(capabilities(env).color, expected)

    def test_discovery_does_not_accept_a_fake_stringio_tty(self):
        stream = StringIO()
        stream.isatty = lambda: True
        self.assertFalse(discover_terminal(stream, stream, env=KITTY).stdout_tty)

    def test_discovery_never_reads_input_or_probes(self):
        stdin = mock.Mock()
        stdin.isatty.return_value = False
        stdin.read.side_effect = AssertionError("input consumed")
        stream = StringIO()
        discover_terminal(stream, stdin, env=KITTY)
        stdin.read.assert_not_called()
        self.assertEqual(stream.getvalue(), "")


class SelectionTests(unittest.TestCase):
    def test_auto_selects_kitty(self):
        result = decision()
        self.assertEqual(result.backend, "kitty")
        self.assertFalse(result.explicit)

    def test_auto_unicode_and_reduced_color_fallback(self):
        result = decision(capabilities({"TERM": "xterm-256color"}))
        self.assertEqual((result.backend, result.text_style, result.color), ("text", "halfblock", "256"))
        self.assertTrue(result.fallback)

    def test_ascii_fallback_for_non_unicode_output(self):
        result = decision(capabilities({"TERM": "vt100"}, unicode=False))
        self.assertEqual((result.text_style, result.color), ("ascii", "none"))

    def test_explicit_kitty_can_confirm_unknown_direct_terminal(self):
        result = decision(capabilities({"TERM": "xterm-256color", "COLORTERM": "truecolor"}), AvatarPreferences("kitty"))
        self.assertEqual(result.backend, "kitty")
        self.assertTrue(result.explicit)

    def test_explicit_text_respects_configured_style(self):
        result = decision(preferences=AvatarPreferences("text", "braille"))
        self.assertEqual((result.backend, result.text_style), ("text", "braille"))

    def test_legacy_style_remains_authoritative(self):
        self.assertEqual(decision(preferences=AvatarPreferences("auto", "halfblock", True)).backend, "text")

    def test_disabled_or_missing_avatar_does_not_select_graphics(self):
        self.assertEqual(decision(avatar=False).backend, "none")
        self.assertEqual(decision(has_asset=False).backend, "none")

    def test_every_non_graphics_output_is_excluded_even_when_forced(self):
        for output in ("plain", "json", "svg", "card", "png"):
            self.assertEqual(decision(preferences=AvatarPreferences("kitty"), output_format=output).backend, "text")

    def test_captured_classic_and_watch_paths_are_excluded(self):
        for kwargs in ({"captured": True}, {"modern": False}, {"watch": True}):
            self.assertEqual(decision(preferences=AvatarPreferences("kitty"), **kwargs).backend, "text")

    def test_monochrome_and_reduced_color_requests_are_explicit(self):
        for color in ("none", "256"):
            self.assertEqual(decision(preferences=AvatarPreferences("kitty", color=color)).backend, "text")
        self.assertEqual(decision(color_allowed=False).backend, "text")
        self.assertEqual(decision(capabilities({**KITTY, "NO_COLOR": "1"})).backend, "text")

    def test_no_graphics_for_redirected_stdout_even_with_override(self):
        caps = classify_terminal(KITTY, stdout_tty=False)
        self.assertEqual(decision(caps, AvatarPreferences("kitty")).backend, "text")

    def test_noninteractive_default_keeps_legacy_ascii(self):
        caps = classify_terminal(KITTY, stdout_tty=False)
        self.assertEqual(decision(caps).text_style, "ascii")


class PreferenceTests(unittest.TestCase):
    def setUp(self):
        self.config = preset_config("compact")
        normalize_config(self.config)

    def resolve(self, *, saved=(), overrides=(), renderer=None, style=None):
        return resolve_preferences(self.config, saved=set(saved), overrides=list(overrides), renderer=renderer, style=style)

    def test_fresh_defaults_are_automatic(self):
        self.assertEqual(self.resolve().renderer, "auto")

    def test_saved_legacy_style_is_text(self):
        self.assertEqual(self.resolve(saved=["avatar_style"]).renderer, "text")

    def test_saved_renderer_auto_authorizes_auto_over_saved_default_style(self):
        self.assertEqual(self.resolve(saved=["avatar_style", "avatar_renderer"]).renderer, "auto")

    def test_cli_style_overrides_saved_renderer(self):
        result = self.resolve(saved=["avatar_renderer"], style="halfblock")
        self.assertEqual(result.renderer, "text")
        self.assertTrue(result.legacy_style)

    def test_cli_renderer_overrides_cli_style(self):
        self.assertEqual(self.resolve(renderer="kitty", style="halfblock").renderer, "kitty")
        self.assertEqual(self.resolve(renderer="auto", style="ascii").renderer, "auto")

    def test_dotted_renderer_overrides_saved_style(self):
        self.config["display"]["avatar_renderer"] = "kitty"
        self.assertEqual(self.resolve(saved=["avatar_style"], overrides=["display.avatar_renderer=kitty"]).renderer, "kitty")

    def test_dotted_style_overrides_saved_renderer(self):
        self.assertEqual(self.resolve(saved=["avatar_renderer"], overrides=["display.avatar_style=braille"]).renderer, "text")

    def test_cli_style_overrides_dotted_renderer(self):
        self.assertEqual(self.resolve(overrides=["display.avatar_renderer=kitty"], style="braille").renderer, "text")

    def test_provenance_is_optional_and_not_added_to_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text('[display]\navatar_style="halfblock"\n')
            keys = set()
            loaded = load_config(path, explicit_display=keys)
            self.assertEqual(keys, {"avatar_style"})
            self.assertEqual(loaded, load_config(path))
            self.assertNotIn("_avatar_style_explicit", loaded)

    def test_new_configs_roundtrip_without_hidden_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            write_config(path, self.config)
            keys = set()
            self.assertEqual(load_config(path, explicit_display=keys), self.config)
            self.assertIn("avatar_renderer", keys)

    def test_old_style_survives_later_configuration_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text('[display]\navatar_style="braille"\n')
            loaded = load_config(path)
            self.assertEqual(loaded["display"]["avatar_renderer"], "text")
            write_config(path, loaded)
            saved = set()
            reloaded = load_config(path, explicit_display=saved)
            self.assertEqual(resolve_preferences(reloaded, saved=saved, overrides=[], renderer=None, style=None).renderer, "text")

    def test_custom_ramp_is_an_authoritative_legacy_text_choice(self):
        self.assertEqual(self.resolve(saved=["ascii_ramp"]).renderer, "text")
        self.assertEqual(self.resolve(overrides=["display.ascii_ramp=.#"]).renderer, "text")
        self.assertEqual(self.resolve(saved=["ascii_ramp"], renderer="auto").renderer, "auto")

    def test_validation_rejects_unknown_and_wrong_types(self):
        for value in ("sixel", True, 42):
            config = copy.deepcopy(self.config)
            config["display"]["avatar_renderer"] = value
            with self.assertRaises(ConfigError):
                normalize_config(config)

    def test_completions_cover_all_new_choices(self):
        for shell in ("bash", "zsh", "fish"):
            text = script_for(shell)
            self.assertIn("avatar-renderer", text)
            self.assertIn("graphics-info", text)
            self.assertIn("auto kitty text", text)

    def test_diagnostic_needs_no_username_token_plugins_or_network(self):
        from contextlib import redirect_stdout
        with (tempfile.TemporaryDirectory() as directory, redirect_stdout(StringIO()) as output,
              mock.patch("gitfetch.cli.get_token", side_effect=AssertionError("token resolution")),
              mock.patch("gitfetch.cli.create_provider_client", side_effect=AssertionError("provider")),
              mock.patch("gitfetch.cli.load_plugin_modules", side_effect=AssertionError("plugins")),
              mock.patch("gitfetch.images.urlopen", side_effect=AssertionError("avatar"))):
            path = Path(directory) / "config.toml"
            path.write_text('[profile]\nusername=""\n')
            self.assertEqual(main(["--config", str(path), "--graphics-info"]), 0)
            data = json.loads(output.getvalue())
            self.assertFalse(data["active_probe"])
            self.assertTrue(data["asset_not_checked"])
            self.assertEqual(data["decision"]["backend"], "text")

    def test_diagnostic_rejects_subcommands_before_collection(self):
        from contextlib import redirect_stderr
        with (redirect_stderr(StringIO()) as errors,
              mock.patch("gitfetch.modes.create_provider_client", side_effect=AssertionError("provider"))):
            self.assertEqual(main(["--graphics-info", "repo", "alice/project"]), 2)
        self.assertIn("omit the subcommand", errors.getvalue())

    def test_native_preview_refuses_piped_output(self):
        from contextlib import redirect_stderr, redirect_stdout

        from preview_native import main as preview
        with (redirect_stdout(StringIO()) as output, redirect_stderr(StringIO()),
              mock.patch("gitfetch.images.urlopen", side_effect=AssertionError("preview network")),
              self.assertRaises(SystemExit) as result):
            preview(["--confirm-kitty"])
        self.assertEqual(result.exception.code, 2)
        self.assertEqual(output.getvalue(), "")


class KittyEncodingTests(unittest.TestCase):
    def setUp(self):
        self.asset = prepare_avatar(image_bytes("partial"))

    def encode(self, asset=None, **kwargs):
        return encode_avatar(asset or self.asset, number=kwargs.get("number", 7), columns=kwargs.get("columns", 24), rows=kwargs.get("rows", 12))

    def payload(self, transmission):
        return base64.b64decode("".join(chunk.split(";", 1)[1][:-2] for chunk in transmission.chunks), validate=True)

    def test_apc_and_png_parameters(self):
        result = self.encode()
        self.assertTrue(result.chunks[0].startswith("\x1b_Ga=T,f=100,t=d,I=7,c=24,r=12,C=1,q=2,m="))
        self.assertTrue(all(chunk.endswith("\x1b\\") for chunk in result.chunks))
        self.assertTrue(self.payload(result).startswith(b"\x89PNG\r\n\x1a\n"))

    def test_full_alpha_and_colors_are_preserved(self):
        with Image.open(BytesIO(self.payload(self.encode()))) as image:
            self.assertEqual(image.convert("RGBA").tobytes(), self.asset.image.tobytes())
            self.assertEqual(image.getpixel((0, 0))[3], 0)
            self.assertIn(128, image.getchannel("A").get_flattened_data())

    def test_non_square_tiny_oriented_and_animated_sources(self):
        for case in CASES:
            asset = prepare_avatar(image_bytes(case))
            with Image.open(BytesIO(self.payload(self.encode(asset)))) as image:
                self.assertEqual(image.size, asset.effective_size)
                self.assertEqual(image.mode, "RGBA")

    def test_larger_asset_is_bounded_preserving_aspect(self):
        source = Image.new("RGBA", (1024, 512), (20, 40, 60, 128))
        asset = PreparedAvatar(source, source.size, source.size, True, True, "network")
        with Image.open(BytesIO(self.payload(self.encode(asset)))) as image:
            self.assertEqual(image.size, (512, 256))

    def test_multipart_chunks_and_final_signaling(self):
        random_bytes = random.Random(7).randbytes(128 * 128 * 4)
        image = Image.frombytes("RGBA", (128, 128), random_bytes)
        asset = replace(self.asset, image=image)
        result = self.encode(asset)
        self.assertGreater(len(result.chunks), 1)
        for chunk in result.chunks[:-1]:
            encoded = chunk.split(";", 1)[1][:-2]
            self.assertLessEqual(len(encoded), CHUNK_SIZE)
            self.assertEqual(len(encoded) % 4, 0)
            self.assertIn("m=1;", chunk)
        self.assertIn("m=0;", result.chunks[-1])
        self.assertEqual(result.chunks[1].split(";", 1)[0], "\x1b_Gq=2,m=1")
        with Image.open(BytesIO(self.payload(result))) as decoded:
            self.assertEqual(decoded.tobytes(), random_bytes)

    def test_exact_chunk_boundary_has_correct_final_flag(self):
        payload = b"\x89PNG\r\n\x1a\n" + b"x" * (3072 - 8)
        result = chunk_png(payload, number=1, columns=1, rows=1)
        self.assertEqual(len(result.chunks), 1)
        self.assertIn("m=0;", result.chunks[0])
        self.assertEqual(len(result.chunks[0].split(";", 1)[1][:-2]), CHUNK_SIZE)

    def test_invalid_dimensions_ids_modes_and_payloads(self):
        for field in ("number", "columns", "rows"):
            for value in (0, -1, True, 0x100000000):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    self.encode(**{field: value})
        for image in (Image.new("RGB", (2, 2)), Image.new("RGBA", (0, 0)), Image.new("RGBA", (1025, 1))):
            with self.assertRaises(ValueError):
                self.encode(replace(self.asset, image=image))
        for payload in (b"", b"invalid", b"\x89PNG\r\n\x1a\n" + b"x" * MAX_PNG_BYTES):
            with self.assertRaises(ValueError):
                chunk_png(payload, number=1, columns=1, rows=1)

    def test_quiet_every_chunk_no_files_or_global_deletion(self):
        result = self.encode()
        self.assertTrue(all("q=2" in chunk for chunk in result.chunks))
        self.assertNotIn("t=f", "".join(result.chunks))
        self.assertNotIn("t=s", "".join(result.chunks))
        self.assertEqual(result.cleanup, "\x1b_Ga=d,d=N,I=7,q=2;\x1b\\")
        self.assertNotIn("d=A", result.cleanup)

    def test_encoding_deterministic_and_source_unchanged(self):
        before = self.asset.image.tobytes()
        self.assertEqual(self.encode(), self.encode())
        self.assertEqual(self.asset.image.tobytes(), before)

    def test_png_failure_is_raised_before_any_terminal_emission(self):
        with mock.patch.object(Image.Image, "save", side_effect=OSError("PNG encoder failed")), self.assertRaises(OSError):
            self.encode()
