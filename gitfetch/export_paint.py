"""Two small painters for the same fixed export scene; no semantic decisions."""
import base64
import math
from functools import lru_cache
from io import BytesIO
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw

from gitfetch.design import HEX_COLOR
from gitfetch.export_design import ExportPlan, Picture, Rectangle, Text, dimensions
from gitfetch.export_fonts import FONT_PATH, drawable, font
from gitfetch.terminal_text import sanitize_text


def xml(value: str) -> str:
    return escape(sanitize_text(value), {'"': '&quot;', "'": '&apos;'})


@lru_cache(maxsize=1)
def font_css() -> str:
    try:
        encoded = base64.b64encode(FONT_PATH.read_bytes()).decode('ascii')
    except OSError:
        return ''
    return '@font-face{font-family:Gitfetch;src:url(data:font/ttf;base64,' + encoded + ') format("truetype")}'


@lru_cache(maxsize=1)
def font_license() -> str:
    try:
        return FONT_PATH.with_name('LICENSE-DejaVu.txt').read_text(encoding='utf-8')
    except OSError:
        return ''


def image_uri(image: Image.Image) -> str:
    with BytesIO() as output:
        embedded = image.convert('RGBA')
        embedded.info.clear()
        embedded.save(output, 'PNG')
        return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode('ascii')


def ascent(size: int) -> int:
    face = font(size)
    return face.getmetrics()[0] if hasattr(face, 'getmetrics') else size


def validate_scene(plan: ExportPlan) -> None:
    dimensions({'card_width': plan.width, 'card_height': plan.height})
    if ('background' not in plan.colors or len(plan.nodes) > 4096
            or any(not isinstance(value, str) or not HEX_COLOR.fullmatch(value) for value in plan.colors.values())):
        raise ValueError('invalid or excessive export scene')
    for node in plan.nodes:
        if not all(math.isfinite(value) and value >= 0 for value in (node.x, node.y, node.width)):
            raise ValueError('invalid export geometry')
        if node.x+node.width > plan.width+1 or node.y > plan.height:
            raise ValueError('export geometry exceeds canvas')
        if isinstance(node, Text):
            if not 8 <= node.size <= 40 or len(node.text) > 4096 or not HEX_COLOR.fullmatch(node.color):
                raise ValueError('invalid export text')
        elif node.height < 0 or not math.isfinite(node.height) or node.y+node.height > plan.height+1:
            raise ValueError('invalid export geometry')
        elif isinstance(node, Rectangle) and not HEX_COLOR.fullmatch(node.color):
            raise ValueError('invalid export color')
        elif isinstance(node, Picture) and (min(node.image.size) < 1 or node.image.width*node.image.height > 4_194_304):
            raise ValueError('invalid export image')


def scene_svg(plan: ExportPlan) -> str:
    validate_scene(plan)
    parts = [(f'<svg xmlns="http://www.w3.org/2000/svg" width="{plan.width}" height="{plan.height}" '
             f'viewBox="0 0 {plan.width} {plan.height}">'),
             '<metadata id="font-license">' + xml(font_license()) + '</metadata>',
             '<defs><style>' + font_css() + '</style>'
             f'<clipPath id="canvas"><rect width="{plan.width}" height="{plan.height}"/></clipPath></defs>',
             f'<rect width="{plan.width}" height="{plan.height}" fill="{plan.colors["background"]}"/>',
             '<g clip-path="url(#canvas)" font-family="Gitfetch, sans-serif">']
    for index, node in enumerate(plan.nodes):
        if isinstance(node, Text):
            parts.append(f'<defs><clipPath id="text{index}"><rect x="{node.x:g}" y="{node.y:g}" '
                         f'width="{node.width:g}" height="{node.size+7}"/></clipPath></defs>')
            # The packaged face supplies the exact metrics used by the planner.
            parts.append(f'<text x="{node.x:g}" y="{node.y+ascent(node.size):g}" fill="{node.color}" '
                         f'font-size="{node.size}" clip-path="url(#text{index})" font-weight="{"600" if node.strong else "400"}">{xml(node.text)}</text>')
        elif isinstance(node, Rectangle):
            parts.append(f'<rect x="{node.x:g}" y="{node.y:g}" width="{node.width:g}" height="{node.height:g}" '
                         f'rx="{node.radius:g}" fill="{node.color}"/>')
        elif isinstance(node, Picture):
            parts.append(f'<image href="{image_uri(node.image)}" x="{node.x:g}" y="{node.y:g}" '
                         f'width="{node.width:g}" height="{node.height:g}" preserveAspectRatio="xMidYMid meet"/>')
    parts.append('</g></svg>')
    return '\n'.join(parts)


def scene_png(plan: ExportPlan, path) -> None:
    validate_scene(plan)
    canvas = Image.new('RGBA', (plan.width, plan.height), plan.colors['background'])
    draw = ImageDraw.Draw(canvas)
    for node in plan.nodes:
        if isinstance(node, Text):
            face = font(node.size)
            text = drawable(node.text, face)
            if hasattr(face, 'getmetrics'):
                draw.text((node.x, node.y+ascent(node.size)), text, font=face, fill=node.color, anchor='ls',
                          stroke_width=1 if node.strong else 0)
            else:
                draw.text((node.x, node.y), text, font=face, fill=node.color)
        elif isinstance(node, Rectangle):
            draw.rounded_rectangle((node.x, node.y, node.x+node.width, node.y+node.height),
                                   radius=node.radius, fill=node.color)
        elif isinstance(node, Picture):
            image = node.image.convert('RGBA').resize((max(1, round(node.width)), max(1, round(node.height))),
                                                     Image.Resampling.LANCZOS)
            canvas.alpha_composite(image, (round(node.x), round(node.y)))
    canvas.convert('RGB').save(path, 'PNG')
