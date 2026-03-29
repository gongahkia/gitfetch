import tempfile
import unittest
from pathlib import Path

from gitfetch.config import load_config, preset_config, set_override, write_config


class ConfigTests(unittest.TestCase):
    def test_preset_config_enables_showcase(self) -> None:
        config = preset_config("showcase")
        self.assertTrue(config["modules"]["showcase"]["enabled"])
        self.assertEqual(config["modules"]["order"][0], "identity")

    def test_write_and_load_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.toml"
            config = preset_config("minimal")
            config["profile"]["username"] = "octocat"
            write_config(path, config)
            loaded = load_config(path)
            self.assertEqual(loaded["profile"]["username"], "octocat")
            self.assertFalse(loaded["display"]["avatar"])

    def test_set_override_coerces_values(self) -> None:
        config = preset_config("compact")
        set_override(config, "display.avatar", "false")
        set_override(config, "modules.languages.limit", "3")
        self.assertFalse(config["display"]["avatar"])
        self.assertEqual(config["modules"]["languages"]["limit"], 3)
