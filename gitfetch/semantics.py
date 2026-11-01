"""Internal measurement provenance; never implicitly serialized into public JSON.

Coverage describes the stated scope, not the whole account. A complete scan of
selected repositories can still be an incomplete profile measurement.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Literal

Availability = Literal["available", "unavailable", "unsupported", "auth_required"]
Coverage = Literal["complete", "partial", "unknown"]


@dataclass(frozen=True)
class Measurement:
    value: int | float | None = None
    provider: str = ""
    unit: str = "count"
    scope: str = ""
    availability: Availability = "available"
    source: str = ""
    coverage: Coverage = "unknown"
    sample_size: int | None = None
    denominator: int | float | None = None
    start: str | None = None
    end: str | None = None
    reason: str = ""
    languages: tuple[str, ...] = ()
    complete_profile: bool = False
    eligible_repositories: int | None = None
    attempted: int | None = None
    failed: int = 0
    missing: int = 0
    sampling_policy: str = ""
    language_totals: tuple[tuple[str, int | float], ...] = ()


@dataclass(frozen=True)
class RepositoryCoverage:
    fetched: int
    retained: int
    public: int
    private: int
    scope: str
    filters: tuple[str, ...] = ()
    eligible: int | None = None


class LanguageData(dict[str, int | float]):
    """A dict-compatible response, including successful empty responses."""

    def __init__(self, values: dict[str, Any], measurement: Measurement) -> None:
        super().__init__(values)
        self.measurement = measurement


class HeatmapData(list[dict[str, Any]]):
    def __init__(self, values: list[dict[str, Any]], measurement: Measurement) -> None:
        super().__init__(values)
        self.measurement = measurement


def number(value: Any) -> int | float | None:
    """Accept measured, finite, nonnegative numbers, including a real zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if value >= 0 and (isinstance(value, int) or isfinite(value)) else None


def metric_text(value: Any) -> str:
    return "unavailable" if number(value) is None else str(value)


def profile_measurements(user: dict[str, Any], provider: str) -> dict[str, Measurement]:
    unsupported = {"public_gists"} if provider in {"gitlab", "gitea", "forgejo", "codeberg"} else set()
    if provider == "bitbucket":
        unsupported |= {"followers", "following", "public_gists"}
    result = {}
    for field in ("public_repos", "followers", "following", "public_gists"):
        value = number(user.get(field))
        status: Availability = "available" if value is not None else "unsupported" if field in unsupported else "unavailable"
        result[field] = Measurement(
            value, provider, "repositories" if field == "public_repos" else "count",
            "public owned repositories" if field == "public_repos" else field,
            status, "profile response", "complete" if value is not None else "unknown",
            reason="not supplied by this endpoint" if value is None else "",
        )
    return result


def repository_coverage(fetched: list[dict[str, Any]], retained: list[dict[str, Any]],
                        viewer: bool, filters: dict[str, Any], eligible: int | None = None) -> RepositoryCoverage:
    return RepositoryCoverage(
        len(fetched), len(retained), sum(r.get("private") is False for r in fetched),
        sum(r.get("private") is True for r in fetched),
        "viewer owned repositories" if viewer else "public owned repositories",
        tuple(sorted(key for key, value in filters.items() if value)),
        len(fetched) if eligible is None else eligible,
    )


def aggregate(repos: list[dict[str, Any]], field: str) -> int | float | None:
    values = [number(repo.get(field)) for repo in repos]
    return sum(value for value in values if value is not None) if all(v is not None for v in values) else None


def repository_measurements(repo: dict[str, Any], provider: str) -> dict[str, Measurement]:
    unsupported = {"watchers_count", "subscribers_count"} if provider == "gitlab" else set()
    if provider == "bitbucket":
        unsupported |= {"stargazers_count", "open_issues_count"}
    result = {}
    for key in ("stargazers_count", "forks_count", "watchers_count", "subscribers_count", "open_issues_count", "size"):
        value = number(repo.get(key))
        availability: Availability = "available" if value is not None else "unsupported" if key in unsupported else "unavailable"
        result[key] = Measurement(value, provider, "bytes" if key == "size" and provider in {"gitlab", "bitbucket"}
                                  else "KB" if key == "size" else "count", "repository", availability,
                                  "repository response", "complete" if value is not None else "unknown")
    return result
