# Automatic terminal graphics and Kitty transport (Tranche 05B)

## Boundaries

The profile CLI resolves configuration and capabilities once, evaluates existing
modules once, builds its existing document, and chooses a backend. Native output
uses `terminal_output.TerminalFrame`: styled text, the existing `LayoutPlan`, a
`BackendDecision`, and optional `KittyTransmission`. Protocol data is separate
from profile text and the semantic document. `render_output()` remains a string
serializer and never emits Kitty commands. No dependency was added.

`terminal_capabilities.py` contains the small frozen capability/preferences/decision
records, pure classification/selection, and a passive discovery wrapper.
`kitty_graphics.py` contains encoding only. `terminal_output.py` composes one
interactive frame and writes it. `render.py` shares its existing modern row
painting helper; its string output and visual fixtures remain unchanged.
`layout.py`, `presentation.py`, providers, measurements, API caches and modules
retain their implementations. Repository, organization and comparison output
remain text/export paths; they do not acquire native graphics in this tranche.

## Detection and selection

`Support` distinguishes supported, unsupported and unknown **effective paths**.
Capabilities record stdout TTY/writability, input TTY, interactive restrictions,
a normalized identity, multiplexer, color/Unicode capability, evidence and safe
placement eligibility. Diagnostics never include raw environment values, account
names, socket paths, SSH addresses, tokens or profile data.

Discovery checks the actual stdout file descriptor as well as `isatty()`. A
StringIO capture cannot acquire graphics merely by overriding its `isatty` method.
It reads no input, opens no controlling-terminal input device, changes no termios
settings, launches no subprocess and sends no query. `probe_safe` remains false.
There is no active-probe timeout or response reader. Ordinary keystrokes cannot
be stolen by this implementation. The specification's query/DA-response approach
was reviewed and deliberately deferred because safely separating/reinjecting
unrelated input cannot be guaranteed portably.

Passive automatic support requires matching direct-terminal evidence: Kitty's
`xterm-kitty` plus its numeric window identity or matching program name; Ghostty's
`xterm-ghostty` plus matching program name. Conflicting identities do not count.
An outer identity is invalidated by multiplexer/SSH ambiguity. This is a narrow
known-environment policy, **not a successful live protocol acknowledgement**;
spoofed or stale environments cannot be completely excluded without querying.
Only the two corroborated direct paths are automatically enabled by the CLI.
Ghostty documents its graphics implementation in its [feature list](https://ghostty.org/docs/features).

| Environment | Automatic behavior | Explicit Kitty behavior |
| --- | --- | --- |
| Corroborated direct Kitty / Ghostty, writable ANSI TTY | Kitty | Kitty |
| Unknown direct terminal with a suitable color/placement path | Text | User asserts effective Kitty support |
| SSH with uncertain effective path | Text | Direct PNG transport when explicitly confirmed |
| Zellij, unknown version/host/session option | Text | User confirms 0.45+, compatible host and enabled support |
| Zellij with independently verified effective support | Model permits automatic Kitty | Kitty |
| Known policy-unsupported host path | Text | Text |
| tmux / GNU screen / nested path containing either | Text | Text |
| Windows / Windows Terminal path | Text | Text |
| Pipe, capture, save, CI, dumb console, missing/unwritable TTY | Text or no output | No Kitty |
| Plain/JSON/SVG/card/PNG, classic presentation | Existing output | No Kitty |
| Watch | Text | Text |

No passive variable establishes all of Zellij's version, actual attached host
support and session option. The CLI therefore leaves Zellij unknown, rather than
claiming automatic verification. The pure model accepts authoritative effective
support from a verified caller; tests cover that positive pane-local path. There
is no invented `ZELLIJ_VERSION` or graphics-support environment variable and no
configuration dump treated as evidence of an already-running session.

Zellij's [compatibility documentation](https://zellij.dev/documentation/compatibility.html)
describes pane-managed images and host negotiation; its
[`support_kitty_graphics_protocol` option](https://zellij.dev/documentation/options.html#support_kitty_graphics_protocol)
requires restarting the session when changed. Gitfetch neither edits that option
nor adds tmux DCS wrapping around Zellij commands.

The [tmux FAQ](https://github.com/tmux/tmux/wiki/FAQ#what-is-the-passthrough-escape-sequence-and-how-do-i-use-it)
requires configured passthrough and warns about terminal state outside tmux's
knowledge. This implementation cannot establish safe pane-relative native
placement through it, so both automatic and forced requests use text. It never
changes tmux settings. An inherited `TERM_PROGRAM` cannot bypass this restriction.

## Preferences and compatibility

New options:

```sh
gitfetch --avatar-renderer auto
gitfetch --avatar-renderer kitty
gitfetch --avatar-renderer text
gitfetch --graphics-info
```

The existing configuration adds `display.avatar_renderer = "auto"`, accepting
`auto`, `kitty`, `text`. CLI help and Bash/Zsh/Fish completions cover both flags.
The README is intentionally unchanged.

Precedence, highest first:

1. `--no-avatar` and destination/safety/color restrictions always apply.
2. CLI renderer flag, then CLI avatar-style flag.
3. Dotted renderer override, then dotted style/custom-ramp override.
4. Explicit saved renderer, then explicit saved style/custom ramp.
5. New automatic default.

Within one tier, an explicit renderer (including `auto`) takes precedence over
style. A higher-tier style beats a lower-tier renderer. An explicit text renderer
uses the configured text style. `--avatar-style ascii|halfblock|braille` remains
authoritative unless a higher-priority renderer override is supplied. Custom
ASCII ramps are preserved. No module is enabled or fetched by presentation choices.

`load_config(..., explicit_display=set())` optionally records parsed display keys
without inserting provenance into the dictionary, TOML or public JSON. Old files
with a style/custom ramp but no renderer resolve to text. Their in-memory renderer
is set to `text`, so a later config-management write cannot accidentally convert
a legacy preference into an explicit automatic default. No file is rewritten
just by loading it. New presets include `auto`; old configurations can opt in
with `--avatar-renderer auto` or by explicitly setting the new TOML key.

For modern interactive automatic fallback, UTF-capable output uses half-blocks:
truecolor, 256-color or monochrome according to capability/preference. An
ASCII-encoded stream uses ASCII. Classic, captured and explicitly selected text
styles retain their existing behavior. Themes keep their meanings.

`--no-color`, `display.color=false`, theme `mono`, `NO_COLOR` (including an empty
value), and `--avatar-color none` disable native color images. Explicit
`--avatar-color 256` also selects text to honor its palette constraint. Renderer
forcing cannot bypass these restrictions. Existing `--color` can still override
`NO_COLOR` for ordinary text, but not for native images. A native image preserves
its source colors rather than being recolored by a theme.

`--graphics-info` prints a safe JSON diagnostic **without profile collection,
token resolution, plugin loading, avatar loading or terminal queries**. It works
without a configured username and reports `asset_not_checked: true`. It describes
the output destination of that invocation: piping the diagnostic itself correctly
reports a pipe, not the original interactive destination. Subcommands reject this
profile-only diagnostic flag before fetching anything.

## Encoding, placement and lifecycle

The existing 05A `AvatarLoader` supplies the detached RGBA asset. The native path
uses its bounded aspect-preserving `fit()` method, at most 512 pixels per edge,
and writes a static PNG in memory. Encoded PNGs are limited to two MiB. No image
is redownloaded, decoded again or encoded for speculative layout candidates.
Alpha is retained; no terminal background color is assumed or composited.

The [Kitty protocol specification](https://sw.kovidgoyal.net/kitty/graphics-protocol/)
defines the APC transport used here. PNG data uses `a=T,f=100,t=d`, base64 chunks
of at most 4096 characters, `m=1` continuations and a final `m=0`. Every chunk uses
`q=2`. A fresh random positive 32-bit image **number** (`I`) asks the terminal to
allocate an image ID rather than overwriting a guessed global ID. No file/shared
memory transport is used. Both cell dimensions (`c,r`) bound the image; the
protocol preserves aspect ratio inside that rectangle. `C=1` leaves cursor
movement under the writer's control. There are no Unicode placeholders or
separate placement-ID commands.

The existing planner receives actual prepared geometry, using its half-block cell
geometry for a native rectangle. It retains all split/stack/text decisions,
height limits and margins. Native output uses actual pane TTY rows/columns from
`os.get_terminal_size`, avoiding outer screen coordinates or inherited COLUMNS
for image placement. Text-only/tiny/no-avatar plans do not transmit an image;
obviously text-only viewports skip asset loading as in 05A.

The writer validates styled text, cell widths, rectangle and destination before
output. In a split composition, spaces reserve the avatar's left columns and
text begins after the existing gap. In a stack, text begins below avatar rows
and the existing separator. It first prints the avatar-height prefix rows,
reserving real visible space even if the command starts at the pane bottom.
It moves up only those rows, moves right by the planned margin, transmits, then
returns down to the reserved baseline and prints the remaining rows. CRLF cancels
pending right-margin wrapping. It uses no absolute positioning, cursor-save slot,
alternate screen, hidden cursor, scroll-region changes or terminal input modes.
A normal shell command is assumed to begin output on a fresh current line.

The destination size is checked before output, after row reservation and before
the final chunk. A pre-output failure permits ordinary text fallback with the
same asset memo/document. A later resize/write failure/interruption never triggers
a blind profile redraw. Recovery best-effort closes an incomplete APC, deletes
only the newest owned image number with `a=d,d=N,I=...`, restores the reserved
baseline and resets styling. A detached/non-TTY stream receives no recovery
controls. A fixed concise diagnostic and exit code 1 (130 for interruption) replace
a traceback. If writes remain impossible, terminal recovery cannot be guaranteed.
No global image-delete command is sent.

Successful images remain attached to their printed rows for scrollback. Native
terminals control scrollback storage/eviction; ordinary terminal reflow after
completion is not an interactive Gitfetch relayout. Random numbers make ownership
collisions unlikely; they are not a globally reserved namespace. Watch deliberately
uses text even when forced, so it cannot accumulate native placements or repeatedly
probe. Capabilities are discovered once per command; asset disk caching and fresh
watch-frame memos remain 05A's existing behavior.

Offline, refresh, cache-disabled loading and private scope isolation are unchanged.
An offline miss or invalid avatar leaves useful profile text and transmits no
image. Source pixels, provider data, measurements, module/plugin ordering and public
JSON envelopes remain unchanged. Exports never use this writer. Native output is
exclusive to uncaptured, interactive modern ANSI profile output.

## Automated and manual acceptance

Tests use synthetic assets, mocked capability data and isolated caches. They
inspect framing, decode generated PNG payloads, exercise multipart boundaries,
selection/provenance, layout dimensions, fallbacks, offline behavior, modules and
recovery. Controlled POSIX PTYs verify output transport, unchanged terminal
settings and untouched pending input. A small cursor model simulates invocation
at the pane bottom. These are **automated/simulated tests, not physical graphics
verification**; a PTY does not implement Kitty rendering.

Run offline checks/previews from the repository root:

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_terminal*.py'
PYTHONPATH=tests .venv/bin/python tests/benchmark_graphics.py
PYTHONPATH=tests .venv/bin/python tests/preview_avatars.py --case transparent --style halfblock --color truecolor
```

For physical review in Ghostty directly, then Kitty directly if installed:

```sh
gitfetch --graphics-info
gitfetch --avatar-renderer auto
gitfetch --user octocat --avatar-renderer auto
gitfetch --avatar-renderer kitty --presentation modern
gitfetch --avatar-style halfblock
gitfetch --avatar-style braille
gitfetch --avatar-renderer text --avatar-style ascii
gitfetch --avatar-renderer kitty --set display.layout=stack
gitfetch --avatar-renderer auto --details
gitfetch --avatar-renderer auto --no-color
gitfetch --avatar-renderer auto --no-avatar
```

Inspect `no_color`, `evidence` and `reason` first. Explicit legacy styles/ramp files
need the renderer override shown above to opt in. If NO_COLOR is intentional,
expect text even with a Kitty override. Use a temporary per-command environment
change only if you deliberately want color images; Gitfetch does not alter it.

In Zellij, check `zellij --version` in your environment, confirm 0.45+ and the
host/session option yourself, then use the explicit Kitty command above. No DCS
wrapper is needed. Repeat in Zellij on an incompatible host: automatic selection
must remain text. Do not assert support with `kitty` on an unverified older or
incompatible session. Inside tmux, including a host with Kitty support,
`gitfetch --graphics-info --avatar-renderer kitty` must report a text fallback.
An ordinary unsupported terminal must also fall back automatically. Over SSH,
use automatic fallback or explicitly confirm a working effective path; image
bytes travel in-band, not through paths on either machine.

Check destinations (all must contain no Kitty APC transport):

```sh
gitfetch --avatar-renderer kitty | cat
gitfetch --avatar-renderer kitty > /tmp/gitfetch-captured.txt
gitfetch --avatar-renderer kitty --save /tmp/gitfetch-saved.txt
gitfetch --avatar-renderer kitty --format plain
gitfetch --avatar-renderer kitty --format json
gitfetch --avatar-renderer kitty --format svg --save /tmp/gitfetch.svg
gitfetch --avatar-renderer kitty --format card --save /tmp/gitfetch-card.svg
gitfetch --avatar-renderer kitty --format png --save /tmp/gitfetch-card.png
```

Resize to 40×12, 60×20, 80×24, 100×30, 140×40 and 200×15; test split, stack,
margins and details. Check text/image separation, scrolling, shell prompt position,
resize during output, interruption and `--watch 2` text fallback. Physical font
and cell dimensions can vary; image aspect ratio should remain intact.

For deterministic alpha/non-square **native** acceptance without live providers,
the helper below uses existing local fixtures and refuses non-TTY output. It
requires an explicit confirmation flag for native transport:

```sh
PYTHONPATH=tests .venv/bin/python tests/preview_native.py --case transparent --confirm-kitty
PYTHONPATH=tests .venv/bin/python tests/preview_native.py --case partial --confirm-kitty
PYTHONPATH=tests .venv/bin/python tests/preview_native.py --case landscape --confirm-kitty
PYTHONPATH=tests .venv/bin/python tests/preview_native.py --case portrait --confirm-kitty --layout stack
```

Finally warm your actual configured profile and confirm offline reuse. Use the
local helper for an isolated missing-asset case, keeping personal caches intact:

```sh
gitfetch --refresh --avatar-renderer auto
gitfetch --offline --avatar-renderer auto
PYTHONPATH=tests .venv/bin/python tests/preview_native.py --confirm-kitty --offline cached
PYTHONPATH=tests .venv/bin/python tests/preview_native.py --confirm-kitty --offline missing
```

The helper's missing case must show useful profile text without an image or any
network access. Its temporary cache is separate from provider JSON and user caches.

Physical Ghostty, Kitty, Zellij, tmux and SSH rendering are **NOT VERIFIED** in
this development environment. Windows/macOS terminal behavior is also unverified;
Windows native output is disabled. Known 05A Pillow-10 organization-PNG bitmap-font
limitations remain separate. Future iTerm/Sixel backends may reuse assets and
capabilities, but no such protocol or general graphics framework is implemented.

## Verification record

Implementation started on `main` at
`14ac337285f506e631fac82f6f79eee9eb68bb0c`. The only initial worktree change was
the existing verification appendix in `docs/avatar-assets.md`; it was preserved
byte-for-byte. HEAD remained unchanged during this tranche. README, existing tests
and visual fixtures, provider/semantic/presentation/layout code, 05A assets/cache
and format encoders were checked against an initial source copy. No commit, tag,
release or dependency change was made.

Incoming validation discovered 458 tests: 452 passed, six opt-in tests skipped.
The final checkout and the installed wheel each discover **556 tests: 550 passed,
six skipped**, on both Python 3.10.21 and 3.12.14 with Pillow 11.3.0. The 98 new
tests cover capability policy, configuration provenance, encoding, placement,
failure recovery, PTY/input preservation and profile CLI integration. Existing
tests were not edited. No live-provider tests were enabled.

Commands executed from the repository root unless noted:

```sh
.venv/bin/python -m unittest discover -s tests
/tmp/gitfetch-foundation-310/bin/python -m unittest discover -s tests
/tmp/gitfetch-foundation-312/bin/ruff check gitfetch tests installer
/tmp/gitfetch-foundation-312/bin/mypy gitfetch
/tmp/gitfetch-foundation-310/bin/python -m compileall -q gitfetch installer tests
uv pip check --python .venv/bin/python
uv pip check --python /tmp/gitfetch-foundation-310/bin/python
uv pip check --python /tmp/gitfetch-foundation-312/bin/python
git diff --check
PYTHONPATH=tests .venv/bin/python tests/benchmark_graphics.py
```

Both suites, Ruff, mypy (24 runtime source files), compilation, dependency checks
and diff checks passed. New untracked files were also checked for trailing
whitespace. A separate incoming/current renderer comparison produced 160
byte-identical classic ANSI/plain/JSON/SVG/card outputs; 90 modern text/layout
cases matched with avatar encoding held constant. Existing PNG, all-format offline,
nullable JSON and six-provider tests pass in the complete suites. New integration
tests assert single module/provider evaluation and shared asset acquisition.

Packaging used an isolated source copy to leave editable-install metadata alone:

```sh
/tmp/gitfetch-foundation-312/bin/python -m build --no-isolation --sdist --wheel /tmp/gitfetch-tranche05b-package-rnre0r9e/source --outdir /tmp/gitfetch-tranche05b-package-rnre0r9e/dist
uv pip install --python /tmp/gitfetch-foundation-312/bin/python --no-deps --link-mode copy --target /tmp/gitfetch-tranche05b-package-rnre0r9e/installed /tmp/gitfetch-tranche05b-package-rnre0r9e/dist/gitfetch-2.0.0-py3-none-any.whl
```

The wheel and sdist build successfully. Existing setuptools warnings about the
absent root LICENSE file and deprecated license table remain unchanged. All 24
runtime sources were byte-checked against the build copy and installed wheel.
From `/tmp`, both installed-package full suites were run using:

```sh
PYTHONPATH=/tmp/gitfetch-tranche05b-package-rnre0r9e/installed /tmp/gitfetch-foundation-312/bin/python -m unittest discover -s /home/gongahkia/coding/projects/gitfetch/tests
PYTHONPATH=/tmp/gitfetch-tranche05b-package-rnre0r9e/installed /tmp/gitfetch-foundation-310/bin/python -m unittest discover -s /home/gongahkia/coding/projects/gitfetch/tests
```

Additional installed-wheel smoke tests on both versions verify import origins,
CLI help/version/parser, no-fetch graphics diagnostics, quiet PNG encoding,
prepared orientation/strict offline assets, modern previews and raw nullable JSON.
The installed console entrypoint also passes `--version` and `--graphics-info`.

Pillow 10.0.0 was tested separately with Python 3.10:

```sh
PYTHONPATH=/tmp/gitfetch-avatar-pillow10:tests /tmp/gitfetch-foundation-310/bin/python -m unittest test_terminal_graphics test_terminal_output
PYTHONPATH=/tmp/gitfetch-avatar-pillow10 /tmp/gitfetch-foundation-310/bin/python -m unittest discover -s tests
```

All 98 new tests pass at that lower bound. The full lower-bound suite reproduces
the same three preexisting organization-PNG errors as the saved incoming checkout
(458 tests before changes, 556 after). Without preferred fonts, Pillow 10's default
bitmap font cannot encode the existing star glyph. This is a **known baseline
failure**, not a passing minimum-Pillow full suite or a new native-graphics error;
no unrelated export/font change was included.

Local processing benchmarks (Python 3.12.14, Pillow 11.3.0; median of five batches,
no network or real terminal emission):

| Operation | Median milliseconds |
| --- | ---: |
| Passive classification + selection | 0.0084 |
| Prepared 64×64 PNG + protocol chunks | 0.2446 |
| High-entropy 512×512 PNG + chunks | 64.1581 |
| Chunking only, preencoded 1,050,601-byte PNG | 3.2736 |
| Existing half-block resize/truecolor encoding | 0.4485 |
| Frame composition, PNG encoding excluded | 2.7440 |
| Complete typical native frame, acquisition excluded | 3.3042 |
| No-avatar selection | 0.0031 |

The script records batch sizes and generates fixtures locally. These are component
measurements, not an end-to-end or network speed claim. There is no active-probe
cost. Physical rendering remains NOT VERIFIED as described above; deterministic
protocol/geometry and controlled-PTY verification pass.
