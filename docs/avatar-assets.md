# Avatar assets and image quality (Tranche 05A)

## Boundary and API

`images.AvatarLoader.load(url) -> AvatarResult` acquires and prepares an optional
avatar independently of themes, viewport, layout and graphics protocols. It
performs no provider collection. `AvatarPolicy` carries the existing cache
policy, offline/refresh state and a hashed authentication/instance/access scope.
`AvatarResult` contains a `PreparedAvatar` or a safe failure category, never an
exception message or sensitive URL.

`PreparedAvatar` contains a detached RGBA image, original dimensions, oriented
source dimensions, effective dimensions, prepared-image transparency/partial-alpha
flags, and `network`, `cache` or `stale-cache` source status. Treat its Pillow
image as read-only. `fit((width, height))` returns an independent, bounded RGBA
copy, preserving aspect ratio without upscaling. It is suitable for a later
native-graphics backend; no graphics transport, capability probe or cursor
operation is implemented here.

The explicit API can be used without any terminal or renderer:

```python
policy = AvatarPolicy.from_cache(
    cache, provider=provider, instance=instance, token=token,
    mode="public", offline=offline,
)
loader = AvatarLoader(policy)
result = loader.load(document.avatar_reference)
if result.asset is not None:
    rgba = result.asset.fit((256, 256))
```

The loader memo holds at most eight URL results, including safe failures. A memo
hit does not read, download or decode again. Eviction bounds retained pixel data;
a URL revisited after eviction must be loaded again. Prepared images are at most
1024×1024 (four MiB of RGBA pixels each), rather than retained full-resolution
source images. The loader should live for one frame/command, not indefinitely.

## Cache and isolation

Binary source images live in `~/.cache/gitfetch/avatars-v1/`, beside and separate
from the API JSON response cache. Nothing is base64-encoded into response JSON.
The entry name is SHA-256 of the scope plus the exact source URL. The scope
hashes a structured tuple of provider, API instance, access mode and a SHA-256
credential fingerprint. Anonymous and authenticated data, different credentials,
instances and providers do not share entries. No raw token, URL, signed query,
account name or other lookup metadata is written to filenames or sidecars.
An exact URL change produces a different key, never an unrelated-avatar fallback.
Provider response-cache keys and authentication behavior are unchanged.

Caching uses the existing `cache.enabled` and `cache.ttl_seconds` settings.
Expiration is file mtime plus that TTL; online reads reject expired entries.
Offline reads may reuse expired entries, reported as `stale-cache`, consistent
with existing provider offline reuse. `--refresh` bypasses avatar reads and
replaces a cached image only after successful download and preparation. A failed
refresh displays no avatar and leaves a previous valid disk entry intact.
`--offline` always prevents HTTP, even if a library caller also sets refresh.
The CLI's existing refresh/offline argument constraints remain unchanged.

Directories use 0700 and files 0600. Existing permissions are tightened before
reads. Reads reject symlink entries, nonregular/oversized files and foreign-owned
files where ownership APIs are available. Writes use a private temporary file,
flush/fsync and atomic replacement, then remove temporary files on failure.
Symlink cache directories are rejected. Optional cache I/O failures cause a cache
miss or skipped write, never loss of the textual profile. Cache-disabled loading
does not create or read asset files. Corrupt cached images are discarded; online
loading can retry HTTP, offline loading falls back to no avatar.

After successful writes, oldest owned avatar entries are pruned to 128 files and
64 MiB, whichever limit is reached first. Unrelated files are retained. Abandoned
`.avatar-*.tmp` files older than a day are cleaned during pruning. The cache is
best-effort under simultaneous processes: individual writes are atomic, but this
is not a transactional quota manager; a concurrent writer can temporarily exceed
the quota until another write/prune. No database, lock service or new option was
added.

## Fetching and preparation limits

Only HTTP(S) URLs without URL-userinfo credentials are accepted. Self-hosted
instances, custom ports and private/loopback hosts remain supported deliberately;
this CLI does not impose a public-IP-only network policy. Provider authorization
headers, cookies and token-bearing sessions are never given to the image client.
Signed query URLs remain supported, without being logged or stored as metadata.
The isolated urllib opener uses normal TLS verification and validates each
redirect. At most three redirects are followed; unsupported schemes, credentials
and HTTPS-to-HTTP downgrades are refused. Relative safe redirects work.

Each HTTP operation uses a ten-second socket timeout. This is an I/O timeout,
not a hard end-to-end deadline against a peer continuously trickling bytes.
Downloads request identity encoding and read at most five MiB plus one byte.
Content-Length can reject an excessive response early, but actual bytes are
always bounded, including missing, inaccurate or malformed lengths. Responses
and redirect errors are closed. Network and image errors become safe optional
failures without a traceback or a URL-bearing diagnostic.

Pillow recognizes only PNG, JPEG, GIF, WebP and BMP in this path; unsupported
formats fall back to text. Container verification precedes pixel decoding. Before
loading pixels, dimensions must be positive, at most 8192 on either edge, and at
most 4,194,304 pixels total. Pillow decompression-bomb warnings are errors within
the decode scope; its global pixel limit is never disabled or changed. Truncated
images are not enabled. These bounds constrain work, not a guarantee of exact
process RSS: codec buffers, Pillow metadata and transient image copies also cost
memory. PNG's own compressed-metadata limits remain enabled.

Only frame zero of animated inputs is prepared. EXIF orientation is applied once.
Conversion retains RGBA, then Lanczos downsampling bounds the longest edge to
1024. Embedded EXIF/GPS/comments/profiles are removed from the prepared image,
not copied into exports. Container verification opens the header separately;
actual pixel decoding/preparation occurs once per loader miss, not once per
renderer or layout candidate. No additional image-processing dependency was added.

## Encoding and intentional visual differences

All three text styles use one RGBA Lanczos resize per encoding. Existing
cell-geometry factors remain ASCII 0.55, half-block/Braille 0.5; Braille keeps
its 2×4 dot geometry and original dot orientation. Non-square images retain
their aspect ratio, subject to integer cell rounding. Modern planning still
uses source image geometry, budgets rows/columns and encodes only its final
allocation. A final legacy-encoder guard caps dimensions at 256 cells in each
axis, reducing width proportionally or omitting an impossibly tall source.
This prevents pathological aspect ratios or enormous configured widths from
expanding an otherwise small valid image into unbounded output. Normal modern
allocations are much smaller and unaffected.

- **ASCII:** fully transparent samples are spaces. Custom ramps, single-cell
  grapheme filtering, historic luminance direction and monochrome/color support
  remain intact. Dark opaque pixels are not background-keyed or erased. Dense
  `B` regions can therefore remain for genuinely opaque dark images with the
  historic ramp; a user can choose a lighter ramp, for example
  `--set 'display.ascii_ramp=.:-=+*#%@'`. No silent ramp override was introduced.
- **Half-block:** two visible halves use foreground/background `▀`; top-only
  uses foreground `▀`, bottom-only foreground `▄`, with the default background
  restored. Two transparent halves use a reset and space. Opaque black remains
  black image content. Monochrome retains brightness-based block selection.
- **Braille:** transparent samples never set dots or contaminate dot colors;
  color averages the lit visible dots, rather than hidden/dark pixels. Entirely
  transparent cells are spaces. Brightness threshold and dot ordering remain.

Arbitrary alpha compositing is impossible in ordinary ANSI without knowing the
terminal background. Partial alpha uses deterministic 4×4 ordered coverage,
retaining original visible RGB instead of blending against assumed black.
This approximates opacity spatially and can show a pattern at small sizes.
Pillow premultiplied-alpha resampling avoids dark transparent-edge fringes, with
possible one-unit RGB rounding. Resampling and corrected visible-dot coloring
intentionally change some opaque avatar glyphs/colors too. No terminal background
color is set, and only trusted SGR styling is generated. Plain/no-color output
contains no escape sequences.

Card SVG/PNG retain their existing layout, palette and circular avatar slot.
Non-square sources are now contained within that slot using transparent padding,
rather than stretched. SVG embeds the prepared static PNG. PNG multiplies the
circular mask by source alpha and composites onto the already-defined card
background; transparent corners no longer paste black. These are image-correctness
fixes, not an export visual redesign. Terminal SVG retains its classic path.

## Rendering integration and compatibility

Profile CLI rendering builds the semantic document once, then supplies one lazy
loader through a shallow rendering-config copy for each frame. Module/plugin
configuration and evaluation are unchanged. Watch creates a fresh frame memo so
TTL and refresh remain meaningful, while reusing disk assets. Modes construct
one command-scoped loader with the same resolved cache/auth policy.

`avatar_context(loader)` and the small `avatar_render` decorator bridge legacy
`fetch_avatar_image(url)`/rendering signatures without duplicate format-specific
loaders. Context variables scope that bridge and reset after nested calls; the
explicit `AvatarLoader` remains the preferred acquisition API. Existing direct
library calls without an injected loader remain uncached HTTP-capable calls,
with the new validation/preparation limits. Library offline callers must pass
an offline loader, either through `avatar_context` or `_avatar_loader` in their
rendering configuration; CLI `--offline` supplies it automatically.

`render_output`, card and summary SVG/PNG, mode terminal/SVG rendering and
comparison avatars all consume this policy. Comparison reuses an identical URL
within its bounded command memo. Modern's existing cheap width/height preflight
skips images for obviously text-only viewports; actual geometry can still cause
a candidate image to be rejected after loading. The planner performs no I/O,
decoding or capability detection. `--no-avatar` and every JSON path skip asset
acquisition. Missing offline/invalid avatars leave useful text. Provider API
request counts, module execution/selection, nullable metrics, presentation data
and public JSON envelopes/values remain unchanged; no image payload or internal
loader metadata enters JSON. Existing flags, themes and configurations continue
to work, with only clarified offline help text and two README usage examples.

## Deterministic verification and previews

`avatar_fixtures.py` generates small local images, including opaque, transparent,
partial-alpha, landscape, portrait, one-pixel, oriented and animated inputs.
Eight source images and eight monochrome style previews live in
`tests/fixtures/avatars/`. Security tests synthesize invalid, truncated, oversized
and excessive-dimension payloads without allocating giant decoded images.
Image/caching tests use temporary directories, not user caches. API and avatar
network guards fail unexpected requests, including offline export paths.

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_avatar*.py'
PYTHONPATH=tests .venv/bin/python tests/preview_avatars.py --case transparent
PYTHONPATH=tests .venv/bin/python tests/preview_avatars.py --case partial --style halfblock --color truecolor
PYTHONPATH=tests .venv/bin/python tests/preview_avatars.py --case portrait --style braille --color 256
PYTHONPATH=tests .venv/bin/python tests/preview_avatars.py --write
PYTHONPATH=tests .venv/bin/python tests/preview_modern.py --case standard-80x24 --ansi
PYTHONPATH=tests .venv/bin/python tests/benchmark_avatars.py
```

Eleven existing modern goldens intentionally changed only in avatar glyphs from
Lanczos downsampling. Their non-avatar content/layout is unchanged, as are the
four avatar-free goldens. Generated previews are not physical-terminal capture.
Benchmarks separate mocked HTTP reads, cold fetch/decode/cache writes, warm disk
read/decode, memo hits, preparation, fitting, encoders and no-avatar asset setup.
There is no claim of lower live-network latency or an end-to-end speedup.

Native graphics, asset conditional-HTTP revalidation, terminal alpha blending,
physical font/background validation and graphical export redesign remain outside
05A. The prepared RGBA API is ready for 05B; no 05B implementation was started.
