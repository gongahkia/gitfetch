# Responsive terminal profiles (Tranches 04 and 04.1)

## Boundary and execution

`layout.plan_profile(document, viewport, preferences, avatar, *, reference_date)`
is a pure function over the Tranche 03 document. `Viewport`, `Preferences`,
`AvatarGeometry`, `Span`, `Row` and `LayoutPlan` are small frozen records. A plan
contains safe text, semantic color roles, ordered module identities, composition,
text/asset allocations, effective margins, condensation and omitted-module names.
It contains no ANSI, images, provider clients or generic widget tree.

The existing profile frame remains collection → selected module evaluation →
one document. `render_output` selects the presentation after JSON/card/SVG
format dispatch. Modern rendering measures the terminal once, obtains at most
one avatar image, plans once using its actual dimensions, applies the existing
theme, and encodes only the final avatar allocation. Tiny/text-only/no-avatar
frames skip the asset load. Avatar retrieval/offline/cache behavior otherwise
remains the existing behavior; no asset caching or graphics protocols were added.

The planner does not query the terminal, clock, network, filesystem or plugins.
The renderer supplies a UTC reference date for account age. Tests supply a fixed
date; age is a readable approximate duration (365-day years, 30-day months), not
an hours-since-creation statistic. Future/invalid join dates do not invent an age.

## Selection and compatibility

New settings, with the normal precedence of TOML → `--set` → explicit flag:

```toml
[display]
presentation = "auto" # auto | modern | classic
details = false
```

`--presentation modern|classic` overrides presentation; `--details` sets details
for this invocation. Neither changes modules, sample limits, GraphQL inclusion,
authentication, public/viewer mode, tokens, filters or provider calls. Named
profiles retain their existing profile-data overrides. The two flags are
profile presentation options; repository/org/compare retain their current UI.
Shell completions include the new flags and values.

| Situation | `auto` presentation |
| --- | --- |
| ANSI profile written to a TTY, including `--no-color` | Modern |
| ANSI pipe/redirect, `--save`, or non-TTY capture | Classic |
| Plain text | Classic |
| JSON, terminal SVG, card SVG, PNG | Existing format-specific path |

Explicit modern also works for ANSI capture, `--save` and plain text. Explicit
classic uses the prior renderer unchanged. Color forcing does not select a
presentation. JSON still serializes the original visible `ModuleResult.data`,
including nullable numeric corrections, never the layout plan/document/notices.
Terminal SVG intentionally keeps the classic compatibility renderer. Card/PNG
and repository, organization and comparison rendering are unchanged. Watch
keeps the existing refresh loop and constructs one document/plan per frame;
no module/plugin is reevaluated for layout exploration.

## Composition and budgets

Terminal measurement uses `shutil.get_terminal_size((80, 24))`, respecting its
existing `COLUMNS`/`LINES` behavior. Dimensions are separate planner inputs.
The normal row budget is `max(1, rows - 2)`, leaving two rows of headroom.
Margins remain horizontal as in classic, and modern clamps extreme margins to
leave at least 20 content columns (or the whole width when narrower than 20).
Every planned text row respects the remaining cell width.

`display.layout = "split" | "stack"` keeps its existing avatar composition
meaning; existing presets/TOML are not reinterpreted as density or visual presets.
Split prefers side-by-side output when at least 32 text columns remain after
wrapping. If that is impossible in a narrow viewport, it can fall back to stack,
then text. Stack remains stacked when readable and otherwise falls back to text;
it does not silently switch an explicit stack request into split. Old compact
presets therefore continue preferring stacked avatars.

Avatar allocation requires at least 45 usable columns and 14 terminal rows.
Its width is bounded by configured width, one third of usable width and 34
columns. It receives at most 16 rows, and at most half the normal row budget in
split, one third in stack. Widths below eight are omitted. Actual source aspect
ratio is preserved using the existing encoders' cell geometry: ASCII height is
`int(aspect * width * .55)`, half-block and Braille are `.5`, with a one-row
minimum. Candidate evaluation is a bounded scan of at most 27 widths; it does
not process an image. Short profiles also cap avatar height by actual content
height, with at most one content reflow after shrinking; candidate layouts never
encode an image. A stacked avatar gives way when it would crowd out the
primary information. Source geometry can also make text-only output necessary.

| Viewport | Typical synthetic fixture behavior |
| --- | --- |
| 30×40 / 50×40 | Compact language lists; narrow activity summary or bounded sparkline |
| 40×12 | Text only, primary identity/metrics, small language/activity summaries |
| 60×20 | Small avatar if feasible, compact languages and dated activity |
| 80×24 | Balanced split, language bars, compact dated activity; ≤22 rows |
| 100×30 | More language/secondary entries; ≤28 rows |
| 120×40 / 140×40 | Bounded avatar, weekday calendar, repository descriptions |
| 200×15 | At most six avatar rows; horizontal metrics and dated activity summary |
| 200×60 | Larger content allocation, full selected languages and secondary content |

These are composition goals, not fixed promises about every profile. Tests assert
width/height invariants across all eight viewports, non-square images, huge
avatar widths, missing assets and margins. **Terminal dimensions do not reveal
the cursor position or remaining rows below it.** Gitfetch cannot promise that
printing will never scroll. Details mode deliberately permits scrolling.

## Information hierarchy and safe text

Identity uses prominent name/handle and a quieter provider/instance line, bounded
word-wrapped biography and optional metadata. Statistics pack into horizontal
strips or short rows, preserving measured zero, unavailable/unsupported/auth
status and non-public repository scopes. Sections remain in resolved user order;
the hierarchy does not override custom ordering or resurrect disabled modules.
Repositories/followers form the primary statistics strip; following, gists and
account age share a secondary foreground row where possible. Zero gists remain
available rather than being removed or turned into unavailable data.

Languages use full aggregate denominators, never the sum of displayed entries.
Bytes use byte percentages. Repository measurements use `n/N repos` bars and
explicit primary-language/prevalence labels; multi-label prevalence need not sum
to 100%. Unknown/zero denominators use labeled values without ratio bars.
Repository sample/failed/missing/coverage information remains on the document and
is shown as space permits, with sampled/partial scope retained in compact labels.
Language rails use 8–16 cells, a heavy line for measured fill, a half-line endcap
for fractional/small positive values, and sparse dotted empty space, with aligned
numeric labels. Glyphs are quantized; the numeric values retain their precision.
They do not form solid block rectangles
in monochrome. Below 52 **content** columns, including tall panes and details,
languages use aligned lists. Short normal viewports also use compact lists;
extra terminal height does not force bars into a narrow information column.
Unit/scope/coverage/sample metadata appears once before entries. Short normal
views show two languages at ≤15 rows, three at ≤24, five at ≤30 and all selected
entries above that. The configured module entry limit remains authoritative even in details. Full
language totals are retained for the denominator, not used to secretly expand
module selection. Details displays every selected entry.

Contributions use actual ordered dates and measurements. Compact activity shows
a dated sparkline; tall/wide layouts use Sunday-first weekday panels. Normal
output below 40 content columns uses a dated summary. Sparklines occupy at most
32 cells and two thirds of content width; narrow details wraps the collected
history into dated chunks instead of discarding it. `·` means
an observed zero, `?` means an unknown date, and `▁`–`█` encodes 1 through the
labeled peak. Density/glyphs carry meaning without color. Dates absent from the
document appear only as explicitly unknown chart positions, never measured zero.
Chart dates are labeled **Shown**, while the total is labeled **in window** with
its separate measurement bounds. A cropped visual cannot relabel an 84-day total
as the total for its last 40 displayed days, or as a year. Unknown/partial coverage
is explicit. A chart and legend are retained together or replaced with a dated
summary when fitting height. Streaks keep current/longest **observed** semantics
and the observed window; nothing is recalculated or called longest ever.

Pinned/top repositories retain names, known/unknown stars, language and optional
descriptions/URLs. Recent events retain original timestamps and public/visible
scope. Pinned gists and unadapted pinned content retain the module-text fallback.
Unknown plugins keep an ordered generic section, including indentation and empty
lines. Opaque raw plugin objects are not stringified. Existing `ModuleResult`,
plugin registry/loading and hidden-module behavior remain unchanged.

All display text passes through `terminal_text` sanitization and wcwidth-based
measurement/clipping/wrapping. Prose wraps at words, with grapheme-safe hard wraps
for CJK, emoji and uninterrupted URLs; generic module lines preserve whitespace.
Normal density bounds large text before expanding it into temporary rows. Raw
provider data, plugin payloads and JSON are not sanitized destructively. ANSI is
emitted only by the renderer, with closed SGR boundaries; no control sequences
appear in plain output. Existing SVG/XML escaping remains in place.

## Density, notices and themes

Normal fitting gives up spacing first, then lower-priority secondary content,
then uses concise contribution/language/statistics/identity allocations. Resolved
module order remains unchanged. It avoids orphan secondary headings. Hidden or
unselected modules never appear. Meaningful sampling/status/window labels remain
part of their sections rather than being converted to successful numeric data.
Already-condensed views with sufficient height reserve up to two section breaks
before languages/activity without crowding out their minimum useful content.
Unused rows after fitting restore spacing at those boundaries first. Pinned
headings do not repeat “pinned repositories”; streak uncertainty and its matching
date window are explained together rather than repeated per metric.

Condensation, clipped names/bios, omitted descriptions/URLs, chart cropping or
omitted sections produces the longest **complete** hint that fits:
`More enabled content: --details` (31 cells), `Run --details` (13), or
`--details` (9). Below nine cells the indicator is just `…`; a truncated flag is
never printed. A 30-column pane therefore uses `Run --details`. Literal plugin
wrapping also keeps flag names together; clipping backs up before a flag instead
of displaying a broken prefix. A flag wider than the entire pane becomes `…`;
widening the pane is necessary to display it whole, including in details.
Raw document/plugin data and JSON keep their original values. No indicator is
added just for removing spacing. Authentication/status instructions wrap at words
so provider environment-variable names and configuration keys remain usable in
30-column panes; ordinary plugin indentation/empty lines retain literal wrapping.
`--details` removes
height caps and density truncation, preserves enabled visible sections and all
generic lines, expands already-collected calendars, wraps width safely, and adds
no requests. Module-level limits still apply. Classic already prints enabled
module text fully; details does not change its format.

Modern roles map onto the existing title/key/value/dim/accent palette. No new
themes or dependencies were added. Identity/headings are bold outside mono;
language bars and activity use accent plus glyph density. All existing themes
work, including Dracula, Nord, Gruvbox and Catppuccin. `mono` suppresses avatar
and text colors. Secondary/descriptive text uses the terminal foreground instead
of low-contrast dark theme gray; only decorative rail dots use the dim palette.
No terminal background control is required. `--no-color` suppresses both avatar
and text colors as well. Existing
`--avatar-color 256` also maps modern hexadecimal theme colors into the 256-color
palette; `truecolor`/`auto` retain existing truecolor behavior. There is no new
terminal capability probe or guarantee about font-specific emoji rendering.

## Offline previews and manual acceptance

Fifteen plain-text golden files live in `tests/fixtures/modern/`. They include a
synthetic fixed-date profile and a locally generated image; no credentials or
network are used. Invisible trailing padding, including empty separator rows, is normalized
in these preview files. They supplement semantic/geometric assertions, not replace
them. From the repository root:

```sh
PYTHONPATH=tests .venv/bin/python tests/preview_modern.py --case standard-80x24
PYTHONPATH=tests .venv/bin/python tests/preview_modern.py --case narrow-tall-30x40 --ansi
PYTHONPATH=tests .venv/bin/python tests/preview_modern.py --case tiny-40x12
PYTHONPATH=tests .venv/bin/python tests/preview_modern.py --case no-color --ansi
PYTHONPATH=tests .venv/bin/python tests/preview_modern.py --case plugin-narrow
PYTHONPATH=tests .venv/bin/python tests/preview_modern.py --case large-140x40 --ansi
PYTHONPATH=tests .venv/bin/python tests/preview_modern.py --case partial-contributions --ansi
PYTHONPATH=tests .venv/bin/python tests/preview_modern.py --case unicode-biography
PYTHONPATH=tests .venv/bin/python tests/preview_modern.py --case details
# Intentional golden regeneration after visual review:
PYTHONPATH=tests .venv/bin/python tests/preview_modern.py --write
# Planner-only benchmark, excluding provider/asset latency and ANSI painting:
PYTHONPATH=tests .venv/bin/python tests/benchmark_layout.py
```

Preview the matching terminal dimensions (e.g. 80×24 or 140×40); the case itself
always plans those fixed dimensions. These are deterministic preview files,
**not a claim of physical terminal/screenshot verification**.

For live manual review, with the repository installed and a saved username:

```sh
gitfetch
gitfetch --user octocat
gitfetch --presentation modern
gitfetch --presentation classic
gitfetch --presentation modern --no-avatar
gitfetch --presentation modern --theme nord
gitfetch --presentation modern --details
```

Resize to 30×40, 40×12, 60×20, 80×24, 100×30, 140×40 and 200×15, or set
`COLUMNS=60 LINES=20` explicitly for a controlled modern capture. Existing
provider authentication/module configuration continues to determine available
data; these commands do not turn on optional authenticated modules.

## Remaining limits

No physical terminal/font testing or live-provider verification was performed.
Unicode ambiguous width uses wcwidth's narrow policy; terminal emoji/font choices
can differ. Very small widths necessarily lose labels in normal mode; details
keeps all content wrapped, with oversized graphemes using the foundation's `?`
fallback. Detailed calendars group wide unknown gaps into explicit dated unknown
intervals rather than materializing years of absent cells. Avatar asset
download/cache/offline limitations and export design
remain separate tranches. Generic plugin payloads without structured adapters
remain text. Statistics not represented structurally cannot be recovered by
parsing legacy prose; the original classic view remains available. No provider
semantics, API costs, sample caps or cache keys changed.

## Tranche 04 verification record

Started on `main`, HEAD `caec20fae8d43e8b0633a12294c4403c28e253b2`.
Incoming changes were `gitfetch/presentation.py`, `tests/test_presentation.py`
and untracked `docs/presentation-model.md`. They were snapshotted at
`/tmp/gitfetch-tranche04-incoming-ozbsm0ag` and preserved byte for byte. Another
process committed those three files as
`5e754ac10d4c5da4301040b627e53205469ec14f`; this task issued no commit, tag,
publish, reset, rebase or amend commands. Provider, semantics, module and export
sources were also verified unchanged against the incoming copy.

Added `layout.py`, this document, five test/helper scripts
(`test_layout.py`, `test_modern_render.py`, `modern_fixtures.py`,
`preview_modern.py`, `benchmark_layout.py`) and ten golden text files.
Modified `cli.py`, `config.py`, `render.py`, `completions.py` and README.
All incoming test files remain byte-identical. The 79 new tests comprise
50 planner tests and 29 modern renderer/pipeline tests, with additional subcases
for all required dimensions, themes, providers, image aspects and safety inputs.

| Exact command/check | Result |
| --- | --- |
| `.venv/bin/python -m unittest discover -s tests` before edits | 275 discovered: 269 passed, 6 skipped |
| `.venv/bin/python -m unittest discover -s tests` (3.12.14) | 354 discovered: 348 passed, 6 skipped |
| `/tmp/gitfetch-foundation-310/bin/python -m unittest discover -s tests` (3.10.21) | Same 354/348/6 |
| `/tmp/gitfetch-foundation-312/bin/ruff check gitfetch tests installer` | PASS |
| `/tmp/gitfetch-foundation-312/bin/mypy gitfetch` | PASS, 20 files, Python 3.10 target |
| `/tmp/gitfetch-foundation-310/bin/python -m compileall -q gitfetch` | PASS |
| `uv pip check --python .venv/bin/python` | PASS |
| `uv pip check --python /tmp/gitfetch-foundation-310/bin/python` | PASS |
| `uv pip check --python /tmp/gitfetch-foundation-312/bin/python` | PASS |
| `git diff --check` | PASS; all 17 added files also checked for whitespace errors |
| `PYTHONPATH=/home/gongahkia/coding/projects/gitfetch .venv/bin/python /tmp/gitfetch-tranche04-compatibility.py` | 160 byte-identical incoming/classic ANSI/plain/JSON/SVG/card outputs |
| `PYTHONPATH=tests .venv/bin/python tests/benchmark_layout.py` | Median 1.21–1.95 ms/plan across eight sizes, 5 batches ×100 each |

The benchmark is a local observation excluding collection, assets and painting;
it is not an end-to-end speedup claim. The standard fixture is 22 rows, compact
60×20 is 17, 100×30 is 28, large 140×40 is 38, wide/short 200×15 is 13. Details
is 48 rows at an 80×24 width and intentionally scrolls. PNG byte parity is tested
with classic versus modern/details settings. Mocked collection tests assert two
language calls for two repositories and one handler call per selected module,
with unchanged GraphQL selection. Asset tests assert at most one load/encoding.

Builds used a separate source copy to preserve editable-install metadata:

```sh
/tmp/gitfetch-foundation-312/bin/python -m build --no-isolation --sdist --wheel /tmp/gitfetch-tranche04-package-hqv4jopk/source --outdir /tmp/gitfetch-tranche04-package-hqv4jopk/dist
uv pip install --python /tmp/gitfetch-foundation-312/bin/python --no-deps --link-mode copy --reinstall --target /tmp/gitfetch-tranche04-package-hqv4jopk/installed /tmp/gitfetch-tranche04-package-hqv4jopk/dist/gitfetch-2.0.0-py3-none-any.whl
# From /tmp, outside the checkout:
PYTHONPATH=/tmp/gitfetch-tranche04-package-hqv4jopk/installed /tmp/gitfetch-foundation-312/bin/python -m unittest discover -s /home/gongahkia/coding/projects/gitfetch/tests
```

Both artifacts built successfully; the installed-wheel suite also passed
354/348/6. Installed import-path, help/version, parser, Unicode preview and raw
JSON smoke checks passed on both 3.10 and 3.12 using
`/tmp/gitfetch-tranche04-wheel-smoke.py`, with `PYTHONPATH` set to the installed
root and repository tests directory. The installed console entrypoint reported
`gitfetch 2.0.0`. All runtime source files matched both build copy and installed
wheel byte for byte. Build logs retain the preexisting missing-root-`LICENSE`
and deprecated `project.license` warnings; no dependency/release metadata changed.

Verdict: **PASS**. **NOT VERIFIED:** physical terminals/fonts, live providers,
personal credentials and a Homebrew installation. The six opt-in tests stayed
skipped. No graphics protocols, asset-cache redesign or graphical export redesign
was started. The planner/render boundary is ready for Tranche 05.

## Tranche 04.1 verification record

Started on `main` at `292f97230b59c06be9e15583f05e469843b6eb51`, with a
clean worktree. The incoming snapshot is
`/tmp/gitfetch-tranche041-incoming-f95n_tw8`. Another process committed earlier
work in progress as `1a0cc65f951b56c929c50dc1fd7cf8ac9b28462f`; that commit
and the subsequent working changes were preserved. This task issued no commit,
tag, release, reset, rebase, amend or publish commands.

Runtime edits are limited to `layout.py` and four lines in `render.py`.
`plan_profile`, avatar allocation/asset behavior, the presentation/measurement
models, providers, modules, CLI, configuration, dependencies, JSON and exports
retain their implementations. The public README has no edits in this pass.
Changes are section formatting, safe hint/flag wrapping, density and spacing
policy, and foreground roles. Numeric units, full denominators, selected-entry
order, contribution observations and semantic metadata are not modified.

Added `test_visual_polish.py`: 27 deterministic tests covering thin/fractional
rails, aligned values, 30–50-column lists, width-and-height density, intact hints
at widths 1–51, literal/quoted flags, long URLs, all six provider token names,
partial/missing samples, zero versus unavailable, contributions/unknown gaps,
secondary statistics, Unicode, plugin text, section order, safety and foreground
contrast. All 354 incoming test cases and their test files were preserved.
The fixture helper now covers ten dimensions and fifteen golden previews;
five new previews are narrow/tall 30×40, tiny 40×12, slim 50×40, explicit no-color
and a narrow generic plugin. The original ten previews were deliberately updated
for the visual changes above, not for any provider/API/schema change.

| Exact command/check | Result |
| --- | --- |
| `.venv/bin/python -m unittest discover -s tests` before edits | 354 discovered: 348 passed, 6 skipped |
| `.venv/bin/python -m unittest discover -s tests` (3.12.14) | 381 discovered: 375 passed, 6 skipped |
| `/tmp/gitfetch-foundation-310/bin/python -m unittest discover -s tests` (3.10.21) | Same 381/375/6 |
| `.venv/bin/python -m unittest discover -s tests -p test_visual_polish.py` | 27 passed |
| `/tmp/gitfetch-foundation-312/bin/ruff check gitfetch tests installer` | PASS |
| `/tmp/gitfetch-foundation-312/bin/mypy gitfetch` | PASS, 20 files, Python 3.10 target |
| `/tmp/gitfetch-foundation-310/bin/python -m compileall -q gitfetch` | PASS |
| `uv pip check --python .venv/bin/python` | PASS |
| `uv pip check --python /tmp/gitfetch-foundation-310/bin/python` | PASS |
| `uv pip check --python /tmp/gitfetch-foundation-312/bin/python` | PASS |
| `git diff --check` | PASS, including separate added-file whitespace checks |
| `PYTHONPATH=/home/gongahkia/coding/projects/gitfetch .venv/bin/python /tmp/gitfetch-tranche041-compatibility.py` | 160 byte-identical incoming/classic ANSI/plain/JSON/SVG/card outputs |

Existing pipeline tests also verify PNG byte parity, unchanged language request
counts, one execution per module/plugin, configuration precedence and watch
behavior. Source checks confirm that all runtime files other than layout/render
are byte-identical to the incoming snapshot, and the planner and avatar-gate
functions themselves are unchanged. The final runtime matches the installed
wheel byte for byte.

Packaging used a separate source copy to preserve the editable installation:

```sh
/tmp/gitfetch-foundation-312/bin/python -m build --no-isolation --sdist --wheel /tmp/gitfetch-tranche041-package-l6r_aazk/source --outdir /tmp/gitfetch-tranche041-package-l6r_aazk/dist
uv pip install --python /tmp/gitfetch-foundation-312/bin/python --no-deps --link-mode copy --reinstall --target /tmp/gitfetch-tranche041-package-l6r_aazk/installed /tmp/gitfetch-tranche041-package-l6r_aazk/dist/gitfetch-2.0.0-py3-none-any.whl
# From /tmp, outside the checkout:
PYTHONPATH=/tmp/gitfetch-tranche041-package-l6r_aazk/installed /tmp/gitfetch-foundation-312/bin/python -m unittest discover -s /home/gongahkia/coding/projects/gitfetch/tests
```

Both artifacts built successfully; the installed-wheel suite passed 381/375/6.
Installed import-path, version/help, parser, narrow/no-color preview and JSON
smoke checks passed on both Python versions using
`/tmp/gitfetch-tranche041-wheel-smoke.py`, with `PYTHONPATH` set to the installed
root and repository tests directory. The installed console entrypoint still
reports `gitfetch 2.0.0`. The existing missing-root-`LICENSE` and deprecated
`project.license` warnings remain; dependency/release metadata was untouched.

`PYTHONPATH=tests .venv/bin/python tests/benchmark_layout.py` observed median
1.10–1.57 ms/plan across ten dimensions (five batches of 100), excluding provider
collection, images and ANSI painting. This is a local observation, not an
end-to-end speedup claim. The new standard preview is 22 rows, tiny 40×12 is 10,
compact 60×20 is 18, 100×30 is 28, large 140×40 is 38 and wide/short 200×15 is 13.
Narrow/tall 30×40 is 38 rows; details remains uncapped and is 46 rows at 80 columns.

Verdict: **PASS**. **NOT VERIFIED:** physical font/terminal appearance, including
opaque/transparent background combinations, and live providers. The six opt-in
tests stayed skipped. Terminals narrower than a full flag necessarily show a
marker instead; actual fonts can differ from wcwidth's narrow ambiguous-width
policy. Review the deterministic previews above in the target terminal. No
Tranche 05 work, graphics protocols, asset caching or export redesign was started.
