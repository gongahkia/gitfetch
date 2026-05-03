from __future__ import annotations

import argparse
import shutil
from typing import Any

from gitfetch.cache import CacheStore
from gitfetch.config import (
    cache_dir,
    config_path,
    get_token,
    load_config,
    set_override,
    ConfigError,
)
from gitfetch.github_api import GitHubAPIError, GitHubClient
from gitfetch.modules.builtin import MODULE_HANDLERS, ModuleResult, build_module_list
from gitfetch.render import (
    SPLIT_GAP,
    apply_margin,
    color_enabled,
    module_lines,
    palette_for,
    render_avatar,
    visible_len,
)


def _apply_common_overrides(args: argparse.Namespace, config: dict[str, Any]) -> None:
    for item in getattr(args, "set", []) or []:
        if "=" not in item:
            raise ConfigError(f"invalid override '{item}', expected KEY=VALUE")
        key, value = item.split("=", 1)
        set_override(config, key, value)
    if getattr(args, "format", None):
        config["display"]["format"] = args.format
    if getattr(args, "no_avatar", False):
        config["display"]["avatar"] = False
    if getattr(args, "margin", None) is not None:
        if args.margin < 0:
            raise ConfigError("--margin must be non-negative")
        config["display"]["margin"] = args.margin
    if getattr(args, "theme", None):
        config["display"]["theme"] = args.theme
    if getattr(args, "color", None) is True:
        config["_color_force"] = "on"
    elif getattr(args, "color", None) is False:
        config["_color_force"] = "off"
    if getattr(args, "avatar_style", None):
        config["display"]["avatar_style"] = args.avatar_style
    if getattr(args, "avatar_color", None):
        config["display"]["avatar_color"] = args.avatar_color


def _load_config_with_path(args: argparse.Namespace) -> dict[str, Any]:
    from pathlib import Path
    path = Path(args.config_path) if getattr(args, "config_path", None) else config_path()
    config = load_config(path)
    _apply_common_overrides(args, config)
    return config


def _client_for(args: argparse.Namespace, config: dict[str, Any]) -> GitHubClient:
    token = get_token(getattr(args, "token", None), config)
    cache = CacheStore(
        cache_dir(),
        enabled=bool(config["cache"]["enabled"]),
        ttl_seconds=int(config["cache"]["ttl_seconds"]),
    )
    return GitHubClient(token=token, cache=cache)


def _render_with_lines(
    config: dict[str, Any],
    output_format: str,
    avatar_url: str | None,
    text_lines: list[str],
) -> str:
    margin = max(0, int(config["display"].get("margin", 0)))
    result: str | None = None
    if config["display"].get("avatar") and output_format in {"ansi", "plain"} and avatar_url:
        configured_width = int(config["display"]["avatar_width"])
        term_cols = shutil.get_terminal_size((configured_width, 24)).columns
        usable_cols = max(0, term_cols - 2 * margin)
        layout = config["display"].get("layout", "split")
        if layout == "split":
            text_width = max((visible_len(line) for line in text_lines), default=0)
            available = usable_cols - text_width - SPLIT_GAP
        else:
            available = usable_cols
        if available >= 20:
            avatar = render_avatar(
                avatar_url,
                width=min(configured_width, available),
                style=config["display"].get("avatar_style", "ascii"),
                color_mode=config["display"].get("avatar_color", "none") if color_enabled(config, output_format) else "none",
                ramp=config["display"]["ascii_ramp"],
            )
            if avatar:
                if layout == "split":
                    width = max((visible_len(line) for line in avatar), default=0)
                    rows: list[str] = []
                    total = max(len(avatar), len(text_lines))
                    for i in range(total):
                        if i < len(avatar):
                            line = avatar[i]
                            pad = " " * (width - visible_len(line))
                        else:
                            line = " " * width
                            pad = ""
                        text = text_lines[i] if i < len(text_lines) else ""
                        rows.append(f"{line}{pad}   {text}" if text else line + pad)
                    result = "\n".join(rows)
                else:
                    result = "\n".join(avatar + [""] + text_lines)
    if result is None:
        result = "\n".join(text_lines)
    return apply_margin(result, margin)


def handle_repo_command(args: argparse.Namespace) -> int:
    if "/" not in args.target:
        raise ConfigError("repo target must be OWNER/NAME")
    owner, name = args.target.split("/", 1)
    config = _load_config_with_path(args)
    client = _client_for(args, config)
    try:
        repo = client.get_repo(owner, name)
        languages = client.get_repo_languages(owner, name)
        contributors = client.get_repo_contributors(owner, name, limit=args.contributors_limit)
        commits = client.get_repo_commits(owner, name, limit=args.commits_limit)
    except GitHubAPIError as exc:
        print(f"api error: {exc}")
        return 1

    output_format = args.format or config["display"].get("format", "ansi")
    enabled_color = color_enabled(config, output_format)
    palette = palette_for(config)

    modules: list[ModuleResult] = []
    identity_lines = [f"{repo.get('full_name')}"]
    if repo.get("description"):
        identity_lines.append(repo["description"])
    if repo.get("homepage"):
        identity_lines.append(f"homepage: {repo['homepage']}")
    if (repo.get("license") or {}).get("spdx_id"):
        identity_lines.append(f"license: {repo['license']['spdx_id']}")
    identity_lines.append(f"default branch: {repo.get('default_branch', 'main')}")
    modules.append(ModuleResult("identity", "Repository", identity_lines, repo))

    stats_lines = [
        f"stars: {repo.get('stargazers_count', 0)}",
        f"forks: {repo.get('forks_count', 0)}",
        f"watchers: {repo.get('subscribers_count', repo.get('watchers_count', 0))}",
        f"open issues: {repo.get('open_issues_count', 0)}",
        f"size: {repo.get('size', 0)} KB",
    ]
    if repo.get("pushed_at"):
        stats_lines.append(f"last push: {repo['pushed_at']}")
    modules.append(ModuleResult("stats", "Stats", stats_lines, repo))

    total_bytes = sum(languages.values()) or 1
    lang_lines = [
        f"{language} {count * 100 // total_bytes}%"
        for language, count in sorted(languages.items(), key=lambda kv: kv[1], reverse=True)[:5]
    ]
    if lang_lines:
        modules.append(ModuleResult("languages", "Languages", lang_lines, languages))

    contrib_lines = [
        f"{c.get('login')} ({c.get('contributions', 0)} commits)"
        for c in contributors
    ]
    if contrib_lines:
        modules.append(ModuleResult("contributors", "Contributors", contrib_lines, contributors))

    commit_lines: list[str] = []
    for commit in commits:
        message = ((commit.get("commit") or {}).get("message") or "").splitlines()[0][:60]
        sha = (commit.get("sha") or "")[:7]
        author = (((commit.get("commit") or {}).get("author")) or {}).get("name", "?")
        commit_lines.append(f"{sha} {author}: {message}")
    if commit_lines:
        modules.append(ModuleResult("recent_commits", "Recent Commits", commit_lines, commits))

    text = module_lines(modules, enabled_color, palette)
    avatar_url = (repo.get("owner") or {}).get("avatar_url")
    print(_render_with_lines(config, output_format, avatar_url, text))
    return 0


def handle_org_command(args: argparse.Namespace) -> int:
    config = _load_config_with_path(args)
    client = _client_for(args, config)
    try:
        org = client.get_org(args.target)
        members = client.get_org_members(args.target, limit=args.members_limit)
        repos = client.get_org_repos(args.target)
    except GitHubAPIError as exc:
        print(f"api error: {exc}")
        return 1

    output_format = args.format or config["display"].get("format", "ansi")
    enabled_color = color_enabled(config, output_format)
    palette = palette_for(config)

    identity_lines = [f"@{org.get('login')}"]
    if org.get("name"):
        identity_lines.append(org["name"])
    if org.get("description"):
        identity_lines.append(org["description"])
    if org.get("blog"):
        identity_lines.append(f"blog: {org['blog']}")
    if org.get("location"):
        identity_lines.append(f"location: {org['location']}")
    if org.get("email"):
        identity_lines.append(f"email: {org['email']}")

    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    stats_lines = [
        f"public repos: {org.get('public_repos', len(repos))}",
        f"members shown: {len(members)}",
        f"total stars: {total_stars}",
        f"followers: {org.get('followers', 0)}",
    ]

    sorted_repos = sorted(repos, key=lambda r: r.get("stargazers_count", 0), reverse=True)[:args.repos_limit]
    repo_lines = [f"{r.get('name')} ({r.get('language') or 'n/a'}, ★{r.get('stargazers_count', 0)})" for r in sorted_repos]
    member_lines = [m.get("login", "?") for m in members]

    modules = [
        ModuleResult("identity", "Organization", identity_lines, org),
        ModuleResult("stats", "Stats", stats_lines, org),
    ]
    if repo_lines:
        modules.append(ModuleResult("top_repos", "Top Repos", repo_lines, sorted_repos))
    if member_lines:
        modules.append(ModuleResult("members", "Members", member_lines, members))

    text = module_lines(modules, enabled_color, palette)
    print(_render_with_lines(config, output_format, org.get("avatar_url"), text))
    return 0


def handle_compare_command(args: argparse.Namespace) -> int:
    if len(args.users) < 2:
        raise ConfigError("compare needs at least two users")
    config = _load_config_with_path(args)
    client = _client_for(args, config)
    output_format = args.format or config["display"].get("format", "ansi")
    enabled_color = color_enabled(config, output_format)
    palette = palette_for(config)

    columns: list[list[str]] = []
    avatars: list[list[str]] = []
    margin = max(0, int(config["display"].get("margin", 0)))

    column_width = max(20, args.column_width)
    avatar_color = config["display"].get("avatar_color", "none") if enabled_color else "none"

    for user_login in args.users:
        try:
            ctx = client.get_context(
                username=user_login,
                mode="public",
                repo_filters=config["repo_filters"],
            )
        except GitHubAPIError as exc:
            print(f"api error for {user_login}: {exc}")
            return 1
        modules: list[ModuleResult] = []
        for name in build_module_list(config):
            try:
                result = MODULE_HANDLERS[name](config, ctx, client)
            except KeyError:
                continue
            hide_if_empty = config["modules"].get(name, {}).get("hide_if_empty", True)
            if hide_if_empty and not result.lines:
                result.hidden = True
            modules.append(result)
        visible = [m for m in modules if not m.hidden]
        text = module_lines(visible, enabled_color, palette)
        columns.append(text)
        if config["display"].get("avatar") and output_format in {"ansi", "plain"}:
            avatars.append(
                render_avatar(
                    ctx.user.get("avatar_url"),
                    width=column_width,
                    style=config["display"].get("avatar_style", "ascii"),
                    color_mode=avatar_color,
                    ramp=config["display"]["ascii_ramp"],
                )
            )
        else:
            avatars.append([])

    blocks: list[list[str]] = []
    for avatar, text in zip(avatars, columns):
        block = list(avatar)
        if avatar:
            block.append("")
        block.extend(text)
        blocks.append(block)

    height = max((len(b) for b in blocks), default=0)
    rows: list[str] = []
    for row in range(height):
        parts: list[str] = []
        for block in blocks:
            line = block[row] if row < len(block) else ""
            visible = visible_len(line)
            pad = " " * max(0, column_width - visible)
            parts.append(line + pad)
        rows.append("    ".join(parts))
    print(apply_margin("\n".join(rows), margin))
    return 0
