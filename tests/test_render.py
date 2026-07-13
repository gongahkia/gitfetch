import unittest
import tempfile
from pathlib import Path

from gitfetch.modules.builtin import ModuleResult
from gitfetch.formats import render_card_png
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

    def _visual_config(self) -> dict:
        return {
            "display": {
                "avatar": False,
                "color": True,
                "theme": "default",
                "format": "svg",
                "margin": 0,
                "ascii_ramp": "BS#&@$%*!:.",
                "avatar_width": 60,
                "layout": "split",
            }
        }

    def test_render_svg_emits_svg_root_with_color_spans(self) -> None:
        config = self._visual_config()
        modules = [ModuleResult(name="identity", title="Identity", lines=["@octocat"], data={})]
        rendered = render_output(config, {"login": "octocat"}, modules, "svg")
        self.assertTrue(rendered.startswith("<svg"))
        self.assertIn("@octocat", rendered)
        self.assertIn("<tspan", rendered)
        self.assertIn('font-family="monospace"', rendered)

    def test_render_card_emits_card_with_login_and_languages(self) -> None:
        config = self._visual_config()
        modules = [
            ModuleResult(
                name="languages",
                title="Languages",
                lines=["Python 90%"],
                data=[{"language": "Python", "bytes": 100}],
            ),
        ]
        user = {"login": "octocat", "name": "Octo", "public_repos": 5, "followers": 10, "following": 0}
        rendered = render_output(config, user, modules, "card")
        self.assertTrue(rendered.startswith("<svg"))
        self.assertIn("@octocat", rendered)
        self.assertIn("Python", rendered)
        self.assertIn('data:image/png;base64,', rendered)

    def test_card_truncates_long_text_and_keeps_language_pills_in_bounds(self) -> None:
        config = self._visual_config()
        config["display"]["card_width"] = 180
        long = "x" * 500
        modules = [
            ModuleResult(name="languages", title="Languages", lines=[], data=[{"language": long}]),
        ]
        rendered = render_output(config, {"login": long, "name": long, "bio": long}, modules, "card")
        self.assertNotIn(long, rendered)
        self.assertIn("…", rendered)

    def test_render_card_png_writes_file(self) -> None:
        config = self._visual_config()
        modules = [ModuleResult(name="languages", title="Languages", lines=["Python 90%"], data=[])]
        user = {"login": "octocat", "name": "Octo", "public_repos": 5, "followers": 10, "following": 0}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "card.png"
            render_card_png(config, user, modules, path)
            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 0)
