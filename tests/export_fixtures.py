"""Fixed-date, offline scenes for export regression and manual previews."""
from dataclasses import replace
from io import BytesIO

from avatar_fixtures import image_bytes
from modern_fixtures import REFERENCE, fixture
from PIL import Image

from gitfetch.config import preset_config
from gitfetch.export_design import plan_profile_card, plan_summary_card
from gitfetch.images import prepare_avatar
from gitfetch.modules.builtin import ModuleResult

CASES = {
    'balanced': {'card_width': 720, 'card_height': 360},
    'compact': {'card_width': 600, 'card_height': 320, 'visual_preset': 'compact'},
    'showcase': {'card_width': 960, 'card_height': 540, 'visual_preset': 'showcase'},
    'dark': {'card_width': 720, 'card_height': 360, 'theme': 'dracula'},
    'light': {'card_width': 720, 'card_height': 360, 'theme': 'catppuccin-latte'},
    'custom': {'card_width': 720, 'card_height': 360, 'colors': {'identity': '#ffb86c', 'accent': '#bd93f9'}},
    'unicode-long': {'card_width': 960, 'card_height': 540, 'visual_preset': 'showcase'},
    'partial': {'card_width': 720, 'card_height': 360},
    'missing-avatar': {'card_width': 320, 'card_height': 180},
    'narrow-tall': {'card_width': 320, 'card_height': 640},
    'small': {'card_width': 128, 'card_height': 96},
    'repository': {'card_width': 720, 'card_height': 360},
    'organization': {'card_width': 720, 'card_height': 360},
    'comparison': {'card_width': 960, 'card_height': 540},
}


def fixture_plan(case):
    config = preset_config('minimal')
    config['display'].update(export_style='modern', **CASES[case])
    image = prepare_avatar(image_bytes('transparent')).image
    if case == 'missing-avatar':
        image = None
    if case in {'repository', 'organization', 'comparison'}:
        title, subtitle, lines = {
            'repository': ('alex-dev/terminal-tools', 'Repository · GitHub',
                           ['0 stars · 12 forks · Python', 'Last activity: unavailable', 'Languages: Python 73.0% · Shell 27.0%']),
            'organization': ('Synthetic Organization', 'Organization · Codeberg',
                             ['12 public repositories · followers: unsupported', 'Popular: example/core · 34 stars',
                              'Public members only · partial coverage']),
            'comparison': ('Alex vs River vs Sam', 'Comparison · public profiles',
                           ['Followers: Alex 12 = River 12 > Sam unavailable', 'Languages: non-comparable provider units',
                            'Repositories: Alex 4 · River 8 · Sam 0']),
        }[case]
        modules = [ModuleResult(case, case.title(), lines, {})]
        return plan_summary_card(title, subtitle, modules, config['display'], image)
    _, _, document = fixture(partial=case == 'partial', unicode=case == 'unicode-long', plugin=True)
    if case == 'unicode-long':
        document = replace(document, sections=tuple(replace(s, content=replace(s.content,
                    biography='世界 · cafe\u0301 · 👩🏽‍💻 · ' * 50)) if s.name == 'identity' else s for s in document.sections))
    return plan_profile_card(document, config['display'], image, reference_date=REFERENCE)


def image_copy(image):
    with BytesIO() as buffer:
        image.save(buffer, 'PNG')
        with Image.open(BytesIO(buffer.getvalue())) as loaded:
            return loaded.convert('RGBA')
