from __future__ import annotations

import argparse
import json
import shutil
from itertools import pairwise
from pathlib import Path
from typing import Any

from gitfetch.cache import CacheStore
from gitfetch.config import (
    PROVIDER_TOKEN_ENVS,
    ConfigError,
    apply_named_profile,
    cache_dir,
    config_path,
    get_token,
    load_config,
    normalize_config,
    set_override,
)
from gitfetch.github_api import GitHubAPIError, GitHubClient
from gitfetch.modules import MODULE_HANDLERS, available_module_metadata, build_module_list, load_plugin_modules
from gitfetch.modules.builtin import GRAPHQL_MODULES, ModuleResult
from gitfetch.providers import create_provider_client
from gitfetch.render import (
    SPLIT_GAP,
    apply_margin,
    color_enabled,
    effective_avatar_color,
    module_lines,
    palette_for,
    render_avatar,
    visible_len,
)
from gitfetch.semantics import (
    Measurement,
    RepositoryCoverage,
    aggregate,
    number,
    profile_measurements,
    repository_measurements,
)
from gitfetch.terminal_text import sanitize_text


def _apply_common_overrides(args: argparse.Namespace, config: dict[str, Any]) -> None:
    for item in getattr(args, "set", []) or []:
        if "=" not in item:
            raise ConfigError(f"invalid override '{item}', expected KEY=VALUE")
        key, value = item.split("=", 1)
        set_override(config, key, value)
    if getattr(args, "format", None):
        config["display"]["format"] = args.format
    if getattr(args, "provider", None):
        config["profile"]["provider"] = args.provider
    if getattr(args, "base_url", None):
        provider = config["profile"].get("provider", "github")
        config.setdefault("providers", {}).setdefault(provider, {})["base_url"] = args.base_url
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
    normalize_config(config)


def _load_config_with_path(args: argparse.Namespace) -> dict[str, Any]:
    from pathlib import Path
    path = Path(args.config_path) if getattr(args, "config_path", None) else config_path()
    config = load_config(path)
    apply_named_profile(config, getattr(args, "profile", None))
    _apply_common_overrides(args, config)
    load_plugin_modules(config)
    return config


def _client_for(args: argparse.Namespace, config: dict[str, Any]) -> GitHubClient:
    token = get_token(getattr(args, "token", None), config)
    cache = CacheStore(
        cache_dir(),
        enabled=bool(config["cache"]["enabled"]),
        ttl_seconds=int(config["cache"]["ttl_seconds"]),
        bypass_read=bool(getattr(args, "refresh", False)),
    )
    return create_provider_client(config, token=token, cache=cache, offline=bool(getattr(args, "offline", False)))


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
                color_mode=effective_avatar_color(config, output_format),
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


def _module_payload(modules: list[ModuleResult]) -> dict[str, Any]:
    return {module.name: module.data for module in modules if not module.hidden}


def _metric_text(value: Any) -> str:
    return "unavailable" if value is None else str(value)


def _emit_mode_output(
    config: dict[str, Any],
    args: argparse.Namespace,
    *,
    kind: str,
    title: str,
    subtitle: str,
    avatar_url: str | None,
    modules: list[ModuleResult],
    extra: dict[str, Any] | None = None,
) -> None:
    output_format = args.format or config["display"].get("format", "ansi")
    visible_modules = [module for module in modules if not module.hidden]
    if output_format == "json":
        payload = {
            "type": kind,
            "title": title,
            "subtitle": subtitle,
            "modules": _module_payload(visible_modules),
        }
        if extra:
            payload.update(extra)
        _write_or_print(json.dumps(payload, indent=2), args)
        return

    if output_format in {"card", "png"}:
        from gitfetch.formats import render_summary_card_png, render_summary_card_svg

        if output_format == "png":
            render_summary_card_png(config, title, subtitle, visible_modules, avatar_url, _png_output_path(args))
            print(f"wrote {args.save}")
        else:
            _write_or_print(render_summary_card_svg(config, title, subtitle, visible_modules, avatar_url), args)
        return

    if output_format == "svg":
        from gitfetch.formats import render_terminal_svg

        svg_config = {**config, "_color_force": "on"}
        palette = palette_for(svg_config)
        text_lines = module_lines(visible_modules, color_enabled(svg_config, "ansi"), palette)
        terminal_text = _render_with_lines(svg_config, "ansi", avatar_url, text_lines)
        _write_or_print(render_terminal_svg(terminal_text, config), args)
        return

    enabled_color = color_enabled(config, output_format)
    palette = palette_for(config)
    text = module_lines(visible_modules, enabled_color, palette)
    _write_or_print(_render_with_lines(config, output_format, avatar_url, text), args)


def _token_required_result(name: str, client=None) -> ModuleResult:
    env_name = PROVIDER_TOKEN_ENVS.get(getattr(client, "provider_name", "github"), "GITHUB_TOKEN")
    return ModuleResult(
        name,
        name.replace("_", " ").title(),
        [f"requires --token, {env_name}, or profile.token_command"],
        {"requires_token": True},
        requires_token=True,
        measurements={name: Measurement(provider=getattr(client, "provider_name", "github"), availability="auth_required",
                                        reason="module requires a token")},
    )


def _unsupported_provider_result(name: str, client) -> ModuleResult:
    reason = client.unsupported_reason(name)
    return ModuleResult(
        name,
        name.replace("_", " ").title(),
        [f"unsupported on {client.provider_title}: {reason}"],
        {"unsupported": True, "provider": client.provider_name, "reason": reason},
        measurements={name: Measurement(provider=client.provider_name, availability="unsupported", reason=reason)},
    )


class _ComparedMetrics(dict[str, Any]):
    """Keep ranking provenance outside the existing JSON metric fields."""

    measurements: dict[str, Measurement]


def _compare_metrics(ctx) -> dict[str, Any]:
    languages: dict[str, int] = {}
    for repo in ctx.repos:
        language = repo.get("language")
        if language:
            languages[language] = languages.get(language, 0) + 1
    provider = getattr(ctx, "provider", "github")
    measured = profile_measurements(ctx.user, provider)
    supplied = getattr(ctx, "measurements", {})
    if isinstance(supplied, dict):
        measured.update({key: value for key, value in supplied.items()
                         if key in measured and isinstance(value, Measurement)})
    coverage = getattr(ctx, "repository_coverage", None)
    scope = coverage.scope if isinstance(coverage, RepositoryCoverage) else "public owned repositories"
    filters = coverage.filters if isinstance(coverage, RepositoryCoverage) else ()
    def measured_value(key: str):
        measurement = measured[key]
        return number(measurement.value) if measurement.availability == "available" else None

    result = _ComparedMetrics({
        "login": ctx.user.get("login"),
        "followers": measured_value("followers"),
        "following": measured_value("following"),
        "public_repos": measured_value("public_repos"),
        "stars": aggregate(ctx.repos, "stargazers_count"),
        "forks": aggregate(ctx.repos, "forks_count"),
        "languages": languages,
        "top_language": min(languages, key=lambda language: (-languages[language], language.casefold(), language)) if languages else None,
    })
    for key in ("stars", "forks"):
        measured[key] = Measurement(result[key], provider, key, f"{scope}; selected; filters={filters}",
                                    "available" if result[key] is not None else "unavailable", "repository responses", "complete" if result[key] is not None else "partial",
                                    sample_size=len(ctx.repos))
    result.measurements = measured
    known_languages = sum(bool(repo.get("language")) for repo in ctx.repos)
    measured["languages"] = Measurement(known_languages, provider, "repositories", "selected primary-language metadata",
                                        coverage="complete" if known_languages == len(ctx.repos) else "partial",
                                        sample_size=known_languages, denominator=len(ctx.repos))
    return result


def _rank_line(metrics: list[dict[str, Any]], key: str, label: str) -> str:
    ranked = [item for item in metrics if number(item.get(key)) is not None]
    missing = sorted(str(item["login"]) for item in metrics if number(item.get(key)) is None)
    scopes = set()
    for item in ranked:
        measurement = getattr(item, "measurements", {}).get(key)
        if measurement:
            scopes.add((measurement.provider, measurement.unit, measurement.scope))
    if len(scopes) > 1:
        return f"{label}: not comparable (different providers or measurement scopes)"
    suffix = f"; unavailable: {', '.join(missing)}" if missing else ""
    if len(ranked) < 2:
        return f"{label}: insufficient comparable data{suffix}"
    ranked.sort(key=lambda item: (-item[key], str(item["login"]).casefold(), str(item["login"])))
    values = f"{ranked[0]['login']} {ranked[0][key]}"
    for previous, item in pairwise(ranked):
        values += (" = " if previous[key] == item[key] else " > ") + f"{item['login']} {item[key]}"
    return f"{label}: {values}{suffix}"


def _compare_summary_module(metrics: list[dict[str, Any]]) -> ModuleResult:
    language_sets = [set(item["languages"]) for item in metrics]
    overlap = sorted(set.intersection(*language_sets)) if language_sets and all(language_sets) else []
    top_languages = ", ".join(f"{item['login']} {item.get('top_language') or 'n/a'}" for item in metrics)
    partial_languages = any(getattr(item, "measurements", {}).get("languages", Measurement()).coverage != "complete"
                            for item in metrics)
    overlap_text = ', '.join(overlap) if overlap else 'none'
    if partial_languages:
        overlap_text = f"{', '.join(overlap) if overlap else 'unavailable'} (primary-language metadata incomplete)"
    lines = [
        _rank_line(metrics, "followers", "followers"),
        _rank_line(metrics, "public_repos", "repos"),
        _rank_line(metrics, "stars", "stars (selected repos)"),
        _rank_line(metrics, "forks", "forks (selected repos)"),
        f"observed language overlap: {overlap_text}",
        f"top primary languages (selected repos): {top_languages}",
    ]
    return ModuleResult(
        "summary",
        "Compare Summary",
        lines,
        {
            "metrics": metrics,
            "language_overlap": overlap,
        },
    )


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
        print(sanitize_text(f"api error: {exc}"))
        return 1

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
        f"stars: {_metric_text(repo.get('stargazers_count'))}",
        f"forks: {_metric_text(repo.get('forks_count'))}",
        f"watchers: {_metric_text(repo.get('subscribers_count', repo.get('watchers_count')))}",
        f"open issues: {_metric_text(repo.get('open_issues_count'))}",
        f"size: {_metric_text(repo.get('size'))} {'bytes' if client.provider_name in {'gitlab', 'bitbucket'} else 'KB'}",
    ]
    if repo.get("pushed_at"):
        stats_lines.append(f"last push: {repo['pushed_at']}")
    modules.append(ModuleResult("stats", "Stats", stats_lines, repo, measurements=repository_measurements(repo, client.provider_name)))

    total_bytes = sum(languages.values()) or 1
    unit = getattr(client, "language_breakdown_unit", "bytes")
    ranked = sorted(languages.items(), key=lambda kv: (-kv[1], kv[0].casefold(), kv[0]))[:5]
    if unit == "percent":
        lang_lines = [f"{language} {count:g}% (project usage)" for language, count in ranked]
    elif unit == "repositories":
        lang_lines = [f"{language} (primary language)" for language, _ in ranked]
    else:
        lang_lines = [f"{language} {count * 100 // total_bytes}%" for language, count in ranked]
    if lang_lines:
        modules.append(ModuleResult("languages", "Languages", lang_lines, languages))

    contrib_lines = [
        f"{c.get('login')} ({_metric_text(c.get('contributions'))} commits{' in retrieved sample' if client.provider_name in {'gitea', 'forgejo', 'codeberg', 'bitbucket'} else ''})"
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

    avatar_url = (repo.get("owner") or {}).get("avatar_url")
    _emit_mode_output(
        config,
        args,
        kind="repository",
        title=repo.get("full_name") or args.target,
        subtitle=repo.get("description") or f"{client.provider_title} repository",
        avatar_url=avatar_url,
        modules=modules,
        extra={"target": args.target, "provider": client.provider_name},
    )
    return 0


def handle_org_command(args: argparse.Namespace) -> int:
    config = _load_config_with_path(args)
    client = _client_for(args, config)
    try:
        org = client.get_org(args.target)
        members = client.get_org_members(args.target, limit=args.members_limit)
        repos = client.get_org_repos(args.target)
    except GitHubAPIError as exc:
        print(sanitize_text(f"api error: {exc}"))
        return 1

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

    public_repos = org.get("public_repos")
    stats_lines = [
        f"public repos: {_metric_text(public_repos)}",
        f"members shown: {len(members)}",
        f"followers: {_metric_text(org.get('followers'))}",
    ]
    if all(repo.get("stargazers_count") is not None for repo in repos):
        total_stars = sum(repo["stargazers_count"] for repo in repos)
        stats_lines.insert(2, f"stars in fetched repos: {total_stars}")
    else:
        stats_lines.insert(2, "stars in fetched repos: unavailable")
    if public_repos is None:
        stats_lines.append(f"repos fetched: {len(repos)} (viewer-accessible)")

    measured_repos = [repo for repo in repos if number(repo.get("stargazers_count")) is not None]
    sorted_repos = sorted(measured_repos, key=lambda r: (-r["stargazers_count"], str(r.get("name") or "")))[:args.repos_limit]
    repo_title = "Top Repos (Known Stars)" if len(measured_repos) != len(repos) else "Top Repos"
    if not measured_repos:
        sorted_repos = sorted(repos, key=lambda r: str(r.get("name") or ""))[:args.repos_limit]
        repo_title = "Repositories (Stars Unavailable)"
    repo_lines = [
        f"{r.get('name')} ({r.get('language') or 'n/a'}, "
        f"★{_metric_text(r.get('stargazers_count'))})"
        for r in sorted_repos
    ]
    member_lines = [m.get("login", "?") for m in members]

    modules = [
        ModuleResult("identity", "Organization", identity_lines, org),
        ModuleResult("stats", "Stats", stats_lines, org, measurements=profile_measurements(org, client.provider_name)),
    ]
    if repo_lines:
        modules.append(ModuleResult("top_repos", repo_title, repo_lines, sorted_repos))
    if member_lines:
        modules.append(ModuleResult("members", "Members", member_lines, members))

    _emit_mode_output(
        config,
        args,
        kind="organization",
        title=org.get("name") or org.get("login") or args.target,
        subtitle=f"@{org.get('login', args.target)}",
        avatar_url=org.get("avatar_url"),
        modules=modules,
        extra={"target": args.target, "provider": client.provider_name},
    )
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
    contexts = []
    modules_by_user: dict[str, list[ModuleResult]] = {}
    margin = max(0, int(config["display"].get("margin", 0)))

    user_count = len(args.users)
    gap = 4
    if args.column_width is not None:
        column_width = max(20, args.column_width)
    else:
        term_cols = shutil.get_terminal_size((120, 24)).columns
        budget = term_cols - 2 * margin - gap * (user_count - 1)
        column_width = max(20, budget // user_count)
    avatar_color = effective_avatar_color(config, output_format)
    metadata = available_module_metadata()
    selected_modules = build_module_list(config)
    include_graphql = bool(set(selected_modules) & GRAPHQL_MODULES)

    for user_login in args.users:
        try:
            ctx = client.get_context(
                username=user_login,
                mode="public",
                repo_filters=config["repo_filters"],
                include_graphql=include_graphql,
            )
        except GitHubAPIError as exc:
            print(sanitize_text(f"api error for {user_login}: {exc}"))
            return 1
        contexts.append(ctx)
        modules: list[ModuleResult] = []
        for name in selected_modules:
            try:
                if not client.supports_module(name):
                    modules.append(_unsupported_provider_result(name, client))
                    continue
                token_required = client.module_token_required(name, metadata.get(name, {}).get("token_required", False))
                if token_required and not client.token:
                    modules.append(_token_required_result(name, client))
                    continue
                result = MODULE_HANDLERS[name](config, ctx, client)
            except KeyError:
                continue
            hide_if_empty = config["modules"].get(name, {}).get("hide_if_empty", True)
            if hide_if_empty and not result.lines:
                result.hidden = True
            modules.append(result)
        visible = [m for m in modules if not m.hidden]
        modules_by_user[user_login] = visible
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

    metrics = [_compare_metrics(ctx) for ctx in contexts]
    summary = _compare_summary_module(metrics)
    if output_format == "json":
        payload = {
            "type": "compare",
            "provider": client.provider_name,
            "users": args.users,
            "summary": summary.data,
            "modules": {
                user: _module_payload(modules)
                for user, modules in modules_by_user.items()
            },
        }
        _write_or_print(json.dumps(payload, indent=2), args)
        return 0

    if output_format in {"card", "png"}:
        card_modules = [summary]
        for metric in metrics:
            card_modules.append(
                ModuleResult(
                    metric["login"],
                    str(metric["login"]),
                    [
                        f"followers: {_metric_text(metric['followers'])}",
                        f"repos: {_metric_text(metric['public_repos'])}",
                        f"stars: {_metric_text(metric['stars'])}",
                        f"top language: {metric.get('top_language') or 'n/a'}",
                    ],
                    metric,
                )
            )
        _emit_mode_output(
            config,
            args,
            kind="compare",
            title=f"{client.provider_title} Compare",
            subtitle=" vs ".join(args.users),
            avatar_url=None,
            modules=card_modules,
            extra={"users": args.users, "provider": client.provider_name},
        )
        return 0

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
            visible_width = visible_len(line)
            pad = " " * max(0, column_width - visible_width)
            parts.append(line + pad)
        rows.append("    ".join(parts))
    summary_text = module_lines([summary], enabled_color, palette)
    final_text = "\n".join(summary_text + [""] + rows)
    if output_format == "svg":
        from gitfetch.formats import render_terminal_svg

        svg_config = {**config, "_color_force": "on"}
        svg_summary = module_lines([summary], color_enabled(svg_config, "ansi"), palette_for(svg_config))
        _write_or_print(render_terminal_svg("\n".join(svg_summary + [""] + rows), config), args)
    else:
        _write_or_print(apply_margin(final_text, margin), args)
    return 0
