# Tranche 02: provider semantics and metric correctness

## Starting state and boundaries

Started at `90e8935f433b78020e33032c79a4ccc3deb6d7af`, branch `main`.
The incoming worktree contained Tranche 01 changes in `Formula/gitfetch.rb`,
`gitfetch/{cli,formats,modes,render}.py`, `pyproject.toml`, `requirements.txt`,
and untracked `docs/`, `gitfetch/terminal_text.py`, `tests/test_contracts.py`,
`tests/test_terminal_text.py`. These were preserved. The initial suite discovered
137 tests: 131 passed, 6 opt-in live/integration tests skipped.

This tranche changes metric interpretation and corrective labels, not layout,
themes, graphics, configuration, providers, or the presentation architecture.
CLI flags, module ordering, plugin registration, token resolution, exit-code
conventions, and output envelopes remain in place.

## Internal representation

`gitfetch.semantics.Measurement` is frozen metadata attached to contexts and
`ModuleResult.measurements`. Its fields distinguish available, unavailable,
unsupported, and authentication-required data independently of coverage
(complete, partial, unknown). It records provider, unit, scope, source, reason,
sample size, denominator, observed date bounds, sampling policy, repository
attempt/failure/missing counts, and all collected language totals. These
attributes are internal; the existing serializers still explicitly emit only
`ModuleResult.data`.

`RepositoryCoverage` separates API-returned, eligible, retained, known-public,
and known-private counts, selection scope, and filters. Counts describe what
was returned; they do not promise that token permissions expose the entire
account. `LanguageData` and `HeatmapData` remain dict/list compatible while
carrying response availability independently of an empty payload. Old
positional `ModuleResult` and `GitHubContext` construction remains valid.
Line-only plugins and plugins constructing `ModuleResult` need no changes.
Consumers doing arithmetic on normalized metrics must handle unavailable data.

A real numeric zero stays zero. Missing fields do not imply zero. A missing
field alone does not prove authentication is required: only a module's declared
requirement or an explicit authorization error establishes that status.

## Provider investigation and corrections

| Provider | Profile language measurement | Repository language measurement | Limitations |
| --- | --- | --- | --- |
| GitHub | Sum genuine byte counts in selected repositories | Bytes; percentages use the entire returned map | Existing sample cap and bounded workers retained; not necessarily whole profile |
| GitLab | Count projects containing each positive-usage language | Original per-project decimal percentages | Prevalence is multi-label: one project can count toward several languages; never byte-weighted |
| Bitbucket Cloud | Count repository primary-language metadata | Primary language only | Not an exhaustive analysis; missing primary language contributes no language |
| Gitea | Sum language endpoint byte counts | Bytes | Endpoint availability and repository sampling constrain coverage |
| Forgejo | Same verified byte response contract | Bytes | Instance versions and permissions may differ |
| Codeberg | Forgejo adapter byte response contract | Bytes | No live instance validation performed |

GitLab's fractional percentages were confirmed against its official
[project language usage endpoint](https://docs.gitlab.com/api/projects/#retrieve-programming-language-usage-information).
The old accumulator truncated them with `int()` and incorrectly labeled the
result as bytes. Profile prevalence now counts positive language detections per
project, including fractional values such as `0.5`; zero usage does not count
as a detection. Repository mode displays the original percentages without
renormalizing them.

GitHub documents bytes in its
[repository languages endpoint](https://docs.github.com/en/rest/repos/repos#list-repository-languages).
The Gitea and Forgejo implementations explicitly serialize language `Size`
and describe the endpoint in bytes:
[Gitea source](https://github.com/go-gitea/gitea/blob/v1.24.0/routers/api/v1/repo/language.go),
[Forgejo source](https://codeberg.org/forgejo/forgejo/src/branch/forgejo/routers/api/v1/repo/language.go).
Codeberg uses the existing Forgejo-compatible adapter; deployments can still
vary, so failed responses are not treated as measurements.

The module stores **all** collected language totals and their denominator
before truncating display to the configured limit. Byte percentages are never
reconstructed from just the displayed top five. Prevalence denominators count
successful repository responses, including empty responses; missing endpoints,
failed requests, invalid measurements, and sampling are recorded separately.
Ties sort by count, then language name, independently of worker completion.
A complete scan of selected repositories is distinct from a complete profile.
Whole-profile completeness requires matching a reported public total, public
scope, no active filters, and no sampling/failures/missing endpoints.

Bitbucket's primary-language placeholder `n/a` was also incorrectly parsed as
language `a` by splitting at the last slash. Prefix removal fixes that error
and preserves language names containing slashes.

Confirmed profile/repository normalization bugs corrected:

- Missing GitLab and Gitea-family followers/following no longer default to zero.
- Unsupported public gist counts, and Bitbucket workspace social counts, are
  unavailable rather than fictional zero measurements. Snippet modules remain
  supported where they already were; snippets are not a measured public-gist
  total.
- Missing GitLab/Gitea stars, forks, watchers, issues and size stay missing.
  GitLab watchers are no longer aliases of stars; missing Gitea watchers no
  longer fall back to stars.
- GitLab repository size uses optional `statistics.repository_size` in bytes.
  It does not request statistics or invent a zero when absent. Bitbucket size
  is displayed in bytes, following its repository representation. Existing
  GitHub/Gitea size conventions remain unchanged.
- GitLab/Gitea/Bitbucket generic activity timestamps are no longer called push
  timestamps. Maintainer activity uses only actual push dates, reports the
  known-date denominator, and cannot turn wholly missing dates into zero
  measured activity.
- Filtered repository lists no longer overwrite `public_repos`. Group project
  counts are not assumed to be public counts. Unknown public counts remain
  unknown; fetched/selected counts are labeled separately.
- Public mode excludes known-private and unknown-visibility repositories on
  GitLab/Gitea/Bitbucket, even when a token exposes them. Viewer mode still
  requires a matching authenticated target. Gitea viewer profile collections
  exclude collaborations owned by someone else. GitLab group profiles exclude
  shared projects owned by a different namespace when ownership is supplied.
- Organization zero public counts are preserved. Fetched star sums are labeled
  as fetched, and missing metrics prevent incomplete sums from appearing exact.
- Top repositories exclude missing star measurements; comparison and optional
  aggregate modules no longer substitute zero for missing inputs.
- Missing optional GitHub GraphQL PR/issue/contribution breakdown counts are
  unavailable rather than zero; explicitly returned zero remains valid.
- Gitea push activity no longer invents one commit per event; GitLab missing
  push commit counts also remain unknown. Sample-based Gitea/Bitbucket repository
  contributors are explicitly labeled as a retrieved commit sample. Non-GitHub
  activity is labeled visible, since token permissions can expose more than
  public activity without supplying an event-level visibility flag.
- Incomplete star rankings identify their known-star scope; organizations with
  no star measurements retain an alphabetical, explicitly unranked repository
  listing rather than inventing a numerical order. Missing comparison language
  metadata is labeled incomplete rather than proving no language overlap.

## Contribution calendars and streaks

The official [Gitea heatmap endpoint](https://docs.gitea.com/api/operations/user-get-heatmap-data/)
returns timestamped contribution records, not commit totals or coverage bounds.
The inspected [Gitea implementation](https://github.com/go-gitea/gitea/blob/v1.24.0/models/activities/user_heatmap.go)
counts activity actions, applies viewer permissions, uses a bounded lookback,
and can successfully return an empty array when activity is not readable.
The [Forgejo heatmap implementation](https://codeberg.org/forgejo/forgejo/src/branch/forgejo/models/activities/user_heatmap.go)
also counts activity actions and applies visibility and lookback conditions;
its timestamps do not certify continuous coverage.
Consequently, a successful empty response means **zero returned records with
unknown visibility/window coverage**, not a proven zero-activity year.

- Failures carry unavailable/auth-required status and do not produce calendars.
- Explicit dated zero records remain dated zero measurements.
- Nonempty payloads containing no valid records are unavailable, not zero.
- All valid returned timestamps are preserved, grouped into UTC dates and
  Sunday-based weeks. No 84-day truncation or zero padding remains.
- Gitea's total is a sum of returned activity counts, never relabeled commits,
  issues, reviews, or annual contributions. Unsupported breakdown fields are
  no longer manufactured inside its internal GraphQL-compatible bundle.
- Observed earliest/latest dates are recorded, but do not establish continuous
  coverage. Missing days and weeks remain unknown. Existing heatmap/sparkline
  blank cells preserve calendar spacing; labels identify unknown coverage.
- Streaks break across missing dates. Current streak requires observed data
  anchored to UTC today (allowing an explicitly measured zero today while
  yesterday is active). Historical/stale data cannot establish a current
  streak. Longest means **longest observed in this window**, never longest ever.
- Display labels use window totals and actual bounds, not “year total”.
  Cadence windows select dates, not the last N sparse records. A zero sparkline
  peak remains zero; missing dates are not compressed into adjacent days.
- GitHub's contribution dates/counts and distinct commits/reviews remain
  provider-defined; its contiguous returned calendar window is retained.

No new requests discover instance versions or guess a Gitea/Forgejo deployment's
lookback setting. These uncertainties remain explicit rather than being filled
with zeros. Authentication-scoped caches prevent mixing viewers' responses.

## Comparisons

Only finite, nonnegative measured numbers enter rankings; real zero is valid.
Unavailable users are listed separately. Fewer than two measurements produces
an insufficient-data explanation. Equal values use `=` and alphabetical tie
ordering. Comparisons refuse mixed providers, units, public/viewer scopes, or
filter scopes. Stars/forks refer explicitly to selected repositories, not a
purported account lifetime total. Language overlap/top language use repository
primary-language metadata, not byte distributions. Existing metric field names
and summary envelope are retained.

## Public JSON compatibility: explicit corrective exceptions

Envelope schemas, module names, field names, raw text values, and output-format
selection are unchanged. Internal metadata is not automatically added to JSON.
Two semantic corrections cannot preserve every historical leaf type/value:

1. Numeric fields that previously fabricated zero or partial sums are now
   **number-or-null**. Keeping `0` and adding a status field would still publish
   an incorrect measurement to existing consumers. This is an intentional,
   documented widening, not a promise of strict leaf-type compatibility.
   It affects normalized user `public_repos`, `followers`, `following`,
   `public_gists`; normalized repository star/fork/watcher/subscriber/issue/size
   fields when missing or unsupported; missing contributor `contributions`;
   comparison summary `followers`, `following`, `public_repos`, `stars`, `forks`;
   unknown `streaks.current`; optional maintainer aggregates/date counts,
   public-event commit counts and missing GraphQL breakdown/PR/issue counts.
   These normalized objects occur in identity/stats, repository lists and other
   existing module data; no field is removed. Correct numeric values keep their
   numeric types. Normalized unknown `private` and unproven `pushed_at` likewise
   become null instead of claiming a boolean or push timestamp.
2. GitLab profile languages now use the existing repository-count list-entry
   variant `{ "language": str, "repositories": int }`, already used by
   Bitbucket, instead of the misleading `{ "language": str, "bytes": int }`.
   Adding a numeric `bytes` alias cannot be correct because no bytes were
   measured. Repository-mode language dictionaries retain decimal percentages.

Consumers should use `value is not None`, not truthiness, and branch language
entries by measurement field. No broad schema versioning is introduced.
Gitea contribution lists contain actual observed dates, with empty week lists
for unknown gaps where needed; unknown periods no longer appear as dated zeros.
Unavailable calendar modules can emit a diagnostic and their existing empty
payload rather than silently disappearing.

## Cache, requests and performance

Cache keys, provider/base-URL/token isolation, TTLs, refresh and offline policy
are unchanged. A cache audit found affected language, profile, repository and
heatmap entries store raw responses, not aggregate language totals or synthetic
calendars. Re-normalizing those raw entries fixes interpretation without a
cache flush or version bump. Old GitLab decimal maps and empty Gitea heatmaps
are tested offline. Old empty heatmaps still do not establish coverage.

Language work remains bounded by `max_repos` and `workers`; no new statistics,
authenticated, version-discovery or per-day requests were added. Tests count
language requests, concurrent workers, cache reuse, and the optional single
heatmap request. Bitbucket primary-language collection makes no HTTP calls.
Existing Bitbucket repository detail fork/watcher requests remain unchanged.
No performance improvement is claimed.

## Regression expectations and remaining uncertainty

`tests/test_semantics.py` adds deterministic fixtures with a network-failure
guard. Tranche 01 contract/safety/plugin tests remain enabled and unchanged.
Four existing assertions were deliberately corrected: one organization sum label,
one historical-current-streak assertion, and two GitLab inferred-total assertions
(the group fixture now explicitly specifies public visibility).

No live provider tests are enabled. Instance-specific language analysis freshness,
permission-filtered repository completeness, private contribution visibility,
and Gitea-family coverage remain unverified. A successful response does not
establish complete account coverage. Gitea/Bitbucket contributors remain bounded
samples, not lifetime counts. Existing caching of stale successful responses
retains its original behavior; no freshness guarantee is added. Unknown profile
metrics and selected-collection totals should be carried into Tranche 03 without
inventing measurements or exposing internal provenance by accident.

## Final verification and changed files

Verdict: **PASS**, with the explicit JSON leaf-type corrections above and the
preexisting packaging warnings below. Final suite: **204 discovered, 198 passed,
6 skipped**; 67 new semantic tests. No existing tests were removed. Tranche 01's
contract and terminal-text test files, terminal-text utilities, renderer,
dependencies, formula and original foundation report remain byte-for-byte
unchanged. Changes to its CLI/formats/modes files are layered metric fixes.
This agent issued no commit, tag, publish or release commands. During final
validation another process advanced `main` through commits `63b0523`
(`cleanedup`) and `607c166` (`tanaka`), incorporating the work in progress.
The latter HEAD was observed at the final inspection; runtime and test sources
were byte-identical to the final tested build copy. These intervening commits
were preserved. The initial HEAD and dirty worktree recorded above remain the
starting-state audit, rather than a claim that HEAD never changed.

Added: `gitfetch/semantics.py`, `tests/test_semantics.py`, this report.
Modified for this tranche: `gitfetch/cli.py`, `gitfetch/formats.py`,
`gitfetch/github_api.py`, `gitfetch/modes.py`, `gitfetch/modules/builtin.py`,
`gitfetch/providers.py`, `tests/test_modes.py`, `tests/test_modules.py`,
`tests/test_providers.py`.

Commands executed from the checkout unless otherwise specified:

| Check | Exact command | Result |
| --- | --- | --- |
| Incoming baseline | `.venv/bin/python -m unittest discover -s tests -v` | 137 tests, 131 passed, 6 skipped |
| Final Python 3.12.14 | `.venv/bin/python -m unittest discover -s tests` | 204 tests, 198 passed, 6 skipped |
| Final Python 3.10.21 | `/tmp/gitfetch-foundation-310/bin/python -m unittest discover -s tests` | Same 204/198/6 |
| Ruff | `/tmp/gitfetch-foundation-312/bin/ruff check gitfetch tests installer` | PASS |
| mypy, Python 3.10 target | `/tmp/gitfetch-foundation-312/bin/mypy gitfetch` | PASS, 18 source files |
| Compile, Python 3.10 | `/tmp/gitfetch-foundation-310/bin/python -m compileall -q gitfetch` | PASS |
| Patch whitespace | `git diff --check` | PASS |
| Dependencies | `uv pip check --python /tmp/gitfetch-foundation-312/bin/python` | PASS |
| Dependencies, Python 3.10 | `uv pip check --python /tmp/gitfetch-foundation-310/bin/python` | PASS |
| Checkout dependencies | `uv pip check --python .venv/bin/python` | PASS |

The environments do not include the `pip` module; attempted `python -m pip
check` could not run. The equivalent dependency checks above used installed
`uv` successfully.

Packaging used a copy of the source, excluding `.git`, virtual environments,
caches and build artifacts, so existing editable-install metadata was not
modified. The final build directory was
`/tmp/gitfetch-tranche02-final-l55in3i1` (`PACKAGE_ROOT` below):

```sh
/tmp/gitfetch-foundation-312/bin/python -m build --no-isolation --sdist --wheel "$PACKAGE_ROOT/source" --outdir "$PACKAGE_ROOT/dist"
uv pip install --python /tmp/gitfetch-foundation-312/bin/python --no-deps --link-mode copy --target "$PACKAGE_ROOT/installed" "$PACKAGE_ROOT/dist/gitfetch-2.0.0-py3-none-any.whl"
# Run from /tmp, outside the checkout:
PYTHONPATH="$PACKAGE_ROOT/installed" /tmp/gitfetch-foundation-312/bin/python -m unittest discover -s /home/gongahkia/coding/projects/gitfetch/tests
```

All passed; the installed wheel also ran 204 tests (198 passed, 6 skipped).
A Python 3.10 installed-wheel smoke script asserted its import path came from
`$PACKAGE_ROOT/installed`, exercised the CLI version exit, and checked legacy
`ModuleResult`/`GitHubContext` constructors and zero/missing measurements: PASS.

The build retains two existing warnings: deprecated `project.license` table
metadata and the repository's missing root `LICENSE` file. No license or release
metadata was changed. **NOT VERIFIED:** live provider APIs, actual personal
credentials, deployment-specific coverage and a Homebrew installation. The six
opt-in integration tests remained skipped throughout.

The corrected values and explicit internal provenance are ready for Tranche 03's
shared presentation document. That document and the responsive redesign have
not been started.
