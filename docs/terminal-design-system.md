# Tranche 06A — terminal design system

Implementation and automated verification: PASS. Physical acceptance of the new
preset appearances is NOT VERIFIED; use the commands below. Tranche 06B is not
started. README.md is intentionally unchanged at the user's request.

## Incoming state

HEAD: `da98f1d9c07411d0487620ed1a8b7950773fca36`, branch `main`, clean worktree.
Recent commits: `da98f1d addedtweaning`, `337a398 nearingcokmpletionoffirsttrance`,
`14ac337 optimising for ghosty and kitty`, `6b507d6 newsybilsystem`, `1a0cc65 added`.
The incoming Python 3.12.14 suite discovered 569 tests: 563 passed, 6 skipped.
The accepted avatar policy is `auto`: modern fits visible alpha, classic and
exports preserve original appearance; explicit original/visible remain supported.

## Independent controls

| Concern | Interface | Effect |
| --- | --- | --- |
| Config/module preset | `gitfetch config init --preset minimal/compact/full/showcase` | Existing collection and config choices |
| Presentation | `--presentation modern/classic` | Modern planner or established renderer |
| Visual preset | `--visual-preset balanced/compact/showcase` | Formatting of already-selected profile data |
| Composition | `--set display.layout=split` or `stack` | Avatar placement relative to content |
| Theme | `--theme nord` (all existing names retained) | Built-in color palette |
| Custom roles | `--set display.colors.accent=#89b4fa` | Modern semantic foreground colors |
| Avatar backend | `--avatar-renderer auto/kitty/text` | Existing graphics selection policy |
| Text avatar style | `--avatar-style ascii/halfblock/braille` | Existing explicit style precedence |
| Fitting | `--set display.avatar_fit=auto/original/visible` | Accepted alpha fitting policy |
| Completeness | `--details` | All selected content, with scrolling allowed |

The default visual preset is balanced. A visual preset does not implicitly select
modern presentation in captured/piped output: use `--presentation modern` to
request it there. Existing modern/classic automatic selection is unchanged.
Configuration presets, module order, explicit module exclusions, result limits,
authentication and provider requests are unaffected. The config wizard retains
its existing module-preset workflow; visual selection needs no extra prompt.

```toml
[display]
presentation = "modern"
visual_preset = "showcase"
layout = "split"
theme = "catppuccin-mocha"
avatar_fit = "auto"

[display.colors]
identity = "#cba6f7"
accent = "#89b4fa"
# Optional independent chart color:
language = "#a6e3a1"
```

Dedicated CLI flags override dotted `--set` values, which override saved TOML,
which overrides defaults. Multiple dotted overrides retain their existing
last-write behavior. Built-in visual policies never rewrite these user settings.
`avatar_width` remains an explicit upper bound within responsive preset caps;
small terminals may allocate less or omit the avatar. Composition, margins,
style, fitting, module limits and details remain independent constraints.

## Architecture and responsive policy

`design.py` owns the built-in theme tables, small semantic color resolver and
immutable visual policy records. `render.THEMES` remains an alias for backward
compatibility with existing imports and exporters. No dependency was added.

The existing pure `plan_profile` takes one new `Preferences.visual_preset`.
It consumes the same document, section adapters and budget fitter. There is no
second layout engine, capability discovery, I/O, plugin execution or provider
client inside planning. Candidate avatar allocation remains a bounded scan
(at most 40 columns), followed by the existing single content reflow when needed.

| Preset | Avatar cap | Section treatment |
| --- | --- | --- |
| balanced | 34 columns, 16 rows | Existing spacing, identity, metrics, rails and activity rules |
| compact | 24 columns, 8 rows | No inter-section blank lines; one-line biography where possible; packed language labels; dated contribution summary; compact secondary lists |
| showcase | 40 columns, 16 rows | Larger split-avatar share when height allows; expanded biography, individually emphasized primary metrics, repository descriptions and contribution calendars at comfortable sizes |

These are caps, not mandatory dimensions. Showcase uses at most two-thirds of
the height budget for a split avatar, versus balanced's half; stack retains its
one-third share. Compact uses existing short-terminal section formatting; showcase
uses the next richer formatting tier at heights of at least 26. Actual budgets
always use the real viewport, leaving two terminal rows, and the avatar remains
bounded by visible content. On small or short terminals, expressive formatting
yields to the existing priority fitter and summaries. Split requires room for
text; explicit stack remains stack or safely becomes text-only.

Details bypasses presentation truncation and omission, keeps module ordering,
retains complete action hints and uses all selected language/calendar/plugin
content. It may scroll, as before. Compact details retains packed language
styling and no separator rows; it does not hide entries to achieve a fixed height.
No preset changes module-level limits or reruns modules. Coverage, denominators,
unknown values and dated observations retain their provider semantics.

## Semantic color roles

`resolve_colors()` returns immutable `Color` values containing RGB triples,
terminal palette indexes 0–15, or neither (the terminal's foreground). It does
not return ANSI strings. The modern painter turns these tokens into SGR once
per frame. `color_role()` maps chart accent spans to language/contribution roles
using module identity, without parsing display text.

| Role | Default source / purpose |
| --- | --- |
| identity | Built-in title color; name, with emphasis |
| handle | Terminal foreground; handle/provider |
| text | Terminal foreground; primary text and labels |
| muted | Terminal foreground; readable metadata and coverage |
| heading | Built-in key color; section headings, with emphasis |
| stat | Built-in title color; primary statistic groups |
| accent | Built-in accent color; general emphasis |
| language | Accent; language rail fill |
| contribution | Accent; activity intensity glyphs |
| track | Built-in dim color; decorative rail track only |
| notice | Accent; availability and details notices |
| warning | Accent; unavailable language/activity measurements |

Custom overrides accept only the keys above and exactly six hexadecimal digits
prefixed by `#`. Unknown roles, arbitrary ANSI, names, short hex, alpha hex,
non-string values and executable data are rejected during config validation.
Omitted roles retain their defaults. An accent override also supplies language,
contribution, notice and warning unless those roles are independently overridden.

Ordinary text and metadata follow the terminal foreground across every built-in
theme. No profile panels or background colors are emitted; only the existing
avatar encoder may use pixel background colors. Meaning remains in labels,
dates, coverage text and glyphs, not color alone. Custom foreground choices
cannot guarantee contrast against an unknown wallpaper; users own that choice.

`--no-color` and NO_COLOR suppress modern SGR; existing `--color` precedence over
NO_COLOR is preserved. Mono suppresses both custom colors and bold emphasis.
256-color capability/preference quantizes RGB to indexed foreground colors,
including with an explicit text-avatar style. Truecolor uses RGB foregrounds.
Built-in terminal palette colors retain their existing indexed/system meaning.
ANSI encoders remain internal; custom colors are never interpolated as raw SGR.

## Compatibility and export boundary

Classic text, JSON envelopes, terminal SVG, SVG cards and PNG cards retain their
existing output. Modern visual policies and custom role overrides do not enter
those render paths. Theme tables and their existing legacy keys are preserved
byte-for-byte. Repo/org/compare summary renderers keep their existing appearance;
these new visual presets apply to modern profile presentation.

The new RGB/terminal-index/foreground color tokens can be consumed directly by
Tranche 06B. Future exporters can map terminal indexes to export colors without
parsing ANSI strings. This tranche deliberately does not connect the new roles
or presets to export generation or change fonts/Pillow behavior.

AvatarLoader, PreparedAvatar, cache bytes, alpha handling, visible fitting,
Kitty encoding, capability/multiplexer detection, placement and cursor recovery
are unchanged. Only allocated dimensions vary by visual policy. Native and text
frames receive the same preset and fitted geometry. Images still acquire lazily
once per frame; safe text fallback and strict offline behavior remain intact.
Watch keeps its existing text-avatar policy. Automated tests never send Kitty
sequences to a physical terminal.

## Deterministic fixtures and tests

`tests/design_fixtures.py` uses fixed-date synthetic profiles, partial coverage,
generic plugin text and a generated avatar. Eleven cases each have plain-text
and trusted-SGR golden files (22 files) under `tests/fixtures/design`:
balanced 80×24/140×40, compact 60×20/80×24, showcase 100×30/140×40,
mono, custom colors, narrow Unicode, no-avatar and compact details.

Regenerate only when intentionally accepting appearance changes:

```sh
.venv/bin/python tests/preview_design.py --write
.venv/bin/python -m unittest discover -s tests -p test_design_system.py
```

The design tests also assert meaningful geometry, semantics, module order and
collection invariants. The responsive matrix covers six providers, all three
presets, split/stack, missing/landscape/portrait geometry and these viewports:
30×40, 40×12, 60×20, 80×24, 100×30, 120×40, 140×40, 200×15, 200×60.
It includes Unicode, incomplete activity, partial language data and plugin
fallbacks. Existing tests retain long-URL, unknown-value, hostile-text, explicit
avatar style, no-avatar, cache/offline, graphics-safety and fitting coverage.
Pipeline tests assert one semantic build and one selected module evaluation,
unchanged language request counts and GraphQL selection, configured/default
user parity, plugin safety/order, offline/watch composition and CLI precedence.
Export tests compare outputs and PNG bytes with and without the new controls.

## Verification commands

The commands below use the prepared Python 3.10 environment from setup.
Temporary package environments are outside the checkout.

```sh
.venv/bin/python -m unittest discover -s tests
/tmp/gitfetch-default-310/bin/python -m unittest discover -s tests
.venv/bin/ruff check gitfetch tests installer
.venv/bin/mypy gitfetch
.venv/bin/python -m compileall -q gitfetch tests
/tmp/gitfetch-default-310/bin/python -m compileall -q gitfetch tests
uv build --out-dir /tmp/gitfetch-06a-dist
uv venv --python 3.12 /tmp/gitfetch-06a-wheel-312
uv pip install --python /tmp/gitfetch-06a-wheel-312/bin/python /tmp/gitfetch-06a-dist/gitfetch-2.0.0-py3-none-any.whl
uv venv --python 3.10 /tmp/gitfetch-06a-wheel-310
uv pip install --python /tmp/gitfetch-06a-wheel-310/bin/python /tmp/gitfetch-06a-dist/gitfetch-2.0.0-py3-none-any.whl
# Run from /tmp to avoid importing the checkout:
(cd /tmp && /tmp/gitfetch-06a-wheel-312/bin/gitfetch --help)
(cd /tmp && /tmp/gitfetch-06a-wheel-310/bin/gitfetch modules list)
(cd /tmp && /tmp/gitfetch-06a-wheel-312/bin/python -m unittest discover -s /Users/gabrielongtemasek/Desktop/personal/gitfetch/tests)
(cd /tmp && /tmp/gitfetch-06a-wheel-310/bin/python -m unittest discover -s /Users/gabrielongtemasek/Desktop/personal/gitfetch/tests)
git diff --check
.venv/bin/python tests/benchmark_design.py
```

## Manual appearance acceptance

No credentials or network are needed for synthetic previews:

```sh
.venv/bin/python tests/preview_design.py --case balanced-80x24 --ansi
.venv/bin/python tests/preview_design.py --case compact-60x20 --ansi
.venv/bin/python tests/preview_design.py --case showcase-100x30 --ansi
.venv/bin/python tests/preview_design.py --case custom-colors --ansi
.venv/bin/python tests/preview_design.py --case narrow-unicode
.venv/bin/python tests/preview_design.py --case details --ansi
```

These synthetic previews produce text avatars only. For physical Ghostty/Zellij
acceptance with an already cached account:

```sh
source .venv/bin/activate
gitfetch --offline --presentation modern --visual-preset balanced
gitfetch --offline --user YOUR_USERNAME --presentation modern --visual-preset compact
gitfetch --offline --user YOUR_USERNAME --presentation modern --visual-preset showcase
gitfetch --offline --user YOUR_USERNAME --presentation modern --visual-preset showcase --set display.layout=stack
gitfetch --offline --user YOUR_USERNAME --presentation modern --visual-preset compact --details
gitfetch --offline --user YOUR_USERNAME --presentation modern --visual-preset showcase --avatar-renderer text --avatar-style halfblock
gitfetch --offline --user YOUR_USERNAME --presentation modern --visual-preset showcase --theme mono
gitfetch --offline --user YOUR_USERNAME --presentation modern --visual-preset showcase --set display.colors.identity=#cba6f7 --set display.colors.accent=#89b4fa
```

Repeat across the documented sizes on dark, light and transparent terminals.
Check name/avatar alignment, legibility, correct coverage, no clipping/overlap,
prompt below output, and text fallback. Multiplexer support assertions and
explicit confirmation procedures remain those from Tranche 05B.

## Design review boundaries

The interface-polish skill was applied to the existing terminal design, in full
scope for this tranche: wrapping, hierarchy, optical avatar allocation and
foreground contrast. Typography and image composition were inspected through
source, synthetic previews and geometry invariants. Browser surfaces, pointer
icons and animations are not applicable to this non-interactive CLI; no motion
or browser UI was introduced. CPU performance was measured independently.
Decorative borders/background panels and automatic module enabling were
considered and rejected because they reduce portability or change collection.
Physical wallpaper/font-dependent appearance remains unverified.

## Final results and limitations

| Check | Result |
| --- | --- |
| Python 3.10.21 checkout suite | PASS: 582 discovered, 576 passed, 6 skipped |
| Python 3.12.14 checkout suite | PASS: 582 discovered, 576 passed, 6 skipped |
| Python 3.10.21 installed wheel suite, from /tmp | PASS: same 582/576/6 |
| Python 3.12.14 installed wheel suite, from /tmp | PASS: same 582/576/6 |
| Ruff | PASS |
| mypy | PASS: 25 runtime source files |
| Compilation, both Python versions | PASS |
| Wheel and sdist build | PASS |
| Installed CLI help and module listing, both versions | PASS |
| Installed dependency checks, both versions | PASS |
| Visual fixture comparisons | PASS: all 22 files |
| Classic/JSON/SVG/card/PNG compatibility | PASS: automated parity tests |
| Provider/module/plugin execution counts | PASS: synthetic pipeline tests |
| Native placement/fallback/cache safety | PASS: existing and new automated tests |
| git diff --check and README parity | PASS |
| New-preset physical Ghostty/Zellij acceptance | NOT VERIFIED |

Thirteen new deterministic tests were added. The six skips are the existing
opt-in credential/live-provider checks. Both Python environments use Pillow
11.3.0; Pillow 10 organization-PNG behavior was not changed or reverified.
Builds retain the existing warnings about the missing top-level LICENSE and the
deprecated TOML license table. HEAD and branch remain unchanged.

CPU-only timings on this machine, median of three batches of 100, with semantic
data and the avatar already in memory; collection, network, asset decoding,
Kitty transport and physical terminal output are excluded. Timings vary with
host load and are not latency guarantees:

| Preset | Viewport | Planning ms | Text styling ms | Half-block encoding ms |
| --- | --- | ---: | ---: | ---: |
| balanced | 80×24 | 3.183 | 0.052 | 0.823 |
| balanced | 140×40 | 3.595 | 0.080 | 1.483 |
| compact | 80×24 | 2.972 | 0.041 | 0.544 |
| compact | 140×40 | 2.676 | 0.042 | 0.514 |
| showcase | 80×24 | 2.897 | 0.036 | 1.066 |
| showcase | 140×40 | 3.046 | 0.070 | 1.348 |

Changed existing files: `gitfetch/cli.py`, `gitfetch/completions.py`,
`gitfetch/config.py`, `gitfetch/layout.py`, `gitfetch/render.py`,
`gitfetch/terminal_output.py`.
New files: `gitfetch/design.py`, this document, `tests/test_design_system.py`,
`tests/design_fixtures.py`, `tests/preview_design.py`, `tests/benchmark_design.py`,
and the 22 golden files in `tests/fixtures/design/` (34 files total).
No existing fixture was rewritten. README.md was not edited. No commits, tags,
publishing or releases were performed. The reusable color primitives are ready
for Tranche 06B; no export redesign or Tranche 06B implementation was started.
