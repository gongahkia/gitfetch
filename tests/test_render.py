import unittest

from gitfetch.modules.builtin import ModuleResult
from gitfetch.render import render_output


class RenderTests(unittest.TestCase):
    def test_render_json_output(self) -> None:
        config = {
            "display": {
                "avatar": False,
                "color": False,
                "format": "json",
            }
        }
        modules = [ModuleResult(name="identity", title="Identity", lines=["@octocat"], data={"login": "octocat"})]
        rendered = render_output(config, {"login": "octocat"}, modules, "json")
        self.assertIn('"identity"', rendered)

    def test_render_plain_output(self) -> None:
        config = {
            "display": {
                "avatar": False,
                "color": False,
                "layout": "stack",
            }
        }
        modules = [ModuleResult(name="stats", title="Stats", lines=["8 repos"], data={"repos": 8})]
        rendered = render_output(config, {"login": "octocat"}, modules, "plain")
        self.assertIn("Stats", rendered)
        self.assertIn("8 repos", rendered)
