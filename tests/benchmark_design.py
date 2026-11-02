"""CPU-only timings; prebuilt semantic data and decoded image, no I/O."""
from statistics import median
from timeit import repeat

from modern_fixtures import REFERENCE, avatar_image, fixture

from gitfetch.config import preset_config
from gitfetch.design import VISUAL_PRESETS
from gitfetch.layout import AvatarGeometry, Preferences, Viewport, plan_profile
from gitfetch.render import _paint_modern_rows, _render_avatar_image


def main():
    _, _, document = fixture(plugin=True, partial=True)
    image = avatar_image()
    for preset in VISUAL_PRESETS:
        for columns, rows in [(80, 24), (140, 40)]:
            preferences = Preferences(visual_preset=preset)
            viewport = Viewport(columns, rows)
            config = preset_config('minimal')
            config['_color_force'] = 'on'
            def plan(viewport=viewport, preferences=preferences):
                return plan_profile(document, viewport, preferences, AvatarGeometry(*image.size), reference_date=REFERENCE)
            result = plan()
            def paint(config=config, result=result):
                _paint_modern_rows(config, result.rows, 'ansi')
            def text_avatar(result=result):
                _render_avatar_image(image, result.avatar_width, 'halfblock', 'truecolor', 'BS#&@$%*!:.')
            timings = [median(repeat(fn, number=100, repeat=3)) * 10 for fn in (plan, paint, text_avatar)]
            print(f'{preset:8} {columns}x{rows}: plan {timings[0]:.3f} ms; paint {timings[1]:.3f} ms; '
                  f'text avatar {timings[2]:.3f} ms')


if __name__ == '__main__':
    main()
