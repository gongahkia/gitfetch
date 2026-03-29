import base64
import time
from dataclasses import dataclass
from typing import Any

import requests

from gitfetch.cache import CacheStore


USER_AGENT = "gitfetch/2.0.0"


class GitHubAPIError(RuntimeError):
    pass


@dataclass
class GitHubContext:
    target_user: str
    user: dict[str, Any]
    repos: list[dict[str, Any]]
    events: list[dict[str, Any]]
    viewer_mode: bool
    authenticated_login: str | None
    graphql: dict[str, Any]


class GitHubClient:
    def __init__(self, token: str, cache: CacheStore) -> None:
        self.token = token
        self.cache = cache
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "User-Agent": USER_AGENT,
            }
        )
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def get_context(
        self,
        username: str,
        mode: str,
        repo_filters: dict[str, Any],
    ) -> GitHubContext:
        public_user = self.get_user(username)
        authenticated_login = None
        viewer_mode = False
        if mode == "viewer" and self.token:
            viewer = self.get_authenticated_user()
            authenticated_login = viewer.get("login")
            if authenticated_login and authenticated_login.lower() == username.lower():
                viewer_mode = True
                public_user = viewer

        repos = self.get_repos(username, viewer_mode=viewer_mode)
        repos = filter_repos(repos, repo_filters)
        events = self.get_events(username)
        graphql = self.get_graphql_bundle(username) if self.token else {}
        return GitHubContext(
            target_user=username,
            user=public_user,
            repos=repos,
            events=events,
            viewer_mode=viewer_mode,
            authenticated_login=authenticated_login,
            graphql=graphql,
        )

    def _cache_key(self, prefix: str, *parts: str) -> str:
        suffix = "|".join(parts)
        auth_scope = "auth" if self.token else "anon"
        return f"{prefix}|{auth_scope}|{suffix}"

    def _get_json(self, path: str, params: dict[str, Any] | None = None, cache_key: str | None = None) -> Any:
        if cache_key:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached
        response = self.session.get(f"https://api.github.com{path}", params=params, timeout=20)
        if response.status_code == 404:
            raise GitHubAPIError("GitHub user or resource not found")
        if response.status_code == 401:
            raise GitHubAPIError("GitHub authentication failed")
        if response.status_code == 403:
            raise GitHubAPIError(f"GitHub rate limited request: {response.json().get('message', '')}")
        if not response.ok:
            raise GitHubAPIError(f"GitHub API returned HTTP {response.status_code}")
        payload = response.json()
        if cache_key:
            self.cache.set(cache_key, payload)
        return payload

    def _paginate(self, path: str, params: dict[str, Any] | None = None, cache_key: str | None = None) -> list[dict[str, Any]]:
        if cache_key:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached
        merged_params = dict(params or {})
        merged_params["per_page"] = 100
        page = 1
        items: list[dict[str, Any]] = []
        while True:
            merged_params["page"] = page
            batch = self._get_json(path, params=merged_params)
            if not isinstance(batch, list) or not batch:
                break
            items.extend(batch)
            page += 1
        if cache_key:
            self.cache.set(cache_key, items)
        return items

    def get_user(self, username: str) -> dict[str, Any]:
        return self._get_json(
            f"/users/{username}",
            cache_key=self._cache_key("user", username),
        )

    def get_authenticated_user(self) -> dict[str, Any]:
        return self._get_json(
            "/user",
            cache_key=self._cache_key("viewer", "self"),
        )

    def get_repos(self, username: str, viewer_mode: bool) -> list[dict[str, Any]]:
        if viewer_mode:
            return self._paginate(
                "/user/repos",
                params={"type": "owner", "sort": "updated"},
                cache_key=self._cache_key("repos", "viewer", username),
            )
        return self._paginate(
            f"/users/{username}/repos",
            params={"sort": "updated"},
            cache_key=self._cache_key("repos", "public", username),
        )

    def get_languages(self, languages_url: str) -> dict[str, int]:
        cache_key = self._cache_key("languages", languages_url)
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        response = self.session.get(languages_url, timeout=20)
        if response.status_code == 403:
            raise GitHubAPIError(f"GitHub rate limited request: {response.json().get('message', '')}")
        if not response.ok:
            return {}
        payload = response.json()
        self.cache.set(cache_key, payload)
        return payload

    def get_social_accounts(self, username: str) -> list[dict[str, Any]]:
        return self._paginate(
            f"/users/{username}/social_accounts",
            cache_key=self._cache_key("social_accounts", username),
        )

    def get_organizations(self, username: str) -> list[dict[str, Any]]:
        return self._paginate(
            f"/users/{username}/orgs",
            cache_key=self._cache_key("orgs", username),
        )

    def get_starred(self, username: str, limit: int) -> list[dict[str, Any]]:
        return self._paginate(
            f"/users/{username}/starred",
            cache_key=self._cache_key("starred", username, str(limit)),
        )[:limit]

    def get_subscriptions(self, username: str, limit: int) -> list[dict[str, Any]]:
        return self._paginate(
            f"/users/{username}/subscriptions",
            cache_key=self._cache_key("subscriptions", username, str(limit)),
        )[:limit]

    def get_gists(self, username: str, limit: int) -> list[dict[str, Any]]:
        return self._paginate(
            f"/users/{username}/gists",
            cache_key=self._cache_key("gists", username, str(limit)),
        )[:limit]

    def get_events(self, username: str, limit: int = 10) -> list[dict[str, Any]]:
        return self._get_json(
            f"/users/{username}/events/public",
            params={"per_page": limit},
            cache_key=self._cache_key("events", username, str(limit)),
        )[:limit]

    def get_profile_readme(self, username: str) -> str | None:
        cache_key = self._cache_key("profile_readme", username)
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        response = self.session.get(
            f"https://api.github.com/repos/{username}/{username}/readme",
            timeout=20,
        )
        if response.status_code == 404:
            return None
        if response.status_code == 403:
            raise GitHubAPIError(f"GitHub rate limited request: {response.json().get('message', '')}")
        if not response.ok:
            return None
        payload = response.json()
        content = payload.get("content")
        if not content:
            return None
        decoded = base64.b64decode(content).decode("utf-8", errors="replace")
        self.cache.set(cache_key, decoded)
        return decoded

    def get_graphql_bundle(self, username: str) -> dict[str, Any]:
        cache_key = self._cache_key("graphql_bundle", username)
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        query = """
        query GitFetchProfile($login: String!, $showcaseLimit: Int!) {
          user(login: $login) {
            login
            hasSponsorsListing
            contributionsCollection {
              contributionCalendar {
                weeks {
                  contributionDays {
                    contributionCount
                    date
                  }
                }
              }
            }
            itemShowcase {
              hasPinnedItems
              items(first: $showcaseLimit) {
                nodes {
                  __typename
                  ... on Repository {
                    nameWithOwner
                    description
                    url
                    stargazerCount
                    isFork
                    primaryLanguage {
                      name
                    }
                  }
                  ... on Gist {
                    name
                    description
                    url
                  }
                }
              }
            }
          }
        }
        """
        response = self.session.post(
            "https://api.github.com/graphql",
            json={"query": query, "variables": {"login": username, "showcaseLimit": 10}},
            timeout=20,
        )
        if response.status_code == 403:
            raise GitHubAPIError(f"GitHub rate limited request: {response.json().get('message', '')}")
        if not response.ok:
            return {}
        payload = response.json()
        if payload.get("errors"):
            return {}
        user = payload.get("data", {}).get("user", {}) or {}
        self.cache.set(cache_key, user)
        return user


def filter_repos(repos: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for repo in repos:
        if filters.get("exclude_forks") and repo.get("fork"):
            continue
        if filters.get("exclude_archived") and repo.get("archived"):
            continue
        if filters.get("exclude_templates") and repo.get("is_template"):
            continue
        results.append(repo)
    return results


def format_relative_days(timestamp: str | None) -> str | None:
    if not timestamp:
        return None
    try:
        parsed = time.strptime(timestamp.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        return None
    seconds = time.time() - time.mktime(parsed)
    days = int(max(seconds, 0) // 86400)
    return f"{days} days ago"
