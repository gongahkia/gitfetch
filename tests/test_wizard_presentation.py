"""Wizard-only welcome screen; no real terminal clearing or config writes."""
import contextlib
import io
import os
import unittest
from unittest import mock

from gitfetch.cli import WIZARD_BANNER, run_config_wizard


class Terminal(io.StringIO):
    def isatty(self):
        return True


class WizardPresentationTests(unittest.TestCase):
    def run_wizard(self, *, tty=True, color=None, environment=None):
        stream = Terminal() if tty else io.StringIO()
        with (contextlib.redirect_stdout(stream), mock.patch('sys.stdin.isatty', return_value=tty),
              mock.patch.dict(os.environ, {'TERM': 'xterm-256color', **(environment or {})}, clear=True),
              mock.patch('builtins.input', side_effect=['', 'synthetic', '', '', '', '']) as ask):
            config = run_config_wizard(color=color)
        return stream.getvalue(), [c.args[0] for c in ask.call_args_list], config

    def test_interactive_clear_banner_then_colored_prompts(self):
        output, prompts, config = self.run_wizard()
        self.assertTrue(output.startswith('\033[2J\033[H\033[1;36m' + WIZARD_BANNER))
        self.assertIn("Let's set up", output)
        self.assertTrue(all(p.startswith('\033[36m') and p.endswith('\033[0m') for p in prompts))
        self.assertEqual(config['profile']['username'], 'synthetic')
        self.assertEqual(config['display']['format'], 'ansi')

    def test_captured_wizard_has_no_terminal_controls(self):
        for color in (None, True, False):
            output, prompts, _ = self.run_wizard(tty=False, color=color)
            self.assertTrue(output.startswith(WIZARD_BANNER))
            self.assertNotIn('\033', output + ''.join(prompts))

    def test_no_color_keeps_interactive_clear_without_styled_prompts(self):
        for color, environment in ((False, {}), (None, {'NO_COLOR': ''}), (None, {'NO_COLOR': '1'})):
            output, prompts, _ = self.run_wizard(color=color, environment=environment)
            self.assertTrue(output.startswith('\033[2J\033[H' + WIZARD_BANNER))
            self.assertNotIn('\033', output[len('\033[2J\033[H'):] + ''.join(prompts))

    def test_dumb_terminal_is_plain(self):
        output, prompts, _ = self.run_wizard(environment={'TERM': 'dumb'})
        self.assertNotIn('\033', output + ''.join(prompts))
