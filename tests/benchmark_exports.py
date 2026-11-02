"""Local export CPU timings, excluding provider/network/disk latency."""
from io import BytesIO
from statistics import median
from timeit import repeat

from avatar_fixtures import image_bytes
from modern_fixtures import REFERENCE, fixture

from gitfetch.config import preset_config
from gitfetch.export_design import plan_profile_card
from gitfetch.export_fonts import length
from gitfetch.export_paint import scene_png, scene_svg
from gitfetch.images import AvatarLoader, AvatarResult, prepare_avatar


def timed(function, number=10):
    return median(repeat(function, number=number, repeat=3))*1000/number


def main():
    _, _, document = fixture(plugin=True, partial=True)
    payload = image_bytes('transparent')
    asset = prepare_avatar(payload)
    memo = AvatarLoader()
    memo._memo['https://synthetic.invalid/avatar'] = AvatarResult(asset)
    print(f'Avatar preparation: {timed(lambda: prepare_avatar(payload)):.3f} ms')
    print(f'Avatar memo reuse: {timed(lambda: memo.load("https://synthetic.invalid/avatar"), 1000):.6f} ms')
    print(f'Font measurement (cached face): {timed(lambda: length("A synthetic profile · café", 14), 100):.3f} ms')
    for preset in ['balanced', 'compact', 'showcase']:
        display = {**preset_config('minimal')['display'], 'card_width': 960, 'card_height': 540, 'visual_preset': preset}
        def plan(display=display):
            return plan_profile_card(document, display, asset.image, reference_date=REFERENCE)
        prepared = plan()
        scene_svg(prepared)  # Warm immutable font-data cache separately from serialization.
        def svg(prepared=prepared):
            return scene_svg(prepared)
        def png(prepared=prepared):
            with BytesIO() as output:
                scene_png(prepared, output)
        print(f'{preset}: plan {timed(plan):.3f} ms; SVG {timed(svg):.3f} ms; PNG {timed(png):.3f} ms')


if __name__ == '__main__':
    main()
