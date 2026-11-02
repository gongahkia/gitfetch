# Tranche 07.3 — Homebrew dependency security and resource hardening

Assessment date: 2026-11-02. This is security remediation, not a release.

## Verdict and repository state

**Security remediation: PASS. Overall public release readiness: NOT READY.**

The four vulnerable Homebrew resources are upgraded to verified patched releases.
All 16 original advisory records are accounted for below. Fresh audits of the
complete seven-resource set and installed dependencies report **zero known
third-party vulnerabilities**. No advisory was ignored, suppressed, or dismissed
on the basis of limited application reachability.

The first read observed `main` at
`07f6987e45ce889f2db3a2f0b7151b4dcc7e7b0e`, with the previous tranche's edits and
release-candidate report present. A concurrent maintainer commit advanced HEAD
to `ad06587c17a2a5ee3ca950e4d96b2b106c0663d5` (`preparforhomebrew`) and committed
that work **before this tranche edited any repository file**. The adopted
incoming worktree at that commit was clean. Recent history also includes
`ff9fd87`, `e530498`, `1f4c4c4`, and `da98f1d`. No Git mutation was performed by
this review. Existing and concurrent work was preserved.

The incoming suite ran before modification: **623 discovered, 617 passed,
6 skipped**, 19.585 seconds on Python 3.12.14 / Pillow 13.0.0. The reports
`RELEASE-READINESS-V3.md`, `RELEASE-CANDIDATE-V3.md`,
`pillow-security-remediation.md`, and `MIGRATION-V3.md`, current metadata,
requirements and local formula were inspected. Remote source was not used as a
substitute for this checkout.

Public version remains **2.0.0**. The production formula's main archive remains:

```text
https://github.com/gongahkia/gitfetch/archive/refs/tags/2.0.tar.gz
c0cc31a94da4543a9d83b43b63c5078f45876bd880a3d80b5070321981fd9050
```

Those existing release coordinates still block representing this checkout as
Gitfetch 3.0.0. No version, tag, release checksum or publication was changed.

## Original findings: all 16 records

The fresh incoming audit reproduced 16 records across four packages. These
represent **nine distinct advisories**: one Critical, six High and two Medium.
Seven records are duplicate database entries with the **same advisory ID and
aliases**, not seven additional vulnerabilities. Raw records are preserved in
[original-audit.json](security-audits/tranche-07.3/original-audit.json).

All nine original package pins fall inside the authoritative affected ranges.
There is no verified downstream backport. In the requested classifications:

- **A, confirmed affected versions:** all nine unique advisories / 16 records.
- **B, potentially affected versions:** none left undecided; actual exploit
  reachability is conditional for several APIs, as described below.
- **C, not applicable to the actual version:** none. Some API paths are unused;
  that does not make an affected installed version patched.
- **D, duplicates:** records 2, 4, 6, 11, 12, 13 and 14.
- **E, already patched elsewhere:** Pillow 13.0.0 was already fixed by T07.2,
  is unchanged here and is not one of these 16 records. All nine network
  advisories are resolved by the verified upgrades in this tranche.

| Record | Actual pin | Advisory ID and upstream source | CVE | Severity | Disposition |
| --- | --- | --- | --- | --- | --- |
| 1 | certifi 2025.8.3 | PYSEC-2026-4320 / [GHSA-6q48-6c7w-9gw2](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2) | None assigned | Critical | fixed by 2026.10.23 |
| 2 | certifi 2025.8.3 | PYSEC-2026-4320 / [GHSA-6q48-6c7w-9gw2](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2) | None assigned | Critical | Duplicate of #1; fixed by 2026.10.23 |
| 3 | idna 3.10 | PYSEC-2026-215 / [GHSA-65pc-fj4g-8rjx](https://github.com/kjd/idna/security/advisories/GHSA-65pc-fj4g-8rjx) | CVE-2026-45409 | Medium | fixed by 3.20 |
| 4 | idna 3.10 | PYSEC-2026-215 / [GHSA-65pc-fj4g-8rjx](https://github.com/kjd/idna/security/advisories/GHSA-65pc-fj4g-8rjx) | CVE-2026-45409 | Medium | Duplicate of #3; fixed by 3.20 |
| 5 | requests 2.32.5 | PYSEC-2026-2275 / [GHSA-gc5v-m9x4-r6x2](https://github.com/psf/requests/security/advisories/GHSA-gc5v-m9x4-r6x2) | CVE-2026-25645 | Medium | fixed by 2.34.2 |
| 6 | requests 2.32.5 | PYSEC-2026-2275 / [GHSA-gc5v-m9x4-r6x2](https://github.com/psf/requests/security/advisories/GHSA-gc5v-m9x4-r6x2) | CVE-2026-25645 | Medium | Duplicate of #5; fixed by 2.34.2 |
| 7 | urllib3 2.5.0 | PYSEC-2026-1998 / [GHSA-gm62-xv2j-4w53](https://github.com/urllib3/urllib3/security/advisories/GHSA-gm62-xv2j-4w53) | CVE-2025-66418 | High | fixed by 2.8.0 |
| 8 | urllib3 2.5.0 | PYSEC-2026-1994 / [GHSA-2xpw-w6gg-jr37](https://github.com/urllib3/urllib3/security/advisories/GHSA-2xpw-w6gg-jr37) | CVE-2025-66471 | High | fixed by 2.8.0 |
| 9 | urllib3 2.5.0 | PYSEC-2026-1996 / [GHSA-38jv-5279-wg99](https://github.com/urllib3/urllib3/security/advisories/GHSA-38jv-5279-wg99) | CVE-2026-21441 | High | fixed by 2.8.0 |
| 10 | urllib3 2.5.0 | PYSEC-2026-141 / [GHSA-qccp-gfcp-xxvc](https://github.com/urllib3/urllib3/security/advisories/GHSA-qccp-gfcp-xxvc) | CVE-2026-44431 | High | fixed by 2.8.0 |
| 11 | urllib3 2.5.0 | PYSEC-2026-141 / [GHSA-qccp-gfcp-xxvc](https://github.com/urllib3/urllib3/security/advisories/GHSA-qccp-gfcp-xxvc) | CVE-2026-44431 | High | Duplicate of #10; fixed by 2.8.0 |
| 12 | urllib3 2.5.0 | PYSEC-2026-1998 / [GHSA-gm62-xv2j-4w53](https://github.com/urllib3/urllib3/security/advisories/GHSA-gm62-xv2j-4w53) | CVE-2025-66418 | High | Duplicate of #7; fixed by 2.8.0 |
| 13 | urllib3 2.5.0 | PYSEC-2026-1994 / [GHSA-2xpw-w6gg-jr37](https://github.com/urllib3/urllib3/security/advisories/GHSA-2xpw-w6gg-jr37) | CVE-2025-66471 | High | Duplicate of #8; fixed by 2.8.0 |
| 14 | urllib3 2.5.0 | PYSEC-2026-1996 / [GHSA-38jv-5279-wg99](https://github.com/urllib3/urllib3/security/advisories/GHSA-38jv-5279-wg99) | CVE-2026-21441 | High | Duplicate of #9; fixed by 2.8.0 |
| 15 | urllib3 2.5.0 | PYSEC-2026-4177 / [GHSA-vxq7-64xx-v4gw](https://github.com/urllib3/urllib3/security/advisories/GHSA-vxq7-64xx-v4gw) | CVE-2026-97689 | High | fixed by 2.8.0 |
| 16 | urllib3 2.5.0 | PYSEC-2026-4175 / [GHSA-8988-9cw3-xx77](https://github.com/urllib3/urllib3/security/advisories/GHSA-8988-9cw3-xx77) | CVE-2026-97687 | High | fixed by 2.8.0 |

Upstream severity and ranges were checked using each project's advisory and
GitHub's public advisory API; the audit is not the sole classification source.
The compact upstream metadata snapshot is
[upstream-advisories.json](security-audits/tranche-07.3/upstream-advisories.json).

| Advisory | Affected versions | First patched | Application-path assessment |
| --- | --- | --- | --- |
| GHSA-6q48-6c7w-9gw2 | >=2019.03.09,<2026.10.18 | 2026.10.18 | Requests uses certifi for normal API TLS verification. Compromised intermediate keys make the obsolete root bundle relevant to on-path attacks. 2026.10.19 restores unaffected roots; selected 2026.10.23 includes that correction. |
| GHSA-65pc-fj4g-8rjx | <3.15 | 3.15 | Requests uses IDNA for internationalized hosts. Very long crafted inputs can consume CPU; no Gitfetch exploit is claimed. 3.14 did not cover all alternate codec/per-label APIs, so it is not the selected fix. |
| GHSA-gc5v-m9x4-r6x2 | <2.33.0 | 2.33.0 | Upstream limits impact to direct callers of `extract_zipped_paths()`. Gitfetch has no such call; normal Requests usage is not affected. The vulnerable installed utility is still upgraded. |
| GHSA-gm62-xv2j-4w53 | >=1.24,<2.6.0 | 2.6.0 | Requests decodes HTTP response content. A malicious server can supply excessive chained encodings. The patched decoder rejects chains longer than five. |
| GHSA-2xpw-w6gg-jr37 | >=1.0,<2.6.0 | 2.6.0 | urllib3 streaming reads can over-decompress a small input. Requests uses this transport for content consumption; ordinary successful JSON responses do not establish immunity. No Brotli extra is installed in the formula graph. |
| GHSA-38jv-5279-wg99 | >=1.22,<2.6.3 | 2.6.3 | Vulnerable urllib3 redirect draining with `preload_content=False` may decompress a bomb before a read. Requests manages its redirects above urllib3, so the exact low-level redirect scenario is not demonstrated in Gitfetch. The installed affected library is upgraded. |
| GHSA-qccp-gfcp-xxvc | >=1.23,<2.7.0 | 2.7.0 | Sensitive headers can leak in proxied low-level cross-origin redirects. Gitfetch has no direct `connection_from_url().urlopen()` call and uses Requests' redirect handling. Proxy use remains possible; upgrade rather than rely on that distinction. |
| GHSA-vxq7-64xx-v4gw | >=1.10.3,<2.8.0 | 2.8.0 | Chunk-size lines can grow without bound through Requests/urllib3 streaming. Relevant to hostile HTTP response parsing; 2.8.0 adds a 65,536-byte bound. |
| GHSA-8988-9cw3-xx77 | >=1.26.0,<2.8.0 | 2.8.0 | HTTPS proxy/target TLS policies can be confused. Gitfetch does not configure custom proxy SSL contexts or disable certificate verification. User environment proxies can still be used; affected code is upgraded. A full HTTPS-proxy appliance was not exercised. |

All patched releases exist. **No confirmed unmitigated High/Critical finding
remains in the intended pinned graph as of this audit.** This is not a guarantee
against undisclosed vulnerabilities or a claim that every API exploit was
reproduced. No malicious public endpoint or real token was used.

## Resource changes, provenance and checksums

| Resource | Incoming | Selected | Requires-Python | Reason |
| --- | --- | --- | --- | --- |
| certifi | 2025.8.3 | **2026.10.23** | >=3.7 | Updated trust store, including restoration of unaffected roots |
| charset-normalizer | 3.4.3 | 3.4.3 | >=3.7 | No finding; canonical source URL correction only |
| idna | 3.10 | **3.20** | >=3.9 | Includes complete 3.15 security fix |
| Pillow | 13.0.0 | 13.0.0 | >=3.11 | Already patched by T07.2 |
| Requests | 2.32.5 | **2.34.2** | >=3.10 | Includes 2.33.0 utility fix; compatible dependency metadata |
| urllib3 | 2.5.0 | **2.8.0** | >=3.10 | Includes all six cited fixes, including the two requiring 2.8.0 |
| wcwidth | 0.9.3 | 0.9.3 | >=3.9 | No finding; preserve existing pin |

Selection used current upstream security information and release-specific PyPI
JSON, followed by reading the actual sdist `PKG-INFO`. For example:
`https://pypi.org/pypi/urllib3/2.8.0/json`. All four replacements are the releases
reported by the project index at assessment time; latest status alone was not
treated as a security assessment.

The exact source artifacts were fetched over verified HTTPS from
`files.pythonhosted.org`, not a mirror. Actual byte length, archive metadata and
SHA-256 were compared with release-specific PyPI metadata. The unchanged Pillow
archive from T07.2 was reused after a fresh remote availability/length check and
re-hashing its 47,058,631 bytes. All other sources were downloaded anew. Every
actual formula resource URL was checked, including the old charset-normalizer
alias redirect before normalizing it. No TLS or checksum check was bypassed.

| Source archive | Verified SHA-256 |
| --- | --- |
| [certifi-2026.10.23.tar.gz](https://files.pythonhosted.org/packages/fd/11/b524cbd9bbdaca58608e4cf4053fd463417549e1959fa8d3aa18319f9555/certifi-2026.10.23.tar.gz) | `a9895e6e2758b371e0545e321a3a8fd1fcfd9829ada8824a936dfb16aaaf36cd` |
| [charset_normalizer-3.4.3.tar.gz](https://files.pythonhosted.org/packages/83/2d/5fd176ceb9b2fc619e63405525573493ca23441330fcdaee6bef9460e924/charset_normalizer-3.4.3.tar.gz) | `6fce4b8500244f6fcb71465d4a4930d132ba9ab8e71a7859e6a5d59851068d14` |
| [idna-3.20.tar.gz](https://files.pythonhosted.org/packages/f5/08/8eea9d4b8302028f3abb2c0813953f7aec26d33b7a8960ed760e65ff29fa/idna-3.20.tar.gz) | `a7db850025b95ded1eae8a46181a1a6c56c92c96f0e2b005d9ff8dc0210cab44` |
| [pillow-13.0.0.tar.gz](https://files.pythonhosted.org/packages/ce/a4/9cc30690a394a8305e8be4c9036aa16d0dfddadd09079860b582f562496d/pillow-13.0.0.tar.gz) | `cdcd1ba258178f7356d74170c9a81ba4eab6a5d55748bc402a5a2a6fe6be3510` |
| [requests-2.34.2.tar.gz](https://files.pythonhosted.org/packages/ac/c3/e2a2b89f2d3e2179abd6d00ebd70bff6273f37fb3e0cc209f48b39d00cbf/requests-2.34.2.tar.gz) | `f288924cae4e29463698d6d60bc6a4da69c89185ad1e0bcc4104f584e960b9ed` |
| [urllib3-2.8.0.tar.gz](https://files.pythonhosted.org/packages/e3/05/b17359e1cefb4f909b5e40b1b90a496d987258916dbbf88e842c729f510e/urllib3-2.8.0.tar.gz) | `63bf2ead4c879426ebf22ef2a781eeb4aa3b4ae798a0435506f8687fd5bb9b63` |
| [wcwidth-0.9.3.tar.gz](https://files.pythonhosted.org/packages/69/4a/82d61476a1ccc20d43d0805724c5de4baa4971131a8db1816705ef53fe16/wcwidth-0.9.3.tar.gz) | `dfe7cfbd4cb59db9fe0931bd6091ab4a95b3acc5d56bfb50fa9fef0ccba5dc5c` |

The complete URLs, sizes, old/new pins, metadata requirements and digests are in
[resources.json](security-audits/tranche-07.3/resources.json). Each `formula_url`
is the exact production resource URL; all seven are now canonical source URLs.
This is origin and byte-integrity verification, not a claim of independent
cryptographic publisher attestation.

Homebrew's strict audit also required an empty line after the Python module
inclusion and the canonical charset-normalizer URL. These two small formula
corrections preserve its version/hash and do not change runtime behavior.

This follows Homebrew's [recursive Python-resource guidance](https://docs.brew.sh/Language-Specific-Formulae)
and [checksum requirements](https://docs.brew.sh/Checksum-Requirements).

To recheck exact source bytes without executing an archive:

```sh
python3 - <<'PY'
import hashlib, json, tempfile, urllib.request
from pathlib import Path
manifest = json.loads(Path('docs/security-audits/tranche-07.3/resources.json').read_text())
with tempfile.TemporaryDirectory() as directory:
    for resource in manifest:
        digest = hashlib.sha256()
        size = 0
        with urllib.request.urlopen(resource['formula_url'], timeout=60) as response:
            assert response.url.startswith('https://files.pythonhosted.org/packages/')
            with (Path(directory) / (resource['name'] + '.tar.gz')).open('wb') as output:
                while chunk := response.read(65536):
                    size += len(chunk)
                    assert size <= 128 * 1024 * 1024
                    digest.update(chunk)
                    output.write(chunk)
        assert digest.hexdigest() == resource['sha256']
        assert size == resource['bytes']
        print(resource['name'], resource['version'], digest.hexdigest())
PY
```

## Dependency closure and isolated environments

The existing seven resources form the complete required runtime closure.
Requests 2.34.2 requires `charset_normalizer>=2,<4`, `idna>=2.5,<4`,
`urllib3>=1.26,<3`, and `certifi>=2023.5.7`; the selected pins satisfy each bound.
Gitfetch additionally requires Pillow >=13,<14 and wcwidth >=0.9.3,<1.
No required recursive dependency is missing. Development, SOCKS, Brotli, HTTP/2,
documentation and other optional extras are not implicitly enabled.

Three different claims are kept separate:

1. **Unconstrained project resolution:** a fresh installation of the built wheel
   from `pyproject.toml` resolves the same four new network versions and Pillow,
   but charset-normalizer **3.5.2** and wcwidth **0.9.4**. This separate graph was
   audited and tested; it was not substituted for the formula graph.
2. **Exact Homebrew resources:** fresh Python 3.11.16, 3.12.14 and 3.14.7
   environments install the wheel plus all seven exact pins using the normal
   resolver. Installed metadata asserts precisely Gitfetch plus those seven
   distributions, with no inherited system packages. An additional Python 3.11
   environment installs the current sdist and rebuilds the four changed network
   packages from their verified source archives. All dependency checks pass.
3. **Actual Homebrew installation:** see the installation evidence below. A
   pip/uv installation with matching versions alone is not a Homebrew install.

The package and flat requirement ranges are unchanged in this tranche. A clean
fresh project resolution does not imply every older combination permitted by
those ranges has been independently security-cleared. These are runtime-graph
audits, not audits of every Homebrew native library, development tool or OS.

## Fresh audits and retained evidence

All audits used pip-audit **2.10.1**, its reachable PyPI advisory service, and no
ignored vulnerability IDs. Final runs used separate new HTTP cache directories
(`--cache-dir /tmp/gitfetch-073-fresh-...`) to force fresh advisory queries.
Original vulnerable versions were inventoried without installing them. `--no-deps --disable-pip` was used only for the explicit complete
resource lists (plus local Gitfetch in the actual-install inventory);
installed-site audits independently verify the closure.

| Input | Third-party packages | Advisory records | Result |
| --- | ---: | ---: | --- |
| Incoming seven pins | 7 | **16 / 9 unique** | FAIL, expected reproduction |
| Updated exact seven pins | 7 | **0** | PASS |
| Installed exact-pin environment, Python 3.12 | 7 | **0** | PASS |
| Installed unconstrained project environment | 7 | **0** | PASS |
| Actual Linux Homebrew installation inventory | 7 | **0** | PASS |

Gitfetch itself is reported by installed-site audits as not found on PyPI at
version 2.0.0 and therefore not database-auditable. That skip is preserved in the
raw output; it does not conceal a dependency advisory. Application security
coverage comes from the existing deterministic suite/review. Audit tooling's
own dependencies are not included as runtime resources.

```sh
audit_dir=docs/security-audits/tranche-07.3
uvx --from pip-audit==2.10.1 pip-audit \
  -r "$audit_dir/original-pins.txt" --no-deps --disable-pip \
  --cache-dir /tmp/gitfetch-073-fresh-original \
  --format json --output /tmp/gitfetch-original-audit.json
# Expected nonzero exit and the original findings above.
uvx --from pip-audit==2.10.1 pip-audit \
  -r "$audit_dir/updated-pins.txt" --no-deps --disable-pip \
  --cache-dir /tmp/gitfetch-073-fresh-updated \
  --format json --output /tmp/gitfetch-updated-audit.json
uvx --from pip-audit==2.10.1 pip-audit \
  --path /tmp/gitfetch-073-312/lib/python3.12/site-packages \
  --cache-dir /tmp/gitfetch-073-fresh-installed \
  --format json --output /tmp/gitfetch-installed-audit.json
uvx --from pip-audit==2.10.1 pip-audit \
  --path /tmp/gitfetch-073-project/lib/python3.12/site-packages \
  --cache-dir /tmp/gitfetch-073-fresh-project \
  --format json --output /tmp/gitfetch-project-audit.json
uvx --from pip-audit==2.10.1 pip-audit \
  -r "$audit_dir/actual-homebrew-pins.txt" --no-deps --disable-pip \
  --cache-dir /tmp/gitfetch-073-fresh-actual \
  --format json --output /tmp/gitfetch-actual-homebrew-audit.json
```

Raw results are retained as [updated-audit.json](security-audits/tranche-07.3/updated-audit.json),
[installed-homebrew-audit.json](security-audits/tranche-07.3/installed-homebrew-audit.json),
[project-audit.json](security-audits/tranche-07.3/project-audit.json), and
[actual-homebrew-audit.json](security-audits/tranche-07.3/actual-homebrew-audit.json).
Re-audit immediately before a separately authorized release; advisory databases
change. An unreachable service must be reported NOT VERIFIED, never zero.

## Regression, transport and package validation

Host: macOS 15.7.7 x86_64, plus the Ubuntu 24.04 container noted below. Each
complete suite ran outside the checkout, importing the installed package from
disposable site-packages. Tests and synthetic fixtures
came from the checkout. Standalone installer tests intentionally exercise its
installer source.

| Environment | Discovered | Passed | Skipped | Seconds |
| --- | ---: | ---: | ---: | ---: |
| Incoming editable Python 3.12.14 / Pillow 13.0.0 | 623 | 617 | 6 | 19.585 |
| Installed wheel, exact pins, Python 3.11.16 / Pillow 13.0.0 | 623 | 617 | 6 | 45.086 |
| Installed wheel, exact pins, Python 3.12.14 / Pillow 13.0.0 | 623 | 617 | 6 | 47.360 |
| Installed wheel, exact pins, Python 3.14.7 / Pillow 13.0.0 | 623 | 617 | 6 | 46.096 |
| Installed sdist + verified network sdists, Python 3.11.16 | 623 | 617 | 6 | 49.478 |
| Installed wheel, unconstrained project resolution, Python 3.12.14 | 623 | 617 | 6 | 49.176 |
| Actual Linux Homebrew source install, Python 3.12.16 / Pillow 13.0.0 | 623 | 617 | 6 | 28.541 |

Suites ran concurrently, so durations are not performance comparisons. No new
Python unittest was needed: the network updates exposed no application API
incompatibility. A targeted formula test was added after the source-build
findings below. The six existing opt-in provider/credentialed integration skips
remain skips.

Existing tests cover six-provider fixture collection and measurement semantics,
token/cache isolation, strict offline operation, avatar caching/limits, hostile
PNG EXIF, partial alpha, aspect ratio/fitting, Pillow 13 encoders, fonts, terminal
sanitization, Kitty/frame safety, SVG/PNG/summary exports, JSON/configuration
compatibility, module/plugin ordering, request counts and single evaluation.
No application code or collection behavior changes in this tranche.

An additional disposable loopback harness passed **eight assertions** on each of
Python 3.11/3.12/3.14 exact-pin environments and the independently resolved
Python 3.12 environment, then the actual Linux Homebrew installation:
transient GET retry, same-origin auth retention,
cross-origin auth stripping, normal gzip JSON, rejection of six chained gzip
encodings, explicit HTTP proxy routing, rejection of an untrusted TLS certificate
and acceptance with its explicit test CA. Synthetic certificates/sentinels only;
verification was never disabled. No external provider request occurred. This
does not establish every enterprise HTTPS-proxy configuration or live provider.

Additional checks passed:

- Ruff 0.17.3, entire checkout; mypy 1.20.2, 29 runtime source files.
- Python 3.11/3.12/3.14 compilation; dependency checks in all five environments.
- Isolated wheel/sdist build and Twine 7.0.0 checks, no build warnings.
- Installed console and module entrypoints, help/version, modules, graphics
  diagnostics and Bash/Zsh/Fish completion generation in all five environments.
- Licensed bundled DejaVu font, language icons and their licenses in wheel and
  sdist; installed font lookup and Unicode measurement. No system font required.
- All seven source checksums and availability; Ruby syntax; whitespace diff.

Reproduction commands (from the checkout unless `cd` is shown):

```sh
uvx --from build==1.4.0 pyproject-build --outdir /tmp/gitfetch-073-dist
uvx --from twine==7.0.0 twine check /tmp/gitfetch-073-dist/*
repo_dir="$PWD"
for py_minor in 3.11 3.12 3.14; do
  env_dir="/tmp/gitfetch-073-${py_minor/./}"
  uv venv --python "$py_minor" "$env_dir"
  uv pip install --python "$env_dir/bin/python" \
    /tmp/gitfetch-073-dist/gitfetch-2.0.0-py3-none-any.whl \
    -r "$repo_dir/docs/security-audits/tranche-07.3/updated-pins.txt"
  uv pip check --python "$env_dir/bin/python"
  (cd /tmp && "$env_dir/bin/python" -m unittest discover -s "$repo_dir/tests")
  "$env_dir/bin/python" -m compileall -q gitfetch installer tests
done
uv venv --python 3.11 /tmp/gitfetch-073-sdist
uv pip install --python /tmp/gitfetch-073-sdist/bin/python \
  /tmp/gitfetch-073-dist/gitfetch-2.0.0.tar.gz \
  -r docs/security-audits/tranche-07.3/updated-pins.txt
# Four verified local sdists were additionally rebuilt/reinstalled here.
(cd /tmp && /tmp/gitfetch-073-sdist/bin/python -m unittest discover -s "$repo_dir/tests")
uv venv --python 3.12 /tmp/gitfetch-073-project
uv pip install --python /tmp/gitfetch-073-project/bin/python \
  /tmp/gitfetch-073-dist/gitfetch-2.0.0-py3-none-any.whl
(cd /tmp && /tmp/gitfetch-073-project/bin/python -m unittest discover -s "$repo_dir/tests")
/tmp/gitfetch-072-312/bin/ruff check .
/tmp/gitfetch-072-312/bin/mypy gitfetch
ruby -c Formula/gitfetch.rb
git diff --check
```

Artifacts are private verification builds still named **2.0.0**, in
`/tmp/gitfetch-073-dist`; they are not release candidates. Byte digests, package
inventories, import paths and loopback outcomes are retained in
[verification.json](security-audits/tranche-07.3/verification.json).

## Homebrew verification and installation

The host Homebrew installation was never modified. Developer checks ran in a
copy at `/tmp/gitfetch-073-brew`, with separate HOME, cache, logs and build temp.
The production formula was copied into an explicitly trusted disposable tap.
**Ruby syntax, `brew audit --strict` and `brew style` pass.** The initial strict
audit identified the spacing/canonical-URL issues corrected above.

The exact requested standalone-path command was attempted:

```sh
brew update-python-resources --print-only Formula/gitfetch.rb
```

This Homebrew rejects formula files outside a tap. Retrying its tap copy reached
Python setup, but the nonstandard temporary prefix could not bootstrap its
Python dependency (`Inherited sandbox permits writes to .../bin/brew`). It
produced no trustworthy generated resource set. No sandbox was disabled and no
normal Homebrew settings or system developer tools were changed. The verified
manual PyPI metadata/archive/checksum procedure above is the resource-update
basis; an old GitHub release was not used to resolve unreleased v3 requirements.

### Native source-build repair

Isolated source verification found a packaging omission masked by PyPI wheels.
The formula declared only Python, while Pillow source builds need native image
and font libraries. A clean build of the **verified Pillow 13 sdist** failed with
`RequiredDependencyException: ... could not be found for zlib`. The initial
Homebrew attempt also entered a nested pip source build of CMake through
Pillow's pybind11 build dependency. It was stopped in the disposable container
before the CMake bootstrap completed. This is not reported as a completed
Homebrew installation failure or a Python API incompatibility.

The formula now declares:

- Build tools: `cmake`, `pkgconf`.
- Runtime libraries: `freetype`, `jpeg-turbo`, `webp`, `zlib-ng-compat`.
- Existing runtime interpreter: `python@3.12`.

Zlib/JPEG are Pillow's default required native codecs; FreeType supports the
bundled TrueType font, and WebP retains an allowed avatar format. This is the
needed subset of [Pillow's source prerequisites](https://pillow.readthedocs.io/en/stable/installation/building-from-source.html),
not a change to image policy or a new rendering feature. CMake avoids building
the same tool from a pip sdist; pkgconf supplies native-library discovery.
Homebrew manages these native formulae and their checksummed official bottles;
they are not invented Python resources or unverified mirrors.

The formula's test now checks JPEG/zlib/WebP/FreeType capabilities, loads its
**packaged** DejaVu font with combining/CJK text, verifies PNG/WebP partial-alpha
round trips and a non-square JPEG round trip, as well as CLI help. It performs
no provider request and cannot be satisfied by a codec-less Pillow build.

A second packaging defect was reproduced in Homebrew's default inherited Python
site-packages: `pip check` reported `wheel 0.48.0 requires packaging, which is
not installed`. This came from the base interpreter's global tooling, not a
missing Gitfetch runtime requirement. The formula now explicitly uses
`virtualenv_install_with_resources system_site_packages: false`. Its test asserts
the isolated `pyvenv.cfg` policy. The installed environment contains **only
Gitfetch plus its seven declared resources**; neither inherited tooling nor
unrelated site packages can mask missing resources. The final dependency check
passes without adding an unnecessary packaging runtime resource.

### Actual installation results

**PASS in a disposable Ubuntu 24.04 x86_64 Docker container**, using standard
`/home/linuxbrew/.linuxbrew` and the current local sdist. Homebrew installed all
seven resources from source and verified their formula checksums. The private
source archive was `gitfetch-2.0.0.tar.gz`, SHA-256
`35d01cec14ee94bb094fee60962dc2bb19045e2b46804ee59fc41a5f7d54737b`.
This digest was computed from actual local bytes and used **only** in the
container's test formula. It is not Gitfetch's production release checksum.

Final evidence:

- Interpreter Python **3.12.16**; exact seven resource versions match the table.
- Only the application's site-packages are exposed. Full inventory and import
  path are retained in `verification.json`; dependency check passes.
- Source-built Pillow 13.0.0 reports JPEG, zlib, WebP and FreeType available.
- `brew test` passes its CLI, bundled-font, isolated-env and image round trips.
- Both console/module entrypoints and all three completion generators pass.
- The complete installed suite passes: **623 discovered, 617 passed, 6 skipped**,
  28.541 seconds, from `/tmp` rather than the source directory.
- All eight loopback HTTP/TLS checks pass. A fresh audit of the **actual installed
  inventory**, including the local Gitfetch skip described above, reports no
  known third-party advisories.

The first Linux suite had one fixture-setup failure: `/acceptance` contained
`tests` and `installer`, but lacked `pyproject.toml`. The mocked standalone
installer therefore correctly selected its remote fallback rather than the
expected local checkout. Copying the actual metadata file corrected the
acceptance fixture; no application code/test expectation was changed. The
complete suite was rerun successfully, rather than omitting that test.

The tested native versions include CMake 4.4.5, pkgconf 3.0.10, FreeType 2.15.0,
jpeg-turbo 3.2.1, WebP 1.6.0 and zlib-ng-compat 2.3.3_1. The complete native
inventory is retained in [native-versions.txt](security-audits/tranche-07.3/native-versions.txt).
These native/OS/build-tool packages are **not** represented as cleared by
pip-audit; the security inventory here covers the Python runtime resources.

Homebrew warns that source builds are unsupported by its current support policy;
the requested explicit source install nevertheless completed. Docker's kernel
provides Landlock ABI 8 rather than 10, so Homebrew reported applying the network
restrictions supported there. No isolation/checksum/TLS setting was disabled.
This is actual container installation evidence, not physical Linux terminal
acceptance, a macOS install, or acceptance of the future 3.0.0 release archive.
Those three broader claims remain **NOT VERIFIED** in this tranche. The test
container was removed after capturing evidence; the preexisting Ubuntu image
and normal Homebrew installation were preserved.

For a fresh isolated installation (requires Docker, uses only a disposable
Ubuntu container; does not touch the host's Homebrew):

```sh
repo_dir="$PWD"
evidence_dir=$(mktemp -d)
# Build the current 2.0.0-labelled verification artifacts first, as above.
cp docs/security-audits/tranche-07.3/brew-install.sh "$evidence_dir/brew-install.sh"
docker run --rm \
  --mount "type=bind,src=/tmp/gitfetch-073-dist,dst=/candidate,readonly" \
  --mount "type=bind,src=$repo_dir/Formula/gitfetch.rb,dst=/production.rb,readonly" \
  --mount "type=bind,src=$evidence_dir,dst=/evidence" \
  ubuntu:24.04 bash /evidence/brew-install.sh
```

The helper computes the local source SHA-256 and changes **only its container
formula** to that local archive. It installs with `--build-from-source`, runs
`brew test`, and prints installed versions/entrypoint output. Its container
package-manager operations need no host sudo, shell-file edit or global pip
installation. For macOS, repeat the same local-archive formula procedure in a
**disposable macOS VM with its own standard-prefix Homebrew**, then run:

```sh
brew trust gitfetch/security       # only the known local test tap in the VM
brew audit --strict gitfetch/security/gitfetch
brew style gitfetch/security/gitfetch
brew install --build-from-source gitfetch/security/gitfetch
brew test gitfetch/security/gitfetch
"$(brew --prefix python@3.12)/bin/python3.12" -m pip \
  --python="$(brew --prefix gitfetch/security/gitfetch)/libexec/bin/python" check
```

An eventual release must repeat installation against the actual approved 3.0.0
source artifact with its own computed checksum, not reuse this temporary digest.

## Exact checkout changes

- `Formula/gitfetch.rb`: four security upgrades; canonical charset-normalizer
  source URL; native prerequisites; isolated virtualenv; codec/font/alpha test;
  required formula spacing.
- `docs/HOMEBREW-SECURITY-V3.md`: this evidence and acceptance procedure.
- `docs/RELEASE-READINESS-V3.md`, `docs/RELEASE-CANDIDATE-V3.md`: focused current
  security/install addenda; historical findings retained.
- `docs/security-audits/tranche-07.3/`: `original-pins.txt`,
  `original-audit.json`, `updated-pins.txt`, `updated-audit.json`,
  `installed-homebrew-audit.json`, `project-audit.json`,
  `actual-homebrew-pins.txt`, `actual-homebrew-audit.json`, `resources.json`,
  `upstream-advisories.json`, `verification.json`, `native-versions.txt`, and
  `brew-install.sh`.

Final observed HEAD remains `ad06587c17a2a5ee3ca950e4d96b2b106c0663d5`, branch
`main`. The listed work is uncommitted. README, Python application/tests,
requirements, package metadata, public version and main source checksum are
unchanged. No preexisting changes were overwritten.

## Release impact and remaining limitations

The dependency-security blocker for the intended Homebrew resource set is
resolved. Runtime resolution remains clean, Pillow 13/Python >=3.11 policy is
unchanged, and no application API incompatibility remains. The application code,
README, public version, package requirements, terminal layouts, graphics
protocol and export designs are unchanged. Homebrew gains the required native
source-build dependencies, environment isolation and a targeted formula test.

Release remains **NOT READY** until the maintainer separately authorizes and
verifies version synchronization, actual 3.0.0 artifacts and the main Homebrew
archive/checksum. Lifecycle/platform/live-provider acceptance from the existing
readiness reports is not replaced by this security exercise. No physical
Ghostty/Zellij/SSH/Windows or credentialed-provider acceptance was attempted;
macOS Homebrew installation and the final release archive still need acceptance.

Dependency security is ready for the next **separately authorized RC preparation**
step, followed by a fresh audit of the final bytes. Do not restore obsolete
resource pins as a rollback; investigate a compatible patched release instead.
No commit, tag, push, publication, normal Homebrew installation change or release
coordination was performed.
