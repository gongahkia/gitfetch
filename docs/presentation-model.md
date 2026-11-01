# Shared profile presentation model (Tranche 03)

## Responsibility and construction

`gitfetch.presentation.build_profile_document(user, modules, *, provider,
instance="", context=None)` consumes a normalized user dictionary and an
already-resolved sequence of evaluated `ModuleResult` objects. Provider and
instance are explicit inputs. The optional context is the already-collected
`GitHubContext` shared by all providers, not a client.

Construction is deterministic and pure: no requests, files, avatar downloads,
terminal queries, printing, clock reads, styling, encoding, or module evaluation.
Timestamps remain their supplied values; relative labels in legacy fallback
lines have already been evaluated by modules. No dependency was added.

The document describes content and uncertainty. It has no dimensions, layout
presets, themes, cell widths, font metrics, coordinates, or graphics protocols.
It is an internal model, not a new public JSON schema or component framework.

## Types and ordering

All records are frozen dataclasses. Ordered collections are tuples; measurement
maps and ordinary raw dictionaries use read-only mapping proxies.

| Type | Purpose and future planner consumer |
| --- | --- |
| `ProfileDocument` | Provider/API-instance reference, target username, avatar reference, ordered visible sections, notices, viewer mode and existing `RepositoryCoverage` |
| `PresentationSection` | Original module name/title, ordered classic fallback lines, optional typed content, measurements and raw semantic payload |
| `ProfileIdentity` | Handle, name, biography, company, location, website, avatar/profile references and supplied creation/update timestamps |
| `Metric` / `MetricGroup` | Identifier, label and existing `Measurement`; compact statistics and observed-window streaks |
| `LanguageEntry` / `LanguageDistribution` | Selected entries in module order, available full totals, authoritative aggregate measurement; future language bars |
| `ContributionDay` / `ContributionActivity` | Actual dates/counts, selected observations, full already-collected calendar and separate window metadata; future compact/detailed calendars |
| `Repository` / `RepositoryList` | Pinned/top repository descriptors and star measurements, with collection scope |
| `ActivityEvent` / `RecentActivity` | Supplied event type, repository and timestamp, with public/visible collection scope |
| `PresentationNotice` | Availability, coverage or scope explanation, a representative `Measurement` and all affected `(module, measurement)` subjects |

Sections, not a fixed set of document-wide fields, determine what can be shown
and in what order. `document.identity` is only a convenience lookup over
selected identity content; it returns `None` when that module is absent/hidden.
The document-level target/avatar references are routing/assets metadata and do
not enable an identity section or override existing avatar configuration.

## Module adapters

| Evaluated module | Typed content and source |
| --- | --- |
| `identity` | `ProfileIdentity` from `data.user`; legacy flat identity dictionaries and the supplied user remain supported |
| `stats` | `MetricGroup` from supplied measurements and normalized `data.user`; context profile measurements are fallback provenance; explicit module metadata wins |
| `languages` | `LanguageDistribution` from structured selected entries and `measurements.languages` |
| `contributions` | `ContributionActivity` from dated module weeks and existing context calendar; never from rendered glyphs |
| `streaks` | `MetricGroup` preserving current/longest metadata and structured window total |
| `pinned`, `top_repos` | `RepositoryList` preserving supplied order, descriptions, language, URL and star availability |
| `recent_activity` | `RecentActivity` from structured event records and original timestamps |
| Other modules/plugins | Generic section with all text, raw payload and measurement metadata retained |

Metric extraction never parses English display lines. No module, plugin or
provider handler is called by an adapter. Modules without enough structured data
retain their generic fallback instead of gaining invented metrics. Pinned gists
remain in the complete raw payload and classic text; this tranche does not
invent a repository representation for them. A future specialized renderer
must retain that fallback for unadapted content.

## Measurement and provider semantics

There is no second availability/coverage model. Metrics and distributions refer
to Tranche 02's `Measurement`; the document retains `RepositoryCoverage` directly.
The existing dict/list-compatible `LanguageData` and `HeatmapData` continue to
serve provider collection; this stage consumes their evaluated module results.

- A measured zero stays zero. Unavailable, unsupported and auth-required values
  keep their status and do not become zero or valid empty content.
- All module measurements are retained, including those absent from text lines.
  Derived legacy metadata never replaces supplied metadata.
- GitHub and Gitea-family language bytes remain bytes. GitLab repository
  prevalence retains its multi-label scope; Bitbucket primary-language counts
  remain repository counts. Units are not inferred from a provider's name.
- Full language totals, original denominator, successful sample size, attempted,
  failed/missing counts, eligible repositories, sampling policy and
  whole-profile completeness remain on the original aggregate measurement.
  Truncating selected entries never changes the denominator. Legacy lists
  without aggregate metadata get an unknown denominator, not a top-five sum.
- Contribution dates are canonical ISO dates represented as `datetime.date`.
  They retain the provider's already-normalized calendar dates; this constructor
  performs no timezone conversion. Dated zero is known zero; explicit missing
  counts are `None`; absent dates/weeks remain absent, meaning unknown.
- Selected and full calendar observations are separate. Full context data is
  read only for a selected, visible contributions section. Its original source
  metadata wins when supplied; otherwise window bounds/total are carried over
  using the selected measurement's provider/unit/coverage semantics. No missing
  day is generated or filled. Broader calendar uncertainty is also retained
  under the section's `calendar` measurement when different from the selection.
- A complete-coverage claim contradicted by gaps, unknown counts or missing
  edge dates is downgraded to partial. Missing observations/invalid bounds
  cannot establish complete coverage. Original input metadata is never mutated.
- Gitea/Forgejo/Codeberg unknown coverage cannot become complete annual coverage.
  Current and longest observed streaks retain their different scopes, units,
  date windows and nullable current values. No streak is recalculated.
- Recent activity remains public for GitHub and viewer-visible for other
  providers, consistent with the existing collection semantics. No counts are
  inferred from event names or repository update times.

## Notices and generic/plugin fallback

Notices use three categories: availability, coverage and scope. Their actual
status/provenance is always the existing `Measurement`. Equivalent explanations
are grouped with all subjects retained; streak coverage already represented by
its contribution window is not repeated for current and longest separately.
Language/profile completeness and selected-repository ranking scopes remain
explicit. Missing optional identity fields do not generate separate warnings.

Selected auth-required/unsupported module payloads retain actionable text and
metadata, and do not gain typed valid data. The older capability payload shapes
remain recognizable when their measurements are absent. `requires_token=True`
on a successfully evaluated module is not itself an authentication failure.

`ModuleResult` construction, registry/loading behavior, plugin enable/disable and
resolved order are unchanged. Hidden modules and their notices are excluded.
The builder never decides selection or broadens GraphQL/optional collection.
Existing configuration normalization still appends configured plugins after
built-ins; the document preserves the resolved sequence it receives.

Generic text remains untrusted. No content is stripped from the raw semantic
payload to make terminal output safe. Standard containers are snapshotted and
frozen without invoking `deepcopy`/string conversion hooks. Arbitrary objects,
extended plugin containers and cyclic/deep branches are retained as borrowed,
opaque raw values, never interpreted by the classic renderer. These exceptional
raw values cannot be promised immutable; their owning plugin must treat them as
read-only. Raw payloads are excluded from dataclass equality/repr because opaque
objects need not implement safe equality or representation. Malformed text gets
a safe fallback; unknown data remains available rather than being stringified.
This is compatibility handling, not a sandbox for opted-in Python plugins.

## Integration and compatibility boundary

The profile path in `cli.handle_render_command.render_once` now runs:

```text
collect context -> evaluate selected modules once -> build document once
                                                   -> format dispatch
```

The same path handles configured `gitfetch` and explicit `--user` lookups. Watch
builds one document per existing refresh frame. No additional calls or optional
module executions are introduced.

`render_output` retains its four positional parameters and adds an optional
keyword-only `document`. ANSI/plain and terminal SVG use its ordered section
lines directly through the existing `module_lines` painter and avatar/layout
code. There is no conversion back to `ModuleResult`. Standalone visual calls
without a document build a pure compatibility document once. Existing sanitizer,
Unicode-width helpers, themes, margins, avatar styles and split/stack behavior
remain in the renderer. The document does not contain renderer-generated ANSI.
Fallback text can still contain untrusted escape characters from its source;
Tranche 01 sanitization remains mandatory at the display boundary.

The transitional classic lines intentionally retain already-formatted module
text, including legacy contribution glyphs/relative labels. The typed content is
independent of that representation. A future planner must use typed data for
new metrics/charts and never reverse-parse those lines.

Paths intentionally retained:

- **JSON:** original `user`/`ModuleResult.data` serialization, including hidden
  filtering and Tranche 02 nullable values. It never serializes the presentation
  document, notices, frozen raw containers or internal metadata. No new version.
- **Card SVG and PNG:** original export functions receive the original user and
  visible module objects. The CLI constructs the document at the shared stage,
  but these formats keep their legacy visual design and data path until their
  dedicated export work. Direct card/JSON render helpers do not build documents.
- **Repository, organization and compare:** existing evaluation and rendering
  paths remain unchanged. `module_lines` simply accepts either evaluated module
  results or document sections; no mode is routed through the profile document.

## Future planner interface and limits

Tranche 04 can accept `ProfileDocument` plus a separate viewport/layout policy
and produce a render plan. It should preserve section selection/order, choose
semantic content by type, retain generic fallbacks, honor notices and select the
appropriate contribution window. Renderers then apply themes, cell measurement,
clipping/wrapping and encoding. None of that planning is implemented here.

There is no new public document serialization contract, repository enrichment,
provider normalization, avatar caching, responsive composition or export redesign.
The model conservatively retains unknown metadata instead of estimating
coverage or percentages. Generic opaque payloads may require a future explicit
plugin adapter, while their existing classic text remains fully usable.

## Verification record

Incoming checkout: `607c1669754d4761a10af7c8632937496ed2f4d8`, branch
`main`, with only `docs/provider-semantics.md` modified. That preexisting edit,
Tranche 02's semantic types and all existing tests were preserved. Another
process committed work in progress as `55513e9` and `caec20f`; this agent issued
no commit, tag, publish, reset, rebase or amend commands. Last inspected HEAD
was `caec20fae8d43e8b0633a12294c4403c28e253b2`; runtime/tests matched the
validated package build copy byte for byte.

Added `presentation.py`, this document, `test_presentation.py` (50 tests) and
`test_presentation_pipeline.py` (21 tests). Runtime integration changes are
limited to `cli.py` and `render.py`. No configuration, dependency, provider,
module/plugin registry or existing test file changes were needed.

| Command | Result |
| --- | --- |
| `.venv/bin/python -m unittest discover -s tests -v` before edits | 204 discovered: 198 passed, 6 skipped |
| `.venv/bin/python -m unittest discover -s tests` (Python 3.12.14) | 275 discovered: 269 passed, 6 skipped |
| `/tmp/gitfetch-foundation-310/bin/python -m unittest discover -s tests` (Python 3.10.21) | Same 275/269/6 |
| `.venv/bin/python -m unittest discover -s tests -p 'test_presentation*.py'` | 71 passed |
| `/tmp/gitfetch-foundation-312/bin/ruff check gitfetch tests installer` | PASS |
| `/tmp/gitfetch-foundation-312/bin/mypy gitfetch` | PASS, 19 source files, configured Python 3.10 target |
| `/tmp/gitfetch-foundation-310/bin/python -m compileall -q gitfetch` | PASS |
| `uv pip check --python .venv/bin/python` | PASS |
| `uv pip check --python /tmp/gitfetch-foundation-310/bin/python` | PASS |
| `uv pip check --python /tmp/gitfetch-foundation-312/bin/python` | PASS |
| `git diff --check` | PASS |

A comparative check at `/tmp/gitfetch-tranche03-compatibility.py` loaded the
saved incoming renderer and compared 160 outputs across ANSI/plain/SVG/card/JSON,
two themes, split/stack layouts, avatar on/off, terminal widths 40/120 and forced
color on/off. Every output was byte-identical. Network/avatar downloads were
blocked. Command:

```sh
PYTHONPATH=/home/gongahkia/coding/projects/gitfetch .venv/bin/python /tmp/gitfetch-tranche03-compatibility.py
```

Builds used a source copy under
`PACKAGE_ROOT=/tmp/gitfetch-tranche03-package-awct9oja`, excluding Git metadata,
virtual environments, caches and existing build/install artifacts:

```sh
/tmp/gitfetch-foundation-312/bin/python -m build --no-isolation --sdist --wheel "$PACKAGE_ROOT/source" --outdir "$PACKAGE_ROOT/dist"
uv pip install --python /tmp/gitfetch-foundation-312/bin/python --no-deps --link-mode copy --target "$PACKAGE_ROOT/installed" "$PACKAGE_ROOT/dist/gitfetch-2.0.0-py3-none-any.whl"
# From /tmp, outside the source checkout:
PYTHONPATH="$PACKAGE_ROOT/installed" /tmp/gitfetch-foundation-312/bin/python -m unittest discover -s /home/gongahkia/coding/projects/gitfetch/tests
```

Build, install and installed-wheel suite passed (275 tests, 269 passed, 6
skipped). An installed-wheel smoke script on Python 3.10 verified import paths,
legacy constructors, document construction, classic output and CLI version exit.
Builds retain the preexisting missing-root-`LICENSE` warning and deprecated
`project.license` metadata warning; neither was changed in this tranche.

Verdict: **PASS**. **NOT VERIFIED:** live providers, personal credentials and
actual Homebrew installation. The six opt-in live/integration tests stayed
skipped. Responsive planning and a new visual design remain Tranche 04 work.
