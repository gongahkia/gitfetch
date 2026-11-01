"""Pure, unstyled profile documents built from already evaluated modules.

Text and raw payloads are untrusted semantic data. Renderers must sanitize text
at their display boundary. Nothing here measures, positions, styles or fetches.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal

from gitfetch.semantics import Measurement, RepositoryCoverage, number, profile_measurements, repository_measurements

if TYPE_CHECKING:
    from gitfetch.github_api import GitHubContext
    from gitfetch.modules.builtin import ModuleResult


@dataclass(frozen=True)
class ProfileIdentity:
    provider: str
    instance: str
    username: str | None
    display_name: str | None
    biography: str | None
    company: str | None
    location: str | None
    website: str | None
    avatar_reference: str | None
    url: str | None
    created_at: str | None
    updated_at: str | None


@dataclass(frozen=True)
class Metric:
    identifier: str
    label: str
    measurement: Measurement


@dataclass(frozen=True)
class MetricGroup:
    metrics: tuple[Metric, ...]


@dataclass(frozen=True)
class LanguageEntry:
    language: str
    value: int | float


@dataclass(frozen=True)
class LanguageDistribution:
    selected: tuple[LanguageEntry, ...]
    totals: tuple[LanguageEntry, ...]
    measurement: Measurement


@dataclass(frozen=True)
class ContributionDay:
    date: date
    count: int | None  # None is an explicitly unknown date, never a zero.


@dataclass(frozen=True)
class ContributionActivity:
    days: tuple[ContributionDay, ...]
    measurement: Measurement
    calendar_days: tuple[ContributionDay, ...]
    calendar_measurement: Measurement


@dataclass(frozen=True)
class Repository:
    name: str
    description: str | None
    language: str | None
    url: str | None
    metrics: tuple[Metric, ...]


@dataclass(frozen=True)
class RepositoryList:
    repositories: tuple[Repository, ...]
    measurement: Measurement


@dataclass(frozen=True)
class ActivityEvent:
    event_type: str | None
    repository: str | None
    occurred_at: str | None


@dataclass(frozen=True)
class RecentActivity:
    events: tuple[ActivityEvent, ...]
    measurement: Measurement


@dataclass(frozen=True)
class PresentationNotice:
    kind: Literal["availability", "coverage", "scope", "data"]
    subjects: tuple[tuple[str, str], ...]  # (module, measurement identifier)
    measurement: Measurement


Content = ProfileIdentity | MetricGroup | LanguageDistribution | ContributionActivity | RepositoryList | RecentActivity


@dataclass(frozen=True)
class PresentationSection:
    name: str
    title: str
    lines: tuple[str, ...]  # Transitional classic rendering; never parsed for metrics.
    content: Content | None
    measurements: Mapping[str, Measurement]
    raw_data: Any = field(repr=False, compare=False)


@dataclass(frozen=True)
class ProfileDocument:
    provider: str
    instance: str  # API instance reference, without probing or URL rewriting.
    username: str | None
    avatar_reference: str | None
    sections: tuple[PresentationSection, ...]
    notices: tuple[PresentationNotice, ...]
    repository_coverage: RepositoryCoverage | None
    viewer_mode: bool

    @property
    def identity(self) -> ProfileIdentity | None:
        return next((s.content for s in self.sections if isinstance(s.content, ProfileIdentity)), None)


def _mapping(value: Any) -> dict:
    # Do not invoke arbitrary plugin mapping/iteration/conversion protocols.
    return value if type(value) is dict else value.copy() if type(value) is MappingProxyType else {}


def _sequence(value: Any) -> Sequence:
    return value if type(value) in (list, tuple) else ()


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _display_text(value: Any) -> str:
    if value is None:
        return ""
    if type(value) in (str, int, float, bool):
        return str(value)
    return "[unsupported display value]"


def _snapshot(value: Any, ancestors: frozenset[int] = frozenset()) -> Any:
    """Freeze ordinary containers without deepcopy hooks or traversing objects.

    Opaque plugin objects and cyclic/deep branches remain borrowed opaque data.
    They are never interpreted or rendered by the compatibility renderer.
    """
    if id(value) in ancestors or len(ancestors) >= 64:
        return value
    branch = ancestors | {id(value)}
    if type(value) is dict:
        return MappingProxyType({key: _snapshot(item, branch) for key, item in dict.items(value)})
    if type(value) in (list, tuple):
        return tuple(_snapshot(item, branch) for item in value)
    if type(value) in (set, frozenset):
        return frozenset(_snapshot(item, branch) for item in value)
    return value


def _measurement(value: Any, *, provider: str, unit: str, scope: str, source: str) -> Measurement:
    measured = number(value)
    return Measurement(measured, provider, unit, scope, "available" if measured is not None else "unavailable",
                       source, reason="measurement not supplied" if measured is None else "")


def _identity(user: dict, provider: str, instance: str) -> ProfileIdentity:
    return ProfileIdentity(provider, instance, *(_text(user.get(key)) for key in (
        "login", "name", "bio", "company", "location", "blog", "avatar_url", "html_url", "created_at", "updated_at",
    )))


def _metrics(name: str, data: Any, metadata: Mapping[str, Measurement], provider: str) -> MetricGroup | None:
    if name == "stats":
        labels = {"public_repos": "Public repositories", "public_gists": "Public gists",
                  "followers": "Followers", "following": "Following"}
        user = _mapping(_mapping(data).get("user"))
        measured = profile_measurements(user, provider) if user else {}
        measured.update(metadata)
    else:
        labels = {"current": "Current observed streak", "longest": "Longest observed streak", "total": "Window total"}
        values = _mapping(data)
        measured = dict(metadata)
        for key in labels:
            if key in measured or key not in values:
                continue
            base = metadata.get("contributions") if key == "total" else None
            value = number(values[key])
            measured[key] = replace(base, value=value if base.availability == "available" else None,
                                    availability="unavailable" if value is None and base.availability == "available" else base.availability) if base else _measurement(
                values[key], provider=provider, unit="days" if key != "total" else "contributions",
                scope="observed contribution window", source="streaks module data")
    metrics = tuple(Metric(key, labels.get(key, key.replace("_", " ").title()), value)
                    for key, value in measured.items() if key != "contributions" or name != "streaks")
    return MetricGroup(metrics) if metrics else None


def _languages(data: Any, metadata: Mapping[str, Measurement], provider: str) -> LanguageDistribution | None:
    measurement = metadata.get("languages")
    selected = []
    units = set()
    for item in _sequence(data):
        row = _mapping(item)
        language = _text(row.get("language"))
        for unit in ((measurement.unit,) if measurement else ("bytes", "repositories")):
            value = number(row.get(unit))
            if language is not None and value is not None:
                selected.append(LanguageEntry(language, value))
                units.add(unit)
                break
    if measurement is None:
        if len(units) != 1:
            return None
        # Legacy results can reveal their units, but a truncated list cannot
        # establish a denominator or complete profile distribution.
        measurement = Measurement(provider=provider, unit=next(iter(units)), scope="module language entries",
                                  source="languages module data", reason="aggregate denominator not supplied")
    totals = tuple(LanguageEntry(language, value) for language, value in measurement.language_totals)
    return LanguageDistribution(tuple(selected), totals, measurement)


def _days(weeks: Any) -> tuple[ContributionDay, ...]:
    observations = {}
    for week in _sequence(weeks):
        for day in _sequence(_mapping(week).get("contributionDays")):
            row = _mapping(day)
            try:
                observed = date.fromisoformat(row["date"])
            except (KeyError, TypeError, ValueError):
                continue
            count = row.get("contributionCount")
            if count is None or (type(count) is int and count >= 0):
                observations[observed] = ContributionDay(observed, count)
    return tuple(observations[key] for key in sorted(observations))


def _observed_coverage(days: tuple[ContributionDay, ...], measurement: Measurement) -> Measurement:
    if (days and measurement.coverage == "complete"
            and (any(day.count is None for day in days) or (days[-1].date - days[0].date).days + 1 != len(days))):
        return replace(measurement, coverage="partial")
    return measurement


def _contributions(data: Any, metadata: Mapping[str, Measurement], provider: str,
                   context: GitHubContext | None) -> ContributionActivity:
    days = _days(data)
    measurement = metadata.get("contributions") or Measurement(
        provider=provider, unit="contributions", scope="module contribution observations",
        availability="available" if days else "unavailable", source="contributions module data")
    measurement = _observed_coverage(days, measurement)
    calendar_days = days
    calendar_measurement = measurement
    if context is not None:
        bundle = _mapping(_mapping(getattr(context, "graphql", None)).get("contributionsCollection"))
        calendar = _mapping(bundle.get("contributionCalendar"))
        collected = _days(calendar.get("weeks"))
        if collected:
            calendar_days = collected
            source = _mapping(getattr(context, "measurements", None)).get("contributions")
            if isinstance(source, Measurement):
                calendar_measurement = source
            elif collected != days:
                calendar_measurement = replace(
                    measurement, value=number(calendar.get("totalContributions")), sample_size=len(collected),
                    start=collected[0].date.isoformat(), end=collected[-1].date.isoformat(),
                )
    calendar_measurement = _observed_coverage(calendar_days, calendar_measurement)
    return ContributionActivity(days, measurement, calendar_days, calendar_measurement)


def _repositories(name: str, data: Any, metadata: Mapping[str, Measurement], provider: str) -> RepositoryList | None:
    if type(data) not in (list, tuple):
        return None
    repositories = []
    for item in data:
        row = _mapping(item)
        if row.get("__typename") not in (None, "Repository"):
            continue  # Pinned gists remain in raw_data and the classic fallback.
        repo_name = _text(row.get("nameWithOwner") or row.get("name") or row.get("full_name"))
        if repo_name is None:
            continue
        stars = row.get("stargazerCount") if name == "pinned" else row.get("stars")
        metric = repository_measurements({"stargazers_count": stars}, provider)["stargazers_count"]
        language = _text(_mapping(row.get("primaryLanguage")).get("name")) if name == "pinned" else _text(row.get("language"))
        repositories.append(Repository(repo_name, _text(row.get("description")), language,
                                       _text(row.get("url")), (Metric("stars", "Stars", metric),)))
    measurement = metadata.get(name) or Measurement(
        provider=provider, unit="repositories", scope="pinned repositories" if name == "pinned" else "selected repositories ranked by known stars",
        source=f"{name} module data", sample_size=len(repositories))
    return RepositoryList(tuple(repositories), measurement)


def _content(name: str, data: Any, metadata: Mapping[str, Measurement], user: dict,
             provider: str, instance: str, context: GitHubContext | None) -> Content | None:
    status = metadata.get(name)
    if status is not None and status.availability != "available":
        return None
    if name == "identity":
        payload = _mapping(data)
        return _identity(_mapping(payload.get("user")) or (payload if "login" in payload else user), provider, instance)
    if name in {"stats", "streaks"}:
        return _metrics(name, data, metadata, provider)
    if name == "languages":
        return _languages(data, metadata, provider)
    if name == "contributions":
        return _contributions(data, metadata, provider, context)
    if name in {"pinned", "top_repos"}:
        return _repositories(name, data, metadata, provider)
    if name == "recent_activity" and type(data) in (list, tuple):
        events = tuple(ActivityEvent(_text(row.get("type")), _text(row.get("repo")), _text(row.get("created_at")))
                       for item in data if (row := _mapping(item)))
        measurement = metadata.get(name) or Measurement(
            provider=provider, unit="events", scope="public activity" if provider == "github" else "viewer-visible activity",
            source="recent_activity module data", sample_size=len(events))
        return RecentActivity(events, measurement)
    return None


def _notices(sections: Sequence[PresentationSection]) -> tuple[PresentationNotice, ...]:
    notices: dict[tuple, PresentationNotice] = {}
    for section in sections:
        for key, measurement in section.measurements.items():
            kinds = []
            if measurement.availability != "available":
                kinds.append("availability")
            elif (measurement.coverage != "complete"
                  and not (section.name == "streaks" and key in {"current", "longest"} and "contributions" in section.measurements)):
                # Current/longest streaks refer to the same underlying window.
                kinds.append("coverage")
            if section.name == "languages" and key == "languages" and not measurement.complete_profile:
                kinds.append("scope")
            for kind in kinds:
                identity = (kind, measurement.availability, measurement.coverage, measurement.provider,
                            measurement.source, measurement.reason, measurement.start, measurement.end)
                subject = (section.name, key)
                if identity in notices:
                    old = notices[identity]
                    if subject not in old.subjects:
                        notices[identity] = replace(old, subjects=(*old.subjects, subject))
                else:
                    notices[identity] = PresentationNotice(kind, (subject,), measurement)
    return tuple(notices.values())


def build_profile_document(user: Mapping[str, Any], modules: Sequence[ModuleResult], *,
                           provider: str, instance: str = "", context: GitHubContext | None = None) -> ProfileDocument:
    """Consume the resolved visible module results, without evaluating anything.

    The caller supplies provider/instance explicitly. No clock or viewport is
    consulted; relative labels in the classic fallback are already evaluated.
    """
    profile = _mapping(user)
    sections = []
    for index, module in enumerate(modules):
        if module.hidden:
            continue
        name = _text(module.name) or f"module-{index}"
        metadata = {key: value for key, value in _mapping(module.measurements).items()
                    if isinstance(key, str) and isinstance(value, Measurement)}
        payload = _mapping(module.data)
        if name not in metadata:
            if payload.get("requires_token") is True and len(payload) == 1:
                metadata[name] = Measurement(provider=provider, scope=name, availability="auth_required", source="module capability")
            elif payload.get("unsupported") is True and "provider" in payload and "reason" in payload:
                metadata[name] = Measurement(provider=provider, scope=name, availability="unsupported",
                                             source="module capability", reason=_text(payload.get("reason")) or "")
        content = _content(name, module.data, metadata, profile, provider, instance, context)
        # Retain derived structured metadata too, including legacy modules that
        # supplied data without measurements. Explicit module metadata wins.
        if isinstance(content, MetricGroup):
            for metric in content.metrics:
                metadata.setdefault(metric.identifier, metric.measurement)
        elif isinstance(content, (LanguageDistribution, ContributionActivity, RepositoryList, RecentActivity)):
            metadata.setdefault(name, content.measurement)
        lines = (module.lines,) if isinstance(module.lines, str) else _sequence(module.lines)
        sections.append(PresentationSection(name, _display_text(module.title), tuple(_display_text(line) for line in lines),
                                             content, MappingProxyType(metadata), _snapshot(module.data)))
    coverage = getattr(context, "repository_coverage", None) if context is not None else None
    return ProfileDocument(provider, instance, _text(profile.get("login")), _text(profile.get("avatar_url")),
                           tuple(sections), _notices(sections),
                           coverage if isinstance(coverage, RepositoryCoverage) else None,
                           getattr(context, "viewer_mode", False) is True)
