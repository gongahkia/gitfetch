"""Bounded, portable graphical typography using a licensed packaged font."""
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

from gitfetch.terminal_text import sanitize_text

FONT_PATH = Path(__file__).parent / 'assets' / 'fonts' / 'DejaVuSans.ttf'


@lru_cache(maxsize=32)
def font(size: int):
    # A packaged face is independent of Arial/Helvetica/system installations.
    try:
        return ImageFont.truetype(str(FONT_PATH), max(8, min(40, size)))
    except (OSError, ImportError):
        return ImageFont.load_default()


def drawable(text: str, face) -> str:
    text = sanitize_text(text[:4096])
    try:
        face.getbbox(text)
        return text
    except UnicodeEncodeError:
        # Only the emergency Pillow 10 bitmap fallback needs this. The semantic
        # plan and provider payload retain the original Unicode text.
        return text.encode('latin-1', 'replace').decode('latin-1')


def length(text: str, size: int) -> float:
    face = font(size)
    value = drawable(text, face)
    left, _, right, _ = face.getbbox(value)
    return max(float(face.getlength(value)), float(right - min(0, left)))


def clip(text: str, width: float, size: int) -> str:
    text = sanitize_text(text[:4096])
    if length(text, size) <= width:
        return text
    # Grapheme clusters preserve combining marks and emoji sequences.
    from wcwidth import iter_graphemes
    units = list(iter_graphemes(text))
    low, high = 0, len(units)
    while low < high:
        middle = (low + high + 1) // 2
        if length(''.join(units[:middle]) + '…', size) <= width:
            low = middle
        else:
            high = middle - 1
    return ''.join(units[:low]) + '…' if length('…', size) <= width else ''


def wrap(text: str, width: float, size: int, limit: int) -> tuple[list[str], bool]:
    text = sanitize_text(text[:4096])
    words = text.split()
    lines: list[str] = []
    pending = ''
    condensed = False
    for index, word in enumerate(words):
        candidate = pending + (' ' if pending else '') + word
        if length(candidate, size) <= width:
            pending = candidate
            continue
        if pending:
            lines.append(pending)
            pending = ''
        if len(lines) >= limit:
            return lines[:limit-1] + [clip(lines[limit-1] + ' …', width, size)], True
        if length(word, size) > width:
            # Bound long URLs/unbroken strings without quadratic character scans.
            lines.append(clip(word, width, size))
            condensed = True
        else:
            pending = word
        if len(lines) >= limit and (pending or index + 1 < len(words)):
            return lines[:limit-1] + [clip(lines[limit-1] + ' …', width, size)], True
    if pending:
        lines.append(pending)
    return lines[:limit], condensed
