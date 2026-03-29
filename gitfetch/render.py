from __future__ import annotations

import json
import os
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


def colorize(text: str, code: int, enabled: bool) -> str:
    if not enabled:
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

    enabled_color = bool(config["display"]["color"] and output_format == "ansi")
    lines = module_lines(visible_modules, enabled_color)
    if config["display"].get("avatar") and output_format in {"ansi", "plain"}:
        avatar = avatar_to_ascii(
            user.get("avatar_url"),
            width=config["display"]["avatar_width"],
            chars=config["display"]["ascii_ramp"],
        )
        if avatar:
            layout = config["display"].get("layout", "split")
            if layout == "split":
                return combine_split(avatar, lines)
            return "\n".join(avatar + [""] + lines)
    return "\n".join(lines)


def module_lines(modules: list[ModuleResult], color_enabled: bool) -> list[str]:
    lines: list[str] = []
    for module in modules:
        lines.append(colorize(module.title, COLOR_CODES["green"], color_enabled))
        lines.append(colorize("-" * len(module.title), COLOR_CODES["gray"], color_enabled))
        lines.extend(module.lines)
        lines.append("")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def avatar_to_ascii(avatar_url: str | None, width: int, chars: str) -> list[str]:
    if not avatar_url:
        return []
    ramp = list(chars)
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    try:
        urllib.request.urlretrieve(avatar_url, tmp.name)
        avatar_img = Image.open(tmp.name)
        source_width, source_height = avatar_img.size
        aspect_ratio = source_height / source_width
        target_height = max(1, int(aspect_ratio * width * 0.55))
        avatar_img = avatar_img.resize((width, target_height)).convert("L")
        pixels = avatar_img.getdata()
        scaled = [ramp[min(len(ramp) - 1, pixel * len(ramp) // 256)] for pixel in pixels]
        joined = "".join(scaled)
        return [joined[index:index + width] for index in range(0, len(joined), width)]
    finally:
        tmp.close()
        try:
            os.remove(tmp.name)
        except OSError:
            pass


def combine_split(avatar_lines: list[str], text_lines: list[str]) -> str:
    width = max((len(line) for line in avatar_lines), default=0)
    total_lines = max(len(avatar_lines), len(text_lines))
    output: list[str] = []
    for index in range(total_lines):
        avatar = avatar_lines[index] if index < len(avatar_lines) else " " * width
        text = text_lines[index] if index < len(text_lines) else ""
        if text:
            output.append(f"{avatar}   {text}")
        else:
            output.append(avatar)
    return "\n".join(output)
