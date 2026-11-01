"""Safe single-line display text and deterministic terminal-cell utilities.

Provider/module/plugin strings are untrusted: use ``sanitize_text`` before
adding renderer styling. ``trusted_ansi=True`` and ``sanitize_styled_text``
are exclusively for renderer-generated SGR, never a permission inferred from
the contents of a string. None of these functions mutate provider data.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterator

from wcwidth import iter_graphemes, propagate_sgr, wcswidth

SGR_RE = re.compile(r"\x1b\[[0-9;]*m")
_BIDI_CONTROLS = frozenset("\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")
_STRING_STARTS = frozenset("]PX^_\x90\x98\x9d\x9e\x9f")


def _control_end(text: str, start: int, kind: str) -> int:
    """Consume a control sequence, including an unterminated string payload."""
    index = start
    if kind in _STRING_STARTS:
        while index < len(text):
            char = text[index]
            if char in "\x18\x1a\x9c" or (kind in "]\x9d" and char == "\x07"):
                return index + 1
            if text.startswith("\x1b\\", index):
                return index + 2
            index += 1
        return index
    if kind in {"[", "\x9b"}:
        while index < len(text):
            char = text[index]
            if "@" <= char <= "~":
                return index + 1
            if char in "\x18\x1a":
                return index + 1
            if char == "\x1b":
                return index
            index += 1
        return index
    # Other ECMA-48 ESC sequences, including charset selection and ESC c.
    while index < len(text) and " " <= text[index] <= "/":
        index += 1
    if index < len(text) and "0" <= text[index] <= "~":
        index += 1
    return index


def _normalize(value: object, allow_sgr: bool) -> str:
    text = "" if value is None else str(value)
    output: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\x1b":
            match = SGR_RE.match(text, index) if allow_sgr else None
            if match:
                output.append(match.group())
                index = match.end()
                continue
            index += 1
            if index < len(text):
                kind = text[index]
                if kind == "[" or kind in _STRING_STARTS:
                    index = _control_end(text, index + 1, kind)
                else:
                    index = _control_end(text, index, "")
            continue
        if char in "\x90\x98\x9b\x9d\x9e\x9f":
            index = _control_end(text, index + 1, char)
            continue
        if char == "\r" and text.startswith("\r\n", index):
            index += 1  # Treat CRLF as one whitespace separator.
        if char.isspace():
            output.append(" ")
        elif char not in _BIDI_CONTROLS:
            category = unicodedata.category(char)
            if category == "Cs" or char in "\ufffe\uffff":
                output.append("\ufffd")
            elif category != "Cc":
                output.append(char)
        index += 1
    return "".join(output)


def sanitize_text(value: object) -> str:
    """Remove terminal sequences; turn each whitespace separator into a space.

    Existing spaces are preserved. CRLF becomes one space. Other C0/C1
    controls and bidi embedding/override/isolate controls are removed.
    Surrogates and XML-invalid U+FFFE/U+FFFF become U+FFFD. No Unicode normalization:
    combining marks, ZWJ/ZWNJ, variation selectors and natural RTL text survive.
    Unterminated OSC/DCS/APC/PM/SOS strings consume their remaining payload.
    """
    return _normalize(value, allow_sgr=False)


def sanitize_styled_text(value: object) -> str:
    """Normalize a renderer-owned line, retaining only numeric SGR escapes."""
    return _normalize(value, allow_sgr=True)


def cell_width(value: object) -> int:
    """Measure normalized display text in cells; styling has zero width.

    Uses wcwidth's fixed default (narrow ambiguous characters), independent of
    locale, terminal environment variables, or terminal probing.
    """
    return max(0, wcswidth(sanitize_text(value)))


def _clusters(text: str) -> Iterator[tuple[str, str, int]]:
    """Keep SGR inside grapheme clusters intact, including combining accents."""
    fragments: list[str] = []
    styles: dict[int, str] = {}
    previous = offset = 0
    for match in SGR_RE.finditer(text):
        fragment = text[previous:match.start()]
        fragments.append(fragment)
        offset += len(fragment)
        styles[offset] = styles.get(offset, "") + match.group()
        previous = match.end()
    fragments.append(text[previous:])
    plain = "".join(fragments)
    offset = 0
    for cluster in iter_graphemes(plain):
        styled = "".join(styles.get(index, "") + char for index, char in enumerate(cluster, offset))
        offset += len(cluster)
        if offset == len(plain):
            styled += styles.get(offset, "")
        yield cluster, styled, max(0, wcswidth(cluster))


def _close_styles(text: str) -> str:
    return propagate_sgr([text])[0] if "\x1b" in text else text


def _prefix(text: str, budget: int) -> str:
    result: list[str] = []
    used = 0
    for _plain, styled, width in _clusters(text):
        if used + width > budget:
            break
        result.append(styled)
        used += width
    return _close_styles("".join(result))


def clip_text(value: object, budget: int, *, ellipsis: str = "…", trusted_ansi: bool = False) -> str:
    """Clip at whole graphemes, reserving cells for a sanitized ellipsis.

    Nonpositive budgets return empty text. An ellipsis too wide for the budget
    is itself clipped. Trusted styles are closed before the unstyled ellipsis.
    """
    if budget <= 0:
        return ""
    text = _normalize(value, allow_sgr=trusted_ansi)
    if cell_width(text) <= budget:
        return _prefix(text, budget)
    marker = _prefix(sanitize_text(ellipsis), budget)
    return _prefix(text, budget - cell_width(marker)) + marker


def wrap_text(value: object, budget: int, *, trusted_ansi: bool = False) -> list[str]:
    """Hard-wrap at whole graphemes, preserving normalized spaces.

    Each line is independently style-balanced. Empty text returns no lines;
    a nonpositive budget raises ValueError. An indivisible grapheme wider than
    the entire budget becomes '?' so every emitted line respects its budget.
    No wrapping is applied to the existing UI automatically.
    """
    if budget <= 0:
        raise ValueError("cell budget must be positive")
    text = _normalize(value, allow_sgr=trusted_ansi)
    lines: list[str] = []
    current: list[str] = []
    used = 0
    for _plain, styled, width in _clusters(text):
        if width > budget:
            styled = "".join(SGR_RE.findall(styled)) + "?"
            width = 1
        if current and used + width > budget:
            lines.append("".join(current))
            current = []
            used = 0
        current.append(styled)
        used += width
    if current:
        lines.append("".join(current))
    return propagate_sgr(lines) if trusted_ansi else lines
