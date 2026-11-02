"""Release identity stays consistent without sending provider requests."""
import contextlib
import io
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from gitfetch import USER_AGENT, __version__
from gitfetch.cache import CacheStore
from gitfetch.cli import main
from gitfetch.config import preset_config
from gitfetch.images import _download
from gitfetch.providers import create_provider_client


class VersionTests(unittest.TestCase):
    def test_package_metadata_and_cli_match_runtime(self):
        metadata = tomllib.loads((Path(__file__).parents[1] / 'pyproject.toml').read_text())
        self.assertEqual(metadata['project']['version'], __version__)
        with contextlib.redirect_stdout(io.StringIO()) as output, self.assertRaises(SystemExit) as stopped:
            main(['--version'])
        self.assertEqual(stopped.exception.code, 0)
        self.assertEqual(output.getvalue().strip(), f'gitfetch {__version__}')

    def test_six_provider_user_agents_match_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            for provider in ('github', 'gitlab', 'bitbucket', 'gitea', 'forgejo', 'codeberg'):
                with self.subTest(provider=provider):
                    config = preset_config('minimal')
                    config['profile']['provider'] = provider
                    if provider == 'forgejo':
                        config['providers'][provider]['base_url'] = 'https://forgejo.synthetic.invalid/api/v1'
                    client = create_provider_client(config, '', CacheStore(Path(directory), False, 0), offline=True)
                    self.assertEqual(client.session.headers['User-Agent'], f'gitfetch/{__version__}')
                    client.session.close()

    def test_avatar_user_agent_matches_runtime_without_authentication(self):
        response = io.BytesIO(b'synthetic-avatar')
        response.headers = {}
        with mock.patch('gitfetch.images.urlopen', return_value=response) as opened:
            self.assertEqual(_download('https://synthetic.invalid/avatar.png'), b'synthetic-avatar')
        request = opened.call_args.args[0]
        self.assertEqual(request.get_header('User-agent'), USER_AGENT)
        self.assertEqual(USER_AGENT, f'gitfetch/{__version__}')
        self.assertIsNone(request.get_header('Authorization'))
