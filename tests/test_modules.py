import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gitfetch.config import ConfigError
from gitfetch.modules import MODULE_HANDLERS, available_module_metadata, load_plugin_modules
from gitfetch.modules.builtin import (
    SPARKLINE_BLOCKS,
    module_languages,
    module_pinned,
    module_pull_requests,
    module_rate_limit,
    module_sparkline,
    module_streaks,
)


def _ctx_with_graphql(graphql):
    ctx = mock.Mock()
    ctx.graphql = graphql
    return ctx


def _config_with(name, defaults):
    return {"modules": {name: defaults, "order": []}, "display": {}}


class ModuleTests(unittest.TestCase):
    def test_plugins_do_not_leak_between_in_process_config_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plugin.py"
            path.write_text("MODULES = {'example_metric': lambda config, context, client: ['ok']}\n", encoding="utf-8")
            load_plugin_modules({"plugins": {"paths": [str(path)]}})
            self.assertIn("example_metric", MODULE_HANDLERS)
            self.assertIn("example_metric", available_module_metadata())
            load_plugin_modules({"plugins": {"paths": []}})
        self.assertNotIn("example_metric", MODULE_HANDLERS)
        self.assertNotIn("example_metric", available_module_metadata())

    def test_plugins_cannot_replace_builtin_modules(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plugin.py"
            path.write_text("MODULES = {'identity': lambda config, context, client: ['bad']}\n", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_plugin_modules({"plugins": {"paths": [str(path)]}})

    def test_bitbucket_languages_are_labelled_as_repository_counts(self) -> None:
        context = mock.Mock(repos=[{"languages_url": "bitbucket://language/Python"}])
        client = mock.Mock(language_breakdown_unit="repositories")
        client.get_languages.return_value = {"Python": 1}
        config = {"modules": {"languages": {"limit": 5, "workers": 1}}}
        result = module_languages(config, context, client)
        self.assertEqual(result.title, "Languages (Repo Count)")
        self.assertEqual(result.lines, ["Python 1 repo(s)"])
        self.assertEqual(result.data, [{"language": "Python", "repositories": 1}])

    def test_streaks_computes_current_and_longest(self) -> None:
        days = [
            {"date": f"2024-01-{i + 1:02d}", "contributionCount": 1 if i < 5 else 0}
            for i in range(10)
        ]
        days.extend(
            [{"date": f"2024-02-{i + 1:02d}", "contributionCount": 2} for i in range(3)]
        )
        graphql = {
            "contributionsCollection": {
                "contributionCalendar": {"weeks": [{"contributionDays": days}]}
            }
        }
        result = module_streaks(_config_with("streaks", {}), _ctx_with_graphql(graphql), mock.Mock())
        self.assertFalse(result.hidden)
        self.assertEqual(result.data["longest"], 5)
        self.assertEqual(result.data["current"], 3)
        self.assertEqual(result.data["total"], 11)

    def test_sparkline_emits_blocks_and_meta(self) -> None:
        days = [{"date": f"2024-01-{i + 1:02d}", "contributionCount": i} for i in range(10)]
        graphql = {
            "contributionsCollection": {
                "contributionCalendar": {"weeks": [{"contributionDays": days}]}
            }
        }
        result = module_sparkline(
            _config_with("sparkline", {"days": 10}), _ctx_with_graphql(graphql), mock.Mock()
        )
        self.assertEqual(len(result.lines), 2)
        self.assertEqual(result.lines[0][-1], SPARKLINE_BLOCKS[-1])
        self.assertIn("peak 9", result.lines[1])

    def test_pull_requests_renders_totals(self) -> None:
        graphql = {
            "openPRs": {"totalCount": 3},
            "mergedPRs": {"totalCount": 50},
            "closedPRs": {"totalCount": 5},
        }
        result = module_pull_requests(
            _config_with("pull_requests", {}), _ctx_with_graphql(graphql), mock.Mock()
        )
        self.assertIn("open: 3", result.lines)
        self.assertIn("merged: 50", result.lines)
        self.assertIn("closed: 5", result.lines)

    def test_pinned_renders_repos_and_hides_when_empty(self) -> None:
        graphql = {
            "pinnedItems": {
                "nodes": [
                    {
                        "__typename": "Repository",
                        "nameWithOwner": "alice/repo",
                        "stargazerCount": 100,
                        "primaryLanguage": {"name": "Python"},
                    }
                ]
            }
        }
        config = _config_with("pinned", {"limit": 6})
        result = module_pinned(config, _ctx_with_graphql(graphql), mock.Mock())
        self.assertFalse(result.hidden)
        self.assertIn("alice/repo (Python, ★100)", result.lines)

        empty = module_pinned(
            config, _ctx_with_graphql({"pinnedItems": {"nodes": []}}), mock.Mock()
        )
        self.assertTrue(empty.hidden)

    def test_rate_limit_renders_window(self) -> None:
        client = mock.Mock()
        client.get_rate_limit.return_value = {
            "resources": {
                "core": {"limit": 5000, "remaining": 4500, "reset": 9999999999},
                "graphql": {"limit": 5000, "remaining": 4000},
            }
        }
        result = module_rate_limit(_config_with("rate_limit", {}), mock.Mock(), client)
        self.assertIn("core: 4500/5000", result.lines)
        self.assertIn("graphql: 4000/5000", result.lines)
