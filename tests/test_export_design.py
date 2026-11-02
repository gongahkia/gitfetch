"""Shared graphical layout, font portability, safety and semantic contracts."""
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest import mock
from xml.etree import ElementTree as ET

import test_contracts as contracts
import test_presentation_pipeline as pipeline
from avatar_fixtures import image_bytes
from export_fixtures import CASES, fixture_plan
from modern_fixtures import REFERENCE, fixture
from PIL import Image, ImageFont

from gitfetch.config import ConfigError, normalize_config, preset_config
from gitfetch.design import HEX_COLOR, THEMES
from gitfetch.export_design import (
    Picture,
    Rectangle,
    Text,
    dimensions,
    export_colors,
    plan_profile_card,
    plan_summary_card,
)
from gitfetch.export_fonts import FONT_PATH, clip, font, length
from gitfetch.export_paint import scene_png, scene_svg
from gitfetch.formats import render_card_png, render_card_svg, render_summary_card_png, render_summary_card_svg
from gitfetch.images import AvatarLoader, AvatarPolicy, AvatarResult, avatar_context, prepare_avatar
from gitfetch.modules.builtin import ModuleResult
from gitfetch.presentation import build_profile_document
from gitfetch.render import render_output

SVG = '{http://www.w3.org/2000/svg}'
SIZES = [(320, 180), (600, 320), (720, 360), (960, 540), (1200, 630), (320, 640), (128, 96)]


class ExportDesignTests(unittest.TestCase):
    def setUp(self):
        self.config = preset_config('minimal')
        self.config['display'].update(export_style='modern', avatar=False)
        self.user, self.modules, self.document = fixture(plugin=True, partial=True)
        network = mock.patch('requests.Session.request', side_effect=AssertionError('unexpected provider request'))
        network.start()
        self.addCleanup(network.stop)
        download = mock.patch('gitfetch.images._download', side_effect=AssertionError('unexpected avatar request'))
        download.start()
        self.addCleanup(download.stop)

    def plan(self, **settings):
        display = {**self.config['display'], **settings}
        return plan_profile_card(self.document, display, reference_date=REFERENCE)

    def test_preset_canvas_matrix_and_actual_font_bounds(self):
        for preset in ['balanced', 'compact', 'showcase']:
            for width, height in SIZES:
                with self.subTest(preset=preset, size=(width, height)):
                    plan = self.plan(visual_preset=preset, card_width=width, card_height=height)
                    self.assertEqual((plan.width, plan.height), (width, height))
                    for node in plan.nodes:
                        self.assertGreaterEqual(node.x, 0)
                        self.assertGreaterEqual(node.y, 0)
                        self.assertLessEqual(node.x+node.width, width+0.01)
                        if isinstance(node, Text):
                            self.assertLessEqual(length(node.text, node.size), node.width+0.01)
                            self.assertLessEqual(node.y+node.size+6, height)
                        else:
                            self.assertLessEqual(node.y+node.height, height)
                    svg = scene_svg(plan)
                    self.assertEqual(ET.fromstring(svg).get('width'), str(width))
                    with BytesIO() as output:
                        scene_png(plan, output)
                        with Image.open(output) as png:
                            self.assertEqual(png.size, (width, height))
        plans = [self.plan(visual_preset=preset) for preset in ['balanced', 'compact', 'showcase']]
        self.assertEqual(len({tuple((n.x, n.y, n.text, n.size) for n in p.nodes if isinstance(n, Text)) for p in plans}), 3)

    def test_dimensions_reject_unsafe_allocations_before_loading(self):
        for size in [(0, 0), (100, 50), (4097, 100), (4096, 4096), (True, 360), ('720', 360)]:
            with self.subTest(size=size), self.assertRaises((ValueError, TypeError)):
                dimensions({'card_width': size[0], 'card_height': size[1]})
        for style in ['modern', 'legacy']:
            self.config['display'].update(export_style=style, card_width=100_000)
            with (mock.patch('gitfetch.formats.fetch_avatar_image', side_effect=AssertionError('asset should not load')),
                  self.assertRaises(ValueError)):
                render_card_svg(self.config, self.user, self.modules)
            with self.assertRaises(ConfigError):
                normalize_config(self.config)

    def test_svg_and_png_painters_consume_identical_decisions(self):
        plan = self.plan(card_width=960, card_height=540)
        expected = [node.text for node in plan.nodes if isinstance(node, Text)]
        root = ET.fromstring(scene_svg(plan))
        self.assertEqual([element.text or '' for element in root.iter(SVG+'text')], expected)
        with BytesIO() as output, mock.patch('gitfetch.export_paint.ImageDraw.Draw') as draw:
            scene_png(plan, output)
        self.assertEqual([call.args[1] for call in draw.return_value.text.call_args_list], expected)
        self.assertEqual([call.kwargs['fill'] for call in draw.return_value.text.call_args_list],
                         [node.color for node in plan.nodes if isinstance(node, Text)])

    def test_disabled_hidden_and_identity_boundaries(self):
        user = {**self.user, 'followers': 987654321, 'bio': 'PRIVATE_BIO_SENTINEL'}
        hidden = ModuleResult('stats', 'SECRET_STATS', ['SECRET_LINE'], {'user': user}, hidden=True)
        for style in ['modern', 'legacy']:
            self.config['display']['export_style'] = style
            root = ET.fromstring(render_card_svg(self.config, user, [hidden]))
            text = ''.join(root.itertext())
            for secret in ['987654321', 'PRIVATE_BIO_SENTINEL', 'SECRET_LINE', 'SECRET_STATS']:
                self.assertNotIn(secret, text)
        document = build_profile_document(user, [], provider='github')
        plan = plan_profile_card(document, self.config['display'], reference_date=REFERENCE)
        self.assertFalse(any(node.text == 'Stats' for node in plan.nodes if isinstance(node, Text)))

    def test_measurement_units_denominators_zero_and_unknown(self):
        for provider, expected in [('github', '73.0%'), ('gitlab', '18/20 repos'), ('bitbucket', '12/20 repos')]:
            _user, _modules, document = fixture(provider)
            plan = plan_profile_card(document, {**self.config['display'], 'card_width': 1200, 'card_height': 630},
                                     reference_date=REFERENCE)
            text = '\n'.join(n.text for n in plan.nodes if isinstance(n, Text))
            self.assertIn(expected, text)
            self.assertIn('20/42 selected repos', text)
            if provider == 'gitlab':
                self.assertIn('prevalence', text)
            if provider == 'bitbucket':
                self.assertIn('Primary languages', text)
                self.assertIn('unsupported followers', text)
                self.assertNotIn('0 followers', text)
        user = {**self.user, 'followers': 0, 'following': None}
        document = build_profile_document(user, [ModuleResult('stats', 'Stats', [], {'user': user})], provider='github')
        text = '\n'.join(n.text for n in plan_profile_card(document, self.config['display'], reference_date=REFERENCE).nodes
                         if isinstance(n, Text))
        self.assertIn('0 followers', text)
        self.assertIn('unavailable following', text)

    def test_partial_calendar_dates_gaps_and_generic_plugin(self):
        plan = self.plan(card_width=1200, card_height=630)
        text = '\n'.join(n.text for n in plan.nodes if isinstance(n, Text))
        self.assertIn('unknown coverage', text)
        self.assertIn('2025-11-06', text)
        self.assertIn('? unknown', text)
        self.assertTrue(any(isinstance(n, Text) and n.text == '?' for n in plan.nodes))
        self.assertIn('Local notes', text)
        self.assertIn('plugin', text)
        self.assertTrue(plan.condensed)

    def test_all_theme_roles_custom_colors_and_light_mono(self):
        for theme in THEMES:
            colors = export_colors({'theme': theme})
            self.assertTrue(all(HEX_COLOR.fullmatch(color) for color in colors.values()))
            self.assertNotEqual(colors['text'], colors['background'])
        self.assertEqual(export_colors({'theme': 'catppuccin-latte'})['background'], '#eff1f5')
        self.assertEqual(export_colors({'colors': {'identity': '#123456'}})['identity'], '#123456')
        legacy = export_colors({'card_palette': {'accent': '#123456'}})
        self.assertEqual(legacy['language'], '#123456')
        custom = export_colors({'card_palette': {'accent': '#123456'}, 'colors': {'accent': '#abcdef'}})
        self.assertEqual(custom['language'], '#abcdef')
        mono = export_colors({'theme': 'mono', 'colors': {'identity': '#ff0000'}})
        self.assertEqual(mono['identity'], '#eeeeee')
        for colors in [{'identity': '#123'}, {'identity': 'red'}, {'identity': '#123456\n'}, {'script': '#ffffff'}]:
            with self.assertRaises((ValueError, TypeError)):
                export_colors({'colors': colors})
        with self.assertRaises(ValueError):
            export_colors({'card_palette': {'background': '"/><script/>'}})

    def test_untrusted_text_and_svg_are_self_contained(self):
        hostile = '<script onload="evil()">&"\x1b_Gsecret\x1b\\世界\ud800'
        modules = [ModuleResult('plugin', hostile, [hostile], {})]
        svg = render_summary_card_svg(self.config, hostile, hostile, modules)
        root = ET.fromstring(svg)
        for element in root.iter():
            self.assertNotIn(element.tag.split('}')[-1], ['script', 'foreignObject'])
            for key, value in element.attrib.items():
                self.assertFalse(key.lower().startswith('on'))
                if key.endswith('href'):
                    self.assertTrue(value.startswith('data:image/png;base64,'))
        self.assertNotIn('\x1b', svg)
        self.assertIn('&lt;script', svg)
        self.assertNotIn('secret', svg)
        self.assertIn('data:font/ttf;base64,', svg)
        self.assertNotIn('https://', svg)

    def test_avatar_reuse_alpha_aspect_and_export_fit_policy(self):
        original = prepare_avatar(image_bytes('transparent'))
        loader = mock.Mock(spec=AvatarLoader)
        loader.load.return_value = AvatarResult(original)
        self.config['_avatar_loader'] = loader
        self.config['display']['avatar'] = True
        from gitfetch.formats import _profile_plan
        def prepared_plan():
            with avatar_context(loader):
                return _profile_plan(self.config, self.user, self.modules, self.document)
        plan = prepared_plan()
        loader.load.assert_called_once()
        picture = next(n for n in plan.nodes if isinstance(n, Picture))
        self.assertIs(picture.image, original.image)
        self.assertAlmostEqual(picture.width/picture.height, original.image.width/original.image.height)
        self.assertEqual(picture.image.getchannel('A').getextrema()[0], 0)
        for fit in ['auto', 'visible', 'original']:
            self.config['display']['avatar_fit'] = fit
            self.assertIs(next(n for n in prepared_plan().nodes
                               if isinstance(n, Picture)).image, original.image)
        self.config['display']['export_avatar_fit'] = 'visible'
        fitted = next(n for n in prepared_plan().nodes if isinstance(n, Picture))
        self.assertLessEqual(fitted.image.width, original.image.width)
        self.assertEqual(original.effective_size, original.image.size)
        # A single real frame memo serves separate supported API painters too.
        memo = AvatarLoader()
        with (mock.patch('gitfetch.images._download', return_value=image_bytes('transparent')) as download,
              mock.patch('gitfetch.images.prepare_avatar', wraps=prepare_avatar) as decode):
            self.config['_avatar_loader'] = memo
            render_card_svg(self.config, self.user, self.modules, document=self.document)
            with BytesIO() as output:
                render_card_png(self.config, self.user, self.modules, output, document=self.document)
            download.assert_called_once()
            decode.assert_called_once()

    def test_offline_missing_avatar_does_not_fetch(self):
        self.config['display']['avatar'] = True
        self.config['_avatar_loader'] = AvatarLoader(AvatarPolicy(offline=True))
        with mock.patch('gitfetch.images._download', side_effect=AssertionError('network')):
            svg = render_card_svg(self.config, self.user, self.modules)
        self.assertFalse(list(ET.fromstring(svg).iter(SVG+'image')))

    def test_transparent_image_composites_on_background_without_black_key(self):
        from gitfetch.export_design import ExportPlan
        image = Image.new('RGBA', (20, 10))
        image.putpixel((5, 5), (0, 0, 0, 255))
        image.putpixel((6, 5), (255, 0, 0, 128))
        plan = ExportPlan(128, 96, {'background': '#ffffff'}, (Picture(0, 0, 20, 10, image),), False)
        with BytesIO() as output:
            scene_png(plan, output)
            with Image.open(output) as result:
                self.assertEqual(result.getpixel((0, 0)), (255, 255, 255))
                self.assertEqual(result.getpixel((5, 5)), (0, 0, 0))
                self.assertEqual(result.getpixel((6, 5)), (255, 127, 127))

    def test_font_bundle_unicode_and_missing_system_fonts(self):
        actual = ImageFont.truetype
        font.cache_clear()
        def without_system(name, *args, **kwargs):
            if isinstance(name, str) and name != str(FONT_PATH):
                raise OSError('optional font unavailable')
            return actual(name, *args, **kwargs)
        with mock.patch('PIL.ImageFont.truetype', side_effect=without_system):
            self.assertTrue(FONT_PATH.is_file())
            self.assertTrue(FONT_PATH.with_name('LICENSE-DejaVu.txt').is_file())
            for name in ['★', '组织', 'cafe\u0301', '👩🏽‍💻', '\U0010ffff', 'Very long name ' * 100]:
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory)/'org.png'
                    render_summary_card_png(self.config, name, 'Repositories — unknown', [], None, path)
                    with Image.open(path) as image:
                        self.assertEqual(image.size, (720, 360))
                self.assertLessEqual(length(clip(name, 80, 14), 14), 80)
        self.assertGreater(length('WWW', 14), length('iii', 14))

    def test_emergency_pillow10_bitmap_font_fallback_does_not_crash(self):
        bitmap = ImageFont.load_default()
        for style in ['modern', 'legacy']:
            self.config['display']['export_style'] = style
            with (mock.patch('gitfetch.export_fonts.font', return_value=bitmap),
                  mock.patch('gitfetch.export_paint.font', return_value=bitmap), BytesIO() as output):
                render_summary_card_png(self.config, '组织 👩🏽‍💻 cafe\u0301 ★', 'unknown — unavailable', [], None, output)
                with Image.open(output) as image:
                    self.assertEqual(image.size, (720, 360))

    def test_modern_terminal_svg_is_headless_and_deterministic(self):
        self.config['display'].update(presentation='modern', avatar=False, svg_columns=80, svg_rows=24)
        self.config['_reference_date'] = REFERENCE
        with mock.patch('shutil.get_terminal_size', side_effect=AssertionError('terminal query')):
            first = render_output(self.config, self.user, self.modules, 'svg', document=self.document)
            second = render_output(self.config, self.user, self.modules, 'svg', document=self.document)
        self.assertEqual(first, second)
        root = ET.fromstring(first)
        self.assertEqual(root.get('width'), '672')
        self.assertIn('Alex Rivera', ''.join(root.itertext()))
        self.assertNotIn('\x1b', first)
        self.config['display']['visual_preset'] = 'compact'
        self.assertNotEqual(first, render_output(self.config, self.user, self.modules, 'svg', document=self.document))
        huge = build_profile_document(self.user, [ModuleResult('plugin', 'Plugin',
                    [f'row {i}' for i in range(300)], {})], provider='github')
        self.config['display']['details'] = True
        bounded = render_output(self.config, self.user, self.modules, 'svg', document=huge)
        self.assertIn('More selected content omitted', ''.join(ET.fromstring(bounded).itertext()))
        self.assertEqual(ET.fromstring(bounded).get('height'), '2592')
        self.config['display']['presentation'] = 'classic'
        self.assertIn('<tspan', render_output(self.config, self.user, self.modules, 'svg', document=self.document))

    def test_summary_modes_and_fixtures_share_scene(self):
        for case in CASES:
            plan = fixture_plan(case)
            root = ET.fromstring(scene_svg(plan))
            self.assertEqual(root.get('height'), str(plan.height))
            self.assertTrue(any(isinstance(n, Text) and n.text == 'gitfetch' for n in plan.nodes))
        hidden = ModuleResult('hidden', 'SECRET_TITLE', ['SECRET_VALUE'], {}, hidden=True)
        plan = plan_summary_card('Comparison', 'non-comparable', [hidden], self.config['display'])
        self.assertNotIn('SECRET', ''.join(n.text for n in plan.nodes if isinstance(n, Text)))


    def test_scene_rejects_unsafe_colors_and_geometry(self):
        from gitfetch.export_design import ExportPlan
        for node in [Text(0, 0, 'safe', 12, '"/><script/>', 50),
                     Rectangle(float('nan'), 0, 10, 10, '#ffffff')]:
            plan = ExportPlan(128, 96, {'background': '#ffffff'}, (node,), False)
            with self.assertRaises(ValueError):
                scene_svg(plan)
            with BytesIO() as output, self.assertRaises(ValueError):
                scene_png(plan, output)

    def test_details_and_legacy_policy_are_explicit(self):
        condensed = self.plan(visual_preset='compact', card_width=320, card_height=180, details=True)
        self.assertEqual((condensed.width, condensed.height), (320, 180))
        self.assertTrue(condensed.condensed)
        before = self.user.copy()
        self.config['display'].update(export_style='auto', presentation='classic')
        automatic = render_card_svg(self.config, self.user, self.modules)
        self.config['display'].update(export_style='legacy', presentation='modern')
        self.assertEqual(automatic, render_card_svg(self.config, self.user, self.modules))
        self.config['display']['export_style'] = 'modern'
        modern = render_card_svg(self.config, self.user, self.modules)
        self.assertNotEqual(automatic[:200], modern[:200])
        self.assertEqual(self.user, before)


class ExportPipelineTests(unittest.TestCase):
    setUp = pipeline.PresentationPipelineTests.setUp
    select = pipeline.PresentationPipelineTests.select
    run_cli = pipeline.PresentationPipelineTests.run_cli

    def test_profile_exports_build_document_once_and_do_not_repeat_modules(self):
        from gitfetch.modules import MODULE_HANDLERS
        self.select('identity', 'stats', 'languages')
        self.context.repos = [{'languages_url': 'https://example.test/languages'}]
        for output_format in ['card', 'png', 'svg']:
            self.client.reset_mock()
            handlers = {name: mock.Mock(wraps=MODULE_HANDLERS[name]) for name in ['identity', 'stats', 'languages']}
            arguments = ['--save', str(self.root/'profile.png')] if output_format == 'png' else []
            with (mock.patch.dict(MODULE_HANDLERS, handlers),
                  mock.patch('gitfetch.cli.discover_terminal', side_effect=AssertionError('capability query'))):
                _, documents = self.run_cli('--presentation', 'modern', '--details', '--set', 'display.export_style=modern',
                                            *arguments, output_format=output_format)
            self.assertEqual(len(documents), 1)
            self.client.get_context.assert_called_once()
            self.client.get_languages.assert_called_once()
            self.assertFalse(self.client.get_context.call_args.kwargs['include_graphql'])
            for handler in handlers.values():
                handler.assert_called_once()


class ModeExportPipelineTests(contracts._ContractFixtures):
    def test_repo_org_compare_exports_and_request_counts(self):
        for command in [['repo', 'alice/project'], ['org', 'example'], ['compare', 'alice', 'bob']]:
            counts = []
            for output_format in ['json', 'svg', 'card', 'png']:
                client = self.client()
                path = Path(self.directory)/'mode.png'
                arguments = ['--set', 'display.export_style=modern', '--visual-preset', 'compact', *command]
                if output_format == 'png':
                    arguments = ['--save', str(path), *arguments]
                with mock.patch('gitfetch.modes.shutil', mock.Mock(
                        get_terminal_size=mock.Mock(side_effect=AssertionError('terminal query')))):
                    self.run_cli(arguments, client, output_format=output_format)
                counts.append({name: getattr(client, name).call_count for name in
                               ['get_repo', 'get_context', 'get_repo_languages', 'get_repo_contributors',
                                'get_repo_commits', 'get_org', 'get_org_members', 'get_org_repos']})
                if output_format == 'png':
                    with Image.open(path) as image:
                        self.assertEqual(image.size, (720, 360))
            self.assertEqual(counts[0], counts[1])
            self.assertEqual(counts[0], counts[2])
            self.assertEqual(counts[0], counts[3])
