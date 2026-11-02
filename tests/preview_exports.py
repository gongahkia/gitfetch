"""Generate deterministic SVG/PNG previews plus an inspection contact sheet."""
import argparse
from pathlib import Path

from export_fixtures import CASES, fixture_plan
from PIL import Image, ImageDraw

from gitfetch.export_fonts import font
from gitfetch.export_paint import scene_png, scene_svg


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('/tmp/gitfetch-06b-previews'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    sheet = Image.new('RGB', (1320, ((len(CASES)+2)//3)*300), '#30343c')
    draw = ImageDraw.Draw(sheet)
    for index, case in enumerate(CASES):
        plan = fixture_plan(case)
        (args.output / f'{case}.svg').write_text(scene_svg(plan), encoding='utf-8')
        scene_png(plan, args.output / f'{case}.png')
        with Image.open(args.output / f'{case}.png') as image:
            image.thumbnail((420, 260))
            x, y = (index % 3)*440+10, (index//3)*300+30
            sheet.paste(image, (x, y))
            draw.text((x, y-23), f'{case} · {plan.width}×{plan.height}', fill='white', font=font(14))
    sheet.save(args.output / 'contact-sheet.png')
    print(f'Wrote {len(CASES)} SVG/PNG pairs and contact-sheet.png to {args.output}')


if __name__ == '__main__':
    main()
