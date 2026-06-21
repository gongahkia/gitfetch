from __future__ import annotations

import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from gitfetch.github_api import GitHubClient, GitHubContext, format_relative_days


HEATMAP_BLOCKS = [" ", "░", "▒", "▓", "█"]
SPARKLINE_BLOCKS = [" ", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]


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
    selected = [name for name in order if modules.get(name, {}).get("enabled")]
    for name in config.get("plugins", {}).get("modules", []) or []:
        if name not in selected and modules.get(name, {"enabled": True}).get("enabled", True):
            selected.append(name)
    return selected


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
    provider_title = getattr(context, "provider_title", getattr(client, "provider_title", "GitHub"))
    created_at = _parse_github_timestamp(user.get("created_at"))
    age_hours = int((datetime.now(created_at.tzinfo) - created_at).total_seconds() / 3600) if created_at else None
    latest_repo_activity = None
    for repo in context.repos:
        pushed_at = repo.get("pushed_at")
        if pushed_at and (latest_repo_activity is None or pushed_at > latest_repo_activity):
            latest_repo_activity = pushed_at
    latest_public_event = context.events[0]["created_at"] if context.events else None
    lines = []
    if age_hours is not None:
        lines.append(f"{age_hours} hours since joining {provider_title}")
    else:
        lines.append(f"join date unavailable on {provider_title}")
    lines.extend([
        f"{user.get('public_repos', len(context.repos))} public repos",
        f"{user.get('public_gists', 0)} public gists",
        f"{user.get('followers', 0)} followers",
        f"{user.get('following', 0)} following",
    ])
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
    workers = max(1, int(config["modules"]["languages"].get("workers", 8)))
    totals: dict[str, int] = {}
    urls = [repo.get("languages_url") for repo in context.repos if repo.get("languages_url")]
    if workers == 1 or len(urls) <= 1:
        language_payloads = [client.get_languages(url) for url in urls]
    else:
        language_payloads = []
        with ThreadPoolExecutor(max_workers=min(workers, len(urls))) as executor:
            futures = [executor.submit(client.get_languages, url) for url in urls]
            for future in as_completed(futures):
                language_payloads.append(future.result())
    for payload in language_payloads:
        for language, bytes_count in payload.items():
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


def _split_full_name(repo: dict[str, Any]) -> tuple[str, str] | None:
    full_name = repo.get("full_name")
    if isinstance(full_name, str) and "/" in full_name:
        owner, name = full_name.split("/", 1)
        return owner, name
    owner = (repo.get("owner") or {}).get("login")
    name = repo.get("name")
    if owner and name:
        return owner, name
    return None


def _recent_repos(context: GitHubContext, limit: int) -> list[dict[str, Any]]:
    return sorted(
        context.repos,
        key=lambda repo: repo.get("pushed_at") or repo.get("updated_at") or "",
        reverse=True,
    )[:limit]


def _parse_github_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def module_releases(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    settings = config["modules"]["releases"]
    limit = int(settings.get("limit", 5))
    repos_limit = int(settings.get("repos_limit", 8))
    lines: list[str] = []
    data: list[dict[str, Any]] = []
    for repo in _recent_repos(context, repos_limit):
        parsed = _split_full_name(repo)
        if not parsed:
            continue
        owner, name = parsed
        for release in client.get_repo_releases(owner, name, limit=1):
            tag = release.get("tag_name") or release.get("name") or "release"
            when = format_relative_days(release.get("published_at") or release.get("created_at"))
            lines.append(f"{repo.get('name')}: {tag}" + (f" ({when})" if when else ""))
            data.append({"repository": repo.get("full_name"), "release": release})
            if len(lines) >= limit:
                return ModuleResult("releases", "Releases", lines, data)
    return ModuleResult("releases", "Releases", lines, data, hidden=not bool(lines))


def module_discussions(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    settings = config["modules"]["discussions"]
    limit = int(settings.get("limit", 5))
    repos_limit = int(settings.get("repos_limit", 8))
    rows: list[tuple[str, int]] = []
    for repo in _recent_repos(context, repos_limit):
        parsed = _split_full_name(repo)
        if not parsed:
            continue
        count = client.get_repo_discussions_count(*parsed)
        if count:
            rows.append((repo.get("name") or repo.get("full_name") or "repo", count))
    rows.sort(key=lambda item: item[1], reverse=True)
    lines = [f"{name}: {count}" for name, count in rows[:limit]]
    data = [{"repository": name, "discussions": count} for name, count in rows[:limit]]
    return ModuleResult("discussions", "Discussions", lines, data, hidden=not bool(lines), requires_token=True)


def module_actions_status(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    settings = config["modules"]["actions_status"]
    limit = int(settings.get("limit", 5))
    repos_limit = int(settings.get("repos_limit", 8))
    lines: list[str] = []
    data: list[dict[str, Any]] = []
    for repo in _recent_repos(context, repos_limit):
        parsed = _split_full_name(repo)
        if not parsed:
            continue
        runs = client.get_repo_workflow_runs(*parsed, limit=1)
        if not runs:
            continue
        run = runs[0]
        status = run.get("conclusion") or run.get("status") or "unknown"
        workflow = run.get("name") or run.get("display_title") or "workflow"
        lines.append(f"{repo.get('name')}: {workflow} {status}")
        data.append({"repository": repo.get("full_name"), "run": run})
        if len(lines) >= limit:
            break
    return ModuleResult("actions_status", "Actions", lines, data, hidden=not bool(lines))


def module_repo_health(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    repos = context.repos
    total = len(repos)
    if not total:
        return ModuleResult("repo_health", "Repo Health", [], {}, hidden=True)
    licensed = sum(1 for repo in repos if repo.get("license"))
    issues_enabled = sum(1 for repo in repos if repo.get("has_issues"))
    archived = sum(1 for repo in repos if repo.get("archived"))
    templates = sum(1 for repo in repos if repo.get("is_template"))
    now = datetime.now(timezone.utc)
    active_90 = 0
    for repo in repos:
        pushed_at = _parse_github_timestamp(repo.get("pushed_at") or repo.get("updated_at"))
        if pushed_at and (now - pushed_at).days <= 90:
            active_90 += 1
    lines = [
        f"active in 90d: {active_90}/{total}",
        f"licensed: {licensed}/{total}",
        f"issues enabled: {issues_enabled}/{total}",
        f"archived: {archived}",
    ]
    if templates:
        lines.append(f"templates: {templates}")
    data = {
        "total": total,
        "active_90_days": active_90,
        "licensed": licensed,
        "issues_enabled": issues_enabled,
        "archived": archived,
        "templates": templates,
    }
    return ModuleResult("repo_health", "Repo Health", lines, data)


def module_topics(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    limit = int(config["modules"]["topics"].get("limit", 8))
    counter: Counter[str] = Counter()
    for repo in context.repos:
        for topic in repo.get("topics") or []:
            counter[str(topic)] += 1
    lines = [f"{topic}: {count}" for topic, count in counter.most_common(limit)]
    data = [{"topic": topic, "count": count} for topic, count in counter.most_common(limit)]
    return ModuleResult("topics", "Topics", lines, data, hidden=not bool(lines))


def module_dependencies(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    settings = config["modules"]["dependencies"]
    limit = int(settings.get("limit", 6))
    repos_limit = int(settings.get("repos_limit", 5))
    package_counter: Counter[str] = Counter()
    repos_scanned = 0
    for repo in _recent_repos(context, repos_limit):
        parsed = _split_full_name(repo)
        if not parsed:
            continue
        sbom = client.get_repo_sbom(*parsed)
        packages = (sbom.get("sbom") or {}).get("packages") or []
        if packages:
            repos_scanned += 1
        for package in packages:
            name = package.get("name") or package.get("SPDXID") or "unknown"
            if name != "unknown":
                package_counter[str(name)] += 1
    lines = [f"{name}: {count}" for name, count in package_counter.most_common(limit)]
    if repos_scanned:
        lines.append(f"repos scanned: {repos_scanned}")
    data = {
        "repos_scanned": repos_scanned,
        "packages": [{"name": name, "count": count} for name, count in package_counter.most_common(limit)],
    }
    return ModuleResult("dependencies", "Dependencies", lines, data, hidden=not bool(package_counter))


def module_security_advisories(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    settings = config["modules"]["security_advisories"]
    limit = int(settings.get("limit", 5))
    repos_limit = int(settings.get("repos_limit", 8))
    advisories: list[dict[str, Any]] = []
    for repo in _recent_repos(context, repos_limit):
        parsed = _split_full_name(repo)
        if not parsed:
            continue
        for advisory in client.get_repo_security_advisories(*parsed, limit=limit):
            advisories.append({"repository": repo.get("full_name"), "advisory": advisory})
            if len(advisories) >= limit:
                break
        if len(advisories) >= limit:
            break
    severity_counts: Counter[str] = Counter()
    lines: list[str] = []
    for item in advisories:
        advisory = item["advisory"]
        severity = advisory.get("severity") or advisory.get("cvss", {}).get("severity") or "unknown"
        severity_counts[str(severity)] += 1
        summary = advisory.get("summary") or advisory.get("ghsa_id") or "advisory"
        lines.append(f"{item['repository']}: {severity} {summary[:60]}")
    if severity_counts:
        lines.insert(0, "severity: " + ", ".join(f"{k} {v}" for k, v in severity_counts.items()))
    return ModuleResult("security_advisories", "Security Advisories", lines, advisories, hidden=not bool(lines), requires_token=True)


def module_packages(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    settings = config["modules"]["packages"]
    limit = int(settings.get("limit", 5))
    package_types = settings.get("types") or ["container", "npm", "maven", "rubygems", "nuget"]
    lines: list[str] = []
    data: list[dict[str, Any]] = []
    for package_type in package_types:
        packages = client.get_user_packages(context.target_user, str(package_type), limit=limit)
        for package in packages:
            name = package.get("name") or package.get("html_url") or "package"
            lines.append(f"{package_type}: {name}")
            data.append({"type": package_type, "package": package})
            if len(lines) >= limit:
                return ModuleResult("packages", "Packages", lines, data)
    return ModuleResult("packages", "Packages", lines, data, hidden=not bool(lines))


def module_contribution_breakdown(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    contrib = context.graphql.get("contributionsCollection", {})
    if not contrib:
        return ModuleResult("contribution_breakdown", "Contribution Breakdown", [], {}, hidden=True, requires_token=True)
    lines = [
        f"commits: {contrib.get('totalCommitContributions', 0)}",
        f"issues: {contrib.get('totalIssueContributions', 0)}",
        f"pull requests: {contrib.get('totalPullRequestContributions', 0)}",
        f"reviews: {contrib.get('totalPullRequestReviewContributions', 0)}",
    ]
    calendar = contrib.get("contributionCalendar") or {}
    if calendar.get("totalContributions") is not None:
        lines.append(f"calendar total: {calendar.get('totalContributions', 0)}")
    data = {
        "commits": contrib.get("totalCommitContributions", 0),
        "issues": contrib.get("totalIssueContributions", 0),
        "pull_requests": contrib.get("totalPullRequestContributions", 0),
        "reviews": contrib.get("totalPullRequestReviewContributions", 0),
        "calendar_total": calendar.get("totalContributions", 0),
    }
    return ModuleResult("contribution_breakdown", "Contribution Breakdown", lines, data, requires_token=True)


def module_commit_cadence(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    window = int(config["modules"]["commit_cadence"].get("days", 30))
    days = _flatten_contribution_days(context.graphql)
    if days:
        recent = sorted(days, key=lambda d: d.get("date", ""))[-window:]
        active_days = sum(1 for day in recent if day.get("contributionCount", 0) > 0)
        total = sum(day.get("contributionCount", 0) for day in recent)
        peak = max((day.get("contributionCount", 0) for day in recent), default=0)
        lines = [
            f"last {len(recent)} days: {total} contributions",
            f"active days: {active_days}",
            f"peak day: {peak}",
        ]
        return ModuleResult("commit_cadence", "Commit Cadence", lines, {"days": recent, "total": total, "active_days": active_days})

    push_events = [event for event in context.events if event.get("type") == "PushEvent"]
    commit_count = sum(len((event.get("payload") or {}).get("commits") or []) for event in push_events)
    lines = [
        f"push events shown: {len(push_events)}",
        f"commits in public events: {commit_count}",
    ]
    data = {"push_events": len(push_events), "commits": commit_count}
    return ModuleResult("commit_cadence", "Commit Cadence", lines, data, hidden=not bool(push_events))


def module_maintainer_activity(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    repos = context.repos
    if not repos:
        return ModuleResult("maintainer_activity", "Maintainer Activity", [], {}, hidden=True)
    now = datetime.now(timezone.utc)
    recent_pushes = 0
    stale = 0
    open_issues = 0
    stars = 0
    forks = 0
    for repo in repos:
        pushed = _parse_github_timestamp(repo.get("pushed_at") or repo.get("updated_at"))
        if pushed and (now - pushed).days <= 30:
            recent_pushes += 1
        if pushed and (now - pushed).days > 365:
            stale += 1
        open_issues += int(repo.get("open_issues_count", 0) or 0)
        stars += int(repo.get("stargazers_count", 0) or 0)
        forks += int(repo.get("forks_count", 0) or 0)
    lines = [
        f"pushed in 30d: {recent_pushes}/{len(repos)}",
        f"stale >365d: {stale}",
        f"open issues: {open_issues}",
        f"stars/forks: {stars}/{forks}",
    ]
    data = {
        "recent_pushes_30_days": recent_pushes,
        "stale_repos_over_365_days": stale,
        "open_issues": open_issues,
        "stars": stars,
        "forks": forks,
    }
    return ModuleResult("maintainer_activity", "Maintainer Activity", lines, data)


def _flatten_contribution_days(graphql: dict[str, Any]) -> list[dict[str, Any]]:
    weeks = graphql.get("contributionsCollection", {}).get("contributionCalendar", {}).get("weeks", [])
    days: list[dict[str, Any]] = []
    for week in weeks:
        for day in week.get("contributionDays", []):
            days.append(day)
    return days


def module_streaks(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    days = _flatten_contribution_days(context.graphql)
    if not days:
        return ModuleResult("streaks", "Streaks", [], {}, hidden=True, requires_token=True)
    today_iso = time.strftime("%Y-%m-%d")
    days_sorted = sorted(days, key=lambda d: d.get("date", ""))
    longest = current = run = 0
    for day in days_sorted:
        if day.get("contributionCount", 0) > 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    current = 0
    for day in reversed(days_sorted):
        date = day.get("date", "")
        count = day.get("contributionCount", 0)
        if not current and date == today_iso and count == 0:
            continue
        if count > 0:
            current += 1
        else:
            break
    total = sum(day.get("contributionCount", 0) for day in days_sorted)
    contrib = context.graphql.get("contributionsCollection", {})
    lines = [
        f"current: {current} day(s)",
        f"longest: {longest} day(s)",
        f"year total: {total}",
    ]
    if contrib.get("totalCommitContributions") is not None:
        lines.append(f"commits: {contrib.get('totalCommitContributions', 0)}")
        lines.append(f"reviews: {contrib.get('totalPullRequestReviewContributions', 0)}")
    data = {"current": current, "longest": longest, "total": total}
    return ModuleResult("streaks", "Streaks", lines, data, requires_token=True)


def module_pull_requests(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    graphql = context.graphql
    if not graphql:
        return ModuleResult("pull_requests", "Pull Requests", [], {}, hidden=True, requires_token=True)
    open_count = (graphql.get("openPRs") or {}).get("totalCount", 0)
    merged_count = (graphql.get("mergedPRs") or {}).get("totalCount", 0)
    closed_count = (graphql.get("closedPRs") or {}).get("totalCount", 0)
    lines = [
        f"open: {open_count}",
        f"merged: {merged_count}",
        f"closed: {closed_count}",
    ]
    data = {"open": open_count, "merged": merged_count, "closed": closed_count}
    title = "Merge Requests" if getattr(client, "provider_name", "") == "gitlab" else "Pull Requests"
    return ModuleResult("pull_requests", title, lines, data, requires_token=True)


def module_issues(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    graphql = context.graphql
    if not graphql:
        return ModuleResult("issues", "Issues", [], {}, hidden=True, requires_token=True)
    open_count = (graphql.get("openIssues") or {}).get("totalCount", 0)
    closed_count = (graphql.get("closedIssues") or {}).get("totalCount", 0)
    lines = [f"open: {open_count}", f"closed: {closed_count}"]
    data = {"open": open_count, "closed": closed_count}
    return ModuleResult("issues", "Issues", lines, data, requires_token=True)


def module_rate_limit(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    payload = client.get_rate_limit()
    core = (payload.get("resources") or {}).get("core") or payload.get("rate") or {}
    if not core:
        return ModuleResult("rate_limit", "Rate Limit", [], {}, hidden=True)
    remaining = core.get("remaining", 0)
    limit = core.get("limit", 0)
    reset = core.get("reset")
    lines = [f"core: {remaining}/{limit}"]
    if reset:
        secs = max(0, int(reset) - int(time.time()))
        lines.append(f"resets in: {secs // 60}m {secs % 60}s")
    graphql_bucket = (payload.get("resources") or {}).get("graphql") or {}
    if graphql_bucket:
        lines.append(f"graphql: {graphql_bucket.get('remaining', 0)}/{graphql_bucket.get('limit', 0)}")
    return ModuleResult("rate_limit", "Rate Limit", lines, payload)


def module_pinned(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    nodes = (context.graphql.get("pinnedItems") or {}).get("nodes") or []
    limit = config["modules"]["pinned"].get("limit", 6)
    lines: list[str] = []
    data: list[dict[str, Any]] = []
    for node in nodes[:limit]:
        if node.get("__typename") == "Repository":
            language = (node.get("primaryLanguage") or {}).get("name") or "n/a"
            stars = node.get("stargazerCount", 0)
            lines.append(f"{node.get('nameWithOwner')} ({language}, ★{stars})")
        else:
            lines.append(f"gist: {node.get('name') or node.get('description') or 'untitled'}")
        data.append(node)
    return ModuleResult("pinned", "Pinned", lines, data, hidden=not bool(lines), requires_token=True)


def module_sparkline(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    days = _flatten_contribution_days(context.graphql)
    if not days:
        return ModuleResult("sparkline", "Sparkline", [], {}, hidden=True, requires_token=True)
    window = int(config["modules"]["sparkline"].get("days", 30))
    recent = sorted(days, key=lambda d: d.get("date", ""))[-window:]
    counts = [d.get("contributionCount", 0) for d in recent]
    peak = max(counts) or 1
    line = "".join(SPARKLINE_BLOCKS[min(len(SPARKLINE_BLOCKS) - 1, c * (len(SPARKLINE_BLOCKS) - 1) // peak)] for c in counts)
    lines = [line, f"last {len(counts)} days, peak {peak}"]
    return ModuleResult("sparkline", "Sparkline", lines, counts, requires_token=True)


MODULE_HANDLERS: dict[str, Callable[[dict[str, Any], GitHubContext, GitHubClient], ModuleResult]] = {
    "identity": module_identity,
    "stats": module_stats,
    "languages": module_languages,
    "contributions": module_contributions,
    "sparkline": module_sparkline,
    "streaks": module_streaks,
    "pull_requests": module_pull_requests,
    "issues": module_issues,
    "pinned": module_pinned,
    "rate_limit": module_rate_limit,
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
    "releases": module_releases,
    "discussions": module_discussions,
    "actions_status": module_actions_status,
    "repo_health": module_repo_health,
    "topics": module_topics,
    "dependencies": module_dependencies,
    "security_advisories": module_security_advisories,
    "packages": module_packages,
    "contribution_breakdown": module_contribution_breakdown,
    "commit_cadence": module_commit_cadence,
    "maintainer_activity": module_maintainer_activity,
}
