from __future__ import annotations

import argparse
import sys
from pathlib import Path

from gitfetch import __version__
from gitfetch.cache import CacheStore
from gitfetch.config import (
    MODULE_METADATA,
    config_path,
    cache_dir,
    get_token,
    load_config,
    preset_config,
    set_override,
    write_config,
    ConfigError,
)
from gitfetch.github_api import GitHubAPIError, GitHubClient
from gitfetch.modules import MODULE_HANDLERS, build_module_list
from gitfetch.render import render_output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Configurable GitHub profile fetch for the terminal")
    parser.add_argument("--version", action="version", version=f"gitfetch {__version__}")
    parser.add_argument("--user", help="GitHub username override")
    parser.add_argument("--token", help="GitHub token override")
    parser.add_argument("--mode", choices=["public", "viewer"], help="Profile data mode override")
    parser.add_argument("--config", dest="config_path", help="Path to config.toml")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="Override a config value")
    parser.add_argument("--format", choices=["ansi", "plain", "json", "svg", "card"], help="Output format override")
    parser.add_argument("--no-avatar", action="store_true", help="Disable avatar rendering for this run")
    parser.add_argument("--margin", type=int, help="Character-wide margin around the rendered output")
    color_group = parser.add_mutually_exclusive_group()
    color_group.add_argument("--color", dest="color", action="store_true", default=None, help="Force ANSI colors on (overrides NO_COLOR and TTY detection)")
    color_group.add_argument("--no-color", dest="color", action="store_false", help="Force ANSI colors off")
    parser.add_argument("--theme", choices=sorted(["default", "mono", "solarized", "dracula", "gruvbox", "nord"]), help="Color theme")
    parser.add_argument("--avatar-style", choices=["ascii", "halfblock", "braille"], help="Avatar rendering style")
    parser.add_argument("--avatar-color", choices=["none", "256", "truecolor"], help="Avatar color mode")
    parser.add_argument("--watch", type=int, metavar="SECS", help="Re-render every N seconds until interrupted")
    cache_group = parser.add_mutually_exclusive_group()
    cache_group.add_argument("--refresh", action="store_true", help="Bypass cache reads for this run")
    cache_group.add_argument("--offline", action="store_true", help="Read from cache only; fail if anything is missing")

    subparsers = parser.add_subparsers(dest="command")
    config_parser = subparsers.add_parser("config", help="Manage gitfetch configuration")
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)

    config_init = config_subparsers.add_parser("init", help="Write a config.toml preset")
    config_init.add_argument("--preset", choices=["minimal", "compact", "full", "showcase"], default="compact")
    config_init.add_argument("--force", action="store_true", help="Overwrite an existing config.toml")

    config_subparsers.add_parser("path", help="Print the config path")
    config_subparsers.add_parser("validate", help="Validate config.toml")

    modules_parser = subparsers.add_parser("modules", help="Inspect available modules")
    modules_subparsers = modules_parser.add_subparsers(dest="modules_command", required=True)
    modules_subparsers.add_parser("list", help="List supported modules")

    repo_parser = subparsers.add_parser("repo", help="Render a repository profile")
    repo_parser.add_argument("target", help="Repository in OWNER/NAME form")
    repo_parser.add_argument("--contributors-limit", type=int, default=10)
    repo_parser.add_argument("--commits-limit", type=int, default=5)

    org_parser = subparsers.add_parser("org", help="Render an organization profile")
    org_parser.add_argument("target", help="Organization login")
    org_parser.add_argument("--members-limit", type=int, default=10)
    org_parser.add_argument("--repos-limit", type=int, default=8)

    compare_parser = subparsers.add_parser("compare", help="Render multiple users side-by-side")
    compare_parser.add_argument("users", nargs="+", help="Two or more GitHub usernames")
    compare_parser.add_argument("--column-width", type=int, default=40, help="Width per column in characters")

    completions_parser = subparsers.add_parser("completions", help="Print shell completion script")
    completions_parser.add_argument("shell", choices=["bash", "zsh", "fish"], help="Target shell")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "config":
            return handle_config_command(args)
        if args.command == "modules":
            return handle_modules_command()
        if args.command == "repo":
            from gitfetch.modes import handle_repo_command
            return handle_repo_command(args)
        if args.command == "org":
            from gitfetch.modes import handle_org_command
            return handle_org_command(args)
        if args.command == "compare":
            from gitfetch.modes import handle_compare_command
            return handle_compare_command(args)
        if args.command == "completions":
            return handle_completions_command(args)
        return handle_render_command(args)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
    except GitHubAPIError as exc:
        print(f"api error: {exc}", file=sys.stderr)
        return 1


def handle_config_command(args: argparse.Namespace) -> int:
    path = Path(args.config_path) if getattr(args, "config_path", None) else config_path()
    if args.config_command == "path":
        print(path)
        return 0
    if args.config_command == "validate":
        load_config(path)
        print(f"valid: {path}")
        return 0
    if args.config_command == "init":
        if path.exists() and not args.force:
            raise ConfigError(f"{path} already exists (use --force to overwrite)")
        config = preset_config(args.preset)
        legacy_username = load_config(path).get("profile", {}).get("username", "")
        if legacy_username:
            config["profile"]["username"] = legacy_username
        write_config(path, config)
        print(f"wrote {path} using preset '{args.preset}'")
        return 0
    raise ConfigError("unknown config command")


def handle_modules_command() -> int:
    for name, meta in MODULE_METADATA.items():
        token_note = "token" if meta["token_required"] else "public"
        print(f"{name:16} {token_note:6} {meta['description']}")
    return 0


def handle_completions_command(args: argparse.Namespace) -> int:
    from gitfetch.completions import script_for
    print(script_for(args.shell))
    return 0


def handle_render_command(args: argparse.Namespace) -> int:
    path = Path(args.config_path) if args.config_path else config_path()
    config = load_config(path)
    for item in args.set:
        if "=" not in item:
            raise ConfigError(f"invalid override '{item}', expected KEY=VALUE")
        key, value = item.split("=", 1)
        set_override(config, key, value)
    if args.user:
        config["profile"]["username"] = args.user
    if args.mode:
        config["profile"]["mode"] = args.mode
    if args.format:
        config["display"]["format"] = args.format
    if args.no_avatar:
        config["display"]["avatar"] = False
    if args.margin is not None:
        if args.margin < 0:
            raise ConfigError("--margin must be non-negative")
        config["display"]["margin"] = args.margin
    if args.theme:
        config["display"]["theme"] = args.theme
    if args.color is True:
        config["_color_force"] = "on"
    elif args.color is False:
        config["_color_force"] = "off"
    if args.avatar_style:
        config["display"]["avatar_style"] = args.avatar_style
    if args.avatar_color:
        config["display"]["avatar_color"] = args.avatar_color

    username = config["profile"].get("username", "").strip()
    if not username:
        raise ConfigError(
            "no username configured; run 'gitfetch config init' or pass --user <username>"
        )

    token = get_token(args.token, config)
    cache = CacheStore(
        cache_dir(),
        enabled=bool(config["cache"]["enabled"]),
        ttl_seconds=int(config["cache"]["ttl_seconds"]),
        bypass_read=bool(args.refresh),
    )
    client = GitHubClient(token=token, cache=cache, offline=bool(args.offline))

    def render_once() -> None:
        context = client.get_context(
            username=username,
            mode=config["profile"]["mode"],
            repo_filters=config["repo_filters"],
        )
        module_results = []
        for name in build_module_list(config):
            result = MODULE_HANDLERS[name](config, context, client)
            hide_if_empty = config["modules"].get(name, {}).get("hide_if_empty", True)
            if hide_if_empty and not result.lines:
                result.hidden = True
            module_results.append(result)
        output_format = args.format or config["display"].get("format", "ansi")
        print(render_output(config, context.user, module_results, output_format))

    if args.watch:
        if args.watch < 1:
            raise ConfigError("--watch interval must be at least 1 second")
        run_watch_loop(render_once, args.watch)
        return 0
    render_once()
    return 0


def run_watch_loop(render_once, interval: int) -> None:
    import time
    try:
        while True:
            sys.stdout.write("\x1b[H\x1b[2J")
            sys.stdout.flush()
            try:
                render_once()
            except GitHubAPIError as exc:
                print(f"api error: {exc}", file=sys.stderr)
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
