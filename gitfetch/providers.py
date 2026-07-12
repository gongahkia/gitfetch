from __future__ import annotations

import base64
import hashlib
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import requests

from gitfetch.cache import CacheStore
from gitfetch.config import ConfigError, MODULE_METADATA, SUPPORTED_PROVIDERS
from gitfetch.github_api import GitHubAPIError, GitHubClient, GitHubContext, configure_http_retries, filter_repos


class BaseProviderClient:
    provider_name = "provider"
    provider_title = "Provider"
    supported_modules: set[str] = {"identity", "stats"}
    token_required_modules: set[str] = set()
    language_breakdown_unit = "bytes"
    unsupported_reasons: dict[str, str] = {}

    def __init__(self, token: str, cache: CacheStore, offline: bool, base_url: str) -> None:
        self.token = token
        self.cache = cache
        self.offline = offline
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        configure_http_retries(self.session)
        self.session.headers.update({"User-Agent": "gitfetch/2.0.0"})

    def supports_module(self, name: str) -> bool:
        if name not in MODULE_METADATA:
            return True
        return name in self.supported_modules

    def unsupported_reason(self, name: str) -> str:
        return self.unsupported_reasons.get(name, "no equivalent public API is configured")

    def module_token_required(self, name: str, default: bool) -> bool:
        return name in self.token_required_modules

    def _cache_key(self, prefix: str, *parts: str) -> str:
        auth_scope = f"token:{hashlib.sha256(self.token.encode('utf-8')).hexdigest()[:16]}" if self.token else "anon"
        suffix = "|".join(str(part) for part in parts)
        return f"{self.provider_name}|{self.base_url}|{prefix}|{auth_scope}|{suffix}"

    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{self.base_url}{path}"

    def _message(self, response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text[:120]
        if isinstance(payload, dict):
            message = payload.get("message") or payload.get("error") or payload.get("error_description")
            if message:
                return str(message)
        return response.text[:120]

    def _get_json(self, path: str, params: dict[str, Any] | None = None, cache_key: str | None = None) -> Any:
        if cache_key:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached
        if self.offline:
            raise GitHubAPIError(f"offline mode: {path} not available in cache")
        response = self.session.get(self._url(path), params=params, timeout=20)
        if response.status_code == 404:
            raise GitHubAPIError(f"{self.provider_title} user or resource not found")
        if response.status_code == 401:
            raise GitHubAPIError(f"{self.provider_title} authentication failed")
        if response.status_code == 403:
            raise GitHubAPIError(f"{self.provider_title} rejected request: {self._message(response)}")
        if not response.ok:
            raise GitHubAPIError(f"{self.provider_title} API returned HTTP {response.status_code}")
        payload = response.json()
        if cache_key:
            self.cache.set(cache_key, payload)
        return payload

    def _get_json_optional(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        cache_key: str | None = None,
        default: Any = None,
    ) -> Any:
        try:
            return self._get_json(path, params=params, cache_key=cache_key)
        except (GitHubAPIError, requests.RequestException, ValueError):
            return default

    def _get_text_optional(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        cache_key: str | None = None,
    ) -> str | None:
        if cache_key:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached
        if self.offline:
            return None
        try:
            response = self.session.get(self._url(path), params=params, timeout=20)
        except requests.RequestException:
            return None
        if not response.ok:
            return None
        if cache_key:
            self.cache.set(cache_key, response.text)
        return response.text


class GitLabClient(BaseProviderClient):
    provider_name = "gitlab"
    provider_title = "GitLab"
    supported_modules = {
        "identity",
        "stats",
        "languages",
        "social_accounts",
        "organizations",
        "starred",
        "gists",
        "recent_activity",
        "profile_readme",
        "top_repos",
        "releases",
        "actions_status",
        "repo_health",
        "topics",
        "dependencies",
        "security_advisories",
        "packages",
        "maintainer_activity",
    }
    token_required_modules = {"dependencies", "security_advisories"}
    unsupported_reasons = {
        "contributions": "GitLab does not expose a stable public user contribution-calendar API",
        "sparkline": "GitLab does not expose a stable public user contribution-calendar API",
        "streaks": "GitLab does not expose a stable public user contribution-calendar API",
        "pull_requests": "GitLab profile-wide merge-request totals are not equivalent to the profile contribution model",
        "issues": "GitLab profile-wide issue totals are not equivalent to the profile contribution model",
        "contribution_breakdown": "GitLab does not expose a stable public user contribution breakdown API",
        "commit_cadence": "GitLab does not expose a stable public user contribution-calendar API",
        "watched": "GitLab has no matching public watched-repositories API",
        "rate_limit": "GitLab does not expose a portable public rate-limit endpoint here",
        "pinned": "GitLab does not expose GitHub-style pinned profile items",
        "showcase": "GitLab has no GitHub-style profile showcase API",
        "sponsors": "GitLab has no matching sponsors listing API",
        "discussions": "GitLab discussions are not exposed as a profile-level public metric",
    }

    def __init__(self, token: str, cache: CacheStore, offline: bool, base_url: str) -> None:
        super().__init__(token, cache, offline, base_url)
        self.session.headers.update({"Accept": "application/json"})
        if token:
            self.session.headers["PRIVATE-TOKEN"] = token

    def _paginate(self, path: str, params: dict[str, Any] | None = None, cache_key: str | None = None) -> list[dict[str, Any]]:
        if cache_key:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached
        if self.offline:
            raise GitHubAPIError(f"offline mode: {path} not available in cache")
        merged = dict(params or {})
        merged.setdefault("per_page", 100)
        page = 1
        items: list[dict[str, Any]] = []
        while True:
            merged["page"] = page
            response = self.session.get(self._url(path), params=merged, timeout=20)
            if response.status_code == 404:
                raise GitHubAPIError(f"{self.provider_title} user or resource not found")
            if response.status_code in {401, 403}:
                raise GitHubAPIError(f"{self.provider_title} rejected request: {self._message(response)}")
            if not response.ok:
                raise GitHubAPIError(f"{self.provider_title} API returned HTTP {response.status_code}")
            payload = response.json()
            if isinstance(payload, list):
                items.extend(payload)
            next_page = response.headers.get("X-Next-Page")
            if not next_page:
                break
            page = int(next_page)
        if cache_key:
            self.cache.set(cache_key, items)
        return items

    def _count_list(self, path: str, params: dict[str, Any]) -> int:
        merged = dict(params)
        merged["per_page"] = 1
        if self.offline:
            return 0
        try:
            response = self.session.get(self._url(path), params=merged, timeout=20)
        except requests.RequestException:
            return 0
        if not response.ok:
            return 0
        total = response.headers.get("X-Total")
        if total and total.isdigit():
            return int(total)
        try:
            payload = response.json()
        except ValueError:
            return 0
        return len(payload) if isinstance(payload, list) else 0

    def _resolve_user(self, username: str) -> dict[str, Any]:
        users = self._get_json(
            "/users",
            params={"username": username},
            cache_key=self._cache_key("user_lookup", username),
        )
        if not isinstance(users, list) or not users:
            raise GitHubAPIError(f"{self.provider_title} user or resource not found")
        return users[0]

    def _resolve_group(self, namespace: str) -> dict[str, Any]:
        payload = self._get_json(
            f"/groups/{quote(namespace, safe='')}",
            cache_key=self._cache_key("group_lookup", namespace),
        )
        if not isinstance(payload, dict) or not payload.get("id"):
            raise GitHubAPIError(f"{self.provider_title} user or resource not found")
        return payload

    def get_context(self, username: str, mode: str, repo_filters: dict[str, Any]) -> GitHubContext:
        try:
            raw_user = self._resolve_user(username)
        except GitHubAPIError:
            # A GitLab namespace can be a group rather than a user.  Groups do
            # not have a user activity/contribution API, but their public
            # projects are still a useful profile target.
            user = self._normalize_group(self._resolve_group(username))
            is_group = True
        else:
            user = self._normalize_user(raw_user)
            is_group = False
        repos = filter_repos(self.get_repos(username, viewer_mode=False), repo_filters)
        user["public_repos"] = len(repos)
        events = [] if is_group else self.get_events(str(raw_user["id"]), limit=10)
        # GitLab's public GraphQL API has no stable equivalent of GitHub's
        # profile contribution calendar. Do not manufacture one from events.
        graphql = {}
        return GitHubContext(
            target_user=username,
            user=user,
            repos=repos,
            events=events,
            viewer_mode=False,
            authenticated_login=None,
            graphql=graphql,
        )

    def get_user(self, username: str) -> dict[str, Any]:
        try:
            return self._normalize_user(self._resolve_user(username))
        except GitHubAPIError:
            return self._normalize_group(self._resolve_group(username))

    def get_repos(self, username: str, viewer_mode: bool = False) -> list[dict[str, Any]]:
        try:
            user = self._resolve_user(username)
        except GitHubAPIError:
            group = self._resolve_group(username)
            path = f"/groups/{quote(str(group['id']), safe='')}/projects"
        else:
            path = f"/users/{user['id']}/projects"
        projects = self._paginate(
            path,
            params={"order_by": "updated_at", "sort": "desc", "simple": "false"},
            cache_key=self._cache_key("repos", username),
        )
        return [self._normalize_project(project) for project in projects]

    def get_languages(self, languages_url: str) -> dict[str, int]:
        if not languages_url.startswith("gitlab://project/"):
            return {}
        project_id = languages_url.rsplit("/", 1)[-1]
        payload = self._get_json_optional(
            f"/projects/{quote(project_id, safe='')}/languages",
            cache_key=self._cache_key("languages", project_id),
            default={},
        )
        return payload if isinstance(payload, dict) else {}

    def get_events(self, username: str, limit: int = 10) -> list[dict[str, Any]]:
        user_id = username if str(username).isdigit() else str(self._resolve_user(username)["id"])
        events = self._get_json(
            f"/users/{user_id}/events",
            params={"per_page": min(max(limit, 1), 100)},
            cache_key=self._cache_key("events", user_id, str(limit)),
        )
        return [self._normalize_event(event) for event in events[:limit]] if isinstance(events, list) else []

    def get_social_accounts(self, username: str) -> list[dict[str, Any]]:
        user = self.get_user(username)
        rows = [{"provider": "gitlab", "url": user.get("html_url"), "display_name": user.get("login")}]
        if user.get("blog"):
            rows.append({"provider": "website", "url": user["blog"], "display_name": user["blog"]})
        return [row for row in rows if row.get("url")]

    def get_organizations(self, username: str) -> list[dict[str, Any]]:
        user = self._resolve_user(username)
        groups = self._get_json_optional(
            f"/users/{user['id']}/groups",
            cache_key=self._cache_key("groups", username),
            default=[],
        )
        return [self._normalize_group(group) for group in groups] if isinstance(groups, list) else []

    def get_starred(self, username: str, limit: int) -> list[dict[str, Any]]:
        user = self._resolve_user(username)
        projects = self._paginate(
            f"/users/{user['id']}/starred_projects",
            params={"order_by": "updated_at", "sort": "desc"},
            cache_key=self._cache_key("starred", username, str(limit)),
        )
        return [self._normalize_project(project) for project in projects[:limit]]

    def get_subscriptions(self, username: str, limit: int) -> list[dict[str, Any]]:
        return []

    def get_gists(self, username: str, limit: int) -> list[dict[str, Any]]:
        user = self._resolve_user(username)
        snippets = self._paginate(
            f"/users/{user['id']}/snippets",
            cache_key=self._cache_key("snippets", username, str(limit)),
        )
        return [
            {
                "id": snippet.get("id"),
                "description": snippet.get("title") or snippet.get("file_name") or "untitled snippet",
                "html_url": snippet.get("web_url"),
            }
            for snippet in snippets[:limit]
        ]

    def get_profile_readme(self, username: str) -> str | None:
        project = self._get_project_optional(username, username)
        if not project:
            return None
        ref = project.get("default_branch") or "main"
        project_id = quote(str(project.get("id")), safe="")
        for name in ("README.md", "readme.md"):
            path = quote(name, safe="")
            if self.offline:
                return None
            response = self.session.get(
                self._url(f"/projects/{project_id}/repository/files/{path}/raw"),
                params={"ref": ref},
                timeout=20,
            )
            if response.ok:
                return response.text
        return None

    def get_repo(self, owner: str, name: str) -> dict[str, Any]:
        project = self._get_json(f"/projects/{quote(owner + '/' + name, safe='')}", cache_key=self._cache_key("repo", owner, name))
        return self._normalize_project(project)

    def get_repo_languages(self, owner: str, name: str) -> dict[str, int]:
        repo = self.get_repo(owner, name)
        return self.get_languages(repo.get("languages_url", ""))

    def get_repo_contributors(self, owner: str, name: str, limit: int = 10) -> list[dict[str, Any]]:
        project = self.get_repo(owner, name)
        contributors = self._get_json_optional(
            f"/projects/{quote(str(project['id']), safe='')}/repository/contributors",
            cache_key=self._cache_key("repo_contributors", owner, name),
            default=[],
        )
        if not isinstance(contributors, list):
            return []
        return [{"login": c.get("name") or c.get("email") or "unknown", "contributions": c.get("commits", 0)} for c in contributors[:limit]]

    def get_repo_commits(self, owner: str, name: str, limit: int = 5) -> list[dict[str, Any]]:
        project = self.get_repo(owner, name)
        commits = self._get_json_optional(
            f"/projects/{quote(str(project['id']), safe='')}/repository/commits",
            params={"per_page": limit},
            cache_key=self._cache_key("repo_commits", owner, name, str(limit)),
            default=[],
        )
        if not isinstance(commits, list):
            return []
        return [self._normalize_commit(commit) for commit in commits[:limit]]

    def get_repo_releases(self, owner: str, name: str, limit: int = 3) -> list[dict[str, Any]]:
        project = self.get_repo(owner, name)
        payload = self._get_json_optional(
            f"/projects/{quote(str(project['id']), safe='')}/releases",
            params={"per_page": limit},
            cache_key=self._cache_key("repo_releases", owner, name, str(limit)),
            default=[],
        )
        return payload[:limit] if isinstance(payload, list) else []

    def get_repo_workflow_runs(self, owner: str, name: str, limit: int = 1) -> list[dict[str, Any]]:
        project = self.get_repo(owner, name)
        pipelines = self._get_json_optional(
            f"/projects/{quote(str(project['id']), safe='')}/pipelines",
            params={"per_page": limit},
            cache_key=self._cache_key("repo_pipelines", owner, name, str(limit)),
            default=[],
        )
        if not isinstance(pipelines, list):
            return []
        return [
            {
                "name": f"pipeline #{pipeline.get('id')}",
                "status": pipeline.get("status"),
                "conclusion": pipeline.get("status"),
                "html_url": pipeline.get("web_url"),
            }
            for pipeline in pipelines[:limit]
        ]

    def get_repo_discussions_count(self, owner: str, name: str) -> int | None:
        return None

    def get_repo_sbom(self, owner: str, name: str) -> dict[str, Any]:
        project = self.get_repo(owner, name)
        dependencies = self._get_json_optional(
            f"/projects/{quote(str(project['id']), safe='')}/dependencies",
            params={"per_page": 100},
            cache_key=self._cache_key("repo_dependencies", owner, name),
            default=[],
        )
        if not isinstance(dependencies, list):
            return {}
        packages = []
        for dependency in dependencies:
            packages.append(
                {
                    "name": dependency.get("name") or dependency.get("package_name"),
                    "version": dependency.get("version"),
                    "package_manager": dependency.get("package_manager"),
                    "licenses": dependency.get("licenses") or [],
                    "vulnerabilities": dependency.get("vulnerabilities") or [],
                }
            )
        return {"sbom": {"packages": [package for package in packages if package.get("name")]}}

    def get_repo_security_advisories(self, owner: str, name: str, limit: int = 5) -> list[dict[str, Any]]:
        project = self.get_repo(owner, name)
        findings = self._get_json_optional(
            f"/projects/{quote(str(project['id']), safe='')}/vulnerability_findings",
            params={"per_page": limit, "scope": "all"},
            cache_key=self._cache_key("repo_vulnerability_findings", owner, name, str(limit)),
            default=[],
        )
        if not isinstance(findings, list):
            return []
        advisories = []
        for finding in findings[:limit]:
            advisories.append(
                {
                    **finding,
                    "summary": finding.get("name") or finding.get("title") or "vulnerability finding",
                    "severity": finding.get("severity") or "unknown",
                    "html_url": finding.get("blob_path") or finding.get("create_vulnerability_feedback_issue_path"),
                }
            )
        return advisories

    def get_user_packages(self, username: str, package_type: str, limit: int = 5) -> list[dict[str, Any]]:
        if package_type == "container":
            return []
        group = self._get_json_optional(
            f"/groups/{quote(username, safe='')}",
            cache_key=self._cache_key("package_group_lookup", username),
            default=None,
        )
        params = {"per_page": limit, "sort": "desc"}
        if package_type:
            params["package_type"] = package_type
        if isinstance(group, dict):
            packages = self._get_json_optional(
                f"/groups/{quote(str(group['id']), safe='')}/packages",
                params=params,
                cache_key=self._cache_key("group_packages", username, package_type, str(limit)),
                default=[],
            )
            return packages[:limit] if isinstance(packages, list) else []

        rows: list[dict[str, Any]] = []
        for repo in self.get_repos(username)[:8]:
            project_id = repo.get("id")
            if not project_id:
                continue
            packages = self._get_json_optional(
                f"/projects/{quote(str(project_id), safe='')}/packages",
                params=params,
                cache_key=self._cache_key("project_packages", str(project_id), package_type, str(limit)),
                default=[],
            )
            if isinstance(packages, list):
                for package in packages:
                    rows.append({**package, "project_path": repo.get("full_name")})
                    if len(rows) >= limit:
                        return rows
        return rows

    def get_org(self, name: str) -> dict[str, Any]:
        group = self._get_json(f"/groups/{quote(name, safe='')}", cache_key=self._cache_key("org", name))
        return self._normalize_group(group)

    def get_org_members(self, name: str, limit: int = 10) -> list[dict[str, Any]]:
        org = self.get_org(name)
        members = self._get_json_optional(
            f"/groups/{quote(str(org['id']), safe='')}/members",
            params={"per_page": limit},
            cache_key=self._cache_key("org_members", name, str(limit)),
            default=[],
        )
        if not isinstance(members, list):
            return []
        return [{"login": member.get("username") or member.get("name") or "unknown", **member} for member in members[:limit]]

    def get_org_repos(self, name: str) -> list[dict[str, Any]]:
        org = self.get_org(name)
        projects = self._paginate(
            f"/groups/{quote(str(org['id']), safe='')}/projects",
            params={"order_by": "updated_at", "sort": "desc", "include_subgroups": "false"},
            cache_key=self._cache_key("org_repos", name),
        )
        return [self._normalize_project(project) for project in projects]

    def get_rate_limit(self) -> dict[str, Any]:
        return {"rate": {"remaining": 0, "limit": 0}}

    def _graphql_like_bundle(self, user_id: int, events: list[dict[str, Any]]) -> dict[str, Any]:
        opened_mrs = self._count_list("/merge_requests", {"author_id": user_id, "state": "opened", "scope": "all"})
        merged_mrs = self._count_list("/merge_requests", {"author_id": user_id, "state": "merged", "scope": "all"})
        closed_mrs = self._count_list("/merge_requests", {"author_id": user_id, "state": "closed", "scope": "all"})
        opened_issues = self._count_list("/issues", {"author_id": user_id, "state": "opened", "scope": "all"})
        closed_issues = self._count_list("/issues", {"author_id": user_id, "state": "closed", "scope": "all"})
        days = _contribution_days_from_events(events)
        return {
            "contributionsCollection": {
                "totalCommitContributions": sum(len((event.get("payload") or {}).get("commits") or []) for event in events),
                "totalIssueContributions": opened_issues + closed_issues,
                "totalPullRequestContributions": opened_mrs + merged_mrs + closed_mrs,
                "totalPullRequestReviewContributions": 0,
                "contributionCalendar": {
                    "totalContributions": sum(day["contributionCount"] for week in days for day in week["contributionDays"]),
                    "weeks": days,
                },
            },
            "openPRs": {"totalCount": opened_mrs},
            "mergedPRs": {"totalCount": merged_mrs},
            "closedPRs": {"totalCount": closed_mrs},
            "openIssues": {"totalCount": opened_issues},
            "closedIssues": {"totalCount": closed_issues},
        }

    def _get_project_optional(self, owner: str, name: str) -> dict[str, Any] | None:
        payload = self._get_json_optional(
            f"/projects/{quote(owner + '/' + name, safe='')}",
            cache_key=self._cache_key("repo", owner, name),
            default=None,
        )
        return payload if isinstance(payload, dict) else None

    def _normalize_user(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            **raw,
            "login": raw.get("username") or raw.get("login") or str(raw.get("id", "")),
            "name": raw.get("name") or raw.get("username"),
            "bio": raw.get("bio") or raw.get("public_email") or "",
            "blog": raw.get("website_url") or raw.get("web_url") or "",
            "company": raw.get("organization") or "",
            "location": raw.get("location") or "",
            "avatar_url": raw.get("avatar_url"),
            "html_url": raw.get("web_url"),
            "created_at": raw.get("created_at"),
            "updated_at": raw.get("last_activity_on") or raw.get("created_at"),
            "followers": raw.get("followers", 0),
            "following": raw.get("following", 0),
            "public_gists": 0,
        }

    def _normalize_project(self, raw: dict[str, Any]) -> dict[str, Any]:
        namespace = raw.get("namespace") or {}
        full_name = raw.get("path_with_namespace") or raw.get("full_path") or raw.get("name")
        topics = raw.get("topics") or raw.get("tag_list") or []
        license_payload = raw.get("license") or {}
        return {
            **raw,
            "name": raw.get("path") or raw.get("name"),
            "full_name": full_name,
            "description": raw.get("description"),
            "html_url": raw.get("web_url"),
            "stargazers_count": raw.get("star_count", 0),
            "forks_count": raw.get("forks_count", 0),
            "watchers_count": raw.get("star_count", 0),
            "open_issues_count": raw.get("open_issues_count", 0),
            "size": 0,
            "language": None,
            "languages_url": f"gitlab://project/{raw.get('id')}",
            "created_at": raw.get("created_at"),
            "updated_at": raw.get("last_activity_at") or raw.get("updated_at"),
            "pushed_at": raw.get("last_activity_at") or raw.get("updated_at"),
            "archived": bool(raw.get("archived")),
            "fork": bool(raw.get("forked_from_project")),
            "is_template": False,
            "private": raw.get("visibility") != "public",
            "has_issues": raw.get("issues_enabled", True),
            "topics": topics,
            "default_branch": raw.get("default_branch") or "main",
            "license": {"spdx_id": license_payload.get("spdx_identifier") or license_payload.get("nickname") or license_payload.get("name")} if license_payload else None,
            "owner": {"login": namespace.get("path") or namespace.get("full_path") or "", "avatar_url": raw.get("avatar_url")},
        }

    def _normalize_group(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            **raw,
            "login": raw.get("path") or raw.get("full_path") or raw.get("name"),
            "name": raw.get("name") or raw.get("full_name"),
            "description": raw.get("description"),
            "blog": raw.get("web_url") or "",
            "location": "",
            "email": "",
            "avatar_url": raw.get("avatar_url"),
            "public_repos": raw.get("projects_count", 0),
            "followers": 0,
        }

    def _normalize_event(self, raw: dict[str, Any]) -> dict[str, Any]:
        action = str(raw.get("action_name") or raw.get("target_type") or "Event")
        event_type = "PushEvent" if "push" in action.lower() else action.replace(" ", "_")
        commits = [{}] * int((raw.get("push_data") or {}).get("commit_count", 0) or 0)
        return {
            **raw,
            "type": event_type,
            "repo": {"name": raw.get("project_id") or raw.get("target_title") or "unknown project"},
            "created_at": raw.get("created_at"),
            "payload": {"commits": commits},
        }

    def _normalize_commit(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            **raw,
            "sha": raw.get("id") or raw.get("short_id"),
            "commit": {
                "message": raw.get("message") or raw.get("title") or "",
                "author": {"name": raw.get("author_name") or raw.get("committer_name") or "?"},
            },
        }


class GiteaClient(BaseProviderClient):
    provider_name = "gitea"
    provider_title = "Gitea"
    supported_modules = {
        "identity",
        "stats",
        "languages",
        "contributions",
        "sparkline",
        "streaks",
        "social_accounts",
        "organizations",
        "starred",
        "watched",
        "recent_activity",
        "profile_readme",
        "top_repos",
        "releases",
        "actions_status",
        "repo_health",
        "topics",
        "packages",
        "commit_cadence",
        "maintainer_activity",
    }
    token_required_modules = {"organizations", "starred", "watched"}
    unsupported_reasons = {
        "gists": "Gitea-compatible APIs have no gist/snippet equivalent in this provider layer",
        "rate_limit": "Gitea-compatible APIs do not expose a portable public rate-limit endpoint here",
        "pinned": "Gitea-compatible APIs have no GitHub-style pinned profile items",
        "showcase": "Gitea-compatible APIs have no GitHub-style profile showcase API",
        "sponsors": "Gitea-compatible APIs have no matching sponsors listing API",
        "discussions": "Gitea-compatible APIs do not expose GitHub Discussions as a profile metric",
        "dependencies": "Gitea-compatible APIs do not expose a public SBOM summary API",
        "security_advisories": "Gitea-compatible APIs do not expose repository advisory summaries as a public profile metric",
        "pull_requests": "Gitea search results are repository-owner scoped, not profile-author totals",
        "issues": "Gitea search results are repository-owner scoped, not profile-author totals",
        "contribution_breakdown": "Gitea heatmap data does not provide an exact issue, pull-request, and review breakdown",
    }

    def __init__(self, token: str, cache: CacheStore, offline: bool, base_url: str) -> None:
        super().__init__(token, cache, offline, base_url)
        self.session.headers.update({"Accept": "application/json"})
        if token:
            self.session.headers["Authorization"] = f"token {token}"

    def _paginate(self, path: str, params: dict[str, Any] | None = None, cache_key: str | None = None) -> list[dict[str, Any]]:
        if cache_key:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached
        if self.offline:
            raise GitHubAPIError(f"offline mode: {path} not available in cache")
        merged = dict(params or {})
        merged.setdefault("limit", 50)
        page = 1
        items: list[dict[str, Any]] = []
        while True:
            merged["page"] = page
            response = self.session.get(self._url(path), params=merged, timeout=20)
            if response.status_code == 404:
                raise GitHubAPIError(f"{self.provider_title} user or resource not found")
            if response.status_code == 401:
                raise GitHubAPIError(f"{self.provider_title} authentication failed")
            if response.status_code == 403:
                raise GitHubAPIError(f"{self.provider_title} rejected request: {self._message(response)}")
            if not response.ok:
                raise GitHubAPIError(f"{self.provider_title} API returned HTTP {response.status_code}")
            payload = response.json()
            if not isinstance(payload, list) or not payload:
                break
            items.extend(payload)
            link = response.headers.get("Link", "")
            if 'rel="next"' not in link:
                break
            page += 1
        if cache_key:
            self.cache.set(cache_key, items)
        return items

    def _count_list(self, path: str, params: dict[str, Any]) -> int:
        if self.offline:
            return 0
        merged = dict(params)
        merged["limit"] = 1
        try:
            response = self.session.get(self._url(path), params=merged, timeout=20)
        except requests.RequestException:
            return 0
        if not response.ok:
            return 0
        total = response.headers.get("X-Total-Count")
        if total and total.isdigit():
            return int(total)
        try:
            payload = response.json()
        except ValueError:
            return 0
        return len(payload) if isinstance(payload, list) else 0

    def get_context(self, username: str, mode: str, repo_filters: dict[str, Any]) -> GitHubContext:
        user = self.get_user(username)
        authenticated_login = None
        viewer_mode = False
        if mode == "viewer" and self.token:
            viewer = self.get_authenticated_user()
            authenticated_login = viewer.get("login")
            if authenticated_login and authenticated_login.lower() == username.lower():
                user = viewer
                viewer_mode = True
        repos = filter_repos(self.get_repos(username, viewer_mode=viewer_mode), repo_filters)
        user["public_repos"] = len(repos)
        events = self.get_events(username, limit=10)
        heatmap = self.get_heatmap(username)
        graphql = self._graphql_like_bundle(username, heatmap)
        return GitHubContext(
            target_user=username,
            user=user,
            repos=repos,
            events=events,
            viewer_mode=viewer_mode,
            authenticated_login=authenticated_login,
            graphql=graphql,
        )

    def get_user(self, username: str) -> dict[str, Any]:
        raw = self._get_json(f"/users/{quote(username, safe='')}", cache_key=self._cache_key("user", username))
        return self._normalize_user(raw)

    def get_authenticated_user(self) -> dict[str, Any]:
        raw = self._get_json("/user", cache_key=self._cache_key("viewer", "self"))
        return self._normalize_user(raw)

    def get_repos(self, username: str, viewer_mode: bool = False) -> list[dict[str, Any]]:
        if viewer_mode:
            repos = self._paginate("/user/repos", cache_key=self._cache_key("repos", "viewer", username))
        else:
            repos = self._paginate(
                f"/users/{quote(username, safe='')}/repos",
                cache_key=self._cache_key("repos", "public", username),
            )
        return [self._normalize_repo(repo) for repo in repos]

    def get_languages(self, languages_url: str) -> dict[str, int]:
        payload = self._get_json_optional(languages_url, cache_key=self._cache_key("languages", languages_url), default={})
        return payload if isinstance(payload, dict) else {}

    def get_heatmap(self, username: str) -> list[dict[str, Any]]:
        payload = self._get_json_optional(
            f"/users/{quote(username, safe='')}/heatmap",
            cache_key=self._cache_key("heatmap", username),
            default=[],
        )
        return payload if isinstance(payload, list) else []

    def get_events(self, username: str, limit: int = 10) -> list[dict[str, Any]]:
        events = self._get_json_optional(
            f"/users/{quote(username, safe='')}/activities/feeds",
            params={"limit": min(max(limit, 1), 50)},
            cache_key=self._cache_key("events", username, str(limit)),
            default=[],
        )
        return [self._normalize_event(event) for event in events[:limit]] if isinstance(events, list) else []

    def get_social_accounts(self, username: str) -> list[dict[str, Any]]:
        user = self.get_user(username)
        rows = [{"provider": self.provider_name, "url": user.get("html_url"), "display_name": user.get("login")}]
        if user.get("blog"):
            rows.append({"provider": "website", "url": user["blog"], "display_name": user["blog"]})
        return [row for row in rows if row.get("url")]

    def get_organizations(self, username: str) -> list[dict[str, Any]]:
        orgs = self._get_json_optional(
            f"/users/{quote(username, safe='')}/orgs",
            cache_key=self._cache_key("orgs", username),
            default=[],
        )
        return [self._normalize_org(org) for org in orgs] if isinstance(orgs, list) else []

    def get_starred(self, username: str, limit: int) -> list[dict[str, Any]]:
        repos = self._paginate(
            f"/users/{quote(username, safe='')}/starred",
            params={"limit": min(max(limit, 1), 50)},
            cache_key=self._cache_key("starred", username, str(limit)),
        )
        return [self._normalize_repo(repo) for repo in repos[:limit]]

    def get_subscriptions(self, username: str, limit: int) -> list[dict[str, Any]]:
        repos = self._paginate(
            f"/users/{quote(username, safe='')}/subscriptions",
            params={"limit": min(max(limit, 1), 50)},
            cache_key=self._cache_key("subscriptions", username, str(limit)),
        )
        return [self._normalize_repo(repo) for repo in repos[:limit]]

    def get_gists(self, username: str, limit: int) -> list[dict[str, Any]]:
        return []

    def get_profile_readme(self, username: str) -> str | None:
        repo = self._get_repo_optional(username, username)
        if not repo:
            return None
        ref = repo.get("default_branch") or "main"
        for name in ("README.md", "readme.md"):
            payload = self._get_json_optional(
                f"/repos/{quote(username, safe='')}/{quote(username, safe='')}/contents/{quote(name, safe='')}",
                params={"ref": ref},
                cache_key=self._cache_key("profile_readme", username, name, ref),
                default=None,
            )
            content = self._decode_content(payload)
            if content:
                return content
        return None

    def get_repo(self, owner: str, name: str) -> dict[str, Any]:
        repo = self._get_json(
            f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}",
            cache_key=self._cache_key("repo", owner, name),
        )
        return self._normalize_repo(repo)

    def get_repo_languages(self, owner: str, name: str) -> dict[str, int]:
        repo = self.get_repo(owner, name)
        return self.get_languages(repo.get("languages_url", ""))

    def get_repo_contributors(self, owner: str, name: str, limit: int = 10) -> list[dict[str, Any]]:
        commits = self.get_repo_commits(owner, name, limit=100)
        counts: Counter[str] = Counter()
        for commit in commits:
            author = commit.get("author") or {}
            commit_author = ((commit.get("commit") or {}).get("author") or {})
            login = author.get("login") or commit_author.get("name") or "unknown"
            counts[str(login)] += 1
        return [{"login": login, "contributions": count} for login, count in counts.most_common(limit)]

    def get_repo_commits(self, owner: str, name: str, limit: int = 5) -> list[dict[str, Any]]:
        commits = self._get_json_optional(
            f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}/commits",
            params={"limit": min(max(limit, 1), 50)},
            cache_key=self._cache_key("repo_commits", owner, name, str(limit)),
            default=[],
        )
        return [self._normalize_commit(commit) for commit in commits[:limit]] if isinstance(commits, list) else []

    def get_repo_releases(self, owner: str, name: str, limit: int = 3) -> list[dict[str, Any]]:
        releases = self._get_json_optional(
            f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}/releases",
            params={"limit": min(max(limit, 1), 50)},
            cache_key=self._cache_key("repo_releases", owner, name, str(limit)),
            default=[],
        )
        return releases[:limit] if isinstance(releases, list) else []

    def get_repo_workflow_runs(self, owner: str, name: str, limit: int = 1) -> list[dict[str, Any]]:
        if getattr(self, "_actions_unavailable", False):
            return []
        cache_key = self._cache_key("repo_actions_runs", owner, name, str(limit))
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        if self.offline:
            return []
        try:
            response = self.session.get(
                self._url(f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}/actions/runs"),
                params={"limit": min(max(limit, 1), 50)},
                timeout=5,
            )
        except (requests.RequestException, ValueError):
            self._actions_unavailable = True
            return []
        if response.status_code in {401, 403, 502, 503, 504}:
            self._actions_unavailable = True
            return []
        if not response.ok:
            return []
        try:
            payload = response.json()
        except ValueError:
            return []
        if isinstance(payload, dict):
            runs = payload.get("workflow_runs") or payload.get("runs") or []
        elif isinstance(payload, list):
            runs = payload
        else:
            runs = []
        normalized = [
            {
                "name": run.get("name") or run.get("display_title") or f"run #{run.get('run_number') or run.get('id')}",
                "status": run.get("status"),
                "conclusion": run.get("conclusion") or run.get("status"),
                "html_url": run.get("html_url") or run.get("url"),
            }
            for run in runs[:limit]
        ]
        self.cache.set(cache_key, normalized)
        return normalized

    def get_repo_discussions_count(self, owner: str, name: str) -> int | None:
        return None

    def get_repo_sbom(self, owner: str, name: str) -> dict[str, Any]:
        return {}

    def get_repo_security_advisories(self, owner: str, name: str, limit: int = 5) -> list[dict[str, Any]]:
        return []

    def get_user_packages(self, username: str, package_type: str, limit: int = 5) -> list[dict[str, Any]]:
        packages = self._get_json_optional(
            f"/packages/{quote(username, safe='')}",
            params={"type": package_type, "limit": min(max(limit, 1), 50)},
            cache_key=self._cache_key("packages", username, package_type, str(limit)),
            default=[],
        )
        return packages[:limit] if isinstance(packages, list) else []

    def get_org(self, name: str) -> dict[str, Any]:
        org = self._get_json(f"/orgs/{quote(name, safe='')}", cache_key=self._cache_key("org", name))
        return self._normalize_org(org)

    def get_org_members(self, name: str, limit: int = 10) -> list[dict[str, Any]]:
        members = self._get_json_optional(
            f"/orgs/{quote(name, safe='')}/members",
            params={"limit": min(max(limit, 1), 50)},
            cache_key=self._cache_key("org_members", name, str(limit)),
            default=[],
        )
        return [self._normalize_user(member) for member in members[:limit]] if isinstance(members, list) else []

    def get_org_repos(self, name: str) -> list[dict[str, Any]]:
        repos = self._paginate(
            f"/orgs/{quote(name, safe='')}/repos",
            cache_key=self._cache_key("org_repos", name),
        )
        return [self._normalize_repo(repo) for repo in repos]

    def get_rate_limit(self) -> dict[str, Any]:
        return {"rate": {"remaining": 0, "limit": 0}}

    def _graphql_like_bundle(self, username: str, heatmap: list[dict[str, Any]]) -> dict[str, Any]:
        days = _contribution_days_from_heatmap(heatmap)
        total = sum(day["contributionCount"] for week in days for day in week["contributionDays"])
        return {
            "contributionsCollection": {
                "totalCommitContributions": total,
                "totalIssueContributions": 0,
                "totalPullRequestContributions": 0,
                "totalPullRequestReviewContributions": 0,
                "contributionCalendar": {"totalContributions": total, "weeks": days},
            },
        }

    def _get_repo_optional(self, owner: str, name: str) -> dict[str, Any] | None:
        payload = self._get_json_optional(
            f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}",
            cache_key=self._cache_key("repo", owner, name),
            default=None,
        )
        return self._normalize_repo(payload) if isinstance(payload, dict) else None

    def _decode_content(self, payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return None
        content = payload.get("content")
        if not isinstance(content, str):
            return None
        if payload.get("encoding") == "base64":
            try:
                return base64.b64decode(content).decode("utf-8", errors="replace")
            except (ValueError, OSError):
                return None
        return content

    def _normalize_user(self, raw: dict[str, Any]) -> dict[str, Any]:
        last_login = raw.get("last_login")
        if isinstance(last_login, str) and last_login.startswith("0001-01-01"):
            last_login = None
        return {
            **raw,
            "login": raw.get("login") or raw.get("username") or str(raw.get("id", "")),
            "name": raw.get("full_name") or raw.get("login") or raw.get("username"),
            "bio": raw.get("description") or "",
            "blog": raw.get("website") or raw.get("html_url") or "",
            "company": "",
            "location": raw.get("location") or "",
            "avatar_url": raw.get("avatar_url"),
            "html_url": raw.get("html_url"),
            "created_at": raw.get("created") or raw.get("created_at"),
            "updated_at": raw.get("updated_at") or last_login or raw.get("created") or raw.get("created_at"),
            "followers": raw.get("followers_count", 0),
            "following": raw.get("following_count", 0),
            "public_gists": 0,
        }

    def _normalize_repo(self, raw: dict[str, Any]) -> dict[str, Any]:
        owner = raw.get("owner") or {}
        license_payload = raw.get("license") or {}
        license_id = license_payload.get("spdx_id") or license_payload.get("spdx_identifier") or license_payload.get("key") or license_payload.get("name")
        return {
            **raw,
            "name": raw.get("name"),
            "full_name": raw.get("full_name") or f"{owner.get('login') or owner.get('username') or ''}/{raw.get('name')}",
            "description": raw.get("description"),
            "homepage": raw.get("website") or raw.get("link") or "",
            "html_url": raw.get("html_url"),
            "stargazers_count": raw.get("stars_count", raw.get("stargazers_count", 0)),
            "forks_count": raw.get("forks_count", 0),
            "watchers_count": raw.get("watchers_count", raw.get("stars_count", 0)),
            "subscribers_count": raw.get("watchers_count", 0),
            "open_issues_count": raw.get("open_issues_count", 0),
            "size": raw.get("size", 0),
            "language": raw.get("language"),
            "languages_url": raw.get("languages_url"),
            "created_at": raw.get("created_at"),
            "updated_at": raw.get("updated_at"),
            "pushed_at": raw.get("updated_at"),
            "archived": bool(raw.get("archived")),
            "fork": bool(raw.get("fork")),
            "is_template": bool(raw.get("template")),
            "private": bool(raw.get("private") or raw.get("internal")),
            "has_issues": bool(raw.get("has_issues", False)),
            "topics": raw.get("topics") or [],
            "default_branch": raw.get("default_branch") or "main",
            "license": {"spdx_id": license_id} if license_id else None,
            "owner": {
                "login": owner.get("login") or owner.get("username") or "",
                "avatar_url": owner.get("avatar_url"),
            },
        }

    def _normalize_org(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            **raw,
            "login": raw.get("username") or raw.get("name") or raw.get("full_name"),
            "name": raw.get("full_name") or raw.get("username") or raw.get("name"),
            "description": raw.get("description"),
            "blog": raw.get("website") or "",
            "location": raw.get("location") or "",
            "email": raw.get("email") or "",
            "avatar_url": raw.get("avatar_url"),
            "public_repos": raw.get("public_repos", 0),
            "followers": raw.get("followers_count", 0),
        }

    def _normalize_event(self, raw: dict[str, Any]) -> dict[str, Any]:
        op_type = str(raw.get("op_type") or "activity")
        event_type = "PushEvent" if "push" in op_type else op_type
        repo = raw.get("repo") or {}
        return {
            **raw,
            "type": event_type,
            "repo": {"name": repo.get("full_name") or repo.get("name") or "unknown repo"},
            "created_at": raw.get("created") or raw.get("created_at"),
            "payload": {"commits": [{}] if "push" in op_type else []},
        }

    def _normalize_commit(self, raw: dict[str, Any]) -> dict[str, Any]:
        commit = raw.get("commit") or {}
        author = commit.get("author") or {}
        return {
            **raw,
            "sha": raw.get("sha") or raw.get("id"),
            "commit": {
                "message": commit.get("message") or raw.get("message") or "",
                "author": {"name": author.get("name") or ((raw.get("author") or {}).get("login")) or "?"},
            },
        }


class ForgejoClient(GiteaClient):
    provider_name = "forgejo"
    provider_title = "Forgejo"


class CodebergClient(GiteaClient):
    provider_name = "codeberg"
    provider_title = "Codeberg"


class BitbucketClient(BaseProviderClient):
    provider_name = "bitbucket"
    provider_title = "Bitbucket"
    # Bitbucket Cloud exposes a repository's primary language but not a
    # language-by-byte endpoint, so never present repository counts as bytes.
    language_breakdown_unit = "repositories"
    supported_modules = {
        "identity",
        "stats",
        "languages",
        "social_accounts",
        "gists",
        "recent_activity",
        "profile_readme",
        "releases",
        "actions_status",
        "commit_cadence",
    }
    unsupported_reasons = {
        "contributions": "Bitbucket Cloud has no public profile contribution calendar API",
        "sparkline": "Bitbucket Cloud has no public profile contribution calendar API",
        "streaks": "Bitbucket Cloud has no public profile contribution calendar API",
        "pull_requests": "Bitbucket Cloud pull request data is repository scoped, not profile scoped here",
        "issues": "Bitbucket Cloud issues are repository scoped and may be disabled per repo",
        "rate_limit": "Bitbucket Cloud does not expose a portable public rate-limit endpoint here",
        "pinned": "Bitbucket Cloud has no GitHub-style pinned profile items",
        "organizations": "Bitbucket targets are workspaces; use the org command for a workspace summary",
        "starred": "Bitbucket Cloud has no matching public starred-repositories API",
        "watched": "Bitbucket Cloud has no matching public watched-repositories API",
        "showcase": "Bitbucket Cloud has no GitHub-style profile showcase API",
        "sponsors": "Bitbucket Cloud has no matching sponsors listing API",
        "discussions": "Bitbucket Cloud has no profile discussion metric API",
        "dependencies": "Bitbucket Cloud has no public SBOM summary API",
        "security_advisories": "Bitbucket Cloud has no public repository advisory summary API",
        "packages": "Bitbucket Cloud has no matching public packages API",
        "contribution_breakdown": "Bitbucket Cloud has no profile contribution breakdown API",
        "top_repos": "Bitbucket Cloud does not expose repository star counts for ranking",
        "repo_health": "Bitbucket Cloud does not expose the repository metadata required for this summary",
        "topics": "Bitbucket Cloud does not expose repository topics in this API",
        "maintainer_activity": "Bitbucket Cloud does not expose repository star, fork, and issue totals in this API",
    }

    def __init__(self, token: str, cache: CacheStore, offline: bool, base_url: str) -> None:
        super().__init__(token, cache, offline, base_url)
        self.session.headers.update({"Accept": "application/json"})
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def _paginate(self, path: str, params: dict[str, Any] | None = None, cache_key: str | None = None) -> list[dict[str, Any]]:
        if cache_key:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached
        if self.offline:
            raise GitHubAPIError(f"offline mode: {path} not available in cache")
        url = self._url(path)
        merged = dict(params or {})
        merged.setdefault("pagelen", 100)
        items: list[dict[str, Any]] = []
        while url:
            response = self.session.get(url, params=merged, timeout=20)
            merged = {}
            if response.status_code == 404:
                raise GitHubAPIError(f"{self.provider_title} user or resource not found")
            if response.status_code in {401, 403}:
                raise GitHubAPIError(f"{self.provider_title} rejected request: {self._message(response)}")
            if not response.ok:
                raise GitHubAPIError(f"{self.provider_title} API returned HTTP {response.status_code}")
            payload = response.json()
            values = payload.get("values", []) if isinstance(payload, dict) else []
            items.extend(values)
            url = payload.get("next") if isinstance(payload, dict) else None
        if cache_key:
            self.cache.set(cache_key, items)
        return items

    def get_context(self, username: str, mode: str, repo_filters: dict[str, Any]) -> GitHubContext:
        user = self.get_user(username)
        repos = filter_repos(self.get_repos(username, viewer_mode=False), repo_filters)
        user["public_repos"] = len(repos)
        events = self._events_from_repos(username, repos, limit=30)
        return GitHubContext(
            target_user=username,
            user=user,
            repos=repos,
            events=events,
            viewer_mode=False,
            authenticated_login=None,
            graphql={},
        )

    def get_user(self, username: str) -> dict[str, Any]:
        workspace = self._get_json(f"/workspaces/{username}", cache_key=self._cache_key("workspace", username))
        return self._normalize_workspace(workspace)

    def get_repos(self, username: str, viewer_mode: bool = False) -> list[dict[str, Any]]:
        repos = self._paginate(
            f"/repositories/{username}",
            params={"sort": "-updated_on"},
            cache_key=self._cache_key("repos", username),
        )
        return [self._normalize_repo(repo) for repo in repos]

    def get_languages(self, languages_url: str) -> dict[str, int]:
        if not languages_url.startswith("bitbucket://language/"):
            return {}
        language = languages_url.rsplit("/", 1)[-1]
        return {language: 1} if language and language != "n/a" else {}

    def get_social_accounts(self, username: str) -> list[dict[str, Any]]:
        user = self.get_user(username)
        return [{"provider": "bitbucket", "url": user.get("html_url"), "display_name": user.get("login")}]

    def get_organizations(self, username: str) -> list[dict[str, Any]]:
        return []

    def get_starred(self, username: str, limit: int) -> list[dict[str, Any]]:
        return []

    def get_subscriptions(self, username: str, limit: int) -> list[dict[str, Any]]:
        return []

    def get_gists(self, username: str, limit: int) -> list[dict[str, Any]]:
        payload = self._get_json_optional(
            f"/snippets/{username}",
            params={"pagelen": min(max(limit, 1), 100), "sort": "-updated_on"},
            cache_key=self._cache_key("snippets", username, str(limit)),
            default={},
        )
        snippets = payload.get("values", []) if isinstance(payload, dict) else []
        return [
            {
                "id": snippet.get("id"),
                "description": snippet.get("title") or snippet.get("description") or "untitled snippet",
                "html_url": ((snippet.get("links") or {}).get("html") or {}).get("href"),
            }
            for snippet in snippets[:limit]
        ]

    def get_events(self, username: str, limit: int = 10) -> list[dict[str, Any]]:
        return self._events_from_repos(username, self.get_repos(username), limit=limit)

    def get_profile_readme(self, username: str) -> str | None:
        repo = self._get_json_optional(
            f"/repositories/{username}/{username}",
            cache_key=self._cache_key("profile_repo", username),
            default=None,
        )
        if not isinstance(repo, dict):
            return None
        branch = ((repo.get("mainbranch") or {}).get("name")) or "HEAD"
        for name in ("README.md", "readme.md"):
            content = self._get_text_optional(
                f"/repositories/{username}/{username}/src/{quote(branch, safe='')}/{quote(name, safe='')}",
                cache_key=self._cache_key("profile_readme", username, name, branch),
            )
            if content:
                return content
        return None

    def get_repo(self, owner: str, name: str) -> dict[str, Any]:
        raw = self._get_json(f"/repositories/{owner}/{name}", cache_key=self._cache_key("repo", owner, name))
        repo = self._normalize_repo(raw)
        # Cloud exposes exact collection sizes for forks and watchers, but not
        # as fields on the repository representation.
        repo["forks_count"] = self._collection_size(owner, name, "forks")
        watchers = self._collection_size(owner, name, "watchers")
        repo["watchers_count"] = watchers
        repo["subscribers_count"] = watchers
        return repo

    def _collection_size(self, owner: str, name: str, collection: str) -> int | None:
        payload = self._get_json_optional(
            f"/repositories/{owner}/{name}/{collection}",
            params={"pagelen": 1},
            cache_key=self._cache_key("repo_collection_size", owner, name, collection),
            default=None,
        )
        size = payload.get("size") if isinstance(payload, dict) else None
        return size if isinstance(size, int) else None

    def get_repo_languages(self, owner: str, name: str) -> dict[str, int]:
        repo = self.get_repo(owner, name)
        return self.get_languages(repo.get("languages_url", ""))

    def get_repo_contributors(self, owner: str, name: str, limit: int = 10) -> list[dict[str, Any]]:
        commits = self.get_repo_commits(owner, name, limit=100)
        counts: Counter[str] = Counter()
        for commit in commits:
            author = ((commit.get("commit") or {}).get("author") or {}).get("name") or "unknown"
            counts[author] += 1
        return [{"login": login, "contributions": count} for login, count in counts.most_common(limit)]

    def get_repo_commits(self, owner: str, name: str, limit: int = 5) -> list[dict[str, Any]]:
        payload = self._get_json(
            f"/repositories/{owner}/{name}/commits",
            params={"pagelen": min(max(limit, 1), 100)},
            cache_key=self._cache_key("repo_commits", owner, name, str(limit)),
        )
        commits = payload.get("values", []) if isinstance(payload, dict) else []
        return [self._normalize_commit(commit) for commit in commits[:limit]]

    def get_repo_releases(self, owner: str, name: str, limit: int = 3) -> list[dict[str, Any]]:
        downloads = self._get_json_optional(
            f"/repositories/{owner}/{name}/downloads",
            params={"pagelen": min(max(limit, 1), 100)},
            cache_key=self._cache_key("repo_downloads", owner, name, str(limit)),
            default={},
        )
        values = downloads.get("values", []) if isinstance(downloads, dict) else []
        releases = [
            {
                "tag_name": item.get("name"),
                "name": item.get("name"),
                "html_url": ((item.get("links") or {}).get("self") or {}).get("href"),
                "published_at": item.get("created_on"),
                "created_at": item.get("created_on"),
            }
            for item in values[:limit]
        ]
        if releases:
            return releases
        tags = self._get_json_optional(
            f"/repositories/{owner}/{name}/refs/tags",
            params={"pagelen": min(max(limit, 1), 100), "sort": "-target.date"},
            cache_key=self._cache_key("repo_tags", owner, name, str(limit)),
            default={},
        )
        values = tags.get("values", []) if isinstance(tags, dict) else []
        return [
            {
                "tag_name": tag.get("name"),
                "name": tag.get("name"),
                "html_url": ((tag.get("links") or {}).get("html") or {}).get("href"),
                "published_at": (tag.get("target") or {}).get("date"),
                "created_at": (tag.get("target") or {}).get("date"),
            }
            for tag in values[:limit]
        ]

    def get_repo_workflow_runs(self, owner: str, name: str, limit: int = 1) -> list[dict[str, Any]]:
        pipelines = self._get_json_optional(
            f"/repositories/{owner}/{name}/pipelines/",
            params={"pagelen": limit},
            cache_key=self._cache_key("repo_pipelines", owner, name, str(limit)),
            default={},
        )
        values = pipelines.get("values", []) if isinstance(pipelines, dict) else []
        return [
            {
                "name": f"pipeline #{pipeline.get('build_number') or pipeline.get('uuid')}",
                "status": (pipeline.get("state") or {}).get("name") or "unknown",
                "conclusion": (pipeline.get("state") or {}).get("result", {}).get("name"),
                "html_url": ((pipeline.get("links") or {}).get("html") or {}).get("href"),
            }
            for pipeline in values[:limit]
        ]

    def get_repo_discussions_count(self, owner: str, name: str) -> int | None:
        return None

    def get_repo_sbom(self, owner: str, name: str) -> dict[str, Any]:
        return {}

    def get_repo_security_advisories(self, owner: str, name: str, limit: int = 5) -> list[dict[str, Any]]:
        return []

    def get_user_packages(self, username: str, package_type: str, limit: int = 5) -> list[dict[str, Any]]:
        return []

    def get_org(self, name: str) -> dict[str, Any]:
        return self.get_user(name)

    def get_org_members(self, name: str, limit: int = 10) -> list[dict[str, Any]]:
        members = self._get_json_optional(
            f"/workspaces/{name}/members",
            params={"pagelen": limit},
            cache_key=self._cache_key("workspace_members", name, str(limit)),
            default={},
        )
        values = members.get("values", []) if isinstance(members, dict) else []
        normalized = []
        for item in values[:limit]:
            user = item.get("user") or item
            normalized.append({"login": user.get("nickname") or user.get("display_name") or user.get("account_id") or "unknown", **user})
        return normalized

    def get_org_repos(self, name: str) -> list[dict[str, Any]]:
        return self.get_repos(name)

    def get_rate_limit(self) -> dict[str, Any]:
        return {"rate": {"remaining": 0, "limit": 0}}

    def _events_from_repos(self, username: str, repos: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for repo in sorted(repos, key=lambda item: item.get("updated_at") or "", reverse=True)[:8]:
            full_name = repo.get("full_name")
            if not isinstance(full_name, str) or "/" not in full_name:
                continue
            rows.append(
                {
                    "type": "RepositoryEvent",
                    "repo": {"name": full_name},
                    "created_at": repo.get("updated_at"),
                    "payload": {"commits": []},
                }
            )
        rows.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        return rows[:limit]

    def _normalize_workspace(self, raw: dict[str, Any]) -> dict[str, Any]:
        links = raw.get("links") or {}
        return {
            **raw,
            "login": raw.get("slug") or raw.get("name") or raw.get("uuid"),
            "name": raw.get("name") or raw.get("slug"),
            "bio": raw.get("type", "workspace"),
            "company": "",
            "blog": ((links.get("html") or {}).get("href")) or "",
            "location": "",
            "avatar_url": ((links.get("avatar") or {}).get("href")),
            "html_url": ((links.get("html") or {}).get("href")),
            "created_at": raw.get("created_on"),
            "updated_at": raw.get("updated_on") or raw.get("created_on"),
            "public_gists": 0,
            "followers": 0,
            "following": 0,
        }

    def _normalize_repo(self, raw: dict[str, Any]) -> dict[str, Any]:
        links = raw.get("links") or {}
        owner = raw.get("owner") or raw.get("workspace") or {}
        language = raw.get("language") or "n/a"
        full_name = raw.get("full_name") or f"{owner.get('nickname') or owner.get('slug', '')}/{raw.get('slug') or raw.get('name')}"
        return {
            **raw,
            "name": raw.get("slug") or raw.get("name"),
            "full_name": full_name,
            "description": raw.get("description"),
            "html_url": ((links.get("html") or {}).get("href")),
            "stargazers_count": None,
            "forks_count": None,
            "watchers_count": None,
            "open_issues_count": None,
            "size": raw.get("size", 0),
            "language": language if language != "n/a" else None,
            "languages_url": f"bitbucket://language/{language}",
            "created_at": raw.get("created_on"),
            "updated_at": raw.get("updated_on"),
            "pushed_at": raw.get("updated_on"),
            "archived": False,
            "fork": bool(raw.get("parent")),
            "is_template": False,
            "private": bool(raw.get("is_private")),
            "has_issues": bool(raw.get("has_issues", False)),
            "topics": [],
            "default_branch": (raw.get("mainbranch") or {}).get("name") or "main",
            "license": None,
            "owner": {
                "login": owner.get("nickname") or owner.get("slug") or owner.get("username") or "",
                "avatar_url": ((owner.get("links") or {}).get("avatar") or {}).get("href"),
            },
        }

    def _normalize_commit(self, raw: dict[str, Any]) -> dict[str, Any]:
        author = raw.get("author") or {}
        user = author.get("user") or {}
        return {
            **raw,
            "sha": raw.get("hash"),
            "commit": {
                "message": raw.get("message") or "",
                "author": {"name": user.get("display_name") or author.get("raw") or "?"},
            },
        }


def _contribution_days_from_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=83)
    counts: Counter[str] = Counter()
    for event in events:
        created = event.get("created_at")
        if not created:
            continue
        try:
            day = datetime.fromisoformat(str(created).replace("Z", "+00:00")).date()
        except ValueError:
            continue
        if start <= day <= today:
            counts[day.isoformat()] += 1
    weeks: list[dict[str, Any]] = []
    cursor = start
    while cursor <= today:
        week_days = []
        for _ in range(7):
            if cursor > today:
                break
            iso = cursor.isoformat()
            week_days.append({"date": iso, "contributionCount": counts[iso]})
            cursor += timedelta(days=1)
        weeks.append({"contributionDays": week_days})
    return weeks


def _contribution_days_from_heatmap(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=83)
    counts: Counter[str] = Counter()
    for point in points:
        try:
            day = datetime.fromtimestamp(int(point.get("timestamp", 0)), timezone.utc).date()
        except (TypeError, ValueError, OSError):
            continue
        if start <= day <= today:
            counts[day.isoformat()] += int(point.get("contributions", 0) or 0)
    weeks: list[dict[str, Any]] = []
    cursor = start
    while cursor <= today:
        week_days = []
        for _ in range(7):
            if cursor > today:
                break
            iso = cursor.isoformat()
            week_days.append({"date": iso, "contributionCount": counts[iso]})
            cursor += timedelta(days=1)
        weeks.append({"contributionDays": week_days})
    return weeks


def provider_name_from_config(config: dict[str, Any]) -> str:
    name = str(config.get("profile", {}).get("provider", "github")).lower()
    if name not in SUPPORTED_PROVIDERS:
        raise ConfigError(f"unsupported provider: {name}")
    return name


def provider_base_url(config: dict[str, Any], provider: str) -> str:
    return str(config.get("providers", {}).get(provider, {}).get("base_url", "")).rstrip("/")


def create_provider_client(config: dict[str, Any], token: str, cache: CacheStore, offline: bool = False):
    provider = provider_name_from_config(config)
    base_url = provider_base_url(config, provider)
    if not base_url:
        raise ConfigError(f"providers.{provider}.base_url must not be empty")
    if provider == "github":
        return GitHubClient(token=token, cache=cache, offline=offline, base_url=base_url)
    if provider == "gitlab":
        return GitLabClient(token=token, cache=cache, offline=offline, base_url=base_url)
    if provider == "bitbucket":
        return BitbucketClient(token=token, cache=cache, offline=offline, base_url=base_url)
    if provider == "gitea":
        return GiteaClient(token=token, cache=cache, offline=offline, base_url=base_url)
    if provider == "forgejo":
        return ForgejoClient(token=token, cache=cache, offline=offline, base_url=base_url)
    if provider == "codeberg":
        return CodebergClient(token=token, cache=cache, offline=offline, base_url=base_url)
    raise ConfigError(f"unsupported provider: {provider}")
