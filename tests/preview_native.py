"""Explicit, local native-avatar acceptance; never downloads or queries a terminal."""
import argparse
import sys
import tempfile
from pathlib import Path

from avatar_fixtures import CASES, image_bytes
from modern_fixtures import REFERENCE, fixture

from gitfetch.config import preset_config
from gitfetch.images import AvatarLoader, AvatarPolicy
from gitfetch.terminal_capabilities import AvatarPreferences, discover_terminal, select_avatar_backend
from gitfetch.terminal_output import (
    FrameUnavailable,
    TerminalWriteError,
    build_terminal_frame,
    terminal_viewport,
    write_terminal_frame,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, default="transparent")
    parser.add_argument("--layout", choices=("split", "stack"), default="split")
    parser.add_argument("--confirm-kitty", action="store_true", help="Confirm the current effective path supports Kitty graphics")
    parser.add_argument("--offline", choices=("cached", "missing"), default="cached", help="Exercise only an isolated temporary asset cache")
    args = parser.parse_args(argv)
    caps = discover_terminal(sys.stdout, sys.stdin)
    if not caps.stdout_tty or not caps.writable:
        parser.error("native previews require a writable terminal; use preview_avatars.py for text captures")
    selected = select_avatar_backend(caps, AvatarPreferences("kitty" if args.confirm_kitty else "text"),
                                     output_format="ansi", modern=True, color_allowed=not caps.no_color)
    print(f"Preview backend: {selected.backend} ({selected.reason})", file=sys.stderr)
    _, _, document = fixture()
    config = preset_config("minimal")
    config["display"].update(avatar=True, presentation="modern", layout=args.layout)
    if selected.color != "auto":
        config["display"]["avatar_color"] = selected.color
    if caps.no_color:
        config["_color_force"] = "off"
    with tempfile.TemporaryDirectory() as directory:
        loader = AvatarLoader(AvatarPolicy(Path(directory), True, 60, offline=True, scope="local-preview"))
        if args.offline == "cached":
            loader.cache.put(loader.policy.scope, document.avatar_reference, image_bytes(args.case))
        config["_avatar_loader"] = loader
        try:
            frame = build_terminal_frame(config, document, selected, terminal_viewport(sys.stdout), reference_date=REFERENCE)
            write_terminal_frame(frame, sys.stdout)
        except (FrameUnavailable, OSError, ValueError):
            print("Preview terminal unavailable or resized; run again.", file=sys.stderr)
            return 1
        except TerminalWriteError as exc:
            print(str(exc), file=sys.stderr)
            return 130 if exc.interrupted else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
