"""Pure responsive planning: semantic, geometric and safety invariants."""
import copy
import unittest
from dataclasses import replace
from datetime import date
from unittest import mock

from modern_fixtures import DIMENSIONS, REFERENCE, fixture

from gitfetch.layout import AvatarGeometry, Preferences, Viewport, plan_profile
from gitfetch.modules.builtin import ModuleResult
from gitfetch.presentation import build_profile_document
from gitfetch.semantics import Measurement
from gitfetch.terminal_text import cell_width


def text(plan):
    return "\n".join(row.text for row in plan.rows)


SQUARE_AVATAR = AvatarGeometry(96, 96)


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.user, self.modules, self.document = fixture()

    def plan(self, columns=80, rows=24, document=None, avatar=SQUARE_AVATAR, **preferences):
        return plan_profile(document or self.document, Viewport(columns, rows), Preferences(**preferences), avatar,
                            reference_date=REFERENCE)

    def build(self, *modules, provider="github"):
        return build_profile_document(self.user, modules, provider=provider)

    def test_all_required_viewports_bound_width_and_height(self):
        for columns, rows in DIMENSIONS:
            with self.subTest(columns=columns, rows=rows):
                plan = self.plan(columns, rows)
                self.assertLessEqual(plan.height, rows - 2)
                for row in plan.rows:
                    self.assertLessEqual(cell_width(row.text), plan.text_width)
                    prefix = plan.avatar_width + 3 if plan.composition == "split" else 0
                    self.assertLessEqual(cell_width(row.text) + prefix + 2 * plan.margin, columns)
                self.assertEqual(plan, self.plan(columns, rows))

    def test_standard_target_is_at_most_22_rows(self):
        self.assertLessEqual(self.plan().height, 22)

    def test_wide_short_avatar_is_height_limited(self):
        short, tall = self.plan(200, 15), self.plan(200, 60)
        self.assertLessEqual(short.avatar_rows, 6)
        self.assertLess(short.avatar_rows, tall.avatar_rows)
        self.assertLessEqual(tall.avatar_width, 34)

    def test_narrow_short_omits_avatar(self):
        self.assertEqual(self.plan(40, 12).composition, "text")
        self.assertIn("Alex Rivera", text(self.plan(40, 12)))

    def test_missing_avatar_produces_full_width_text(self):
        plan = self.plan(80, 24, avatar=None)
        self.assertEqual((plan.composition, plan.avatar_width, plan.text_width), ("text", 0, 80))

    def test_oversized_configured_avatar_is_capped(self):
        plan = self.plan(200, 60, avatar_width=1000000)
        self.assertLessEqual(plan.avatar_width, 34)
        self.assertLessEqual(plan.avatar_rows, 16)

    def test_configured_small_avatar_width_is_authoritative(self):
        self.assertLessEqual(self.plan(140, 40, avatar_width=12).avatar_width, 12)
        self.assertEqual(self.plan(140, 40, avatar_width=4).composition, "text")

    def test_short_content_does_not_get_a_disproportionate_avatar(self):
        document = self.build(ModuleResult("plugin", "Plugin", ["a short line"], {}))
        for layout in ("split", "stack"):
            plan = self.plan(140, 40, document=document, layout=layout)
            self.assertLessEqual(plan.avatar_rows, 4)
            self.assertIn("a short line", text(plan))

    def test_split_and_stack_preferences_remain_distinct(self):
        self.assertEqual(self.plan(100, 40, layout="split").composition, "split")
        self.assertEqual(self.plan(100, 40, layout="stack").composition, "stack")
        self.assertEqual(self.plan(40, 12, layout="stack").composition, "text")

    def test_all_avatar_styles_preserve_source_geometry(self):
        for style in ("ascii", "halfblock", "braille"):
            for geometry in (AvatarGeometry(100, 50), AvatarGeometry(50, 100), AvatarGeometry(1, 1000)):
                with self.subTest(style=style, geometry=geometry):
                    plan = self.plan(140, 40, avatar=geometry, avatar_style=style)
                    if plan.avatar_width:
                        self.assertEqual(plan.avatar_rows, geometry.rows_at(plan.avatar_width, style))
                        self.assertLessEqual(plan.avatar_rows, 16)

    def test_extreme_margins_are_clamped_to_leave_readable_content(self):
        for columns, rows in DIMENSIONS:
            plan = self.plan(columns, rows, margin=1000000)
            self.assertGreaterEqual(plan.text_width, 20)
            self.assertLessEqual(max((cell_width(r.text) for r in plan.rows), default=0) + 2 * plan.margin, columns)
            self.assertLessEqual(plan.height, rows - 2)

    def test_tiny_or_invalid_dimensions_do_not_overflow(self):
        for columns, rows in ((1, 1), (2, 2), (0, 0), (-1, -1), (8, 5)):
            plan = self.plan(columns, rows)
            self.assertLessEqual(plan.height, max(1, rows - 2))
            self.assertTrue(all(cell_width(r.text) <= max(1, columns) for r in plan.rows))

    def test_details_preserves_all_sections_and_all_generic_lines(self):
        plugin = ModuleResult("plugin", "Plugin", [f"enabled detail {i}" for i in range(100)], {})
        document = self.build(*self.modules, plugin)
        plan = self.plan(40, 12, document=document, details=True)
        self.assertGreater(plan.height, 12)
        self.assertEqual(plan.omitted_modules, ())
        self.assertFalse(plan.condensed)
        self.assertIn("enabled detail 99", text(plan))
        self.assertNotIn("--details", text(plan))
        self.assertEqual(list(dict.fromkeys(r.module for r in plan.rows if r.module)), [s.name for s in document.sections])

    def test_omissions_have_an_explicit_details_indicator(self):
        plan = self.plan(40, 12)
        self.assertTrue(plan.condensed)
        self.assertIn("--details", text(plan))
        self.assertTrue(plan.omitted_modules)

    def test_tiny_activity_summary_retains_its_date_window(self):
        output = text(self.plan(40, 12))
        self.assertIn("2025-11-06 – 2026-01-28", output)
        self.assertIn("complete", output)

    def test_impossible_budget_omits_activity_instead_of_detaching_total_from_dates(self):
        plan = self.plan(40, 12, margin=1000000)
        contribution_rows = [row for row in plan.rows if row.module == "contributions"]
        if contribution_rows:
            output = " ".join(row.text for row in contribution_rows)
            self.assertIn("2025-11-06", output)
            self.assertIn("2026-01-28", output)
        else:
            self.assertIn("contributions", plan.omitted_modules)

    def test_generic_plugin_indentation_and_empty_lines_are_preserved(self):
        module = ModuleResult("plugin", "Plugin", ["root", "  child", "", "    nested"], {})
        plan = self.plan(document=self.build(module), details=True)
        self.assertEqual([row.text for row in plan.rows], ["Plugin", "root", "  child", "", "    nested"])

    def test_exact_width_generic_line_is_not_clipped(self):
        module = ModuleResult("plugin", "Plugin", ["x" * 40], {})
        output = text(self.plan(40, 12, document=self.build(module), details=True))
        self.assertIn("x" * 40, output)
        self.assertNotIn("…", output)

    def test_future_account_creation_does_not_fabricate_zero_age(self):
        module = ModuleResult("stats", "Stats", [], {"user": {"followers": 0, "created_at": "2099-01-01"}})
        self.assertNotIn("days on platform", text(self.plan(document=self.build(module), details=True)))

    def test_no_indicator_when_nothing_is_condensed(self):
        document = self.build(ModuleResult("plugin", "Plugin", ["one complete line"], {}))
        plan = self.plan(80, 24, document=document, avatar=None)
        self.assertFalse(plan.condensed)
        self.assertNotIn("--details", text(plan))

    def test_long_bio_and_url_wrap_without_eliminating_split(self):
        user = {**self.user, "bio": "very long biography " * 100, "blog": "https://example.test/" + "x" * 300}
        document = build_profile_document(user, [ModuleResult("identity", "Identity", [], {"user": user})], provider="github")
        plan = self.plan(100, 30, document=document)
        self.assertEqual(plan.composition, "split")
        self.assertTrue(plan.condensed)
        self.assertTrue(all(cell_width(row.text) <= plan.text_width for row in plan.rows))

    def test_unicode_graphemes_and_controls_are_safe(self):
        samples = ("alice", "世界开发者", "e\u0301", "👩🏽‍💻👨‍👩‍👧‍👦", "مرحبا بالعالم", "a\tline\nnext\rreturn",
                   "safe\x1b[2J\x1b]0;title\aOK", "x\x1b]8;;https://evil\x1b\\link\x1b]8;;\x1b\\")
        for value in samples:
            document = self.build(ModuleResult("plugin", "Plugin", [value * 4], None))
            plan = self.plan(20, 12, document=document, details=True)
            output = text(plan)
            self.assertNotIn("\x1b", output)
            self.assertNotIn("\r", output)
            self.assertNotIn("\t", output)
            self.assertTrue(all(cell_width(row.text) <= 20 for row in plan.rows))
        self.assertIn("e\u0301", text(self.plan(document=self.build(ModuleResult("p", "P", ["e\u0301"], {})), details=True)))

    def test_language_percentage_uses_full_denominator_not_displayed_top_five(self):
        plan = self.plan(140, 40, details=True)
        output = text(plan)
        self.assertIn("73.0%", output)
        self.assertIn("1.0%", output)
        self.assertNotIn("73.7%", output)
        self.assertNotIn("Other", output)  # Module selection limit remains authoritative.

    def test_gitlab_multilabel_repository_prevalence_not_bytes(self):
        _, _, document = fixture("gitlab")
        output = text(self.plan(140, 40, document=document, details=True))
        self.assertIn("repository prevalence", output)
        self.assertIn("18/20 repos", output)
        self.assertIn("12/20 repos", output)
        self.assertNotIn("90.0%", output)

    def test_bitbucket_primary_language_counts_not_byte_percentages(self):
        _, _, document = fixture("bitbucket")
        output = text(self.plan(140, 40, document=document, details=True))
        self.assertIn("primary-language repos", output)
        self.assertIn("12/20 repos", output)
        self.assertNotIn("60.0%", output)

    def test_unknown_language_denominator_is_a_labeled_list(self):
        module = ModuleResult("languages", "Languages", [], [{"language": "Python", "bytes": 80}])
        output = text(self.plan(100, 30, document=self.build(module), details=True))
        self.assertIn("80 bytes", output)
        self.assertNotIn("%", output)
        self.assertNotIn("█", output)

    def test_zero_and_empty_successful_language_measurements(self):
        measurement = Measurement(provider="github", unit="bytes", denominator=0, coverage="complete")
        for entries in ([], [{"language": "Python", "bytes": 0}]):
            module = ModuleResult("languages", "Languages", [], entries, measurements={"languages": measurement})
            output = text(self.plan(document=self.build(module), details=True))
            self.assertNotIn("%", output)
            self.assertIn("0 bytes" if entries else "No language measurements", output)

    def test_language_partial_coverage_is_visible(self):
        output = text(self.plan(140, 40))
        self.assertIn("partial", output)
        self.assertIn("20/42 repos scanned", output)
        self.assertIn("selected repos", output)

    def test_details_preserves_long_language_name(self):
        name = "Very long language name with CJK 世界 " * 4
        module = ModuleResult("languages", "Languages", [], [{"language": name, "bytes": 12}], measurements={
            "languages": Measurement(provider="github", unit="bytes", denominator=100, coverage="complete")})
        output = text(self.plan(80, 24, document=self.build(module), details=True))
        self.assertIn("Very long language name with CJK 世界", output)
        self.assertIn("12.0%", output)

    def test_contributions_keep_zero_unknown_gaps_dates_and_scope(self):
        data = [{"contributionDays": [{"date": "2026-01-01", "contributionCount": 0},
                                     {"date": "2026-01-03", "contributionCount": 4}]}]
        for provider in ("gitea", "forgejo", "codeberg"):
            measurement = Measurement(4, provider, "activity actions", "returned heatmap records", coverage="unknown",
                                      start="2026-01-01", end="2026-01-03")
            document = self.build(ModuleResult("contributions", "Contributions", [], data,
                                              measurements={"contributions": measurement}), provider=provider)
            output = text(self.plan(40, 24, document=document, details=True))
            self.assertIn("·?█", output)
            self.assertIn("2026-01-01 – 2026-01-03", output)
            self.assertIn("unknown coverage", " ".join(output.split()))
            self.assertIn("activity actions", output)
            self.assertNotIn("year", output)

    def test_calendar_is_chronological_with_weekday_labels(self):
        output = text(self.plan(140, 40))
        self.assertIn("2025-11-06 – 2026-01-28", output)
        self.assertLess(output.index("Su  "), output.index("Sa  "))
        self.assertIn("· zero  ? unknown", output)

    def test_sparse_centuries_do_not_materialize_unknown_daily_calendars(self):
        data = [{"contributionDays": [{"date": "1900-01-01", "contributionCount": 0},
                                     {"date": "2026-01-28", "contributionCount": 4}]}]
        document = self.build(ModuleResult("contributions", "Contributions", [], data))
        for width in (40, 100):
            plan = self.plan(width, 40, document=document, avatar=None, details=True)
            self.assertLess(plan.height, 50)
            self.assertIn("Unknown dates:", text(plan))
            self.assertIn("2026-01-28", text(plan))

    def test_extreme_valid_calendar_dates_do_not_overflow(self):
        for value in ("0001-01-01", "9999-12-31"):
            data = [{"contributionDays": [{"date": value, "contributionCount": 0}]}]
            document = self.build(ModuleResult("contributions", "Contributions", [], data))
            for details in (False, True):
                plan = self.plan(140, 40, document=document, details=details)
                self.assertIn(value, text(plan))

    def test_missing_calendar_not_presented_as_zero(self):
        for availability in ("unavailable", "auth_required", "unsupported"):
            measurement = Measurement(provider="github", availability=availability)
            document = self.build(ModuleResult("contributions", "Contributions", [availability], [], measurements={"contributions": measurement}))
            output = text(self.plan(document=document, details=True))
            self.assertNotIn("0 contributions", output)
            self.assertIn("auth_required" if availability == "auth_required" else availability, output)

    def test_real_zero_and_missing_statistics_are_distinct(self):
        user = {**self.user, "followers": 0, "following": None}
        module = ModuleResult("stats", "Stats", [], {"user": user})
        output = text(self.plan(document=self.build(module), details=True))
        self.assertIn("0 followers", output)
        self.assertIn("unavailable following", output)
        self.assertNotIn("0 following", output)

    def test_unsupported_and_auth_required_numeric_metrics_do_not_become_zero(self):
        metadata = {"custom": Measurement(provider="github", availability="auth_required", reason="token required"),
                    "following": Measurement(provider="github", availability="unsupported")}
        output = text(self.plan(document=self.build(ModuleResult("stats", "Stats", [], {}, measurements=metadata)), details=True))
        self.assertIn("auth required", output)
        self.assertIn("unsupported", output)
        self.assertNotIn("0 ", output)

    def test_filtered_repository_scope_is_not_relabelled_as_public_total(self):
        metadata = {"public_repos": Measurement(35, "github", "repositories", "selected repositories", coverage="complete")}
        output = text(self.plan(document=self.build(ModuleResult("stats", "Stats", [], {}, measurements=metadata)), details=True))
        self.assertIn("35 selected repositories", output)
        self.assertNotIn("35 public repos", output)

    def test_additional_metric_units_and_selected_scope_are_not_discarded(self):
        metadata = {"storage": Measurement(35, "gitea", "KB", "selected repositories", coverage="complete")}
        output = text(self.plan(document=self.build(ModuleResult("stats", "Stats", [], {}, measurements=metadata)), details=True))
        self.assertIn("35 KB storage (selected repositories)", output)

    def test_streaks_are_observed_and_window_limited(self):
        output = text(self.plan(140, 40, details=True))
        self.assertIn("current observed streak", output)
        self.assertIn("longest observed streak", output)
        self.assertIn("Observed window: 2025-11-06 – 2026-01-28", output)
        self.assertNotIn("ever", output)

    def test_account_age_uses_explicit_reference_date(self):
        first = self.plan(details=True)
        second = plan_profile(self.document, Viewport(), Preferences(details=True), reference_date=date(2027, 1, 28))
        self.assertIn("7 years on platform", text(first))
        self.assertIn("8 years on platform", text(second))
        self.assertNotIn("hours", text(first))

    def test_pinned_recent_and_generic_plugins_remain_visible_in_details(self):
        plugin = ModuleResult("plugin", "My plugin", ["UNSTRUCTURED SENTINEL"], object())
        plan = self.plan(document=self.build(*self.modules, plugin), details=True)
        output = text(plan)
        for value in ("alex-dev/gitfetch", "0 stars", "PushEvent", "2026-01-28T09:00:00Z", "UNSTRUCTURED SENTINEL"):
            self.assertIn(value, output)

    def test_pinned_gist_fallback_not_discarded(self):
        module = ModuleResult("pinned", "Pinned", ["gist: useful shell snippet"], [{"__typename": "Gist", "name": "snippet"}])
        self.assertIn("gist: useful shell snippet", text(self.plan(document=self.build(module), details=True)))

    def test_hidden_and_unselected_modules_do_not_reappear(self):
        hidden = ModuleResult("identity", "Identity", ["PRIVATE SENTINEL"], {"user": self.user}, hidden=True)
        document = self.build(hidden, ModuleResult("plugin", "Plugin", ["hello"], {}))
        output = text(self.plan(document=document, details=True))
        self.assertNotIn("Alex Rivera", output)
        self.assertNotIn("PRIVATE SENTINEL", output)
        self.assertNotIn("Languages", output)

    def test_user_defined_order_is_preserved_even_when_identity_is_not_first(self):
        modules = [self.modules[2], ModuleResult("plugin", "Plugin", ["hello"], {}), self.modules[0], self.modules[1]]
        plan = self.plan(document=self.build(*modules), details=True)
        self.assertEqual(list(dict.fromkeys(row.module for row in plan.rows if row.module)), [m.name for m in modules])

    def test_module_token_notice_keeps_actionable_text(self):
        module = ModuleResult("pinned", "Pinned", ["requires --token, GITHUB_TOKEN, or profile.token_command"], {},
                              measurements={"pinned": Measurement(availability="auth_required")})
        output = text(self.plan(document=self.build(module), details=True))
        self.assertIn("GITHUB_TOKEN", output)
        self.assertIn("--token", output)

    def test_planner_has_no_io_terminal_clock_or_plugin_execution(self):
        failure = AssertionError("planner performed an effect")
        with (mock.patch("requests.Session.request", side_effect=failure),
              mock.patch("builtins.open", side_effect=failure),
              mock.patch("shutil.get_terminal_size", side_effect=failure),
              mock.patch("gitfetch.render._load_avatar", side_effect=failure),
              mock.patch("gitfetch.cli.MODULE_HANDLERS", {})):
            self.plan()

    def test_source_data_and_document_are_not_mutated(self):
        before = copy.deepcopy((self.user, self.modules))
        sections = self.document.sections
        self.plan(details=True)
        self.assertEqual((self.user, self.modules), before)
        self.assertEqual(self.document.sections, sections)

    def test_empty_document_stays_empty(self):
        document = replace(self.document, sections=(), notices=(), avatar_reference=None)
        plan = self.plan(document=document, avatar=None)
        self.assertEqual(plan.rows, ())
        self.assertFalse(plan.condensed)

    def test_unknown_plugin_objects_are_not_stringified(self):
        class Opaque:
            def __str__(self):
                raise AssertionError("opaque data must not be rendered")
        module = ModuleResult("plugin", "Plugin", ["safe fallback"], Opaque())
        self.assertIn("safe fallback", text(self.plan(document=self.build(module), details=True)))

    def test_many_modules_fit_normal_height_but_details_keeps_them(self):
        modules = [ModuleResult(f"plugin{i}", f"Plugin {i}", ["x" * 500] * 10, {}) for i in range(50)]
        document = self.build(*modules)
        self.assertLessEqual(self.plan(document=document).height, 22)
        detailed = self.plan(document=document, details=True)
        self.assertEqual(len({row.module for row in detailed.rows if row.module}), 50)
