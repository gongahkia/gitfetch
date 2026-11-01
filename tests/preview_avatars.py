"""Offline image previews; no URLs, terminal probes, downloads or credentials."""
import argparse
from pathlib import Path

from avatar_fixtures import CASES, image_bytes

from gitfetch.images import prepare_avatar
from gitfetch.render import _render_avatar_image

ROOT = Path(__file__).parent / "fixtures" / "avatars"


def preview(case, *, style=None, color="none", width=24):
    asset = prepare_avatar(image_bytes(case))
    styles = (style,) if style else ("ascii", "halfblock", "braille")
    lines = []
    for selected in styles:
        lines.append(f"{case} / {selected} / {asset.oriented_size[0]}x{asset.oriented_size[1]}")
        lines.extend(line.rstrip() for line in _render_avatar_image(asset.image, width, selected, color, "BS#&@$%*!:."))
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, default="transparent")
    parser.add_argument("--style", choices=("ascii", "halfblock", "braille"))
    parser.add_argument("--color", choices=("none", "256", "truecolor"), default="none")
    parser.add_argument("--width", type=int, default=24)
    parser.add_argument("--write", action="store_true", help="Regenerate synthetic source images and monochrome previews")
    args = parser.parse_args()
    if args.write:
        ROOT.mkdir(parents=True, exist_ok=True)
        for case in CASES:
            extension = "jpg" if case == "oriented" else "gif" if case == "animated" else "png"
            (ROOT / f"{case}.{extension}").write_bytes(image_bytes(case))
            (ROOT / f"{case}.txt").write_text(preview(case), encoding="utf-8")
    else:
        print(preview(args.case, style=args.style, color=args.color, width=args.width))


if __name__ == "__main__":
    main()
