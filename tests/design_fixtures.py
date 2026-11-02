"""Deterministic terminal design previews; no network or real identities."""
import os
from datetime import datetime, timezone
from unittest import mock

from modern_fixtures import REFERENCE, avatar_image, fixture

from gitfetch.config import preset_config
from gitfetch.render import render_output

CASES = {
    'balanced-80x24': (80, 24, {}),
    'balanced-140x40': (140, 40, {}),
    'compact-60x20': (60, 20, {'visual_preset': 'compact'}),
    'compact-80x24': (80, 24, {'visual_preset': 'compact'}),
    'showcase-100x30': (100, 30, {'visual_preset': 'showcase'}),
    'showcase-140x40': (140, 40, {'visual_preset': 'showcase'}),
    'monochrome': (80, 24, {'theme': 'mono', 'visual_preset': 'showcase'}),
    'custom-colors': (100, 30, {'colors': {'identity': '#cba6f7', 'accent': '#89b4fa'}}),
    'narrow-unicode': (30, 40, {'visual_preset': 'compact', 'unicode': True}),
    'no-avatar': (80, 24, {'avatar': False, 'visual_preset': 'showcase'}),
    'details': (80, 24, {'details': True, 'visual_preset': 'compact'}),
}


def preview(case, *, ansi=False):
    columns, rows, settings = CASES[case]
    settings = dict(settings)
    user, modules, document = fixture(unicode=settings.pop('unicode', False), plugin=True, partial=True)
    config = preset_config('minimal')
    config['display'].update(presentation='modern', avatar=True, visual_preset='balanced')
    config['display'].update(settings)
    config['_color_force'] = 'on' if ansi else 'off'
    with (mock.patch('gitfetch.render.shutil.get_terminal_size', return_value=os.terminal_size((columns, rows))),
          mock.patch('gitfetch.render._load_avatar', return_value=avatar_image()),
          mock.patch('gitfetch.render.datetime') as clock):
        clock.now.return_value = datetime.combine(REFERENCE, datetime.min.time(), timezone.utc)
        return '\n'.join(line.rstrip() for line in render_output(config, user, modules, 'ansi' if ansi else 'plain',
                                                                 document=document).splitlines())
