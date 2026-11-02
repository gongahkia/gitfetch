# Tranche 06B — unified graphical exports

Implementation verdict and final measurements are recorded at the end of this
report. This is CLI export work only: no GUI, graphics protocol, provider or
release integration was added. README.md is intentionally unchanged, respecting
the user's earlier instruction; working examples are here.

## Incoming state and preservation

HEAD was `da98f1d9c07411d0487620ed1a8b7950773fca36`, on `main`. The incoming
Python 3.12.14/Pillow 11.3.0 suite discovered 582 tests: 576 passed, 6 skipped.
Recent commits were `da98f1d`, `337a398`, `14ac337`, `6b507d6`, `1a0cc65`.

The worktree already contained T06A changes to `cli.py`, `completions.py`,
`config.py`, `layout.py`, `render.py`, `terminal_output.py`, plus untracked
`design.py`, `docs/terminal-design-system.md`, design fixture/preview/benchmark
scripts, tests and golden files. Those changes were preserved. T06B builds on
them; a HEAD-relative diff also includes those preexisting changes.

## Shared architecture

The modern profile path is:

1. The CLI evaluates selected modules once and constructs its existing
   `ProfileDocument` once, with provider `Measurement` semantics intact.
2. `formats.py` passes that document and one lazily acquired prepared avatar to
   `plan_profile_card()`. Public card APIs accept an optional keyword-only
   `document` while preserving their existing positional signatures.
3. `export_design.py` resolves T06A semantic color tokens into concrete colors,
   measures text with the selected packaged font, and produces an immutable
   `ExportPlan` containing only Text, Rectangle and Picture nodes.
4. `export_paint.py` serializes that same scene to SVG or paints it with Pillow.
   Neither painter chooses metrics, sections, limits, windows or layout.

`plan_summary_card()` uses the same builder and scene for repository, organization
and comparison cards. It treats their already-produced mode-specific lines as
opaque text; it never parses those lines into numbers or forces their structures
through `ProfileDocument`. Existing mode JSON contracts and request paths remain.

The planner has no provider/client/terminal dependency. Font metrics are local,
with cached packaged faces. Asset acquisition is outside planning. A caller
exporting both formats can construct one document/plan and call `scene_svg(plan)`
and `scene_png(plan, path)` without decoding an image or making semantic decisions
a second time. Separate supported API calls can also share one `AvatarLoader`.

## Appearance, presets and section allocation

Cards share terminal roles, naming, availability text, proportional language
measurements, activity glyph semantics and prominent identity typography.
Their pixel geometry is deliberately different from a terminal screenshot.

| Visual preset | Graphical interpretation |
| --- | --- |
| balanced | 88-pixel avatar slot at comfortable sizes, 25-pixel title, moderate gaps, primary metrics followed by adaptive two-column content |
| compact | 64-pixel avatar slot, 21-pixel title, small gaps, packed metrics, two language entries and a dated activity summary |
| showcase | 112-pixel avatar slot, 30-pixel title, more metadata, detailed charts and repository descriptions where space permits |

Smaller canvases use 56-pixel avatar slots and smaller type, or omit the avatar
when a readable header cannot share its row. All three presets use the same
builder. Visual presets never enable modules or alter collection limits.

The minimum identity header identifies the requested target. A selected identity
section supplies display name, biography and metadata. If that section is
absent/hidden, its optional biography and metadata do not reappear: the minimum
header uses the document's target handle/provider. Optional statistics,
languages, contributions, repositories, plugins and notices come only from the
selected non-hidden sections. Legacy card adapters also filter hidden modules,
suppress unselected statistics and suppress unselected identity biographies.
This intentionally corrects the old top-level-user-field resurrection behavior.

The selected section sequence is consumed in caller order. At widths of at
least 600 and heights of at least 300, balanced/showcase put the primary metric
section across the card and allocate subsequent sections to the currently
shorter of two lanes. Reading positions may therefore interleave later secondary
sections; source/paint order remains the selected order. Compact and narrow
cards use a single lane. Branding and an omission-notice area are reserved.
No decorative dashboard panels or ornamental borders were added.

Language percentages use `Measurement.denominator`, never the displayed top-N
sum. Repository-based measures retain `N/D repos` with prevalence versus primary
language headings. Unknown, unsupported and authentication-required values are
labeled; measured zero remains zero. Contribution summaries retain units,
coverage and observed dates. Charts show bounded dated positions with `?` for
unknown dates, a baseline for known zero, and height relative to the shown peak.
They do not fill missing dates with invented zeros. Streak metrics retain their
observed-window labeling and date/coverage notices.

## Themes and concrete export colors

T06A `resolve_colors()` remains the semantic authority. The new resolver converts
RGB tokens and terminal palette indexes to hexadecimal RGB. Terminal foreground
roles use a documented export fallback: `#e6edf3` on dark cards and `#303446` on
Catppuccin Latte. The card has its own explicit theme-compatible background:
Nord `#2e3440`, Dracula `#282a36`, Gruvbox `#282828`, Catppuccin variants' bases,
Latte `#eff1f5`, and a dark `#0d1117` fallback for other themes. No wallpaper or
terminal background is queried.

All existing theme names and T06A role names are retained: identity, handle,
text, muted, heading, stat, accent, language, contribution, track, notice,
warning. Custom `[display.colors]` overrides use the existing strict six-digit
hex validation and precedence. Mono uses grayscale regardless of custom hues.
The old `CARD_PALETTE` is retained only for legacy artwork. Existing validated
`card_palette` foreground/surface overrides remain usable in modern cards;
semantic overrides have priority for matching roles. Invalid colors are rejected
at configuration and renderer boundaries, never interpolated as SVG markup.

Cards use explicit theme RGB colors independently of terminal color capability.
Use `--theme mono` for monochrome cards. Existing `--no-color` behavior remains
for terminal output and terminal SVG. SVG and PNG cards use the same color map.

## Compatibility and configuration

All output names retain their meanings:

- `svg`: terminal-oriented SVG, not a graphical card.
- `card`: shareable graphical SVG.
- `png`: shareable graphical raster card.
- `ansi`, `plain`, `json`: their established terminal/data contracts.

The only new controls are dotted TOML settings, requiring no new CLI flags or
shell completions:

| Display setting | Default | Meaning |
| --- | --- | --- |
| `export_style` | `auto` | Modern card artwork, with the existing classic presentation mapped to legacy artwork |
| `export_avatar_fit` | `original` | Original source canvas; explicit `visible` removes fully transparent exterior padding |
| `svg_columns` | `100` | Deterministic terminal SVG viewport width, 20–240 cells |
| `svg_rows` | `40` | Deterministic terminal SVG viewport height, 2–160 rows |

Existing `card_width`/`card_height` remain supported, defaulting to 720×360.
`export_style=legacy` explicitly selects previous artwork even alongside modern
terminal presentation; `export_style=modern` explicitly selects redesigned cards
even alongside classic terminal presentation. The default classic mapping
preserves existing classic behavior. It does not redefine `--presentation
classic` to mean a new visual engine.

Legacy artwork retains its historical fixed coordinate design, including its
limitations on tiny cards. Modern cards use the new bounded layout. Legacy
output also receives font and security corrections, so it is an appearance
compatibility path rather than a promise of exact old raster bytes.

CLI flags > dotted overrides > saved TOML > defaults remains the existing rule.
Mode commands now also pass through visual-preset/presentation/details flags.
Config/module presets remain independent from visual presets.

## Sizing, overflow and details

Modern cards support 128–4096 pixels wide, 96–4096 pixels high, and at most
8,000,000 pixels. Impossible dimensions, booleans and non-integers are rejected
before image acquisition/allocation. These are allocation bounds, not a promise
that all selected content fits the smallest size. 320×180, 600×320, 720×360,
960×540, 1200×630, 320×640 and 128×96 are exercised across all presets.

The builder measures text in pixels using its actual font, wraps biography and
fallback text, and clips long labels at grapheme boundaries with ellipses. It
never uses terminal cell width as a substitute for card font measurements.
Avatar and chart bounds come from the same plan in both formats. Content cannot
overlap the reserved footer. SVG has per-text clips and a canvas clip as final containment guards;
PNG uses the same bounded coordinates.

`--details` offers all selected language entries (up to the bounded planning cap)
and the already-collected full calendar to the fixed-size card. It also expands
secondary candidates. It does not grow the canvas, exceed module limits, enable
modules, or collect more data. Content that still cannot fit produces an explicit
"More selected content omitted" notice (itself shortened on extremely small
cards). Details is therefore not an all-content guarantee for fixed-size cards.
Terminal details continues its existing scrolling behavior.

## Terminal SVG

Explicit `--presentation modern --format svg` uses the existing responsive
planner with the configured deterministic SVG viewport and visual preset. Text
rows are serialized directly from semantic spans and resolved export colors.
Only the existing Unicode/avatar encoder's trusted color runs use the narrow
legacy SGR adapter; semantic profile text is not converted to ANSI and reparsed.
No Kitty APC or active probing is involved.

Terminal SVG deliberately keeps an 8×16 cell grid and the existing configurable
monospace font-family fallback. It uses explicit text lengths for cell geometry;
viewer fonts can still affect glyph appearance. It is a terminal representation,
not the card engine. Details can extend output up to 160 SVG rows, the export
resource limit. A bounded notice marks additional omitted rows.

Auto/classic presentation retains the public `render_terminal_svg(text, config)`
compatibility path; explicit `export_style=legacy` retains it with modern
presentation too. Mode terminal SVGs retain their generic classic line adapter.
Their viewport is now deterministic, including comparisons. Graphical export
CLI paths do not discover terminal capabilities (except explicit
`--graphics-info`, whose existing passive diagnostic behavior is preserved).

## Font portability and Pillow 10 investigation

The historical documentation identifies three organization-PNG failures from
Pillow 10's Latin-1 bitmap default when preferred fonts were unavailable and
organization rows contained `★`. The saved incoming `formats.py` was exercised
under Python 3.10.21/Pillow 10.0.0 with preferred fonts forced unavailable. Three
synthetic organization variants containing `★` reproduce the failure; the full
trace is in `/tmp/gitfetch-06b-star-reproduction.log`.

The traceback first shows a handled missing `getmask2`; the final failure is
`UnicodeEncodeError` in bitmap-font `getmask`. The defect is not a call to
removed `getsize` or `textsize`. This distinction was established before the
font implementation changed. The ordinary Mac mode tests passed with installed
preferred fonts, so the forced-missing-font reproduction is necessary evidence.

One packaged DejaVu Sans face (~738 KiB) replaces the optional-system-font
assumption. It supplies stable scalable metrics in headless installations and
is cached by size. Its pinned source is Matplotlib v3.10.8's DejaVu font asset;
the complete Bitstream/DejaVu/Arev redistribution notice is packaged alongside
it as `assets/fonts/LICENSE-DejaVu.txt`. No proprietary font is required.

Modern measurement uses supported `getbbox`/`getlength`, with baseline placement
from the same font ascent. PNG uses baseline anchors for FreeType faces and a
safe unanchored emergency bitmap path. SVG embeds that font as a static data URI and includes its redistribution notice in static metadata;
no remote font dependency is introduced. Strong text may be synthesized
slightly differently by SVG viewers and Pillow.

The emergency fallback also protects legacy drawing: unsupported bitmap glyphs
are replaced only in the painter's display string. Raw provider data and the
semantic plan retain their original Unicode. The normal packaged face handles
Latin, combining accents and many scripts/symbols, including `★`. It does not
contain complete CJK or emoji coverage. Missing glyphs may appear as boxes; SVG
viewers may use an additional local fallback. Faithful CJK/color-emoji artwork
is not promised by this one-font package, but these names do not crash rendering
and are never fabricated or changed in source data.

Official API references:
[Pillow 10 removals](https://pillow.readthedocs.io/en/stable/releasenotes/10.0.0.html),
[ImageDraw text APIs](https://pillow.readthedocs.io/en/stable/reference/ImageDraw.html),
[font redistribution terms](https://raw.githubusercontent.com/matplotlib/matplotlib/v3.10.8/lib/matplotlib/mpl-data/fonts/ttf/LICENSE_DEJAVU).

## Avatar, offline and security boundaries

The existing AvatarLoader, preparation limits, cache scopes, EXIF orientation,
alpha, offline/refresh behavior and memoized asset are reused. No avatar is
fetched by the scene painters. Original export fitting remains the default,
independent of modern terminal `avatar_fit=auto` (visible). Explicit
`export_avatar_fit=visible` is non-destructive and shared by both card painters
and modern terminal SVG. Transparent and non-square images are contained,
never stretched or keyed against black. PNG composites alpha over the defined
card background. SVG embeds sanitized PNG bytes; image metadata is cleared from
the encoded copy. Original cached bytes/images are never rewritten.

Profile and plugin strings are sanitized and XML escaped. No scripts, event
attributes, foreign objects, external images, token URLs or cache metadata are
introduced. Colors and canvas dimensions are validated at the renderer boundary.
Scene serialization also rejects unsafe colors, nonfinite coordinates,
out-of-canvas geometry, excessive nodes and oversized pictures. Text work is
bounded to 4096 characters per block; planning bounds section/secondary work.
Legacy terminal SVG also bounds text volume and clamps numeric SGR colors.

Raster allocation is capped at eight million pixels (about 32 MB for the base
RGBA canvas, with additional conversion/encoding buffers). The new SVG font is
embedded once per file, roughly one MB in base64 form. This favors portability
over minimal SVG file size. Embedding fonts can be ignored by restrictive SVG
viewers; such viewers may use their own fallback metrics. Browser/viewer-specific
acceptance is separate from XML and scene tests.

## Reproduction and manual inspection

Synthetic visual fixtures use no real user profile, credentials or network:

```sh
.venv/bin/python tests/preview_exports.py
# Optional alternate destination:
.venv/bin/python tests/preview_exports.py --output /tmp/gitfetch-06b-previews
```

The output contains fourteen SVG/PNG pairs and `contact-sheet.png`: balanced,
compact, showcase, dark, light, custom colors, Unicode/long biography, partial
coverage, missing avatar, narrow/tall, unusually small, repository, organization
and comparison. Dates and payloads are fixed. Generated binary/large SVG preview
artifacts live outside the repository and can be regenerated intentionally.
The contact sheet was visually inspected; browser-specific SVG appearance and
physical terminal acceptance are not inferred from that inspection.

Working CLI examples (replace account/repository placeholders):

```sh
source .venv/bin/activate
gitfetch --offline --user YOUR_USERNAME --presentation modern --visual-preset showcase --format svg --save terminal-profile.svg
gitfetch --offline --user YOUR_USERNAME --format card --save profile.svg
gitfetch --offline --user YOUR_USERNAME --visual-preset compact --theme nord --format png --save profile.png
gitfetch --offline --user YOUR_USERNAME --visual-preset showcase --theme catppuccin-latte --set display.card_width=1200 --set display.card_height=630 --format png --save showcase.png
gitfetch --offline --user YOUR_USERNAME --set display.export_style=legacy --format card --save legacy.svg
gitfetch --offline --user YOUR_USERNAME --set display.export_avatar_fit=visible --format png --save fitted.png
gitfetch --offline --format card --save repo.svg repo OWNER/REPOSITORY
gitfetch --offline --format png --save org.png org ORGANIZATION
gitfetch --offline --format png --save comparison.png compare USER_A USER_B
```

Offline commands need existing provider/asset caches; missing avatars remain
optional. Synthetic previews require neither caches nor credentials.

## Validation commands

```sh
.venv/bin/python -m unittest discover -s tests
/tmp/gitfetch-default-310/bin/python -m unittest discover -s tests
/tmp/gitfetch-06b-pillow10/bin/python -m unittest discover -s tests
/tmp/gitfetch-06b-312-pillow104/bin/python -m unittest discover -s tests
.venv/bin/ruff check gitfetch tests installer
.venv/bin/mypy gitfetch
.venv/bin/python -m compileall -q gitfetch tests
/tmp/gitfetch-06b-pillow10/bin/python -m compileall -q gitfetch tests
uv build --out-dir /tmp/gitfetch-06b-dist
.venv/bin/python tests/benchmark_exports.py
git diff --check
git diff --exit-code -- README.md
```

The Pillow 10.0.0 environment was created with `uv venv --python 3.10
/tmp/gitfetch-06b-pillow10` and `uv pip install --python
/tmp/gitfetch-06b-pillow10/bin/python -e . 'Pillow==10.0.0'`. The additional Python
3.12 environment uses Pillow 10.4.0. Newer supported verification uses Pillow
11.3.0; the declared dependency remains `Pillow>=10,<12`.

The new tests combine semantic/value assertions, measured geometry matrices,
XML inspection, PNG pixel checks, shared SVG/PNG text/color decisions, missing
fonts, the star-glyph regression, caller-owned data preservation, request counts,
module-evaluation counts, hidden modules, cache reuse, and headless rendering.
Nineteen tests were added; four preexisting tests in three files were adjusted to explicitly
exercise legacy artwork or supply the selected stats module rather than relying
on the now-fixed resurrection of disabled statistics. No test was deleted.
