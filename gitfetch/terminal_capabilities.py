"""Small passive terminal capability model and deterministic avatar policy.

No terminal queries or input reads. Environment hints are corroborated and
invalidated by multiplexers, remote ambiguity and restricted destinations.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal, TextIO


class Support(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TerminalCapabilities:
    stdout_tty: bool
    writable: bool
    input_tty: bool
    interactive: bool
    identity: str
    multiplexer: str
    kitty: Support
    color: Literal["truecolor", "256", "none"]
    unicode: bool
    no_color: bool
    evidence: tuple[str, ...]
    placement_safe: bool
    probe_safe: bool = False


@dataclass(frozen=True)
class AvatarPreferences:
    renderer: str = "auto"
    style: str = "ascii"
    legacy_style: bool = False
    color: str = "auto"


@dataclass(frozen=True)
class BackendDecision:
    backend: Literal["kitty", "text", "none"]
    text_style: str
    color: str
    reason: str
    explicit: bool = False
    fallback: bool = False


def classify_terminal(env: Mapping[str, str], *, stdout_tty: bool, writable: bool = True,
                      input_tty: bool = False, platform: str = "posix", unicode: bool = True,
                      effective_kitty: Support | None = None) -> TerminalCapabilities:
    """Pure classification. effective_kitty is reserved for verified callers.

    The CLI supplies no unverified multiplexer attestation here. It uses an
    explicit renderer override when the user knows their effective path.
    """
    term, program = env.get("TERM", "").lower(), env.get("TERM_PROGRAM", "").lower()
    mux = "tmux" if env.get("TMUX") or term.startswith("tmux") else (
        "screen" if env.get("STY") else "zellij" if env.get("ZELLIJ") else (
            "screen" if term.startswith("screen") else "direct"))
    identity = "kitty" if term == "xterm-kitty" else "ghostty" if term == "xterm-ghostty" else "other"
    restricted = bool(env.get("CI")) or term in {"dumb", "linux", "cons25"}
    no_color = "NO_COLOR" in env
    interactive = stdout_tty and writable and not restricted
    safe = interactive and mux in {"direct", "zellij"} and platform != "nt"
    evidence = []
    support = Support.UNKNOWN
    if not interactive:
        support = Support.UNSUPPORTED
        evidence.append("output is redirected, unwritable or restricted")
    elif platform == "nt" or env.get("WT_SESSION"):
        support, safe = Support.UNSUPPORTED, False
        evidence.append("Windows graphics path is not verified")
    elif mux in {"tmux", "screen"}:
        support, safe = Support.UNKNOWN, False
        evidence.append("multiplexer passthrough and placement are not verified")
    elif effective_kitty is not None:
        support = effective_kitty
        evidence.append("effective protocol support supplied by a verified caller")
    elif mux == "zellij":
        if program in {"apple_terminal", "vscode", "alacritty"}:
            support = Support.UNSUPPORTED
            evidence.append("Zellij host has no verified Kitty implementation")
        else:
            evidence.append("Zellij host support, version and session option are unknown")
    elif env.get("SSH_CONNECTION") or env.get("SSH_TTY"):
        evidence.append("remote effective terminal path is unverified")
    elif term == "xterm-kitty" and program in {"", "kitty"} and (env.get("KITTY_WINDOW_ID", "").isdigit() or program == "kitty"):
        support = Support.SUPPORTED
        evidence.append("direct Kitty TERM corroborated by terminal identity")
    elif term == "xterm-ghostty" and program == "ghostty":
        support = Support.SUPPORTED
        evidence.append("direct Ghostty TERM and TERM_PROGRAM agree")
    elif program in {"apple_terminal", "vscode", "alacritty"}:
        support = Support.UNSUPPORTED
        # No promise about future/optional backends from a program name alone.
        evidence.append("terminal graphics implementation is not verified by this policy")
    else:
        evidence.append("insufficient corroborated terminal identity")
    color: Literal["truecolor", "256", "none"] = "none"
    if not no_color and term != "dumb":
        if env.get("COLORTERM", "").lower() in {"truecolor", "24bit"} or support == Support.SUPPORTED:
            color = "truecolor"
        elif "256color" in term:
            color = "256"
    return TerminalCapabilities(stdout_tty, writable, input_tty, interactive, identity, mux, support,
                                color, unicode, no_color, tuple(evidence), safe)


def _is_tty(stream: TextIO) -> bool:
    try:
        return bool(stream.isatty()) and os.isatty(stream.fileno())
    except (OSError, ValueError, AttributeError):
        return False


def discover_terminal(stdout: TextIO, stdin: TextIO, *, env: Mapping[str, str] | None = None) -> TerminalCapabilities:
    try:
        writable = stdout.writable()
    except (OSError, ValueError, AttributeError):
        writable = False
    encoding = (getattr(stdout, "encoding", None) or "ascii").lower().replace("-", "")
    return classify_terminal(os.environ if env is None else env, stdout_tty=_is_tty(stdout), writable=writable,
                             input_tty=_is_tty(stdin), platform=os.name, unicode=encoding.startswith("utf"))


def resolve_preferences(config: dict[str, Any], *, saved: set[str], overrides: list[str],
                        renderer: str | None, style: str | None) -> AvatarPreferences:
    """CLI flags > dotted overrides > saved settings > defaults; renderer wins
    over a style within the same tier. Configuration dictionaries stay ordinary.
    """
    display = config["display"]
    dotted = {entry.split("=", 1)[0] for entry in overrides}
    legacy = False
    if renderer is not None:
        choice = renderer
    elif style is not None:
        choice, legacy = "text", True
    elif "display.avatar_renderer" in dotted:
        choice = display.get("avatar_renderer", "auto")
    elif {"display.avatar_style", "display.ascii_ramp"} & dotted:
        choice, legacy = "text", True
    elif "avatar_renderer" in saved:
        choice = display.get("avatar_renderer", "auto")
    elif {"avatar_style", "ascii_ramp"} & saved:
        choice, legacy = "text", True
    else:
        choice = display.get("avatar_renderer", "auto")
    return AvatarPreferences(choice, display.get("avatar_style", "ascii"), legacy, display.get("avatar_color", "auto"))


def select_avatar_backend(caps: TerminalCapabilities, preferences: AvatarPreferences, *, output_format: str,
                          modern: bool, avatar: bool = True, has_asset: bool = True,
                          captured: bool = False, watch: bool = False, color_allowed: bool = True) -> BackendDecision:
    explicit = preferences.renderer != "auto" or preferences.legacy_style
    automatic_style = (caps.interactive and output_format == "ansi" and modern
                       and preferences.renderer == "auto" and not preferences.legacy_style)
    style = ("halfblock" if caps.unicode else "ascii") if automatic_style else preferences.style
    color = caps.color if preferences.color == "auto" and automatic_style else preferences.color
    def text(reason: str) -> BackendDecision:
        return BackendDecision("text", style, color, reason, explicit, preferences.renderer != "text")
    if not avatar or not has_asset:
        return BackendDecision("none", style, color, "avatar disabled or asset unavailable", explicit)
    if preferences.renderer == "text" or preferences.legacy_style:
        return text("explicit text renderer or legacy avatar style")
    if output_format != "ansi" or captured or not modern:
        return text("native graphics require uncaptured modern ANSI output")
    if not caps.interactive or not caps.stdout_tty or not caps.writable:
        return text("output is not an interactive writable TTY")
    if watch:
        return text("watch uses text avatars for a bounded graphics lifecycle")
    if not color_allowed or caps.no_color or caps.color == "none" or preferences.color in {"none", "256"}:
        return text("monochrome preference disables native color images")
    if not caps.placement_safe or caps.kitty == Support.UNSUPPORTED:
        return text("effective graphics placement is unavailable")
    if caps.kitty == Support.SUPPORTED or preferences.renderer == "kitty":
        reason = "corroborated effective Kitty support" if caps.kitty == Support.SUPPORTED else "user-confirmed effective Kitty path"
        return BackendDecision("kitty", style, caps.color if color == "auto" else color, reason, preferences.renderer == "kitty")
    return text("Kitty support is unknown; using Unicode/text fallback")
