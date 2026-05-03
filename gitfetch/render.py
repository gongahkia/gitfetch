from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import urllib.request
from typing import Any

from PIL import Image

from gitfetch.modules.builtin import ModuleResult


COLOR_CODES = {
    "red": 91,
    "green": 92,
    "yellow": 93,
    "blue": 94,
    "purple": 95,
    "cyan": 96,
    "gray": 97,
}

THEMES: dict[str, dict[str, int]] = {
    "default": {"title": 92, "dim": 97, "key": 96, "value": 0, "accent": 93},
    "mono":    {"title": 0,  "dim": 0,  "key": 0,  "value": 0, "accent": 0},
    "solarized": {"title": 33, "dim": 90, "key": 36, "value": 0, "accent": 34},
    "dracula": {"title": 95, "dim": 90, "key": 96, "value": 0, "accent": 91},
    "gruvbox": {"title": 33, "dim": 90, "key": 32, "value": 0, "accent": 91},
    "nord":    {"title": 96, "dim": 90, "key": 94, "value": 0, "accent": 36},
}

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
SPLIT_GAP = 3
MIN_AVATAR_WIDTH = 20


def visible_len(text: str) -> int:
    return len(ANSI_RE.sub("", text))


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
    if callable(stream) and not stream():
        return False
    return True


def palette_for(config: dict[str, Any]) -> dict[str, int]:
    name = config["display"].get("theme", "default")
    return THEMES.get(name, THEMES["default"])


def colorize(text: str, code: int, enabled: bool) -> str:
    if not enabled or not code:
        return text
    return f"\033[{code}m{text}\033[00m"


def render_output(
    config: dict[str, Any],
    user: dict[str, Any],
    modules: list[ModuleResult],
    output_format: str,
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
    if output_format == "svg":
        from gitfetch.formats import render_terminal_svg
        forced = {**config, "_color_force": "on"}
        return render_terminal_svg(_render_visual(forced, user, visible_modules, "ansi"), config)
    return _render_visual(config, user, visible_modules, output_format)


def _render_visual(
    config: dict[str, Any],
    user: dict[str, Any],
    visible_modules: list[ModuleResult],
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
        term_cols = shutil.get_terminal_size((configured_width, 24)).columns
        usable_cols = max(0, term_cols - 2 * margin)
        if layout == "split":
            text_width = max((visible_len(line) for line in lines), default=0)
            available = usable_cols - text_width - SPLIT_GAP
        else:
            available = usable_cols
        if available >= MIN_AVATAR_WIDTH:
            avatar = render_avatar(
                user.get("avatar_url"),
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


def module_lines(modules: list[ModuleResult], color_enabled: bool, palette: dict[str, int]) -> list[str]:
    lines: list[str] = []
    for module in modules:
        lines.append(colorize(module.title, palette["title"], color_enabled))
        lines.append(colorize("-" * len(module.title), palette["dim"], color_enabled))
        for raw in module.lines:
            lines.append(_paint_value_line(raw, color_enabled, palette))
        lines.append("")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


_KEY_VALUE_RE = re.compile(r"^([A-Za-z][\w \-]*?):\s+(.+)$")


def _paint_value_line(line: str, color_enabled: bool, palette: dict[str, int]) -> str:
    if not color_enabled or not line:
        return line
    match = _KEY_VALUE_RE.match(line)
    if match:
        key, value = match.group(1), match.group(2)
        return f"{colorize(key + ':', palette['key'], True)} {colorize(value, palette['value'], True)}"
    return line


def _effective_avatar_color(config: dict[str, Any], output_format: str) -> str:
    requested = config["display"].get("avatar_color", "none")
    if requested == "none":
        return "none"
    if not color_enabled(config, output_format):
        return "none"
    return requested


def _load_avatar(url: str) -> Image.Image | None:
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    try:
        urllib.request.urlretrieve(url, tmp.name)
        return Image.open(tmp.name).copy()
    except (OSError, ValueError):
        return None
    finally:
        tmp.close()
        try:
            os.remove(tmp.name)
        except OSError:
            pass


def render_avatar(avatar_url: str | None, width: int, style: str, color_mode: str, ramp: str) -> list[str]:
    if not avatar_url:
        return []
    img = _load_avatar(avatar_url)
    if img is None:
        return []
    source_width, source_height = img.size
    aspect = source_height / source_width
    if style == "halfblock":
        return _render_halfblock(img, width, aspect, color_mode)
    if style == "braille":
        return _render_braille(img, width, aspect, color_mode)
    return _render_ascii(img, width, aspect, color_mode, ramp)


def avatar_to_ascii(avatar_url: str | None, width: int, chars: str) -> list[str]:
    return render_avatar(avatar_url, width, "ascii", "none", chars)


def _render_ascii(img: Image.Image, width: int, aspect: float, color_mode: str, ramp: str) -> list[str]:
    chars = list(ramp)
    target_h = max(1, int(aspect * width * 0.55))
    gray = img.resize((width, target_h)).convert("L")
    gray_pixels = list(gray.getdata())
    if color_mode == "none":
        joined = "".join(chars[min(len(chars) - 1, pixel * len(chars) // 256)] for pixel in gray_pixels)
        return [joined[i:i + width] for i in range(0, len(joined), width)]
    rgb = img.resize((width, target_h)).convert("RGB")
    rgb_pixels = list(rgb.getdata())
    lines = []
    for row in range(target_h):
        parts: list[str] = []
        for col in range(width):
            idx = row * width + col
            r, g, b = rgb_pixels[idx]
            ch = chars[min(len(chars) - 1, gray_pixels[idx] * len(chars) // 256)]
            parts.append(f"{_fg(r, g, b, color_mode)}{ch}")
        if color_mode != "none":
            parts.append("\x1b[0m")
        lines.append("".join(parts))
    return lines


def _render_halfblock(img: Image.Image, width: int, aspect: float, color_mode: str) -> list[str]:
    target_h = max(1, int(aspect * width * 0.5))
    pixel_h = target_h * 2
    rgb = img.resize((width, pixel_h)).convert("RGB")
    rgb_pixels = list(rgb.getdata())
    lines: list[str] = []
    for row in range(target_h):
        parts: list[str] = []
        for col in range(width):
            top = rgb_pixels[(row * 2) * width + col]
            bot = rgb_pixels[(row * 2 + 1) * width + col]
            if color_mode == "none":
                t_lum = sum(top) // 3
                b_lum = sum(bot) // 3
                if t_lum > 128 and b_lum > 128:
                    parts.append("█")
                elif t_lum > 128:
                    parts.append("▀")
                elif b_lum > 128:
                    parts.append("▄")
                else:
                    parts.append(" ")
            else:
                parts.append(f"{_fg(*top, mode=color_mode)}{_bg(*bot, mode=color_mode)}▀")
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
    pixel_h = target_h * 4
    rgb = img.resize((pixel_w, pixel_h)).convert("RGB")
    gray = img.resize((pixel_w, pixel_h)).convert("L")
    rgb_pixels = list(rgb.getdata())
    gray_pixels = list(gray.getdata())
    lines: list[str] = []
    for row in range(target_h):
        parts: list[str] = []
        for col in range(width):
            mask = 0
            r_sum = g_sum = b_sum = 0
            samples = 0
            for dx, dy, bit in _BRAILLE_OFFSETS:
                px = col * 2 + dx
                py = row * 4 + dy
                idx = py * pixel_w + px
                if gray_pixels[idx] > 128:
                    mask |= bit
                pr, pg, pb = rgb_pixels[idx]
                r_sum += pr
                g_sum += pg
                b_sum += pb
                samples += 1
            ch = chr(0x2800 + mask)
            if color_mode == "none":
                parts.append(ch)
            else:
                r = r_sum // samples
                g = g_sum // samples
                b = b_sum // samples
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
