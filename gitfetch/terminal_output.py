"""Narrow interactive profile frame/writer boundary; serializers stay strings."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from typing import Any, TextIO

from gitfetch.images import AvatarLoader
from gitfetch.kitty_graphics import ST, KittyTransmission, encode_avatar
from gitfetch.layout import AvatarGeometry, LayoutPlan, Preferences, Viewport, avatar_may_fit, plan_profile
from gitfetch.presentation import ProfileDocument
from gitfetch.render import (
    _paint_modern_rows,
    _render_avatar_image,
    apply_margin,
    color_enabled,
    combine_split,
    effective_avatar_color,
)
from gitfetch.terminal_capabilities import BackendDecision, _is_tty
from gitfetch.terminal_text import cell_width, sanitize_styled_text


@dataclass(frozen=True)
class TerminalFrame:
    text: str
    plan: LayoutPlan
    decision: BackendDecision
    graphics: KittyTransmission | None = None


class FrameUnavailable(Exception):
    """Safe to fall back: no bytes have been emitted."""


class TerminalWriteError(Exception):
    def __init__(self, *, interrupted: bool = False):
        self.interrupted = interrupted
        # Only a fixed diagnostic; never protocol bytes or an untrusted URL.
        super().__init__("terminal output interrupted" if interrupted else "terminal output failed")


def terminal_viewport(stream: TextIO) -> Viewport:
    size = os.get_terminal_size(stream.fileno())
    if size.columns < 1 or size.lines < 2:
        raise ValueError("terminal dimensions unavailable")
    return Viewport(size.columns, size.lines)


def build_terminal_frame(config: dict[str, Any], document: ProfileDocument, decision: BackendDecision,
                         viewport: Viewport, *, reference_date: date,
                         image_number: int | None = None) -> TerminalFrame:
    """Already-selected profile, one lazy asset and one pure plan. No output."""
    display = config["display"]
    monochrome = (display.get("theme") == "mono" or config.get("_color_force") == "off"
                  or (not display.get("color", True) and config.get("_color_force") != "on"))
    if decision.backend == "kitty" and (monochrome or display.get("avatar_color") in {"none", "256"}):
        decision = replace(decision, backend="text", text_style="halfblock", fallback=True,
                           reason="render-time color preference requires text")
    style = "halfblock" if decision.backend == "kitty" else decision.text_style
    preferences = Preferences(details=display.get("details", False), layout=display.get("layout", "split"),
                              margin=display.get("margin", 0), avatar=display.get("avatar", True),
                              avatar_width=display.get("avatar_width", 100), avatar_style=style,
                              visual_preset=display.get("visual_preset", "balanced"))
    loader = config.get("_avatar_loader") or AvatarLoader()
    asset = None
    if decision.backend != "none" and avatar_may_fit(viewport, preferences) and document.avatar_reference:
        asset = loader.load(document.avatar_reference).asset
        if asset is not None:
            asset = asset.for_presentation(display.get("avatar_fit", "auto"))
    plan = plan_profile(document, viewport, preferences, AvatarGeometry(*asset.effective_size) if asset else None,
                        reference_date=reference_date)
    paint_config = {**config, "_terminal_color": decision.color} if decision.color == "256" else config
    text_lines = _paint_modern_rows(paint_config, plan.rows, "ansi")
    graphics = None
    avatar = []
    if asset and plan.avatar_width and plan.composition != "text":
        if decision.backend == "kitty":
            try:
                graphics = encode_avatar(asset, number=image_number if image_number is not None else secrets.randbelow(0xffffffff) + 1,
                                         columns=plan.avatar_width, rows=plan.avatar_rows)
            except (OSError, ValueError, RuntimeError):
                decision = replace(decision, backend="text", text_style="halfblock", fallback=True,
                                   reason="PNG encoding failed before terminal output")
        if graphics:
            avatar = [" " * plan.avatar_width] * plan.avatar_rows
        else:
            text_color = "none" if monochrome or not color_enabled(config, "ansi") else decision.color
            if text_color == "auto" or display.get("avatar_color") in {"none", "256"}:
                text_color = effective_avatar_color(config, "ansi")
            avatar = _render_avatar_image(asset.image, plan.avatar_width, style, text_color,
                                          display.get("ascii_ramp", "BS#&@$%*!:."))
    else:
        decision = replace(decision, backend="none", fallback=decision.backend == "kitty",
                           reason="avatar unavailable or layout is text-only")
    if avatar and plan.composition == "split":
        text = combine_split(avatar, text_lines)
    elif avatar and plan.composition == "stack":
        text = "\n".join(avatar + ([""] if text_lines else []) + text_lines)
    else:
        text = "\n".join(text_lines)
    return TerminalFrame(apply_margin(text, plan.margin), plan, decision, graphics)


def _write(stream: TextIO, text: str) -> None:
    offset = 0
    while offset < len(text):
        count = stream.write(text[offset:])
        if count is None or count <= 0:
            raise OSError("terminal write made no progress")
        offset += count


def write_terminal_frame(frame: TerminalFrame, stream: TextIO) -> None:
    """Validate before output. Reserve real rows, rewind only those rows,
    place with C=1, then return below them and finish normal text/scrolling.
    """
    if not _is_tty(stream):
        raise FrameUnavailable("destination is not a TTY")
    try:
        if terminal_viewport(stream) != frame.plan.viewport or not stream.writable():
            raise FrameUnavailable("terminal resized or is unwritable")
    except (OSError, ValueError, AttributeError) as exc:
        raise FrameUnavailable("terminal unavailable") from exc
    lines = frame.text.split("\n")
    if any(sanitize_styled_text(line) != line or cell_width(line) > frame.plan.viewport.columns for line in lines):
        raise FrameUnavailable("unsafe or overflowing terminal text")
    graphics = frame.graphics
    height = frame.plan.avatar_rows if graphics else 0
    if graphics and (height < 1 or height >= frame.plan.viewport.rows or height > len(lines)
                     or graphics.columns != frame.plan.avatar_width or graphics.rows != height
                     or frame.plan.composition == "text"):
        raise FrameUnavailable("unsafe graphics rectangle")
    rewound = False
    started = False
    try:
        if graphics:
            # Printing real text first reserves enough visible rows even when
            # invoked at the bottom of the viewport. CRLF cancels pending wrap.
            _write(stream, "\r" + "\r\n".join(lines[:height]) + "\r\n")
            if terminal_viewport(stream) != frame.plan.viewport:
                raise OSError("terminal resized after row reservation")
            rewound = True
            _write(stream, f"\x1b[{height}A\r" + (f"\x1b[{frame.plan.margin}C" if frame.plan.margin else ""))
            started = True
            for index, chunk in enumerate(graphics.chunks):
                if index == len(graphics.chunks) - 1 and terminal_viewport(stream) != frame.plan.viewport:
                    raise OSError("terminal resized during transmission")
                _write(stream, chunk)
            _write(stream, f"\r\x1b[{height}B")
            rewound = False
        remaining = lines[height:]
        if remaining:
            _write(stream, "\r\n".join(remaining) + "\r\n")
        stream.flush()
    except (OSError, ValueError, KeyboardInterrupt) as exc:
        # No full redraw after partial transmission. Close any APC, abort/free
        # only our image number and restore the cursor to the reserved baseline.
        try:
            if not _is_tty(stream):
                raise OSError("terminal detached")
            recovery = ST + graphics.cleanup if graphics and started else ""
            if rewound:
                recovery += f"\r\x1b[{height}B"
            _write(stream, recovery + "\x1b[0m\r\n")
            stream.flush()
        except (OSError, ValueError, KeyboardInterrupt):
            pass
        raise TerminalWriteError(interrupted=isinstance(exc, KeyboardInterrupt)) from None


def emit_native_profile(config: dict[str, Any], document: ProfileDocument, decision: BackendDecision, stream: TextIO) -> bool:
    """False means safe pre-output fallback, never a request to redraw partial output."""
    try:
        viewport = terminal_viewport(stream)
        frame = build_terminal_frame(config, document, decision, viewport,
                                     reference_date=datetime.now(timezone.utc).date())
        write_terminal_frame(frame, stream)
        return True
    except (FrameUnavailable, OSError, ValueError):
        return False
