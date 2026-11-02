"""Reproduced final-acceptance failures; no real providers, plugins or shell rc writes."""
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest import mock

import test_presentation_pipeline as pipeline

from gitfetch.cli import main
from gitfetch.config import ConfigError, load_config, preset_config, write_config
from gitfetch.modules.plugins import _register_from_module, load_plugin_modules


class ReleaseAcceptanceTests(unittest.TestCase):
    def test_binary_config_is_a_configuration_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'invalid.toml'
            path.write_bytes(b'\xff\xfeinvalid')
            with self.assertRaises(ConfigError):
                load_config(path)
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                code = main(['--config', str(path), 'config', 'validate'])
            self.assertEqual(code, 2)
            self.assertNotIn('Traceback', stderr.getvalue())

    def test_wizard_eof_is_an_actionable_error(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch('builtins.input', side_effect=EOFError), \
             contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(main(['--config', str(Path(directory)/'new.toml'), 'config', 'wizard']), 2)
            self.assertIn('ended early', stderr.getvalue())

    def test_no_disabled_plugin_source_is_loaded(self):
        for requested in [[], ['disabled']]:
            config = preset_config('minimal')
            config['plugins'] = {'paths': ['untrusted-not-executed.py'], 'modules': requested, 'allow_unsafe': True}
            config['modules']['order'].append('disabled')
            config['modules']['disabled'] = {'enabled': False}
            with mock.patch('gitfetch.modules.plugins._load_module_from_path', side_effect=AssertionError('execution')):
                load_plugin_modules(config)

    def test_registration_failure_is_config_error(self):
        module = ModuleType('synthetic')
        module.register = mock.Mock(side_effect=ValueError('synthetic failure'))
        with self.assertRaisesRegex(ConfigError, 'registration failed'):
            _register_from_module(module, Path('synthetic.py'))


    def test_corrupt_cache_metadata_is_a_miss(self):
        from gitfetch.cache import CacheStore
        with tempfile.TemporaryDirectory() as directory:
            cache = CacheStore(Path(directory), True, 60)
            for payload in [b'\xff', b'[]', b'null', b'{"expires_at":'+b'9'*5000+b',"value":1}', json.dumps({'expires_at': 'later', 'value': 1}).encode(),
                            json.dumps({'expires_at': float('nan'), 'value': 1}).encode()]:
                cache._path_for('sample').write_bytes(payload)
                self.assertIsNone(cache.get('sample'))
                self.assertIsNone(cache.get('sample', allow_expired=True))

    def test_invalid_legacy_utf8_does_not_break_first_run(self):
        from gitfetch.config import migrate_legacy_username
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'legacy'
            for payload in [b'\xffinvalid', b'[]', b'null', b'42']:
                path.write_bytes(payload)
                with mock.patch('gitfetch.config.legacy_config_path', return_value=path):
                    self.assertIsNone(migrate_legacy_username())


    def test_github_token_is_not_an_implicit_cross_provider_fallback(self):
        from gitfetch.config import get_token
        for provider in ['gitlab', 'bitbucket', 'gitea', 'forgejo', 'codeberg']:
            config = preset_config('minimal')
            config['profile']['provider'] = provider
            with mock.patch.dict('os.environ', {'GITHUB_TOKEN': 'SYNTHETIC_ONLY'}, clear=True):
                self.assertEqual(get_token(None, config), '')
                self.assertEqual(get_token('EXPLICIT_CLI', config), 'EXPLICIT_CLI')

    def test_explicit_custom_and_provider_token_sources_are_preserved(self):
        from gitfetch.config import get_token
        config = preset_config('minimal')
        config['profile'].update(provider='forgejo', token_env='WORK_TOKEN')
        with mock.patch.dict('os.environ', {'WORK_TOKEN': 'CUSTOM', 'FORGEJO_TOKEN': 'PROVIDER'}, clear=True):
            self.assertEqual(get_token(None, config), 'CUSTOM')
        config['profile']['token_env'] = 'GITHUB_TOKEN'
        config['providers']['forgejo']['token_env'] = 'GITHUB_TOKEN'
        with mock.patch.dict('os.environ', {'GITHUB_TOKEN': 'DELIBERATELY_SELECTED'}, clear=True):
            self.assertEqual(get_token(None, config), 'DELIBERATELY_SELECTED')


class OutputFailureTests(unittest.TestCase):
    setUp = pipeline.PresentationPipelineTests.setUp
    select = pipeline.PresentationPipelineTests.select

    def test_unwritable_export_destinations_have_no_traceback(self):
        write_config(self.path, self.config)
        (self.root/'blocked').write_text('a file is not a directory')
        for output_format in ['plain', 'json', 'svg', 'card', 'png']:
            with contextlib.redirect_stderr(io.StringIO()) as stderr, contextlib.redirect_stdout(io.StringIO()):
                code = main(['--config', str(self.path), '--format', output_format, '--save',
                             str(self.root/'blocked'/'output')])
            self.assertEqual(code, 1)
            self.assertIn('filesystem error', stderr.getvalue())
            self.assertNotIn('Traceback', stderr.getvalue())


    def test_missing_png_destination_fails_before_provider_requests(self):
        write_config(self.path, self.config)
        for command in [[], ['repo', 'owner/project'], ['org', 'example'], ['compare', 'alice', 'bob']]:
            with (contextlib.redirect_stderr(io.StringIO()) as stderr,
                  mock.patch('gitfetch.cli.get_token', side_effect=AssertionError('token lookup')),
                  mock.patch('gitfetch.modes._client_for', side_effect=AssertionError('provider lookup'))):
                self.assertEqual(main(['--config', str(self.path), '--format', 'png', *command]), 2)
            self.assertIn('--save', stderr.getvalue())


    def test_non_utf8_output_fails_cleanly_without_rewriting_names(self):
        self.context.user['name'] = '世界'
        write_config(self.path, self.config)
        with io.TextIOWrapper(io.BytesIO(), encoding='ascii') as output, \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()) as stderr:
            code = main(['--config', str(self.path), '--format', 'plain'])
        self.assertEqual(code, 1)
        self.assertIn('UTF-8', stderr.getvalue())
        self.assertNotIn('Traceback', stderr.getvalue())
        self.assertEqual(self.context.user['name'], '世界')


class InstallerTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).parents[1]/'installer'/'installation.py'
        spec = importlib.util.spec_from_file_location('installer_under_test', path)
        self.installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.installer)

    def test_virtualenv_installs_local_checkout_without_shell_changes(self):
        with mock.patch.object(self.installer.sys, 'prefix', '/temporary/venv'), \
             mock.patch.object(self.installer.sys, 'base_prefix', '/base'), \
             mock.patch.object(self.installer.subprocess, 'run') as run, \
             mock.patch.object(self.installer, '_ensure_user_bin_on_path', side_effect=AssertionError('shell mutation')), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.installer.main(), 0)
        arguments = run.call_args.args[0]
        self.assertNotIn('--user', arguments)
        self.assertEqual(Path(arguments[-1]), Path(__file__).parents[1])

    def test_user_bin_path_is_quoted_and_not_matched_as_substring(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)/'a user base'
            rc = Path(directory)/'shellrc'
            rc.write_text('# existing configuration without a final newline')
            with mock.patch.object(self.installer.site, 'getuserbase', return_value=str(base)), \
                 mock.patch.object(self.installer, '_rc_file', return_value=rc), \
                 mock.patch.dict(self.installer.os.environ, {'PATH': str(base/'bin-other')}), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.installer._ensure_user_bin_on_path()
                self.installer._ensure_user_bin_on_path()
            self.assertEqual(rc.read_text().count('export PATH='), 1)
            self.assertTrue(rc.read_text().startswith('# existing configuration without a final newline\nexport PATH='))
            self.assertIn("'", rc.read_text())
