"""Deterministic provider semantics and public-data regression tests (no network)."""
import argparse
import json
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from gitfetch.cache import CacheStore
from gitfetch.config import preset_config
from gitfetch.github_api import GitHubAPIError, GitHubClient, GitHubContext
from gitfetch.modes import (
    _compare_metrics,
    _compare_summary_module,
    _module_payload,
    _rank_line,
    handle_org_command,
    handle_repo_command,
)
from gitfetch.modules.builtin import (
    ModuleResult,
    module_commit_cadence,
    module_contributions,
    module_languages,
    module_maintainer_activity,
    module_sparkline,
    module_stats,
    module_streaks,
    module_top_repos,
)
from gitfetch.providers import BitbucketClient, CodebergClient, ForgejoClient, GiteaClient, GitLabClient
from gitfetch.semantics import (
    Measurement,
    RepositoryCoverage,
    number,
    profile_measurements,
    repository_measurements,
)


def context(repos=(), user=None, provider="github", graphql=None):
    return GitHubContext("alice", user or {"login": "alice"}, list(repos), [], False, None,
                         graphql or {}, provider=provider)


def calendar(days):
    return {"contributionsCollection": {"contributionCalendar": {
        "totalContributions": sum(day["contributionCount"] for day in days),
        "weeks": [{"contributionDays": days}],
    }}}


class SemanticTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.cache = CacheStore(Path(self.directory.name), enabled=False, ttl_seconds=1000)
        self.config = preset_config("minimal")
        self.config["modules"]["languages"].update(workers=1, max_repos=40, limit=5)
        self.no_network = mock.patch("requests.Session.request", side_effect=AssertionError("unexpected network"))
        self.no_network.start()
        self.addCleanup(self.no_network.stop)

    def client(self, cls=GitHubClient, token=""):
        return cls(token, self.cache, False, "https://example.test")

    def languages(self, payloads, unit="bytes", **settings):
        self.config["modules"]["languages"].update(settings)
        ctx = context([{"languages_url": str(i)} for i in range(len(payloads))])
        client = self.client()
        client.language_breakdown_unit = unit
        with mock.patch.object(client, "get_languages", side_effect=payloads) as get:
            result = module_languages(self.config, ctx, client)
        return result, get

    def test_github_byte_denominator_includes_languages_beyond_display_limit(self):
        result, get = self.languages([{"Python": 60, "Go": 30}, {"Shell": 10}], limit=1)
        self.assertEqual(result.data, [{"language": "Python", "bytes": 60}])
        self.assertEqual(result.lines, ["Python 60%"])
        measurement = result.measurements["languages"]
        self.assertEqual(measurement.denominator, 100)
        self.assertEqual(measurement.language_totals, (("Python", 60), ("Go", 30), ("Shell", 10)))
        self.assertEqual(measurement.sample_size, 2)
        self.assertEqual(get.call_count, 2)

    def test_gitlab_fractions_are_preserved_in_repository_response(self):
        client = self.client(GitLabClient)
        with mock.patch.object(client, "_get_json", return_value={"Python": 99.5, "Go": 0.5}) as get:
            data = client.get_languages("gitlab://project/42")
        self.assertEqual(data, {"Python": 99.5, "Go": 0.5})
        self.assertEqual(data.measurement.unit, "percent")
        self.assertEqual(get.call_count, 1)
        self.assertEqual(json.loads(json.dumps(data)), {"Python": 99.5, "Go": 0.5})

    def test_gitlab_profile_language_prevalence_counts_positive_languages_per_project(self):
        result, get = self.languages([{"Python": 99.5, "Go": 0.5, "Shell": 0}, {"Go": 100}], unit="percent")
        self.assertEqual(result.data, [{"language": "Go", "repositories": 2}, {"language": "Python", "repositories": 1}])
        self.assertIn("not byte-weighted", result.lines[-1])
        self.assertEqual(result.measurements["languages"].denominator, 2)
        self.assertEqual(result.measurements["languages"].unit, "repositories")
        self.assertEqual(get.call_count, 2)

    def test_bitbucket_primary_language_is_a_repository_count(self):
        client = self.client(BitbucketClient)
        ctx = context([{"languages_url": "bitbucket://language/Python"}, {"languages_url": "bitbucket://language/n/a"}], provider="bitbucket")
        result = module_languages(self.config, ctx, client)
        self.assertEqual(result.data, [{"language": "Python", "repositories": 1}])
        self.assertIn("primary language", result.measurements["languages"].scope)
        self.assertEqual(result.measurements["languages"].denominator, 2)

    def test_gitea_family_language_endpoints_return_bytes(self):
        for cls in (GiteaClient, ForgejoClient, CodebergClient):
            with self.subTest(provider=cls.provider_name):
                client = self.client(cls)
                ctx = context([{"languages_url": "https://example.test/languages"}], provider=cls.provider_name)
                with mock.patch.object(client, "_get_json", return_value={"Go": 100, "C": 300}) as get:
                    result = module_languages(self.config, ctx, client)
                self.assertEqual(result.data, [{"language": "C", "bytes": 300}, {"language": "Go", "bytes": 100}])
                self.assertEqual(result.measurements["languages"].provider, cls.provider_name)
                self.assertEqual(result.measurements["languages"].denominator, 400)
                self.assertEqual(get.call_count, 1)

    def test_language_sampling_and_missing_endpoints_have_separate_counts(self):
        client = self.client()
        ctx = context([{"languages_url": "a"}, {"languages_url": "b"}, {}])
        self.config["modules"]["languages"]["max_repos"] = 1
        with mock.patch.object(client, "get_languages", return_value={"C": 0}) as get:
            result = module_languages(self.config, ctx, client)
        m = result.measurements["languages"]
        self.assertEqual((m.attempted, m.sample_size, m.eligible_repositories, m.missing), (1, 1, 3, 1))
        self.assertEqual(m.coverage, "partial")
        self.assertFalse(m.complete_profile)
        self.assertEqual(result.data, [{"language": "C", "bytes": 0}])
        self.assertEqual(get.call_count, 1)

    def test_successful_empty_language_response_is_not_a_failure(self):
        result, _ = self.languages([{}])
        self.assertTrue(result.hidden)
        m = result.measurements["languages"]
        self.assertEqual((m.value, m.sample_size, m.failed, m.availability), (0, 1, 0, "available"))

    def test_all_failed_language_requests_are_unavailable_not_zero(self):
        result, _ = self.languages([GitHubAPIError("failed")])
        self.assertEqual(result.measurements["languages"].availability, "unavailable")
        self.assertIsNone(result.measurements["languages"].value)
        self.assertFalse(result.hidden)

    def test_partial_language_failure_preserves_sample_and_denominator(self):
        result, _ = self.languages([{"C": 10}, GitHubAPIError("failed"), {"C": 5, "Go": 5}])
        m = result.measurements["languages"]
        self.assertEqual((m.failed, m.sample_size, m.attempted, m.denominator), (1, 2, 3, 20))
        self.assertEqual(m.coverage, "partial")
        self.assertEqual(result.lines[0], "C 75%")
        self.assertIn("incomplete", result.lines[-1])

    def test_language_authentication_restriction_is_explicit(self):
        result, _ = self.languages([GitHubAPIError("forbidden", status_code=403)])
        self.assertEqual(result.measurements["languages"].availability, "auth_required")

    def test_provider_language_failure_and_authentication_are_preserved(self):
        for cls in (GitLabClient, GiteaClient):
            client = self.client(cls)
            url = "gitlab://project/42" if cls is GitLabClient else "https://example.test/languages"
            with mock.patch.object(client, "_get_json", side_effect=GitHubAPIError("denied", status_code=401)):
                data = client.get_languages(url)
            self.assertEqual(data, {})
            self.assertEqual(data.measurement.availability, "auth_required")

    def test_invalid_language_counts_are_not_truncated_or_ranked(self):
        result, _ = self.languages([{"C": 1.5, "Go": -1, "Rust": True, "Python": 0, "Ruby": float("nan")}])
        self.assertEqual(result.data, [{"language": "Python", "bytes": 0}])
        self.assertEqual(result.measurements["languages"].coverage, "partial")

    def test_language_ties_are_stable_independent_of_completion_order(self):
        result, _ = self.languages([{"Zulu": 10, "Alpha": 10}], workers=4)
        self.assertEqual([row["language"] for row in result.data], ["Alpha", "Zulu"])

    def test_language_concurrency_is_bounded_and_cap_limits_requests(self):
        client = self.client()
        ctx = context([{"languages_url": str(i)} for i in range(20)])
        self.config["modules"]["languages"].update(workers=2, max_repos=4)
        barrier = threading.Barrier(2)
        active = peak = calls = 0
        lock = threading.Lock()
        def get_languages(url):
            nonlocal active, peak, calls
            with lock:
                active += 1
                peak = max(peak, active)
                calls += 1
            barrier.wait(timeout=5)
            with lock:
                active -= 1
            return {"C": 1}
        with mock.patch.object(client, "get_languages", side_effect=get_languages):
            module_languages(self.config, ctx, client)
        self.assertEqual((peak, calls), (2, 4))

    def test_complete_language_scan_is_not_automatically_a_complete_profile(self):
        client = self.client()
        ctx = context([{"languages_url": "a"}], {"login": "alice", "public_repos": 50})
        ctx.repository_coverage = RepositoryCoverage(50, 1, 50, 0, "public owned repositories", ("exclude_forks",))
        with mock.patch.object(client, "get_languages", return_value={"C": 10}):
            result = module_languages(self.config, ctx, client)
        self.assertEqual(result.measurements["languages"].coverage, "complete")
        self.assertFalse(result.measurements["languages"].complete_profile)
        ctx.user["public_repos"] = 1
        ctx.repository_coverage = RepositoryCoverage(1, 1, 1, 0, "public owned repositories")
        with mock.patch.object(client, "get_languages", return_value={"C": 10}):
            result = module_languages(self.config, ctx, client)
        self.assertTrue(result.measurements["languages"].complete_profile)

    def test_profile_missing_and_measured_zero_are_distinct_on_every_provider(self):
        for cls in (GitLabClient, GiteaClient, ForgejoClient, CodebergClient):
            client = self.client(cls)
            missing = client._normalize_user({"login": "alice"})
            raw = {"login": "alice", "followers": 0, "following": 0, "followers_count": 0, "following_count": 0}
            zero = client._normalize_user(raw)
            with self.subTest(provider=cls.provider_name):
                self.assertIsNone(missing["followers"])
                self.assertEqual(zero["followers"], 0)
                self.assertIsNone(zero["public_gists"])
                self.assertEqual(profile_measurements(zero, cls.provider_name)["public_gists"].availability, "unsupported")
        self.assertEqual(profile_measurements({}, "github")["followers"].availability, "unavailable")
        self.assertEqual(profile_measurements({"followers": 0}, "github")["followers"].value, 0)
        workspace = self.client(BitbucketClient)._normalize_workspace({"slug": "alice"})
        self.assertIsNone(workspace["followers"])
        self.assertEqual(profile_measurements(workspace, "bitbucket")["followers"].availability, "unsupported")

    def test_repository_missing_and_zero_are_distinct(self):
        for cls in (GitLabClient, GiteaClient, ForgejoClient, CodebergClient):
            client = self.client(cls)
            normalize = client._normalize_project if cls is GitLabClient else client._normalize_repo
            missing = normalize({})
            zero = normalize({"star_count": 0, "stars_count": 0, "forks_count": 0, "watchers_count": 0, "open_issues_count": 0})
            with self.subTest(provider=cls.provider_name):
                self.assertIsNone(missing["stargazers_count"])
                self.assertIsNone(missing["forks_count"])
                self.assertEqual(zero["stargazers_count"], 0)
                self.assertEqual(zero["forks_count"], 0)
        self.assertEqual(repository_measurements({}, "bitbucket")["stargazers_count"].availability, "unsupported")

    def test_watchers_are_not_stars_and_activity_is_not_push_time(self):
        gitlab = self.client(GitLabClient)._normalize_project({"star_count": 40, "last_activity_at": "2024-01-01"})
        self.assertIsNone(gitlab["watchers_count"])
        self.assertIsNone(gitlab["pushed_at"])
        for cls in (GiteaClient, ForgejoClient, CodebergClient):
            repo = self.client(cls)._normalize_repo({"stars_count": 40, "updated_at": "2024-01-01"})
            self.assertIsNone(repo["watchers_count"])
            self.assertIsNone(repo["pushed_at"])

    def test_gitlab_size_is_optional_bytes_not_fabricated_zero(self):
        client = self.client(GitLabClient)
        self.assertIsNone(client._normalize_project({})["size"])
        self.assertEqual(client._normalize_project({"statistics": {"repository_size": 2048}})["size"], 2048)

    def test_reported_repository_count_survives_filters_on_all_clients(self):
        for cls in (GitHubClient, GitLabClient, GiteaClient, ForgejoClient, CodebergClient, BitbucketClient):
            client = self.client(cls)
            user = {"login": "alice", "public_repos": 50}
            repos = [{"name": "a", "private": False, "fork": False}, {"name": "b", "private": False, "fork": True}]
            with mock.patch.object(client, "get_user", return_value=user), \
                 mock.patch.object(client, "get_repos", return_value=repos), \
                 mock.patch.object(client, "get_events", return_value=[]), \
                 mock.patch.object(client, "_resolve_user", create=True, return_value={"id": 1, "username": "alice", "public_repos": 50}):
                ctx = client.get_context("alice", "public", {"exclude_forks": True}, include_graphql=False)
            with self.subTest(provider=cls.provider_name):
                self.assertEqual(ctx.user["public_repos"], 50)
                self.assertEqual((ctx.repository_coverage.fetched, ctx.repository_coverage.retained), (2, 1))

    def test_missing_repository_total_is_labelled_as_fetched_not_account_total(self):
        ctx = context([{"private": False}], {"login": "alice", "public_repos": None})
        ctx.repository_coverage = RepositoryCoverage(3, 1, 2, 1, "viewer owned repositories")
        result = module_stats(self.config, ctx, self.client())
        self.assertIn("unavailable public repos", result.lines)
        self.assertIn("2 public repos fetched; 1 repos selected", result.lines)
        self.assertIsNone(result.data["user"]["public_repos"])

    def test_public_and_viewer_repository_access_stay_separate(self):
        for cls in (GitLabClient, GiteaClient, ForgejoClient, CodebergClient):
            client = self.client(cls, "token")
            repos = [{"private": False, "owner": {"login": "alice"}}, {"private": True, "owner": {"login": "alice"}}]
            with mock.patch.object(client, "get_user", return_value={"login": "alice"}), \
                 mock.patch.object(client, "get_authenticated_user", return_value={"login": "alice"}), \
                 mock.patch.object(client, "get_repos", return_value=repos), \
                 mock.patch.object(client, "get_events", return_value=[]), \
                 mock.patch.object(client, "_resolve_user", create=True, return_value={"id": 1, "username": "alice"}):
                public = client.get_context("alice", "public", {}, include_graphql=False)
                viewer = client.get_context("alice", "viewer", {}, include_graphql=False)
                other = client.get_context("bob", "viewer", {}, include_graphql=False)
            with self.subTest(provider=cls.provider_name):
                self.assertEqual((len(public.repos), len(viewer.repos), len(other.repos)), (1, 2, 1))
                self.assertEqual(viewer.repository_coverage.private, 1)
                self.assertFalse(other.viewer_mode)

    def test_gitea_viewer_excludes_collaborations_from_owned_profile_metrics(self):
        client = self.client(GiteaClient, "token")
        repos = [{"private": False, "owner": {"login": "alice"}}, {"private": True, "owner": {"login": "team"}}]
        with mock.patch.object(client, "get_user", return_value={"login": "alice"}), \
             mock.patch.object(client, "get_authenticated_user", return_value={"login": "alice"}), \
             mock.patch.object(client, "get_repos", return_value=repos), \
             mock.patch.object(client, "get_events", return_value=[]):
            ctx = client.get_context("alice", "viewer", {}, include_graphql=False)
        self.assertEqual(len(ctx.repos), 1)

    def test_heatmap_failure_is_not_a_zero_calendar(self):
        for cls in (GiteaClient, ForgejoClient, CodebergClient):
            client = self.client(cls)
            with mock.patch.object(client, "_get_json", side_effect=GitHubAPIError("failed")):
                heatmap = client.get_heatmap("alice")
            self.assertEqual(heatmap.measurement.availability, "unavailable")
            self.assertIsNone(heatmap.measurement.value)
            self.assertEqual(client._graphql_like_bundle("alice", heatmap), {})

    def test_heatmap_successful_empty_preserves_visibility_uncertainty(self):
        client = self.client(GiteaClient)
        with mock.patch.object(client, "_get_json", return_value=[]):
            heatmap = client.get_heatmap("alice")
        self.assertEqual(heatmap.measurement.availability, "available")
        self.assertEqual(heatmap.measurement.value, 0)
        self.assertEqual(heatmap.measurement.coverage, "unknown")
        graphql = client._graphql_like_bundle("alice", heatmap)
        self.assertEqual(graphql["contributionsCollection"]["contributionCalendar"], {"totalContributions": 0, "weeks": []})
        ctx = context(graphql=graphql, provider="gitea")
        ctx.measurements["contributions"] = heatmap.measurement
        self.assertIn("coverage unknown", module_contributions(self.config, ctx, client).lines[0])
        self.assertEqual(module_streaks(self.config, ctx, client).data, {})

    def test_heatmap_measured_zero_is_preserved_as_a_dated_record(self):
        client = self.client(GiteaClient)
        raw = [{"timestamp": 1704067200, "contributions": 0}]
        with mock.patch.object(client, "_get_json", return_value=raw):
            heatmap = client.get_heatmap("alice")
        self.assertEqual((heatmap.measurement.value, heatmap.measurement.sample_size), (0, 1))
        self.assertEqual(heatmap.measurement.start, "2024-01-01")

    def test_heatmap_preserves_old_records_and_utc_dates_without_padding(self):
        client = self.client(GiteaClient)
        points = [
            {"timestamp": 1704153599, "contributions": 2},  # Jan 1 23:59:59 UTC
            {"timestamp": 1704067200, "contributions": 1},
            {"timestamp": 1704240000, "contributions": 4},  # Jan 3
        ]
        graphql = client._graphql_like_bundle("alice", points)
        contrib = graphql["contributionsCollection"]
        days = [day for week in contrib["contributionCalendar"]["weeks"] for day in week["contributionDays"]]
        self.assertEqual(days, [{"date": "2024-01-01", "contributionCount": 3}, {"date": "2024-01-03", "contributionCount": 4}])
        self.assertNotIn("totalCommitContributions", contrib)
        self.assertNotIn("totalIssueContributions", contrib)

    def test_heatmap_http_auth_restriction_is_preserved(self):
        client = self.client(GiteaClient)
        with mock.patch.object(client, "_get_json", side_effect=GitHubAPIError("denied", status_code=403)):
            heatmap = client.get_heatmap("alice")
        self.assertEqual(heatmap.measurement.availability, "auth_required")

    def test_heatmap_request_remains_optional_and_bounded(self):
        client = self.client(GiteaClient)
        with mock.patch.object(client, "get_user", return_value={"login": "alice"}), \
             mock.patch.object(client, "get_repos", return_value=[]), \
             mock.patch.object(client, "get_events", return_value=[]), \
             mock.patch.object(client, "_get_json", return_value=[]) as get:
            client.get_context("alice", "public", {}, include_graphql=False)
            get.assert_not_called()
            ctx = client.get_context("alice", "public", {}, include_graphql=True)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(ctx.measurements["contributions"].coverage, "unknown")

    def test_heatmap_weekdays_and_missing_weeks_retain_calendar_chronology(self):
        client = self.client(GiteaClient)
        raw = [{"timestamp": 1704067200, "contributions": 2}, {"timestamp": 1705276800, "contributions": 2}]
        ctx = context(graphql=client._graphql_like_bundle("alice", raw), provider="gitea")
        result = module_contributions(self.config, ctx, client)
        self.assertEqual(result.lines[0], "   ")  # Sundays are unknown, not Monday records.
        self.assertEqual(result.lines[1], "█ █")
        self.assertEqual(result.data[1], {"contributionDays": []})

    def test_streaks_do_not_bridge_unknown_dates_or_claim_lifetime_maximum(self):
        days = [{"date": "2024-01-01", "contributionCount": 3}, {"date": "2024-01-03", "contributionCount": 2}]
        ctx = context(graphql=calendar(days))
        result = module_streaks(self.config, ctx, self.client())
        self.assertEqual(result.data, {"current": None, "longest": 1, "total": 5})
        self.assertIn("longest observed: 1 day(s)", result.lines)
        self.assertIn("partial", result.lines[3])
        self.assertNotIn("year total", " ".join(result.lines))

    def test_current_streak_uses_utc_today_and_yesterday_with_a_frozen_clock(self):
        days = [{"date": f"2024-01-{i:02d}", "contributionCount": 1 if i < 4 else 0} for i in range(1, 5)]
        frozen = mock.Mock(wraps=datetime)
        frozen.now.return_value = datetime(2024, 1, 4, 1, tzinfo=timezone.utc)
        with mock.patch("gitfetch.modules.builtin.datetime", frozen):
            result = module_streaks(self.config, context(graphql=calendar(days)), self.client())
        frozen.now.assert_called_with(timezone.utc)
        self.assertEqual(result.data, {"current": 3, "longest": 3, "total": 3})

    def test_partial_window_cadence_uses_dates_not_last_n_records(self):
        days = [{"date": "2024-01-01", "contributionCount": 50}, {"date": "2024-02-01", "contributionCount": 1}]
        self.config["modules"]["commit_cadence"]["days"] = 7
        result = module_commit_cadence(self.config, context(graphql=calendar(days)), self.client())
        self.assertEqual(result.data["total"], 1)
        self.assertEqual(len(result.data["days"]), 1)

    def test_zero_sparkline_peak_is_not_fabricated_as_one(self):
        days = [{"date": "2024-01-01", "contributionCount": 0}]
        result = module_sparkline(self.config, context(graphql=calendar(days)), self.client())
        self.assertEqual(result.data, [0])
        self.assertIn("peak 0", result.lines[1])

    def test_sparkline_unknown_days_are_not_compressed_into_adjacent_days(self):
        days = [{"date": "2024-01-01", "contributionCount": 1}, {"date": "2024-01-03", "contributionCount": 1}]
        result = module_sparkline(self.config, context(graphql=calendar(days)), self.client())
        self.assertEqual(result.lines[0], "█ █")
        self.assertIn("gaps unknown", result.lines[1])
        self.assertEqual(result.data, [1, 1])

    def test_gitea_events_do_not_invent_a_commit_per_push(self):
        client = self.client(GiteaClient)
        event = client._normalize_event({"op_type": "push", "created_at": "2024-01-01"})
        ctx = context()
        ctx.events = [event]
        result = module_commit_cadence(self.config, ctx, client)
        self.assertIsNone(result.data["commits"])
        self.assertIn("commits in visible events: unavailable", result.lines)

    def test_comparison_excludes_unavailable_but_preserves_real_zero(self):
        metrics = [_compare_metrics(context(user={"login": login, "followers": value}))
                   for login, value in (("missing", None), ("zero", 0), ("one", 1))]
        self.assertEqual(_rank_line(metrics, "followers", "followers"), "followers: one 1 > zero 0; unavailable: missing")
        self.assertIsNone(metrics[0]["followers"])

    def test_comparison_ties_are_explicit_and_deterministic(self):
        metrics = [{"login": "z", "stars": 0}, {"login": "a", "stars": 0}]
        self.assertEqual(_rank_line(metrics, "stars", "stars"), "stars: a 0 = z 0")

    def test_comparison_with_insufficient_values_explains_absence(self):
        metrics = [{"login": "a", "stars": 0}, {"login": "b", "stars": None}]
        self.assertEqual(_rank_line(metrics, "stars", "stars"), "stars: insufficient comparable data; unavailable: b")

    def test_comparison_refuses_mixed_scopes_or_providers(self):
        a, b = context([{"stargazers_count": 0}]), context([{"stargazers_count": 10}])
        b.repository_coverage = RepositoryCoverage(1, 1, 0, 1, "viewer owned repositories")
        self.assertIn("not comparable", _rank_line([_compare_metrics(a), _compare_metrics(b)], "stars", "stars"))
        b.repository_coverage = None
        b.provider = "gitea"
        self.assertIn("not comparable", _rank_line([_compare_metrics(a), _compare_metrics(b)], "stars", "stars"))

    def test_comparison_partial_repo_metrics_do_not_enter_rankings(self):
        ctx = context([{"stargazers_count": 10, "forks_count": 0}, {"stargazers_count": None, "forks_count": 0}])
        metrics = _compare_metrics(ctx)
        self.assertIsNone(metrics["stars"])
        self.assertEqual(metrics["forks"], 0)
        self.assertIsNone(metrics["public_repos"])

    def test_comparison_json_envelope_never_leaks_internal_provenance(self):
        summary = _compare_summary_module([_compare_metrics(context()), _compare_metrics(context(user={"login": "bob"}))])
        payload = json.loads(json.dumps(summary.data))
        self.assertEqual(set(payload), {"metrics", "language_overlap"})
        self.assertEqual(set(payload["metrics"][0]), {"login", "followers", "following", "public_repos", "stars", "forks", "languages", "top_language"})
        self.assertIsNone(payload["metrics"][0]["followers"])
        self.assertNotIn("measurements", json.dumps(payload))

    def test_optional_modules_do_not_sum_missing_repository_metrics_as_zero(self):
        ctx = context([{"name": "a", "full_name": "alice/a", "stargazers_count": None}, {"name": "b", "full_name": "alice/b", "stargazers_count": 0}])
        result = module_maintainer_activity(self.config, ctx, self.client())
        self.assertIsNone(result.data["stars"])
        self.assertIsNone(result.data["forks"])
        ranked = module_top_repos(self.config, ctx, self.client())
        self.assertEqual([item["name"] for item in ranked.data], ["alice/b"])
        self.assertEqual(ranked.data[0]["stars"], 0)

    def test_module_result_positional_plugin_contract_and_raw_data_are_preserved(self):
        raw = {"bio": "unsafe\x1b[2J", "metric": None}
        result = ModuleResult("plugin", "Plugin", ["line"], raw, False, False)
        result.measurements["metric"] = Measurement(availability="unavailable")
        self.assertEqual(_module_payload([result]), {"plugin": raw})
        self.assertEqual(json.loads(json.dumps(_module_payload([result])))["plugin"], raw)

    def test_old_cached_gitlab_percentages_are_reinterpreted_without_network(self):
        self.cache.enabled = True
        self.cache.directory.mkdir(exist_ok=True)
        client = self.client(GitLabClient)
        client.offline = True
        self.cache.set(client._cache_key("languages", "42"), {"Python": 99.5, "Go": 0.5})
        data = client.get_languages("gitlab://project/42")
        self.assertEqual(data, {"Python": 99.5, "Go": 0.5})
        self.assertEqual(data.measurement.unit, "percent")

    def test_old_cached_empty_heatmap_remains_unknown_not_full_year_zero(self):
        self.cache.enabled = True
        self.cache.directory.mkdir(exist_ok=True)
        client = self.client(GiteaClient)
        client.offline = True
        self.cache.set(client._cache_key("heatmap", "alice"), [])
        data = client.get_heatmap("alice")
        self.assertEqual(data.measurement.coverage, "unknown")
        self.assertIsNone(data.measurement.start)

    def test_cache_provider_and_authentication_isolation_is_unchanged(self):
        a, b = self.client(GiteaClient, "a"), self.client(GiteaClient, "b")
        self.assertNotEqual(a._cache_key("heatmap", "alice"), b._cache_key("heatmap", "alice"))
        self.assertNotEqual(a._cache_key("languages", "a"), self.client(ForgejoClient, "a")._cache_key("languages", "a"))

    def test_repository_mode_preserves_decimal_json_and_labels_the_unit(self):
        client = self.client(GitLabClient)
        args = argparse.Namespace(target="alice/project", contributors_limit=3, commits_limit=3)
        with mock.patch("gitfetch.modes._load_config_with_path", return_value=self.config), \
             mock.patch("gitfetch.modes._client_for", return_value=client), \
             mock.patch.object(client, "get_repo", return_value={"full_name": "alice/project"}), \
             mock.patch.object(client, "get_repo_languages", return_value={"Python": 99.5, "Go": 0.5}), \
             mock.patch.object(client, "get_repo_contributors", return_value=[]), \
             mock.patch.object(client, "get_repo_commits", return_value=[]), \
             mock.patch("gitfetch.modes._emit_mode_output") as emit:
            self.assertEqual(handle_repo_command(args), 0)
        modules = {module.name: module for module in emit.call_args.kwargs["modules"]}
        self.assertEqual(modules["languages"].lines, ["Python 99.5% (project usage)", "Go 0.5% (project usage)"])
        self.assertEqual(modules["languages"].data, {"Python": 99.5, "Go": 0.5})
        self.assertIn("stars: unavailable", modules["stats"].lines)
        self.assertIn("size: unavailable bytes", modules["stats"].lines)

    def test_organization_zero_public_count_is_not_replaced_by_fetched_count(self):
        client = self.client()
        args = argparse.Namespace(target="team", members_limit=3, repos_limit=3)
        with mock.patch("gitfetch.modes._load_config_with_path", return_value=self.config), \
             mock.patch("gitfetch.modes._client_for", return_value=client), \
             mock.patch.object(client, "get_org", return_value={"login": "team", "public_repos": 0}), \
             mock.patch.object(client, "get_org_repos", return_value=[{"name": "private", "private": True}]), \
             mock.patch.object(client, "get_org_members", return_value=[]), \
             mock.patch("gitfetch.modes._emit_mode_output") as emit:
            self.assertEqual(handle_org_command(args), 0)
        stats = emit.call_args.kwargs["modules"][1]
        self.assertIn("public repos: 0", stats.lines)
        self.assertIn("followers: unavailable", stats.lines)
        self.assertIn("stars in fetched repos: unavailable", stats.lines)

    def test_invalid_numbers_never_become_measurements(self):
        for invalid in (None, "0", True, -1, float("inf"), float("nan")):
            self.assertIsNone(number(invalid))
        self.assertEqual(number(0), 0)

    def test_github_language_http_requests_and_cache_reuse_are_unchanged(self):
        self.cache.enabled = True
        self.cache.directory.mkdir(exist_ok=True)
        client = self.client()
        response = mock.Mock(ok=True, status_code=200)
        response.json.return_value = {"Python": 80, "Go": 20}
        with mock.patch.object(client.session, "get", return_value=response) as get:
            first = client.get_languages("https://example.test/languages")
            second = client.get_languages("https://example.test/languages")
        self.assertEqual(get.call_count, 1)
        self.assertEqual(first, second)
        self.assertEqual(second.measurement.unit, "bytes")
        client.offline = True
        self.assertEqual(client.get_languages("https://example.test/languages"), first)

    def test_github_rate_limit_is_not_mislabelled_as_authentication_required(self):
        client = self.client()
        response = mock.Mock(ok=False, status_code=403)
        response.headers = {"X-RateLimit-Remaining": "0"}
        with mock.patch.object(client.session, "get", return_value=response):
            result = module_languages(self.config, context([{"languages_url": "https://example.test/languages"}]), client)
        self.assertEqual(result.measurements["languages"].availability, "unavailable")

    def test_gitlab_fractional_zero_usage_does_not_invent_repository_prevalence(self):
        result, _ = self.languages([{"Python": 0.0}], unit="percent")
        self.assertEqual(result.data, {})
        self.assertEqual(result.measurements["languages"].value, 0)
        self.assertEqual(result.measurements["languages"].sample_size, 1)

    def test_bitbucket_language_placeholder_is_not_a_language_and_slashes_survive(self):
        client = self.client(BitbucketClient)
        self.assertEqual(client.get_languages("bitbucket://language/n/a"), {})
        self.assertEqual(client.get_languages("bitbucket://language/C/C++"), {"C/C++": 1})

    def test_returned_and_eligible_repository_counts_remain_distinct(self):
        client = self.client(GiteaClient, "token")
        repos = [{"private": False, "owner": {"login": "alice"}}, {"private": True, "owner": {"login": "alice"}}]
        with mock.patch.object(client, "get_user", return_value={"login": "alice"}), \
             mock.patch.object(client, "get_repos", return_value=repos), \
             mock.patch.object(client, "get_events", return_value=[]):
            ctx = client.get_context("alice", "public", {}, include_graphql=False)
        self.assertEqual((ctx.repository_coverage.fetched, ctx.repository_coverage.eligible, ctx.repository_coverage.retained), (2, 1, 1))
        self.assertEqual((ctx.repository_coverage.public, ctx.repository_coverage.private), (1, 1))

    def test_old_raw_cached_profile_cannot_reintroduce_filtered_repository_total(self):
        self.cache.enabled = True
        self.cache.directory.mkdir(exist_ok=True)
        client = self.client(GiteaClient)
        client.offline = True
        self.cache.set(client._cache_key("user", "alice"), {"login": "alice", "public_repos": 50})
        self.cache.set(client._cache_key("repos", "public", "alice"), [
            {"name": "a", "private": False, "fork": True}, {"name": "b", "private": False},
        ])
        ctx = client.get_context("alice", "public", {"exclude_forks": True}, include_graphql=False)
        self.assertEqual(ctx.user["public_repos"], 50)
        self.assertEqual(len(ctx.repos), 1)

    def test_heatmap_invalid_records_are_not_successful_measured_zero(self):
        client = self.client(GiteaClient)
        with mock.patch.object(client, "_get_json", return_value=[{"timestamp": "invalid", "contributions": 5}, "invalid"]):
            heatmap = client.get_heatmap("alice")
        self.assertEqual(heatmap.measurement.availability, "unavailable")
        self.assertIsNone(heatmap.measurement.value)
        self.assertEqual(client._graphql_like_bundle("alice", heatmap), {})

    def test_github_full_calendar_preserves_reported_contribution_semantics(self):
        days = [{"date": f"2024-01-{i:02d}", "contributionCount": i} for i in range(1, 8)]
        ctx = context(graphql=calendar(days))
        ctx.graphql["contributionsCollection"]["totalCommitContributions"] = 9
        ctx.graphql["contributionsCollection"]["totalPullRequestReviewContributions"] = 0
        result = module_streaks(self.config, ctx, self.client())
        self.assertEqual(result.data["total"], 28)
        self.assertEqual(result.measurements["contributions"].coverage, "complete")
        self.assertIn("commits: 9", result.lines)
        self.assertIn("reviews: 0", result.lines)
        self.assertTrue(result.requires_token)

    def test_compare_distinct_filter_scopes_are_not_ranked_together(self):
        a, b = context([{"stargazers_count": 0}]), context([{"stargazers_count": 10}])
        a.repository_coverage = RepositoryCoverage(1, 1, 1, 0, "public owned repositories", ("exclude_forks",))
        b.repository_coverage = RepositoryCoverage(1, 1, 1, 0, "public owned repositories")
        self.assertIn("not comparable", _rank_line([_compare_metrics(a), _compare_metrics(b)], "stars", "stars"))

    def test_missing_push_dates_are_not_zero_measured_activity(self):
        ctx = context([{"name": "a", "updated_at": "2024-01-01T00:00:00Z"}])
        result = module_maintainer_activity(self.config, ctx, self.client())
        self.assertIsNone(result.data["recent_pushes_30_days"])
        self.assertIsNone(result.data["stale_repos_over_365_days"])

    def test_profile_card_missing_stats_use_unavailable_and_zero_is_retained(self):
        from gitfetch.formats import render_card_svg
        for followers, expected in ((None, "unavailable"), (0, "0")):
            user = {"login": "alice", "followers": followers, "public_repos": 0, "following": 0}
            svg = render_card_svg(self.config, user, [ModuleResult("stats", "Stats", [], {"user": user})])
            self.assertIn(expected + " followers", svg)
            self.assertNotIn(">None</text>", svg)

    def test_repository_bitbucket_primary_language_is_not_an_exhaustive_percentage(self):
        client = self.client(BitbucketClient)
        args = argparse.Namespace(target="alice/project", contributors_limit=3, commits_limit=3)
        with mock.patch("gitfetch.modes._load_config_with_path", return_value=self.config), \
             mock.patch("gitfetch.modes._client_for", return_value=client), \
             mock.patch.object(client, "get_repo", return_value={"full_name": "alice/project", "size": 2048}), \
             mock.patch.object(client, "get_repo_languages", return_value={"Python": 1}), \
             mock.patch.object(client, "get_repo_contributors", return_value=[{"login": "alice", "contributions": 3}]), \
             mock.patch.object(client, "get_repo_commits", return_value=[]), \
             mock.patch("gitfetch.modes._emit_mode_output") as emit:
            self.assertEqual(handle_repo_command(args), 0)
        modules = {module.name: module for module in emit.call_args.kwargs["modules"]}
        self.assertEqual(modules["languages"].lines, ["Python (primary language)"])
        self.assertIn("size: 2048 bytes", modules["stats"].lines)
        self.assertIn("in retrieved sample", modules["contributors"].lines[0])

    def test_empty_week_lists_and_invalid_day_counts_do_not_crash_or_make_zeros(self):
        graphql = {"contributionsCollection": {"contributionCalendar": {"weeks": [
            {"contributionDays": []}, {"contributionDays": [
                {"date": "invalid", "contributionCount": 4},
                {"date": "2024-01-01", "contributionCount": 1.5},
                {"date": "2024-01-02", "contributionCount": None},
            ]},
        ]}}}
        result = module_contributions(self.config, context(graphql=graphql), self.client())
        self.assertEqual(result.data, [])
        self.assertEqual(result.measurements["contributions"].availability, "auth_required")

    def test_missing_github_calendar_breakdown_is_unavailable_not_zero(self):
        from gitfetch.modules.builtin import module_contribution_breakdown, module_pull_requests
        ctx = context(graphql={"contributionsCollection": {"contributionCalendar": {}}, "openPRs": {"totalCount": 0}})
        result = module_contribution_breakdown(self.config, ctx, self.client())
        self.assertIsNone(result.data["commits"])
        self.assertIn("commits: unavailable", result.lines)
        prs = module_pull_requests(self.config, ctx, self.client())
        self.assertEqual(prs.data["open"], 0)
        self.assertIsNone(prs.data["merged"])

    def test_token_and_unsupported_module_provenance_is_internal_only(self):
        from gitfetch.cli import _token_required_result, _unsupported_provider_result
        client = self.client(BitbucketClient)
        result = _unsupported_provider_result("contributions", client)
        self.assertEqual(result.measurements["contributions"].availability, "unsupported")
        self.assertNotIn("measurements", json.dumps(_module_payload([result])))
        token = _token_required_result("organizations", self.client(GiteaClient))
        self.assertEqual(token.measurements["organizations"].availability, "auth_required")
        self.assertEqual(token.data, {"requires_token": True})

    def test_comparison_unknown_primary_languages_do_not_claim_no_overlap(self):
        metrics = [_compare_metrics(context([{"language": None}])), _compare_metrics(context([{"language": "Go"}]))]
        summary = _compare_summary_module(metrics)
        self.assertIn("observed language overlap: unavailable (primary-language metadata incomplete)", summary.lines)
        self.assertEqual(summary.data["language_overlap"], [])

    def test_profile_metric_scope_metadata_is_respected_in_comparisons(self):
        a, b = context(user={"login": "alice", "followers": 0}), context(user={"login": "bob", "followers": 1})
        a.measurements["followers"] = Measurement(0, "github", "count", "restricted followers", "auth_required")
        metrics = [_compare_metrics(a), _compare_metrics(b)]
        self.assertIsNone(metrics[0]["followers"])
        self.assertIn("unavailable: alice", _rank_line(metrics, "followers", "followers"))


if __name__ == "__main__":
    unittest.main()
