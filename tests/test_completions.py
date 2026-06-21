import shutil
import subprocess
import unittest

from gitfetch.completions import script_for


class CompletionsTests(unittest.TestCase):
    def test_bash_script_contains_completion_function(self) -> None:
        out = script_for("bash")
        self.assertIn("_gitfetch_completions", out)
        self.assertIn("complete -F", out)
        self.assertIn("ansi plain json svg card", out)
        self.assertIn("github gitlab bitbucket", out)

    def test_zsh_script_has_compdef(self) -> None:
        out = script_for("zsh")
        self.assertIn("#compdef gitfetch", out)
        self.assertIn("compdef _gitfetch gitfetch", out)

    def test_fish_script_uses_complete(self) -> None:
        out = script_for("fish")
        self.assertIn("complete -c gitfetch", out)
        self.assertIn("ansi plain json svg card", out)

    def test_bash_script_has_valid_syntax(self) -> None:
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("bash not available")
        result = subprocess.run(
            [bash, "-n"], input=script_for("bash"), text=True, capture_output=True
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
