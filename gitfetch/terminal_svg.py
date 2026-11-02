"""Deterministic modern terminal SVG: semantic rows plus existing avatar encoder."""
from datetime import datetime, timezone

from gitfetch.design import color_role
from gitfetch.export_design import export_colors
from gitfetch.export_paint import xml
from gitfetch.images import fetch_avatar_image, fit_avatar_image
from gitfetch.layout import AvatarGeometry, Preferences, Viewport, avatar_may_fit, plan_profile
from gitfetch.terminal_text import cell_width, clip_text


def render_modern_svg(config, document):
    from gitfetch.formats import _ansi_segments
    from gitfetch.render import _render_avatar_image

    display = config['display']
    columns, rows = display.get('svg_columns', 100), display.get('svg_rows', 40)
    if not isinstance(columns, int) or not isinstance(rows, int) or not 20 <= columns <= 240 or not 2 <= rows <= 160:
        raise ValueError('SVG viewport requires 20–240 columns and 2–160 rows')
    preferences = Preferences(details=display.get('details', False), layout=display.get('layout', 'split'),
                              margin=display.get('margin', 0), avatar=display.get('avatar', True),
                              avatar_width=display.get('avatar_width', 100), avatar_style=display.get('avatar_style', 'ascii'),
                              visual_preset=display.get('visual_preset', 'balanced'))
    viewport = Viewport(columns, rows)
    image = fetch_avatar_image(document.avatar_reference) if document.avatar_reference and avatar_may_fit(viewport, preferences) else None
    if image is not None:
        image = fit_avatar_image(image, display.get('export_avatar_fit', 'original'))
    plan = plan_profile(document, viewport, preferences, AvatarGeometry(*image.size) if image else None,
                        reference_date=config.get('_reference_date') or datetime.now(timezone.utc).date())
    colors = export_colors(display)
    color = 'none' if display.get('theme') == 'mono' or config.get('_color_force') == 'off' else display.get('avatar_color', 'truecolor')
    color = 'truecolor' if color == 'auto' else color
    avatar = _render_avatar_image(image, plan.avatar_width, preferences.avatar_style, color,
                                  display.get('ascii_ramp', 'BS#&@$%*!:.')) if image is not None and plan.avatar_width else []
    height_rows = min(160, plan.height)
    content_rows = height_rows - int(plan.height > 160)
    width, height = columns*8+32, height_rows*16+32
    parts = [(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'font-family="{xml(display.get("svg_font_family", "monospace"))}" font-size="14">'),
             f'<rect width="{width}" height="{height}" fill="{colors["background"]}"/>']

    def text(value, x, y, fill, strong=False):
        if not value or y >= height-8:
            return
        parts.append(f'<text x="{x:g}" y="{y:g}" fill="{fill}" font-weight="{"600" if strong else "400"}" '
                     f'textLength="{cell_width(value)*8}" lengthAdjust="spacingAndGlyphs" xml:space="preserve">{xml(value)}</text>')

    for index, line in enumerate(avatar[:height_rows]):
        x, y = 16+plan.margin*8, 28+index*16
        for chunk, fg, bg in _ansi_segments(line):
            cells = cell_width(chunk)
            if bg:
                parts.append(f'<rect x="{x}" y="{y-12}" width="{cells*8}" height="16" fill="{bg}"/>')
            text(chunk, x, y, fg or colors['text'])
            x += cells*8
    text_x = 16+(plan.margin + (plan.avatar_width+3 if avatar and plan.composition == 'split' else 0))*8
    offset = plan.avatar_rows+1 if avatar and plan.composition == 'stack' else 0
    for index, row in enumerate(plan.rows[:max(0, content_rows-offset)]):
        x, y = text_x, 28+(index+offset)*16
        for span in row.spans:
            role = color_role(span.role, row.module)
            fill = colors[role] if config.get('_color_force') != 'off' and display.get('color', True) else colors['text']
            text(span.text, x, y, fill, span.role in {'identity', 'heading'} and display.get('theme') != 'mono')
            x += cell_width(span.text)*8
    if plan.height > 160:
        notice = clip_text('More selected content omitted', max(1, columns-2*plan.margin))
        text(notice, 16+plan.margin*8, 28+(height_rows-1)*16, colors['notice'])
    parts.append('</svg>')
    return '\n'.join(parts)
