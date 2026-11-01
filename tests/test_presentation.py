"""Semantic document construction, independently of layout and output formats."""
import copy
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import date
from types import MappingProxyType
from unittest import mock

from gitfetch.github_api import GitHubContext
from gitfetch.modules.builtin import ModuleResult
from gitfetch.presentation import (
    ContributionActivity,
    LanguageDistribution,
    MetricGroup,
    RecentActivity,
    RepositoryList,
    build_profile_document,
)
from gitfetch.semantics import Measurement, RepositoryCoverage


def profile():
    return {"login": "alice", "name": "Alice", "bio": "Builds things", "company": "Example",
            "location": "Singapore", "blog": "https://alice.test", "avatar_url": "https://alice.test/avatar.png",
            "html_url": "https://github.test/alice", "public_repos": 3, "followers": 0,
            "following": None, "public_gists": 0, "created_at": "2020-01-01T00:00:00Z"}


def weeks(*observations):
    return [{"contributionDays": [{"date": day, "contributionCount": count} for day, count in observations]}]


class PresentationTests(unittest.TestCase):
    def setUp(self):
        self.user = profile()
        self.context = GitHubContext("alice", self.user, [], [], False, None, {})
        self.network = mock.patch("requests.Session.request", side_effect=AssertionError("unexpected network"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def build(self, *modules, provider="github", context=None):
        return build_profile_document(self.user, modules, provider=provider,
                                      instance="https://git.example/api", context=context)

    def test_normal_github_identity_and_stats(self):
        identity = ModuleResult("identity", "Identity", ["@alice", "Alice"], {"user": self.user})
        stats = ModuleResult("stats", "Stats", ["0 followers"], {"user": self.user, "viewer_mode": False})
        document = self.build(identity, stats, context=self.context)
        self.assertEqual(document.username, "alice")
        self.assertEqual(document.identity.display_name, "Alice")
        self.assertEqual(document.identity.company, "Example")
        self.assertEqual(document.identity.location, "Singapore")
        self.assertEqual(document.identity.website, "https://alice.test")
        self.assertEqual(document.identity.url, "https://github.test/alice")
        self.assertEqual(document.avatar_reference, self.user["avatar_url"])
        self.assertIsInstance(document.sections[1].content, MetricGroup)
        metrics = {m.identifier: m for m in document.sections[1].content.metrics}
        self.assertEqual(metrics["followers"].measurement.value, 0)
        self.assertIsNone(metrics["following"].measurement.value)

    def test_codeberg_and_custom_instance_identity(self):
        document = self.build(ModuleResult("identity", "Identity", [], {"user": self.user}), provider="codeberg")
        self.assertEqual(document.identity.provider, "codeberg")
        self.assertEqual(document.identity.instance, "https://git.example/api")
        self.assertEqual(document.provider, "codeberg")

    def test_identity_uses_structured_module_payload(self):
        document = self.build(ModuleResult("identity", "Identity", ["fake display name"], {"user": {"login": "bob", "name": "Robert"}}))
        self.assertEqual(document.identity.username, "bob")
        self.assertEqual(document.identity.display_name, "Robert")
        self.assertEqual(document.username, "alice")  # Render target is independent of selected identity content.

    def test_identity_not_selected_is_not_a_display_section(self):
        document = self.build(ModuleResult("plugin", "Plugin", ["hello"], []))
        self.assertIsNone(document.identity)
        self.assertEqual([s.name for s in document.sections], ["plugin"])

    def test_metrics_do_not_parse_english_lines_or_fabricate_values(self):
        measured = Measurement(None, "github", "count", "followers", "unavailable", reason="missing")
        result = ModuleResult("stats", "Stats", ["999 followers"], {"user": {"followers": 500}}, measurements={"followers": measured})
        document = self.build(result)
        followers = next(m for m in document.sections[0].content.metrics if m.identifier == "followers")
        self.assertIs(followers.measurement, measured)
        self.assertIsNone(followers.measurement.value)

    def test_zero_and_missing_have_distinct_availability(self):
        document = self.build(ModuleResult("stats", "Stats", [], {"user": self.user}))
        values = {m.identifier: m.measurement for m in document.sections[0].content.metrics}
        self.assertEqual((values["followers"].value, values["followers"].availability), (0, "available"))
        self.assertEqual((values["following"].value, values["following"].availability), (None, "unavailable"))

    def test_measurement_not_mentioned_in_lines_is_retained(self):
        measured = Measurement(12, "github", "count", "custom scope", source="fixture", coverage="partial", denominator=20)
        document = self.build(ModuleResult("stats", "Stats", [], {}, measurements={"custom_metric": measured}))
        self.assertEqual(document.sections[0].content.metrics[0].identifier, "custom_metric")
        self.assertIs(document.sections[0].measurements["custom_metric"], measured)

    def test_stats_can_use_context_provenance_without_replacing_module_metadata(self):
        self.context.measurements["followers"] = Measurement(None, "github", availability="auth_required")
        document = self.build(ModuleResult("stats", "Stats", [], {"user": self.user}), context=self.context)
        self.assertEqual(document.sections[0].measurements["followers"].availability, "auth_required")
        supplied = Measurement(0, "github", scope="followers", coverage="complete")
        document = self.build(ModuleResult("stats", "Stats", [], {"user": self.user}, measurements={"followers": supplied}), context=self.context)
        self.assertIs(document.sections[0].measurements["followers"], supplied)

    def test_unsupported_module_has_a_notice_and_no_valid_data(self):
        measured = Measurement(provider="gitlab", availability="unsupported", reason="no public calendar")
        result = ModuleResult("contributions", "Contributions", ["unsupported on GitLab"], {"unsupported": True}, measurements={"contributions": measured})
        document = self.build(result, provider="gitlab")
        self.assertIsNone(document.sections[0].content)
        self.assertEqual(len(document.notices), 1)
        self.assertEqual(document.notices[0].measurement.availability, "unsupported")

    def test_authentication_notice_preserves_actionable_fallback(self):
        result = ModuleResult("pinned", "Pinned", ["requires --token or GITHUB_TOKEN"], {"requires_token": True}, requires_token=True)
        document = self.build(result)
        self.assertIsNone(document.sections[0].content)
        self.assertEqual(document.notices[0].measurement.availability, "auth_required")
        self.assertIn("GITHUB_TOKEN", document.sections[0].lines[0])

    def test_requires_token_flag_is_not_an_unavailable_measurement(self):
        node = {"__typename": "Repository", "nameWithOwner": "alice/project", "stargazerCount": 0}
        document = self.build(ModuleResult("pinned", "Pinned", [], [node], requires_token=True))
        self.assertIsInstance(document.sections[0].content, RepositoryList)
        self.assertFalse(any(n.measurement.availability == "auth_required" for n in document.notices))

    def test_legacy_unsupported_payload_is_recognized(self):
        result = ModuleResult("pinned", "Pinned", ["unsupported"], {"unsupported": True, "provider": "bitbucket", "reason": "no pinned API"})
        document = self.build(result, provider="bitbucket")
        self.assertEqual(document.notices[0].measurement.availability, "unsupported")
        self.assertEqual(document.notices[0].measurement.reason, "no pinned API")

    def test_all_coverage_values_are_preserved(self):
        for coverage in ("complete", "partial", "unknown"):
            with self.subTest(coverage=coverage):
                measurement = Measurement(0, "github", scope="fixture", coverage=coverage)
                document = self.build(ModuleResult("plugin", "Plugin", [], None, measurements={"metric": measurement}))
                self.assertEqual(document.sections[0].measurements["metric"].coverage, coverage)
                self.assertEqual(any(n.kind == "coverage" for n in document.notices), coverage != "complete")

    def test_duplicate_notices_are_grouped_without_losing_subjects(self):
        measurement = Measurement(provider="github", scope="followers", availability="unavailable", reason="not supplied")
        document = self.build(ModuleResult("one", "One", [], {}, measurements={"followers": measurement}),
                              ModuleResult("two", "Two", [], {}, measurements={"followers": measurement}))
        self.assertEqual(len(document.notices), 1)
        self.assertEqual(document.notices[0].subjects, (("one", "followers"), ("two", "followers")))

    def language_result(self, provider="github", unit="bytes", scope="selected repository language bytes"):
        totals = (("Python", 50), ("Go", 20), ("C", 10), ("Shell", 8), ("Rust", 7), ("Ruby", 5))
        if unit == "repositories":
            totals = (("Python", 5), ("Go", 2), ("C", 1), ("Shell", 1), ("Rust", 1), ("Ruby", 1))
        metadata = Measurement(sum(value for _, value in totals), provider, unit, scope, source="fixture languages", coverage="partial",
                               sample_size=8, denominator=100 if unit == "bytes" else 8,
                               languages=tuple(name for name, _ in totals), language_totals=totals,
                               eligible_repositories=20, attempted=10, failed=2, missing=3,
                               sampling_policy="first 10 repositories", complete_profile=False)
        result = ModuleResult("languages", "Languages", ["not parsed"], [{"language": name, unit: value} for name, value in totals[:5]],
                              measurements={"languages": metadata})
        return result, metadata

    def test_languages_top_five_does_not_lose_full_denominator_or_totals(self):
        result, metadata = self.language_result()
        document = self.build(result)
        distribution = document.sections[0].content
        self.assertIsInstance(distribution, LanguageDistribution)
        self.assertEqual(len(distribution.selected), 5)
        self.assertEqual(sum(entry.value for entry in distribution.selected), 95)
        self.assertEqual(distribution.measurement.denominator, 100)
        self.assertEqual(len(distribution.totals), 6)
        self.assertEqual(distribution.totals[-1].language, "Ruby")
        self.assertIs(distribution.measurement, metadata)

    def test_language_sample_details_are_not_discarded(self):
        result, metadata = self.language_result()
        distribution = self.build(result).sections[0].content
        self.assertEqual((distribution.measurement.sample_size, distribution.measurement.attempted,
                          distribution.measurement.failed, distribution.measurement.missing), (8, 10, 2, 3))
        self.assertEqual(distribution.measurement.eligible_repositories, 20)
        self.assertEqual(distribution.measurement.sampling_policy, "first 10 repositories")
        self.assertFalse(distribution.measurement.complete_profile)
        self.assertEqual(distribution.measurement, metadata)

    def test_gitlab_prevalence_does_not_become_bytes_or_percentages(self):
        result, _ = self.language_result("gitlab", "repositories", "language prevalence in selected repositories")
        distribution = self.build(result, provider="gitlab").sections[0].content
        self.assertEqual(distribution.measurement.unit, "repositories")
        self.assertIn("prevalence", distribution.measurement.scope)
        self.assertEqual(distribution.measurement.denominator, 8)
        self.assertEqual(distribution.selected[0].value, 5)
        self.assertGreater(sum(entry.value for entry in distribution.totals), distribution.measurement.denominator)

    def test_bitbucket_primary_language_counts_keep_their_scope(self):
        measurement = Measurement(2, "bitbucket", "repositories", "primary language of selected repositories",
                                  coverage="complete", denominator=3, sample_size=3)
        data = [{"language": "Go", "repositories": 2}]
        document = self.build(ModuleResult("languages", "Languages", [], data, measurements={"languages": measurement}), provider="bitbucket")
        self.assertEqual(document.sections[0].content.selected[0].value, 2)
        self.assertEqual(document.sections[0].content.measurement.unit, "repositories")
        self.assertIn("primary", document.sections[0].content.measurement.scope)

    def test_language_successful_empty_is_not_missing_or_zero_fabrication(self):
        measurement = Measurement(0, "github", "bytes", "selected repositories", coverage="complete", denominator=0, sample_size=2)
        result = ModuleResult("languages", "Languages", [], {}, measurements={"languages": measurement})
        distribution = self.build(result).sections[0].content
        self.assertEqual(distribution.selected, ())
        self.assertEqual(distribution.measurement.value, 0)
        self.assertEqual(distribution.measurement.availability, "available")

    def test_unavailable_languages_do_not_become_an_empty_successful_distribution(self):
        measured = Measurement(provider="github", unit="bytes", availability="unavailable")
        result = ModuleResult("languages", "Languages", ["unavailable"], {}, measurements={"languages": measured})
        document = self.build(result)
        self.assertIsNone(document.sections[0].content)
        self.assertIsNone(document.sections[0].measurements["languages"].value)

    def test_legacy_language_list_does_not_invent_denominator(self):
        result = ModuleResult("languages", "Languages", [], [{"language": "Python", "bytes": 90}])
        distribution = self.build(result).sections[0].content
        self.assertIsNone(distribution.measurement.denominator)
        self.assertEqual(distribution.totals, ())
        self.assertEqual(distribution.measurement.coverage, "unknown")

    def test_language_mixed_units_without_metadata_fall_back_to_generic(self):
        result = ModuleResult("languages", "Languages", ["legacy"], [{"language": "A", "bytes": 5}, {"language": "B", "repositories": 2}])
        document = self.build(result)
        self.assertIsNone(document.sections[0].content)
        self.assertEqual(document.sections[0].lines, ("legacy",))

    def test_whole_profile_language_completeness_is_preserved(self):
        result, metadata = self.language_result()
        metadata = replace(metadata, complete_profile=True, coverage="complete", failed=0, missing=0,
                           attempted=8, eligible_repositories=8, sampling_policy="all repositories")
        result.measurements["languages"] = metadata
        document = self.build(result)
        self.assertTrue(document.sections[0].content.measurement.complete_profile)
        self.assertFalse(document.notices)

    def test_contributions_keep_actual_dates_and_unknown_gaps(self):
        data = weeks(("2024-01-01", 0), ("2024-01-03", 2), ("2024-01-04", None))
        measurement = Measurement(2, "gitea", "activity records", "viewer-visible activity", coverage="unknown",
                                  start="2024-01-01", end="2024-01-04", reason="coverage not reported")
        result = ModuleResult("contributions", "Contributions", [], data, measurements={"contributions": measurement})
        activity = self.build(result, provider="gitea").sections[0].content
        self.assertIsInstance(activity, ContributionActivity)
        self.assertEqual([(d.date, d.count) for d in activity.days], [(date(2024, 1, 1), 0), (date(2024, 1, 3), 2), (date(2024, 1, 4), None)])
        self.assertNotIn(date(2024, 1, 2), [day.date for day in activity.days])
        self.assertEqual(activity.measurement.coverage, "unknown")
        self.assertEqual(activity.measurement.unit, "activity records")

    def test_gitea_and_forgejo_do_not_become_complete_annual_calendars(self):
        for provider in ("gitea", "forgejo", "codeberg"):
            measured = Measurement(2, provider, "activity records", "viewer-visible activity", coverage="unknown",
                                   start="2024-01-01", end="2024-03-24")
            result = ModuleResult("contributions", "Contributions", [], weeks(("2024-01-01", 1), ("2024-03-24", 1)), measurements={"contributions": measured})
            activity = self.build(result, provider=provider).sections[0].content
            self.assertEqual(len(activity.days), 2)
            self.assertEqual(activity.measurement.coverage, "unknown")
            self.assertEqual(activity.measurement.end, "2024-03-24")

    def test_full_collected_calendar_survives_compact_module_window(self):
        selected = weeks(("2024-01-03", 2))
        full = weeks(("2024-01-01", 0), ("2024-01-02", 1), ("2024-01-03", 2))
        measured = Measurement(2, "github", "contributions", "provider contribution calendar", coverage="complete",
                               start="2024-01-03", end="2024-01-03", sample_size=1)
        self.context.graphql = {"contributionsCollection": {"contributionCalendar": {"weeks": full, "totalContributions": 3}}}
        result = ModuleResult("contributions", "Contributions", [], selected, measurements={"contributions": measured})
        activity = self.build(result, context=self.context).sections[0].content
        self.assertEqual(len(activity.days), 1)
        self.assertEqual(len(activity.calendar_days), 3)
        self.assertEqual(activity.calendar_measurement.start, "2024-01-01")
        self.assertEqual(activity.calendar_measurement.value, 3)
        self.assertEqual(activity.measurement.value, 2)

    def test_context_calendar_coverage_takes_precedence_over_observed_bounds(self):
        self.context.graphql = {"contributionsCollection": {"contributionCalendar": {"weeks": weeks(("2024-01-01", 2), ("2024-01-03", 3))}}}
        source = Measurement(5, "forgejo", "activity records", "viewer-visible activity", coverage="unknown", start="2024-01-01", end="2024-01-03")
        self.context.measurements["contributions"] = source
        result = ModuleResult("contributions", "Contributions", [], weeks(("2024-01-03", 3)), measurements={"contributions": replace(source, start="2024-01-03", value=3)})
        activity = self.build(result, provider="forgejo", context=self.context).sections[0].content
        self.assertIs(activity.calendar_measurement, source)
        self.assertEqual(activity.calendar_measurement.coverage, "unknown")

    def test_non_contiguous_observations_cannot_claim_complete_coverage(self):
        measured = Measurement(2, "github", "contributions", coverage="complete")
        result = ModuleResult("contributions", "Contributions", [], weeks(("2024-01-01", 1), ("2024-01-03", 1)), measurements={"contributions": measured})
        activity = self.build(result).sections[0].content
        self.assertEqual(activity.measurement.coverage, "partial")
        self.assertEqual(measured.coverage, "complete")  # Original metadata was not mutated.
        document = self.build(result)
        self.assertEqual(document.sections[0].measurements["contributions"].coverage, "partial")
        self.assertTrue(any(notice.kind == "coverage" for notice in document.notices))

    def test_missing_calendar_and_successful_empty_response_are_distinct(self):
        missing = ModuleResult("contributions", "Contributions", ["unavailable"], [], measurements={"contributions": Measurement(availability="unavailable")})
        empty = ModuleResult("contributions", "Contributions", ["no returned records"], [], measurements={"contributions": Measurement(0, "gitea", "activity records", coverage="unknown")})
        self.assertIsNone(self.build(missing).sections[0].content)
        observed = self.build(empty, provider="gitea").sections[0].content
        self.assertEqual(observed.days, ())
        self.assertEqual(observed.measurement.value, 0)
        self.assertEqual(observed.measurement.coverage, "unknown")

    def test_streaks_preserve_current_unknown_and_longest_observed_window(self):
        window = Measurement(5, "forgejo", "activity records", "viewer-visible activity", coverage="unknown", start="2024-01-01", end="2024-01-03")
        current = replace(window, value=None, unit="days", scope="observed current streak", availability="unavailable")
        longest = replace(window, value=1, unit="days", scope="longest observed streak in window")
        result = ModuleResult("streaks", "Streaks", [], {"current": None, "longest": 1, "total": 5}, measurements={"contributions": window, "current": current, "longest": longest})
        content = self.build(result, provider="forgejo").sections[0].content
        metrics = {m.identifier: m for m in content.metrics}
        self.assertIs(metrics["current"].measurement, current)
        self.assertIs(metrics["longest"].measurement, longest)
        self.assertEqual(metrics["total"].measurement.value, 5)
        self.assertIn("observed", metrics["longest"].measurement.scope)
        self.assertEqual(metrics["longest"].measurement.start, "2024-01-01")

    def test_pinned_repositories_keep_stars_description_and_primary_language(self):
        repo = {"__typename": "Repository", "nameWithOwner": "alice/tool", "url": "https://github.test/alice/tool",
                "description": "A tool", "stargazerCount": 0, "primaryLanguage": {"name": "Python"}}
        content = self.build(ModuleResult("pinned", "Pinned", [], [repo])).sections[0].content
        self.assertEqual(content.repositories[0].name, "alice/tool")
        self.assertEqual(content.repositories[0].language, "Python")
        self.assertEqual(content.repositories[0].description, "A tool")
        self.assertEqual(content.repositories[0].metrics[0].measurement.value, 0)

    def test_pinned_gists_are_retained_in_raw_and_classic_fallback(self):
        gist = {"__typename": "Gist", "name": "example", "description": "A gist"}
        section = self.build(ModuleResult("pinned", "Pinned", ["gist: example"], [gist])).sections[0]
        self.assertEqual(section.raw_data[0]["description"], "A gist")
        self.assertEqual(section.lines, ("gist: example",))

    def test_top_repository_order_and_missing_stars_are_not_reinterpreted(self):
        data = [{"name": "alice/one", "stars": 2, "language": "Go", "url": "https://one.test"},
                {"name": "alice/two", "stars": None, "language": None}]
        content = self.build(ModuleResult("top_repos", "Top Repos", [], data)).sections[0].content
        self.assertEqual([r.name for r in content.repositories], ["alice/one", "alice/two"])
        self.assertIsNone(content.repositories[1].metrics[0].measurement.value)
        self.assertIn("selected", content.measurement.scope)

    def test_recent_activity_uses_actual_timestamp_without_relative_clock(self):
        data = [{"type": "PushEvent", "repo": "alice/tool", "created_at": "2024-01-01T23:59:00Z"}]
        content = self.build(ModuleResult("recent_activity", "Recent Activity", ["already relative"], data)).sections[0].content
        self.assertIsInstance(content, RecentActivity)
        self.assertEqual(content.events[0].occurred_at, "2024-01-01T23:59:00Z")
        self.assertEqual(content.measurement.scope, "public activity")
        visible = self.build(ModuleResult("recent_activity", "Recent Activity", [], data), provider="gitlab").sections[0].content
        self.assertEqual(visible.measurement.scope, "viewer-visible activity")

    def test_generic_line_only_plugin_is_ordered_and_preserved(self):
        module = ModuleResult("plugin", "Plugin", ["first", "second"], ["first", "second"])
        section = self.build(module).sections[0]
        self.assertIsNone(section.content)
        self.assertEqual(section.lines, ("first", "second"))
        self.assertEqual(section.raw_data, ("first", "second"))

    def test_less_common_structured_modules_keep_raw_data_without_guessed_semantics(self):
        data = {"licenses": {"MIT": 3}, "grade": "A"}
        section = self.build(ModuleResult("repo_health", "Health", ["health"], data)).sections[0]
        self.assertIsNone(section.content)
        self.assertEqual(section.raw_data["licenses"]["MIT"], 3)
        self.assertEqual(section.measurements, {})

    def test_unexpected_opaque_plugin_data_is_neither_inspected_nor_copied(self):
        class Opaque:
            def __str__(self):
                raise AssertionError("unexpected conversion")
            def __deepcopy__(self, memo):
                raise AssertionError("unexpected deepcopy")
            def __iter__(self):
                raise AssertionError("unexpected iteration")
        opaque = Opaque()
        section = self.build(ModuleResult("plugin", "Plugin", ["safe"], {"opaque": opaque})).sections[0]
        self.assertIs(section.raw_data["opaque"], opaque)
        self.assertEqual(section.lines, ("safe",))

    def test_cyclic_plugin_data_does_not_recurse_indefinitely(self):
        cycle = []
        cycle.append(cycle)
        document = self.build(ModuleResult("plugin", "Plugin", ["cycle"], cycle))
        self.assertEqual(document.sections[0].lines, ("cycle",))
        self.assertIs(document.sections[0].raw_data[0], cycle)

    def test_malformed_plugin_text_and_builtin_payloads_do_not_crash(self):
        result = ModuleResult("plugin", None, [None, 12, object()], object(), measurements=None)
        section = self.build(result).sections[0]
        self.assertEqual(section.title, "")
        self.assertEqual(section.lines[:2], ("", "12"))
        for name in ("stats", "languages", "contributions", "streaks", "pinned", "top_repos", "recent_activity"):
            with self.subTest(name=name):
                self.build(ModuleResult(name, name, ["fallback"], object()))

    def test_hidden_modules_and_their_notices_do_not_reappear(self):
        hidden = ModuleResult("identity", "Identity", ["secret"], {"user": self.user}, hidden=True,
                              measurements={"identity": Measurement(availability="unsupported")})
        document = self.build(hidden)
        self.assertEqual(document.sections, ())
        self.assertEqual(document.notices, ())
        self.assertIsNone(document.identity)

    def test_constructor_consumes_only_resolved_selection_and_order(self):
        modules = [ModuleResult(name, name, [name], {}) for name in ("plugin_b", "stats", "plugin_a")]
        document = self.build(*modules)
        self.assertEqual([s.name for s in document.sections], ["plugin_b", "stats", "plugin_a"])
        self.assertIsNone(document.identity)
        self.assertFalse(any(isinstance(s.content, ContributionActivity) for s in document.sections))

    def test_construction_is_deterministic_without_mutating_inputs(self):
        result, _ = self.language_result()
        self.context.repository_coverage = RepositoryCoverage(30, 20, 25, 5, "viewer owned repositories", ("exclude_forks",), 28)
        self.context.viewer_mode = True
        user_before, module_before = copy.deepcopy(self.user), copy.deepcopy(result)
        first = self.build(result, context=self.context)
        second = self.build(result, context=self.context)
        self.assertEqual(first, second)
        self.assertEqual(self.user, user_before)
        self.assertEqual(result, module_before)
        self.assertIs(first.repository_coverage, self.context.repository_coverage)
        self.assertTrue(first.viewer_mode)

    def test_document_containers_are_immutable_and_detached(self):
        data = {"nested": [{"value": 1}]}
        result = ModuleResult("plugin", "Plugin", ["old"], data)
        document = self.build(result)
        with self.assertRaises(FrozenInstanceError):
            document.provider = "gitlab"
        with self.assertRaises(TypeError):
            document.sections[0].raw_data["new"] = 1
        data["nested"][0]["value"] = 2
        result.lines.append("new")
        self.assertEqual(document.sections[0].raw_data["nested"][0]["value"], 1)
        self.assertEqual(document.sections[0].lines, ("old",))
        self.assertIsInstance(document.sections[0].measurements, MappingProxyType)

    def test_builder_performs_no_io_printing_clock_or_terminal_detection(self):
        result, _ = self.language_result()
        forbidden = AssertionError("constructor crossed a pure boundary")
        frozen_date = mock.Mock(wraps=date)
        frozen_date.today.side_effect = forbidden
        with (mock.patch("builtins.open", side_effect=forbidden),
              mock.patch("pathlib.Path.open", side_effect=forbidden),
              mock.patch("builtins.print", side_effect=forbidden),
              mock.patch("shutil.get_terminal_size", side_effect=forbidden),
              mock.patch("time.time", side_effect=forbidden),
              mock.patch("gitfetch.images.fetch_avatar_image", side_effect=forbidden),
              mock.patch("gitfetch.presentation.date", frozen_date)):
            document = self.build(result, ModuleResult("contributions", "Contributions", [], weeks(("2024-01-01", 0))))
        self.assertEqual(document.sections[0].content.measurement.denominator, 100)

    def test_untrusted_text_is_retained_for_display_boundary_sanitization(self):
        payload = "名前 e\u0301 👩🏽‍💻\x1b]0;bad\a\n\t"
        self.user["bio"] = payload
        module = ModuleResult("identity", "Identity", [payload], {"user": self.user})
        document = self.build(module)
        self.assertEqual(document.identity.biography, payload)
        self.assertEqual(document.sections[0].lines, (payload,))
        self.assertEqual(document.sections[0].raw_data["user"]["bio"], payload)

    def test_unsupported_metric_inside_stats_stays_unsupported(self):
        measurement = Measurement(None, "bitbucket", "count", "followers", "unsupported", reason="not supported")
        result = ModuleResult("stats", "Stats", ["followers: unsupported"], {}, measurements={"followers": measurement})
        document = self.build(result, provider="bitbucket")
        metric = document.sections[0].content.metrics[0]
        self.assertIsNone(metric.measurement.value)
        self.assertEqual(metric.measurement.availability, "unsupported")

    def test_declared_calendar_bounds_do_not_hide_unknown_edge_dates(self):
        measurement = Measurement(1, "github", "contributions", coverage="complete", start="2024-01-01", end="2024-01-03")
        result = ModuleResult("contributions", "Contributions", [], weeks(("2024-01-02", 1)), measurements={"contributions": measurement})
        activity = self.build(result).sections[0].content
        self.assertEqual(activity.measurement.coverage, "partial")
        self.assertEqual(len(activity.days), 1)

    def test_noncanonical_dates_are_rejected_consistently_across_python_versions(self):
        result = ModuleResult("contributions", "Contributions", [], weeks(("20240101", 1), ("2024-01-02", 0)))
        activity = self.build(result).sections[0].content
        self.assertEqual([(day.date.isoformat(), day.count) for day in activity.days], [("2024-01-02", 0)])

    def test_full_calendar_uncertainty_is_available_as_a_notice(self):
        selected = Measurement(1, "forgejo", "activity records", "visible activity", coverage="complete", start="2024-01-03", end="2024-01-03")
        source = replace(selected, value=3, coverage="unknown", start="2024-01-01", reason="coverage not reported")
        self.context.measurements["contributions"] = source
        self.context.graphql = {"contributionsCollection": {"contributionCalendar": {"weeks": weeks(("2024-01-01", 2), ("2024-01-03", 1))}}}
        result = ModuleResult("contributions", "Contributions", [], weeks(("2024-01-03", 1)), measurements={"contributions": selected})
        document = self.build(result, provider="forgejo", context=self.context)
        self.assertIs(document.sections[0].measurements["calendar"], source)
        self.assertTrue(any(("contributions", "calendar") in notice.subjects and notice.measurement.coverage == "unknown"
                            for notice in document.notices))

    def test_plugin_container_subclasses_do_not_execute_conversion_hooks(self):
        class PluginDict(dict):
            def get(self, *args):
                raise AssertionError("plugin get hook executed")
        class PluginLines(list):
            def __iter__(self):
                raise AssertionError("plugin iterator executed")
        data = PluginDict({"value": None})
        result = ModuleResult("plugin", "Plugin", PluginLines(["hello"]), data)
        document = self.build(result)
        self.assertEqual(document.sections[0].lines, ("hello",))
        self.assertIs(document.sections[0].raw_data, data)  # Extended opaque payload is retained intact.


if __name__ == "__main__":
    unittest.main()
