"""Targeted T04.1 regressions for rails, narrow panes, hints and contrast."""
import copy
import os
import re
import unittest
from dataclasses import replace
from unittest import mock

from modern_fixtures import DIMENSIONS, REFERENCE, fixture, preview

from gitfetch.config import preset_config
from gitfetch.layout import AvatarGeometry, Preferences, Viewport, plan_profile
from gitfetch.modules.builtin import ModuleResult
from gitfetch.presentation import build_profile_document
from gitfetch.render import render_output
from gitfetch.semantics import Measurement
from gitfetch.terminal_text import cell_width


class VisualPolishTests(unittest.TestCase):
    def setUp(self):
        self.user, self.modules, self.document = fixture()

    def plan(self, width=80, height=24, *, document=None, **preferences):
        return plan_profile(document or self.document, Viewport(width, height), Preferences(avatar=False, **preferences),
                            reference_date=REFERENCE)

    def build(self, *modules):
        return build_profile_document(self.user, modules, provider="github")

    def output(self, plan, module=None):
        return "\n".join(row.text for row in plan.rows if module is None or row.module == module)

    def test_short_sparse_rails_replace_dense_block_rectangles(self):
        for width in (52, 56, 80, 140):
            plan = self.plan(width, 40, details=True)
            rails = [row for row in plan.rows if row.module == "languages" and any(s.role == "track" for s in row.spans)]
            self.assertEqual(len(rails), 5)
            for row in rails:
                rail = "".join(s.text for s in row.spans if s.role in {"accent", "track"})
                self.assertGreaterEqual(cell_width(rail), 8)
                self.assertLessEqual(cell_width(rail), 16)
                self.assertNotIn("█", rail)
                self.assertNotIn("░", rail)
                self.assertIn("·", rail)
            self.assertIn("· ", self.output(plan, "languages"))

    def test_rail_columns_and_percentage_labels_align(self):
        plan = self.plan(80, 40, details=True)
        rows = [r for r in plan.rows if r.module == "languages" and any(s.role == "track" for s in r.spans)]
        self.assertEqual(len({cell_width(r.text) for r in rows}), 1)
        self.assertEqual(len({cell_width(r.spans[0].text) for r in rows}), 1)
        self.assertEqual(len({sum(cell_width(s.text) for s in r.spans if s.role in {"accent", "track"}) for r in rows}), 1)

    def test_bar_ratio_uses_original_full_denominator(self):
        plan = self.plan(80, 40, details=True)
        python = next(r for r in plan.rows if r.module == "languages" and r.text.startswith("Python"))
        rail = [s for s in python.spans if s.role in {"accent", "track"}]
        filled = sum(s.text.count("━") + s.text.count("╸") / 2 for s in rail if s.role == "accent")
        width = sum(cell_width(s.text) for s in rail)
        self.assertLessEqual(abs(filled / width - 7300 / 10000), 0.5 / width)
        self.assertTrue(python.text.endswith("73.0%"))
        self.assertNotIn("73.7%", self.output(plan))

    def test_small_positive_values_keep_a_visible_endcap(self):
        plan = self.plan(80, 40, details=True)
        for name in ("Rust", "Shell"):
            row = next(r for r in plan.rows if r.module == "languages" and r.text.startswith(name))
            self.assertTrue(any(s.text for s in row.spans if s.role == "accent"))
            self.assertIn("╸", row.text)

    def test_narrow_tall_languages_use_lists_even_in_details(self):
        for width in (30, 40, 50):
            for details in (False, True):
                with self.subTest(width=width, details=details):
                    plan = self.plan(width, 40, details=details)
                    rows = [r for r in plan.rows if r.module == "languages"]
                    self.assertFalse(any(s.role in {"accent", "track"} for r in rows for s in r.spans))
                    self.assertIn("Python", self.output(plan, "languages"))
                    self.assertIn("Shell", self.output(plan, "languages"))
                    self.assertTrue(all(cell_width(r.text) <= width for r in rows))

    def test_short_wide_terminal_also_uses_compact_languages(self):
        rows = [r for r in self.plan(200, 15).rows if r.module == "languages"]
        self.assertFalse(any(s.role == "track" for row in rows for s in row.spans))
        self.assertIn("73.0%", " ".join(r.text for r in rows))

    def test_language_metadata_has_one_scope_and_coverage_disclosure(self):
        for width in (30, 80):
            text = self.output(self.plan(width, 40, details=True), "languages")
            self.assertEqual(text.count("selected repos"), 1)
            self.assertEqual(text.count("partial"), 1)
            self.assertIn("20/42", text)
            if width == 30:
                self.assertIn("20/42 selected repos · partial", text.splitlines())

    def test_failed_and_missing_language_requests_remain_explicit(self):
        measurement = replace(self.modules[2].measurements["languages"], failed=2, missing=1)
        module = copy.deepcopy(self.modules[2])
        module.measurements["languages"] = measurement
        for width in (30, 80):
            output = self.output(self.plan(width, 40, document=self.build(module), details=True))
            for expected in ("partial", "2 failed", "1 missing", "20/42", "73.0%"):
                self.assertIn(expected, output)

    def test_repository_language_units_and_multilabel_denominators_survive_polish(self):
        for provider, expected in (("gitlab", "18/20 repos"), ("bitbucket", "12/20 repos")):
            _, _, document = fixture(provider)
            for width in (30, 80):
                output = self.output(self.plan(width, 40, document=document, details=True), "languages")
                self.assertIn(expected, output)
                self.assertNotIn("%", output)
                self.assertIn("prevalence" if provider == "gitlab" else "Primary" if width == 30 else "primary-language", output)

    def test_empty_unknown_and_zero_language_values_do_not_gain_percentages(self):
        for values, denominator in (([], 0), ([{"language": "Python", "bytes": 0}], 0),
                                     ([{"language": "Python", "bytes": 80}], None)):
            module = ModuleResult("languages", "Languages", [], values, measurements={
                "languages": Measurement(unit="bytes", denominator=denominator)})
            output = self.output(self.plan(30, 40, document=self.build(module), details=True))
            self.assertNotIn("%", output)
            self.assertNotIn("━", output)
            self.assertIn("No language measurements" if not values else "0 bytes" if denominator == 0 else "80 bytes", output)

    def test_footer_selects_complete_hints_at_every_narrow_width(self):
        document = self.build(ModuleResult("plugin", "Plugin", ["long line " * 100], {}))
        for width in range(1, 52):
            plan = self.plan(width, 8, document=document)
            hint = plan.rows[-1].text
            self.assertTrue(plan.condensed)
            self.assertIn(hint, ("More enabled content: --details", "Run --details", "--details", "…"))
            self.assertLessEqual(cell_width(hint), width)
            if width >= 9:
                self.assertIn("--details", hint)
            else:
                self.assertEqual(hint, "…")
        self.assertEqual(self.plan(30, 8, document=document).rows[-1].text, "Run --details")
        self.assertEqual(self.plan(31, 8, document=document).rows[-1].text, "More enabled content: --details")

    def test_generic_plugin_flags_wrap_as_whole_tokens(self):
        flags = ("--details", "--presentation", "--no-color", "--token")
        lines = ["x" * 25 + " " + flag + " rest" for flag in flags]
        module = ModuleResult("plugin", "Plugin", ["  indented", "", *lines], {"raw": lines})
        plan = self.plan(30, 40, document=self.build(module), details=True)
        tokens = re.findall(r"--[A-Za-z][A-Za-z0-9-]*", self.output(plan))
        self.assertEqual(tokens, list(flags))
        self.assertTrue(all(cell_width(row.text) <= 30 for row in plan.rows))
        self.assertIn("  indented", self.output(plan))
        self.assertEqual(module.data["raw"], lines)

    def test_bounded_plugin_text_does_not_publish_a_partial_flag(self):
        module = ModuleResult("plugin", "Plugin", ["x " * 56 + "--presentation modern"], {})
        document = self.build(module)
        compact = self.output(self.plan(30, 12, document=document))
        self.assertEqual(re.findall(r"--[A-Za-z][A-Za-z0-9-]*", compact), ["--details"])
        expanded = self.output(self.plan(30, 12, document=document, details=True))
        self.assertIn("--presentation", expanded)

    def test_long_urls_containing_double_hyphens_are_not_treated_as_flags(self):
        url = "https://example.test/--" + "longpath" * 10 + "?x=--" + "value" * 10
        module = ModuleResult("plugin", "Plugin", [url], {})
        plan = self.plan(30, 40, document=self.build(module), details=True)
        self.assertEqual("".join(row.text for row in plan.rows[1:]), url)

    def test_quoted_action_flags_also_wrap_whole(self):
        module = ModuleResult("plugin", "Plugin", ["x" * 26 + " (--details)", "x" * 26 + " `--no-color`"], {})
        plan = self.plan(30, 40, document=self.build(module), details=True)
        self.assertEqual(re.findall(r"--[A-Za-z][A-Za-z0-9-]*", self.output(plan)), ["--details", "--no-color"])

    def test_auth_instructions_preserve_flags_environment_names_and_config_keys(self):
        for env in ("GITHUB_TOKEN", "GITLAB_TOKEN", "BITBUCKET_TOKEN", "GITEA_TOKEN", "FORGEJO_TOKEN", "CODEBERG_TOKEN"):
            module = ModuleResult("pinned", "Pinned", [f"requires --token, {env}, or profile.token_command"], {},
                                  measurements={"pinned": Measurement(availability="auth_required")})
            plan = self.plan(30, 40, document=self.build(module), details=True)
            for token in ("--token", env, "profile.token_command"):
                self.assertTrue(any(token in row.text for row in plan.rows), (env, token))

    def test_clipped_biography_does_not_publish_a_partial_flag(self):
        user = {**self.user, "bio": "a" * 20 + " --details more words " * 5}
        document = build_profile_document(user, [ModuleResult("identity", "Identity", [], {"user": user})], provider="github")
        for details in (False, True):
            output = self.output(self.plan(30, 20, document=document, details=details))
            tokens = re.findall(r"--[A-Za-z][A-Za-z0-9-]*", output)
            self.assertTrue(tokens)
            self.assertTrue(all(token == "--details" for token in tokens))

    def test_flags_wider_than_entire_pane_use_a_marker_instead_of_fragments(self):
        module = ModuleResult("plugin", "Plugin", ["--presentation"], {})
        output = self.output(self.plan(8, 40, document=self.build(module), details=True))
        self.assertIn("…", output)
        self.assertNotIn("--", output)
        self.assertEqual(module.lines, ["--presentation"])

    def test_narrow_activity_is_summary_or_bounded_sparkline(self):
        plan = self.plan(30, 40)
        self.assertIn("2025-11-06 – 2026-01-28", self.output(plan, "contributions"))
        self.assertFalse(any(s.role == "accent" for r in plan.rows if r.module == "contributions" for s in r.spans))
        for width in (30, 40, 50):
            expanded = self.plan(width, 40, details=True)
            charts = [r for r in expanded.rows if r.module == "contributions" and any(s.role == "accent" for s in r.spans)]
            self.assertTrue(charts)
            self.assertTrue(all(cell_width(r.text) <= width * 2 // 3 for r in charts))

    def test_unknown_dates_and_zero_survive_narrow_activity(self):
        data = [{"contributionDays": [{"date": "2026-01-01", "contributionCount": 0},
                                     {"date": "2026-01-03", "contributionCount": 4}]}]
        module = ModuleResult("contributions", "Contributions", [], data, measurements={
            "contributions": Measurement(4, "gitea", "activity actions", coverage="unknown", start="2026-01-01", end="2026-01-03")})
        output = self.output(self.plan(30, 40, document=self.build(module), details=True))
        self.assertIn("·?█", output)
        self.assertIn("unknown coverage", output)
        self.assertIn("2026-01-01 – 2026-01-03", output)
        self.assertIn("activity actions", " ".join(output.split()))

    def test_repositories_and_followers_are_primary_gists_stay_secondary(self):
        rows = [r for r in self.plan(80, 40, details=True).rows if r.module == "stats"]
        primary = " ".join(s.text for r in rows for s in r.spans if s.role == "stat")
        secondary = " ".join(s.text for r in rows for s in r.spans if s.role == "muted")
        self.assertIn("42 public repos", primary)
        self.assertIn("1,280 followers", primary)
        self.assertNotIn("gists", primary)
        self.assertIn("0 gists", secondary)
        self.assertIn("87 following", secondary)
        self.assertIn("years on platform", secondary)

    def test_partial_streak_window_is_explained_once(self):
        _, _, document = fixture(partial=True)
        output = self.output(self.plan(100, 40, document=document, details=True), "streaks")
        self.assertEqual(output.count("unknown coverage"), 1)
        self.assertIn("Observed window:", output)
        self.assertIn("longest observed streak", output)
        self.assertNotIn("ever", output)

    def test_primary_section_breaks_remain_within_row_budget(self):
        for width, height in ((80, 24), (100, 30), (140, 40)):
            plan = self.plan(width, height)
            for name in ("languages", "contributions"):
                index = next(i for i, row in enumerate(plan.rows) if row.module == name)
                self.assertEqual(plan.rows[index - 1].text, "")
            self.assertLessEqual(plan.height, height - 2)
            self.assertNotIn("\n\n\n", self.output(plan))

    def test_unicode_missing_values_and_generic_content_fit_required_sizes(self):
        user = {**self.user, "name": "林明 👩🏽‍💻", "bio": "cafe\u0301 世界 مرحبا " * 100,
                "followers": 0, "following": None}
        plugin = ModuleResult("plugin", "Plugin", ["safe \x1b]0;title\a notes", "  --details"], object())
        modules = [ModuleResult("identity", "Identity", [], {"user": user}),
                   ModuleResult("stats", "Stats", [], {"user": user}), self.modules[2], self.modules[3], plugin]
        document = build_profile_document(user, modules, provider="github")
        for width, height in DIMENSIONS:
            for details in (False, True):
                plan = self.plan(width, height, document=document, details=details)
                self.assertTrue(all(cell_width(row.text) <= width for row in plan.rows))
                self.assertNotIn("\x1b", self.output(plan))
                if not details:
                    self.assertLessEqual(plan.height, height - 2)
                else:
                    self.assertIn("unavailable following", " ".join(self.output(plan).split()))
                    self.assertIn("0 followers", self.output(plan))
                    self.assertIn("--details", self.output(plan, "plugin"))
                    order = list(dict.fromkeys(r.module for r in plan.rows if r.module))
                    self.assertEqual(order, [m.name for m in modules])

    def test_secondary_text_follows_terminal_foreground_not_dark_theme_gray(self):
        for theme in ("dracula", "nord", "gruvbox", "catppuccin-mocha"):
            config = preset_config("minimal")
            config["display"].update(presentation="modern", details=True, theme=theme)
            config["_color_force"] = "on"
            with mock.patch("gitfetch.render.shutil.get_terminal_size", return_value=os.terminal_size((100, 40))):
                output = render_output(config, self.user, self.modules, "ansi", document=self.document)
            handle = next(line for line in output.splitlines() if "@alex-dev" in line)
            counts = next(line for line in output.splitlines() if "0 gists" in line)
            self.assertNotIn("\x1b", handle)
            self.assertNotIn("\x1b", counts)
            self.assertNotIn("\x1b[48;", output)

    def test_explicit_no_color_preview_has_no_control_sequences(self):
        output = preview("no-color", ansi=True)
        self.assertNotIn("\x1b", output)
        self.assertIn("━", output)
        self.assertIn("73.0%", output)

    def test_planning_does_not_download_or_execute_plugins(self):
        failure = AssertionError("unexpected effect")
        with (mock.patch("requests.Session.request", side_effect=failure),
              mock.patch("gitfetch.render._load_avatar", side_effect=failure),
              mock.patch("shutil.get_terminal_size", side_effect=failure)):
            plan_profile(self.document, Viewport(30, 40), Preferences(), AvatarGeometry(96, 96), reference_date=REFERENCE)
