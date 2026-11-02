# Gitfetch 3.0 release checklist

This is a future maintainer procedure. No approval to publish is implied by the
local `3.0.0rc1` candidate or this checklist. See the candidate verification report
and its exact manifest, test evidence and outstanding manual matrix.

## Candidate review

- Verify `SHA256SUMS` and `scripts/assemble_rc.py --verify <manifest>`.
- Review the recorded dirty-tree source provenance, included file list and diff.
- Install the candidate wheel and sdist into separate environments outside the
  checkout; confirm metadata, CLI, User-Agents and full suites.
- Review the wheel/sdist dependency audits. Homebrew is excluded by maintainer direction.
- Complete or explicitly disposition physical lifecycle,
  SSH/Windows/Linux desktop and authorized live-provider checks.
- Record final maintainer approval and supported-platform limitations.

## Final release, only after separate authorization

1. Freeze the approved source and review concurrent changes. Preserve unrelated
   edits; prepare the intended release changes for review before any commit.
2. Change package metadata and runtime `__version__` from `3.0.0rc1` to `3.0.0`;
   User-Agents derive from that constant. Update current README/migration status.
   Retain historical engineering reports and do not claim existing RC hashes are
   hashes of the final version.
3. Rebuild wheel/sdist from the exact final source in clean pinned build tools:

   ```sh
   python -m build --outdir /tmp/gitfetch-final-dist
   python -m twine check /tmp/gitfetch-final-dist/*
   shasum -a 256 /tmp/gitfetch-final-dist/*
   ```

4. Repeat the Python 3.11/3.12/3.14 installed-artifact suites, Ruff, mypy,
   compilation, security audits, resource/export/JSON/protocol/offline checks and
   installed-package tests. Review the final diff and generated metadata.
   A source change invalidates verification of those earlier bytes.
5. Obtain explicit approval for the exact final files and release actions. Stage
   only reviewed paths, then create the approved commit and annotated tag:

   ```sh
   git diff --check
   git status --short
   # git add <explicit reviewed release paths>
   git diff --cached
   git commit -m "Release Gitfetch 3.0.0"
   git tag -a v3.0.0 -m "Gitfetch 3.0.0"
   git show --stat v3.0.0
   ```

6. Confirm the tag points to the approved source; push the approved branch and
   tag only with authorization. Create the GitHub release with reviewed notes,
   migration/limitations and the verified final artifacts/checksums:

   ```sh
   git push origin <approved-release-branch>
   git push origin v3.0.0
   gh release create v3.0.0 /tmp/gitfetch-final-dist/* \
     --verify-tag --title "Gitfetch 3.0.0" --notes-file /tmp/gitfetch-release-notes.md
   # PyPI publication is a separate explicitly approved action, if desired.
   ```

7. Verify the published final artifacts against the approved hashes. Homebrew
   packaging/publication is excluded by maintainer direction. Existing formula
   files are legacy repository material and are not a release deliverable.

## Rollback

Retain RC/final manifests and exact artifacts. Before publication discard only
the newly assembled candidate attempt, never unrelated work. After publication,
do not move an existing tag or replace published artifact bytes. If necessary
withdraw an affected package through the channel's approved process and prepare
a new version. Preserve Python >=3.11 and security-patched Pillow/network
dependencies; rolling back application code is not permission to restore known
vulnerable resource pins. Back up user configuration; never clear user caches or
credentials as a release rollback step.
