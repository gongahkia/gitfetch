import tempfile
import unittest
from pathlib import Path

from gitfetch.config import ConfigError, load_config, preset_config, set_override, write_config


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
            self.assertEqual(loaded["profile"]["provider"], "github")
            self.assertIn("gitlab", loaded["providers"])
            self.assertFalse(loaded["display"]["avatar"])

    def test_invalid_config_types_raise_config_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.toml"
            path.write_text("[cache]\nttl_seconds = 'never'\n", encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "cache.ttl_seconds"):
                load_config(path)

    def test_all_builtin_module_setting_types_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.toml"
            path.write_text("[modules.releases]\nlimit = 'five'\n", encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "config.modules.releases.limit"):
                load_config(path)

    def test_set_override_coerces_values(self) -> None:
        config = preset_config("compact")
        set_override(config, "display.avatar", "false")
        set_override(config, "modules.languages.limit", "3")
        set_override(config, "profile.provider", "gitlab")
        self.assertFalse(config["display"]["avatar"])
        self.assertEqual(config["modules"]["languages"]["limit"], 3)
        self.assertEqual(config["profile"]["provider"], "gitlab")
