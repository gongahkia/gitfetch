from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

from PIL import Image


_ICON_NAMES = {
    "c": "c",
    "c++": "cpp",
    "c#": "csharp",
    "css": "css",
    "dart": "dart",
    "go": "go",
    "golang": "go",
    "html": "html",
    "html5": "html",
    "java": "java",
    "javascript": "javascript",
    "js": "javascript",
    "kotlin": "kotlin",
    "lua": "lua",
    "php": "php",
    "python": "python",
    "r": "r",
    "ruby": "ruby",
    "rust": "rust",
    "shell": "shell",
    "bash": "shell",
    "swift": "swift",
    "typescript": "typescript",
    "ts": "typescript",
}
_ICON_DIRECTORY = Path(__file__).with_name("assets") / "language-icons"


def _icon_path(language: object) -> Path | None:
    name = _ICON_NAMES.get(str(language).strip().lower())
    if not name:
        return None
    path = _ICON_DIRECTORY / f"{name}.png"
    return path if path.is_file() else None


@lru_cache(maxsize=32)
def language_icon_data_uri(language: str) -> str | None:
    path = _icon_path(language)
    if path is None:
        return None
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def language_icon_image(language: object, size: int) -> Image.Image | None:
    path = _icon_path(language)
    if path is None:
        return None
    try:
        with Image.open(path) as image:
            return image.convert("RGBA").resize((size, size))
    except OSError:
        return None
