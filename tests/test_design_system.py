"""Design policy, semantic colors, responsive invariants and public contracts."""
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

import test_presentation_pipeline as pipeline
from design_fixtures import CASES, preview
from modern_fixtures import REFERENCE, fixture
from test_avatar_composition import asset
from test_terminal_graphics import decision

from gitfetch.cli import build_parser
from gitfetch.completions import script_for
from gitfetch.config import ConfigError, load_config, normalize_config, preset_config, set_override, write_config
from gitfetch.design import ROLE_PALETTE, THEMES, VISUAL_PRESETS, Color, resolve_colors
from gitfetch.formats import render_card_png
from gitfetch.images import AvatarLoader, AvatarResult
from gitfetch.layout import AvatarGeometry, Preferences, Viewport, plan_profile
from gitfetch.modules import MODULE_HANDLERS, build_module_list
from gitfetch.render import ANSI_RE, _paint_modern_rows, render_output
from gitfetch.terminal_output import build_terminal_frame
from gitfetch.terminal_text import cell_width

DIMENSIONS = [(30, 40), (40, 12), (60, 20), (80, 24), (100, 30), (120, 40),
              (140, 40), (200, 15), (200, 60)]


class DesignTests(unittest.TestCase):
    def test_config_selection_round_trip_validation_and_module_independence(self):
        config = preset_config('showcase')
        self.assertEqual(config['display']['visual_preset'], 'balanced')
        normalize_config(config)
        selected = build_module_list(config)
        for preset in VISUAL_PRESETS:
            set_override(config, 'display.visual_preset', preset)
            set_override(config, 'display.colors.accent', '#89b4fa')
            normalize_config(config)
            self.assertEqual(build_module_list(config), selected)
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'config.toml'
                write_config(path, config)
                loaded = load_config(path)
            self.assertEqual(loaded['display']['visual_preset'], preset)
            self.assertEqual(loaded['display']['colors'], {'accent': '#89b4fa'})
        for invalid in ['unknown', None, 12, ['balanced']]:
            config['display']['visual_preset'] = invalid
            with self.assertRaises(ConfigError):
                normalize_config(config)

    def test_cli_and_completions(self):
        for preset in VISUAL_PRESETS:
            self.assertEqual(build_parser().parse_args(['--visual-preset', preset]).visual_preset, preset)
        for shell in ['bash', 'zsh', 'fish']:
            script = script_for(shell)
            self.assertIn('visual-preset', script)
            self.assertIn('balanced compact showcase', script)
            if shell == 'fish':
                self.assertIn('minimal compact full showcase', script)

    def test_safe_custom_colors_and_strict_roles(self):
        for invalid in ['#abc', '#1234567', '#gg0000', 'red', '\x1b[31m', '#123456\n', 12, None]:
            config = preset_config('minimal')
            config['display']['colors'] = {'accent': invalid}
            with self.subTest(invalid=invalid), self.assertRaises(ConfigError):
                normalize_config(config)
        for invalid in [[], 'red', {'background': '#000000'}, {'__class__': '#ffffff'}]:
            config['display']['colors'] = invalid
            with self.assertRaises(ConfigError):
                normalize_config(config)
        colors = resolve_colors('default', {'accent': '#89b4fa', 'language': '#ffffff'})
        self.assertEqual(colors['accent'], Color(rgb=(137, 180, 250)))
        self.assertEqual(colors['contribution'], colors['accent'])
        self.assertEqual(colors['language'], Color(rgb=(255, 255, 255)))
        self.assertEqual(colors['text'], Color())
        for theme in THEMES:
            colors = resolve_colors(theme)
            self.assertEqual(set(colors), set(ROLE_PALETTE))
            self.assertEqual(colors['text'], Color())
            self.assertEqual(colors['muted'], Color())
            self.assertEqual(colors['handle'], Color())

    def test_color_modes_and_background_independence(self):
        _, _, document = fixture()
        plan = plan_profile(document, Viewport(140, 40), Preferences(avatar=False), reference_date=REFERENCE)
        config = preset_config('minimal')
        config['_color_force'] = 'on'
        config['display']['colors'] = {role: '#89b4fa' for role in ROLE_PALETTE}
        for theme in THEMES:
            config['display']['theme'] = theme
            full = '\n'.join(_paint_modern_rows(config, plan.rows, 'ansi'))
            if theme == 'mono':
                self.assertNotIn('\x1b', full)
            else:
                self.assertIn('38;2;137;180;250', full)
            self.assertNotIn('[48;', full)
            self.assertEqual(ANSI_RE.sub('', full), '\n'.join(r.text for r in plan.rows))
            config['_terminal_color'] = '256'
            reduced = '\n'.join(_paint_modern_rows(config, plan.rows, 'ansi'))
            self.assertNotIn('38;2;', reduced)
            config.pop('_terminal_color')
        config['display']['theme'] = 'default'
        config['_color_force'] = 'off'
        self.assertNotIn('\x1b', '\n'.join(_paint_modern_rows(config, plan.rows, 'ansi')))
        config.pop('_color_force')
        with mock.patch.dict(os.environ, {'NO_COLOR': '1'}), mock.patch('sys.stdout.isatty', return_value=True):
            self.assertNotIn('\x1b', '\n'.join(_paint_modern_rows(config, plan.rows, 'ansi')))

    def test_responsive_matrix_and_details_preserve_selected_content(self):
        for provider in ['github', 'gitlab', 'bitbucket', 'gitea', 'forgejo', 'codeberg']:
            _, _, document = fixture(provider, unicode=True, plugin=True, partial=True)
            for preset in VISUAL_PRESETS:
                for columns, rows in DIMENSIONS:
                    for layout in ['split', 'stack']:
                        for geometry in [None, AvatarGeometry(2048, 1024), AvatarGeometry(600, 1200)]:
                            with self.subTest(provider=provider, preset=preset, size=(columns, rows), layout=layout):
                                preferences = Preferences(visual_preset=preset, layout=layout, avatar_width=18)
                                plan = plan_profile(document, Viewport(columns, rows), preferences, geometry,
                                                    reference_date=REFERENCE)
                                self.assertLessEqual(plan.height, rows-2)
                                self.assertLessEqual(plan.avatar_width, 18)
                                self.assertLessEqual(plan.avatar_rows, 16)
                                self.assertTrue(all(cell_width(r.text) <= plan.text_width for r in plan.rows))
                                text = '\n'.join(r.text for r in plan.rows)
                                if plan.condensed:
                                    self.assertIn('--details', text)
                                self.assertNotIn('\x1b', text)
        _, _, document = fixture(plugin=True, unicode=True)
        for preset in VISUAL_PRESETS:
            plan = plan_profile(document, Viewport(30, 40), Preferences(details=True, avatar=False, visual_preset=preset),
                                reference_date=REFERENCE)
            self.assertFalse(plan.condensed)
            self.assertFalse(plan.omitted_modules)
            self.assertEqual(list(dict.fromkeys(r.module for r in plan.rows if r.module)),
                             [s.name for s in document.sections])
            text = '\n'.join(r.text for r in plan.rows)
            for expected in ['Shell', '--details', 'plugin']:
                # Plugin fixture contains its own actionable --details line.
                self.assertIn(expected, text)

    def test_presets_are_distinct_and_balanced_is_implicit(self):
        _, _, document = fixture()
        viewport = Viewport(100, 30)
        plans = {name: plan_profile(document, viewport, Preferences(visual_preset=name), AvatarGeometry(96, 96),
                                    reference_date=REFERENCE) for name in VISUAL_PRESETS}
        self.assertEqual(plans['balanced'], plan_profile(document, viewport, avatar=AvatarGeometry(96, 96),
                                                        reference_date=REFERENCE))
        self.assertLess(plans['compact'].avatar_width, plans['balanced'].avatar_width)
        self.assertGreater(plans['showcase'].avatar_width, plans['balanced'].avatar_width)
        self.assertEqual(len({tuple(r.text for r in p.rows) for p in plans.values()}), 3)
        self.assertFalse(any(not r.text for r in plans['compact'].rows))
        large = {preset: plan_profile(document, Viewport(140, 40), Preferences(visual_preset=preset),
                                      AvatarGeometry(96, 96), reference_date=REFERENCE)
                 for preset in VISUAL_PRESETS}
        self.assertNotEqual(large['balanced'].rows, large['showcase'].rows)

    def test_native_and_fallback_share_preset_and_fit(self):
        _, _, document = fixture()
        original = asset()
        for preset in VISUAL_PRESETS:
            config = preset_config('minimal')
            config['display'].update(avatar=True, presentation='modern', visual_preset=preset,
                                     colors={'identity': '#ffffff'})
            config['_color_force'] = 'on'
            loader = mock.Mock(spec=AvatarLoader)
            loader.load.return_value = AvatarResult(original)
            config['_avatar_loader'] = loader
            frame = build_terminal_frame(config, document, decision(), Viewport(100, 30), reference_date=REFERENCE)
            self.assertIsNotNone(frame.graphics)
            loader.load.assert_called_once()
            loader.reset_mock()
            fallback = build_terminal_frame(config, document, replace(decision(), backend='text', text_style='halfblock',
                                                                      color='256'), Viewport(100, 30), reference_date=REFERENCE)
            self.assertEqual(frame.plan, fallback.plan)
            self.assertNotIn('38;2;', fallback.text)
            self.assertNotIn('\x1b_G', fallback.text)
            self.assertEqual(frame.graphics.columns, frame.plan.avatar_width)
            config['display']['avatar'] = False
            loader.reset_mock()
            disabled = build_terminal_frame(config, document, decision(), Viewport(100, 30), reference_date=REFERENCE)
            loader.load.assert_not_called()
            self.assertIsNone(disabled.graphics)

    def test_classic_json_svg_card_png_parity(self):
        user, modules, document = fixture()
        config = preset_config('minimal')
        config['display'].update(avatar=False, presentation='classic')
        baseline = {fmt: render_output(config, user, modules, fmt, document=document)
                    for fmt in ['plain', 'ansi', 'json', 'svg', 'card']}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'card.png'
            render_card_png(config, user, modules, path)
            png = path.read_bytes()
            for preset in VISUAL_PRESETS:
                config['display'].update(visual_preset=preset, colors={'identity': '#00ff00', 'accent': '#ff0000'})
                for fmt, expected in baseline.items():
                    self.assertEqual(render_output(config, user, modules, fmt, document=document), expected)
                render_card_png(config, user, modules, path)
                self.assertEqual(path.read_bytes(), png)

    def test_golden_previews(self):
        root = Path(__file__).parent / 'fixtures' / 'design'
        for name in CASES:
            for ansi, suffix in [(False, 'txt'), (True, 'ansi')]:
                with self.subTest(case=name, ansi=ansi):
                    self.assertEqual(preview(name, ansi=ansi) + '\n', (root / f'{name}.{suffix}').read_text())


class DesignPipelineTests(unittest.TestCase):
    setUp = pipeline.PresentationPipelineTests.setUp
    select = pipeline.PresentationPipelineTests.select
    run_cli = pipeline.PresentationPipelineTests.run_cli

    def test_presets_do_not_change_collection_or_evaluate_modules_twice(self):
        self.select('identity', 'stats', 'languages')
        self.context.repos = [{'languages_url': 'https://example.test/one'}]
        for preset in VISUAL_PRESETS:
            for details in [False, True]:
                self.client.reset_mock()
                handlers = {name: mock.Mock(wraps=MODULE_HANDLERS[name]) for name in ['identity', 'stats', 'languages']}
                with mock.patch.dict(MODULE_HANDLERS, handlers):
                    _, documents = self.run_cli('--presentation', 'modern', '--visual-preset', preset,
                                                *(['--details'] if details else []))
                for handler in handlers.values():
                    handler.assert_called_once()
                self.client.get_context.assert_called_once()
                self.client.get_languages.assert_called_once()
                self.assertFalse(self.client.get_context.call_args.kwargs['include_graphql'])
                self.assertEqual(len(documents), 1)

    def test_cli_precedence_and_configured_username(self):
        self.config['display'].update(presentation='modern', visual_preset='compact')
        from gitfetch.render import render_output as actual
        with mock.patch('gitfetch.cli.render_output', wraps=actual) as render:
            self.run_cli('--set', 'display.visual_preset=balanced', '--visual-preset', 'showcase',
                         '--set', 'display.colors.identity=#123456')
        self.assertEqual(render.call_args.args[0]['display']['visual_preset'], 'showcase')
        self.assertEqual(render.call_args.args[0]['display']['colors']['identity'], '#123456')
        first, _ = self.run_cli()
        second, _ = self.run_cli('--user', 'alice')
        self.assertEqual(first, second)

    def test_plugin_order_exclusions_offline_and_watch(self):
        plugin = self.root / 'plugin.py'
        plugin.write_text("calls = []\ndef handler(config, context, client):\n    calls.append(1)\n    return ['plugin called ' + str(len(calls)), '\\x1b]0;unsafe\\a世界']\nMODULES = {'plugin': handler}\n")
        self.config['plugins'] = {'paths': [str(plugin)], 'modules': ['plugin'], 'allow_unsafe': True}
        self.select('stats', 'identity', 'plugin')
        for preset in VISUAL_PRESETS:
            with mock.patch('gitfetch.cli.run_watch_loop', side_effect=lambda render, *a, **k: render()):
                output, documents = self.run_cli('--presentation', 'modern', '--visual-preset', preset,
                                                '--details', '--offline', '--watch', '10')
            self.assertIn('plugin called 1', output)
            self.assertIn('世界', output)
            self.assertNotIn('\x1b', output)
            self.assertEqual([s.name for s in documents[0].sections], ['stats', 'identity', 'plugin'])
            self.assertEqual(len(documents), 1)
        self.config['modules']['identity']['enabled'] = False
        output, _ = self.run_cli('--presentation', 'modern', '--visual-preset', 'compact', '--details')
        self.assertNotIn('@alice', output)

    def test_cli_reduced_color_caps_custom_roles_even_with_explicit_style(self):
        self.config['display'].update(presentation='modern', colors={'identity': '#89b4fa'})
        with mock.patch.dict(os.environ, {'TERM': 'xterm-256color'}, clear=True):
            output, _ = self.run_cli('--color', '--avatar-style', 'ascii', '--visual-preset', 'showcase',
                                     output_format='ansi')
        self.assertIn('38;5;', output)
        self.assertNotIn('38;2;', output)
