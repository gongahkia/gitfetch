from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from gitfetch.github_api import GitHubClient, GitHubContext, format_relative_days


HEATMAP_BLOCKS = [" ", "░", "▒", "▓", "█"]


@dataclass
class ModuleResult:
    name: str
    title: str
    lines: list[str]
    data: Any
    hidden: bool = False
    requires_token: bool = False


def build_module_list(config: dict[str, Any]) -> list[str]:
    modules = config["modules"]
    order = modules["order"]
    return [name for name in order if modules.get(name, {}).get("enabled")]


def module_identity(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    user = context.user
    lines = [f"@{user['login']}"]
    if user.get("name"):
        lines.append(user["name"])
    if user.get("bio"):
        lines.append(user["bio"])
    for label, field in (
        ("company", "company"),
        ("blog", "blog"),
        ("location", "location"),
    ):
        value = user.get(field)
        if value:
            lines.append(f"{label}: {value}")
    return ModuleResult("identity", "Identity", lines, {"user": user})


def module_stats(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    user = context.user
    created_at = datetime.fromisoformat(user["created_at"].replace("Z", "+00:00"))
    age_hours = int((datetime.now(created_at.tzinfo) - created_at).total_seconds() / 3600)
    latest_repo_activity = None
    for repo in context.repos:
        pushed_at = repo.get("pushed_at")
        if pushed_at and (latest_repo_activity is None or pushed_at > latest_repo_activity):
            latest_repo_activity = pushed_at
    latest_public_event = context.events[0]["created_at"] if context.events else None
    lines = [
        f"{age_hours} hours since joining GitHub",
        f"{user.get('public_repos', len(context.repos))} public repos",
        f"{user.get('public_gists', 0)} public gists",
        f"{user.get('followers', 0)} followers",
        f"{user.get('following', 0)} following",
    ]
    if latest_public_event:
        lines.append(f"last public activity: {format_relative_days(latest_public_event)}")
    elif latest_repo_activity:
        lines.append(f"last repo activity: {format_relative_days(latest_repo_activity)}")
    if user.get("updated_at"):
        lines.append(f"profile updated: {format_relative_days(user['updated_at'])}")
    if context.viewer_mode:
        private_count = sum(1 for repo in context.repos if repo.get("private"))
        if private_count:
            lines.append(f"{private_count} private repos visible in viewer mode")
    return ModuleResult("stats", "Stats", lines, {"user": user, "viewer_mode": context.viewer_mode})


def module_languages(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    limit = config["modules"]["languages"].get("limit", 5)
    totals: dict[str, int] = {}
    for repo in context.repos:
        url = repo.get("languages_url")
        if not url:
            continue
        for language, bytes_count in client.get_languages(url).items():
            totals[language] = totals.get(language, 0) + int(bytes_count)
    total_bytes = sum(totals.values())
    if not total_bytes:
        return ModuleResult("languages", "Languages", [], {}, hidden=True)
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:limit]
    lines = [f"{language} {count * 100 // total_bytes}%" for language, count in ranked]
    data = [{"language": language, "bytes": count} for language, count in ranked]
    return ModuleResult("languages", "Languages", lines, data)


def module_contributions(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    weeks = context.graphql.get("contributionsCollection", {}).get("contributionCalendar", {}).get("weeks", [])
    if not weeks:
        return ModuleResult("contributions", "Contributions", [], [], hidden=True, requires_token=True)
    num_weeks = config["display"]["heatmap_weeks"]
    recent = weeks[-num_weeks:] if len(weeks) > num_weeks else weeks
    max_count = max((day["contributionCount"] for week in recent for day in week["contributionDays"]), default=1) or 1
    lines: list[str] = []
    for day_idx in range(7):
        row = ""
        for week in recent:
            days = week["contributionDays"]
            if day_idx < len(days):
                level = min(4, days[day_idx]["contributionCount"] * 4 // max_count)
                row += HEATMAP_BLOCKS[level]
            else:
                row += " "
        lines.append(row)
    return ModuleResult("contributions", "Contributions", lines, recent, requires_token=True)


def module_social_accounts(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    limit = config["modules"]["social_accounts"].get("limit", 5)
    accounts = client.get_social_accounts(context.target_user)[:limit]
    lines = []
    data = []
    for account in accounts:
        provider = account.get("provider", "unknown")
        url = account.get("url") or account.get("display_name") or ""
        lines.append(f"{provider}: {url}")
        data.append({"provider": provider, "url": account.get("url"), "display_name": account.get("display_name")})
    return ModuleResult("social_accounts", "Social Accounts", lines, data, hidden=not bool(lines))


def module_organizations(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    limit = config["modules"]["organizations"].get("limit", 8)
    orgs = client.get_organizations(context.target_user)[:limit]
    lines = [org["login"] for org in orgs]
    return ModuleResult("organizations", "Organizations", lines, orgs, hidden=not bool(lines))


def _repo_lines(items: list[dict[str, Any]], limit: int, include_owner: bool = True) -> tuple[list[str], list[dict[str, Any]]]:
    lines = []
    data = []
    for item in items[:limit]:
        name = item.get("full_name") if include_owner else item.get("name")
        stars = item.get("stargazers_count")
        language = item.get("language") or item.get("primary_language") or "n/a"
        lines.append(f"{name} ({language}, {stars} stars)")
        data.append(
            {
                "name": name,
                "language": language,
                "stars": stars,
                "url": item.get("html_url"),
                "description": item.get("description"),
            }
        )
    return lines, data


def module_starred(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    limit = config["modules"]["starred"].get("limit", 5)
    repos = client.get_starred(context.target_user, limit)
    lines, data = _repo_lines(repos, limit)
    return ModuleResult("starred", "Starred", lines, data, hidden=not bool(lines))


def module_watched(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    limit = config["modules"]["watched"].get("limit", 5)
    repos = client.get_subscriptions(context.target_user, limit)
    lines, data = _repo_lines(repos, limit)
    return ModuleResult("watched", "Watched", lines, data, hidden=not bool(lines))


def module_gists(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    limit = config["modules"]["gists"].get("limit", 5)
    gists = client.get_gists(context.target_user, limit)
    lines = []
    data = []
    for gist in gists:
        gist_id = gist.get("id")
        description = gist.get("description") or "untitled gist"
        lines.append(f"{gist_id}: {description}")
        data.append({"id": gist_id, "description": description, "url": gist.get("html_url")})
    return ModuleResult("gists", "Gists", lines, data, hidden=not bool(lines))


def module_recent_activity(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    limit = config["modules"]["recent_activity"].get("limit", 5)
    events = context.events[:limit]
    lines = []
    data = []
    for event in events:
        repo_name = (event.get("repo") or {}).get("name", "unknown repo")
        line = f"{event.get('type')}: {repo_name} ({format_relative_days(event.get('created_at'))})"
        lines.append(line)
        data.append({"type": event.get("type"), "repo": repo_name, "created_at": event.get("created_at")})
    return ModuleResult("recent_activity", "Recent Activity", lines, data, hidden=not bool(lines))


def module_showcase(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    limit = config["modules"]["showcase"].get("limit", 5)
    nodes = (
        context.graphql.get("itemShowcase", {})
        .get("items", {})
        .get("nodes", [])
    )[:limit]
    lines = []
    data = []
    for node in nodes:
        typename = node.get("__typename")
        if typename == "Repository":
            primary_language = (node.get("primaryLanguage") or {}).get("name") or "n/a"
            lines.append(f"{node.get('nameWithOwner')} ({primary_language}, {node.get('stargazerCount')} stars)")
        else:
            lines.append(f"{typename}: {node.get('name') or node.get('description') or 'showcase item'}")
        data.append(node)
    return ModuleResult("showcase", "Showcase", lines, data, hidden=not bool(lines), requires_token=True)


def module_sponsors(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    has_listing = bool(context.graphql.get("hasSponsorsListing"))
    lines = ["sponsor listing available"] if has_listing else []
    data = {"has_sponsors_listing": has_listing}
    return ModuleResult("sponsors", "Sponsors", lines, data, hidden=not has_listing, requires_token=True)


def module_profile_readme(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    max_lines = config["modules"]["profile_readme"].get("max_lines", 4)
    content = client.get_profile_readme(context.target_user)
    if not content:
        return ModuleResult("profile_readme", "Profile README", [], None, hidden=True)
    lines = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = line.replace("#", "").strip()
        if line:
            lines.append(line[:120])
        if len(lines) >= max_lines:
            break
    return ModuleResult("profile_readme", "Profile README", lines, content, hidden=not bool(lines))


def module_top_repos(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    limit = config["modules"]["top_repos"].get("limit", 5)
    repos = sorted(
        context.repos,
        key=lambda repo: (repo.get("stargazers_count", 0), repo.get("updated_at", "")),
        reverse=True,
    )[:limit]
    lines, data = _repo_lines(repos, limit)
    return ModuleResult("top_repos", "Top Repos", lines, data, hidden=not bool(lines))


MODULE_HANDLERS: dict[str, Callable[[dict[str, Any], GitHubContext, GitHubClient], ModuleResult]] = {
    "identity": module_identity,
    "stats": module_stats,
    "languages": module_languages,
    "contributions": module_contributions,
    "social_accounts": module_social_accounts,
    "organizations": module_organizations,
    "starred": module_starred,
    "watched": module_watched,
    "gists": module_gists,
    "recent_activity": module_recent_activity,
    "showcase": module_showcase,
    "sponsors": module_sponsors,
    "profile_readme": module_profile_readme,
    "top_repos": module_top_repos,
}
