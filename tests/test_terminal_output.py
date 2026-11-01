"""Placement/frame contracts, synthetic CLI integration and controlled PTYs."""
import copy
import json
import os
import re
import sys
import unittest
from dataclasses import replace
from io import StringIO
from pathlib import Path
from unittest import mock

import test_contracts as contracts
from avatar_fixtures import image_bytes
from modern_fixtures import DIMENSIONS, REFERENCE, fixture
from PIL import Image
from test_avatar_assets import URL, response
from test_terminal_graphics import KITTY, capabilities, decision

from gitfetch.config import write_config
from gitfetch.images import AvatarLoader, AvatarPolicy, prepare_avatar
from gitfetch.layout import Viewport
from gitfetch.render import render_output
from gitfetch.terminal_output import (
    FrameUnavailable,
    TerminalWriteError,
    build_terminal_frame,
    emit_native_profile,
    write_terminal_frame,
)
from gitfetch.terminal_text import cell_width


class FrameTests(unittest.TestCase):
    def setUp(self):
        self.user, self.modules, self.document = fixture(plugin=True)
        from gitfetch.config import preset_config
        self.config = preset_config("minimal")
        self.config["display"].update(avatar=True, presentation="modern")
        self.config["_color_force"] = "on"
        self.loader = mock.Mock(spec=AvatarLoader)
        self.loader.load.return_value.asset = prepare_avatar(image_bytes("transparent"))
        self.config["_avatar_loader"] = self.loader
        self.viewport = Viewport(100, 30)

    def frame(self, **kwargs):
        return build_terminal_frame(self.config, self.document, decision(), kwargs.pop("viewport", self.viewport),
                                    reference_date=REFERENCE, image_number=23, **kwargs)

    def write(self, frame=None, stream=None):
        frame = frame or self.frame()
        stream = stream or StringIO()
        with (mock.patch("gitfetch.terminal_output._is_tty", return_value=True),
              mock.patch("gitfetch.terminal_output.terminal_viewport", return_value=frame.plan.viewport)):
            write_terminal_frame(frame, stream)
        return stream.getvalue()

    def test_split_reserves_left_region_and_text_starts_to_right(self):
        frame = self.frame()
        self.assertEqual(frame.plan.composition, "split")
        self.assertIsNotNone(frame.graphics)
        first = re.sub(r"\x1b\[[0-9;]*m", "", frame.text.splitlines()[0])
        self.assertTrue(first.startswith(" " * (frame.plan.avatar_width + 3)))
        self.assertIn("Alex Rivera", first)
        self.assertEqual(frame.graphics.columns, frame.plan.avatar_width)
        self.assertEqual(frame.graphics.rows, frame.plan.avatar_rows)
        self.assertNotIn("\x1b_G", frame.text)

    def test_stack_places_text_below_avatar_and_separator(self):
        self.config["display"]["layout"] = "stack"
        frame = self.frame(viewport=Viewport(100, 40))
        self.assertEqual(frame.plan.composition, "stack")
        self.assertTrue(all(not row.strip() for row in frame.text.splitlines()[:frame.plan.avatar_rows]))
        self.assertIn("Alex Rivera", frame.text.splitlines()[frame.plan.avatar_rows + 1])

    def test_narrow_and_text_only_plans_never_transmit_or_fetch(self):
        for viewport in (Viewport(30, 40), Viewport(40, 12), Viewport(200, 8)):
            with self.subTest(viewport=viewport):
                self.loader.reset_mock()
                frame = self.frame(viewport=viewport)
                self.assertIsNone(frame.graphics)
                self.loader.load.assert_not_called()

    def test_dimension_invariants_across_required_viewports(self):
        for cols, rows in DIMENSIONS:
            frame = self.frame(viewport=Viewport(cols, rows))
            self.assertTrue(all(cell_width(line) <= cols for line in frame.text.splitlines()))
            self.assertLessEqual(len(frame.text.splitlines()), max(1, rows - 2))
            if frame.graphics:
                self.assertLess(frame.plan.avatar_rows, rows)
                self.assertLessEqual(frame.plan.margin + frame.plan.avatar_width, cols)

    def test_wide_short_avatar_remains_bounded(self):
        frame = self.frame(viewport=Viewport(200, 15))
        self.assertLessEqual(frame.plan.avatar_rows, 7)
        self.assertLessEqual(frame.plan.avatar_width, 34)

    def test_margin_is_part_of_pane_local_anchor(self):
        self.config["display"]["margin"] = 2
        frame = self.frame()
        output = self.write(frame)
        self.assertIn(f"\x1b[{frame.plan.avatar_rows}A\r\x1b[2C\x1b_G", output)
        self.assertNotRegex(output, r"\x1b\[[0-9]+;[0-9]+[Hf]")
        self.assertNotIn("tmux;", output)

    def test_writer_reserves_rows_then_places_without_cursor_save_slots(self):
        frame = self.frame()
        output = self.write(frame)
        prefix, _ = output.split("\x1b_G", 1)
        self.assertEqual(prefix.count("\n"), frame.plan.avatar_rows)
        self.assertIn(f"\r\x1b[{frame.plan.avatar_rows}B", output)
        self.assertTrue(output.endswith("\r\n"))
        self.assertNotIn("\x1b7", output)
        self.assertNotIn("\x1b8", output)
        self.assertNotIn("?1049", output)
        self.assertNotIn("?25", output)

    def test_missing_and_offline_asset_keep_profile_text(self):
        for loader in (AvatarLoader(AvatarPolicy(offline=True)), self.loader):
            if loader is self.loader:
                self.loader.load.return_value.asset = None
            self.config["_avatar_loader"] = loader
            with mock.patch("gitfetch.images.urlopen", side_effect=AssertionError("offline network")):
                frame = self.frame()
                self.assertIsNone(frame.graphics)
                self.assertIn("Alex Rivera", frame.text)

    def test_disabled_avatar_skips_asset_and_encoding(self):
        self.config["display"]["avatar"] = False
        with mock.patch("gitfetch.terminal_output.encode_avatar", side_effect=AssertionError("encode disabled")):
            frame = self.frame()
        self.loader.load.assert_not_called()
        self.assertIsNone(frame.graphics)

    def test_one_load_one_plan_one_png_encode_per_frame(self):
        from gitfetch.kitty_graphics import encode_avatar
        from gitfetch.layout import plan_profile
        with (mock.patch("gitfetch.terminal_output.encode_avatar", wraps=encode_avatar) as encode,
              mock.patch("gitfetch.terminal_output.plan_profile", wraps=plan_profile) as plan):
            frame = self.frame()
        self.assertIsNotNone(frame.graphics)
        self.assertEqual((self.loader.load.call_count, encode.call_count, plan.call_count), (1, 1, 1))

    def test_png_failure_uses_text_without_protocol(self):
        with mock.patch("gitfetch.terminal_output.encode_avatar", side_effect=OSError("invalid encoder")):
            frame = self.frame()
        self.assertIsNone(frame.graphics)
        self.assertEqual(frame.decision.backend, "text")
        self.assertTrue(frame.decision.fallback)
        self.assertNotIn("\x1b_G", self.write(frame))
        self.assertIn("Alex Rivera", frame.text)

    def test_render_time_no_color_is_respected_even_after_selection(self):
        self.config["_color_force"] = "off"
        frame = self.frame()
        self.assertIsNone(frame.graphics)
        self.assertNotIn("\x1b", frame.text)

    def test_resize_before_writing_is_a_zero_output_failure(self):
        frame = self.frame()
        stream = StringIO()
        with (mock.patch("gitfetch.terminal_output._is_tty", return_value=True),
              mock.patch("gitfetch.terminal_output.terminal_viewport", return_value=Viewport(40, 12)),
              self.assertRaises(FrameUnavailable)):
            write_terminal_frame(frame, stream)
        self.assertEqual(stream.getvalue(), "")

    def test_resize_during_transmission_aborts_without_full_redraw(self):
        frame = self.frame()
        stream = StringIO()
        with (mock.patch("gitfetch.terminal_output._is_tty", return_value=True),
              mock.patch("gitfetch.terminal_output.terminal_viewport", side_effect=[frame.plan.viewport, frame.plan.viewport, Viewport(40, 12)]),
              self.assertRaises(TerminalWriteError)):
            write_terminal_frame(frame, stream)
        self.assertIn(frame.graphics.cleanup, stream.getvalue())
        self.assertNotIn("\x1b_Ga=T", stream.getvalue())
        self.assertEqual(stream.getvalue().count("Alex Rivera"), 1)

    def test_pipe_and_missing_tty_are_zero_output_failures(self):
        stream = StringIO()
        with self.assertRaises(FrameUnavailable):
            write_terminal_frame(self.frame(), stream)
        self.assertEqual(stream.getvalue(), "")

    def test_unsafe_text_overflow_and_rectangle_rejected_before_output(self):
        frame = self.frame()
        cases = (replace(frame, text="bad\x1b]0;title\a"), replace(frame, text="x" * 101),
                 replace(frame, graphics=replace(frame.graphics, rows=200)))
        for invalid in cases:
            stream = StringIO()
            with self.assertRaises(FrameUnavailable):
                self.write(invalid, stream)
            self.assertEqual(stream.getvalue(), "")

    def test_short_writes_are_completed(self):
        class ShortWriter(StringIO):
            def write(self, value):
                return super().write(value[:19])
        frame = self.frame()
        self.assertEqual(self.write(frame, ShortWriter()), self.write(frame))

    def test_failure_after_native_output_aborts_only_owned_image_without_redraw(self):
        class FailingWriter(StringIO):
            failed = False
            def write(self, value):
                if value.startswith("\x1b_G") and not self.failed:
                    self.failed = True
                    super().write(value[:13])
                    raise OSError("broken graphics")
                return super().write(value)
        frame = self.frame()
        stream = FailingWriter()
        with self.assertRaises(TerminalWriteError):
            self.write(frame, stream)
        output = stream.getvalue()
        self.assertIn(frame.graphics.cleanup, output)
        self.assertIn(f"\r\x1b[{frame.plan.avatar_rows}B", output)
        self.assertNotIn("d=A", output)
        self.assertEqual(output.count("Alex Rivera"), 1)
        self.assertTrue(output.endswith("\x1b[0m\r\n"))

    def test_ctrl_c_is_recovered_without_global_delete(self):
        class InterruptedWriter(StringIO):
            failed = False
            def write(self, value):
                if value.startswith("\x1b_G") and not self.failed:
                    self.failed = True
                    raise KeyboardInterrupt()
                return super().write(value)
        frame = self.frame()
        stream = InterruptedWriter()
        with self.assertRaises(TerminalWriteError) as context:
            self.write(frame, stream)
        self.assertTrue(context.exception.interrupted)
        self.assertIn(frame.graphics.cleanup, stream.getvalue())

    def test_emitter_does_not_request_fallback_after_partial_output(self):
        with (mock.patch("gitfetch.terminal_output.terminal_viewport", return_value=self.viewport),
              mock.patch("gitfetch.terminal_output.write_terminal_frame", side_effect=TerminalWriteError()),
              self.assertRaises(TerminalWriteError)):
            emit_native_profile(self.config, self.document, decision(), StringIO())

    def test_preoutput_terminal_failure_allows_fallback_without_loading(self):
        with mock.patch("gitfetch.terminal_output.terminal_viewport", side_effect=OSError("missing tty")):
            self.assertFalse(emit_native_profile(self.config, self.document, decision(), StringIO()))
        self.loader.load.assert_not_called()

    def test_details_keep_all_collected_plugin_content(self):
        self.config["display"]["details"] = True
        frame = self.frame()
        self.assertIn("Local notes", frame.text)
        self.assertIn("generic plugin section", frame.text)
        self.assertGreater(len(frame.text.splitlines()), self.viewport.rows)

    def test_document_and_module_payloads_unchanged(self):
        user, modules = copy.deepcopy(self.user), copy.deepcopy(self.modules)
        self.frame()
        self.assertEqual((self.user, self.modules), (user, modules))

    def test_ordinary_string_api_never_emits_native_graphics(self):
        self.config["display"]["avatar_renderer"] = "kitty"
        self.config["display"]["avatar"] = False
        for fmt in ("ansi", "plain", "json", "svg", "card"):
            self.assertNotIn("\x1b_G", render_output(self.config, self.user, self.modules, fmt, document=self.document))


class GraphicsPipelineTests(contracts._ContractFixtures):
    def setUp(self):
        super().setUp()
        self.config["display"].update(avatar=True, presentation="modern")
        self.config["cache"]["enabled"] = True
        write_config(self.path, self.config)
        self.enterContext(mock.patch("gitfetch.cli.discover_terminal", return_value=capabilities()))
        self.enterContext(mock.patch("gitfetch.terminal_output._is_tty", return_value=True))
        self.enterContext(mock.patch("gitfetch.terminal_output.terminal_viewport", return_value=Viewport(100, 30)))

    def avatar_client(self):
        client = self.client()
        def context(username, **_):
            ctx = contracts.profile_context(username)
            ctx.user["avatar_url"] = URL
            return ctx
        client.get_context.side_effect = context
        return client

    def test_configured_and_explicit_user_get_one_native_asset(self):
        for args in ([], ["--user", "bob"]):
            with mock.patch("gitfetch.images.urlopen", return_value=response()) as http:
                output = self.run_cli(["--color", *args], self.avatar_client(), "ansi")
                self.assertIn("\x1b_Ga=T", output)
                self.assertLessEqual(http.call_count, 1)

    def test_plain_json_svg_card_png_remain_independent(self):
        client = self.avatar_client()
        for fmt in ("plain", "json", "svg", "card", "png"):
            extra = ["--save", str(Path(self.directory) / "image.png")] if fmt == "png" else []
            with mock.patch("gitfetch.images.urlopen", return_value=response()):
                output = self.run_cli(["--avatar-renderer", "kitty", "--color", *extra], client, fmt)
            self.assertNotIn("\x1b_G", str(output))
            if fmt == "png":
                with Image.open(Path(self.directory) / "image.png") as image:
                    self.assertEqual(image.format, "PNG")

    def test_saved_output_never_receives_protocol(self):
        path = Path(self.directory) / "snapshot.txt"
        with mock.patch("gitfetch.images.urlopen", return_value=response()):
            self.run_cli(["--avatar-renderer", "kitty", "--color", "--save", str(path)], self.avatar_client(), "ansi")
        self.assertNotIn("\x1b_G", path.read_text())

    def test_no_color_and_no_avatar_suppress_protocol(self):
        for flags in (["--no-avatar"], ["--no-color"], ["--theme", "mono"], ["--avatar-color", "none"], ["--avatar-color", "256"]):
            with mock.patch("gitfetch.images.urlopen", return_value=response()):
                color_flags = [] if flags == ["--no-color"] else ["--color"]
                output = self.run_cli(["--avatar-renderer", "kitty", *color_flags, *flags], self.avatar_client(), "ansi")
            self.assertNotIn("\x1b_G", output)

    def test_explicit_style_stays_text_and_renderer_flag_wins(self):
        with mock.patch("gitfetch.images.urlopen", return_value=response()):
            output = self.run_cli(["--color", "--avatar-style", "halfblock"], self.avatar_client(), "ansi")
            self.assertNotIn("\x1b_G", output)
        output = self.run_cli(["--color", "--avatar-style", "halfblock", "--avatar-renderer", "kitty", "--offline"], self.avatar_client(), "ansi")
        self.assertIn("\x1b_Ga=T", output)

    def test_old_saved_style_remains_text(self):
        self.config["display"].pop("avatar_renderer")
        write_config(self.path, self.config)
        with mock.patch("gitfetch.images.urlopen", return_value=response()):
            output = self.run_cli(["--color"], self.avatar_client(), "ansi")
        self.assertNotIn("\x1b_G", output)

    def test_classic_never_emits_graphics(self):
        with mock.patch("gitfetch.images.urlopen", return_value=response()):
            output = self.run_cli(["--color", "--avatar-renderer", "kitty", "--presentation", "classic"], self.avatar_client(), "ansi")
        self.assertNotIn("\x1b_G", output)

    def test_offline_missing_avatar_never_fetches(self):
        output = self.run_cli(["--offline", "--color", "--avatar-renderer", "kitty"], self.avatar_client(), "ansi")
        self.assertNotIn("\x1b_G", output)
        self.assertIn("alice", output)

    def test_warm_offline_native_does_not_fetch_or_decode_twice(self):
        from gitfetch.images import prepare_avatar
        with (mock.patch("gitfetch.images.urlopen", return_value=response()) as http,
              mock.patch("gitfetch.images.prepare_avatar", wraps=prepare_avatar) as decode):
            self.run_cli(["--color"], self.avatar_client(), "ansi")
        self.assertEqual((http.call_count, decode.call_count), (1, 1))
        output = self.run_cli(["--offline", "--color"], self.avatar_client(), "ansi")
        self.assertIn("\x1b_Ga=T", output)

    def test_resize_fallback_reuses_asset_and_evaluates_modules_once(self):
        client = self.avatar_client()
        with (mock.patch("gitfetch.images.urlopen", return_value=response()) as http,
              mock.patch("gitfetch.terminal_output.write_terminal_frame", side_effect=FrameUnavailable("resized"))):
            output = self.run_cli(["--color"], client, "ansi")
        self.assertEqual(http.call_count, 1)
        self.assertEqual(client.get_context.call_count, 1)
        self.assertNotIn("\x1b_G", output)
        self.assertIn("alice", output)

    def test_watch_is_text_and_discovers_only_once(self):
        def watch(frame, *_args, **_kwargs):
            frame()
            frame()
        with (mock.patch("gitfetch.cli.run_watch_loop", side_effect=watch),
              mock.patch("gitfetch.cli.discover_terminal", return_value=capabilities()) as discover,
              mock.patch("gitfetch.images.urlopen", return_value=response()) as http):
            output = self.run_cli(["--watch", "1", "--color", "--avatar-renderer", "kitty"], self.avatar_client(), "ansi")
        self.assertEqual((discover.call_count, http.call_count), (1, 1))
        self.assertNotIn("\x1b_G", output)

    def test_native_preserves_json_raw_nullable_values(self):
        result = self.run_cli(["--avatar-renderer", "kitty"], self.avatar_client(), "json")
        self.assertEqual(set(result), {"user", "modules"})
        self.assertEqual(result["modules"]["identity"]["user"]["avatar_url"], URL)
        self.assertNotIn("graphics", json.dumps(result))

    def test_real_discovery_on_captured_stdout_prevents_native_output(self):
        from gitfetch.terminal_capabilities import discover_terminal
        with (mock.patch("gitfetch.cli.discover_terminal", wraps=discover_terminal),
              mock.patch("gitfetch.cli.emit_native_profile", side_effect=AssertionError("captured native output")),
              mock.patch("gitfetch.images.urlopen", return_value=response())):
            output = self.run_cli(["--avatar-renderer", "kitty", "--color"], self.avatar_client(), "ansi")
        self.assertNotIn("\x1b_G", output)

    def test_unknown_interactive_terminal_uses_unicode_fallback(self):
        caps = capabilities({"TERM": "xterm-256color"})
        with (mock.patch("gitfetch.cli.discover_terminal", return_value=caps),
              mock.patch("gitfetch.cli.emit_native_profile", side_effect=AssertionError("unverified native output")),
              mock.patch("gitfetch.images.urlopen", return_value=response())):
            output = self.run_cli(["--color"], self.avatar_client(), "ansi")
        self.assertNotIn("\x1b_G", output)
        self.assertIn("38;5;", output)

    def test_line_only_plugin_is_preserved_and_injection_cannot_become_graphics(self):
        from gitfetch.modules import load_plugin_modules
        path = Path(self.directory) / "plugin.py"
        path.write_text("MODULES={'notes': lambda config, context, client: ['hello plugin', '\\x1b_Gmalicious;data\\x1b\\\\']}\n")
        self.config["plugins"] = {"paths": [str(path)], "modules": ["notes"], "allow_unsafe": True}
        write_config(self.path, self.config)
        self.addCleanup(load_plugin_modules, {"plugins": {}})
        with mock.patch("gitfetch.images.urlopen", return_value=response()):
            output = self.run_cli(["--color", "--details"], self.avatar_client(), "ansi")
        self.assertIn("hello plugin", output)
        self.assertNotIn("malicious", output)


@unittest.skipUnless(os.name == "posix", "PTY tests require POSIX")
class ControlledPtyTests(unittest.TestCase):
    def test_pane_local_cursor_scrolling_and_input_preservation(self):
        import fcntl
        import select
        import struct
        import termios
        import threading

        from gitfetch.terminal_capabilities import discover_terminal
        master, slave = os.openpty()
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
        attrs = termios.tcgetattr(slave)
        attrs[3] &= ~termios.ECHO
        termios.tcsetattr(slave, termios.TCSANOW, attrs)
        settings = termios.tcgetattr(slave)
        output = []
        stop = threading.Event()
        def read_output():
            while not stop.is_set():
                ready, _, _ = select.select([master], [], [], .05)
                if ready:
                    output.append(os.read(master, 65536))
        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        try:
            with os.fdopen(os.dup(slave), "w", encoding="utf-8", newline="") as stream:
                caps = discover_terminal(stream, sys.stdin, env=KITTY)
                self.assertTrue(caps.stdout_tty)
                _user, _modules, document = fixture()
                from gitfetch.config import preset_config
                config = preset_config("minimal")
                config["display"].update(avatar=True, presentation="modern")
                config["_color_force"] = "on"
                config["_avatar_loader"] = mock.Mock(spec=AvatarLoader)
                config["_avatar_loader"].load.return_value.asset = prepare_avatar(image_bytes("transparent"))
                frame = build_terminal_frame(config, document, decision(caps), Viewport(80, 24), reference_date=REFERENCE, image_number=41)
                os.write(master, b"untouched input\n")
                write_terminal_frame(frame, stream)
                self.assertTrue(select.select([slave], [], [], 1)[0])
                self.assertEqual(os.read(slave, 100), b"untouched input\n")
                self.assertEqual(termios.tcgetattr(slave), settings)
        finally:
            stop.set()
            reader.join(timeout=1)
            while select.select([master], [], [], 0)[0]:
                output.append(os.read(master, 65536))
        data = b"".join(output).decode("utf-8")
        self.assertIn("\x1b_Ga=T", data)
        self.assertNotIn("\x1b[c", data)
        self.assertNotIn("a=q", data)
        # Model only trusted cursor actions; APC payloads never become text.
        data = re.sub(r"\x1b_G.*?\x1b\\", "", data, flags=re.DOTALL)
        data = re.sub(r"\x1b\[[0-9;]*m", "", data)
        row = 23  # Simulate invocation at the bottom of an 80x24 pane.
        image_top = None
        for token in re.findall(r"\x1b\[\d+[ABC]|[\r\n]|[^\x1b\r\n]+", data):
            if token == "\n":
                row = min(23, row + 1)
            elif re.fullmatch(r"\x1b\[\d+A", token):
                row -= int(token[2:-1])
                image_top = row
            elif re.fullmatch(r"\x1b\[\d+B", token):
                row += int(token[2:-1])
        self.assertGreaterEqual(image_top, 0)
        self.assertLess(image_top + frame.plan.avatar_rows, 24)
        self.assertEqual(row, 23)
