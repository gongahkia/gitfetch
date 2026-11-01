from __future__ import annotations

import time
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from dataclasses import field as dataclass_field
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests

from gitfetch.github_api import GitHubAPIError, GitHubClient, GitHubContext, format_relative_days
from gitfetch.semantics import (
    Availability,
    LanguageData,
    Measurement,
    RepositoryCoverage,
    aggregate,
    metric_text,
    number,
    profile_measurements,
)

HEATMAP_BLOCKS = [" ", "░", "▒", "▓", "█"]
SPARKLINE_BLOCKS = [" ", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
GRAPHQL_MODULES = frozenset({
    "contributions", "sparkline", "streaks", "pull_requests", "issues",
    "pinned", "showcase", "sponsors", "contribution_breakdown", "commit_cadence",
})


@dataclass
class ModuleResult:
    name: str
    title: str
    lines: list[str]
    data: Any
    hidden: bool = False
    requires_token: bool = False
    measurements: dict[str, Measurement] = dataclass_field(default_factory=dict)


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
        pushed_at = repo.get("pushed_at") or repo.get("updated_at")
        if pushed_at and (latest_repo_activity is None or pushed_at > latest_repo_activity):
            latest_repo_activity = pushed_at
    latest_public_event = context.events[0]["created_at"] if context.events else None
    lines = []
    if age_hours is not None:
        lines.append(f"{age_hours} hours since joining {provider_title}")
    else:
        lines.append(f"join date unavailable on {provider_title}")
    provider = getattr(client, "provider_name", "github")
    measurements = profile_measurements(user, provider)
    public_count = measurements["public_repos"]
    lines.append(f"{metric_text(public_count.value)} public repos")
    coverage = getattr(context, "repository_coverage", None)
    if public_count.value is None and isinstance(coverage, RepositoryCoverage):
        lines.append(f"{coverage.public} public repos fetched; {coverage.retained} repos selected")
    for field, label in (("public_gists", "public gists"), ("followers", "followers"), ("following", "following")):
        value = measurements[field].value
        if value is not None:
            lines.append(f"{value} {label}")
        else:
            lines.append(f"{label}: {measurements[field].availability}")
    if latest_public_event:
        relative = format_relative_days(latest_public_event)
        if relative:
            scope_label = "public" if provider == "github" else "visible"
            lines.append(f"last {scope_label} activity: {relative}")
    elif latest_repo_activity:
        relative = format_relative_days(latest_repo_activity)
        if relative:
            lines.append(f"last repo activity: {relative}")
    if user.get("updated_at"):
        relative = format_relative_days(user["updated_at"])
        if relative:
            lines.append(f"profile updated: {relative}")
    if context.viewer_mode:
        private_count = sum(1 for repo in context.repos if repo.get("private"))
        if private_count:
            lines.append(f"{private_count} private repos visible in viewer mode")
    return ModuleResult("stats", "Stats", lines, {"user": user, "viewer_mode": context.viewer_mode},
                        measurements=measurements)


def module_languages(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    settings = config["modules"]["languages"]
    limit = int(settings.get("limit", 5))
    workers = max(1, int(settings.get("workers", 4)))
    max_repos = int(settings.get("max_repos", 40))
    provider = getattr(client, "provider_name", "github")
    unit = getattr(client, "language_breakdown_unit", "bytes")
    # GitLab percentages describe individual projects. Count repositories where
    # a language was detected, preserving fractional percentages in repo mode.
    prevalence = unit == "percent"
    count_unit = "repositories" if prevalence or unit == "repositories" else "bytes"
    all_urls = [repo["languages_url"] for repo in context.repos if repo.get("languages_url")]
    urls = all_urls if max_repos == 0 else all_urls[:max_repos]
    totals: dict[str, int | float] = {}
    failures: list[Measurement] = []
    successful = 0
    invalid = 0

    def collect(url: str) -> dict[str, int | float]:
        try:
            return client.get_languages(url)
        except (GitHubAPIError, requests.RequestException, ValueError, TypeError) as exc:
            auth = isinstance(exc, GitHubAPIError) and exc.status_code in {401, 403} and not exc.rate_limited
            return LanguageData({}, Measurement(availability="auth_required" if auth else "unavailable", reason=str(exc)))

    def add_payload(payload: dict[str, int | float]) -> None:
        nonlocal successful, invalid
        if isinstance(payload, LanguageData) and payload.measurement.availability != "available":
            failures.append(payload.measurement)
            return
        successful += 1
        for language, value in payload.items():
            measured = number(value)
            if measured is None or (unit != "percent" and int(measured) != measured):
                invalid += 1
                continue
            if prevalence:
                if measured > 0:
                    totals[language] = totals.get(language, 0) + 1
            else:
                totals[language] = totals.get(language, 0) + int(measured)

    if workers == 1 or len(urls) <= 1:
        for url in urls:
            add_payload(collect(url))
    else:
        with ThreadPoolExecutor(max_workers=min(workers, len(urls))) as executor:
            futures = [executor.submit(collect, url) for url in urls]
            for future in as_completed(futures):
                add_payload(future.result())
    ranked_all = sorted(totals.items(), key=lambda item: (-item[1], item[0].casefold(), item[0]))
    denominator = successful if count_unit == "repositories" else sum(totals.values())
    sampled = len(urls) < len(all_urls)
    missing = len(context.repos) - len(all_urls)
    partial = sampled or bool(failures) or bool(missing) or bool(invalid)
    coverage = getattr(context, "repository_coverage", None)
    user = getattr(context, "user", {})
    reported = number(user.get("public_repos")) if isinstance(user, dict) else None
    complete_profile = (not partial and isinstance(coverage, RepositoryCoverage) and not coverage.filters
                        and coverage.scope == "public owned repositories" and reported == len(context.repos))
    status: Availability = "available" if successful or not context.repos else (
        "auth_required" if failures and all(f.availability == "auth_required" for f in failures) else "unavailable")
    measurement = Measurement(
        value=sum(totals.values()) if status == "available" else None,
        provider=provider, unit=count_unit,
        scope="language prevalence in selected repositories" if prevalence else (
            "primary language of selected repositories" if unit == "repositories" else "selected repository language bytes"),
        availability=status, source="repository language endpoints" if unit != "repositories" else "repository primary-language metadata",
        coverage="partial" if partial else "complete", sample_size=successful, denominator=denominator,
        reason="; ".join(filter(None, [f"{len(failures)} failed requests" if failures else "",
                                      f"{missing} repositories without language endpoints" if missing else "",
                                      f"{invalid} invalid measurements" if invalid else ""])),
        languages=tuple(language for language, _ in ranked_all), complete_profile=complete_profile,
        eligible_repositories=len(context.repos), attempted=len(urls), failed=len(failures), missing=missing,
        sampling_policy=f"first {max_repos or 'all'} repositories in provider response order",
        language_totals=tuple(ranked_all),
    )
    metadata = {"languages": measurement}
    if not ranked_all:
        lines = [f"languages: {status}"] if status != "available" else []
        return ModuleResult("languages", "Languages", lines, {}, hidden=not bool(lines), measurements=metadata)
    ranked = ranked_all[:limit]
    if count_unit == "repositories":
        lines = [f"{language} {count} repo(s)" for language, count in ranked]
        data = [{"language": language, "repositories": count} for language, count in ranked]
        title = "Languages (Repo Prevalence)" if prevalence else "Languages (Repo Count)"
    else:
        total = sum(totals.values())
        lines = [f"{language} {int(count * 100 // total) if total else 0}%" for language, count in ranked]
        data = [{"language": language, "bytes": count} for language, count in ranked]
        title = "Languages"
    if sampled:
        lines.append(f"sampled: {len(urls)}/{len(all_urls)} repos")
    if failures or missing or invalid:
        lines.append(f"coverage: {successful}/{len(context.repos)} repos; incomplete")
    if prevalence:
        lines.append("repositories containing each language; not byte-weighted")
    return ModuleResult("languages", title, lines, data, measurements=metadata)


def _contribution_measurement(context: GitHubContext, client: GitHubClient) -> Measurement:
    metadata = getattr(context, "measurements", {})
    if isinstance(metadata, dict) and "contributions" in metadata:
        return metadata["contributions"]
    days = _flatten_contribution_days(context.graphql)
    provider = getattr(context, "provider", "github")
    if not isinstance(provider, str):
        provider = "github"
    calendar = context.graphql.get("contributionsCollection", {}).get("contributionCalendar", {})
    if not days:
        reported = number(calendar.get("totalContributions"))
        if reported is not None:
            return Measurement(reported, provider, "contributions", "provider contribution calendar",
                               source="contributionCalendar", reason="calendar dates not returned")
        status: Availability = "auth_required" if provider == "github" and not getattr(client, "token", "") else "unavailable"
        return Measurement(provider=provider, unit="contributions", scope="provider contribution calendar",
                           availability=status, reason="calendar not returned")
    start, end = days[0]["date"], days[-1]["date"]
    continuous = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).days + 1 == len(days)
    reported = number(calendar.get("totalContributions"))
    return Measurement(value=reported if reported is not None else sum(d["contributionCount"] for d in days),
                       provider=provider, unit="contributions",
                       scope="provider contribution calendar", source="GraphQL contributionCalendar",
                       coverage="complete" if continuous else "partial", sample_size=len(days), start=start, end=end)


def _coverage_label(measurement: Measurement) -> str:
    interval = f"{measurement.start} to {measurement.end}" if measurement.start else "unknown interval"
    return f"coverage: {interval}; {measurement.coverage} (UTC)"


def _window_measurement(days: list[dict[str, Any]], measurement: Measurement) -> Measurement:
    if not days:
        return replace(measurement, value=None, sample_size=0, start=None, end=None, availability="unavailable")
    span = (datetime.fromisoformat(days[-1]["date"]) - datetime.fromisoformat(days[0]["date"])).days + 1
    return replace(measurement, value=sum(day["contributionCount"] for day in days),
                   sample_size=len(days), start=days[0]["date"], end=days[-1]["date"],
                   coverage=measurement.coverage if span == len(days) else "partial")


def _recent_days(context: GitHubContext, window: int) -> list[dict[str, Any]]:
    days = _flatten_contribution_days(context.graphql)
    if not days:
        return []
    start = datetime.fromisoformat(days[-1]["date"]) - timedelta(days=window - 1)
    return [day for day in days if datetime.fromisoformat(day["date"]) >= start]


def module_contributions(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    measurement = _contribution_measurement(context, client)
    metadata = {"contributions": measurement}
    observed = _flatten_contribution_days(context.graphql)
    if not observed:
        line = ("no activity records returned; coverage unknown" if measurement.availability == "available"
                else f"contributions: {measurement.availability}")
        return ModuleResult("contributions", "Contributions", [line], [],
                            requires_token=measurement.provider == "github", measurements=metadata)
    num_weeks = config["display"]["heatmap_weeks"]
    # Preserve real calendar spacing even when the provider omits entire weeks.
    by_week: dict[date, list[dict[str, Any]]] = {}
    for day in observed:
        date = datetime.fromisoformat(day["date"])
        sunday = (date - timedelta(days=(date.weekday() + 1) % 7)).date()
        by_week.setdefault(sunday, []).append(day)
    last = max(by_week)
    recent = [{"contributionDays": by_week.get(last - timedelta(weeks=offset), [])}
              for offset in reversed(range(num_weeks))]
    # Avoid adding leading empty weeks beyond the actual observed interval.
    while recent and not recent[0]["contributionDays"]:
        recent.pop(0)
    recent_days = sorted((day for week in recent for day in week["contributionDays"]), key=lambda day: day["date"])
    measurement = _window_measurement(recent_days, measurement)
    metadata["contributions"] = measurement
    max_count = max((day["contributionCount"] for week in recent for day in week["contributionDays"]), default=0) or 1
    lines: list[str] = []
    for day_idx in range(7):
        row = ""
        for week in recent:
            days = {(datetime.fromisoformat(day["date"]).weekday() + 1) % 7: day
                    for day in week["contributionDays"]}
            selected_day = days.get(day_idx)
            count = selected_day["contributionCount"] if selected_day else 0
            level = min(4, max(1, count * 4 // max_count)) if count else 0
            row += HEATMAP_BLOCKS[level]
        lines.append(row)
    lines.append(_coverage_label(measurement))
    return ModuleResult("contributions", "Contributions", lines, recent,
                        requires_token=measurement.provider == "github", measurements=metadata)


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
        star_text = f"{stars} stars" if stars is not None else "stars unavailable"
        lines.append(f"{name} ({language}, {star_text})")
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
        relative = format_relative_days(event.get("created_at"))
        line = f"{event.get('type')}: {repo_name}" + (f" ({relative})" if relative else "")
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
        [repo for repo in context.repos if number(repo.get("stargazers_count")) is not None],
        key=lambda repo: (-repo["stargazers_count"], str(repo.get("full_name") or repo.get("name") or "").casefold()),
    )[:limit]
    lines, data = _repo_lines(repos, limit)
    partial = any(number(repo.get("stargazers_count")) is None for repo in context.repos)
    return ModuleResult("top_repos", "Top Repos (Known Stars)" if partial else "Top Repos", lines, data,
                        hidden=not bool(lines))


def _split_full_name(repo: dict[str, Any]) -> tuple[str, str] | None:
    full_name = repo.get("full_name")
    if isinstance(full_name, str) and "/" in full_name:
        owner, name = full_name.split("/", 1)
        return owner, name
    owner_value = (repo.get("owner") or {}).get("login")
    name_value = repo.get("name")
    if isinstance(owner_value, str) and isinstance(name_value, str) and owner_value and name_value:
        return owner_value, name_value
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
        f"commits: {metric_text(contrib.get('totalCommitContributions'))}",
        f"issues: {metric_text(contrib.get('totalIssueContributions'))}",
        f"pull requests: {metric_text(contrib.get('totalPullRequestContributions'))}",
        f"reviews: {metric_text(contrib.get('totalPullRequestReviewContributions'))}",
    ]
    calendar = contrib.get("contributionCalendar") or {}
    if calendar.get("totalContributions") is not None:
        lines.append(f"calendar total: {calendar.get('totalContributions', 0)}")
    data = {
        "commits": contrib.get("totalCommitContributions"),
        "issues": contrib.get("totalIssueContributions"),
        "pull_requests": contrib.get("totalPullRequestContributions"),
        "reviews": contrib.get("totalPullRequestReviewContributions"),
        "calendar_total": calendar.get("totalContributions"),
    }
    return ModuleResult("contribution_breakdown", "Contribution Breakdown", lines, data, requires_token=True)


def module_commit_cadence(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    window = int(config["modules"]["commit_cadence"].get("days", 30))
    days = _flatten_contribution_days(context.graphql)
    if days:
        recent = _recent_days(context, window)
        active_days = sum(1 for day in recent if day.get("contributionCount", 0) > 0)
        total = sum(day.get("contributionCount", 0) for day in recent)
        peak = max((day.get("contributionCount", 0) for day in recent), default=0)
        lines = [
            f"{len(recent)} observed days: {total} contributions",
            f"active days: {active_days}",
            f"peak day: {peak}",
        ]
        measurement = _window_measurement(recent, _contribution_measurement(context, client))
        lines.append(_coverage_label(measurement))
        return ModuleResult("commit_cadence", "Commit Cadence", lines, {"days": recent, "total": total, "active_days": active_days},
                            measurements={"contributions": measurement})

    push_events = [event for event in context.events if event.get("type") == "PushEvent"]
    commit_count = (sum(len(event["payload"]["commits"]) for event in push_events)
                    if all(isinstance((event.get("payload") or {}).get("commits"), list) for event in push_events) else None)
    lines = [
        f"push events shown: {len(push_events)}",
        f"commits in {'public' if getattr(client, 'provider_name', 'github') == 'github' else 'visible'} events: {metric_text(commit_count)}",
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
    known_dates = 0
    open_issues = aggregate(repos, "open_issues_count")
    stars = aggregate(repos, "stargazers_count")
    forks = aggregate(repos, "forks_count")
    for repo in repos:
        pushed = _parse_github_timestamp(repo.get("pushed_at"))
        if pushed:
            known_dates += 1
        if pushed and (now - pushed).days <= 30:
            recent_pushes += 1
        if pushed and (now - pushed).days > 365:
            stale += 1
    recent_value = recent_pushes if known_dates else None
    stale_value = stale if known_dates else None
    lines = [
        f"pushed in 30d (known dates): {metric_text(recent_value)}/{known_dates}",
        f"stale >365d (known push dates): {metric_text(stale_value)}",
        f"open issues in selected repos: {metric_text(open_issues)}",
        f"stars/forks in selected repos: {metric_text(stars)}/{metric_text(forks)}",
    ]
    data = {
        "recent_pushes_30_days": recent_value,
        "stale_repos_over_365_days": stale_value,
        "open_issues": open_issues,
        "stars": stars,
        "forks": forks,
    }
    return ModuleResult("maintainer_activity", "Maintainer Activity", lines, data)


def _flatten_contribution_days(graphql: dict[str, Any]) -> list[dict[str, Any]]:
    weeks = graphql.get("contributionsCollection", {}).get("contributionCalendar", {}).get("weeks", [])
    days: dict[str, dict[str, Any]] = {}
    for week in weeks:
        for day in week.get("contributionDays", []):
            try:
                parsed = datetime.strptime(day["date"], "%Y-%m-%d")
            except (KeyError, TypeError, ValueError):
                continue
            count = number(day.get("contributionCount"))
            if count is not None and isinstance(count, int) and parsed.date().isoformat() == day["date"]:
                days[day["date"]] = day
    return [days[key] for key in sorted(days)]


def module_streaks(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    days = _flatten_contribution_days(context.graphql)
    measurement = _contribution_measurement(context, client)
    if not days:
        return ModuleResult("streaks", "Streaks", [f"streaks: {measurement.availability if measurement.availability != 'available' else 'unavailable (coverage unknown)'}"],
                            {}, requires_token=measurement.provider == "github", measurements={"contributions": measurement})
    today = datetime.now(timezone.utc).date()
    longest = run = 0
    previous = None
    counts = {}
    for day in days:
        date = datetime.fromisoformat(day["date"]).date()
        if date > today:
            continue
        count = day["contributionCount"]
        counts[date] = count
        if previous is None or date != previous + timedelta(days=1):
            run = 0
        run = run + 1 if count > 0 else 0
        longest = max(longest, run)
        previous = date
    current: int | None = None
    cursor = today
    # Allow today to be unfinished only when its zero is actually measured.
    if counts.get(cursor) == 0:
        cursor -= timedelta(days=1)
    if cursor in counts:
        current = 0
        while counts.get(cursor, 0) > 0:
            current += 1
            cursor -= timedelta(days=1)
    total = sum(counts.values())
    contrib = context.graphql.get("contributionsCollection", {})
    lines = [f"current observed: {metric_text(current)} day(s)", f"longest observed: {longest} day(s)",
             f"window total: {total}", _coverage_label(measurement)]
    for field, label in (("totalCommitContributions", "commits"), ("totalPullRequestReviewContributions", "reviews")):
        if number(contrib.get(field)) is not None:
            lines.append(f"{label}: {contrib[field]}")
    data = {"current": current, "longest": longest, "total": total}
    return ModuleResult("streaks", "Streaks", lines, data, requires_token=measurement.provider == "github", measurements={
        "contributions": measurement,
        "current": replace(measurement, value=current, unit="days", scope="observed current streak",
                           availability="available" if current is not None else "unavailable"),
        "longest": replace(measurement, value=longest, unit="days", scope="longest observed streak in window"),
    })


def module_pull_requests(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    graphql = context.graphql
    if not graphql:
        return ModuleResult("pull_requests", "Pull Requests", [], {}, hidden=True, requires_token=True)
    open_count = (graphql.get("openPRs") or {}).get("totalCount")
    merged_count = (graphql.get("mergedPRs") or {}).get("totalCount")
    closed_count = (graphql.get("closedPRs") or {}).get("totalCount")
    lines = [
        f"open: {metric_text(open_count)}",
        f"merged: {metric_text(merged_count)}",
        f"closed: {metric_text(closed_count)}",
    ]
    data = {"open": open_count, "merged": merged_count, "closed": closed_count}
    title = "Merge Requests" if getattr(client, "provider_name", "") == "gitlab" else "Pull Requests"
    return ModuleResult("pull_requests", title, lines, data, requires_token=True)


def module_issues(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    graphql = context.graphql
    if not graphql:
        return ModuleResult("issues", "Issues", [], {}, hidden=True, requires_token=True)
    open_count = (graphql.get("openIssues") or {}).get("totalCount")
    closed_count = (graphql.get("closedIssues") or {}).get("totalCount")
    lines = [f"open: {metric_text(open_count)}", f"closed: {metric_text(closed_count)}"]
    data = {"open": open_count, "closed": closed_count}
    return ModuleResult("issues", "Issues", lines, data, requires_token=True)


def module_rate_limit(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    payload = client.get_rate_limit()
    core = (payload.get("resources") or {}).get("core") or payload.get("rate") or {}
    if not core:
        return ModuleResult("rate_limit", "Rate Limit", [], {}, hidden=True)
    remaining = core.get("remaining")
    limit = core.get("limit")
    reset = core.get("reset")
    lines = [f"core: {metric_text(remaining)}/{metric_text(limit)}"]
    if reset:
        secs = max(0, int(reset) - int(time.time()))
        lines.append(f"resets in: {secs // 60}m {secs % 60}s")
    graphql_bucket = (payload.get("resources") or {}).get("graphql") or {}
    if graphql_bucket:
        lines.append(f"graphql: {metric_text(graphql_bucket.get('remaining'))}/{metric_text(graphql_bucket.get('limit'))}")
    return ModuleResult("rate_limit", "Rate Limit", lines, payload)


def module_pinned(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    nodes = (context.graphql.get("pinnedItems") or {}).get("nodes") or []
    limit = config["modules"]["pinned"].get("limit", 6)
    lines: list[str] = []
    data: list[dict[str, Any]] = []
    for node in nodes[:limit]:
        if node.get("__typename") == "Repository":
            language = (node.get("primaryLanguage") or {}).get("name") or "n/a"
            stars = node.get("stargazerCount")
            lines.append(f"{node.get('nameWithOwner')} ({language}, ★{metric_text(stars)})")
        else:
            lines.append(f"gist: {node.get('name') or node.get('description') or 'untitled'}")
        data.append(node)
    return ModuleResult("pinned", "Pinned", lines, data, hidden=not bool(lines), requires_token=True)


def module_sparkline(config: dict[str, Any], context: GitHubContext, client: GitHubClient) -> ModuleResult:
    days = _flatten_contribution_days(context.graphql)
    if not days:
        measurement = _contribution_measurement(context, client)
        return ModuleResult("sparkline", "Sparkline", [f"sparkline: {measurement.availability if measurement.availability != 'available' else 'unavailable (coverage unknown)'}"],
                            {}, requires_token=measurement.provider == "github", measurements={"contributions": measurement})
    window = int(config["modules"]["sparkline"].get("days", 30))
    recent = _recent_days(context, window)
    counts = [d.get("contributionCount", 0) for d in recent]
    peak = max(counts)
    dated = {datetime.fromisoformat(day["date"]).date(): day["contributionCount"] for day in recent}
    first, last = min(dated), max(dated)
    line = ""
    for offset in range((last - first).days + 1):
        count = dated.get(first + timedelta(days=offset))
        line += " " if count is None else SPARKLINE_BLOCKS[min(8, count * 8 // (peak or 1))]
    measurement = _window_measurement(recent, _contribution_measurement(context, client))
    lines = [line, f"{len(counts)} observed days, peak {peak}"]
    if measurement.coverage != "complete":
        lines[1] += f"; {measurement.coverage} coverage (gaps unknown)"
    return ModuleResult("sparkline", "Sparkline", lines, counts, requires_token=measurement.provider == "github",
                        measurements={"contributions": measurement})


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
