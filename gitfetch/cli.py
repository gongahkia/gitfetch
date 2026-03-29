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
    parser.add_argument("--format", choices=["ansi", "plain", "json"], help="Output format override")
    parser.add_argument("--no-avatar", action="store_true", help="Disable avatar rendering for this run")

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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "config":
            return handle_config_command(args)
        if args.command == "modules":
            return handle_modules_command()
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
    )
    client = GitHubClient(token=token, cache=cache)
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
    return 0
