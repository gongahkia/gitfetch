"""Terminal design tokens, independent of ANSI, assets and data collection."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

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


# Modern roles are presentation data, not escape sequences. Zero means the
# terminal foreground; only decorative tracks inherit the theme's dim color.
ROLE_PALETTE = {
    "identity": "title", "heading": "key", "text": "value", "muted": "value",
    "track": "dim", "accent": "accent", "stat": "title", "notice": "accent",
    "handle": "value", "language": "accent", "contribution": "accent", "warning": "accent",
}
def color_role(role: str, module: str) -> str:
    """Resolve chart accents without interpreting text or provider measurements."""
    if role == "accent":
        return {"languages": "language", "contributions": "contribution"}.get(module, role)
    return role


HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}\Z")


def validate_colors(colors: Any) -> None:
    if not isinstance(colors, dict):
        raise TypeError("display.colors must be a table")
    for role, value in colors.items():
        if role not in ROLE_PALETTE:
            raise ValueError(f"unknown display.colors role: {role!r}")
        if not isinstance(value, str) or not HEX_COLOR.fullmatch(value):
            raise ValueError(f"display.colors.{role} must be a six-digit hexadecimal color")


@dataclass(frozen=True)
class Color:
    """Device-independent RGB or terminal palette index; empty means foreground."""
    rgb: tuple[int, int, int] | None = None
    terminal_index: int | None = None


def resolve_colors(theme: str, overrides: dict[str, str] | None = None) -> dict[str, Color]:
    """Resolve once per modern frame; classic/export palettes are unchanged."""
    palette = THEMES.get(theme, THEMES["default"])
    values = {role: palette[key] for role, key in ROLE_PALETTE.items()}
    if theme != "mono":
        custom = overrides or {}
        if "accent" in custom:
            for role in ("language", "contribution", "notice", "warning"):
                values[role] = custom["accent"]
        values.update(custom)
    colors = {}
    for role, value in values.items():
        if isinstance(value, str):
            colors[role] = Color(rgb=(int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)))
        else:
            index = value - 90 + 8 if 90 <= value <= 97 else value - 30 if 30 <= value <= 37 else None
            colors[role] = Color(terminal_index=index)
    return colors


@dataclass(frozen=True)
class VisualPreset:
    avatar_columns: int
    avatar_rows: int
    compact: bool = False
    expressive: bool = False


VISUAL_PRESETS = {
    "balanced": VisualPreset(34, 16),
    "compact": VisualPreset(24, 8, compact=True),
    "showcase": VisualPreset(40, 16, expressive=True),
}
