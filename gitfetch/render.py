from __future__ import annotations

import json
import math
import os
import re
import shutil
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from PIL import Image
from wcwidth import iter_graphemes

from gitfetch.images import avatar_render, fetch_avatar_image, fit_avatar_image
from gitfetch.modules.builtin import ModuleResult
from gitfetch.presentation import PresentationSection, ProfileDocument, build_profile_document
from gitfetch.terminal_text import cell_width, sanitize_text

COLOR_CODES = {
    "red": 91,
    "green": 92,
    "yellow": 93,
    "blue": 94,
    "purple": 95,
    "cyan": 96,
    "gray": 97,
}

ThemeValue = int | str

THEMES: dict[str, dict[str, ThemeValue]] = {
    "default":   {"title": 92, "dim": 97, "key": 96, "value": 0, "accent": 93},
    "mono":      {"title": 0,  "dim": 0,  "key": 0,  "value": 0, "accent": 0},
    "solarized": {"title": 33, "dim": 90, "key": 36, "value": 0, "accent": 34},
    "dracula":   {"title": 95, "dim": 90, "key": 96, "value": 0, "accent": 91},
    "gruvbox":   {"title": 33, "dim": 90, "key": 32, "value": 0, "accent": 91},
    "nord":      {"title": 96, "dim": 90, "key": 94, "value": 0, "accent": 36},
    "tokyonight":         {"title": "#7dcfff", "dim": "#565f89", "key": "#bb9af7", "value": 0, "accent": "#9ece6a"},
    "catppuccin-mocha":    {"title": "#cba6f7", "dim": "#585b70", "key": "#89b4fa", "value": 0, "accent": "#f5c2e7"},
    "catppuccin-macchiato":{"title": "#c6a0f6", "dim": "#5b6078", "key": "#8aadf4", "value": 0, "accent": "#f5bde6"},
    "catppuccin-frappe":   {"title": "#ca9ee6", "dim": "#626880", "key": "#8caaee", "value": 0, "accent": "#f4b8e4"},
    "catppuccin-latte":    {"title": "#8839ef", "dim": "#6c6f85", "key": "#1e66f5", "value": 0, "accent": "#ea76cb"},
    "monokai":     {"title": "#a6e22e", "dim": "#75715e", "key": "#66d9ef", "value": 0, "accent": "#f92672"},
    "one-dark":    {"title": "#61afef", "dim": "#5c6370", "key": "#c678dd", "value": 0, "accent": "#98c379"},
    "rose-pine":   {"title": "#ebbcba", "dim": "#6e6a86", "key": "#c4a7e7", "value": 0, "accent": "#f6c177"},
    "ayu":         {"title": "#ffcc66", "dim": "#5c6773", "key": "#5ccfe6", "value": 0, "accent": "#ffa759"},
    "material":    {"title": "#82aaff", "dim": "#546e7a", "key": "#c792ea", "value": 0, "accent": "#ffcb6b"},
    "everforest":  {"title": "#a7c080", "dim": "#859289", "key": "#7fbbb3", "value": 0, "accent": "#dbbc7f"},
}

THEME_NAMES = tuple(THEMES.keys())

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
SPLIT_GAP = 3
MIN_AVATAR_WIDTH = 20
MAX_TEXT_AVATAR_DIMENSION = 256


def visible_len(text: str) -> int:
    return cell_width(text)


def color_enabled(config: dict[str, Any], output_format: str) -> bool:
    if output_format != "ansi":
        return False
    forced = config.get("_color_force")
    if forced == "off":
        return False
    if forced == "on":
        return True
    if not config["display"].get("color", True):
        return False
    if os.environ.get("NO_COLOR"):
        return False
    stream = getattr(sys.stdout, "isatty", None)
    return not (callable(stream) and not stream())


def palette_for(config: dict[str, Any]) -> dict[str, ThemeValue]:
    name = config["display"].get("theme", "default")
    return THEMES.get(name, THEMES["default"])


def _ansi_for(code: ThemeValue) -> str:
    if isinstance(code, int):
        return f"\033[{code}m" if code else ""
    if isinstance(code, str) and code.startswith("#") and len(code) == 7:
        try:
            r = int(code[1:3], 16)
            g = int(code[3:5], 16)
            b = int(code[5:7], 16)
        except ValueError:
            return ""
        return f"\033[38;2;{r};{g};{b}m"
    return ""


def colorize(text: str, code: ThemeValue, enabled: bool) -> str:
    text = sanitize_text(text)
    if not enabled or not code:
        return text
    seq = _ansi_for(code)
    if not seq:
        return text
    return f"{seq}{text}\033[00m"


@avatar_render
def render_output(
    config: dict[str, Any],
    user: dict[str, Any],
    modules: list[ModuleResult],
    output_format: str,
    *,
    document: ProfileDocument | None = None,
) -> str:
    visible_modules = [module for module in modules if not module.hidden]
    if output_format == "json":
        return json.dumps(
            {
                "user": user.get("login"),
                "modules": {module.name: module.data for module in visible_modules},
            },
            indent=2,
        )
    if output_format == "card":
        from gitfetch.formats import render_card_svg
        return render_card_svg(config, user, visible_modules)
    if document is None:
        provider = config.get("profile", {}).get("provider", "github")
        instance = config.get("providers", {}).get(provider, {}).get("base_url", "")
        document = build_profile_document(user, modules, provider=provider, instance=instance)
    if output_format == "svg":
        from gitfetch.formats import render_terminal_svg
        forced = {**config, "_color_force": "on", "_skip_terminal_clamp": True}
        return render_terminal_svg(_render_visual(forced, document.avatar_reference, document.sections, "ansi"), config)
    if output_format in {"ansi", "plain"} and modern_enabled(config, output_format):
        return _render_modern(config, document, output_format)
    return _render_visual(config, document.avatar_reference, document.sections, output_format)


def modern_enabled(config: dict[str, Any], output_format: str) -> bool:
    """Presentation policy is separate from color, collection and export policy."""
    choice = config["display"].get("presentation", "auto")
    if choice != "auto":
        return choice == "modern"
    return output_format == "ansi" and not config.get("_captured_output", False) and sys.stdout.isatty()


def _paint_modern_rows(config: dict[str, Any], rows, output_format: str) -> list[str]:
    display = config["display"]
    enabled = color_enabled(config, output_format)
    palette = palette_for(config)
    # Descriptive text follows the user's foreground instead of a low-contrast
    # dark theme gray. Only decorative rail dots use the dim palette role.
    roles = {"identity": "title", "heading": "key", "text": "value", "muted": "value", "track": "dim",
             "accent": "accent", "stat": "title", "notice": "accent"}
    text_lines = []
    for row in rows:
        parts = []
        for span in row.spans:
            code = palette[roles[span.role]]
            # Existing avatar-color preference also bounds modern text colors;
            # reduced palettes never receive truecolor escape sequences.
            if display.get("avatar_color") == "256" and isinstance(code, str) and code.startswith("#"):
                sequence = _fg(int(code[1:3], 16), int(code[3:5], 16), int(code[5:7], 16), "256")
                parts.append(f"{sequence}{span.text}\x1b[0m" if enabled else span.text)
            else:
                painted = colorize(span.text, code, enabled)
                if enabled and display.get("theme") != "mono" and span.role in {"identity", "heading"}:
                    painted = f"\x1b[1m{painted}\x1b[0m"
                parts.append(painted)
        text_lines.append("".join(parts))
    return text_lines


def _render_modern(config: dict[str, Any], document: ProfileDocument, output_format: str) -> str:
    from gitfetch.layout import AvatarGeometry, Preferences, Viewport, avatar_may_fit, plan_profile

    display = config["display"]
    terminal = shutil.get_terminal_size((80, 24))
    viewport = Viewport(terminal.columns, terminal.lines)
    preferences = Preferences(
        details=display.get("details", False), layout=display.get("layout", "split"),
        margin=display.get("margin", 0), avatar=display.get("avatar", True),
        avatar_width=display.get("avatar_width", 100), avatar_style=display.get("avatar_style", "ascii"),
    )
    reference = datetime.now(timezone.utc).date()
    # Tiny/text-only output need not download an avatar. Source geometry and the
    # semantic document are measured once; only the final allocation is encoded.
    image = _load_avatar(document.avatar_reference) if avatar_may_fit(viewport, preferences) and document.avatar_reference else None
    if image is not None:
        image = fit_avatar_image(image, display.get("avatar_fit", "auto"))
    geometry = AvatarGeometry(*image.size) if image is not None else None
    plan = plan_profile(document, viewport, preferences, geometry, reference_date=reference)
    text_lines = _paint_modern_rows(config, plan.rows, output_format)
    avatar_lines = _render_avatar_image(
        image, plan.avatar_width, preferences.avatar_style,
        "none" if display.get("theme") == "mono" else _effective_avatar_color(config, output_format),
        display.get("ascii_ramp", "BS#&@$%*!:."),
    ) if image is not None and plan.avatar_width else []
    if avatar_lines and plan.composition == "split":
        output = combine_split(avatar_lines, text_lines)
    elif avatar_lines and plan.composition == "stack":
        output = "\n".join(avatar_lines + ([""] if text_lines else []) + text_lines)
    else:
        output = "\n".join(text_lines)
    return apply_margin(output, plan.margin)


def _render_visual(
    config: dict[str, Any],
    avatar_reference: str | None,
    visible_modules: Sequence[ModuleResult | PresentationSection],
    output_format: str,
) -> str:
    enabled_color = color_enabled(config, output_format)
    palette = palette_for(config)
    lines = module_lines(visible_modules, enabled_color, palette)
    margin = max(0, int(config["display"].get("margin", 0)))
    result: str | None = None
    if config["display"].get("avatar") and output_format in {"ansi", "plain"}:
        layout = config["display"].get("layout", "split")
        configured_width = int(config["display"]["avatar_width"])
        if config.get("_skip_terminal_clamp"):
            available = configured_width
        else:
            term_cols = shutil.get_terminal_size((configured_width, 24)).columns
            usable_cols = max(0, term_cols - 2 * margin)
            if layout == "split":
                text_width = max((visible_len(line) for line in lines), default=0)
                available = usable_cols - text_width - SPLIT_GAP
            else:
                available = usable_cols
        if available >= MIN_AVATAR_WIDTH:
            avatar = render_avatar(
                avatar_reference,
                width=min(configured_width, available),
                style=config["display"].get("avatar_style", "ascii"),
                color_mode=_effective_avatar_color(config, output_format),
                ramp=config["display"]["ascii_ramp"],
            )
            if avatar:
                if layout == "split":
                    result = combine_split(avatar, lines)
                else:
                    result = "\n".join(avatar + [""] + lines)
    if result is None:
        result = "\n".join(lines)
    return apply_margin(result, margin)


def apply_margin(text: str, margin: int) -> str:
    if margin <= 0:
        return text
    pad = " " * margin
    return "\n".join(pad + line for line in text.split("\n"))


def module_lines(modules: Sequence[ModuleResult | PresentationSection], color_enabled: bool, palette: dict[str, ThemeValue]) -> list[str]:
    lines: list[str] = []
    for module in modules:
        title = sanitize_text(module.title)
        lines.append(colorize(title, palette["title"], color_enabled))
        lines.append(colorize("-" * visible_len(title), palette["dim"], color_enabled))
        for raw in module.lines:
            lines.append(_paint_value_line(raw, color_enabled, palette))
        lines.append("")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


_KEY_VALUE_RE = re.compile(r"^([A-Za-z][\w \-]*?):\s+(.+)$")


def _paint_value_line(line: str, color_enabled: bool, palette: dict[str, ThemeValue]) -> str:
    line = sanitize_text(line)
    if not color_enabled or not line:
        return line
    match = _KEY_VALUE_RE.match(line)
    if match:
        key, value = match.group(1), match.group(2)
        return f"{colorize(key + ':', palette['key'], True)} {colorize(value, palette['value'], True)}"
    return line


def effective_avatar_color(config: dict[str, Any], output_format: str) -> str:
    requested = config["display"].get("avatar_color", "auto")
    if requested == "none":
        return "none"
    if not color_enabled(config, output_format):
        return "none"
    if requested == "auto":
        return "truecolor"
    return requested


_effective_avatar_color = effective_avatar_color


def _load_avatar(url: str) -> Image.Image | None:
    return fetch_avatar_image(url)


def render_avatar(avatar_url: str | None, width: int, style: str, color_mode: str, ramp: str) -> list[str]:
    if not avatar_url or width < 1:
        return []
    img = _load_avatar(avatar_url)
    if img is None:
        return []
    return _render_avatar_image(img, width, style, color_mode, ramp)


def _render_avatar_image(img: Image.Image, width: int, style: str, color_mode: str, ramp: str) -> list[str]:
    source_width, source_height = img.size
    if source_width < 1 or source_height < 1 or width < 1:
        return []
    aspect = source_height / source_width
    # Even a tiny compressed image can have an extreme aspect ratio. Bound
    # legacy/export upscaling as well as decoding, preserving proportions or
    # falling back to text when one column would already exceed the row limit.
    factor = 0.55 if style not in {"halfblock", "braille"} else 0.5
    width = min(width, MAX_TEXT_AVATAR_DIMENSION, math.floor(MAX_TEXT_AVATAR_DIMENSION / (aspect * factor)))
    if width < 1:
        return []
    if style == "halfblock":
        return _render_halfblock(img, width, aspect, color_mode)
    if style == "braille":
        return _render_braille(img, width, aspect, color_mode)
    return _render_ascii(img, width, aspect, color_mode, ramp)


def avatar_to_ascii(avatar_url: str | None, width: int, chars: str) -> list[str]:
    return render_avatar(avatar_url, width, "ascii", "none", chars)


# Ordered alpha coverage approximates transparency without inventing a terminal
# background. Opaque colors (including black) are never keyed out.
_ALPHA_MATRIX = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


def _alpha_visible(alpha: int, x: int, y: int) -> bool:
    return alpha > _ALPHA_MATRIX[y % 4][x % 4] * 16 + 8


def _avatar_samples(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    # Pillow's RGBA resampling uses premultiplied alpha, avoiding dark fringes.
    rgba = img if img.mode == "RGBA" else img.convert("RGBA")
    return rgba.resize(size, Image.Resampling.LANCZOS)


def _render_ascii(img: Image.Image, width: int, aspect: float, color_mode: str, ramp: str) -> list[str]:
    chars = [char for char in iter_graphemes(sanitize_text(ramp)) if cell_width(char) == 1]
    chars = chars or list("BS#&@$%*!:.")
    target_h = max(1, int(aspect * width * 0.55))
    sampled = _avatar_samples(img, (width, target_h))
    pixels = list(sampled.getdata())
    gray = list(sampled.convert("L").getdata())
    lines = []
    for row in range(target_h):
        parts = []
        for col in range(width):
            idx = row * width + col
            r, g, b, alpha = pixels[idx]
            if not _alpha_visible(alpha, col, row):
                parts.append(" ")
                continue
            # Preserve the historic luminance direction and every custom ramp.
            ch = chars[min(len(chars) - 1, gray[idx] * len(chars) // 256)]
            parts.append(ch if color_mode == "none" else f"{_fg(r, g, b, color_mode)}{ch}")
        if color_mode != "none":
            parts.append("\x1b[0m")
        lines.append("".join(parts))
    return lines


def _render_halfblock(img: Image.Image, width: int, aspect: float, color_mode: str) -> list[str]:
    target_h = max(1, int(aspect * width * 0.5))
    pixels = list(_avatar_samples(img, (width, target_h * 2)).getdata())
    lines = []
    for row in range(target_h):
        parts = []
        for col in range(width):
            top = pixels[row * 2 * width + col]
            bot = pixels[(row * 2 + 1) * width + col]
            t = _alpha_visible(top[3], col, row * 2)
            b = _alpha_visible(bot[3], col, row * 2 + 1)
            if color_mode == "none":
                t = t and sum(top[:3]) // 3 > 128
                b = b and sum(bot[:3]) // 3 > 128
                parts.append("█" if t and b else "▀" if t else "▄" if b else " ")
            elif t and b:
                parts.append(f"{_fg(top[0], top[1], top[2], color_mode)}{_bg(bot[0], bot[1], bot[2], color_mode)}▀")
            elif t or b:
                color = top if t else bot
                # Restore default background after any preceding opaque cell.
                parts.append(f"\x1b[49m{_fg(color[0], color[1], color[2], color_mode)}" + ("▀" if t else "▄"))
            else:
                parts.append("\x1b[0m ")
        if color_mode != "none":
            parts.append("\x1b[0m")
        lines.append("".join(parts))
    return lines


_BRAILLE_OFFSETS = [
    (0, 0, 0x01), (0, 1, 0x02), (0, 2, 0x04), (0, 3, 0x40),
    (1, 0, 0x08), (1, 1, 0x10), (1, 2, 0x20), (1, 3, 0x80),
]


def _render_braille(img: Image.Image, width: int, aspect: float, color_mode: str) -> list[str]:
    target_h = max(1, int(aspect * width * 0.5))
    pixel_w = width * 2
    sampled = _avatar_samples(img, (pixel_w, target_h * 4))
    pixels = list(sampled.getdata())
    gray = list(sampled.convert("L").getdata())
    lines = []
    for row in range(target_h):
        parts = []
        for col in range(width):
            mask = 0
            colors = []
            opaque = False
            for dx, dy, bit in _BRAILLE_OFFSETS:
                px, py = col * 2 + dx, row * 4 + dy
                idx = py * pixel_w + px
                r, g, b, alpha = pixels[idx]
                opaque = opaque or alpha > 0
                if gray[idx] > 128 and _alpha_visible(alpha, px, py):
                    mask |= bit
                    colors.append((r, g, b))
            ch = chr(0x2800 + mask) if opaque else " "
            if color_mode == "none" or not colors:
                parts.append(ch)
            else:
                # Only lit dots contribute color; transparent RGB is irrelevant.
                r, g, b = (sum(c[i] for c in colors) // len(colors) for i in range(3))
                parts.append(f"{_fg(r, g, b, color_mode)}{ch}")
        if color_mode != "none":
            parts.append("\x1b[0m")
        lines.append("".join(parts))
    return lines


def _fg(r: int, g: int, b: int, mode: str = "truecolor") -> str:
    if mode == "256":
        return f"\x1b[38;5;{_rgb_to_256(r, g, b)}m"
    return f"\x1b[38;2;{r};{g};{b}m"


def _bg(r: int, g: int, b: int, mode: str = "truecolor") -> str:
    if mode == "256":
        return f"\x1b[48;5;{_rgb_to_256(r, g, b)}m"
    return f"\x1b[48;2;{r};{g};{b}m"


def _rgb_to_256(r: int, g: int, b: int) -> int:
    if r == g == b:
        if r < 8:
            return 16
        if r > 248:
            return 231
        return 232 + (r - 8) // 10
    return 16 + 36 * (r // 51) + 6 * (g // 51) + (b // 51)


def combine_split(avatar_lines: list[str], text_lines: list[str]) -> str:
    width = max((visible_len(line) for line in avatar_lines), default=0)
    total_lines = max(len(avatar_lines), len(text_lines))
    output: list[str] = []
    for index in range(total_lines):
        if index < len(avatar_lines):
            line = avatar_lines[index]
            pad = " " * (width - visible_len(line))
        else:
            line = " " * width
            pad = ""
        text = text_lines[index] if index < len(text_lines) else ""
        if text:
            output.append(f"{line}{pad}   {text}")
        else:
            output.append(line + pad)
    return "\n".join(output)
