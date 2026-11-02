# Gitfetch 3.0.0rc1 — candidate verification

## Verdict and corrected scope

**CONDITIONALLY READY for RC review. Final publication is not authorized.**

The maintainer clarified during this tranche that Gitfetch is not intended to
be a Homebrew package. Homebrew assembly/testing was stopped and is **excluded
from release acceptance**, superseding that part of the original task. Existing
formula/security history is preserved; no Homebrew publication is proposed.
The deliverables are the Python wheel, sdist, controlled source snapshot and
their verification manifest. Normal Homebrew installations were not modified.

## Provenance and source freeze

- Initial branch `main`, HEAD `ad06587c17a2a5ee3ca950e4d96b2b106c0663d5`.
- Incoming work: 17 uncommitted files from T07.3, including the formula, reports
  and security evidence. Their initial hashes/status were recorded before edits.
- A concurrent commit advanced HEAD to
  `45df88c942e515657098d93912cddcc7c956187c`; it included previous security work
  and a subset of candidate edits. No commit was created by this review.
- The accepted snapshot records that latter HEAD plus the actual dirty tree,
  **193 individually hashed files**, modes, Python/dependency constraints,
  build-tool versions, commands, epoch and artifact hashes.
- Tracked files and explicitly approved new files were copied from disk, not
  from `git archive`. Credentials, local configuration, environments, caches,
  unrelated untracked files and generated previews/logs were not selected.
- The generated verification report/evidence are delivered beside the artifacts,
  outside the hashed source set, avoiding circular report/artifact hashes.
- Source and artifact verification rejects later drift. Earlier assembly
  attempts are invalidated and are not release candidates.

Bundle: `dist/rc-3.0.0rc1/` (ignored by Git). Authoritative provenance:
`source-manifest.json`, `SHA256SUMS`, `release-manifest.json` and `evidence/`.

## Artifacts

| Filename | SHA-256 |
| --- | --- |
| `gitfetch-3.0.0rc1-py3-none-any.whl` | `0fc122a85f938ec3b9310365f6c334f16e6049b143ecc67a999e3f76c006264e` |
| `gitfetch-3.0.0rc1-source.tar.gz` | `845069aeed91e4e77054d249a8855760f6fa39ba18bb996f42e1ccc993550905` |
| `gitfetch-3.0.0rc1.tar.gz` | `79e31ef8be1ef1b3d6cd5840ea8a8c5cedf0669f40bb38cd71573a7667c28d56` |

These are **local candidate bytes**, not a future GitHub-generated tag archive.
The manifest hashes must never be substituted for a different published archive.

Two clean builds matched. An independent rebuild from an extracted snapshot,
without its original Git repository, also matched wheel/sdist hashes. Tools:
Python 3.12.14, build 1.4.0, setuptools 84.2.1, wheel 0.48.0, packaging 26.3.
`SOURCE_DATE_EPOCH` fixes wheel timestamps; source/sdist tar and gzip headers are
canonicalized without changing member content. Reproducibility is established
for the recorded environment, not promised across arbitrary tool/zlib versions.

## Version and metadata changes

`pyproject.toml` and `gitfetch.__version__` now identify **3.0.0rc1**. CLI and
installed metadata agree. A shared `USER_AGENT` derives from the runtime version
and is used by GitHub, the other provider adapters and avatar requests.
Three new regressions verify metadata/CLI agreement, all six provider headers,
and avatar headers without authentication or network access.

Python >=3.11 and Pillow >=13,<14 remain required. Project description names all
six providers; entrypoints and package resources are preserved. Root MIT and
bundled third-party licenses remain included. The composite metadata expression
`MIT AND LicenseRef-DejaVu` accurately preserves the bundled font notice.
Historical versions and the existing production formula's archive/hash remain
historical references, rather than being changed to nonexistent release URLs.

README identifies the unpublished candidate and distinguishes it from remote
2.0 downloads. Migration documents defaults, presets, original/visible avatar
fitting, Python 3.10 removal, Pillow 13, nullable metrics and export compatibility.
Six historical engineering documents had their machine-specific checkout prefix
replaced with `<checkout>`; historical results/counts were retained.

## Confirmed security repair

**P1, fixed:** the old package ranges could retain the pre-T07.3 vulnerable
network packages during an upgrade. `uv pip compile` with the original pins
successfully resolved that affected graph. Fresh installation audits alone did
not protect existing environments.

The candidate now requires Requests >=2.34.2,<3, urllib3 >=2.8,<3,
certifi >=2026.10.23 and idna >=3.20,<4. Existing transitive dependencies were
given explicit security floors; **no package was added to the resolved graph**.
The same vulnerable constraint set now fails resolution. Package and flat
requirements agree. Earlier candidates were invalidated and rebuilt.

Fresh pip-audit 2.10.1 queries against the PyPI advisory service, using new cache
directories, report **zero known third-party advisories**, separately for the
wheel and sdist installations. Timestamped raw evidence and inventories are in
the bundle. Local Gitfetch 3.0.0rc1 is absent from the advisory database and is
explicitly reported as not database-auditable; no finding was suppressed.

Both resolved graphs contain certifi 2026.10.23, charset-normalizer 3.5.2,
idna 3.20, Pillow 13.0.0, Requests 2.34.2, urllib3 2.8.0 and wcwidth 0.9.4.
These audits do not claim clearance of arbitrary older environments, OS packages
or undisclosed vulnerabilities. No live credentials/provider tests were enabled.

## Verification

Incoming baseline: **623 discovered, 617 passed, 6 skipped**, 20.616 seconds.

| Installed artifact | Python | Discovered | Passed | Skipped | Seconds |
| --- | --- | ---: | ---: | ---: | ---: |
| Wheel | 3.11.16 | 626 | 620 | 6 | 67.581 |
| Wheel | 3.12.14 | 626 | 620 | 6 | 69.548 |
| Wheel | 3.14.7 | 626 | 620 | 6 | 67.975 |
| Independent sdist | 3.11.16 | 626 | 620 | 6 | 67.860 |

Tests ran outside the checkout using frozen fixtures and imports from installed
site-packages. The six skips are existing opt-in live-provider/authenticated
tests, not passes. The initial `/tmp` invocation exposed a literal-path assertion
in an existing installer test because macOS resolves `/tmp` to `/private/tmp`.
Using the canonical fixture path corrected the test invocation without changing
application code, assertions or skipping the test. All complete reruns passed.

Documentation-only rebuilds retained the **identical tested wheel/sdist hashes**;
their complete suite evidence therefore applies to these final bytes.

Additional PASS: Ruff; mypy (29 runtime files); compilation on 3.11/3.12/3.14;
dependency checks; Twine; package/resource/license/module content checks; console
and module versions/help; config initialization/validation/profiles; module
listing; graphics diagnostics; completion generation; Bash/Zsh syntax; XML/PNG
validation and source/artifact drift detection. Fish execution and Python 3.13
were not locally verified.

The complete suites cover six-provider semantics, configured/external profiles,
repo/org/compare, JSON, classic/modern presets, details, plugin opt-in, token
isolation, offline/cache behavior, avatar limits/EXIF/alpha/fitting, all text
backends, Kitty transport/cursor safety, exports, request counts and single
module execution. No rendering feature/provider request was added.

## Performance

Repeated fixture benchmarks separate startup/cache/render work from real network
latency. Initial runs overlapped disposable build activity and had substantial
variability; they are retained as measurements, not strict acceptance thresholds
or evidence of a speedup. The maintainer's individual 1.20s/0.49s/9s observations
are not directly comparable controlled workloads.

| Workload | Median ms | Min–max ms |
| --- | ---: | ---: |
| bare_python_startup | 59.298 | 52.377–176.310 |
| cli_import_with_startup | 436.822 | 371.608–518.801 |
| avatar_decode_prepare_64 | 0.195 | 0.178–1.236 |
| provider_cache_read | 0.110 | 0.093–0.280 |
| whole_cli_cached_avatar | 543.708 | 471.869–735.328 |
| whole_cli_cached_no_avatar | 998.442 | 565.284–1277.333 |
| avatar_binary_cache_read | 0.283 | 0.238–0.859 |
| avatar_cache_read_and_decode | 1.101 | 0.800–4.337 |
| avatar_frame_memo | 0.008 | 0.007–0.034 |

Component benchmark medians: layout 5.175 ms, half-block 1.492 ms, Kitty PNG
encoding 0.391 ms, frame composition including encoding 7.627 ms, export planning
65.608 ms, SVG serialization 9.126 ms and PNG rendering 65.154 ms. Full sample
ranges and a same-dependency baseline run are retained in evidence. Unequal
host contention makes a claimed regression/speedup unjustified; no optimization
was attempted. Cold fixture runs made exactly three mocked GETs; warm/offline
runs made no additional provider requests.


## Gates

| Gate | Result | Evidence / limit |
| --- | --- | --- |
| G1 Version | PASS | Package, CLI, runtime and User-Agents agree |
| G2 Snapshot | PASS | 193 file hashes, dirty-tree provenance, drift guard |
| G3 Packaging | PASS | Two matching builds, independent reproduction, resources/licenses |
| G4 Installed artifacts | PASS | Four complete installed suites |
| G5 Providers/CLI | PASS | Fixture regressions; credentialed live checks skipped |
| G6 Terminal | PASS | Regression suites; maintainer accepted unchanged designs |
| G7 SVG/PNG | PASS | Export tests, XML/PNG checks and actual Chrome render |
| G8 Dependencies | PASS | Secure floors, vulnerable graph rejection, two fresh clean audits |
| G9 Homebrew | NOT VERIFIED / excluded | Maintainer removed it from release scope |
| G10 Documentation | PASS | Current README/migration and release checklist |
| G11 Performance | PARTIAL | Repeated measurements available; noisy host, no strict comparative conclusion |
| G12 Physical/live matrix | PARTIAL | Prior visual acceptance; remaining environments below |

## Manual acceptance

Already reported by the maintainer: direct Ghostty and Zellij native images,
modern fitting, three terminal presets, revised card designs and representative
browser appearance. This is prior evidence, not a fresh lifecycle test here.
Balanced SVG was additionally rendered by installed headless Chrome and visually
inspected during this tranche; no obvious layout/content loss was observed.

Still NOT VERIFIED: Zellij scroll/resize/exit lifecycle; SSH; Windows and Linux
desktop terminals; authenticated live providers; instance-specific Gitea/Forgejo.
These require maintainer disposition before claiming platform-wide acceptance.
macOS Homebrew is **not a release requirement** following the scope correction.

Use the candidate interpreter and extracted snapshot; these synthetic previews
perform no provider requests. Run native commands only in the intended physical
terminal, with no pipe/redirection:

```sh
rc_python=/tmp/gitfetch-074-final-312/bin/python
rc_source=/private/tmp/gitfetch-074/accepted-source/gitfetch-3.0.0rc1
"$rc_python" -m gitfetch.main --graphics-info
"$rc_python" "$rc_source/tests/preview_native.py" --case transparent --fit visible --confirm-kitty
"$rc_python" "$rc_source/tests/preview_native.py" --case portrait --fit visible --layout stack --confirm-kitty
"$rc_python" "$rc_source/tests/preview_avatars.py" --case transparent --style halfblock --color truecolor
```

For Zellij, inspect `zellij --version` and effective session configuration first;
`--confirm-kitty` is a user assertion, not automatic evidence. Check scroll,
resize, repeated frames, image cleanup and prompt position. For SSH/Windows/Linux
run diagnostics first and use cached/synthetic text output. Do not infer native
support from inherited TERM variables. Enable live tests only after explicit
authorization; use the provider-specific environment variables documented in
`tests/test_live_providers.py`, never commit credentials.

## Reproduction and final procedure

Exact build/verification commands and raw results accompany the bundle. Core
commands (from the checkout, no publication):

```sh
python scripts/assemble_rc.py --verify dist/rc-3.0.0rc1/source-manifest.json
cd dist/rc-3.0.0rc1 && shasum -a 256 -c SHA256SUMS
# Independent rebuild after extracting the controlled source archive:
# python scripts/assemble_rc.py --root <extracted-source> \
#   --rebuild <bundle>/source-manifest.json --output <fresh-output>
```

Use the recorded pinned build tools. Test commands are
`<installed-python> -m unittest discover -s <canonical-frozen-source>/tests`,
`ruff check .`, `mypy gitfetch`, `python -m compileall -q gitfetch installer tests scripts`,
`uv pip check --python <installed-python>`, and `twine check <wheel> <sdist>`.
Audit commands and timestamps are retained in the bundle evidence.

No confirmed implementation/security blocker remains in the tested Python
candidate. Remaining conditions are manual compatibility disposition and final
maintainer review. Publication remains NOT READY/unauthorized until approval,
final versioning and verification of the **final** bytes.

Follow [RELEASE-CHECKLIST-V3.md](RELEASE-CHECKLIST-V3.md): source freeze; change
3.0.0rc1 to 3.0.0; rebuild final wheel/sdist; repeat installed tests/audits;
review exact files and obtain explicit approval; only then create the approved
commit/tag, push and create a release. Homebrew publication is excluded.
Never reuse RC hashes for final artifacts. Do not move published tags or replace
published bytes on rollback; retain manifests, back up config and prepare a new
approved version. Do not roll back to vulnerable dependencies.

No commit, tag, push, package upload or release was performed by this review.

## Files changed in this tranche

- `Formula/gitfetch.rb`
- `README.md`
- `docs/MIGRATION-V3.md`
- `docs/RELEASE-CANDIDATE-V3.md`
- `docs/RELEASE-CANDIDATE-VERIFICATION-V3.md`
- `docs/RELEASE-CHECKLIST-V3.md`
- `docs/RELEASE-READINESS-V3.md`
- `docs/export-design.md`
- `docs/export-visual-polish.md`
- `docs/pillow-security-remediation.md`
- `docs/terminal-design-system.md`
- `gitfetch/__init__.py`
- `gitfetch/github_api.py`
- `gitfetch/images.py`
- `gitfetch/providers.py`
- `pyproject.toml`
- `requirements.txt`
- `scripts/assemble_rc.py`
- `tests/test_version.py`

Current HEAD remains `45df88c942e515657098d93912cddcc7c956187c`, branch `main`.
Some changes were incorporated by the concurrent commit; remaining edits are
uncommitted. Initial T07.3 security evidence was retained unchanged.
