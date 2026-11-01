"""Alpha fitting is explicit, lossless and shared before planning/encoding."""
import base64
import unittest
from dataclasses import replace
from io import BytesIO
from unittest import mock

from modern_fixtures import REFERENCE, fixture
from PIL import Image
from test_terminal_graphics import decision

from gitfetch.config import ConfigError, normalize_config, preset_config
from gitfetch.images import AvatarLoader, AvatarResult, prepare_avatar
from gitfetch.layout import Viewport
from gitfetch.render import ANSI_RE, _render_avatar_image, render_output
from gitfetch.terminal_output import build_terminal_frame
from gitfetch.terminal_text import cell_width


def asset(size=(100, 100), box=(20, 40, 80, 90), color=(240, 200, 160, 255)):
    image = Image.new('RGBA', size)
    if box:
        image.paste(color, box)
    with BytesIO() as output:
        image.save(output, 'PNG')
        return prepare_avatar(output.getvalue())


class CompositionTests(unittest.TestCase):
    def test_lossless_bounds_for_padding_and_portraits(self):
        for size, box in [((100, 100), (20, 40, 80, 90)), ((100, 100), (0, 30, 100, 100)),
                          ((80, 140), (10, 10, 70, 130)), ((160, 80), (30, 5, 150, 70))]:
            with self.subTest(size=size, box=box):
                original = asset(size, box, (0, 0, 0, 1))
                pixels = original.image.tobytes()
                fitted = original.for_presentation('visible')
                self.assertEqual(fitted.effective_size, (box[2]-box[0], box[3]-box[1]))
                self.assertEqual(fitted.image.tobytes(), original.image.crop(box).tobytes())
                self.assertEqual(original.image.tobytes(), pixels)
                self.assertEqual(fitted.original_size, size)
                self.assertIs(original.for_presentation(), original)

    def test_opaque_black_and_empty_images_are_not_cropped(self):
        for box in [(0, 0, 100, 100), None]:
            original = asset(box=box, color=(0, 0, 0, 255))
            self.assertIs(original.for_presentation('visible'), original)

    def test_partial_edge_pixels_are_retained(self):
        original = asset()
        original.image.putpixel((1, 2), (0, 0, 0, 1))
        fitted = original.for_presentation('visible')
        self.assertEqual(fitted.effective_size, (79, 88))
        self.assertEqual(fitted.image.getpixel((0, 0)), (0, 0, 0, 1))

    def test_intentional_logo_whitespace_is_preserved_by_default(self):
        original = asset(box=(45, 45, 55, 55))
        self.assertIs(original.for_presentation(), original)
        self.assertEqual(original.for_presentation('visible').effective_size, (10, 10))

    def test_backend_layout_matrix_uses_fitted_geometry_without_decoding(self):
        _, _, document = fixture()
        for size, box in [((100, 100), (20, 40, 80, 90)), ((80, 140), (10, 10, 70, 130)),
                          ((160, 80), (30, 5, 150, 70))]:
            original = asset(size, box)
            fitted = original.for_presentation('visible')
            for cols, rows in [(60, 20), (80, 24), (120, 40), (200, 15)]:
                for layout in ['split', 'stack']:
                    for backend in ['kitty', 'ascii', 'halfblock', 'braille']:
                        with self.subTest(size=size, viewport=(cols, rows), layout=layout, backend=backend):
                            config = preset_config('minimal')
                            config['display'].update(avatar=True, presentation='modern', layout=layout, avatar_fit='visible')
                            config['_color_force'] = 'on'
                            loader = mock.Mock(spec=AvatarLoader)
                            loader.load.return_value = AvatarResult(original)
                            config['_avatar_loader'] = loader
                            selected = decision()
                            if backend != 'kitty':
                                selected = replace(selected, backend='text', text_style=backend)
                            with mock.patch('PIL.Image.open', side_effect=AssertionError('duplicate decode')):
                                frame = build_terminal_frame(config, document, selected, Viewport(cols, rows),
                                                             reference_date=REFERENCE, image_number=42)
                            loader.load.assert_called_once_with(document.avatar_reference)
                            self.assertLessEqual(len(frame.text.splitlines()), rows-2)
                            self.assertTrue(all(cell_width(line) <= cols for line in frame.text.splitlines()))
                            if frame.plan.avatar_width:
                                style = 'halfblock' if backend == 'kitty' else backend
                                encoded = _render_avatar_image(fitted.image, frame.plan.avatar_width, style, 'truecolor', 'BS#&@$%*!:.')
                                self.assertEqual(len(encoded), frame.plan.avatar_rows)
                                if frame.graphics:
                                    payload = ''.join(chunk.split(';', 1)[1][:-2] for chunk in frame.graphics.chunks)
                                    with Image.open(BytesIO(base64.b64decode(payload))) as png:
                                        self.assertEqual(png.size, fitted.effective_size)
                                else:
                                    self.assertIn(encoded[0], frame.text)

    def test_reproduction_first_ink_moves_to_heading_row(self):
        original = asset((460, 460), (0, 204, 291, 460))
        for style in ['ascii', 'halfblock', 'braille']:
            def first(image, style=style):
                lines = _render_avatar_image(image, 22, style, 'truecolor', 'BS#&@$%*!:.')
                return next(i for i, line in enumerate(lines) if ANSI_RE.sub('', line).strip(' \u2800'))
            self.assertGreaterEqual(first(original.image), 4)
            self.assertEqual(first(original.for_presentation('visible').image), 0)

    def test_classic_json_and_exports_ignore_modern_fit(self):
        user, modules, document = fixture()
        config = preset_config('minimal')
        config['display'].update(avatar=True, presentation='classic')
        original = asset()
        for output_format in ['plain', 'json', 'svg', 'card']:
            with self.subTest(format=output_format), mock.patch('gitfetch.render._load_avatar', return_value=original.image):
                before = render_output(config, user, modules, output_format, document=document)
                config['display']['avatar_fit'] = 'visible'
                self.assertEqual(render_output(config, user, modules, output_format, document=document), before)
                config['display']['avatar_fit'] = 'original'

    def test_modern_serializer_shares_fit(self):
        user, modules, document = fixture()
        config = preset_config('minimal')
        config['display'].update(avatar=True, presentation='modern', avatar_fit='visible')
        original = asset()
        with mock.patch('gitfetch.render._load_avatar', return_value=original.image), mock.patch(
            'gitfetch.render._render_avatar_image', return_value=[]) as encode:
            render_output(config, user, modules, 'plain', document=document)
        self.assertEqual(encode.call_args.args[0].size, (60, 50))

    def test_invalid_fit_rejected(self):
        config = preset_config('minimal')
        config['display']['avatar_fit'] = 'guess'
        with self.assertRaises(ConfigError):
            normalize_config(config)


class DefaultPolicyTests(unittest.TestCase):
    def test_modern_default_and_explicit_overrides_share_backends(self):
        user, modules, document = fixture()
        original = asset()
        for fit, expected in [(None, (60, 50)), ('auto', (60, 50)),
                              ('visible', (60, 50)), ('original', (100, 100))]:
            for style in ['ascii', 'halfblock', 'braille']:
                with self.subTest(fit=fit, style=style):
                    config = preset_config('minimal')
                    config['display'].update(avatar=True, presentation='modern', avatar_style=style)
                    if fit is None:
                        config['display'].pop('avatar_fit')
                    else:
                        config['display']['avatar_fit'] = fit
                    loader = mock.Mock(spec=AvatarLoader)
                    loader.load.return_value = AvatarResult(original)
                    config['_avatar_loader'] = loader
                    with mock.patch('gitfetch.render._load_avatar', return_value=original.image), mock.patch(
                        'gitfetch.render._render_avatar_image', return_value=[]) as encode:
                        render_output(config, user, modules, 'plain', document=document)
                    self.assertEqual(encode.call_args.args[0].size, expected)
                    with mock.patch('gitfetch.terminal_output.encode_avatar', return_value=None) as native:
                        build_terminal_frame(config, document, decision(), Viewport(80, 24),
                                             reference_date=REFERENCE, image_number=1)
                    self.assertEqual(native.call_args.args[0].effective_size, expected)

    def test_config_round_trip_and_cli_override_preserve_intent(self):
        import tempfile
        from pathlib import Path

        from gitfetch.config import load_config, set_override, write_config

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.toml'
            for saved in [None, 'auto', 'original', 'visible']:
                path.write_text('[display]\npresentation = "modern"\n' +
                                (f'avatar_fit = "{saved}"\n' if saved else ''))
                explicit = set()
                config = load_config(path, explicit_display=explicit)
                self.assertEqual(config['display']['avatar_fit'], saved or 'auto')
                self.assertEqual('avatar_fit' in explicit, saved is not None)
                write_config(path, config)
                self.assertEqual(load_config(path)['display']['avatar_fit'], saved or 'auto')
                for override in ['original', 'visible', 'auto']:
                    set_override(config, 'display.avatar_fit', override)
                    normalize_config(config)
                    self.assertEqual(config['display']['avatar_fit'], override)

    def test_all_presets_keep_unresolved_policy(self):
        from gitfetch.config import PRESETS
        for name in PRESETS:
            self.assertEqual(preset_config(name)['display']['avatar_fit'], 'auto')

    def test_classic_and_exports_are_identical_for_every_policy(self):
        import tempfile
        from pathlib import Path

        from gitfetch.formats import render_card_png

        user, modules, document = fixture()
        original = asset()
        config = preset_config('minimal')
        config['display'].update(avatar=True)
        loader = mock.Mock(spec=AvatarLoader)
        loader.load.return_value = AvatarResult(original)
        config['_avatar_loader'] = loader
        for presentation in ['classic', 'modern', 'auto']:
            config['display']['presentation'] = presentation
            for output_format in ['json', 'svg', 'card'] + (['plain', 'ansi'] if presentation == 'classic' else []):
                outputs = []
                for fit in ['original', 'visible', 'auto']:
                    config['display']['avatar_fit'] = fit
                    outputs.append(render_output(config, user, modules, output_format, document=document))
                self.assertEqual(outputs[0], outputs[1])
                self.assertEqual(outputs[0], outputs[2])
            with tempfile.TemporaryDirectory() as directory:
                outputs = []
                for fit in ['original', 'visible', 'auto']:
                    config['display']['avatar_fit'] = fit
                    path = Path(directory) / 'card.png'
                    render_card_png(config, user, modules, path)
                    outputs.append(path.read_bytes())
                self.assertEqual(outputs[0], outputs[1])
                self.assertEqual(outputs[0], outputs[2])
