from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

from gitfetch import __version__
from gitfetch.cache import CacheStore
from gitfetch.config import (
    apply_named_profile,
    config_path,
    cache_dir,
    get_token,
    load_config,
    normalize_config,
    preset_config,
    set_override,
    write_config,
    ConfigError,
    PROVIDER_TOKEN_ENVS,
    SUPPORTED_PROVIDERS,
)
from gitfetch.github_api import GitHubAPIError, GitHubClient
from gitfetch.modules import MODULE_HANDLERS, available_module_metadata, build_module_list, load_plugin_modules
from gitfetch.modules.builtin import ModuleResult
from gitfetch.providers import create_provider_client
from gitfetch.render import render_output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Configurable git provider profile fetch for the terminal")
    parser.add_argument("--version", action="version", version=f"gitfetch {__version__}")
    parser.add_argument("--user", help="Provider username or workspace override")
    parser.add_argument("--provider", choices=SUPPORTED_PROVIDERS, help="Git provider override")
    parser.add_argument("--base-url", help="Provider API base URL override")
    parser.add_argument("--profile", help="Saved profile name from config.toml")
    parser.add_argument("--token", help="Provider token override")
    parser.add_argument("--mode", choices=["public", "viewer"], help="Profile data mode override")
    parser.add_argument("--config", dest="config_path", help="Path to config.toml")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="Override a config value")
    parser.add_argument("--format", choices=["ansi", "plain", "json", "svg", "card", "png"], help="Output format override")
    parser.add_argument("--save", help="Write output to a file instead of stdout (required for --format png)")
    parser.add_argument("--no-avatar", action="store_true", help="Disable avatar rendering for this run")
    parser.add_argument("--margin", type=int, help="Character-wide margin around the rendered output")
    color_group = parser.add_mutually_exclusive_group()
    color_group.add_argument("--color", dest="color", action="store_true", default=None, help="Force ANSI colors on (overrides NO_COLOR and TTY detection)")
    color_group.add_argument("--no-color", dest="color", action="store_false", help="Force ANSI colors off")
    from gitfetch.render import THEMES
    parser.add_argument("--theme", choices=sorted(THEMES.keys()), help="Color theme")
    parser.add_argument("--avatar-style", choices=["ascii", "halfblock", "braille"], help="Avatar rendering style")
    parser.add_argument("--avatar-color", choices=["auto", "none", "256", "truecolor"], help="Avatar color mode (auto follows --color/--no-color)")
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

    config_wizard = config_subparsers.add_parser("wizard", help="Interactively write a config.toml")
    config_wizard.add_argument("--force", action="store_true", help="Overwrite an existing config.toml")

    config_subparsers.add_parser("path", help="Print the config path")
    config_subparsers.add_parser("validate", help="Validate config.toml")

    profiles_parser = config_subparsers.add_parser("profiles", help="Manage saved profiles")
    profiles_subparsers = profiles_parser.add_subparsers(dest="profiles_command", required=True)
    profiles_subparsers.add_parser("list", help="List saved profiles")
    profile_set = profiles_subparsers.add_parser("set", help="Create or update a saved profile")
    profile_set.add_argument("name")
    profile_set.add_argument("--user", required=True, help="Provider username or workspace for the profile")
    profile_set.add_argument("--provider", choices=SUPPORTED_PROVIDERS, default="github")
    profile_set.add_argument("--mode", choices=["public", "viewer"], default="public")
    profile_set.add_argument("--token-env", default="")
    profile_set.add_argument("--token-command", default="")
    profile_remove = profiles_subparsers.add_parser("remove", help="Remove a saved profile")
    profile_remove.add_argument("name")

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
    compare_parser.add_argument("users", nargs="+", help="Two or more provider usernames")
    compare_parser.add_argument("--column-width", type=int, default=None, help="Width per column in characters (default: auto-fit terminal)")

    completions_parser = subparsers.add_parser("completions", help="Print shell completion script")
    completions_parser.add_argument("shell", choices=["bash", "zsh", "fish"], help="Target shell")

    token_parser = subparsers.add_parser("token", help="Store or inspect a token in macOS Keychain")
    token_subparsers = token_parser.add_subparsers(dest="token_command", required=True)
    token_store = token_subparsers.add_parser("store", help="Store a token in macOS Keychain")
    token_store.add_argument("--service", default="gitfetch")
    token_store.add_argument("--account", default="gitfetch")
    token_store.add_argument("--token", help="Token value; prompts securely when omitted")
    token_get = token_subparsers.add_parser("get", help="Print a token from macOS Keychain")
    token_get.add_argument("--service", default="gitfetch")
    token_get.add_argument("--account", default="gitfetch")
    token_status = token_subparsers.add_parser("status", help="Report whether a token is stored")
    token_status.add_argument("--service", default="gitfetch")
    token_status.add_argument("--account", default="gitfetch")
    token_delete = token_subparsers.add_parser("delete", help="Delete a token from macOS Keychain")
    token_delete.add_argument("--service", default="gitfetch")
    token_delete.add_argument("--account", default="gitfetch")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "config":
            return handle_config_command(args)
        if args.command == "modules":
            return handle_modules_command(args)
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
        if args.command == "token":
            return handle_token_command(args)
        return handle_render_command(args)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
    except GitHubAPIError as exc:
        print(f"api error: {exc}", file=sys.stderr)
        return 1
    except requests.RequestException as exc:
        print(f"network error: {exc}", file=sys.stderr)
        return 1


def handle_config_command(args: argparse.Namespace) -> int:
    path = Path(args.config_path) if getattr(args, "config_path", None) else config_path()
    if args.config_command == "path":
        print(path)
        return 0
    if args.config_command == "validate":
        config = load_config(path)
        load_plugin_modules(config)
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
    if args.config_command == "wizard":
        if path.exists() and not args.force:
            raise ConfigError(f"{path} already exists (use --force to overwrite)")
        config = run_config_wizard()
        write_config(path, config)
        print(f"wrote {path}")
        return 0
    if args.config_command == "profiles":
        return handle_profiles_command(args, path)
    raise ConfigError("unknown config command")


def run_config_wizard() -> dict:
    provider = input(f"Provider [{'/'.join(SUPPORTED_PROVIDERS)}] (github): ").strip().lower() or "github"
    if provider not in SUPPORTED_PROVIDERS:
        raise ConfigError(f"unknown provider: {provider}")
    username = input("Username/workspace: ").strip()
    preset = input("Preset [compact/minimal/full/showcase] (compact): ").strip() or "compact"
    if preset not in {"minimal", "compact", "full", "showcase"}:
        raise ConfigError(f"unknown preset: {preset}")
    avatar_raw = input("Show avatar? [Y/n]: ").strip().lower()
    output_format = input("Default format [ansi/plain/json/svg/card] (ansi): ").strip() or "ansi"
    if output_format not in {"ansi", "plain", "json", "svg", "card"}:
        raise ConfigError(f"unsupported format: {output_format}")
    default_token_env = PROVIDER_TOKEN_ENVS.get(provider, "GITHUB_TOKEN")
    token_env = input(f"Token env var ({default_token_env}): ").strip() or default_token_env
    config = preset_config(preset)
    config["profile"]["provider"] = provider
    config["profile"]["username"] = username
    config["profile"]["token_env"] = token_env
    config["display"]["avatar"] = avatar_raw not in {"n", "no", "false", "0"}
    config["display"]["format"] = output_format
    return config


def handle_profiles_command(args: argparse.Namespace, path: Path) -> int:
    config = load_config(path)
    profiles = config.setdefault("profiles", {})
    if args.profiles_command == "list":
        if not profiles:
            print("no saved profiles")
            return 0
        for name in sorted(profiles):
            profile = profiles[name]
            username = profile.get("username", "")
            provider = profile.get("provider", "github")
            mode = profile.get("mode", "public")
            token_env = profile.get("token_env", "GITHUB_TOKEN")
            token_command = " token-command" if profile.get("token_command") else ""
            print(f"{name:16} {provider:10} {username:20} {mode:6} {token_env}{token_command}")
        return 0
    if args.profiles_command == "set":
        profiles[args.name] = {
            "provider": args.provider,
            "username": args.user,
            "mode": args.mode,
            "token_env": args.token_env or PROVIDER_TOKEN_ENVS.get(args.provider, "GITHUB_TOKEN"),
            "token_command": args.token_command,
        }
        write_config(path, config)
        print(f"saved profile '{args.name}'")
        return 0
    if args.profiles_command == "remove":
        if args.name not in profiles:
            raise ConfigError(f"unknown profile '{args.name}'")
        del profiles[args.name]
        write_config(path, config)
        print(f"removed profile '{args.name}'")
        return 0
    raise ConfigError("unknown profiles command")


def handle_modules_command(args: argparse.Namespace) -> int:
    path = Path(args.config_path) if getattr(args, "config_path", None) else config_path()
    config = load_config(path)
    load_plugin_modules(config)
    for name, meta in available_module_metadata().items():
        token_note = "token" if meta["token_required"] else "public"
        print(f"{name:16} {token_note:6} {meta['description']}")
    return 0


def handle_completions_command(args: argparse.Namespace) -> int:
    from gitfetch.completions import script_for
    print(script_for(args.shell))
    return 0


def handle_token_command(args: argparse.Namespace) -> int:
    import getpass
    import platform
    import shutil
    import subprocess

    if platform.system() != "Darwin" or not shutil.which("security"):
        raise ConfigError("token keychain commands require macOS and the security CLI")

    base = ["security"]
    account = args.account
    service = args.service
    if args.token_command == "store":
        token = args.token or getpass.getpass("Provider token: ").strip()
        if not token:
            raise ConfigError("empty token")
        result = subprocess.run(
            base + ["add-generic-password", "-U", "-a", account, "-s", service, "-w", token],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise ConfigError(result.stderr.strip() or "failed to store token")
        print(f"stored token for service '{service}' account '{account}'")
        return 0
    if args.token_command == "get":
        result = subprocess.run(
            base + ["find-generic-password", "-a", account, "-s", service, "-w"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise ConfigError("no token stored")
        print(result.stdout.strip())
        return 0
    if args.token_command == "status":
        result = subprocess.run(
            base + ["find-generic-password", "-a", account, "-s", service],
            capture_output=True,
            text=True,
            check=False,
        )
        print("stored" if result.returncode == 0 else "not stored")
        return 0
    if args.token_command == "delete":
        result = subprocess.run(
            base + ["delete-generic-password", "-a", account, "-s", service],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise ConfigError("no token stored")
        print(f"deleted token for service '{service}' account '{account}'")
        return 0
    raise ConfigError("unknown token command")


def _write_or_print(text: str, args: argparse.Namespace) -> None:
    if getattr(args, "save", None):
        path = Path(args.save)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path}")
    else:
        print(text)


def _png_output_path(args: argparse.Namespace) -> Path:
    if not getattr(args, "save", None):
        raise ConfigError("--save is required for --format png")
    path = Path(args.save)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _token_required_result(name: str, client=None) -> ModuleResult:
    title = name.replace("_", " ").title()
    env_name = PROVIDER_TOKEN_ENVS.get(getattr(client, "provider_name", "github"), "GITHUB_TOKEN")
    return ModuleResult(
        name,
        title,
        [f"requires --token, {env_name}, or profile.token_command"],
        {"requires_token": True},
        requires_token=True,
    )


def _unsupported_provider_result(name: str, client) -> ModuleResult:
    title = name.replace("_", " ").title()
    reason = client.unsupported_reason(name)
    return ModuleResult(
        name,
        title,
        [f"unsupported on {client.provider_title}: {reason}"],
        {"unsupported": True, "provider": client.provider_name, "reason": reason},
    )


def handle_render_command(args: argparse.Namespace) -> int:
    if args.watch and args.save:
        raise ConfigError("--watch cannot be combined with --save")
    path = Path(args.config_path) if args.config_path else config_path()
    config = load_config(path)
    apply_named_profile(config, args.profile)
    for item in args.set:
        if "=" not in item:
            raise ConfigError(f"invalid override '{item}', expected KEY=VALUE")
        key, value = item.split("=", 1)
        set_override(config, key, value)
    if args.user:
        config["profile"]["username"] = args.user
    if args.provider:
        config["profile"]["provider"] = args.provider
    if args.base_url:
        provider = config["profile"].get("provider", "github")
        config.setdefault("providers", {}).setdefault(provider, {})["base_url"] = args.base_url
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
    normalize_config(config)
    load_plugin_modules(config)

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
    client = create_provider_client(config, token=token, cache=cache, offline=bool(args.offline))

    def render_once() -> None:
        context = client.get_context(
            username=username,
            mode=config["profile"]["mode"],
            repo_filters=config["repo_filters"],
        )
        module_results = []
        metadata = available_module_metadata()
        for name in build_module_list(config):
            if not client.supports_module(name):
                module_results.append(_unsupported_provider_result(name, client))
                continue
            token_required = client.module_token_required(name, metadata.get(name, {}).get("token_required", False))
            if token_required and not token:
                module_results.append(_token_required_result(name, client))
                continue
            result = MODULE_HANDLERS[name](config, context, client)
            hide_if_empty = config["modules"].get(name, {}).get("hide_if_empty", True)
            if hide_if_empty and not result.lines:
                result.hidden = True
            module_results.append(result)
        output_format = args.format or config["display"].get("format", "ansi")
        if output_format == "png":
            from gitfetch.formats import render_card_png

            render_card_png(config, context.user, [m for m in module_results if not m.hidden], _png_output_path(args))
            print(f"wrote {args.save}")
            return
        _write_or_print(render_output(config, context.user, module_results, output_format), args)

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
