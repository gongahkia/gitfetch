# Gitfetch 3.0.0 — release-candidate readiness

Assessment: 2026-11-02. **Preparation only.** All commit, tag, push, publication,
version-edit and formula-edit commands below are future maintainer instructions,
not actions executed by this assessment.

## Verdict

**NOT READY to publish the current artifacts as Gitfetch 3.0.0.**

The application passes its engineering suite and the maintainer has accepted all
three modern terminal presets and the revised SVG/PNG designs. Those appearance
gates are closed; further aesthetic work is not a release prerequisite.

Three concrete areas remain:

1. **Dependency security:** a fresh advisory audit reports affected dependency
   versions, including Pillow in accepted image-processing paths and older
   Homebrew network dependencies. Compatibility PASS is not security clearance.
   Pillow's current security fixes also create a Python 3.10 support decision.
2. **Release identity and final-artifact verification:** current package/runtime
   metadata is still 2.0.0. No final 3.0.0 wheel/sdist exists or has been tested.
3. **Homebrew channel readiness:** the formula still points to the old 2.0 source,
   has old resource pins, and has not been installation-tested against candidate
   bytes. It must not be advertised as installing v3 until updated and tested.

Unverified lifecycle/platform/provider checks are listed separately. They must
be completed or explicitly accepted/documented by the maintainer; successful
unit tests do not turn them into physical or live integration evidence.

## Repository and documentation evidence

- Incoming HEAD: `07f6987e45ce889f2db3a2f0b7151b4dcc7e7b0e`, branch `main`.
- Incoming worktree: clean. Recent commits: `07f6987`, `ff9fd87`, `e530498`,
  `1f4c4c4`, `da98f1d`, `337a398`, `14ac337`, `6b507d6`.
- Final observed HEAD remains the incoming commit. This report is the only
  intended checkout change. No source, version, checksum or existing report
  was edited; no Git mutation or publication was performed.
- The three requested documents were reviewed: [T07 readiness](RELEASE-READINESS-V3.md),
  [migration](MIGRATION-V3.md), and [T07.1 polish](export-visual-polish.md).
- Engineering documentation inspected spans rendering foundation, provider
  semantics, presentation model, responsive design, avatar assets/alignment,
  terminal graphics/design system, and export design/polish. Earlier documents
  preserve their tranche-time counts and NOT VERIFIED statements. Current
  source, current tests and subsequent maintainer acceptance take precedence
  over those historical statements.
- Local files were used as evidence. No remote branch or old published archive
  was substituted for this checkout.
- Local tags are `1.0` and `2.0`; no local `v3.0.0` tag exists. Remote tag and
  release state must be checked immediately before a separately authorized release.

## Current automated results

Host: macOS 15.7.7, x86_64. Full suites were freshly rerun:

| Environment | Discovered | Passed | Skipped | Seconds | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| Python 3.10.21 / Pillow 10.0.0 | 621 | 615 | 6 | 70.778 | PASS |
| Python 3.10.21 / Pillow 11.3.0 | 621 | 615 | 6 | 38.383 | PASS |
| Python 3.12.14 / Pillow 10.4.0 | 621 | 615 | 6 | 47.585 | PASS |
| Python 3.12.14 / Pillow 11.3.0 | 621 | 615 | 6 | 36.453 | PASS |
| Installed wheel: Python 3.12.14 / Pillow 11.3.0 | 621 | 615 | 6 | 26.359 | PASS |
| Installed sdist: Python 3.10.21 / Pillow 10.0.0 | 621 | 615 | 6 | 54.873 | PASS |

Installed suites ran from `/tmp`, importing `gitfetch` from disposable
site-packages. Tests/fixtures came from the checkout; standalone installer tests
intentionally load the checkout's installer. No tests were added or skipped to
obtain these results. The six skips remain five opt-in provider smoke tests and
one authenticated GitHub/GraphQL integration test. No credentialed test ran.

| Check | Result |
| --- | --- |
| Ruff, entire checkout | PASS |
| Mypy, 29 runtime files | PASS |
| Python 3.10/3.12 compilation | PASS |
| Wheel and sdist build | PASS, no build warnings |
| Twine 7.0.0 metadata/readme checks, both distributions | PASS |
| Installed dependency consistency, both environments | PASS (`uv pip check`) |
| Console and module entrypoints, help/version, config/modules/diagnostics | PASS outside checkout |
| Completion generation | PASS; Bash/Zsh syntax PASS; Fish execution NOT VERIFIED (not installed) |
| Font/license/resource and source-byte checks | PASS |
| Fourteen installed-package SVG/PNG fixture pairs | PASS XML/PNG validation, no terminal escapes |
| Shell installer / formula syntax | PASS (`bash -n`, `ruby -c`) |
| Whitespace diff check | PASS |
| Dependency advisory audit | **FAIL / triage required**, details below |
| Final versioned 3.0.0 artifacts | NOT VERIFIED; not built because version changes are not authorized here |

Validation commands executed:

```sh
.venv/bin/python -m unittest discover -s tests
/tmp/gitfetch-default-310/bin/python -m unittest discover -s tests
/tmp/gitfetch-06b-pillow10/bin/python -m unittest discover -s tests
/tmp/gitfetch-06b-312-pillow104/bin/python -m unittest discover -s tests
.venv/bin/ruff check .
.venv/bin/mypy gitfetch
.venv/bin/python -m compileall -q gitfetch installer tests
/tmp/gitfetch-default-310/bin/python -m compileall -q gitfetch installer tests
bash -n installer/mainInstall.sh
ruby -c Formula/gitfetch.rb
uv build --out-dir /tmp/gitfetch-rc-dist
uvx --from twine==7.0.0 twine check /tmp/gitfetch-rc-dist/gitfetch-2.0.0-py3-none-any.whl /tmp/gitfetch-rc-dist/gitfetch-2.0.0.tar.gz
git diff --check
```

The installed environments were created with `uv venv`, then installed with
`uv pip install --python ENV/bin/python ARTIFACT`. The sdist environment also
pinned `Pillow==10.0.0` to exercise the declared lower bound. From `/tmp`:

```sh
/tmp/gitfetch-rc-wheel-env/bin/python -m unittest discover -s /Users/gabrielongtemasek/Desktop/personal/gitfetch/tests
/tmp/gitfetch-rc-sdist-env/bin/python -m unittest discover -s /Users/gabrielongtemasek/Desktop/personal/gitfetch/tests
/tmp/gitfetch-rc-wheel-env/bin/python /tmp/gitfetch-rc-inspect.py
/tmp/gitfetch-rc-sdist-env/bin/python /tmp/gitfetch-rc-inspect.py
uv pip check --python /tmp/gitfetch-rc-wheel-env/bin/python
uv pip check --python /tmp/gitfetch-rc-sdist-env/bin/python
```

Evidence logs: `/tmp/gitfetch-rc-{310,312,pillow100,pillow104}.log`,
`/tmp/gitfetch-rc-installed-{wheel,sdist}.log`, `/tmp/gitfetch-rc-build.log`,
`/tmp/gitfetch-rc-twine.log`, and `/tmp/gitfetch-rc-{wheel,sdist}-inspect.log`.
These are temporary local evidence, not published artifacts.
Copies of logs, advisory JSON, pinned-formula input and the resource inspection
script are retained under `/tmp/gitfetch-rc-evidence/`. The report's 21 shell
blocks passed Bash and Zsh syntax checks, and its embedded Python snippets
compiled; none of the future release checklist commands was executed.

## Version synchronization inventory

| Location | Current state | Required future state |
| --- | --- | --- |
| `pyproject.toml`, project.version | `2.0.0` | `3.0.0` |
| `gitfetch/__init__.py`, `__version__` | `2.0.0` | `3.0.0` |
| `gitfetch/github_api.py`, USER_AGENT | `gitfetch/2.0.0` | `gitfetch/3.0.0` |
| `gitfetch/providers.py`, session User-Agent | `gitfetch/2.0.0` | `gitfetch/3.0.0` |
| `gitfetch/images.py`, avatar User-Agent | `gitfetch/2.0.0` | `gitfetch/3.0.0` |
| CLI `--version` | Derives from runtime constant; prints `gitfetch 2.0.0` | Must derive and print `gitfetch 3.0.0`; no second CLI literal |
| README | Explicit v3-development / old-artifact caveat; historical screenshot labelled | State 3.0.0 release availability only when true; use the released tag/artifact for stable installation |
| `docs/MIGRATION-V3.md` | Explains version is intentionally still 2.0.0 | Update its current-release paragraph; retain genuine 2.x migration/security/nullable-value history |
| Formula | Tag archive `refs/tags/2.0.tar.gz`, old checksum and GitHub-only description | Reviewed 3.0.0 source URL, computed checksum, six-provider description, reviewed resources/licenses and installation test |
| Installer scripts | No embedded version; local checkout or unpinned Git fallback | Verify installed 3.0.0; document cloning `v3.0.0`, not assuming remote HEAD is a release |
| Wheel/sdist metadata and filenames | `gitfetch-2.0.0...`, package `Version: 2.0.0` | Regenerate as `gitfetch-3.0.0...`; never rename an old artifact |
| Historical engineering reports | Tranche-time version/count evidence | Retain history; add current status in this report rather than bulk replacement |

Do not replace dependency strings such as Requests `<3.0.0` merely because they
contain the target release number. Do not edit generated `PKG-INFO`, `METADATA`
or `.egg-info` manually. Installers contain no version literal to synchronize.
An installable public prerelease would need its own approved PEP 440 version;
this report prepares the **stable 3.0.0 target**, not a fake 3.0.0rc package.

## Dependency-security findings — new release gate

`pip-audit 2.10.1` was run without `--fix`. It queried public dependency advisory
metadata, not providers or private profiles. Raw findings contain aliases and
duplicate entries; they are **not counts of proven Gitfetch exploits**:

| Input | Scanner result |
| --- | --- |
| Resolved wheel environment | 73 advisory records in Pillow 11.3.0, 56 distinct scanner IDs; aliases overlap |
| Formula's seven exact resource pins | 89 records across certifi, idna, Pillow, Requests and urllib3 |
| Lower-bound sdist environment | 67 records in Pillow 10.0.0, 51 distinct scanner IDs; aliases overlap |

Gitfetch itself is not found in the scanner's PyPI database and is explicitly
not audited by that database. `uv pip check` only checks dependency consistency.

Concrete upstream evidence relevant to deciding what can ship:

- **PNG EXIF:** Pillow 11.0–12.3 has quadratic EXIF-marker processing, fixed in
  13.0.0. Gitfetch allows PNG and calls `ImageOps.exif_transpose` before metadata
  is cleared. Its byte/pixel caps do not establish a CPU-time bound for this
  path. No exploit was run; source/advisory preconditions require remediation
  or a demonstrated bounded mitigation before release.
  [Pillow advisory](https://github.com/python-pillow/Pillow/security/advisories/GHSA-g4qv-2jxx-769h).
- **Old WebP lower bound:** the installed Pillow 10.0.0 wheel reports libwebp
  1.3.1. Pillow 10.0.1 updated wheels to libwebp 1.3.2 for CVE-2023-4863. Gitfetch
  accepts WebP; allowing 10.0.0 is not a safe release baseline simply because
  it passes rendering tests.
  [Pillow 10.0.1 security notes](https://pillow.readthedocs.io/en/stable/releasenotes/10.0.1.html).
- **Other Pillow records need reachability triage:** `images.py` explicitly
  limits formats to PNG/JPEG/GIF/WEBP/BMP. PSD, JPEG2000 and FPX findings are
  therefore not automatically reachable through the avatar loader. The BMP RLE
  advisory also needs analysis against Gitfetch's stricter edge/pixel caps;
  its upstream oversized-width example is not evidence that Gitfetch accepts
  that example. Do not count all scanner records as vulnerabilities here.
  [BMP advisory](https://github.com/python-pillow/Pillow/security/advisories/GHSA-24rc-8hj2-v98c).
- **Homebrew network pins:** certifi 2025.8.3 retains a root implicated by the
  upstream emSign advisory; urllib3 2.5.0 has decompression-chain/resource
  advisories. The formula intentionally installs these exact old versions.
  Refresh and audit the complete resource set, not just its main source URL.
  [Certifi advisory](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2),
  [urllib3 advisory](https://github.com/urllib3/urllib3/security/advisories/GHSA-gm62-xv2j-4w53).
- The Requests finding in the formula concerns `extract_zipped_paths()` usage;
  routine HTTP calls alone do not establish exposure. idna also needs an
  input-bound/reachability assessment. Preserve this distinction in the review.

**Compatibility decision:** current constraints `Pillow>=10.0.0,<12.0.0` exclude
the cited current fixes. Pillow 13.0.0 requires Python >=3.11, while Gitfetch
declares >=3.10. A blind upgrade would break that contract.
[Pillow's Python support matrix](https://pillow.readthedocs.io/en/stable/installation/python-support.html).
PyPI metadata independently confirmed `13.0.0: >=3.11`, `11.3.0: >=3.9`.

Required next action: approve a tested security/dependency strategy that either
preserves 3.10 with defensible patches/mitigations or explicitly changes the
Python support promise. Then update both dependency declarations and formula
resources, add appropriate regressions, and rerun the approved matrix. This
report chooses neither policy and modifies no dependencies. Raising only to
12.1.1 would not resolve the later cited PNG issue. Audit exceptions must be
specific, justified and tested; blanket ignored IDs are not acceptance.

Reproduction (the generated formula requirements file contains exactly the
seven pins from `Formula/gitfetch.rb`):

```sh
uvx --from pip-audit==2.10.1 pip-audit --path /tmp/gitfetch-rc-wheel-env/lib/python3.12/site-packages --format json --output /tmp/gitfetch-rc-audit.json
uvx --from pip-audit==2.10.1 pip-audit --path /tmp/gitfetch-rc-sdist-env/lib/python3.10/site-packages --format json --output /tmp/gitfetch-rc-pillow10-audit.json
uvx --from pip-audit==2.10.1 pip-audit -r /tmp/gitfetch-rc-formula-requirements.txt --no-deps --disable-pip --format json --output /tmp/gitfetch-rc-formula-audit.json
```

## Licensing, resources and installation paths

Packaging checks PASS independently of the dependency-security gate:

- Root MIT license is present and matches the historical established grant,
  Copyright (c) 2026 gongahkia. No new license was selected.
- Metadata uses `MIT AND LicenseRef-DejaVu`, explicit `license-files` and
  setuptools >=77.0.3. Twine accepts both distributions.
- Both distributions include the licensed DejaVu Sans face, its complete
  Bitstream/Arev notice and the devicon MIT notice. All three notices are also
  included under wheel distribution-level licenses. No runtime font download.
  [Upstream font terms](https://dejavu-fonts.github.io/License.html).
- Font SHA-256: `3fdf69cabf06049ea70a00b5919340e2ce1e6d02b0cc3c4b44fb6801bd1e0d22`.
  Nineteen language-icon PNGs are present. Both installed environments locate
  fonts through package-relative resources, independent of system fonts.
- All 29 runtime modules match checkout, wheel, sdist and installed bytes.
- The console entrypoint is `gitfetch.main:main`; `python -m gitfetch.main`
  works too. No machine-specific resource path is installed.
- The Python/shell installers install their local checkout in a venv without
  editing shell startup files. Their Linux/macOS-only platform guard is
  intentional; Windows installation uses Python packaging, not those scripts.
- The fallback for an installer copied outside its checkout is an unpinned Git
  URL. It is not a reproducible 3.0.0 installation path. Prefer the exact wheel,
  sdist or a checkout of `v3.0.0`.
- Before distributing through Homebrew, review its `license "MIT"` declaration
  against the bundled font terms. Do not blindly paste a Python `LicenseRef`
  into Homebrew; use its supported license representation and retain notices.
  [Formula license guidance](https://docs.brew.sh/Formula-Cookbook#fill-in-the-license).

Inspection builds remain `/tmp/gitfetch-rc-dist/gitfetch-2.0.0...`. They are not
the 3.0.0 release artifacts and their checksums must not be used for that release.

## Outstanding findings, classified

### Release blocking

| ID | Scope | Closure evidence required |
| --- | --- | --- |
| B1 | Dependency security/support policy | Resolve accepted-path Pillow risks and the unsafe lower bound; approve Python support; triage remaining advisory records; retest approved constraints |
| B2 | Public 3.0.0 identity | Synchronize the five version literals, CLI/metadata/README/migration status; no active 2.0.0 identity in release bits |
| B3 | Final artifact provenance | Build from the reviewed frozen commit; test those exact wheel/sdist bytes outside checkout; verify resources, licenses, audit and SHA-256 manifest |
| B4 | Homebrew channel | Refresh audited resources, correct description/source/license representation/checksum; pass isolated install/test and public-asset verification before advertising this channel |

B1–B3 block publication of the current candidate as 3.0.0. B4 blocks declaring
Homebrew ready; the maintainer may deliberately stage that channel later, with
an explicit installation notice. No new source-level exploit reproduction was
attempted in this preparation task.

### Important but deferrable, with explicit limitations/sign-off

- Fresh Ghostty image lifecycle: resize, scroll, repeated frames, interruption,
  pane transitions and prompt restoration. Static preset appearance is accepted;
  that is not the complete lifecycle matrix.
- Effective Zellij session behavior; unverified sessions conservatively fall
  back. Do not advertise universal native Zellij support without acceptance.
- Linux/Windows installed execution and SSH on the intended release bytes.
  Current local execution is macOS only; workflow definitions are not evidence
  that a run on the final commit passed. These checks become required before
  making specific platform/path verification claims.
- Six opt-in live-provider tests and independent Forgejo/self-hosted instances.
  Fixture coverage is strong; authenticated/live boundaries remain unverified.
- CJK/emoji glyph coverage and alternative SVG viewers; no font crash was found.
- Review historical cross-provider credential use where appropriate; the T07
  token-isolation repair remains in place, but historical exposure is unknown.

### Optional improvements

- Replace the explicitly historical README screenshot with accepted modern
  captures; it is currently labelled accurately.
- Broader automated OS/Pillow/terminal CI, dependency locks/SBOM/attestations,
  and removing duplicated user-agent literals in a later maintenance change.
- Pin or retire the standalone installer's unpinned remote fallback. This is
  not needed to use verified release artifacts or a versioned checkout.

## Release checklist — future maintainer actions only

**STOP before any publication while B1 remains unresolved.** The following
sequence prepares 3.0.0 after that decision; it does not authorize executing it
in this assessment. Preserve concurrent work, review explicit diffs and never
stage unrelated files. Do not reset, force-push, move an existing tag, or replace
assets under an already distributed version.

### 1. Close security and accept the remaining environment matrix

- Resolve B1 and review the formula's complete resource set. Re-run the full
  suite, security regressions, advisory triage and installation tests with the
  approved versions on every retained Python version.
- Complete the manual commands below or record precisely which environment
  remains unverified and why that risk is accepted. Record the final commit,
  platform, terminal/mux versions and results; no credentials in evidence.
- Review this report, migration notes and release notes. The intended public
  version is 3.0.0; any Python-minimum change requires explicit approval.

### 2. Synchronize versions in a reviewed preparation change

Start from a clean reviewed branch after intended security changes are retained.
This guard script changes only the five identified literal values, checking all
inputs before writing. It is deliberately included as documentation, not run.

```sh
git status --short
git switch -c release/v3.0.0
python3 - <<'PY'
from pathlib import Path
changes = {
    'pyproject.toml': ('version = "2.0.0"', 'version = "3.0.0"'),
    'gitfetch/__init__.py': ('__version__ = "2.0.0"', '__version__ = "3.0.0"'),
    'gitfetch/github_api.py': ('gitfetch/2.0.0', 'gitfetch/3.0.0'),
    'gitfetch/providers.py': ('gitfetch/2.0.0', 'gitfetch/3.0.0'),
    'gitfetch/images.py': ('gitfetch/2.0.0', 'gitfetch/3.0.0'),
}
prepared = {}
for filename, (old, new) in changes.items():
    text = Path(filename).read_text()
    if text.count(old) != 1:
        raise SystemExit(f'Review changed version source: {filename}')
    prepared[filename] = text.replace(old, new, 1)
for filename, text in prepared.items():
    Path(filename).write_text(text)
PY
```

Update README and the migration guide's current-release paragraph manually.
Do not claim the future tag/download exists before publication. Stable source
installation should use `git clone --branch v3.0.0 --depth 1` after that tag
exists, followed by a venv and `python -m pip install .`.

Create and review `docs/RELEASE-NOTES-3.0.0.md`, covering nullable/fractional JSON
metrics, provider-specific language units, corrected module selection, new card
appearance/legacy style, fitting policy and the token-isolation correction.
Record any approved dependency/Python-support changes. Classic appearance does
not restore old misleading numeric semantics.

```sh
rg -n '2\.0\.0|gitfetch/3\.0\.0|__version__|^version =' pyproject.toml gitfetch
python3 -m gitfetch.main --version
python3 -m unittest discover -s tests
ruff check .
mypy gitfetch
git diff --check
git diff -- pyproject.toml gitfetch/__init__.py gitfetch/github_api.py gitfetch/providers.py gitfetch/images.py README.md docs/MIGRATION-V3.md docs/RELEASE-NOTES-3.0.0.md
```

Stage only the reviewed files; commit/merge through the maintainer's normal
review process. A possible explicit commit command, **only after approval**:

```sh
git add pyproject.toml gitfetch/__init__.py gitfetch/github_api.py gitfetch/providers.py gitfetch/images.py README.md docs/MIGRATION-V3.md docs/RELEASE-NOTES-3.0.0.md
git commit -m "Prepare Gitfetch 3.0.0"
```

### 3. Freeze the approved commit and build artifacts

After review/merge, capture the exact approved commit; any later source change
requires a new build and relevant acceptance. Use an isolated source worktree:

```sh
test -z "$(git status --porcelain)"
gitfetch_release_root="$(git rev-parse --show-toplevel)"
gitfetch_release_commit="$(git rev-parse HEAD)"
gitfetch_release_stage="$(mktemp -d /tmp/gitfetch-v3-release.XXXXXX)"
git worktree add --detach "$gitfetch_release_stage/source" "$gitfetch_release_commit"
uv build "$gitfetch_release_stage/source" --out-dir "$gitfetch_release_stage/artifacts"
uvx --from twine twine check "$gitfetch_release_stage/artifacts/gitfetch-3.0.0-py3-none-any.whl" "$gitfetch_release_stage/artifacts/gitfetch-3.0.0.tar.gz"
printf '%s\n' "$gitfetch_release_commit" > "$gitfetch_release_stage/artifacts/RELEASE-COMMIT"
(
  cd "$gitfetch_release_stage/artifacts"
  shasum -a 256 gitfetch-3.0.0-py3-none-any.whl gitfetch-3.0.0.tar.gz RELEASE-COMMIT > SHA256SUMS
  shasum -a 256 -c SHA256SUMS
)
```

Inspect wheel METADATA / sdist PKG-INFO: name/version, approved Requires-Python,
approved dependencies, entrypoint and all licenses/resources. Never rename the
current 2.0.0 artifacts to 3.0.0. Do not infer archive checksums from Git commit
IDs or from the bundled font checksum.

### 4. Install and test those exact distribution files

Use Python versions consistent with the approved support policy. The commands
below retain the current 3.10/3.12 promise; change it only through the explicit
policy decision, not by silently dropping a failing matrix row.

```sh
python3.12 -m venv "$gitfetch_release_stage/wheel-env"
"$gitfetch_release_stage/wheel-env/bin/python" -m pip install "$gitfetch_release_stage/artifacts/gitfetch-3.0.0-py3-none-any.whl"
python3.10 -m venv "$gitfetch_release_stage/sdist-env"
"$gitfetch_release_stage/sdist-env/bin/python" -m pip install "$gitfetch_release_stage/artifacts/gitfetch-3.0.0.tar.gz"
(
  cd /tmp
  "$gitfetch_release_stage/wheel-env/bin/gitfetch" --version
  "$gitfetch_release_stage/wheel-env/bin/python" -m gitfetch.main --help
  "$gitfetch_release_stage/wheel-env/bin/python" -m pip check
  "$gitfetch_release_stage/wheel-env/bin/python" -m unittest discover -s "$gitfetch_release_stage/source/tests"
  "$gitfetch_release_stage/sdist-env/bin/gitfetch" --version
  "$gitfetch_release_stage/sdist-env/bin/python" -m pip check
  "$gitfetch_release_stage/sdist-env/bin/python" -m unittest discover -s "$gitfetch_release_stage/source/tests"
)
```

For each interpreter, assert `importlib.metadata.version('gitfetch')` and
`gitfetch.__version__` both equal `3.0.0`; check `gitfetch.__file__` points into
that environment, not the source worktree. Re-run the installed resource/font,
offline/export and security checks. Preserve resolved dependency inventories and
the advisory review. The test count may increase after security regressions;
record actual counts rather than forcing the old 621 total.

### 5. Select one canonical Homebrew source artifact and preflight it

**Recommended source:** the built, tested Python sdist uploaded as a GitHub
release asset:

```text
https://github.com/gongahkia/gitfetch/releases/download/v3.0.0/gitfetch-3.0.0.tar.gz
```

The companion wheel is for Python installation. The sdist is Homebrew's source.
GitHub's automatically generated `archive/refs/tags/v3.0.0.tar.gz` is a different
file, with a different checksum. If the maintainer deliberately chooses that
archive instead, download, inspect and installation-test that exact file and
hash it separately. Do not transfer a checksum between these artifact types.
[Homebrew checksum requirements](https://docs.brew.sh/Checksum-Requirements).

No correct 3.0.0 checksum exists in this report: those final bytes do not yet
exist. After building, compute it with:

```sh
shasum -a 256 "$gitfetch_release_stage/artifacts/gitfetch-3.0.0.tar.gz"
```

Preflight Homebrew in a disposable macOS/Linux Homebrew environment, not the
user's existing installation. Use a local tap and a copy of the **reviewed**
formula with audited resource pins and the appropriate license representation.
The following helper updates only main source URL/checksum/description; it does
not resolve the resource-security or license review by itself:

```sh
cat > /tmp/gitfetch-set-formula.py <<'PY'
import hashlib
import json
import re
import sys
from pathlib import Path
formula, archive, url = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
text = formula.read_text()
for pattern, value in [
    (r'^  url "[^"]+"$', '  url '+json.dumps(url)),
    (r'^  sha256 "[^"]+"$', '  sha256 '+json.dumps(digest)),
    (r'^  desc "[^"]+"$', '  desc "Neofetch-style CLI profiles for six Git hosting providers"'),
]:
    text, count = re.subn(pattern, lambda match: value, text, flags=re.M)
    if count != 1:
        raise SystemExit('Review changed formula structure')
formula.write_text(text)
print('Computed source SHA-256:', digest)
PY
```

In the disposable Homebrew machine, serve the artifact directory in a separate
terminal; no release publication is required for this preflight:

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory "$gitfetch_release_stage/artifacts"
```

Then, in the test shell (same disposable machine):

```sh
brew tap-new local/gitfetch-rc
gitfetch_test_tap="$(brew --repository local/gitfetch-rc)"
cp "$gitfetch_release_root/Formula/gitfetch.rb" "$gitfetch_test_tap/Formula/gitfetch.rb"
python3 /tmp/gitfetch-set-formula.py "$gitfetch_test_tap/Formula/gitfetch.rb" "$gitfetch_release_stage/artifacts/gitfetch-3.0.0.tar.gz" http://127.0.0.1:8765/gitfetch-3.0.0.tar.gz
brew install --build-from-source local/gitfetch-rc/gitfetch
brew test local/gitfetch-rc/gitfetch
brew list local/gitfetch-rc/gitfetch
"$(brew --prefix local/gitfetch-rc/gitfetch)/bin/gitfetch" --version
```

This verifies installation using the candidate bytes. It does not establish that
the future public URL works. The local HTTP source is temporary and will not
satisfy a final HTTPS-source audit. Do not publish that local URL. Stop the test
HTTP server afterward. No such install/tap/server was created in this assessment.

Strengthen the reviewed formula test to assert `gitfetch 3.0.0`, exercise
`--graphics-info` without collection, and verify the bundled font/license using
the formula's `libexec/bin/python` plus `importlib.resources.files('gitfetch')`.
Its current test checks help text only. If PyPI publication is part of the
approved release, `brew update-python-resources --print-only` can assist after
that package version exists; do not assume an unpublished PyPI package resolves.

### 6. Tag only the approved, tested commit; prepare a draft GitHub release

These commands require separate maintainer authorization. Ensure the tag does
not already exist and that the approved commit is available through the normal
reviewed remote workflow. Do not let a release command select current main
implicitly:

```sh
git show --stat "$gitfetch_release_commit"
git tag -a v3.0.0 "$gitfetch_release_commit" -m "Gitfetch 3.0.0"
git rev-parse 'v3.0.0^{commit}'
git push origin refs/tags/v3.0.0
gh release create v3.0.0 "$gitfetch_release_stage/artifacts/gitfetch-3.0.0-py3-none-any.whl" "$gitfetch_release_stage/artifacts/gitfetch-3.0.0.tar.gz" "$gitfetch_release_stage/artifacts/SHA256SUMS" "$gitfetch_release_stage/artifacts/RELEASE-COMMIT" --repo gongahkia/gitfetch --verify-tag --draft --title "Gitfetch 3.0.0" --notes-file "$gitfetch_release_stage/source/docs/RELEASE-NOTES-3.0.0.md"
```

Use a signed tag instead if an existing approved signing setup is available.
Do not create a new key silently. `--verify-tag` prevents `gh` from inventing a
tag at default-branch HEAD. Draft release assets are not normal anonymous public
downloads; do not claim the production Homebrew URL passed while still draft.
[GitHub CLI release creation](https://cli.github.com/manual/gh_release_create).

Round-trip the draft assets with authorized GitHub CLI access, then compare to
the locally retained manifest and bytes:

```sh
gh release download v3.0.0 --repo gongahkia/gitfetch --dir "$gitfetch_release_stage/retrieved" --pattern 'gitfetch-3.0.0*' --pattern SHA256SUMS --pattern RELEASE-COMMIT
cmp "$gitfetch_release_stage/artifacts/SHA256SUMS" "$gitfetch_release_stage/retrieved/SHA256SUMS"
(
  cd "$gitfetch_release_stage/retrieved"
  shasum -a 256 -c "$gitfetch_release_stage/artifacts/SHA256SUMS"
)
```

If a draft is already present, inspect it rather than blindly recreating it.
Do not use `gh release upload --clobber` to hide a mismatch: it deletes the
previous asset before replacement succeeds.
[GitHub CLI upload behavior](https://cli.github.com/manual/gh_release_upload).

### 7. Publish only after the final approval, then update the Homebrew channel

Publication is a separate explicit decision, **not performed here**:

```sh
gh release edit v3.0.0 --repo gongahkia/gitfetch --draft=false --latest
curl --fail --location --proto '=https' --proto-redir '=https' --tlsv1.2 https://github.com/gongahkia/gitfetch/releases/download/v3.0.0/gitfetch-3.0.0.tar.gz --output "$gitfetch_release_stage/public-sdist.tar.gz"
cmp "$gitfetch_release_stage/artifacts/gitfetch-3.0.0.tar.gz" "$gitfetch_release_stage/public-sdist.tar.gz"
shasum -a 256 "$gitfetch_release_stage/public-sdist.tar.gz"
```

Only after the downloaded public bytes match, update the reviewed formula on
the maintainer's formula branch. Retain the separately approved resource/license
changes. Compute its checksum with the helper, rather than typing one:

```sh
python3 /tmp/gitfetch-set-formula.py "$gitfetch_release_root/Formula/gitfetch.rb" "$gitfetch_release_stage/public-sdist.tar.gz" https://github.com/gongahkia/gitfetch/releases/download/v3.0.0/gitfetch-3.0.0.tar.gz
ruby -c "$gitfetch_release_root/Formula/gitfetch.rb"
git diff --check
git diff -- Formula/gitfetch.rb
```

Copy that final formula into the local test tap, then in the disposable machine:

```sh
brew fetch --force local/gitfetch-rc/gitfetch
brew reinstall --build-from-source local/gitfetch-rc/gitfetch
brew test local/gitfetch-rc/gitfetch
brew audit --strict --online local/gitfetch-rc/gitfetch
brew style local/gitfetch-rc/gitfetch
```

Commit the reviewed formula separately and submit it to the intended tap through
its maintainer process. No destination tap was verified here; do not invent a
`brew tap gongahkia/...` installation command. Do not retag the source release
to add its own checksum. If an auto-generated tag archive is chosen, putting
its checksum inside that same tagged archive would be circular.

The formula update is a separate channel change: the frozen source tag is not
retagged to incorporate it. Do not tell users to install a stale recipe from the
release tag; advertise the reviewed updated checkout/tap recipe only after its
channel checks pass.

PyPI ownership/publication is not verified by this task. If PyPI is an intended
channel, approve that registry step separately and publish the same retained
wheel/sdist bytes using the project's authorized publishing process; do not
claim `pip install gitfetch==3.0.0` works until it actually does.

## Manual acceptance commands and remaining evidence

All following live/physical commands are **instructions only**. Static terminal
and card appearance already passed maintainer review and does not need redesign.

### Ghostty and Zellij lifecycle

Run in the actual terminal, without piping native previews. Tests use isolated
synthetic offline avatar assets:

```sh
gitfetch --graphics-info
zellij --version
PYTHONPATH=tests python3 tests/preview_native.py --case transparent --fit visible --confirm-kitty
PYTHONPATH=tests python3 tests/preview_native.py --case portrait --fit visible --layout stack --confirm-kitty
PYTHONPATH=tests python3 tests/preview_native.py --case transparent --fit visible --offline missing --confirm-kitty
```

Repeat, scroll and resize; interrupt a frame; switch/split panes and repeat.
Check prompt return, text/image separation, owned-image cleanup, absence of
cross-pane deletion and stable alpha. The explicit confirmation flag asserts
the effective path; it is not a probe or evidence by itself. Current installed
Zellij is 0.45.1. No explicit Kitty setting was found in the user's config in the
previous review; a commented dump default does not prove the attached session.
Inspect that actual session's support before confirmation. Leave tmux settings
unchanged; its conservative fallback remains expected.

For an already cached, authorized profile, check watch and interruption:

```sh
gitfetch --offline --presentation modern --watch 2
gitfetch --offline --avatar-renderer text --avatar-style halfblock
```

Watch is intentionally text-only; a missing profile cache is not a graphics
regression. No active terminal probing or automatic mux reconfiguration is needed.

### Linux, Windows and SSH

On a disposable Linux environment, install the exact wheel into a venv, change
directory outside the checkout, run both entrypoints, config validation,
synthetic exports and the full suite using the checkout's absolute tests path.
Repeat for each retained Python version. Existing Ubuntu CI definitions are
not a recorded PASS for the final release commit; inspect that actual run.

On Windows, use Python packaging, not the Unix installer. In PowerShell, with
`$wheel` set to the downloaded verified wheel and `$repo` to the test checkout:

```powershell
$rc = Join-Path $env:TEMP ("gitfetch-rc-" + [guid]::NewGuid().ToString("N"))
py -3.12 -m venv "$rc\env"
& "$rc\env\Scripts\python.exe" -m pip install $wheel
Push-Location $env:TEMP
& "$rc\env\Scripts\gitfetch.exe" --version
& "$rc\env\Scripts\python.exe" -m gitfetch.main --help
& "$rc\env\Scripts\gitfetch.exe" --graphics-info
& "$rc\env\Scripts\python.exe" "$repo\tests\preview_exports.py" --output "$rc\previews"
Pop-Location
```

Expect text fallback for terminal graphics; check Unicode output and exports
without requiring Unix shells or changing execution policy. Full Windows-suite
portability is NOT VERIFIED; identify platform-specific test assumptions if
running it rather than relabeling unsupported installer tests as product bugs.

For SSH, after selecting an authorized host:

```sh
ssh "$GITFETCH_ACCEPTANCE_HOST" 'gitfetch --version; gitfetch --graphics-info'
```

Test a cached profile there and verify conservative fallback; inherited terminal
variables do not establish a working remote graphics path. Do not enable native
graphics merely to make this check pass.

### Live-provider integration

Six skipped tests cover: public contexts for five providers in one test, a
separate Forgejo-compatible context, GitLab viewer, Gitea viewer, Bitbucket
authenticated workspace and GitHub authenticated/GraphQL context. The Forgejo
default is Codeberg, so an independent Forgejo instance needs its own approved
base URL. Fixtures do not prove every self-hosted instance's behavior.

Before running, select authorized small test accounts via
`GITFETCH_LIVE_<PROVIDER>_USER`, plus `_BASE_URL` where applicable. Review request
pagination before targeting a large namespace. Provision scoped credentials
through the existing secret mechanism, not literal command arguments or this
document. Current provider smoke tests disable persistent response caching but
do make real read-only requests.

```sh
GITFETCH_LIVE_PROVIDERS=1 PYTHONPATH=tests python3 -m unittest test_live_providers.LiveProviderSmokeTests.test_public_profile_contexts test_live_providers.LiveProviderSmokeTests.test_forgejo_compatible_context -v
GITFETCH_LIVE_PROVIDERS=1 PYTHONPATH=tests python3 -m unittest test_live_providers.LiveProviderSmokeTests.test_gitlab_authenticated_viewer_context test_live_providers.LiveProviderSmokeTests.test_gitea_authenticated_viewer_context test_live_providers.LiveProviderSmokeTests.test_bitbucket_authenticated_workspace_context -v
PYTHONPATH=tests python3 -m unittest test_integration -v
```

Required credentials: `GITFETCH_LIVE_GITLAB_USER/TOKEN`,
`GITFETCH_LIVE_GITEA_USER/TOKEN`, Bitbucket `USER/TOKEN/AUTH_USERNAME` (and
appropriate `AUTH_MODE`), and `GITFETCH_INTEGRATION_TOKEN` for GitHub. All use
the prefixes shown in `tests/test_live_providers.py`; never log values. A skipped
credential-dependent case remains NOT VERIFIED, even if the command exits zero.
No live-provider tests were run in this preparation assessment.

## Risks, rollback and final sign-off

- Keep a configuration backup before migration. Nullable/fractional metric
  semantics are intentional major-version changes. `--presentation classic`
  and `export_style=legacy` preserve artwork choices, not incorrect old data.
- Retain local artifact hashes, approved commit, dependency inventory, security
  dispositions and acceptance results. SHA-256 checks integrity, not by itself
  publisher authenticity; use trusted release controls/signing where available.
- Before publication, stop at the draft on a mismatch or failed gate. After
  publication, do not replace an asset, retag 3.0.0 or edit a checksum to conceal
  changed bytes. Issue a new reviewed version for fixes; withdraw/yank a bad
  registry version through the maintainer's channel-specific process if needed.
- Roll back installations into isolated environments using a known reviewed
  safe artifact. Do not assume old 2.0 code/dependencies are a safe rollback:
  the token-isolation repair and dependency advisories must be considered.
  Preserve config and caches; do not reset the working repository.
- Homebrew can change dependencies and existing installations. Its preflight
  belongs in a disposable environment; no sudo/global install or real shell
  startup modification was used for this assessment.
- Fresh previews generated from the installed current wheel are in
  `/tmp/gitfetch-rc-previews/`, including a labelled contact sheet. Their
  structure was validated; visual acceptance is the maintainer's previously
  supplied acceptance of the unchanged T07.1 design, not a new physical run.

Final authorization criteria: B1 closed with approved support/security policy;
B2/B3 verified on final 3.0.0 bytes; manual matrix completed or specifically
accepted as unverified; and B4 closed before promoting Homebrew. Version strings,
the primary Homebrew checksum and all release operations remain untouched here.
