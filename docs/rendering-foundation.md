# Rendering foundation contracts

This tranche started on `main` at
`90e8935f433b78020e33032c79a4ccc3deb6d7af` with a clean tracked/untracked
worktree (`git status --short` produced no output). The initial Python 3.12.14
baseline was 81 discovered tests: 75 passing, 6 opt-in integration/live tests
skipped. Initial Ruff and mypy checks also passed.

## Public contracts protected

`tests/test_contracts.py` uses synthetic provider data and mocked collection;
network requests and avatar downloads fail the tests. Credentials, home
directory and configuration are isolated. Date-sensitive fields are omitted.

- Configured profile and explicit `--user` share the rendering path. Explicit
  lookup does not rewrite saved configuration. Viewer mode does not substitute
  the authenticated account when the target is another user.
- All six provider selections and profile, repository, organization and
  comparison modes retain their current output envelopes.
- Profile JSON has `user: str` and `modules: object`.
- Repository/organization JSON has `type`, `title`, `subtitle`, `target`,
  `provider` and `modules`; titles/targets/provider names are strings.
- Comparison JSON has `type`, `provider`, `users: array`, `summary: object`
  and per-user `modules: object`. Summary metrics and language overlap are arrays.
- Tests assert parsed field presence, types, ordering and representative raw
  values, rather than substring-only JSON checks.
- Enabled module order and explicit exclusions remain authoritative. Hidden
  modules remain absent from JSON. Token-required and unsupported module
  payloads retain their established shapes.
- Local plugins returning only `list[str]` retain both their display fallback
  and their raw list-valued JSON data. `ModuleResult` and plugin registration
  are unchanged.
- All four existing presets round-trip through configuration normalization.
  `display.layout` still means `split` or `stack`. Named profiles, dotted
  overrides and explicit CLI target precedence are preserved.
- Ordinary ASCII module presentation is unchanged. Long lines are not
  automatically clipped or wrapped by this tranche.

## Known incorrect behavior deliberately left for later

These are not desirable contracts or new golden metric fixtures:

- GitLab percentages are currently consumed by the shared byte-count language
  accumulator. Tests do not bless those values as bytes.
- Some missing provider metrics become zero, and comparison can rank those
  zeros as measured values.
- Some repository totals are derived from filtered or viewer-visible lists.
- Gitea-family heatmap failure/absence can become an all-zero calendar, and
  the 84-day calendar can be labeled a year total in streak output.
- Repository-mode metrics, language labels and contributor coverage need a
  separate provider-semantics audit.
- Terminal-height budgeting, avatar asset caching/offline behavior and export
  layout/palette consistency remain separate work.
- Packaging references a missing LICENSE file, and the Homebrew formula is
  still pinned to the existing 2.0 release archive. Release metadata is outside
  this tranche; the added dependency resource is ready for the next formula.

## Display text policy

`gitfetch.terminal_text.sanitize_text()` operates at display boundaries, never
on provider data, `ModuleResult.data`, or JSON serialization.

- Remove untrusted SGR, CSI cursor/screen operations, OSC (including titles and
  hyperlinks), DCS, APC, PM, SOS and other ESC sequences. Both ESC-prefixed and
  C1 control forms are handled.
- Remove control-string payloads through their terminator. An unterminated
  control string consumes the remaining payload. CAN/SUB cancel a sequence.
- Normalize each whitespace separator (tabs, CR, LF, Unicode separators,
  etc.) to one ordinary space. CRLF becomes one space. Preserve existing spaces
  and repeated whitespace; do not expand tabs into terminal-dependent stops.
- Remove remaining C0/C1 controls, including BEL, backspace and DEL. Only
  renderer-owned newlines establish rows.
- Remove bidi embedding/override/isolate controls U+202A–U+202E and
  U+2066–U+2069. Preserve natural RTL text, directional marks, ZWJ/ZWNJ,
  variation selectors, combining marks and emoji sequences. No global `Cf`
  removal or Unicode NFC/NFKC normalization is performed.
- Replace invalid surrogate code points and XML-invalid U+FFFE/U+FFFF with
  U+FFFD. Missing values become empty display text.

Module titles/lines and diagnostics are normalized before renderer styling.
Plugin display strings have the same trust level as remote content; their own
escape sequences never acquire trust just because they look like ANSI.
ASCII avatar ramps are sanitized and restricted to single-cell graphemes;
an empty/unusable ramp uses the existing default glyph set.
Watch-mode screen clearing is emitted only for ANSI output attached to a TTY;
plain, structured and redirected output never receives screen-control codes.
This fixes an existing output-safety bug. Watch timing and module behavior are
unchanged; repeated JSON frames remain separate JSON values as before.

`sanitize_styled_text()` and utility calls with `trusted_ansi=True` are reserved
for renderer-owned strings. They retain only numeric semicolon-delimited SGR,
not OSC links, cursor operations or graphics protocols. Trust must be provided
by the caller, not inferred from the string.

SVG/XML escaping is retained after display normalization. Card text is also
normalized, and interpolated SVG metric values are XML-escaped. This fixes
unsafe content without introducing a new export design. JSON preserves the
original values; its existing encoder escapes control characters in JSON text.

## Terminal cells and reusable utilities

The runtime depends on `wcwidth>=0.9.3,<1.0.0`. Its published metadata requires
Python >=3.9, has no required dependencies, and supports the project's Python
3.10 minimum. See the [package metadata](https://pypi.org/project/wcwidth/0.9.3/)
and [public API](https://wcwidth.readthedocs.io/en/stable/api.html).

Package metadata, `requirements.txt` and the Homebrew resource include the
dependency. Both existing pip-based installers consume package metadata and
need no additional installation command.

- `cell_width(value)` measures normalized text with `wcswidth`; renderer SGR
  occupies zero cells. `render.visible_len()` delegates to it.
- `clip_text(value, budget, ellipsis="…", trusted_ansi=False)` clips only at
  complete grapheme boundaries and reserves space for a sanitized marker.
  Nonpositive budgets return empty text. An oversized marker is clipped first;
  remaining cells can still hold a text prefix. Wide graphemes are never split
  or padded artificially. The result can be shorter than its budget.
- `wrap_text(value, budget, trusted_ansi=False)` hard-wraps at grapheme
  boundaries and preserves normalized spaces. It does not perform word-based
  paragraph formatting. Empty text returns `[]`; nonpositive budgets raise
  `ValueError`. A grapheme wider than an entire line is replaced with `?`, so
  even a one-cell budget cannot overflow.
- Trusted styling within graphemes is preserved. Clipped prefixes close active
  styles before the unstyled ellipsis. Wrapped lines independently close and
  restore styles using wcwidth's SGR propagation.
- Ambiguous-width characters use the library's narrow default. No terminal
  probes, locale-dependent overrides or environment-based width corrections
  are introduced. Font/terminal-specific emoji differences remain possible.

The helpers do not implement layout selection, height fitting, graphics,
provider normalization or the future presentation document. A plugin remains
arbitrary opted-in Python code; these boundaries protect returned display
strings, not direct writes to stdout or other effects performed by plugin code.
