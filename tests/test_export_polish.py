"""Space-sensitive card composition; synthetic data, no providers or terminals."""
import unittest
import xml.etree.ElementTree as ET
from dataclasses import replace
from datetime import date
from io import BytesIO
from unittest import mock

from avatar_fixtures import image_bytes
from modern_fixtures import REFERENCE, fixture

from gitfetch.design import THEMES
from gitfetch.export_design import Picture, Rectangle, Text, export_colors, plan_profile_card, plan_summary_card
from gitfetch.export_fonts import font
from gitfetch.export_paint import ascent, scene_png, scene_svg, validate_scene
from gitfetch.images import fit_avatar_image, prepare_avatar
from gitfetch.modules.builtin import ModuleResult
from gitfetch.presentation import ContributionActivity, ContributionDay, ProfileIdentity
from gitfetch.semantics import Measurement

SIZES = [(320, 180), (600, 320), (720, 360), (960, 540), (1200, 630), (320, 640), (180, 800), (128, 96)]
PRESETS = ['balanced', 'compact', 'showcase']
SVG = '{http://www.w3.org/2000/svg}'


def texts(plan):
    return [node.text for node in plan.nodes if isinstance(node, Text)]


class ExportPolishTests(unittest.TestCase):
    def setUp(self):
        _, _, self.document = fixture(secondary=False)
        self.image = prepare_avatar(image_bytes('transparent')).image
        for target in ['requests.Session.request', 'gitfetch.images._download']:
            patch = mock.patch(target, side_effect=AssertionError('unexpected request'))
            patch.start()
            self.addCleanup(patch.stop)

    def plan(self, preset='balanced', size=(960, 540), **settings):
        return plan_profile_card(self.document, dict(visual_preset=preset, card_width=size[0],
                                 card_height=size[1], **settings), self.image, reference_date=REFERENCE)

    def test_available_space_restores_languages_and_charts_for_every_preset(self):
        for preset in PRESETS:
            plan = self.plan(preset)
            for language in ['Python', 'TypeScript', 'Go', 'Rust', 'Shell']:
                self.assertTrue(any(line.startswith(language+' ') for line in texts(plan)))
            self.assertTrue(any(line.startswith('Shown:') for line in texts(plan)))
            self.assertFalse(plan.condensed, (preset, texts(plan)))
        compact = self.plan('compact', (600, 320))
        self.assertTrue(any(line.startswith('Shell ') for line in texts(compact)))
        self.assertTrue(any(line.startswith('Shown:') for line in texts(compact)))
        narrow = self.plan(size=(320, 640))
        self.assertTrue(any(line.startswith('Shell ') for line in texts(narrow)))
        self.assertTrue(any(line.startswith('Shown:') for line in texts(narrow)))

    def test_avatar_proportions_scale_without_changing_source_or_aspect(self):
        for case in ['transparent', 'portrait', 'landscape']:
            asset = prepare_avatar(image_bytes(case)).image
            original = asset.tobytes()
            for fitting in ['original', 'visible']:
                image = fit_avatar_image(asset, fitting)
                for preset in PRESETS:
                    plan = plan_profile_card(self.document, {'visual_preset': preset,
                              'card_width': 960, 'card_height': 540}, image, reference_date=REFERENCE)
                    picture = next(n for n in plan.nodes if isinstance(n, Picture))
                    self.assertIs(picture.image, image)
                    self.assertAlmostEqual(picture.width/picture.height, image.width/image.height)
                    self.assertGreaterEqual(max(picture.width, picture.height), 112)
                self.assertEqual(asset.tobytes(), original)
        widths = [next(n.width for n in self.plan(p).nodes if isinstance(n, Picture)) for p in PRESETS]
        self.assertLess(widths[1], widths[0])
        self.assertLess(widths[0], widths[2])

    def test_canvas_matrix_has_no_text_collisions_or_orphan_language_heading(self):
        _, _, document = fixture(unicode=True, partial=True, plugin=True)
        document = replace(document, sections=tuple(
            replace(section, content=replace(section.content, display_name='林明 cafe\u0301 · 👩🏽‍💻 · ' * 30))
            if isinstance(section.content, ProfileIdentity) else section for section in document.sections))
        for preset in PRESETS:
            for width, height in SIZES:
                with self.subTest(preset=preset, canvas=(width, height)):
                    plan = plan_profile_card(document, {'visual_preset': preset, 'card_width': width,
                              'card_height': height}, self.image, reference_date=REFERENCE)
                    validate_scene(plan)
                    self.assertTrue(texts(plan)[0].startswith('林明'))
                    boxes = []
                    for node in plan.nodes:
                        if isinstance(node, Text) and node.text:
                            bbox = font(node.size).getbbox(node.text, anchor='ls')
                            box = (node.x+bbox[0], node.y+ascent(node.size)+bbox[1],
                                   node.x+bbox[2], node.y+ascent(node.size)+bbox[3])
                            self.assertLessEqual(box[2], width)
                            self.assertLessEqual(box[3], height)
                            for other in boxes:
                                self.assertFalse(min(box[2], other[2])-max(box[0], other[0]) > 1 and
                                                 min(box[3], other[3])-max(box[1], other[1]) > 1)
                            boxes.append(box)
                    if 'Languages · bytes' in texts(plan):
                        self.assertTrue(any(line.startswith('Python ') for line in texts(plan)))

    def test_contribution_dates_distinguish_zero_and_unknown_through_period_end(self):
        section = next(s for s in self.document.sections if isinstance(s.content, ContributionActivity))
        measurement = Measurement(5, 'forgejo', 'activity actions', 'observed window', coverage='partial',
                                  start='2026-01-01', end='2026-01-07')
        days = (ContributionDay(date(2026, 1, 1), 5), ContributionDay(date(2026, 1, 3), 0),
                ContributionDay(date(2026, 1, 4), None))
        content = ContributionActivity(days, measurement, days, measurement)
        document = replace(self.document, sections=(replace(section, content=content),))
        for details in [False, True]:
            plan = plan_profile_card(document, {'card_width': 960, 'card_height': 540, 'details': details},
                                     reference_date=REFERENCE)
            lines = texts(plan)
            self.assertIn('Activity · activity actions', lines)
            self.assertIn('5 · partial coverage', lines)
            self.assertIn('Shown: 2026-01-01 – 2026-01-07', lines)
            self.assertEqual(lines.count('?'), 5)
            bars = [n for n in plan.nodes if isinstance(n, Rectangle)]
            self.assertEqual(len(bars), 7)
            self.assertEqual(sum(n.color == plan.colors['contribution'] for n in bars), 1)
            self.assertEqual(bars[2].height, 3)  # observed zero, without a '?' marker
            self.assertFalse(plan.condensed)

    def test_card_palette_refinement_preserves_theme_and_override_authority(self):
        self.assertNotEqual(self.plan().colors['identity'], export_colors({})['identity'])
        self.assertEqual(export_colors({})['background'], '#0d1117')  # terminal SVG unchanged
        for theme in THEMES:
            plan = self.plan(theme=theme, colors={'identity': '#aabbcc', 'accent': '#abcdef'})
            if theme == 'mono':
                self.assertEqual(plan.colors['identity'], '#eeeeee')
            else:
                self.assertEqual(plan.colors['identity'], '#aabbcc')
                self.assertEqual(plan.colors['contribution'], '#abcdef')
        self.assertEqual(self.plan(card_palette={'text': '#112233'}).colors['identity'], '#112233')
        self.assertEqual(self.plan(colors={'identity': '#abcdef'},
                                  card_palette={'text': '#112233'}).colors['identity'], '#abcdef')

    def test_svg_png_share_text_image_chart_geometry_and_colors(self):
        for preset in PRESETS:
            plan = self.plan(preset)
            root = ET.fromstring(scene_svg(plan))
            self.assertEqual([n.text or '' for n in root.iter(SVG+'text')], texts(plan))
            picture = next(n for n in plan.nodes if isinstance(n, Picture))
            svg_picture = next(root.iter(SVG+'image'))
            self.assertEqual(float(svg_picture.get('width')), picture.width)
            self.assertEqual(float(svg_picture.get('height')), picture.height)
            rectangles = [n for n in plan.nodes if isinstance(n, Rectangle)]
            with BytesIO() as output, mock.patch('gitfetch.export_paint.ImageDraw.Draw') as draw:
                scene_png(plan, output)
            painted = draw.return_value.rounded_rectangle.call_args_list
            self.assertEqual([call.args[0] for call in painted],
                             [(n.x, n.y, n.x+n.width, n.y+n.height) for n in rectangles])
            self.assertEqual([call.kwargs['fill'] for call in painted], [n.color for n in rectangles])
            self.assertNotIn('\x1b', scene_svg(plan))
            for rectangle in rectangles:
                if rectangle.height == 5 and rectangle.width < 6:
                    self.assertEqual(rectangle.radius, 0)
            # Exercise real painting as well: tiny proportional bars exposed a
            # rounded-rectangle error in Pillow 10, beyond mocked-call parity.
            with BytesIO() as output:
                scene_png(plan, output)

    def test_small_cards_condense_and_summary_modes_remain_bounded(self):
        self.assertTrue(self.plan(size=(320, 180)).condensed)
        self.assertNotIn('Shown:', '\n'.join(texts(self.plan(size=(320, 180)))))
        for mode in ['repository', 'organization', 'comparison']:
            modules = [ModuleResult(mode, mode.title(), ['Measured zero: 0', 'Unavailable: unknown'], {}),
                       ModuleResult('hidden', 'SECRET', ['SECRET'], {}, hidden=True)]
            for preset in PRESETS:
                for width, height in SIZES:
                    plan = plan_summary_card('Long 世界 cafe\u0301 title', mode, modules,
                                 {'visual_preset': preset, 'card_width': width, 'card_height': height}, self.image)
                    validate_scene(plan)
                    self.assertNotIn('SECRET', texts(plan))
