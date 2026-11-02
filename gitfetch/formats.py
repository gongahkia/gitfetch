from __future__ import annotations

import base64
import re
from collections.abc import Iterator
from io import BytesIO
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageOps

from gitfetch.images import avatar_render, fetch_avatar_image
from gitfetch.language_icons import language_icon_data_uri, language_icon_image
from gitfetch.modules.builtin import ModuleResult
from gitfetch.terminal_text import cell_width, clip_text, sanitize_styled_text, sanitize_text

ANSI_TOKEN_RE = re.compile(r"\x1b\[([0-9;]*)m")

NAMED_FG = {
    30: "#000000", 31: "#cc0000", 32: "#4e9a06", 33: "#c4a000",
    34: "#3465a4", 35: "#75507b", 36: "#06989a", 37: "#d3d7cf",
    90: "#555753", 91: "#ef2929", 92: "#8ae234", 93: "#fce94f",
    94: "#729fcf", 95: "#ad7fa8", 96: "#34e2e2", 97: "#eeeeec",
}

def _truncate(text: Any, limit: int) -> str:
    return clip_text(text, limit)


CARD_PALETTE = {
    "background": "#0d1117",
    "surface": "#161b22",
    "border": "#30363d",
    "text": "#c9d1d9",
    "muted": "#8b949e",
    "accent": "#58a6ff",
    "good": "#3fb950",
    "warning": "#d29922",
}


def _xterm256_to_hex(index: int) -> str:
    index = max(0, min(255, index))
    if index < 16:
        return NAMED_FG.get(30 + index if index < 8 else 90 + (index - 8), "#cccccc")
    if index >= 232:
        gray = 8 + (index - 232) * 10
        return f"#{gray:02x}{gray:02x}{gray:02x}"
    cube = index - 16
    r = (cube // 36) * 51
    g = ((cube // 6) % 6) * 51
    b = (cube % 6) * 51
    return f"#{r:02x}{g:02x}{b:02x}"


def _ansi_segments(line: str) -> Iterator[tuple[str, str | None, str | None]]:
    fg: str | None = None
    bg: str | None = None
    pos = 0
    for match in ANSI_TOKEN_RE.finditer(line):
        if match.start() > pos:
            yield line[pos:match.start()], fg, bg
        codes = [int(c) for c in match.group(1).split(";") if c]
        i = 0
        while i < len(codes):
            code = codes[i]
            if code in {0, 39, 49}:
                fg = None if code in {0, 39} else fg
                bg = None if code in {0, 49} else bg
                if code == 0:
                    bg = None
            elif code in NAMED_FG:
                fg = NAMED_FG[code]
            elif code in {38, 48} and i + 1 < len(codes):
                kind = codes[i + 1]
                if kind == 5 and i + 2 < len(codes):
                    color = _xterm256_to_hex(codes[i + 2])
                    if code == 38:
                        fg = color
                    else:
                        bg = color
                    i += 2
                elif kind == 2 and i + 4 < len(codes):
                    red, green, blue = (max(0, min(255, value)) for value in codes[i+2:i+5])
                    color = f"#{red:02x}{green:02x}{blue:02x}"
                    if code == 38:
                        fg = color
                    else:
                        bg = color
                    i += 4
            i += 1
        pos = match.end()
    if pos < len(line):
        yield line[pos:], fg, bg


def render_terminal_svg(text: str, config: dict[str, Any]) -> str:
    from gitfetch.design import HEX_COLOR
    for key in ("svg_background", "svg_foreground"):
        if key in config["display"] and not HEX_COLOR.fullmatch(str(config["display"][key])):
            raise ValueError("invalid SVG color")
    char_width = 8.0
    line_height = 16.0
    font_size = 14
    background = config["display"].get("svg_background", "#0d1117")
    foreground = config["display"].get("svg_foreground", "#c9d1d9")
    raw_lines = [clip_text(sanitize_styled_text(line[:8192]), 240, trusted_ansi=True)
                 for line in text[:262144].split("\n")[:160]]
    visible_lengths = [cell_width(line) for line in raw_lines]
    max_len = max(visible_lengths) if visible_lengths else 0
    width = int(max_len * char_width + 32)
    height = int(len(raw_lines) * line_height + 32)
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" font-family="{_xml_escape(config["display"].get("svg_font_family", "monospace"))}" font-size="{font_size}">',
        f'<rect width="{width}" height="{height}" fill="{background}"/>',
        f'<g fill="{foreground}">',
    ]
    for i, line in enumerate(raw_lines):
        y = int(16 + (i + 1) * line_height - 4)
        parts.append(f'<text x="16" y="{y}" xml:space="preserve">')
        x_offset = 0
        for chunk, fg, bg in _ansi_segments(line):
            if not chunk:
                continue
            visible = chunk
            attrs = []
            if fg:
                attrs.append(f'fill="{fg}"')
            if bg:
                bg_x = 16 + x_offset * char_width
                bg_w = cell_width(visible) * char_width
                bg_y = int(16 + i * line_height)
                parts.insert(-1 - i, f'<rect x="{bg_x}" y="{bg_y}" width="{bg_w}" height="{int(line_height)}" fill="{bg}"/>')
            attr_str = " ".join(attrs)
            escaped = visible.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            parts.append(f'<tspan {attr_str}>{escaped}</tspan>')
            x_offset += cell_width(visible)
        parts.append("</text>")
    parts.append("</g></svg>")
    return "\n".join(parts)


def _embed_avatar_data(url: str | None, size: int) -> str | None:
    image = _avatar_image(url, size)
    if image is None:
        return None
    output = BytesIO()
    image.save(output, "PNG")
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _avatar_image(url: str | None, size: int) -> Image.Image | None:
    image = fetch_avatar_image(url)
    if image is None:
        return None
    # Keep the existing square/circular slot, fitting non-square sources inside
    # it without stretching. Padding is genuinely transparent, not black.
    fitted = ImageOps.contain(image, (size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size))
    canvas.paste(fitted, ((size - fitted.width) // 2, (size - fitted.height) // 2))
    return canvas


def _font(size: int):
    from gitfetch.export_fonts import font
    return font(size)


def _draw_text(draw, position, value, *, font, **kwargs):
    from gitfetch.export_fonts import drawable
    draw.text(position, drawable(sanitize_text(value), font), font=font, **kwargs)


def _module_data(modules: list[ModuleResult], name: str) -> Any:
    for module in modules:
        if module.name == name:
            return module.data
    return None


def _module_lines_text(modules: list[ModuleResult], name: str) -> list[str]:
    for module in modules:
        if module.name == name:
            return [sanitize_text(line) for line in module.lines]
    return []


@avatar_render
def _legacy_render_card_svg(config: dict[str, Any], user: dict[str, Any], modules: list[ModuleResult]) -> str:
    palette = dict(CARD_PALETTE)
    palette.update(config["display"].get("card_palette", {}) or {})
    width = int(config["display"].get("card_width", 720))
    height = int(config["display"].get("card_height", 360))
    avatar_size = 96
    avatar_data = _embed_avatar_data(user.get("avatar_url"), avatar_size) if config["display"].get("avatar", True) else None

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" font-family="{_xml_escape(config["display"].get("svg_font_family", "monospace"))}">',
        f'<rect width="{width}" height="{height}" rx="14" fill="{palette["background"]}" stroke="{palette["border"]}" stroke-width="1.5"/>',
    ]
    if avatar_data:
        parts.append(
            f'<defs><clipPath id="avatarClip"><circle cx="{32 + avatar_size // 2}" cy="{32 + avatar_size // 2}" r="{avatar_size // 2}"/></clipPath></defs>'
        )
        parts.append(
            f'<image href="{avatar_data}" x="32" y="32" width="{avatar_size}" height="{avatar_size}" clip-path="url(#avatarClip)"/>'
        )
    text_x = 32 + (avatar_size + 24 if avatar_data else 0)

    login = str(user.get("login", ""))
    name = user.get("name") or login
    bio = user.get("bio") or ""
    title_limit = max(12, (width - text_x - 32) // 12)
    bio_limit = max(20, (width - text_x - 32) // 7)
    parts.append(
        f'<text x="{text_x}" y="64" fill="{palette["text"]}" font-size="22" font-weight="600">{_xml_escape(_truncate(name, title_limit))}</text>'
    )
    parts.append(
        f'<text x="{text_x}" y="86" fill="{palette["accent"]}" font-size="14">@{_xml_escape(_truncate(login, title_limit))}</text>'
    )
    if bio:
        parts.append(
            f'<text x="{text_x}" y="110" fill="{palette["muted"]}" font-size="13">{_xml_escape(_truncate(bio, bio_limit))}</text>'
        )

    stats_y = 160
    stats_items: list[tuple[str, str]] = []
    if any(module.name == "stats" for module in modules):
        stats_items.append((_metric_value(user.get("public_repos")), "repos"))
        stats_items.append((_metric_value(user.get("followers")), "followers"))
        stats_items.append((_metric_value(user.get("following")), "following"))
    streaks = _module_data(modules, "streaks") or {}
    if streaks.get("current") is not None:
        stats_items.append((str(streaks["current"]), "current streak"))
    prs = _module_data(modules, "pull_requests") or {}
    if prs.get("merged") is not None:
        stats_items.append((str(prs["merged"]), "PRs merged"))
    column_w = (width - 64) / max(1, len(stats_items))
    for i, (value, label) in enumerate(stats_items):
        x = 32 + int(i * column_w)
        parts.append(
            f'<text x="{x}" y="{stats_y}" fill="{palette["text"]}" font-size="20" font-weight="600">{_xml_escape(value)}</text>'
        )
        parts.append(
            f'<text x="{x}" y="{stats_y + 18}" fill="{palette["muted"]}" font-size="12">{_xml_escape(label)}</text>'
        )

    languages = _module_data(modules, "languages") or []
    if languages:
        parts.append(
            f'<text x="32" y="220" fill="{palette["muted"]}" font-size="11" letter-spacing="1.2">LANGUAGES</text>'
        )
        x = 32
        show_icons = bool(config["display"].get("card_language_icons", True))
        for entry in languages[:5]:
            label = _truncate(entry.get("language", "?"), 18)
            icon_uri = language_icon_data_uri(label) if show_icons else None
            pill_w = max(60, len(label) * 8 + 18 + (24 if icon_uri else 0))
            if x + pill_w > width - 32:
                break
            parts.append(
                f'<rect x="{x}" y="232" rx="10" ry="10" width="{pill_w}" height="22" fill="{palette["surface"]}" stroke="{palette["border"]}"/>'
            )
            if icon_uri:
                parts.append(f'<image href="{icon_uri}" x="{x + 6}" y="235" width="16" height="16"/>')
                parts.append(
                    f'<text x="{x + 28}" y="247" fill="{palette["accent"]}" font-size="12">{_xml_escape(label)}</text>'
                )
            else:
                parts.append(
                    f'<text x="{x + pill_w // 2}" y="247" text-anchor="middle" fill="{palette["accent"]}" font-size="12">{_xml_escape(label)}</text>'
                )
            x += pill_w + 8

    pinned_lines = _module_lines_text(modules, "pinned")
    if pinned_lines:
        parts.append(
            f'<text x="32" y="282" fill="{palette["muted"]}" font-size="11" letter-spacing="1.2">PINNED</text>'
        )
        for i, line in enumerate(pinned_lines[:3]):
            parts.append(
                f'<text x="32" y="{300 + i * 16}" fill="{palette["text"]}" font-size="12">{_xml_escape(line[:80])}</text>'
            )

    parts.append(
        f'<text x="{width - 16}" y="{height - 14}" text-anchor="end" fill="{palette["muted"]}" font-size="10">gitfetch</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


@avatar_render
def _legacy_render_card_png(config: dict[str, Any], user: dict[str, Any], modules: list[ModuleResult], path) -> None:
    palette = dict(CARD_PALETTE)
    palette.update(config["display"].get("card_palette", {}) or {})
    width = int(config["display"].get("card_width", 720))
    height = int(config["display"].get("card_height", 360))
    img = Image.new("RGB", (width, height), palette["background"])
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=14, outline=palette["border"], width=2)

    title_font = _font(24)
    body_font = _font(14)
    small_font = _font(12)
    avatar_size = 96
    avatar = _avatar_image(user.get("avatar_url"), avatar_size) if config["display"].get("avatar", True) else None
    text_x = 32
    if avatar:
        mask = Image.new("L", (avatar_size, avatar_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, avatar_size, avatar_size), fill=255)
        img.paste(avatar, (32, 32), ImageChops.multiply(mask, avatar.getchannel("A")))
        text_x += avatar_size + 24

    login = str(user.get("login", ""))
    name = user.get("name") or login
    title_limit = max(12, (width - text_x - 32) // 12)
    bio_limit = max(20, (width - text_x - 32) // 7)
    _draw_text(draw, (text_x, 54), _truncate(name, title_limit), fill=palette["text"], font=title_font)
    _draw_text(draw, (text_x, 84), f"@{_truncate(login, title_limit)}", fill=palette["accent"], font=body_font)
    bio = user.get("bio") or ""
    if bio:
        _draw_text(draw, (text_x, 108), _truncate(bio, bio_limit), fill=palette["muted"], font=small_font)

    stats = [
        (_metric_value(user.get("public_repos")), "repos"),
        (_metric_value(user.get("followers")), "followers"),
        (_metric_value(user.get("following")), "following"),
    ] if any(module.name == "stats" for module in modules) else []
    streaks = _module_data(modules, "streaks") or {}
    if streaks.get("current") is not None:
        stats.append((str(streaks["current"]), "current streak"))
    prs = _module_data(modules, "pull_requests") or {}
    if prs.get("merged") is not None:
        stats.append((str(prs["merged"]), "PRs merged"))
    column_w = (width - 64) / max(1, len(stats))
    for i, (value, label) in enumerate(stats):
        x = 32 + int(i * column_w)
        _draw_text(draw, (x, 150), sanitize_text(value), fill=palette["text"], font=title_font)
        _draw_text(draw, (x, 178), label, fill=palette["muted"], font=small_font)

    languages = _module_data(modules, "languages") or []
    if languages:
        _draw_text(draw, (32, 216), "LANGUAGES", fill=palette["muted"], font=small_font)
        x = 32
        show_icons = bool(config["display"].get("card_language_icons", True))
        for entry in languages[:5]:
            label = _truncate(entry.get("language", "?"), 18)
            icon = language_icon_image(label, 16) if show_icons else None
            pill_w = max(60, len(label) * 8 + 18 + (24 if icon else 0))
            if x + pill_w > width - 32:
                break
            draw.rounded_rectangle((x, 232, x + pill_w, 254), radius=10, fill=palette["surface"], outline=palette["border"])
            if icon:
                img.paste(icon, (x + 6, 235), icon)
            _draw_text(draw, (x + (28 if icon else 10), 237), label, fill=palette["accent"], font=small_font)
            x += pill_w + 8

    pinned_lines = _module_lines_text(modules, "pinned")
    if pinned_lines:
        _draw_text(draw, (32, 280), "PINNED", fill=palette["muted"], font=small_font)
        for i, line in enumerate(pinned_lines[:3]):
            _draw_text(draw, (32, 298 + i * 16), line[:80], fill=palette["text"], font=small_font)

    _draw_text(draw, (width - 70, height - 24), "gitfetch", fill=palette["muted"], font=small_font)
    img.save(path, "PNG")


@avatar_render
def _legacy_render_summary_card_svg(
    config: dict[str, Any],
    title: str,
    subtitle: str,
    modules: list[ModuleResult],
    avatar_url: str | None = None,
) -> str:
    palette = dict(CARD_PALETTE)
    palette.update(config["display"].get("card_palette", {}) or {})
    width = int(config["display"].get("card_width", 720))
    height = int(config["display"].get("card_height", 360))
    avatar_size = 72
    avatar_data = _embed_avatar_data(avatar_url, avatar_size) if avatar_url and config["display"].get("avatar", True) else None
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" font-family="{_xml_escape(config["display"].get("svg_font_family", "monospace"))}">',
        f'<rect width="{width}" height="{height}" rx="14" fill="{palette["background"]}" stroke="{palette["border"]}" stroke-width="1.5"/>',
    ]
    text_x = 32
    if avatar_data:
        parts.append(f'<defs><clipPath id="avatarClip"><circle cx="{32 + avatar_size // 2}" cy="{32 + avatar_size // 2}" r="{avatar_size // 2}"/></clipPath></defs>')
        parts.append(f'<image href="{avatar_data}" x="32" y="32" width="{avatar_size}" height="{avatar_size}" clip-path="url(#avatarClip)"/>')
        text_x += avatar_size + 20
    title_limit = max(12, (width - text_x - 32) // 13)
    subtitle_limit = max(20, (width - text_x - 32) // 7)
    parts.append(f'<text x="{text_x}" y="62" fill="{palette["text"]}" font-size="23" font-weight="600">{_xml_escape(_truncate(title, title_limit))}</text>')
    if subtitle:
        parts.append(f'<text x="{text_x}" y="88" fill="{palette["accent"]}" font-size="13">{_xml_escape(_truncate(subtitle, subtitle_limit))}</text>')

    y = 132
    for module in modules[:5]:
        parts.append(f'<text x="32" y="{y}" fill="{palette["muted"]}" font-size="11" letter-spacing="1.2">{_xml_escape(module.title.upper())}</text>')
        y += 18
        for line in module.lines[:4]:
            parts.append(f'<text x="32" y="{y}" fill="{palette["text"]}" font-size="12">{_xml_escape(sanitize_text(line)[:95])}</text>')
            y += 16
            if y > height - 34:
                break
        y += 10
        if y > height - 34:
            break
    parts.append(f'<text x="{width - 16}" y="{height - 14}" text-anchor="end" fill="{palette["muted"]}" font-size="10">gitfetch</text>')
    parts.append("</svg>")
    return "\n".join(parts)


@avatar_render
def _legacy_render_summary_card_png(
    config: dict[str, Any],
    title: str,
    subtitle: str,
    modules: list[ModuleResult],
    avatar_url: str | None,
    path,
) -> None:
    palette = dict(CARD_PALETTE)
    palette.update(config["display"].get("card_palette", {}) or {})
    width = int(config["display"].get("card_width", 720))
    height = int(config["display"].get("card_height", 360))
    img = Image.new("RGB", (width, height), palette["background"])
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=14, outline=palette["border"], width=2)
    title_font = _font(24)
    body_font = _font(13)
    small_font = _font(11)

    text_x = 32
    avatar_size = 72
    avatar = _avatar_image(avatar_url, avatar_size) if avatar_url and config["display"].get("avatar", True) else None
    if avatar:
        mask = Image.new("L", (avatar_size, avatar_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, avatar_size, avatar_size), fill=255)
        img.paste(avatar, (32, 32), ImageChops.multiply(mask, avatar.getchannel("A")))
        text_x += avatar_size + 20
    title_limit = max(12, (width - text_x - 32) // 13)
    subtitle_limit = max(20, (width - text_x - 32) // 7)
    _draw_text(draw, (text_x, 44), _truncate(title, title_limit), fill=palette["text"], font=title_font)
    if subtitle:
        _draw_text(draw, (text_x, 78), _truncate(subtitle, subtitle_limit), fill=palette["accent"], font=body_font)

    y = 126
    for module in modules[:5]:
        _draw_text(draw, (32, y), sanitize_text(module.title).upper(), fill=palette["muted"], font=small_font)
        y += 18
        for line in module.lines[:4]:
            _draw_text(draw, (32, y), sanitize_text(line)[:95], fill=palette["text"], font=body_font)
            y += 16
            if y > height - 34:
                break
        y += 10
        if y > height - 34:
            break
    _draw_text(draw, (width - 70, height - 24), "gitfetch", fill=palette["muted"], font=small_font)
    img.save(path, "PNG")


def _xml_escape(text: str) -> str:
    return sanitize_text(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _metric_value(value: Any) -> str:
    return "unavailable" if value is None else str(value)


def _legacy_user(user, modules):
    if any(module.name == "identity" for module in modules):
        return user
    return {**user, "name": user.get("login"), "bio": ""}


def _legacy_export(config):
    style = config["display"].get("export_style", "auto")
    return style == "legacy" or style == "auto" and config["display"].get("presentation") == "classic"


def _validate_export(config):
    from gitfetch.export_design import dimensions, export_colors
    dimensions(config["display"])
    export_colors(config["display"])


def _profile_plan(config, user, modules, document=None):
    from datetime import datetime, timezone

    from gitfetch.export_design import plan_profile_card
    from gitfetch.images import fit_avatar_image
    from gitfetch.presentation import build_profile_document
    if document is None:
        provider = config.get("profile", {}).get("provider", "github")
        instance = config.get("providers", {}).get(provider, {}).get("base_url", "")
        document = build_profile_document(user, modules, provider=provider, instance=instance)
    image = fetch_avatar_image(document.avatar_reference) if config["display"].get("avatar", True) else None
    if image is not None:
        image = fit_avatar_image(image, config["display"].get("export_avatar_fit", "original"))
    return plan_profile_card(document, config["display"], image,
                             reference_date=config.get("_reference_date") or datetime.now(timezone.utc).date())


@avatar_render
def render_card_svg(config: dict[str, Any], user: dict[str, Any], modules: list[ModuleResult], *, document=None) -> str:
    _validate_export(config)
    visible = [module for module in modules if not module.hidden]
    if _legacy_export(config):
        return _legacy_render_card_svg(config, _legacy_user(user, visible), visible)
    from gitfetch.export_paint import scene_svg
    return scene_svg(_profile_plan(config, user, visible, document))


@avatar_render
def render_card_png(config: dict[str, Any], user: dict[str, Any], modules: list[ModuleResult], path, *, document=None) -> None:
    _validate_export(config)
    visible = [module for module in modules if not module.hidden]
    if _legacy_export(config):
        return _legacy_render_card_png(config, _legacy_user(user, visible), visible, path)
    from gitfetch.export_paint import scene_png
    scene_png(_profile_plan(config, user, visible, document), path)


def _summary_plan(config, title, subtitle, modules, avatar_url):
    from gitfetch.export_design import plan_summary_card
    from gitfetch.images import fit_avatar_image
    image = fetch_avatar_image(avatar_url) if avatar_url and config["display"].get("avatar", True) else None
    if image is not None:
        image = fit_avatar_image(image, config["display"].get("export_avatar_fit", "original"))
    return plan_summary_card(title, subtitle, modules, config["display"], image)


@avatar_render
def render_summary_card_svg(config: dict[str, Any], title: str, subtitle: str,
                            modules: list[ModuleResult], avatar_url: str | None = None) -> str:
    _validate_export(config)
    modules = [module for module in modules if not module.hidden]
    if _legacy_export(config):
        return _legacy_render_summary_card_svg(config, title, subtitle, modules, avatar_url)
    from gitfetch.export_paint import scene_svg
    return scene_svg(_summary_plan(config, title, subtitle, modules, avatar_url))


@avatar_render
def render_summary_card_png(config: dict[str, Any], title: str, subtitle: str,
                            modules: list[ModuleResult], avatar_url: str | None, path) -> None:
    _validate_export(config)
    modules = [module for module in modules if not module.hidden]
    if _legacy_export(config):
        return _legacy_render_summary_card_png(config, title, subtitle, modules, avatar_url, path)
    from gitfetch.export_paint import scene_png
    scene_png(_summary_plan(config, title, subtitle, modules, avatar_url), path)
