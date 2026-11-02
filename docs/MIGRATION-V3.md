# Migrating a Gitfetch 2.x configuration

The v3 development checkout retains existing command names, saved profiles and
TOML configuration presets. The package/version strings remain 2.0.0 until the
maintainer approves the release version; published 2.0 downloads are not the v3
candidate.

Back up `~/.config/gitfetch/config.toml`, then install the local checkout into a
new virtual environment and run `gitfetch config validate`. Existing explicit
avatar styles are preserved; old style/ramp settings select text rendering.
No interactive setup is performed by ordinary profile output. The config wizard
is opt-in and refuses to replace an existing file without `--force`; force means
replace with a newly chosen preset, so keep a backup of custom settings.

Controls are independent: configuration presets select modules/settings;
modern/classic select presentation; visual presets balanced/compact/showcase
select appearance; split/stack controls composition; themes/custom colors control
foreground colors. Named profiles and dotted overrides retain their precedence.

Modern `avatar_fit=auto` fits nonzero alpha bounds. Use `original` to preserve
intentional whitespace. Classic keeps original fitting. Exports use their own
`export_avatar_fit=original` default; explicit `visible` is non-destructive.

Intentional compatibility changes:

- Missing/unsupported numeric values can be JSON `null` instead of zero. Do not
  assume every numeric leaf remains non-null or integer: GitLab percentages can
  be fractional. JSON envelope shapes remain supported, but nullable semantics
  deliberately corrected earlier misleading values.
- GitLab profile languages are repository prevalence; Bitbucket primary-language
  counts are not byte percentages. Follow units, coverage and scope metadata.
- Cards honor module selection; disabled/hidden statistics and biography no
  longer reappear from top-level user fields.
- SVG/PNG cards are redesigned. `display.export_style=legacy` keeps previous
  artwork, with font/security fixes. Explicit modern terminal SVG uses the
  deterministic `svg_columns`/`svg_rows` viewport.
- Fixed-size cards may omit selected content with a notice even with `--details`.
  Increase card dimensions within the eight-million-pixel limit when needed.
- Plugins require explicit trust. An explicit empty/disabled plugin selection no
  longer imports configured plugin source. SDK registration-only calls that omit
  `plugins.modules` retain their existing behavior.
- Local installer scripts install their checkout. In virtual environments they
  do not modify shell startup files. Remove only obsolete installer PATH lines;
  do not replace the entire PATH.

Before publication the maintainer must choose the version, update release
references and the Homebrew source URL/checksum to that actual artifact, and
review terminal/browser/platform acceptance. See `RELEASE-READINESS-V3.md`.

Security correction: selecting a non-GitHub provider no longer implicitly falls
back to `GITHUB_TOKEN`. Use that provider's own token variable, a custom
`profile.token_env`, or an explicit CLI token. Deliberate provider-level
`providers.<name>.token_env` overrides remain supported. A profile's default
`GITHUB_TOKEN` name is ignored for other services. Review past cross-provider use
if a GitHub credential may have been sent to an unintended service; this audit
used only synthetic sentinels and cannot establish historical exposure.
