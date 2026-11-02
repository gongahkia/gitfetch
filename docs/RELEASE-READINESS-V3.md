# Gitfetch v3 — final engineering acceptance

Assessment date: 2026-11-02. Scope: Tranche 07 integration, hardening and
release readiness. No release, version change, commit, tag, push, deployment,
credentialed integration run or Homebrew submission was performed.

## 1. Executive verdict

**Engineering verification: PASS for the tested local implementation after
targeted repairs. Public v3 release readiness: NOT READY.**

The remaining P1 is release-coordinate coordination: package/runtime metadata
and user-agent strings still identify 2.0.0, and the formula targets the existing
2.0 source artifact. Those coordinates cannot represent a new v3 release. The
maintainer must approve a version and coordinate the eventual artifact URL and
checksum. This assessment deliberately leaves them unchanged.

Physical terminal/multiplexer, additional operating-system and authenticated
provider acceptance also remain incomplete. Automated tests do not establish
those results. Chrome rendering and bounded unauthenticated endpoint checks
were performed; their limited scope is recorded below.

The review reproduced and fixed an implicit cross-provider credential fallback:
selecting a non-GitHub provider could otherwise use `GITHUB_TOKEN`. Reproduction
used synthetic sentinels only. No real credential was sent to a provider during
this audit. Historical exposure cannot be determined from these checks.

## 2. Incoming and final repository state

- Incoming and final observed HEAD: `e53049876b1acdfb8c4d90772748c467903ec493`.
- Branch: `main`. Recent commits: `e530498`, `1f4c4c4`, `da98f1d`,
  `337a398`, `14ac337`, `6b507d6`.
- Incoming local change: `docs/export-design.md`, containing the final T06B
  engineering evidence. It was preserved and was not rewritten for T07.
- Incoming suite: **601 discovered, 595 passed, 6 skipped**.
- Incoming build succeeded but warned about the missing root LICENSE and the
  deprecated license table.
- Final suite: **614 discovered, 608 passed, 6 skipped**, independently in each
  of four Python/Pillow combinations and in the installed wheel/sdist checks.
- Work remains uncommitted. No reset, rebase, amend, cherry-pick or discard was
  used. Build outputs and disposable environments are outside the checkout.

T07 changes:

| File | Purpose |
| --- | --- |
| `gitfetch/config.py` | Isolate implicit provider credentials; malformed UTF-8 TOML and legacy JSON handling |
| `gitfetch/cache.py` | Treat invalid cache JSON, shapes and expiry metadata as misses |
| `gitfetch/cli.py` | Clean filesystem/encoding/EOF errors; reject PNG without a destination before collection |
| `gitfetch/modes.py` | Same early PNG validation for repo/org/compare |
| `gitfetch/modules/plugins.py` | Skip explicitly unselected plugin source; contain registration failures |
| `installer/installation.py` | Install the current checkout, respect venvs, quote PATH and preserve shell-file line boundaries |
| `installer/mainInstall.sh` | Delegate to the same Python installer policy |
| `pyproject.toml` | Six-provider description, modern license metadata and explicit license files |
| `LICENSE` | Restore the exact established historical MIT grant |
| `README.md` | Correct installation, output, compatibility and release-state claims |
| `docs/MIGRATION-V3.md` | Describe intentional contract changes and migration |
| `docs/RELEASE-READINESS-V3.md` | This report |
| `tests/test_release_acceptance.py` | Thirteen deterministic hardening regressions |
| `tests/benchmark_acceptance.py` | Reproducible fixture/cache/component benchmarks |

## 3. Integration and architecture

The T01–T06B boundaries remain intact:

1. Config loading, saved-profile application and explicit overrides precede
   provider construction and module execution.
2. Provider clients/cache own collection. Measurement metadata carries units,
   availability, scope, sampling and observed coverage.
3. `ProfileDocument` construction performs no network/file I/O. Existing tests
   verify one document construction and one execution per selected module/frame.
4. The terminal planner remains a pure responsive function. Preset preferences
   affect geometry and formatting, not capability discovery or collection.
5. Design resolution maps semantic roles independently of raw provider data.
6. Avatar acquisition/preparation remains in the shared asset policy. Renderers
   reuse prepared assets; modern automatic visible fitting and original export
   fitting remain unchanged.
7. Kitty encoding/placement remain isolated in terminal frame output. Text,
   JSON and graphical serializers do not receive Kitty transport.
8. SVG/PNG cards consume the same export plan. Alternate-mode summary cards
   use the same scene and painting system without being forced into a profile
   document. Unknown line-only plugins retain generic sections.

No new provider requests, presentation reconstruction layer, layout engine,
graphics protocol or plugin API was added. No stable rendering subsystem was
refactored for appearance alone.

## 4. Acceptance gates

| Gate | Status | Evidence and boundary |
| --- | --- | --- |
| G1 Core CLI | PASS | Full fixture suites, both installed entrypoints, clean error exits and command/help/config/completion checks |
| G2 Provider semantics | PASS | Six-provider deterministic regressions; live endpoint reachability is separate from semantic acceptance |
| G3 Security/privacy | PASS | Repaired cross-provider token fallback; cache/auth scope, sanitization, asset limits and export adversarial tests pass; no claim of a penetration audit |
| G4 Terminal presentation | PARTIAL | Responsive matrix, goldens and text previews pass; no new physical light/dark/transparent-terminal acceptance |
| G5 Native graphics/fallback | PARTIAL | Capability, cursor, protocol and fallback tests pass; historical Ghostty acceptance is not a fresh T07 physical run |
| G6 SVG/PNG | PASS | Shared-scene semantic/bounds tests, Pillow matrix, synthetic previews and representative Chrome SVG rendering |
| G7 Configuration | PASS | Existing/legacy settings, independent presets, provenance and override tests; nullable JSON changes documented |
| G8 Build/installed package | PASS | Wheel/sdist, resource/license checks, outside-checkout execution and full installed suites |
| G9 Installers/Homebrew | PARTIAL | Local Python/shell installers exercised in a disposable venv; formula Ruby syntax and seven resource hashes pass; actual brew installation NOT VERIFIED and source target remains old |
| G10 Documentation/migration | PASS | Targeted README corrections, migration guide and this evidence report; historical screenshot is explicitly labelled |
| G11 Performance | PASS | Fixture cache, whole-process startup and component timings recorded; no network-speed claim |
| G12 Physical/browser/live | PARTIAL | Actual Chrome SVG rendering and bounded public GETs; authenticated/live-context, physical multiplexer and cross-platform matrix NOT VERIFIED |

## 5. Findings and repairs

| ID / severity | Reproduction and root cause | Fix / regression / remaining risk |
| --- | --- | --- |
| SEC-01 / P0 | Set only a synthetic `GITHUB_TOKEN`, choose Forgejo (or any other non-GitHub provider), call `get_token`: the implicit profile variable was appended again after provider variables | **FIXED**, `config.py`; tests cover all five non-GitHub services, CLI tokens and explicit custom/provider variables. Historical use cannot be audited here |
| CLI-01 / P1 | Save plain/JSON/SVG/card/PNG beneath a regular file used as the parent directory: uncaught filesystem exception | **FIXED**, `cli.py`; all five formats return exit 1 with sanitized diagnostics, no traceback |
| CONFIG-01 / P1 | Invalid UTF-8 TOML, binary legacy config, or legacy JSON `[]`/`null`/scalar crashes first-run/config handling | **FIXED**, `config.py`; TOML becomes ConfigError/exit 2; unusable legacy state is ignored; regression coverage includes each form |
| CACHE-01 / P1 | Cached JSON list/null, invalid UTF-8, nonnumeric/NaN/huge expiry values fail parsing or comparison | **FIXED**, `cache.py`; malformed entries become misses, including expired-cache reads; tests cover parser and overflow paths |
| PKG-01 / P1 | Missing root LICENSE and deprecated license table produce incomplete license distribution/warnings | **FIXED**, exact historical MIT grant restored, PEP 639 metadata and all notices included; maintainer should review the restored historical grant before publishing |
| INSTALL-01 / P1 | Installer selects remote source rather than the checkout, depends on VIRTUAL_ENV env presence and can append unsafe/concatenated PATH lines | **FIXED**, shared local-source policy, interpreter-based venv detection, shell quoting and newline preservation; actual disposable installer tests plus isolated PATH regressions; system-wide installs deliberately not run |
| PLUGIN-01 / P2 | Explicitly disabled/unselected plugin paths can still be imported; registration exception escapes | **FIXED**, selection checked before import and registration errors become ConfigError; trusted plugins remain arbitrary executable Python, not a sandbox |
| CLI-02 / P2 | PNG without --save collects data before discovering the invalid request | **FIXED**, early exit 2 in all four modes, tests forbid token/provider lookup |
| CLI-03 / P2 | Wizard EOF or ASCII-only stdout with non-ASCII names raises an ordinary-user traceback | **FIXED**, clean exit 2/1 and actionable messages; raw names are not rewritten |
| RELEASE-01 / P1 | Metadata/runtime/UA still say 2.0.0 and formula URL targets old source | **OPEN, maintainer release coordination required**. Version/artifact/checksum were intentionally not guessed; publishing these as v3 would be misleading |
| FONT-01 / P2 | Bundled DejaVu lacks some CJK/emoji glyphs; PNG may show missing-glyph boxes while browsers use additional fallback | **KNOWN LIMITATION**, Unicode does not crash, original semantic text remains intact; no unlicensed font substitution |
| ENV-01 / P2 | Physical multiplexer, SSH, Windows/Linux and authenticated instances unavailable in this run | **NOT VERIFIED**, manual matrix below; simulated capability tests are not physical evidence |
| PERF-01 / P2 | Whole-process cached fixture invocation takes roughly 0.49 s here | **MEASURED**, includes interpreter/import startup; no acceptance threshold or demonstrated regression; do not conflate with 10 ms in-process cache work |
| FOLLOWUP-01 / P3 | More automated OS/font/provider environment coverage would reduce future manual work | Future CI coverage only; no feature or framework work included |

## 6. Automated verification

Host: macOS 15.7.7, x86_64. Each source row below ran the **entire** suite:

| Python | Pillow | Discovered | Passed | Skipped | Result |
| --- | --- | ---: | ---: | ---: | --- |
| 3.10.21 | 10.0.0 | 614 | 608 | 6 | PASS |
| 3.10.21 | 11.3.0 | 614 | 608 | 6 | PASS |
| 3.12.14 | 10.4.0 | 614 | 608 | 6 | PASS |
| 3.12.14 | 11.3.0 | 614 | 608 | 6 | PASS |
| Installed wheel, 3.12.14 | 11.3.0 | 614 | 608 | 6 | PASS |
| Installed sdist, 3.10.21 | 10.0.0 | 614 | 608 | 6 | PASS |

Skipped means not passed: five opt-in tests in `test_live_providers.py` and one
authenticated GitHub/GraphQL test in `test_integration.py`. No credentialed
opt-in tests were enabled. Installed runs use the repository's tests/fixtures
but import `gitfetch` from disposable site-packages while working in `/tmp`.
The installer tests intentionally load the checkout's standalone installer.

Thirteen new tests cover malformed configuration/cache data, implicit token
isolation and explicit credentials, disabled plugins, registration failures,
five output-destination failures, early PNG validation in four modes, encoding
errors, wizard EOF and installer policy/PATH handling. They complement existing
provider, contract, rendering, security, avatar and request-count coverage.

Commands executed from the checkout unless stated otherwise:

```sh
.venv/bin/python -m unittest discover -s tests
/tmp/gitfetch-default-310/bin/python -m unittest discover -s tests
/tmp/gitfetch-06b-pillow10/bin/python -m unittest discover -s tests
/tmp/gitfetch-06b-312-pillow104/bin/python -m unittest discover -s tests
.venv/bin/ruff check .
.venv/bin/mypy gitfetch
.venv/bin/python -m compileall -q gitfetch installer tests
/tmp/gitfetch-default-310/bin/python -m compileall -q gitfetch installer tests
uv build --out-dir /tmp/gitfetch-07-dist
uv pip install --python /tmp/gitfetch-07-wheel-env/bin/python --reinstall-package gitfetch /tmp/gitfetch-07-dist/gitfetch-2.0.0-py3-none-any.whl
uv pip install --python /tmp/gitfetch-07-sdist-env/bin/python --reinstall-package gitfetch /tmp/gitfetch-07-dist/gitfetch-2.0.0.tar.gz
uv pip check --python /tmp/gitfetch-07-wheel-env/bin/python
uv pip check --python /tmp/gitfetch-07-sdist-env/bin/python
bash -n installer/mainInstall.sh
ruby -c Formula/gitfetch.rb
git diff --check
```

Outside-checkout suite commands (absolute path is this machine's checkout):

```sh
cd /tmp
/tmp/gitfetch-07-wheel-env/bin/python -m unittest discover -s /Users/gabrielongtemasek/Desktop/personal/gitfetch/tests
/tmp/gitfetch-07-sdist-env/bin/python -m unittest discover -s /Users/gabrielongtemasek/Desktop/personal/gitfetch/tests
/tmp/gitfetch-07-wheel-env/bin/python /tmp/gitfetch-07-package-check.py
/tmp/gitfetch-07-sdist-env/bin/python /tmp/gitfetch-07-package-check.py
```

Ruff: all checks pass. Mypy: no issues in 29 source files. Compilation,
dependency compatibility and diff whitespace checks pass. Build succeeds
without the incoming license warnings. The package smoke script verifies
outside-checkout import origin, modified runtime source bytes, bundled resource
bytes, license metadata, Unicode font measurement, console and module help/
version, config validation/profiles, module listing, graphics diagnostics and
completion generation. Bash and Zsh parse generated completions; Fish content
tests pass, but a Fish interpreter was unavailable.

## 7. CLI and configuration contracts

Fixture tests exercise configured `gitfetch` and explicit `--user`, provider and
instance selection, repo/org/compare dispatch, JSON envelopes, optional module
limits, offline/refresh, watch interruption, config init/wizard/validation/
profiles, token helper behavior and completions. Keychain operations are mocked;
no real token storage was changed. Command errors preserve argparse/config exit
2, operational failures exit 1, and successful execution exit 0.

Installed help was exercised for the top-level parser, repo, org, compare,
config, modules and token. The actual completion syntax is `gitfetch completions
bash|zsh|fish`. Fitting is configured with `--set display.avatar_fit=...`;
there is no invented `--avatar-fit` flag. CLI presentation choices are modern
and classic; auto is the configuration default.

Configuration/module presets remain distinct from visual presets, presentation,
split/stack, themes, renderer selection, fitting and output format. Tests retain
saved profile, dotted override and explicit CLI precedence, legacy avatar-style
authority and config round trips. Modern auto fitting resolves visible; classic
preserves original. Exports retain `export_avatar_fit=original` unless explicitly
overridden. A forced wizard replaces settings only with explicit `--force`;
the migration guide calls for a backup rather than implying custom choices are
merged automatically.

JSON envelopes remain supported. Nullable/fractional leaves intentionally
changed in T02 and are documented as major-version migration concerns; this
report does not claim byte/type identity with all 2.x output.

## 8. Provider evidence

| Provider | Deterministic semantic coverage | Public endpoint check | Authenticated / instance-specific |
| --- | --- | --- | --- |
| GitHub | Byte languages, missing vs zero, viewer/public, GraphQL notices, comparisons | `/users/octocat`: 200 JSON | NOT VERIFIED live |
| GitLab | Fractional project percentages, profile prevalence, scope/sampling | `/users?username=gitlab`: 200 JSON | NOT VERIFIED live |
| Bitbucket Cloud | Primary-language repository counts, unsupported metrics, auth modes | `/workspaces/atlassian`: 200 JSON | NOT VERIFIED live |
| Gitea | Byte languages, observed activity windows, missing metrics | `gitea.com/api/v1/users/gitea`: 200 JSON | NOT VERIFIED live |
| Forgejo | Compatible semantics and configured instance identity | Codeberg `/api/v1/users/forgejo`: 200 JSON | Same endpoint as Codeberg, not an independent Forgejo instance |
| Codeberg | Gitea-family semantics and provider identity | `/api/v1/users/forgejo`: 200 JSON | NOT VERIFIED authenticated |

Six bounded unauthenticated GETs checked reachability/nonempty JSON only. They
did not run full profile/module collection, prove rankings or validate every
self-hosted implementation. No production token, mutation or private data was
used. Results: `/tmp/gitfetch-07-public-checks.json`.

For an authorized later live run, inspect `tests/test_live_providers.py` first.
It loops public profile contexts, separately tests a Forgejo-compatible context,
and has GitLab/Gitea viewer and Bitbucket Basic-auth workspace cases. Supply
`GITFETCH_LIVE_<PROVIDER>_USER`, optional `_BASE_URL` and provider-specific
`_TOKEN` only for an account/instance the maintainer authorizes. Bitbucket also
needs `_AUTH_MODE`/`_AUTH_USERNAME`. The separate GitHub GraphQL test uses
`GITFETCH_INTEGRATION_TOKEN`. Invoke from this checkout with `PYTHONPATH=tests`
and `python -m unittest test_live_providers -v` only after explicitly enabling
`GITFETCH_LIVE_PROVIDERS=1`. Do not put credentials in commands, screenshots or
reports. These opt-in runs remain outstanding.

## 9. Terminal, graphics and responsiveness

All three presets exercise 30x40, 40x12, 60x20, 80x24, 100x30, 120x40,
140x40, 200x15 and 200x60 in deterministic tests. Invariants cover cell-width
bounds, bounded short-terminal avatars, split/stack decisions, CJK/combining
width, long text, known-zero/unknown charts, action hints, generic plugins,
details completeness, no-avatar, monochrome, custom roles and reduced colors.
Details may deliberately scroll; ordinary condensed output respects its budget.

Fresh balanced/compact/showcase and narrow Unicode text captures were inspected.
These prove the serialized composition; they do not establish a physical
terminal's font, transparency, image placement or perceived contrast.

| Environment | Evidence | Physical status |
| --- | --- | --- |
| Direct Ghostty | Passive-selection tests; user accepted T05B.1 historically; installed 1.4.0 | Fresh T07 rendering NOT VERIFIED |
| Direct Kitty | Corroborated capability, encoding, owned cleanup and cursor/frame tests | NOT VERIFIED |
| Unknown terminal / pipes | Conservative selection and absence of Kitty in serializers covered | Physical unknown-terminal variety NOT VERIFIED |
| Zellij 0.45.1 | Pane-relative and positive/negative/unknown effective-support tests | NOT VERIFIED; user config has no explicit Kitty setting |
| tmux 3.8 | Conservative fallback tests | Native path deliberately not enabled; physical fallback NOT VERIFIED |
| SSH / nested mux | Inherited-variable uncertainty and explicit confirmation tests | NOT VERIFIED physically |
| Windows / Linux | Text fallback and portability fixture coverage | No execution on these OSes in this run |

Zellij's dumped config contains a commented `support_kitty_graphics_protocol`
example; that does not prove the active session's effective configuration. No
tmux/Zellij settings were changed. No active terminal probing, input reads,
alternate-screen entry or physical Kitty sequences were issued by acceptance
automation. Watch retains the existing text policy. Protocol tests verify
owned-image deletion, never global deletion; saves/pipes/JSON/plain/SVG/PNG do
not receive image transport.

## 10. SVG/PNG and fonts

Cards share semantic layout decisions across SVG and PNG, including omitted
content notices, module ordering, language denominators, measurement units,
known zero vs missing, coverage and avatar geometry. Tests cover requested small,
large and tall canvases, long descriptions, custom/light/dark/mono themes,
transparent/non-square avatars and missing assets. Dimensions are checked
before asset loading/raster allocation; the eight-million-pixel cap remains.

Terminal SVG remains distinct: classic compatibility and explicit modern
presets are supported. Modern SVG uses deterministic export cells rather than
the invoking terminal's viewport. Neither export path needs terminal graphics
or capability queries. XML escaping, static self-contained assets, safe colors,
clipping and absence of active content/external image references are tested.

Chrome 156.0.8078.74 rendered balanced, compact, showcase and light SVG cards
headlessly using isolated temporary profiles and disabled external host
resolution. Screenshots and the fresh PNG contact sheet were visually inspected:
identity/statistics/language/activity alignment and values agree in these
samples, without visible overlap. Other SVG engines and every theme at every
canvas size were not visually inspected. Structural/theme tests cover those
combinations; they are not a substitute for visual review.

An additional modern terminal SVG with Unicode text was rendered in Chrome and
inspected. Both modern and classic terminal SVG files also passed XML/no-escape
checks with HTTP calls forbidden. Terminal SVG retains fixed cell positioning
and configured system-font fallback, so its glyph appearance and bar shapes
are not promised to be pixel-identical to a particular terminal emulator.

The bundled DejaVu Sans fallback is located from package resources, not a
machine-specific optional font. Font and emergency bitmap regression tests pass
on Pillow 10.0, 10.4 and 11.3. Supported getbbox/getlength measurement avoids the
old organization-PNG failure. Non-Latin/combining/emoji input does not crash;
some glyphs remain unavailable. SVG browser fallback and Pillow rendering can
therefore differ in glyph coverage, not the underlying names or values.

## 11. Packaging, installation, fonts and licenses

Artifacts: `/tmp/gitfetch-07-dist/gitfetch-2.0.0-py3-none-any.whl` and
`gitfetch-2.0.0.tar.gz`. Names intentionally retain the unapproved old version.
Wheel and sdist were installed into separate disposable environments, tested
from `/tmp`, and verified against current source bytes. Both the console script
and `python -m gitfetch.main` execute. Dependencies resolve consistently with
`requirements.txt`; `uv pip check` passes in both installations.

The wheel contains 19 language-icon PNGs, the font and its notice, the icon
notice, and all three distribution-level license files. The sdist contains the
same font/license bytes. Installed font SHA-256:
`3fdf69cabf06049ea70a00b5919340e2ce1e6d02b0cc3c4b44fb6801bd1e0d22`.
No fonts are downloaded at runtime.

History records `4daa862 Delete LICENSE`, with an established MIT grant before
that deletion; current formula metadata still says MIT and package metadata
referenced LICENSE. `LICENSE` was restored byte-for-byte from
`git show 4daa862^:LICENSE`, including Copyright (c) 2026 gongahkia. No new legal
grant or copyright holder was chosen. The history of deletion is disclosed for
maintainer review rather than silently ignored.

Build metadata now uses `license = "MIT AND LicenseRef-DejaVu"` plus explicit
`license-files`, with setuptools >=77.0.3. `LicenseRef-DejaVu` identifies the
bundled font's existing full notice; it does not invent replacement terms.
The icon MIT notice is also distributed. This follows
[PyPA license metadata guidance](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/#license-and-license-files).
The previous missing/deprecated-license warnings are gone. A maintainer legal
review remains prudent; this engineering verification is not legal advice.

Both installer entrypoints were actually run against the local checkout in a
disposable venv. Snapshots of the real user's existing shell startup files were
unchanged. No sudo, global install or system installation replacement occurred.
Non-venv startup-file behavior was tested against temporary paths, including
spaces, duplicate prevention and a missing final newline. A non-venv installation
under an externally managed Python may still be rejected by pip; the README
uses a venv rather than bypassing that protection.

Formula Ruby syntax passes. All seven resource SHA-256 values match the
corresponding official PyPI metadata. This is not an actual Homebrew installation
and does not validate a future v3 archive checksum. The formula still targets
old source; its eventual versioned source and checksum must be updated together.

## 12. Security and privacy boundaries

- Provider token selection no longer falls back implicitly to GitHub on another
  service. Deliberate CLI/custom/profile/provider token sources remain usable.
- Existing authenticated/public cache-scope tests and avatar-cache permissions,
  atomic writes, symlink rejection and scope isolation pass.
- Avatar fetches validate schemes/credentials, redirects and downgrade rules,
  compressed bytes and decoded pixels, with no inherited auth headers. Offline
  paths are covered by tests that fail on attempted HTTP access.
- Untrusted terminal content is sanitized and measured; Kitty payloads come
  only from bounded prepared images. Output diagnostics are sanitized.
- SVG text/attributes are escaped; images/fonts are embedded. PNG allocation
  and text work remain bounded. No tokens or private cache metadata are added
  to exports. Adversarial provider/plugin strings are covered by existing tests.
- Disabled plugin selections now avoid source import. Explicitly enabled local
  plugins remain trusted code with user privileges; this is not isolation from
  malicious enabled plugins or arbitrary configured token commands.
- Existing config writes preserve restricted/atomic behavior. The acceptance
  run used synthetic data and disposable files, not private profile publication.

This is a focused source/regression review, not a vulnerability-database audit
of every transitive dependency or proof against a malicious local account.

## 13. Performance measurements

Command: `PYTHONPATH=tests .venv/bin/python tests/benchmark_acceptance.py`.
Synthetic fixed-date profile, no real provider network latency, 960x540 export
canvas. Median and observed sample range in milliseconds:

| Path | Median | Range |
| --- | ---: | ---: |
| In-process CLI, warm fixture cache | 9.945 | 9.436–10.128 |
| In-process CLI, offline fixture lookup | 10.022 | 9.601–13.045 |
| Whole-process offline CLI including Python startup | 487.166 | 433.999–577.507 |
| In-process CLI, cold fixture cache | 14.883 | 13.999–19.521 |
| Theme resolution | 0.023 | 0.019–0.030 |
| Terminal planner, 100x30 | 2.810 | 2.603–2.899 |
| Half-block avatar, 28 columns | 0.713 | 0.699–0.931 |
| Kitty PNG encoding in memory | 0.851 | 0.702–0.950 |
| Terminal frame including Kitty encoding | 5.343 | 3.778–7.688 |
| Shared export planning/font measurement | 49.169 | 45.709–56.409 |
| SVG serialization of prepared plan | 3.601 | 3.540–3.710 |
| PNG painting of prepared plan | 76.662 | 76.549–78.489 |

The cold fixture transport records three mocked GETs per run; primed cache and
offline runs make zero additional requests. Avatar preparation is reused for
component rendering. Tests separately assert no repeat downloads, module
execution, document building or asset decode caused by presets/exports.
Planner timing includes actual font measurement; serialization/painting reuse
the plan. T06B's roughly 45–47 ms comparable planner timing overlaps this
sample range; these data do not establish a regression or an improvement.
No end-to-end real-network speedup is claimed.

## 14. Acceptance package and manual instructions

Local artifacts (temporary, not published):

- `/tmp/gitfetch-07-acceptance/balanced.txt`, `compact.txt`, `showcase.txt`,
  `narrow.txt`: synthetic terminal previews.
- Sibling `balanced.ansi`, `compact.ansi`, `showcase.ansi`, `halfblock.ansi`:
  SGR/text captures; no Kitty APC output.
- `/tmp/gitfetch-07-acceptance/exports/`: fourteen SVG/PNG pairs:
  balanced, compact, showcase, dark, light, custom, unicode-long, partial,
  missing-avatar, narrow-tall, small, repository, organization, comparison.
- `exports/contact-sheet.png`: all fourteen raster previews, visually inspected.
- `browser-balanced.png`, `browser-compact.png`, `browser-light.png`,
  `svg-browser.png`: inspected Chrome screenshots. The showcase browser shot
  uses the same unchanged export design from the existing T06B fixture.
- `terminal-modern.svg`, `terminal-classic.svg` and `browser-terminal.png`:
  additional terminal-oriented exports; the modern browser capture was inspected.
- `/tmp/gitfetch-07-*.log`: source/installed/build/installer/benchmark evidence.
  `/tmp/gitfetch-07-package-check.py`: installed resource/entrypoint checks.

Regenerate synthetic previews without live data or golden-file edits:

```sh
PYTHONPATH=tests .venv/bin/python tests/preview_design.py --case balanced-80x24
PYTHONPATH=tests .venv/bin/python tests/preview_design.py --case compact-60x20
PYTHONPATH=tests .venv/bin/python tests/preview_design.py --case showcase-100x30
PYTHONPATH=tests .venv/bin/python tests/preview_design.py --case narrow-unicode
PYTHONPATH=tests .venv/bin/python tests/preview_exports.py --output /tmp/gitfetch-07-acceptance/exports
PYTHONPATH=tests .venv/bin/python tests/preview_avatars.py --case transparent --style halfblock --color truecolor
```

For direct physical Ghostty/Kitty acceptance, execute in that terminal, without
piping or redirecting. These previews use an isolated synthetic offline cache:

```sh
PYTHONPATH=tests .venv/bin/python tests/preview_native.py --case transparent --fit visible --confirm-kitty
PYTHONPATH=tests .venv/bin/python tests/preview_native.py --case portrait --fit visible --layout stack --confirm-kitty
PYTHONPATH=tests .venv/bin/python tests/preview_native.py --case transparent --fit original --confirm-kitty
PYTHONPATH=tests .venv/bin/python tests/preview_native.py --case transparent --fit visible --offline missing --confirm-kitty
.venv/bin/python -m gitfetch.main --graphics-info
```

`--confirm-kitty` is a user assertion about the effective path, not automatic
evidence. For Zellij first establish the active session's support/configuration;
repeat split/stack and resize/scroll/prompt-return checks inside that pane. Leave
tmux unchanged and verify its conservative text fallback. Check transparency,
alpha, text/image separation, owned cleanup and prompt placement by eye.

Browser procedure: open each generated SVG locally, compare identity, numeric
values, omitted-content notices and section alignment with its PNG, and inspect
light/dark/Unicode/small cases at native dimensions. On this Mac:

```sh
open /tmp/gitfetch-07-acceptance/exports/balanced.svg
open /tmp/gitfetch-07-acceptance/exports/compact.svg
open /tmp/gitfetch-07-acceptance/exports/showcase.svg
open /tmp/gitfetch-07-acceptance/exports/contact-sheet.png
```

For headless reproduction use the installed Chrome with a disposable profile:

```sh
'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' --headless --disable-gpu --disable-background-networking --disable-component-update --no-first-run --no-default-browser-check --user-data-dir=/tmp/gitfetch-07-chrome-review --host-resolver-rules='MAP * ~NOTFOUND' --screenshot=/tmp/gitfetch-07-browser-review.png --window-size=1000,650 file:///tmp/gitfetch-07-acceptance/exports/balanced.svg
```

Examples using an already configured/cached profile, without additional network:

```sh
gitfetch --offline --presentation modern --visual-preset showcase --format svg --save /tmp/profile-terminal.svg
gitfetch --offline --visual-preset balanced --format card --save /tmp/profile-card.svg
gitfetch --offline --visual-preset compact --format png --save /tmp/profile-card.png
gitfetch --offline --theme nord --format png --save /tmp/profile-nord.png
```

Only intentionally reviewed design changes should regenerate repository goldens
using `tests/preview_design.py --write` or `tests/preview_modern.py --write`.
Final README replacement screenshots are still missing: direct modern balanced,
compact/showcase and native-avatar terminal captures. The old screenshot is
labelled historical and was not overwritten or presented as fresh acceptance.

## 15. Release decision and next maintainer actions

1. Approve the public version. **3.0.0 is the recommendation**, because nullable
   and fractional metrics, corrected provider units and export/module behavior
   can require consumer migration. This report does not change that number.
2. Coordinate `pyproject.toml`, `gitfetch/__init__.py`, user-agent strings in
   `github_api.py`, `providers.py`, `images.py`, and eventual release artifact/
   Homebrew URL and checksum. Keep old published artifacts distinguished until
   the new ones exist. Rebuild/retest those exact final artifacts afterward.
3. Review the restored historical project license and the shipped third-party
   notices. No maintainer-only new license decision was made here.
4. Review the token-isolation correction and any prior cross-provider use. If
   an actual credential reached an unintended service, handle rotation/revocation
   through the account owner's normal process; this audit cannot establish that.
5. Complete fresh Ghostty/Kitty/Zellij physical acceptance and selected
   Linux/Windows/SSH checks; capture honest modern screenshots. Test a local
   Homebrew candidate only once it points at the intended source artifact.
6. Authorize and execute the provider live-context matrix where credentials and
   instance access are available. Treat fixture, public endpoint and authenticated
   evidence as distinct.
7. Perform maintainer review of the uncommitted diff and this report. Only after
   those gates are resolved should a separate authorized release process begin.

No unresolved reproduced P0 remains in the tested source. **RELEASE-01 remains
an explicit P1, so the current checkout must not be published as a completed v3
release.** Environment-specific unverified results remain visible rather than
being converted into PASS by successful unit tests.
