# Tranche 07.1 — final export visual polish

## Verdict and incoming state

**PASS — implementation and engineering visual review. Ready for maintainer
export visual acceptance.** This does not claim that the maintainer has already
accepted the revised cards or that Gitfetch is ready to publish.

Incoming checkout: `main`, HEAD `ff9fd8794ed0a68b819968db9ce90316039acd9c`,
clean worktree. Recent commits: `ff9fd87`, `e530498`, `1f4c4c4`, `da98f1d`,
`337a398`, `14ac337`. The local checkout, not the remote branch, was inspected.
The incoming suite verified **614 discovered, 608 passed, 6 skipped**.
The T07 report and existing export code, tests, fonts and previews were reviewed.

The maintainer reports Balanced, Compact and Showcase terminal presets visually
accepted. This pass changes shareable cards only. Terminal UI, terminal SVG
defaults, Kitty/capability detection, JSON, configuration precedence, provider
collection and public version numbers are unchanged.

## Reproduction and actual causes

Deterministic synthetic previews were captured before editing under
`/tmp/gitfetch-071-before/`. Inspection reproduced the compact card's two-language,
text-only activity presentation and unused horizontal space.

| Finding | Root cause in the incoming planner | Correction |
| --- | --- | --- |
| Small-looking avatar | Fixed 88/64/112-pixel slots, independent of comfortable canvas dimensions; original transparent canvas further reduces visible portrait area | Bounded responsive slot sizes, retaining contain/aspect ratio and original source pixels |
| Two languages | Explicit two-entry cap for compact or any narrow builder, irrespective of remaining height | Offer five selected entries, then use actual line-space checks; details retains its expanded limit |
| Empty right side | Compact explicitly excluded from the existing two-lane flow | Apply that same flow to compact at widths >=600 and heights >=300 |
| Wasted statistics row | Equal-width cells forced the fourth short metric onto another row | Measure full labels; put a short group on one row when their combined widths fit |
| Text-only contributions | Charts explicitly excluded for compact and builders marked small | Permit a dated chart in any preset when its complete chart/caption block fits |
| Unnecessary omission notice | Non-showcase metadata was intentionally suppressed; selecting a labelled chart subwindow also set the global omission flag | Display header metadata when it fits; the explicit chart window alone is not lost selected content |
| Harsh default palette | Terminal bright-green identity/statistic and yellow accent indexes directly resolved against a dark card surface | Card-specific semantic defaults with near-white identity/statistics and restrained teal accents |
| Pillow 10 small-bar error found during verification | A 5.106×5-pixel rounded fill with radius 2 reaches reversed interior bounds in Pillow 10.0 | Keep the exact proportional width and use radius 0 for fills narrower than 6 pixels, in the shared plan |

No actual user's cached avatar was cropped or diagnosed as incorrectly padded.
The synthetic transparent avatar has a 64×64 source and alpha bounds
`(12, 8, 52, 62)` (40×54 visible). Padding compounds fixed-slot proportions but
is legitimate source composition under the existing original export policy.

## Planning changes and measurements

The existing `_Builder`, `_flow_sections` and `ExportPlan` remain the only card
layout path. Painters are unchanged. Responsive preferences are resolved once
for the card; lane builders inherit its body size and spacing. Short comfortable
cards use slightly tighter padding/body spacing. Avatar sizes depend on preset,
width and height, with maxima of 136/112/168 pixels for Balanced/Compact/Showcase.
Titles retain the established 25/21/30-pixel hierarchy, or 16 pixels on small cards.

Observed allocation for the same selected fixture data:

| Preset / canvas | Avatar before → after | Languages before → after | Dated chart before → after |
| --- | --- | --- | --- |
| Balanced 600×320 | 88 → 96 | 1 → 3 | No → No |
| Balanced 720×360 | 88 → 108 | 3 → 5 | Yes → Yes |
| Balanced 960×540 | 88 → 136 | 5 → 5 | Yes → Yes |
| Compact 600×320 | 64 → 84 | 2 → 5 | No → Yes |
| Compact 960×540 | 64 → 112 | 2 → 5 | No → Yes |
| Showcase 720×360 | 112 → 115 | 1 → 4 | Yes → Yes |
| Showcase 960×540 | 112 → 168 | 5 → 5 | Yes → Yes |
| Balanced 320×640 | 56 → 104 | 2 → 5 | No → Yes |

Square-avatar dimensions in this table are allocated source-canvas dimensions,
not a forced square crop. Portrait and landscape sources are contained without
distortion. A 320×180 Balanced card remains tightly bounded (56 → 54 pixels),
demonstrating that larger avatars are not forced into every canvas.

For the synthetic alpha bounds, visible portrait footprints change as follows:

| Case | Visible pixels before → after |
| --- | --- |
| Balanced 720×360 | 55×74.2 → 67.5×91.1 |
| Compact 600×320 | 40×54 → 52.5×70.9 |
| Showcase 960×540 | 70×94.5 → 105×141.8 |

Balanced 720×360 starts the language/activity lanes at y=190 rather than y=200,
despite increasing its avatar. Compact 600×320 moves activity from the single
lane's y=216 to the right lane at y=150; languages now have five entries instead
of two. Showcase 960×540 deliberately uses more header space: the lanes start
at y=260 rather than y=224 while retaining five languages and a chart.
Exact before/after node coordinates are in `comparison.json`; the broader
canvas matrix is in `geometry.json` under the final preview directory.

Balanced/Showcase 600×320 still use a textual activity summary: after identity,
statistics, coverage and observed dates, their remaining lane height cannot fit
the chart plus its dates/legend. Compact's denser treatment fits it. This is
intentional condensation, not a promise to fit every section in every preset.

The no-secondary 960×540 fixture now fits identity metadata, statistics, five
languages and contributions without an omission notice in all three presets.
Curated previews also enable secondary sections/plugins; a notice remains when
those sections are actually clipped or unallocated. Primary language headings
require room for coverage and at least one entry, avoiding an orphan heading.

## Contributions and semantic safety

Charts consume the existing typed contribution days and measurements. Their
bounded daily window is derived from available width, capped at 42 dates, and
explicitly labelled `Shown`. Observed period, total, provider unit and coverage
remain separate. Explicit period bounds are honored, including unknown trailing
dates after the last observation.

Positive bars scale against the shown window's measured peak. Measured zero
uses a baseline; missing/unknown dates have a `?` marker. No missing day is
converted to zero. A regression with a seven-day declared interval and only
three supplied observations verifies five unknown markers, one known-zero
baseline, one positive bar, original activity-action units and partial coverage.
Both normal and details paths are exercised.

Language bars continue using the full `Measurement.denominator`, not the sum of
displayed entries. Repository prevalence and primary-language repository counts
retain their correct units. Unavailable/unsupported values remain distinct from
measured zero. No optional module is enabled, reevaluated or recovered from
hidden top-level fields. Existing provider/module/request-count tests all pass.

## Colors, formats, assets and fonts

Default modern card tokens now resolve through `design.resolve_colors` to:

| Role | Default card RGB |
| --- | --- |
| background | `#141a23` |
| identity / stat | `#e6edf3` |
| heading | `#b3c7df` |
| handle / muted / notice | `#a5b4c6` |
| accent / language / contribution | `#86b7ad` |
| warning | `#e0ba81` |

Other named themes retain their mappings. Explicit custom roles and legacy
card palette settings retain authority; an explicit accent still propagates to
its dependent roles. Mono continues to suppress custom colors. The optional
internal `export_colors(..., card=True)` path isolates this refinement from
terminal SVG's established defaults. No CLI/config flag was added.

SVG and PNG consume identical Text/Rectangle/Picture decisions, including avatar
dimensions, colors, chart positions, labels and omissions. Tests compare SVG
text/image attributes and PNG drawing calls against the same plan, and also run
real PNG painting. Fourteen pairs pass XML/PNG validation. Both painters remain
free of section selection or layout policy. Pixel-identical font antialiasing is
not a contract.

The avatar loader, cache, fitting and font pipeline are unchanged. Exports keep
original fitting unless explicitly set to visible. Tests cover both fits,
partial alpha, original-byte preservation, portrait/landscape/missing avatars,
offline failures and acquisition/decode reuse. The packaged licensed DejaVu face
and Pillow 10 fallback remain intact. No font or remote asset dependency was
added. CJK/emoji can still contain missing-glyph boxes in Pillow, while browsers
may find additional fallback glyphs; semantic text remains unchanged.

## Visual review

Full polish review using `make-interfaces-feel-better`, scoped to the existing
dataclass/SVG/Pillow card system:

| Category | Evidence | Result |
| --- | --- | --- |
| Typography | Title/body/metadata hierarchy, native-size PNGs, Chrome SVG captures, Unicode bounds tests | Refined spacing; original font stack retained |
| Surfaces/proportions | Before/after cards, avatar bounds, theme/custom-color cases | Responsive avatars and restrained default colors |
| Animations | Static CLI export only | Not applicable; no motion introduced |
| Icons | Existing source avatars; no ornamental icon system | Not applicable; no icon changes |
| Performance | Same deterministic planner/serializer/painter benchmark | More compact-card content painted; no network/performance improvement claim |

Considered and rejected: automatically trimming export alpha would violate the
established fitting policy; forcing all sections onto 320×180 would make them
unreadable; globally replacing terminal theme colors would alter accepted
terminal presentation. No new styling system or graphics primitives were needed.

Fresh PNG contact sheet and native-size Compact, Narrow/Tall and Partial cards
were inspected. Chrome rendered Balanced, Compact, Showcase, Light, Partial and
Narrow/Tall SVGs with isolated temporary profiles and external host resolution
disabled. Balanced, Compact, Showcase and Light browser captures were inspected
alongside the PNGs; Partial and Narrow/Tall browser captures were also inspected.
No overlapping identity/statistics/charts was observed in inspected samples.
Other browser engines and every possible font/terminal combination remain
unverified. Engineering visual review: **Approve for maintainer acceptance**,
subject to these documented environmental and font limitations.

## Tests and validation

Seven tests added in `tests/test_export_polish.py` cover:

- Restored language/chart density, legitimate omission and no false core-only
  notice across the three presets.
- Responsive avatar proportions, contain geometry and unchanged source bytes
  under original and visible fitting.
- Actual selected-font text bounds/collisions and language-heading integrity on
  320×180, 600×320, 720×360, 960×540, 1200×630, 320×640, 180×800 and 128×96.
- Dated unknown/zero contribution semantics, including trailing unknown dates.
- All built-in themes, custom-role authority and terminal-SVG default isolation.
- SVG/PNG text, picture, chart geometry/color parity and real tiny-bar painting.
- Small-card condensation and bounded repository/organization/comparison cards
  with hidden content excluded.

One existing alpha-compositing pixel expectation intentionally changed from
`(13,17,23)` to the new `(20,26,35)` default card background. No terminal golden
files or unrelated visual fixtures were regenerated. The first full matrix
exposed that expected color assertion and the Pillow 10 tiny-rounded-bar error;
both were corrected before the final complete runs below.

| Environment | Discovered | Passed | Skipped | Result |
| --- | ---: | ---: | ---: | --- |
| Python 3.10.21 / Pillow 10.0.0 | 621 | 615 | 6 | PASS |
| Python 3.10.21 / Pillow 11.3.0 | 621 | 615 | 6 | PASS |
| Python 3.12.14 / Pillow 10.4.0 | 621 | 615 | 6 | PASS |
| Python 3.12.14 / Pillow 11.3.0 | 621 | 615 | 6 | PASS |
| Installed wheel, Python 3.12.14 / Pillow 11.3.0 | 621 | 615 | 6 | PASS |

The same six opt-in live-provider/authenticated tests remain skipped, not passed.
No credentialed or live provider tests were enabled in this pass. Existing
classic, JSON, module/plugin, request-count, offline/cache, native graphics,
font fallback, alternate-mode and export security regressions remain passing.

Exact commands used:

```sh
.venv/bin/python -m unittest discover -s tests
/tmp/gitfetch-default-310/bin/python -m unittest discover -s tests
/tmp/gitfetch-06b-pillow10/bin/python -m unittest discover -s tests
/tmp/gitfetch-06b-312-pillow104/bin/python -m unittest discover -s tests
.venv/bin/ruff check .
.venv/bin/mypy gitfetch
.venv/bin/python -m compileall -q gitfetch tests
/tmp/gitfetch-default-310/bin/python -m compileall -q gitfetch tests
uv build --out-dir /tmp/gitfetch-071-dist
uv venv --python .venv/bin/python /tmp/gitfetch-071-wheel-env
uv pip install --python /tmp/gitfetch-071-wheel-env/bin/python /tmp/gitfetch-071-dist/gitfetch-2.0.0-py3-none-any.whl
uv pip check --python /tmp/gitfetch-071-wheel-env/bin/python
git diff --check
```

Outside-checkout installed verification:

```sh
cd /tmp
/tmp/gitfetch-071-wheel-env/bin/python -m unittest discover -s <checkout>/tests
/tmp/gitfetch-071-wheel-env/bin/python -m gitfetch.main --help
/tmp/gitfetch-071-wheel-env/bin/gitfetch --version
```

Ruff passes; mypy reports no issues in 29 source files; both compilation checks
and dependency compatibility pass. Wheel and sdist build without warnings.
All 29 runtime module bytes match source, wheel, sdist and installed package;
installed import origin is `/private/tmp/gitfetch-071-wheel-env/lib/python3.12/site-packages/gitfetch`.
Bundled font and license bytes were verified. Final full-suite logs are
`/tmp/gitfetch-071-final-{310,312,pillow100,pillow104}.log`, with installed results
in `/tmp/gitfetch-071-installed-wheel.log` and build log
`/tmp/gitfetch-071-build.log`.

Informational CPU measurements with `tests/benchmark_exports.py`, excluding
provider/asset latency, at 960×540:

| Preset | Shared plan | SVG serialization | PNG rendering |
| --- | ---: | ---: | ---: |
| Balanced | 45.654 ms | 3.885 ms | 80.833 ms |
| Compact | 54.740 ms | 3.748 ms | 75.369 ms |
| Showcase | 39.708 ms | 3.245 ms | 70.790 ms |

These are medians of three ten-iteration batches, after the verification jobs.
The before capture recorded planner medians of 42.226/46.677/45.177 ms; host
load varied, and Compact now lays out substantially more content. These numbers
do not establish an equivalent-workload regression or speedup. Avatar memo
reuse was 0.004621 ms; cached-face text measurement 0.393 ms. No repeated
semantic construction or network acquisition was introduced.

## Files and visual deliverables

Exact changed/added files:

- `gitfetch/export_design.py`: all shared policy/geometry/color corrections.
- `tests/test_export_polish.py`: seven new regressions.
- `tests/test_avatar_rendering.py`: intentional default-background expectation.
- `tests/preview_exports.py`: contact-sheet labels include canvas dimensions.
- `docs/export-design.md`: current preset/color/allocation documentation.
- `docs/RELEASE-READINESS-V3.md`: subsequent-acceptance note preserving T07 history.
- `docs/export-visual-polish.md`: this report.

Final previews: `/tmp/gitfetch-071-previews/`:

- `balanced.svg` / `balanced.png` (720×360).
- `compact.svg` / `compact.png` (600×320).
- `showcase.svg` / `showcase.png` (960×540).
- `light.svg` / `light.png`, `dark.svg` / `dark.png` (720×360).
- `narrow-tall.svg` / `narrow-tall.png` (320×640).
- `partial.svg` / `partial.png`, plus custom-color, long-Unicode,
  missing-avatar, tiny, repository, organization and comparison examples.
- `contact-sheet.png`: fourteen labelled outputs, including dimensions.
- `browser-{balanced,compact,showcase,light,partial,narrow-tall}.png`:
  actual Chrome captures regenerated after the tiny-bar corner correction.
- `geometry.json` / `comparison.json`: allocation evidence.

Regenerate all SVG/PNG pairs and the labelled sheet deterministically:

```sh
PYTHONPATH=tests .venv/bin/python tests/preview_exports.py --output /tmp/gitfetch-071-previews
PYTHONPATH=tests .venv/bin/python tests/benchmark_exports.py
```

For local visual inspection on macOS:

```sh
open /tmp/gitfetch-071-previews/contact-sheet.png
open /tmp/gitfetch-071-previews/balanced.svg
open /tmp/gitfetch-071-previews/compact.svg
open /tmp/gitfetch-071-previews/showcase.svg
```

Headless browser reproduction (installed Chrome 156.0.8078.74):

```sh
'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' --headless --disable-gpu --disable-background-networking --disable-component-update --no-first-run --no-default-browser-check --user-data-dir=/tmp/gitfetch-071-chrome-review --host-resolver-rules='MAP * ~NOTFOUND' --screenshot=/tmp/gitfetch-071-review.png --window-size=1250,850 file:///tmp/gitfetch-071-previews/compact.svg
```

## Remaining limitations and release status

Small cards and secondary-heavy selections can still produce genuine omission
notices. Long labels/names can be clipped with ellipses. Increasing a Showcase
avatar consumes header height intentionally; this does not promise all enabled
sections at 960×540. A chart is a labelled bounded date window, not a full-year
calendar. Missing glyphs and SVG/PNG font-rasterization differences remain.
Other SVG engines and fresh physical terminal/platform paths were not tested.

No terminal UI, Kitty, capability, provider, JSON, config-precedence, public
version, font asset or painter file changed. No commit, tag, push, publication or
release coordination was performed. HEAD remained the incoming `ff9fd87` during
verification; the focused changes remain uncommitted.

**The T07 release-coordinate P1 is unchanged.** Public package/runtime version
strings and Homebrew still target 2.0.0; a separate maintainer-approved release
step is required. The maintainer's terminal-preset acceptance adds evidence but
does not establish Zellij/SSH/OS/authenticated-provider acceptance. This polish
pass is ready for export visual acceptance; overall publication remains governed
by the existing T07 blockers.
