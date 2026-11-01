"""Pure terminal profile planning. No terminal queries, styling, assets or I/O.

Rows contain sanitized text and small semantic color roles, never ANSI. The
renderer measures the viewport and encodes the one allocated avatar afterwards.
"""
from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, timedelta
from types import MappingProxyType
from typing import Literal
from urllib.parse import urlsplit

from wcwidth import iter_graphemes

from gitfetch.presentation import (
    ContributionActivity,
    LanguageDistribution,
    MetricGroup,
    PresentationSection,
    ProfileDocument,
    ProfileIdentity,
    RecentActivity,
    RepositoryList,
)
from gitfetch.semantics import Measurement
from gitfetch.terminal_text import cell_width, clip_text, sanitize_text

Role = Literal["identity", "heading", "text", "muted", "track", "accent", "stat", "notice"]
Composition = Literal["split", "stack", "text"]
# Standalone/help-quoted flags, not double hyphens inside URL paths or queries.
_FLAG = re.compile(r"(?<![^\s(\[{'\"`])--[A-Za-z][A-Za-z0-9-]*")


@dataclass(frozen=True)
class Viewport:
    columns: int = 80
    rows: int = 24


@dataclass(frozen=True)
class Preferences:
    details: bool = False
    layout: Literal["split", "stack"] = "split"
    margin: int = 0
    avatar: bool = True
    avatar_width: int = 100
    avatar_style: str = "ascii"


@dataclass(frozen=True)
class AvatarGeometry:
    width: int
    height: int

    def rows_at(self, columns: int, style: str) -> int:
        factor = 0.55 if style == "ascii" else 0.5
        return max(1, int(self.height / max(1, self.width) * columns * factor))


@dataclass(frozen=True)
class Span:
    text: str
    role: Role = "text"


@dataclass(frozen=True)
class Row:
    spans: tuple[Span, ...]
    module: str = ""

    @property
    def text(self) -> str:
        return "".join(span.text for span in self.spans)


@dataclass(frozen=True)
class LayoutPlan:
    viewport: Viewport
    composition: Composition
    text_width: int
    margin: int
    avatar_width: int
    avatar_rows: int
    rows: tuple[Row, ...]
    condensed: bool
    omitted_modules: tuple[str, ...]

    @property
    def height(self) -> int:
        if self.composition == "stack":
            return self.avatar_rows + bool(self.rows) + len(self.rows)
        return max(self.avatar_rows, len(self.rows))


@dataclass(frozen=True)
class _Section:
    name: str
    rows: tuple[Row, ...]
    priority: int
    minimum: int
    condensed: bool = False
    compact: tuple[Row, ...] = ()


def _line(text: str, role: Role = "text", module: str = "") -> Row:
    return Row((Span(sanitize_text(text), role),), module)


def _wrap(text: str, width: int, role: Role = "text") -> list[Row]:
    # Greedy word wrapping with a grapheme-safe fallback for uninterrupted text.
    # Cache the pending width rather than remeasuring a growing paragraph.
    rows = []
    pending = ""
    used = 0
    for token in re.findall(r"\S+|\s+", sanitize_text(text)):
        cells = cell_width(token)
        if pending and used + cells > width:
            rows.append(_line(pending.rstrip(), role))
            pending, used = "", 0
        if not pending and token.isspace():
            continue
        if cells > width:
            chunks = [row.text for row in _literal(token, width)]
            rows.extend(_line(chunk, role) for chunk in chunks[:-1])
            pending = chunks[-1] if chunks else ""
            used = cell_width(pending)
        else:
            pending += token
            used += cells
    if pending:
        rows.append(_line(pending.rstrip(), role))
    return rows


def _literal(text: str, width: int) -> list[Row]:
    """Preserve literal whitespace and graphemes, keeping CLI flags atomic."""
    safe = sanitize_text(text)

    def units():
        start = 0
        for match in _FLAG.finditer(safe):
            yield from iter_graphemes(safe[start:match.start()])
            yield match.group()
            start = match.end()
        yield from iter_graphemes(safe[start:])

    rows = []
    parts: list[str] = []
    used = 0
    for unit in units():
        cells = cell_width(unit)
        if cells > width:
            unit = "…" if _FLAG.fullmatch(unit) else "?"
            cells = 1
        if parts and used + cells > width:
            rows.append(_line("".join(parts)))
            parts, used = [], 0
        parts.append(unit)
        used += cells
    if parts or not rows:
        rows.append(_line("".join(parts)))
    return rows


def _clip(text: str, width: int) -> str:
    """Clip without publishing a fragment of an actionable flag."""
    safe = sanitize_text(text)
    if cell_width(safe) <= width:
        return safe
    if width < 1:
        return ""
    prefix = clip_text(safe, width - 1, ellipsis="")
    for match in _FLAG.finditer(safe):
        if match.start() < len(prefix) < match.end():
            prefix = safe[:match.start()]
            break
    return prefix + "…"


def _bounded(text: str, width: int, rows: int) -> tuple[str, bool]:
    """Bound temporary layout work after stripping all untrusted sequences."""
    safe = sanitize_text(text)
    budget = max(1, width * rows)
    if cell_width(safe) <= budget:
        return safe, False
    return _clip(safe, budget), True


def _pack(values: list[str], width: int, role: Role = "text") -> list[Row]:
    """Pack bounded labels horizontally; long individual labels wrap safely."""
    rows = []
    pending = ""
    for value in values:
        value = sanitize_text(value)
        if pending and cell_width(pending) + 3 + cell_width(value) > width:
            rows.extend(_wrap(pending, width, role))
            pending = ""
        pending = f"{pending}   {value}" if pending else value
    if pending:
        rows.extend(_wrap(pending, width, role))
    return rows


def _value(measurement: Measurement) -> str:
    if measurement.availability != "available" or measurement.value is None:
        return "auth required" if measurement.availability == "auth_required" else (
            measurement.availability if measurement.availability != "available" else "unavailable")
    return f"{measurement.value:,g}" if isinstance(measurement.value, float) else f"{measurement.value:,}"


def _window(measurement: Measurement) -> str:
    if measurement.start and measurement.end:
        return f"{measurement.start} – {measurement.end}"
    return "date range unknown"


def _shift(day: date, offset: int) -> date:
    return date.fromordinal(min(date.max.toordinal(), max(1, day.toordinal() + offset)))


def _coverage(measurement: Measurement, *, compact: bool = False) -> str:
    parts = []
    selected = not measurement.complete_profile
    if measurement.sample_size is not None:
        count = str(measurement.sample_size)
        if measurement.eligible_repositories is not None:
            count += f"/{measurement.eligible_repositories}"
        parts.append(f"{count} selected repos" if compact and selected else f"{count} repos scanned")
    if selected and not (compact and measurement.sample_size is not None):
        parts.append("selected repos" if measurement.sample_size is not None else "profile coverage unknown")
    if measurement.coverage != "complete" and not (selected and measurement.sample_size is None and measurement.coverage == "unknown"):
        parts.append(measurement.coverage)
    if measurement.failed:
        parts.append(f"{measurement.failed} failed")
    if measurement.missing:
        parts.append(f"{measurement.missing} missing")
    return " · ".join(parts)


def _age(created: object, reference: date) -> str | None:
    if not isinstance(created, str):
        return None
    try:
        joined = date.fromisoformat(created[:10])
    except ValueError:
        return None
    if joined > reference:
        return None
    elapsed = (reference - joined).days
    if elapsed >= 365:
        years = elapsed // 365
        return f"{years} year{'s' if years != 1 else ''} on platform"
    if elapsed >= 30:
        months = elapsed // 30
        return f"{months} month{'s' if months != 1 else ''} on platform"
    return f"{elapsed} day{'s' if elapsed != 1 else ''} on platform"


def _identity(content: ProfileIdentity, width: int, rows: int, details: bool) -> tuple[list[Row], bool]:
    name = content.display_name or (f"@{content.username}" if content.username else content.provider)
    name, condensed = (name, False) if details else _bounded(name, width, 2)
    result = _wrap(name, width, "identity")
    provider = {"github": "GitHub", "gitlab": "GitLab", "bitbucket": "Bitbucket",
                "gitea": "Gitea", "forgejo": "Forgejo", "codeberg": "Codeberg"}.get(content.provider, content.provider)
    try:
        host = urlsplit(content.instance).hostname
    except ValueError:
        host = None
    if host and content.provider in {"gitea", "forgejo", "gitlab"}:
        provider += f" · {host}"
    handle = f"@{content.username} · " if content.username and content.display_name else ""
    result.extend(_wrap(handle + provider, width, "muted"))
    if content.biography:
        limit = 1 if rows <= 20 else 2 if rows <= 30 else 4
        bio, shortened = (content.biography, False) if details else _bounded(content.biography, width, limit + 1)
        condensed |= shortened
        biography = _wrap(bio, width)
        if not details and len(biography) > limit:
            biography = biography[:limit]
            biography[-1] = _line(_clip(biography[-1].text.rstrip("… ") + " …", width))
            condensed = True
        result.extend(biography)
    metadata = []
    for value in (content.location, content.company, content.website):
        if value:
            value, shortened = (value, False) if details else _bounded(value, width, 2)
            condensed |= shortened
            metadata.append(value)
    metadata_rows = _pack(metadata, width, "muted")
    if not details and rows <= 20 and len(metadata_rows) > 1:
        metadata_rows = metadata_rows[:1]
        condensed = True
    result.extend(metadata_rows)
    return result, condensed


def _metrics(section: PresentationSection, content: MetricGroup, width: int, reference: date) -> tuple[list[Row], int]:
    labels = {"public_repos": "public repos", "public_gists": "gists", "followers": "followers", "following": "following"}
    values: list[str] = []
    secondary: list[str] = []
    for metric in content.metrics:
        label = labels.get(metric.identifier, metric.label.lower())
        if metric.identifier == "public_repos" and metric.measurement.scope not in {"public owned repositories", "public_repos", ""}:
            label = metric.measurement.scope
        unit = ""
        if metric.measurement.value is not None and metric.measurement.unit not in {"count", "repositories"}:
            unit = f" {metric.measurement.unit}"
        if section.name == "stats" and metric.identifier not in labels and metric.measurement.scope:
            label += f" ({metric.measurement.scope})"
        target = secondary if section.name == "stats" and metric.identifier not in {"public_repos", "followers"} else values
        target.append(f"{_value(metric.measurement)}{unit} {label}")
    result = _pack(values, width, "stat")
    primary_rows = len(result)
    if section.name == "stats" and type(section.raw_data) in (dict, MappingProxyType):
        user = section.raw_data.get("user")
        if type(user) in (dict, MappingProxyType):
            age = _age(user.get("created_at"), reference)
            if age:
                secondary.append(age)
    result.extend(_pack(secondary, width, "muted"))
    if section.name == "streaks":
        measurement = section.measurements.get("contributions")
        if measurement:
            coverage = f" · {measurement.coverage} coverage" if measurement.coverage != "complete" else ""
            result.extend(_wrap(f"Observed window: {_window(measurement)}{coverage}", width, "muted"))
    return result, max(1, primary_rows)


def _languages(content: LanguageDistribution, width: int, height: int, details: bool) -> tuple[list[Row], bool]:
    measurement = content.measurement
    if measurement.availability != "available":
        return _wrap(f"Languages: {_value(measurement)}", width, "notice"), False
    entries = content.selected
    limit = 2 if height <= 15 else 3 if height <= 24 else 5 if height <= 30 else len(entries)
    shown = entries if details else entries[:limit]
    # A user's module limit still selects entries. Full totals only establish the
    # denominator, never implicitly override that selection or become a top-N sum.
    header = "Languages · bytes" if measurement.unit == "bytes" else (
        "Languages · repository prevalence" if "prevalence" in measurement.scope else
        "Languages · primary-language repos" if measurement.unit == "repositories" else f"Languages · {measurement.unit}")
    compact = width < 52 or (height <= 20 and not details)
    if compact and measurement.unit == "repositories":
        header = "Language prevalence · repos" if "prevalence" in measurement.scope else "Primary languages · repos"
    result = _wrap(header, width, "heading")
    scope = _coverage(measurement, compact=compact)
    if scope:
        result.extend(_wrap(scope, width, "muted"))
    denominator = measurement.denominator
    fractions = denominator is not None and denominator > 0 and measurement.unit in {"bytes", "repositories"}
    name_width = min(18, max(5, width // 3), max((cell_width(e.language) for e in shown), default=5))
    suffixes = []
    for entry in shown:
        value = f"{entry.value:g}"
        if measurement.unit == "bytes" and fractions:
            suffix = f"{entry.value / denominator * 100:.1f}%"  # type: ignore[operator]
        elif measurement.unit == "repositories":
            suffix = f"{value}/{denominator:g} repos" if fractions else f"{value} repos"
        else:
            suffix = f"{value} {measurement.unit}"
        suffixes.append(suffix)
    suffix_width = max((cell_width(suffix) for suffix in suffixes), default=0)
    bar_width = min(16, max(8, width // 4), width - name_width - suffix_width - 4)
    compact_values = []
    clipped_name = False
    for entry, suffix in zip(shown, suffixes):
        if height <= 20 and not details and width >= 40:
            compact_values.append(f"{entry.language} {suffix}")
            continue
        if not compact and fractions and bar_width >= 8:
            ratio = min(1.0, max(0.0, entry.value / denominator))  # type: ignore[operator]
            filled = round(ratio * bar_width)
            label = _clip(entry.language, name_width)
            if cell_width(entry.language) > name_width:
                if details:
                    result.extend(_wrap(entry.language, width))
                else:
                    clipped_name = True
            pad = " " * (name_width - cell_width(label))
            empty = bar_width - filled
            track = ("· " * ((empty + 1) // 2))[:empty]
            result.append(Row((Span(label + pad + "  "), Span("━" * filled, "accent"),
                               Span(track, "track"), Span("  " + " " * (suffix_width - cell_width(suffix)) + suffix))))
        else:
            if cell_width(entry.language) <= name_width and name_width + cell_width(suffix) + 2 <= width:
                result.append(_line(entry.language + " " * (name_width - cell_width(entry.language) + 2) + suffix))
            else:
                result.extend(_wrap(f"{entry.language}  {suffix}", width))
    result.extend(_pack(compact_values, width))
    if not entries:
        result.extend(_wrap("No language measurements returned", width, "muted"))
    if details and measurement.reason:
        result.extend(_wrap(measurement.reason, width, "notice"))
    return result, clipped_name or len(shown) < len(entries)


def _contributions(content: ContributionActivity, width: int, height: int, details: bool) -> tuple[list[Row], bool]:
    observations = content.calendar_days if details else content.days
    measurement = content.calendar_measurement if details else content.measurement
    amount = f"{_value(measurement)} " if measurement.availability == "available" and measurement.value is not None else ""
    summary = (height <= 15 or width < 40) and not details
    heading = f"Activity · {amount if summary else ''}{measurement.unit}"
    if width >= 52:
        result = _wrap(heading + f" · {measurement.coverage} coverage", width, "heading")
    else:
        result = _wrap(heading, width, "heading")
        result.extend(_wrap(f"{measurement.coverage} coverage", width, "muted"))
    if measurement.availability != "available":
        result.extend(_wrap(_value(measurement), width, "notice"))
        return result, False
    if not observations:
        result.extend(_wrap("No dated observations · coverage unknown", width, "notice"))
        return result, False
    if summary:
        result.extend(_wrap(_window(measurement), width, "muted"))
        return result, True  # The dated calendar remains available in details.
    counts = {day.date: day.count for day in observations}
    dates = tuple(counts)
    first, last = observations[0].date, observations[-1].date
    peak = max((day.count or 0 for day in observations), default=0)
    def glyph(day: date) -> str:
        value = counts.get(day)
        if value is None:
            return "?"
        if value == 0:
            return "·"
        return "▁▂▃▄▅▆▇█"[min(7, max(0, (value * 8 - 1) // max(1, peak)))]
    # Calendar cells are dated positions, not invented zero-count observations.
    # Only bounded visible windows are materialized, even for sparse long ranges.
    calendar = width >= 55 and (height >= 36 or details) and first.toordinal() > 7 and last.toordinal() < date.max.toordinal() - 7
    condensed = not details and observations != content.calendar_days
    if calendar:
        weeks_per_panel = max(1, min(26, (width - 4) // 2))
        window = weeks_per_panel * 7
        start = _shift(first, -((first.weekday() + 1) % 7))
        if not details and (last - start).days >= window:
            start = _shift(last, -((last.weekday() + 1) % 7 + (weeks_per_panel - 1) * 7))
            condensed = True
        while start <= last:
            end = min(last, _shift(start, window - 1))
            result.extend(_wrap(f"Shown: {max(start, first)} – {end}", width, "muted"))
            for offset, label in enumerate(("Su", "Mo", "Tu", "We", "Th", "Fr", "Sa")):
                values = []
                cursor = start + timedelta(days=offset)
                while cursor <= end:
                    values.append(glyph(cursor) if cursor >= first else " ")
                    cursor += timedelta(days=7)
                result.append(_line(label + "  " + " ".join(values), "accent"))
            if end == last:
                break
            start = _shift(start, window)
            if details and (index := bisect_right(dates, end)) < len(dates) and (dates[index] - start).days >= window:
                next_start = _shift(dates[index], -((dates[index].weekday() + 1) % 7))
                result.extend(_wrap(f"Unknown dates: {start} – {_shift(next_start, -1)}", width, "notice"))
                start = next_start
    else:
        count = max(1, min(32, width * 2 // 3))
        start = max(first, _shift(last, -(count - 1)))
        condensed |= not details and start > first
        result.extend(_wrap(f"Shown: {first if details else start} – {last}", width, "muted"))
        cursor = first if details else start
        while cursor <= last:
            end = min(last, _shift(cursor, count - 1))
            if details and cursor != start:
                result.extend(_wrap(f"{cursor} – {end}", width, "muted"))
            result.append(_line("".join(glyph(cursor + timedelta(days=i)) for i in range((end - cursor).days + 1)), "accent"))
            if not details or end == last:
                break
            cursor = _shift(end, 1)
            if (index := bisect_right(dates, end)) < len(dates) and (dates[index] - cursor).days >= count:
                result.extend(_wrap(f"Unknown dates: {cursor} – {_shift(dates[index], -1)}", width, "notice"))
                cursor = dates[index]
    legend = f"· zero  ? unknown  ▁–█ 1–{peak}" if peak else "· zero  ? unknown"
    result.extend(_wrap(legend, width, "muted"))
    total = f"{_value(measurement)} in window · " if measurement.value is not None else "Window: "
    result.extend(_wrap(total + _window(measurement), width, "muted"))
    return result, condensed


def _section(section: PresentationSection, width: int, height: int, details: bool, reference: date) -> _Section:
    content = section.content
    condensed = False
    compact: list[Row] = []
    priority, minimum = 4, 0
    if isinstance(content, ProfileIdentity):
        rows, condensed = _identity(content, width, height, details)
        priority, minimum = 0, 2
    elif isinstance(content, MetricGroup):
        rows, primary_rows = _metrics(section, content, width, reference)
        if section.name == "stats":
            priority, minimum = 1, primary_rows
        else:
            rows = _wrap(section.title, width, "heading") + rows
    elif isinstance(content, LanguageDistribution):
        rows, condensed = _languages(content, width, height, details)
        priority, minimum = 2, min(3, len(rows))
    elif isinstance(content, ContributionActivity):
        rows, condensed = _contributions(content, width, height, details)
        if not details:
            compact, _ = _contributions(content, width, min(height, 15), False)
        priority, minimum = 3, len(compact) if compact else 2
    elif isinstance(content, RepositoryList):
        rows = _wrap(section.title, width, "heading")
        limit = len(content.repositories) if details else (2 if height <= 24 else 4)
        for repo in content.repositories[:limit]:
            stars = next((metric.measurement for metric in repo.metrics if metric.identifier == "stars"), Measurement(availability="unavailable"))
            suffix = f"{_value(stars)} stars" + (f" · {repo.language}" if repo.language else "")
            if width < 52 and cell_width(f"{repo.name}  {suffix}") > width:
                rows.extend(_wrap(repo.name, width))
                rows.extend(_wrap(suffix, width, "muted"))
            else:
                rows.extend(_wrap(f"{repo.name}  {suffix}", width))
            if repo.description and (details or height >= 36):
                rows.extend(_wrap(repo.description, width, "muted"))
            if details and repo.url:
                rows.extend(_wrap(repo.url, width, "muted"))
        condensed = limit < len(content.repositories) or (not details and any(repo.description or repo.url for repo in content.repositories))
        # Pinned gists/unadapted rows must retain their line fallback. Do not
        # interpret arbitrary plugin objects or recover metrics from prose.
        if isinstance(section.raw_data, tuple) and len(section.raw_data) != len(content.repositories):
            rows.extend(_wrap("Other pinned content (module text)", width, "muted"))
            for line in section.lines:
                rows.extend(_literal(line, width))
        if content.measurement.scope and content.measurement.scope != "pinned repositories":
            rows.extend(_wrap(content.measurement.scope, width, "muted"))
    elif isinstance(content, RecentActivity):
        rows = _wrap(section.title + " · " + content.measurement.scope, width, "heading")
        limit = len(content.events) if details else (2 if height <= 24 else 4)
        for event in content.events[:limit]:
            fields = [field for field in (event.occurred_at, event.event_type, event.repository) if field]
            rows.extend(_wrap(" · ".join(fields), width))
        condensed = limit < len(content.events)
    else:
        rows = _wrap(section.title, width, "heading")
        cap = max(2, height // 3)
        for index, line in enumerate(section.lines):
            line, shortened = (line, False) if details else _bounded(line, width, cap)
            condensed |= shortened
            rows.extend(_literal(line, width))
            if not details and len(rows) > cap:
                condensed |= len(rows) > cap or index + 1 < len(section.lines)
                rows = rows[:cap]
                break
        if any(m.availability != "available" for m in section.measurements.values()):
            priority, minimum = 2, min(2, len(rows))
    # Preserve meaningful metadata absent from display lines. Specialized views
    # carry their own coverage; generic sections and metrics need notices too.
    if not isinstance(content, (LanguageDistribution, ContributionActivity, RepositoryList)):
        notices = []
        for measurement in section.measurements.values():
            if measurement.availability != "available" and content is not None:
                notices.append(measurement.reason or _value(measurement))
            streak_window = section.measurements.get("contributions") if section.name == "streaks" else None
            already_shown = streak_window is not None and (
                measurement.start, measurement.end, measurement.coverage) == (
                streak_window.start, streak_window.end, streak_window.coverage)
            if measurement.coverage != "complete" and measurement.start and measurement.end and not already_shown:
                notices.append(f"{_window(measurement)} · {measurement.coverage} coverage")
        for notice in dict.fromkeys(notices):
            rows.extend(_wrap(notice, width, "notice"))
    # All text is already safe; attach module identity without a second pass over
    # source data or re-evaluating any modules/plugins.
    return _Section(section.name, tuple(Row(row.spans, section.name) for row in rows), priority, minimum, condensed,
                    tuple(Row(row.spans, section.name) for row in compact))


def _fit(sections: list[_Section], width: int, budget: int, details: bool) -> tuple[tuple[Row, ...], bool, tuple[str, ...]]:
    condensed = any(section.condensed for section in sections)
    sizes = [len(section.rows) for section in sections]
    if not details:
        condensed |= sum(sizes) > budget
    message = next(text for text in ("More enabled content: --details", "Run --details", "--details", "…")
                   if cell_width(text) <= width)
    footer = _line(message, "notice")
    reserve = 1 if condensed and not details else 0
    # Spacing is the first thing to give up. Then shorten lower-priority sections,
    # retaining the caller's order rather than sorting the visible sections.
    spacing = max(0, len(sections) - 1) if details else min(
        max(0, len(sections) - 1), max(0, budget - sum(sizes) - reserve))
    if condensed and not details and budget >= 18:
        preferred_count = sum(index > 0 and section.name in {"languages", "contributions"}
                        for index, section in enumerate(sections))
        room = max(0, budget - reserve - sum(min(len(s.rows), s.minimum) for s in sections))
        spacing = max(spacing, min(preferred_count, room))
    if not details:
        excess = max(0, sum(sizes) + spacing + reserve - budget)
        order = sorted(range(len(sections)), key=lambda i: (sections[i].priority, i), reverse=True)
        for floor in (True, False):
            for index in order:
                # A chart and legend are one unit. After lower-priority content
                # gives way, replace a chart with its dated summary if necessary.
                section = sections[index]
                if excess and floor and section.compact and len(section.compact) < sizes[index]:
                    excess = max(0, excess - sizes[index] + len(section.compact))
                    sections[index] = _Section(section.name, section.compact, section.priority, section.minimum, True)
                    sizes[index] = len(section.compact)
                minimum = min(sizes[index], sections[index].minimum) if floor else 0
                removed = min(excess, max(0, sizes[index] - minimum))
                if removed and not floor and section.name == "contributions":
                    removed = sizes[index]  # Never detach a total from its dates.
                if removed and sections[index].minimum == 0 and sizes[index] - removed == 1:
                    removed += 1  # Avoid leaving a secondary heading alone.
                sizes[index] -= removed
                excess = max(0, excess - removed)
                if not excess:
                    break
            if not excess:
                break
        spacing = min(max(0, sum(size > 0 for size in sizes) - 1), max(0, budget - sum(sizes) - reserve))
    rows: list[Row] = []
    omitted = []
    boundaries = [index for index, size in enumerate(sizes) if size][1:]
    preferred = [index for index in boundaries if sections[index].name in {"languages", "contributions"}]
    gaps = set((preferred + [index for index in boundaries if index not in preferred])[:spacing])
    for index, (section, size) in enumerate(zip(sections, sizes)):
        if not size:
            if section.rows:
                omitted.append(section.name)
            continue
        if index in gaps:
            rows.append(_line(""))
        rows.extend(section.rows[:size])
    if reserve:
        rows.append(footer)
    return tuple(rows), condensed and not details, tuple(omitted)


def avatar_may_fit(viewport: Viewport, preferences: Preferences) -> bool:
    """Cheap asset gate; actual source geometry/content still decide allocation."""
    columns = max(1, viewport.columns)
    margin = min(max(0, preferences.margin), max(0, (columns - min(20, columns)) // 2))
    return preferences.avatar and preferences.avatar_width >= 8 and columns - 2 * margin >= 45 and viewport.rows >= 14


def plan_profile(document: ProfileDocument, viewport: Viewport, preferences: Preferences | None = None,
                 avatar: AvatarGeometry | None = None, *, reference_date: date) -> LayoutPlan:
    """Plan one frame from immutable semantic inputs and an explicit UTC date."""
    preferences = preferences or Preferences()
    columns, height = max(1, viewport.columns), max(1, viewport.rows)
    margin = min(max(0, preferences.margin), max(0, (columns - min(20, columns)) // 2))
    usable = max(1, columns - 2 * margin)
    budget = max(1, height - 2)
    composition: Composition = "text"
    avatar_width = avatar_rows = 0
    text_width = usable
    if avatar_may_fit(viewport, preferences) and avatar and avatar.width > 0 and avatar.height > 0:
        max_rows = min(16, max(4, budget // (3 if preferences.layout == "stack" else 2)))
        if preferences.details:
            max_rows = min(16, max_rows)
        cap = min(max(1, preferences.avatar_width), 34, max(1, usable // 3))
        # A bounded scan (at most 34 columns); never render or download a candidate.
        candidates = [w for w in range(8, cap + 1) if avatar.rows_at(w, preferences.avatar_style) <= max_rows]
        if candidates:
            avatar_width = candidates[-1]
            avatar_rows = avatar.rows_at(avatar_width, preferences.avatar_style)
            if preferences.layout == "split" and usable - avatar_width - 3 >= 32:
                composition = "split"
                text_width = usable - avatar_width - 3
            elif preferences.layout == "stack" or usable < 70:
                composition = "stack"
            else:
                avatar_width = avatar_rows = 0
    if composition == "text":
        avatar_width = avatar_rows = 0
    text_budget = max(1, budget - avatar_rows - 1) if composition == "stack" else budget
    sections = [_section(section, text_width, height, preferences.details, reference_date) for section in document.sections]
    # A stacked avatar must not crowd out the profile's primary information.
    # Fall back to text rather than reversing an explicit stack preference.
    primary = sum(min(len(s.rows), s.minimum) for s in sections)
    if composition == "stack" and not preferences.details and primary + 2 > text_budget:
        composition, avatar_width, avatar_rows, text_budget = "text", 0, 0, budget
    rows, condensed, omitted = _fit(sections, text_width, text_budget, preferences.details)
    if avatar_width and avatar is not None:
        content_cap = max(4, len(rows)) if composition == "split" else max(3, len(rows) // 2)
        if avatar_rows > content_cap:
            widths = [w for w in range(8, avatar_width + 1) if avatar.rows_at(w, preferences.avatar_style) <= content_cap]
            avatar_width = widths[-1] if widths else 0
            avatar_rows = avatar.rows_at(avatar_width, preferences.avatar_style) if avatar_width else 0
            if not avatar_width:
                composition = "text"
            text_width = usable - avatar_width - 3 if composition == "split" else usable
            text_budget = max(1, budget - avatar_rows - 1) if composition == "stack" else budget
            # At most one content reflow for short profiles; never another asset
            # load or image encoding, and no candidate-by-candidate text layouts.
            sections = [_section(section, text_width, height, preferences.details, reference_date) for section in document.sections]
            rows, condensed, omitted = _fit(sections, text_width, text_budget, preferences.details)
    return LayoutPlan(viewport, composition, text_width, margin, avatar_width, avatar_rows, rows, condensed, omitted)
