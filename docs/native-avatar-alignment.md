# Tranche 05B.1 — native avatar alignment

Tranche 05B.1 physical Ghostty acceptance: PASS, confirmed by the user.

Following physical acceptance, the default policy is `avatar_fit=auto`:
modern presentation resolves it to visible fitting; classic and exports retain
original appearance. Explicit `original` and `visible` preferences remain
authoritative for modern rendering. Saved configurations containing an explicit
`original` value keep that preference. Missing values and newly generated
configurations retain `auto` across round trips, including presentation changes.

## Audit and reproduction

The available local cached avatar has a 460×460 canvas and nonzero-alpha
bounds (0, 204, 291, 460), measured without provider requests. Its visible
rectangle is 291×256: 35.2% of the canvas area. There are 204 transparent
rows above and 169 transparent columns to the right. This directly explains
the late portrait and excess gap for this asset. The original screenshot
files were not supplied, so correspondence to those screenshots still needs
physical confirmation.

PreparedAvatar previously retained the entire oriented canvas; the planner
measured that canvas. Kitty transmits an aspect-preserving PNG capped at
512 pixels per edge into the planned c/r rectangle. The writer anchors at
the frame's first row plus its margin, using relative cursor motion and C=1.
Half-block, ASCII and braille compose from row zero next to the first identity
row. There is no vertical centering offset in either path. Split adds three
columns after the avatar rectangle; stack adds one separator row before text.
Transparent padding is therefore inside a correctly positioned rectangle.

At a fixed 22-column width, the actual cached asset's half-block canvas is
11 rows and first ink is row 5. Explicit visible fitting yields 9 rows and
first ink on row 0. ASCII changes from 12 rows / first ink 5 to 10 / 0.
Braille changes from 11 / 6 to 9 / 2: luminance thresholding still affects
which dark portrait pixels become lit dots.

Measured planner allocations using the fixed synthetic profile and the actual
cached image (half-block geometry shared with Kitty):

| Terminal | Original columns × rows | Visible columns × rows |
| --- | --- | --- |
| 60×20 | 19×9 | 20×8 |
| 80×24 | 23×11 | 26×11 |
| 120×40 | 33×16 | 34×14 |
| 200×15 | 13×6 | 15×6 |

These allocations depend on profile content as well as viewport dimensions.

## Conservative fitting policy

Modern presentation now uses visible fitting by default, following physical
acceptance. Use `--set display.avatar_fit=original` to preserve intentional
transparent composition, including small logos. Explicit `visible` is also
supported. Alpha alone cannot identify intentional whitespace; the original
option remains the authoritative opt-out. Classic rendering and exports retain
their original appearance for every fitting preference.

Visible fitting creates a cropped RGBA copy from already-decoded pixels and
retains every pixel with alpha greater than zero, including partial edges and
opaque black. It never trims by RGB/luminance, rewrites cache files, stretches
the crop, or repeats acquisition/decoding. Empty images retain their canvas.
A faint nonzero-alpha outlier deliberately prevents aggressive cropping.

Both interactive backends and modern plain/ANSI serialization fit before
planning. Kitty and text encoders receive the same fitted geometry. The crop
fills the allocated width with the existing three-column split gap, avoiding
an additional horizontal centering policy. Classic rendering, explicit text
styles and ramps, JSON, SVG/card/PNG exports retain their existing behavior.
Cell rounding and assumed character aspect ratios remain as before; physical
font cell proportions and braille luminance can still affect appearance.

The terminal writer, detection, watch policy, cache acquisition and provider
collection are unchanged. Existing safety tests remain in the full suite.

## Verification

Nine tests added in `tests/test_avatar_composition.py`, including subtest
matrices over all four backends, split/stack, the four requested viewports,
non-square images, portraits, all-side and single-side padding, alpha=1 edges,
opaque black, empty images, intentional logo whitespace, decode guards,
serializer consistency and classic/export regression checks.

Four further policy regression tests cover modern implicit and explicit fitting,
all presets, configuration round trips and CLI overrides, and byte-identical
classic/SVG/card/PNG output across fitting preferences and presentations.

Python 3.10.21 and 3.12.14 development suites: each 569 discovered, 563 passed,
6 skipped. Ruff passes; mypy
passes for 24 runtime files; all 14 development packages are compatible.
Wheel and sdist build successfully. The installed wheel, tested on both Python versions from /tmp
outside the checkout, also passes all 569 tests on each (563 passed, 6 skipped);
installed CLI help and module-list smoke tests pass. Existing packaging warnings remain:
missing top-level LICENSE and deprecated TOML license table.

## Direct visual acceptance

In Ghostty, from this repository, replace YOUR_USERNAME with the cached account:

```sh
source .venv/bin/activate
gitfetch --graphics-info
gitfetch --offline --user YOUR_USERNAME --presentation modern --avatar-renderer kitty --set display.avatar_fit=original
gitfetch --offline --user YOUR_USERNAME --presentation modern --avatar-renderer kitty --set display.avatar_fit=visible
gitfetch --offline --user YOUR_USERNAME --presentation modern --avatar-renderer text --avatar-style halfblock --set display.avatar_fit=visible
gitfetch --offline --user YOUR_USERNAME --presentation modern --avatar-renderer text --avatar-style ascii --set display.avatar_fit=visible
gitfetch --offline --user YOUR_USERNAME --presentation modern --avatar-renderer text --avatar-style braille --set display.avatar_fit=visible
gitfetch --offline --user YOUR_USERNAME --presentation modern --avatar-renderer kitty --set display.avatar_fit=visible --set display.layout=stack
```

Repeat at 60×20, 80×24, 120×40 and 200×15. Check portrait alignment, gap,
no overlap, transparency, prompt below output and fallback. Missing offline
assets remain omitted. Local synthetic acceptance can also use:

```sh
python tests/preview_native.py --confirm-kitty --fit visible
python tests/preview_native.py --fit visible --layout stack
```

Zellij acceptance can proceed with the existing procedure and safety policy;
add original/visible comparisons. No multiplexer support is newly asserted.
Ghostty acceptance was recorded by the user. Physical Zellij acceptance remains
pending.
