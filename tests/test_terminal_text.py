import random
import re
import unittest

from gitfetch.render import visible_len
from gitfetch.terminal_text import (
    cell_width,
    clip_text,
    sanitize_styled_text,
    sanitize_text,
    wrap_text,
)


class TerminalTextTests(unittest.TestCase):
    def test_normal_ascii_is_unchanged(self):
        self.assertEqual(sanitize_text("octocat"), "octocat")
        self.assertEqual(cell_width("octocat"), 7)

    def test_cell_widths(self):
        cases = [
            ("", 0), (None, 0), ("漢字", 4), ("cafe\u0301", 4), ("é", 1),
            ("😀", 2), ("👩🏽\u200d💻", 2), ("👨\u200d👩\u200d👧\u200d👦", 2),
            ("🇸🇬", 2), ("1\ufe0f\u20e3", 2), ("\x1b[38;2;1;2;3m漢字\x1b[0m", 4),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(cell_width(value), expected)
                self.assertEqual(visible_len(value), expected)

    def test_unicode_is_not_destructively_normalized(self):
        text = "漢字 cafe\u0301 👩🏽\u200d💻 \u0645\u06cc\u200c\u0631\u0648\u0645 \u2060"
        self.assertEqual(sanitize_text(text), text)

    def test_numeric_and_missing_values(self):
        self.assertEqual(sanitize_text(None), "")
        self.assertEqual(sanitize_text(42), "42")
        self.assertEqual(clip_text(None, 10), "")
        self.assertEqual(wrap_text(None, 10), [])

    def test_whitespace_policy(self):
        self.assertEqual(sanitize_text("a\tb\nc\rd\r\ne"), "a b c d e")
        self.assertEqual(sanitize_text("  a  b  "), "  a  b  ")
        self.assertEqual(sanitize_text("a\v\f\u0085\u2028\u2029b"), "a     b")
        self.assertEqual(cell_width("a\tb\nc"), 5)

    def test_csi_cursor_clear_and_sgr_are_removed_from_untrusted_text(self):
        text = "a\x1b[2Jb\x1b[Hc\x1b[12;4Hd\x1b[31me\x1b[0mf"
        self.assertEqual(sanitize_text(text), "abcdef")
        self.assertEqual(cell_width(text), 6)

    def test_control_strings_and_their_payloads_are_removed(self):
        for start in ("\x1b]", "\x1bP", "\x1b_", "\x1b^", "\x1bX", "\x90", "\x98", "\x9d", "\x9e", "\x9f"):
            for end in ("\x1b\\", "\x9c"):
                with self.subTest(start=start, end=end):
                    self.assertEqual(sanitize_text(f"a{start}hidden{end}b"), "ab")
        self.assertEqual(sanitize_text("a\x1b]0;owned\x07b"), "ab")

    def test_osc_hyperlink_removes_url_but_preserves_label(self):
        text = "\x1b]8;;https://evil.test\x1b\\click 漢字\x1b]8;;\x1b\\"
        self.assertEqual(sanitize_text(text), "click 漢字")
        self.assertEqual(cell_width(text), 10)

    def test_unterminated_and_cancelled_sequences(self):
        for sequence in ("\x1b]title", "\x1bPpayload", "\x1b_payload", "\x9dtitle", "\x1b[123", "\x1b"):
            with self.subTest(sequence=sequence):
                self.assertEqual(sanitize_text("safe" + sequence), "safe")
        self.assertEqual(sanitize_text("a\x1b]payload\x18b"), "ab")
        self.assertEqual(sanitize_text("a\x1b[12\x1b[31mb"), "ab")

    def test_other_escape_sequences_and_c1_csi(self):
        self.assertEqual(sanitize_text("a\x1b7b\x1b8c\x1bcd\x1b(Be\x9b2Jf"), "abcdef")
        self.assertEqual(sanitize_text("a\x1b\x1b[2Jb"), "ab")

    def test_controls_cannot_overwrite_or_ring_the_terminal(self):
        self.assertEqual(sanitize_text("a\x00b\x08c\x07d\x7fe\x80f"), "abcdef")
        self.assertEqual(sanitize_text("original\roverwrite"), "original overwrite")

    def test_bidi_overrides_and_invalid_surrogates(self):
        self.assertEqual(sanitize_text("a\u202eb\u202cc\u2066d\u2069"), "abcd")
        self.assertEqual(sanitize_text("a\ud800b\udfffc"), "a\ufffdb\ufffdc")
        self.assertEqual(sanitize_text("a\ufffe\uffffb"), "a\ufffd\ufffdb")

    def test_trust_is_explicit_and_only_sgr_survives(self):
        text = "\x1b[31mred\x1b[0m\x1b[2J\x1b]0;title\x07"
        self.assertEqual(sanitize_text(text), "red")
        self.assertEqual(sanitize_styled_text(text), "\x1b[31mred\x1b[0m")
        self.assertEqual(clip_text(text, 20), "red")
        self.assertEqual(clip_text(text, 20, trusted_ansi=True), "\x1b[31mred\x1b[0m")

    def test_exact_boundary_clipping_does_not_add_ellipsis(self):
        for text in ("abcd", "漢字", "👩🏽\u200d💻ab", "cafe\u0301"):
            with self.subTest(text=text):
                self.assertEqual(clip_text(text, 4), text)

    def test_clip_reserves_ellipsis_cells(self):
        self.assertEqual(clip_text("abcdef", 4), "abc…")
        self.assertEqual(clip_text("abcdef", 4, ellipsis=".."), "ab..")
        self.assertEqual(clip_text("abcdef", 1, ellipsis="漢"), "a")
        self.assertEqual(clip_text("abcdef", 1), "…")
        self.assertEqual(clip_text("漢字", 2, ellipsis=""), "漢")
        self.assertEqual(clip_text("漢字", 1, ellipsis=""), "")
        self.assertEqual(clip_text("abcdef", 0), "")
        self.assertEqual(clip_text("abcdef", -1), "")

    def test_clip_does_not_split_graphemes(self):
        self.assertEqual(clip_text("e\u0301x", 1, ellipsis=""), "e\u0301")
        self.assertEqual(clip_text("👩🏽\u200d💻xy", 2, ellipsis=""), "👩🏽\u200d💻")
        self.assertEqual(clip_text("🇸🇬xy", 2, ellipsis=""), "🇸🇬")

    def test_clip_balances_trusted_styles(self):
        result = clip_text("\x1b[31mabcdef", 4, trusted_ansi=True)
        self.assertEqual(result, "\x1b[31mabc\x1b[0m…")
        self.assertEqual(cell_width(result), 4)
        self.assertEqual(clip_text("\x1b[31mabc", 3, trusted_ansi=True), "\x1b[31mabc\x1b[0m")

    def test_styling_inside_a_grapheme_does_not_split_it(self):
        text = "\x1b[31me\x1b[0m\u0301x"
        self.assertEqual(sanitize_text(clip_text(text, 1, ellipsis="", trusted_ansi=True)), "e\u0301")
        result = wrap_text(text, 1, trusted_ansi=True)
        self.assertEqual([sanitize_text(line) for line in result], ["e\u0301", "x"])

    def test_wrap_long_biography_urls_and_uninterrupted_words(self):
        for text in ("Builds useful things. " * 30, "https://example.test/" + "path" * 100, "x" * 501):
            with self.subTest(text=text[:30]):
                lines = wrap_text(text, 17)
                self.assertEqual("".join(lines), text)
                self.assertTrue(all(cell_width(line) <= 17 for line in lines))

    def test_wrap_preserves_unicode_and_balances_styles_on_every_line(self):
        text = "\x1b[1;38;2;1;2;3m漢字 e\u0301👩🏽\u200d💻 hello"
        lines = wrap_text(text, 4, trusted_ansi=True)
        self.assertEqual("".join(sanitize_text(line) for line in lines), sanitize_text(text))
        self.assertTrue(all(cell_width(line) <= 4 for line in lines))
        self.assertTrue(all(line.endswith("\x1b[0m") for line in lines))
        self.assertTrue(all(line.startswith("\x1b[") for line in lines))

    def test_wrap_replaces_a_grapheme_that_cannot_fit(self):
        self.assertEqual(wrap_text("漢👩🏽\u200d💻a", 1), ["?", "?", "a"])
        self.assertEqual(wrap_text("", 3), [])
        for budget in (0, -1):
            with self.assertRaises(ValueError):
                wrap_text("abc", budget)

    def test_width_and_clipping_agree_for_all_budgets(self):
        text = "漢字e\u0301👩🏽\u200d💻 \x1b]8;;evil\x07link\x1b]8;;\x07\tend"
        for budget in range(1, 25):
            with self.subTest(budget=budget):
                clipped = clip_text(text, budget)
                self.assertLessEqual(cell_width(clipped), budget)
                self.assertEqual(clipped, sanitize_text(clipped))
                self.assertTrue(all(cell_width(line) <= budget for line in wrap_text(text, budget)))

    def test_ellipsis_cannot_inject_styles_or_terminal_commands(self):
        self.assertEqual(clip_text("abcdef", 4, ellipsis="\x1b[31m.\x1b[2J"), "abc.")

    def test_output_has_no_c0_or_c1_controls(self):
        text = "".join(chr(code) for code in range(160)) + "漢字👩🏽\u200d💻"
        for result in (sanitize_text(text), clip_text(text, 20), *wrap_text(text, 5)):
            self.assertIsNone(re.search(r"[\x00-\x1f\x7f-\x9f]", result))

    def test_mixed_unicode_and_control_inputs_obey_invariants(self):
        generator = random.Random(42)
        fragments = [
            "a", "漢", "e\u0301", "👩🏽\u200d💻", "🇸🇬", " ", "\t", "\r\n", "\ud800",
            "\x1b[31m", "\x1b[0m", "\x1b[2J", "\x1b]8;;evil\x07", "\x1b]8;;\x07",
            "\x1bPpayload\x1b\\", "\x9b2J", "\x08", "\x1b", "\u2066",
        ]
        for _ in range(100):
            text = "".join(generator.choices(fragments, k=12))
            clean = sanitize_text(text)
            self.assertEqual(sanitize_text(clean), clean)
            self.assertIsNone(re.search(r"[\x00-\x1f\x7f-\x9f]", clean))
            for budget in (1, 2, 5):
                for trusted in (False, True):
                    results = [clip_text(text, budget, trusted_ansi=trusted)]
                    results.extend(wrap_text(text, budget, trusted_ansi=trusted))
                    for result in results:
                        self.assertLessEqual(cell_width(result), budget)
                        self.assertIsNone(re.search(r"[\x00-\x1f\x7f-\x9f]", re.sub(r"\x1b\[[0-9;]*m", "", result)))
