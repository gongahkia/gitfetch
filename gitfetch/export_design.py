"""Focused card scene and shared semantic layout; no output, requests or probes."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from PIL import Image

from gitfetch.design import HEX_COLOR, resolve_colors, validate_colors
from gitfetch.export_fonts import clip, length, wrap
from gitfetch.presentation import (
    ContributionActivity,
    LanguageDistribution,
    MetricGroup,
    ProfileDocument,
    ProfileIdentity,
    RecentActivity,
    RepositoryList,
)
from gitfetch.terminal_text import sanitize_text

# Concrete fallbacks for terminal palette entries; role resolution stays in T06A.
SYSTEM_COLORS = ('#000000', '#cc0000', '#4e9a06', '#c4a000', '#3465a4', '#75507b', '#06989a', '#d3d7cf',
                 '#555753', '#ef2929', '#8ae234', '#fce94f', '#729fcf', '#ad7fa8', '#34e2e2', '#eeeeec')
BACKGROUND = {'nord': '#2e3440', 'dracula': '#282a36', 'gruvbox': '#282828',
              'catppuccin-mocha': '#1e1e2e', 'catppuccin-macchiato': '#24273a',
              'catppuccin-frappe': '#303446', 'catppuccin-latte': '#eff1f5', 'solarized': '#002b36',
              'tokyonight': '#1a1b26', 'rose-pine': '#191724', 'everforest': '#2d353b', 'mono': '#111111'}


@dataclass(frozen=True)
class Text:
    x: float
    y: float  # top of a line box; both backends use the same font ascent
    text: str
    size: int
    color: str
    width: float
    strong: bool = False


@dataclass(frozen=True)
class Rectangle:
    x: float
    y: float
    width: float
    height: float
    color: str
    radius: float = 0


@dataclass(frozen=True)
class Picture:
    x: float
    y: float
    width: float
    height: float
    image: Image.Image


@dataclass(frozen=True)
class ExportPlan:
    width: int
    height: int
    colors: dict[str, str]
    nodes: tuple[Text | Rectangle | Picture, ...]
    condensed: bool


def dimensions(display: dict[str, Any]) -> tuple[int, int]:
    width, height = display.get('card_width', 720), display.get('card_height', 360)
    if (isinstance(width, bool) or isinstance(height, bool) or not isinstance(width, int) or not isinstance(height, int)
            or not 128 <= width <= 4096 or not 96 <= height <= 4096 or width * height > 8_000_000):
        raise ValueError('card dimensions require 128–4096 × 96–4096 pixels, at most 8 million pixels')
    return width, height


def export_colors(display: dict[str, Any], *, card: bool = False) -> dict[str, str]:
    overrides = display.get('colors', {})
    validate_colors(overrides)
    theme = display.get('theme', 'default')
    light = theme == 'catppuccin-latte'
    foreground = '#303446' if light else '#e6edf3'
    # Cards have a known surface. Keep terminal SVG's established palette while
    # resolving a restrained default through the same semantic role system.
    defaults = ({'identity': '#e6edf3', 'stat': '#e6edf3', 'heading': '#b3c7df',
                 'handle': '#a5b4c6', 'muted': '#a5b4c6', 'accent': '#86b7ad',
                 'notice': '#a5b4c6', 'warning': '#e0ba81'} if card and theme == 'default' else {})
    if 'accent' in overrides:
        defaults = {key: value for key, value in defaults.items() if key not in {'notice', 'warning'}}
    colors = {}
    for role, color in resolve_colors(theme, {**defaults, **overrides}).items():
        colors[role] = ('#{:02x}{:02x}{:02x}'.format(*color.rgb) if color.rgb is not None else
                        SYSTEM_COLORS[color.terminal_index] if color.terminal_index is not None else foreground)
    colors['background'] = BACKGROUND.get(theme, '#0d1117')
    if card and theme == 'default':
        colors['background'] = '#141a23'
    colors['surface'] = '#dce0e8' if light else '#252d38'
    # Existing custom card surfaces/foreground remain usable. Semantic overrides
    # have priority over the corresponding old palette keys.
    legacy = display.get('card_palette', {}) or {}
    if not isinstance(legacy, dict) or any(k not in {'background', 'surface', 'border', 'text', 'muted', 'accent', 'good', 'warning'}
                                          or not isinstance(v, str) or not HEX_COLOR.fullmatch(v) for k, v in legacy.items()):
        raise ValueError('card_palette requires known keys and six-digit hexadecimal colors')
    protected = set(overrides)
    if 'accent' in protected:
        protected.update({'language', 'contribution', 'notice', 'warning'})
    inherited = {'text': ('text', 'identity', 'stat'), 'muted': ('muted',),
                 'accent': ('accent', 'handle', 'language', 'contribution'),
                 'warning': ('warning', 'notice'), 'good': ('contribution',)}
    for key, value in legacy.items():
        for role in inherited.get(key, (key,)):
            if role not in protected:
                colors[role] = value
    if theme == 'mono':
        colors = {key: ('#111111' if key == 'background' else '#333333' if key == 'surface' else '#eeeeee')
                  for key in colors}
    return colors


def measurement_text(measurement) -> str:
    if measurement.availability != 'available' or measurement.value is None:
        return 'authentication required' if measurement.availability == 'auth_required' else (
            measurement.availability if measurement.availability != 'available' else 'unavailable')
    return f'{measurement.value:,g}' if isinstance(measurement.value, float) else f'{measurement.value:,}'


def coverage_text(measurement) -> str:
    parts = [measurement.coverage + ' coverage']
    if measurement.sample_size is not None:
        count = str(measurement.sample_size)
        if measurement.eligible_repositories is not None:
            count += '/' + str(measurement.eligible_repositories)
        parts.append(count + ' selected repos')
    if measurement.failed:
        parts.append(str(measurement.failed) + ' failed')
    if measurement.missing:
        parts.append(str(measurement.missing) + ' missing')
    return ' · '.join(parts)


class _Builder:
    def __init__(self, display: dict[str, Any], image: Image.Image | None, *, colors: dict[str, str] | None = None) -> None:
        self.width, self.height = dimensions(display)
        self.colors = export_colors(display, card=True) if colors is None else colors
        self.preset = display.get('visual_preset', 'balanced')
        if self.preset not in {'balanced', 'compact', 'showcase'}:
            raise ValueError('invalid visual preset')
        self.small = self.width < 500 or self.height < 240
        self.pad = 16 if self.small or self.preset == 'compact' else 24 if self.height <= 360 else 28
        self.body = 11 if self.small else 12 if self.preset == 'compact' else 13 if self.height <= 360 else 14
        self.gap = 7 if self.preset == 'compact' else 10 if self.height <= 360 else 12
        self.bottom = self.height - self.pad - 24
        self.y = float(self.pad)
        self.nodes: list[Text | Rectangle | Picture] = []
        self.condensed = False
        self.image = image

    def text(self, text, *, role='text', size=None, x=None, width=None, strong=False):
        size = size or self.body
        x = self.pad if x is None else x
        width = self.width - self.pad - x if width is None else width
        safe = sanitize_text(text[:4096])
        fitted = clip(safe, width, size)
        self.condensed |= fitted != safe
        self.nodes.append(Text(x, self.y, fitted, size, self.colors[role], width, strong))

    def line(self, text, role='text', size=None):
        size = size or self.body
        if self.y + size + 6 > self.bottom:
            self.condensed = True
            return False
        self.text(text, role=role, size=size)
        self.y += size + 6
        return True

    def paragraph(self, text, *, role='text', limit=2, x=None, width=None, size=None):
        size = size or self.body
        width = self.width - 2*self.pad if width is None else width
        lines, shortened = wrap(text, width, size, limit)
        self.condensed |= shortened
        for line in lines:
            if self.y + size + 6 > self.bottom:
                self.condensed = True
                break
            self.text(line, role=role, size=size, x=x, width=width)
            self.y += size + 6

    def header(self, name, handle, biography='', metadata=''):
        start = self.y
        preferred, maximum, fraction = {'balanced': (104, 136, .30), 'compact': (80, 112, .28),
                                        'showcase': (120, 168, .32)}[self.preset]
        width_fraction = .19 if self.preset == 'showcase' else .14 if self.preset == 'compact' else .15
        avatar = min(maximum, max(preferred, int(self.width*width_fraction)), int(self.height*fraction))
        avatar = min(avatar, max(0, int(self.bottom - self.y - 30)))
        x = self.pad
        if self.image is not None and avatar >= 32 and self.width >= 300:
            # Contain, never crop or stretch, preserving transparent source canvas.
            scale = min(avatar/self.image.width, avatar/self.image.height)
            w, h = self.image.width*scale, self.image.height*scale
            self.nodes.append(Picture(x+(avatar-w)/2, self.y+(avatar-h)/2, w, h, self.image))
            x += avatar + self.gap
        else:
            avatar = 0
        width = self.width - self.pad - x
        title_size = 16 if self.small else 21 if self.preset == 'compact' else 30 if self.preset == 'showcase' else 25
        self.text(name, role='identity', size=title_size, x=x, width=width, strong=True)
        self.y += title_size + 5
        if self.y+self.body+6 <= self.bottom:
            self.text(handle, role='handle', x=x, width=width)
            self.y += self.body + 6
        if biography and not self.small:
            self.paragraph(biography, role='text', limit=1 if self.height <= 360 or self.preset == 'compact' else 2,
                           x=x, width=width)
        elif biography:
            self.condensed = True
        if metadata and not self.small:
            self.paragraph(metadata, role='muted', limit=1, x=x, width=width, size=max(10, self.body-1))
        elif metadata:
            self.condensed = True
        self.y = max(self.y, start+avatar) + self.gap

    def finish(self):
        self.y = self.height - self.pad - 15
        if self.condensed:
            self.text('More selected content omitted', role='notice', size=9,
                      width=self.width - 2*self.pad - 64)
        brand = 'gitfetch'
        self.text(brand, role='muted', size=10, x=self.width-self.pad-length(brand, 10), width=52)
        return ExportPlan(self.width, self.height, self.colors, tuple(self.nodes), self.condensed)


def plan_profile_card(document: ProfileDocument, display: dict[str, Any], image: Image.Image | None = None,
                      *, reference_date: date) -> ExportPlan:
    """One semantic/layout decision stream for SVG and PNG; font metrics are local."""
    builder = _Builder(display, image)
    identity = document.identity
    name = (identity.display_name or identity.username) if identity else document.username
    handle = '@' + (document.username or 'unknown') + ' · ' + document.provider
    if identity and identity.instance:
        from urllib.parse import urlsplit
        try:
            host = urlsplit(identity.instance).hostname
        except ValueError:
            host = None
        if host:
            handle += ' · ' + host
    metadata = ' · '.join(v for v in (identity.location, identity.company, identity.website) if v) if identity else ''
    builder.header(name or 'Profile', handle, identity.biography or '' if identity else '', metadata)
    sections = [s for s in document.sections if not isinstance(s.content, ProfileIdentity)]
    _flow_sections(builder, display, sections, _draw_section,
                   first_wide=bool(sections and isinstance(sections[0].content, MetricGroup)))
    builder.condensed |= len(sections) > 128
    return builder.finish()


def _flow_sections(builder, display, sections, draw, *, first_wide=False):
    columns = None
    use_columns = builder.width >= 600 and builder.height >= 300
    for index, section in enumerate(sections[:128]):
        if not use_columns or index == 0 and first_wide:
            draw(builder, section, display)
            continue
        if columns is None:
            columns = [builder.y, builder.y]
        column = min(range(2), key=lambda c: columns[c])
        column_width = (builder.width-2*builder.pad-builder.gap)/2
        local = _Builder({**display, 'card_width': int(column_width+2*builder.pad)}, None, colors=builder.colors)
        local.pad, local.body, local.small = builder.pad, builder.body, builder.small
        local.gap = builder.gap
        local.y, local.bottom = columns[column], builder.bottom
        draw(local, section, display)
        offset = column*(column_width+builder.gap)
        builder.nodes.extend(replace(node, x=node.x+offset) for node in local.nodes)
        builder.condensed |= local.condensed
        columns[column] = local.y


def _draw_section(builder, section, display):
    content = section.content
    minimum = builder.body*2+14
    if isinstance(content, LanguageDistribution) and content.selected and content.measurement.availability == 'available':
        minimum = builder.body*2+28  # heading, coverage, at least one entry
    if builder.y + minimum > builder.bottom:
        builder.condensed = True
        return
    if isinstance(content, MetricGroup):
        values = []
        for metric in content.metrics:
            m = metric.measurement
            label = metric.label.lower()
            if section.name == 'stats':
                if metric.identifier == 'public_repos' and m.scope not in {'', 'public owned repositories', 'public_repos'}:
                    label = m.scope
                elif metric.identifier not in {'public_repos', 'followers', 'following', 'public_gists'} and m.scope:
                    label += ' (' + m.scope + ')'
            unit = ' ' + m.unit if m.unit not in {'count', 'repositories'} else ''
            values.append(measurement_text(m) + unit + ' ' + label)
        builder.line(section.title, 'heading')
        if builder.preset == 'compact':
            builder.paragraph(' · '.join(values), role='stat', limit=2)
        else:
            # Use measured widths for a short group; equal cells otherwise
            # waste a whole row when just one label is longer than the others.
            available = builder.width-2*builder.pad
            widths = [length(value, builder.body)+12 for value in values]
            one_row = bool(values) and sum(widths) <= available
            n = len(values) if one_row else (2 if builder.small else 3)
            column = (builder.width-2*builder.pad)/n
            for i in range(0, len(values), n):
                if builder.y+builder.body+6 > builder.bottom:
                    builder.condensed = True
                    break
                for j, value in enumerate(values[i:i+n]):
                    x = builder.pad+sum(widths[:j]) if one_row else builder.pad+j*column
                    width = widths[j]-10 if one_row else column-10
                    builder.text(value, role='stat', x=x, width=width)
                builder.y += builder.body+6
        notices = []
        for measurement in section.measurements.values():
            if measurement.start and measurement.end:
                notices.append(f'Observed: {measurement.start} – {measurement.end} · {measurement.coverage}')
            elif measurement.sample_size is not None:
                notices.append(measurement.scope + ' · ' + coverage_text(measurement))
        for notice in dict.fromkeys(notices):
            builder.line(notice, 'muted', 10)
    elif isinstance(content, LanguageDistribution):
        m = content.measurement
        builder.line(('Language prevalence · repos' if 'prevalence' in m.scope else 'Primary languages · repos')
                     if m.unit == 'repositories' else 'Languages · ' + m.unit, 'heading')
        builder.line(coverage_text(m), 'muted', 10)
        if m.availability != 'available':
            builder.line(measurement_text(m), 'warning')
        else:
            limit = min(256, len(content.selected)) if display.get('details') else 5
            for entry in content.selected[:limit]:
                if builder.y + builder.body+6 > builder.bottom:
                    builder.condensed = True
                    break
                denominator = m.denominator
                ratio = entry.value/denominator if denominator and denominator > 0 else None
                suffix = (f'{ratio*100:.1f}%' if m.unit == 'bytes' and ratio is not None else
                          f'{entry.value:g}/{denominator:g} repos' if m.unit == 'repositories' and ratio is not None else
                          f'{entry.value:g} {m.unit}')
                builder.text(entry.language + '  ' + suffix, role='text', width=(builder.width-2*builder.pad)*0.60)
                if ratio is not None and builder.width-2*builder.pad >= 220:
                    x = builder.pad + (builder.width-2*builder.pad)*0.63
                    w = (builder.width-2*builder.pad)*0.37
                    builder.nodes.append(Rectangle(x, builder.y+5, w, 5, builder.colors['surface'], 2))
                    if ratio > 0:
                        fill_width = min(1, max(0, ratio))*w
                        # Pillow 10 cannot round a five-pixel-high strip whose
                        # width falls between its corner/interior pixel bounds.
                        # Keep the exact proportion, using square tiny fills in
                        # the shared scene so SVG and PNG make the same choice.
                        builder.nodes.append(Rectangle(x, builder.y+5, fill_width, 5,
                                                       builder.colors['language'], 2 if fill_width >= 6 else 0))
                builder.y += builder.body+4
            builder.condensed |= len(content.selected) > limit
    elif isinstance(content, ContributionActivity):
        m = content.calendar_measurement if display.get('details') else content.measurement
        days = content.calendar_days if display.get('details') else content.days
        builder.line('Activity · ' + m.unit, 'heading')
        builder.line(f'{measurement_text(m)} · {m.coverage} coverage', 'muted', 10)
        if m.start and m.end:
            builder.line(f'{m.start} – {m.end}', 'muted', 10)
        if m.availability == 'available' and days and builder.y+57 <= builder.bottom:
            capacity = min(42, max(7, int((builder.width-2*builder.pad)//9)))
            first, last = days[0].date, days[-1].date
            # Dated positions include unknown gaps; never infer zero activity.
            from datetime import timedelta
            try:
                first = date.fromisoformat(m.start) if m.start else first
                last = date.fromisoformat(m.end) if m.end else last
            except ValueError:
                first, last = days[0].date, days[-1].date
            first = max(min(first, last), last-timedelta(days=capacity-1))
            builder.line(f'Shown: {first} – {last}', 'muted', 10)
            day_values = {day.date: day.count for day in days if first <= day.date <= last}
            peak = max((value or 0 for value in day_values.values()), default=0)
            count = (last-first).days+1
            step = (builder.width-2*builder.pad)/count
            if builder.y+26 <= builder.bottom:
                for index in range(count):
                    activity_count = day_values.get(first+timedelta(days=index))
                    color = builder.colors['surface'] if activity_count is None or activity_count == 0 else builder.colors['contribution']
                    h = 3 if activity_count is None or activity_count == 0 else 5+15*activity_count/max(1, peak)
                    builder.nodes.append(Rectangle(builder.pad+index*step, builder.y+20-h, max(1, step-3), h, color, 1))
                    if activity_count is None:
                        builder.nodes.append(Text(builder.pad+index*step, builder.y, '?', 9, builder.colors['warning'], step))
                builder.y += 25
                builder.line('? unknown · baseline zero · relative peak', 'muted', 9)
            else:
                builder.condensed = True
        elif days:
            builder.condensed = True
    else:
        builder.line(section.title, 'heading')
        lines = []
        if isinstance(content, RepositoryList):
            for repo in content.repositories[:16]:
                values = [measurement_text(m.measurement)+' '+m.label.lower() for m in repo.metrics]
                lines.append(repo.name + (' · ' + ' · '.join(values) if values else ''))
                if repo.description and builder.preset == 'showcase':
                    lines.append(repo.description)
        elif isinstance(content, RecentActivity):
            lines = [' · '.join(v for v in (e.occurred_at, e.event_type, e.repository) if v) for e in content.events[:16]]
        else:
            lines = list(section.lines[:16])
        limit = 16 if display.get('details') else 2 if builder.preset == 'compact' else 4
        for line in lines[:limit]:
            builder.paragraph(line, limit=1)
        builder.condensed |= len(lines) > limit
        if isinstance(content, RepositoryList):
            builder.condensed |= len(content.repositories) > 16
        if isinstance(content, RecentActivity):
            builder.condensed |= len(content.events) > 16
        if content is None:
            builder.condensed |= len(section.lines) > 16
        for m in section.measurements.values():
            if m.availability != 'available':
                builder.line(measurement_text(m), 'notice', 10)
    builder.y += builder.gap


def plan_summary_card(title: str, subtitle: str, modules, display: dict[str, Any], image=None) -> ExportPlan:
    """Mode-specific lines are opaque; never infer measurements from their text."""
    builder = _Builder(display, image)
    builder.header(title, subtitle)
    selected = [module for module in modules if not module.hidden]
    _flow_sections(builder, display, selected, _draw_summary_section)
    builder.condensed |= len(selected) > 128
    return builder.finish()


def _draw_summary_section(builder, module, display):
    if builder.y+builder.body*2+12 > builder.bottom:
        builder.condensed = True
        return
    builder.line(module.title, 'heading')
    limit = 16 if display.get('details') else 2 if builder.preset == 'compact' else 5 if builder.preset == 'showcase' else 3
    for line in module.lines[:limit]:
        builder.paragraph(line, limit=1)
    builder.condensed |= len(module.lines) > limit
    builder.y += builder.gap
