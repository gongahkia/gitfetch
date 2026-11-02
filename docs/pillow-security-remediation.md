# Tranche 07.2 — Pillow security and Python support

## Verdict and scope

**PASS for the requested Python/Pillow remediation. Overall release: NOT READY.**

Gitfetch now requires Python >=3.11 and Pillow >=13.0.0,<14.0.0. The affected
Pillow dependency and the unsupported Python 3.10 fallback are removed. Fresh
runtime installations have no reported third-party dependency advisories.

The Homebrew Pillow resource is updated using verified source bytes. Its other
four affected resource pins remain explicitly reported below. Gitfetch's public
version, main Homebrew source URL/checksum, final release process and outstanding
manual acceptance gates are unchanged.

Incoming state: `main` at `07f6987e45ce889f2db3a2f0b7151b4dcc7e7b0e`.
`docs/RELEASE-CANDIDATE-V3.md` was already untracked and was preserved untouched.
No other incoming edits were present. The incoming suite verified 621 discovered,
615 passed, 6 skipped. Recent commits began `07f6987`, `ff9fd87`, `e530498`,
`1f4c4c4`, `da98f1d`, `337a398`.

This report supersedes the unresolved Python/Pillow policy question in the
earlier release-candidate snapshot. That historical report is not rewritten.
No commit, tag, push, release, publication or public version change was performed.

## Advisory and support decision

The official advisory confirms CVE-2026-96643 affects Pillow >=11.0.0,<13.0.0
and is fixed in 13.0.0. Repeated PNG EXIF prefixes can cause excessive CPU work
through the same EXIF-orientation API used by avatar preparation.
[Official advisory](https://github.com/python-pillow/Pillow/security/advisories/GHSA-g4qv-2jxx-769h).

Pillow 13 requires Python >=3.11. Its source archive's PKG-INFO and PyPI metadata
were independently checked against the upstream support matrix.
[Pillow Python support](https://pillow.readthedocs.io/en/stable/installation/python-support.html).
The maintainer explicitly approved dropping Python 3.10 for the major release;
there is no conditional old-Pillow dependency path or compatibility shim.

## Exact dependency and support changes

| Surface | Before | After |
| --- | --- | --- |
| `pyproject.toml` Requires-Python | `>=3.10` | `>=3.11` |
| Package and flat requirements, Pillow | `>=10.0.0,<12.0.0` | `>=13.0.0,<14.0.0` |
| Conditional TOML dependency | `tomli` for Python <3.11 | Removed; built-in `tomllib` |
| Config import | `tomllib` with a `tomli` fallback | Direct `tomllib` |
| Standalone installer | Python 3.10+ guard | Python 3.11+ guard, before pip or shell mutation |
| README / migration / shell diagnostic | Python 3.10+ | Python 3.11+ and patched Pillow requirement |
| Test CI matrix | 3.10 / 3.11 / 3.12 | 3.11 / 3.12 / 3.13 / 3.14, testing Pillow 13.0.0 lower bound |
| Mypy / Ruff language target | 3.10 / py310 | 3.11 / py311 |
| Homebrew Pillow resource | 11.3.0 | Verified 13.0.0 source |

The existing static-analysis and opt-in provider workflows already run Python
3.12 and need no floor change. GitHub workflows were not triggered here. Local
3.13/3.15 execution was unavailable; local 3.14 was tested. The Homebrew Python
dependency remains `python@3.12`, which satisfies the new floor.

Ruff retains the established datetime spellings by excluding the newly applicable
style-only UP017/FURB162 rules rather than rewriting provider/date logic. No
security advisory ID was ignored or suppressed. Other runtime dependency ranges
remain unchanged; a clean resolution is not a claim that every older version
permitted by those ranges has been independently security-cleared.

## Pillow 13 compatibility findings and smallest repairs

[Pillow 13 release notes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html)
were reviewed against actual calls:

- Removed I-mode PNG saving is not used: prepared avatars are RGBA and card
  painters save RGB. Removed/changed `fromarray`, child-image, private show,
  ImageCms metadata and old MakerNote APIs are not used by Gitfetch.
- Straight RGBA is used, so the premultiplied-color API change does not require
  changes. Large-image thumbnail/resampling and font behavior remain covered by
  the existing tests; no alpha or resource limit was relaxed.
- `Image.getdata()` now emits deprecation warnings. These reached captured CLI
  stderr in compatibility tests. Five encoder calls now use the supported
  `get_flattened_data()` tuple API; the same indexed pixel algorithm is retained.
  Two alpha assertions also use that API. No warning filter was added.
- Repeated invalid EXIF prefixes are rejected promptly with SyntaxError by the
  patched parser. Existing AvatarLoader error handling already discards that
  invalid cached asset and safely returns no avatar offline. Normal EXIF rotation
  and partial alpha remain correct. No custom EXIF parser was introduced.

One oriented synthetic JPEG preview changed slightly. An independent comparison
of the **same frozen JPEG** showed identical prepared RGBA bytes in Pillow 11.3
and 13.0. LANCZOS sample bytes changed by at most 2, and grayscale samples by at
most 1. The fixture helper now reads the committed lossy JPEG instead of mixing
new encoder output into a decoder comparison. Only `oriented.txt` was regenerated:
three ASCII rows changed. The JPEG bytes, other avatar goldens and all terminal
design goldens remain unchanged. This is a numerical resampling appearance
difference, not a placement, aspect-ratio or fitting change.

## Security safeguards and regression coverage

Avatar preparation still enforces:

- 5 MiB compressed input; 4,194,304 decoded pixels; maximum source edge 8192.
- PNG/JPEG/GIF/WEBP/BMP allowlist, bounded EXIF-oriented preparation to 1024 pixels
  per edge, preserved alpha and stripped prepared-image metadata.
- Existing URL/redirect validation, cache scoping/permissions, strict offline
  behavior and asset/decode memoization.
- Native Kitty edge cap 512 and PNG payload cap 2 MiB; card allocation cap
  eight million pixels. Cursor/cleanup/detection/watch policies are untouched.

Those safeguards complement the patched dependency. They are not represented as
fixing the EXIF parser vulnerability. `images.py`, avatar caching, Kitty encoding,
terminal frame output and graphical painters did not need code changes.

Two targeted regressions were added:

1. A synthetic PNG contains 750,000 repeated EXIF prefixes (about 4.5 MB), within
   the compressed limit and with a tiny decoded image. Raw chunk insertion avoids
   an image writer normalizing the test away. A subprocess has a ten-second
   containment deadline; the offline loader safely rejects the asset. A normal
   EXIF-orientated RGBA PNG still rotates 32×16 to 16×32 and retains alpha=128.
2. The installer rejects a simulated Python 3.10 interpreter before any pip
   invocation or shell-file operation.

Actual negative checks also confirm the built wheel is rejected on Python 3.10,
the standalone installer prints `Python 3.11+ is required` there, and the resolver
rejects combining the wheel with Pillow 11.3.0. The old interpreter was used only
for these negative checks, not as a supported installation or fallback path.

The complete suites retain avatar decoding/security, alpha, fitting, resizing,
all text fallbacks, Kitty protocol, cursor/frame output, provider request-count,
offline/cache, module/plugin, SVG/PNG/summary, font and resource-limit coverage.
No provider requests or repeated module evaluation were introduced.

## Verified Homebrew Pillow source

Downloaded from the official PyPI sdist URL:

```text
https://files.pythonhosted.org/packages/ce/a4/9cc30690a394a8305e8be4c9036aa16d0dfddadd09079860b582f562496d/pillow-13.0.0.tar.gz
```

- Actual source archive: `/tmp/gitfetch-072-downloads/pillow-13.0.0.tar.gz`.
- Size: **47,058,631 bytes**.
- Computed SHA-256, independently matched to PyPI metadata:
  `cdcd1ba258178f7356d74170c9a81ba4eab6a5d55748bc402a5a2a6fe6be3510`.
- Archive PKG-INFO: version 13.0.0, Requires-Python >=3.11.
- Verification record: `/tmp/gitfetch-072-downloads/pillow-source.json`.

Only the Pillow resource URL/checksum was changed. An explicit comparison with
HEAD confirms Gitfetch's main source URL and checksum are identical to their
incoming values. This hash is for **Pillow**, not a future Gitfetch release.
No Gitfetch 3.0.0 source checksum was created or invented.

Formula Ruby syntax passes. Actual Homebrew installation/source compilation is
NOT VERIFIED: the main recipe still targets the old 2.0 artifact, and other
resource advisories remain. This is a correct staged Pillow resource update,
not a claim that the whole formula is release-ready.

## Dependency audits and remaining findings

Maintained scanner: pip-audit 2.10.1, current public advisory database. No
`--ignore-vuln`, `--fix`, waived findings or skipped vulnerable dependency was
used to obtain a green result.

Fresh installed runtime resolution:

| Package | Version | Reported advisories |
| --- | --- | ---: |
| Pillow | 13.0.0 | 0 |
| Requests | 2.34.2 | 0 |
| urllib3 | 2.8.0 | 0 |
| certifi | 2026.10.23 | 0 |
| idna | 3.20 | 0 |
| charset-normalizer | 3.5.2 | 0 |
| wcwidth | 0.9.4 | 0 |

Gitfetch's unpublished local 2.0.0 identity is not found in the scanner's PyPI
database; that is disclosed rather than treated as a source-code security audit.
Runtime audit output: **No known vulnerabilities found**. This is a dated
advisory check, not a guarantee of vulnerability absence in native/OS libraries.

The actual formula's pinned-resource audit still returns failure:

| Unchanged resource | Version | Raw advisory records | Distinct scanner IDs |
| --- | --- | ---: | ---: |
| certifi | 2025.8.3 | 2 | 1 |
| idna | 3.10 | 2 | 1 |
| Requests | 2.32.5 | 2 | 1 |
| urllib3 | 2.5.0 | 10 | 6 |

Pillow 13.0.0, charset-normalizer and wcwidth have zero formula audit records.
The 16 remaining records include duplicates/aliases and are not 16 proven
Gitfetch exploits. Existing reachability distinctions still apply; e.g. the
Requests advisory concerns a particular utility rather than ordinary HTTP alone.
The older certifi/urllib3 network pins require separate release-blocker work and
the complete formula should be re-audited after approved updates. These resources
were left unchanged to keep this tranche focused and avoid unverified checksums.

Reproduction:

```sh
uvx --from pip-audit==2.10.1 pip-audit --path /tmp/gitfetch-072-wheel-env/lib/python3.12/site-packages --format json --output /tmp/gitfetch-072-runtime-audit.json
uvx --from pip-audit==2.10.1 pip-audit -r /tmp/gitfetch-072-formula-requirements.txt --no-deps --disable-pip --format json --output /tmp/gitfetch-072-formula-audit.json
```

The latter input is generated directly from all seven formula resource pins.
Both full JSON results and diagnostics are retained; the nonzero formula audit
was not relabelled PASS.

## Complete verification results

All environments were created cleanly under `/tmp`, without global installation.

| Environment | Discovered | Passed | Skipped | Seconds |
| --- | ---: | ---: | ---: | ---: |
| Python 3.11.16 + Pillow 13.0.0 | 623 | 617 | 6 | 30.310 |
| Python 3.12.14 + Pillow 13.0.0 | 623 | 617 | 6 | 31.854 |
| Python 3.14.7 + Pillow 13.0.0 | 623 | 617 | 6 | 30.776 |
| Installed wheel, Python 3.12.14 + Pillow 13.0.0 | 623 | 617 | 6 | 50.110 |
| Installed sdist, Python 3.11.16 + Pillow 13.0.0 | 623 | 617 | 6 | 49.248 |

All five rows PASS. The six opt-in provider/authenticated tests remain skipped,
not passed. No credentialed or live-provider tests were enabled. Installed suites
run from `/tmp`, with tests/fixtures in the checkout and runtime imports in the
disposable site-packages. Installer tests intentionally read the standalone
checkout installer.

Commands:

```sh
uv venv --python 3.11 /tmp/gitfetch-072-311
uv venv --python 3.12 /tmp/gitfetch-072-312
uv venv --python 3.14 /tmp/gitfetch-072-314
uv pip install --python /tmp/gitfetch-072-311/bin/python -e '.[dev]' 'Pillow==13.0.0'
uv pip install --python /tmp/gitfetch-072-312/bin/python -e '.[dev]' 'Pillow==13.0.0'
uv pip install --python /tmp/gitfetch-072-314/bin/python -e '.[dev]' 'Pillow==13.0.0'
/tmp/gitfetch-072-311/bin/python -m unittest discover -s tests
/tmp/gitfetch-072-312/bin/python -m unittest discover -s tests
/tmp/gitfetch-072-314/bin/python -m unittest discover -s tests
/tmp/gitfetch-072-312/bin/ruff check .
/tmp/gitfetch-072-312/bin/mypy gitfetch
uv build --out-dir /tmp/gitfetch-072-dist
uvx --from twine==7.0.0 twine check /tmp/gitfetch-072-dist/gitfetch-2.0.0-py3-none-any.whl /tmp/gitfetch-072-dist/gitfetch-2.0.0.tar.gz
```

For each of 3.11/3.12/3.14, `python -m compileall -q gitfetch installer tests`
and `uv pip check --python ENV/bin/python` pass. Ruff passes; mypy reports no
issues in 29 runtime files. Shell/formula syntax and `git diff --check` pass.
Build and Twine checks pass without warnings. The existing package version is
still 2.0.0 intentionally; these artifacts are private verification builds.

Installed-distribution commands, run from `/tmp` after creating fresh wheel/sdist
venvs and installing each corresponding artifact:

```sh
/tmp/gitfetch-072-wheel-env/bin/python -m unittest discover -s <checkout>/tests
/tmp/gitfetch-072-sdist-env/bin/python -m unittest discover -s <checkout>/tests
/tmp/gitfetch-072-wheel-env/bin/python /tmp/gitfetch-072-inspect.py
/tmp/gitfetch-072-sdist-env/bin/python /tmp/gitfetch-072-inspect.py
uv pip check --python /tmp/gitfetch-072-wheel-env/bin/python
uv pip check --python /tmp/gitfetch-072-sdist-env/bin/python
```

The inspection script verifies all 29 runtime module bytes against source,
wheel/sdist and installed files; Python/Pillow metadata; removal of tomli;
both CLI entrypoints, config/modules/diagnostics/completions, 19 icons, bundled
font and complete license notices. Installed font SHA-256 is unchanged:
`3fdf69cabf06049ea70a00b5919340e2ce1e6d02b0cc3c4b44fb6801bd1e0d22`.
No optional system font is required. Bash/Zsh completion syntax was checked;
Fish execution remains unavailable.

Fourteen SVG/PNG pairs were generated from the installed wheel in
`/tmp/gitfetch-072-previews/`, structurally validated, and the PNG contact sheet
was visually inspected. Preset geometry/theme hierarchy remains coherent.
Existing glyph-coverage limits remain. No fresh physical Kitty/multiplexer,
Linux/Windows/SSH or browser appearance acceptance is claimed by this tranche.

Evidence logs use `/tmp/gitfetch-072-final-{311,312,314}.log`,
`/tmp/gitfetch-072-installed-{wheel,sdist}.log`, and the corresponding build,
Twine, audit, inspection and negative-install logs.

## Exact files changed

| File | Change |
| --- | --- |
| `pyproject.toml` | Python/Pillow floor, remove tomli, align tool targets while retaining datetime style |
| `requirements.txt` | Matching Pillow bound and removal of conditional tomli |
| `.github/workflows/tests.yml` | Supported Python matrix and Pillow 13 lower-bound test |
| `gitfetch/config.py` | Built-in TOML import only |
| `gitfetch/render.py` | Supported flattened pixel access in the existing encoders |
| `installer/installation.py` | Python 3.11 minimum guard |
| `installer/mainInstall.sh` | Matching minimum-version diagnostic |
| `Formula/gitfetch.rb` | Verified Pillow 13 resource URL/checksum only |
| `README.md` | Current installation minimum and migration link |
| `docs/MIGRATION-V3.md` | Intentional Python 3.10 removal, security rationale and new-venv instructions |
| `tests/avatar_fixtures.py` | Freeze the existing synthetic lossy JPEG input |
| `tests/fixtures/avatars/oriented.txt` | Three resampling-sensitive ASCII rows |
| `tests/test_avatar_assets.py` | Supported pixel accessor in alpha assertion |
| `tests/test_terminal_graphics.py` | Supported pixel accessor in alpha assertion |
| `tests/test_pillow_security.py` | Two targeted security/support regressions |
| `docs/pillow-security-remediation.md` | This report |

The preexisting untracked release-candidate report is not a new tranche file.
No source image/font/cache was destructively changed. No layout engine, graphics
protocol, provider request, JSON contract or export design was added or replaced.

## Release-readiness impact

The Pillow portion of the dependency blocker and the Python-support decision are
resolved with explicit maintainer authorization and passing clean-environment
evidence. Existing Python 3.10 users must upgrade their interpreter and create a
new environment; no unsupported dependency branch is promised.

The broader release is still NOT READY: the remaining formula resource advisories,
the final Gitfetch 3.0.0 version/artifact/checksum work, actual Homebrew channel
installation and previously unverified environment/provider acceptance remain.
No final release step was started. HEAD remained the incoming commit during
verification; all focused changes remain uncommitted.
