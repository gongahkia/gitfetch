"""Protocol-independent avatar acquisition, validation and preparation.

AvatarLoader is the explicit reusable API. A scoped bridge preserves legacy
rendering signatures; the image HTTP client never receives provider tokens.
"""
from __future__ import annotations

import hashlib
import json
import warnings
from collections import OrderedDict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from http.client import HTTPException
from io import BytesIO
from pathlib import Path
from typing import Any, Final, Literal, TypeVar, cast
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from PIL import Image, ImageOps

from gitfetch.avatar_cache import AvatarCache
from gitfetch.cache import CacheStore

AVATAR_TIMEOUT_SECONDS: Final = 10
MAX_AVATAR_BYTES: Final = 5 * 1024 * 1024
MAX_AVATAR_PIXELS: Final = 2048 * 2048
MAX_AVATAR_EDGE: Final = 8192
PREPARED_AVATAR_EDGE: Final = 1024
MAX_AVATAR_REDIRECTS: Final = 3
_FORMATS = ("PNG", "JPEG", "GIF", "WEBP", "BMP")


@dataclass(frozen=True)
class AvatarPolicy:
    directory: Path | None = None
    enabled: bool = False
    ttl_seconds: int = 3600
    offline: bool = False
    refresh: bool = False
    scope: str = "anonymous"

    @classmethod
    def from_cache(cls, cache: CacheStore, *, provider: str, instance: str, token: str | None,
                   mode: str = "public", offline: bool = False) -> AvatarPolicy:
        # No raw credentials, URLs or account names in policy/cache metadata.
        credential = hashlib.sha256((token or "").encode()).hexdigest()
        scope = hashlib.sha256(json.dumps([provider, instance, mode, credential]).encode()).hexdigest()
        return cls(cache.directory, cache.enabled, cache.ttl_seconds, offline, cache.bypass_read, scope)


@dataclass(frozen=True)
class PreparedAvatar:
    # Treat the detached RGBA image as read-only; fit() returns a new image.
    image: Image.Image
    original_size: tuple[int, int]
    oriented_size: tuple[int, int]
    has_transparency: bool
    has_partial_alpha: bool
    source: Literal["network", "cache", "stale-cache"]

    @property
    def effective_size(self) -> tuple[int, int]:
        return self.image.size

    def fit(self, bounds: tuple[int, int]) -> Image.Image:
        """Bounded RGBA copy, retaining aspect ratio, for future backends too."""
        image = self.image.copy()
        image.thumbnail((max(1, min(bounds[0], PREPARED_AVATAR_EDGE)),
                         max(1, min(bounds[1], PREPARED_AVATAR_EDGE))), Image.Resampling.LANCZOS)
        return image


@dataclass(frozen=True)
class AvatarResult:
    asset: PreparedAvatar | None = None
    reason: str | None = None  # Safe category: never URL or exception text.


def _valid_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
        return (len(url) <= 8192 and not any(ord(c) < 33 or ord(c) == 127 for c in url)
                and parts.scheme in {"http", "https"} and bool(parts.hostname)
                and parts.username is None and parts.password is None
                and (parts.port is None or 0 < parts.port < 65536))
    except ValueError:
        return False


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def urlopen(request: Request, *, timeout: int):
    """Local opener: validate redirects explicitly; never install globally."""
    return build_opener(_NoRedirect()).open(request, timeout=timeout)


def _download(url: str) -> bytes:
    for redirects in range(MAX_AVATAR_REDIRECTS + 1):
        if not _valid_url(url):
            raise ValueError("unsupported avatar source")
        request = Request(url, headers={"User-Agent": "gitfetch/2.0.0", "Accept-Encoding": "identity"})
        try:
            with urlopen(request, timeout=AVATAR_TIMEOUT_SECONDS) as response:
                length = response.headers.get("Content-Length")
                if length is not None:
                    try:
                        declared = int(length)
                    except (ValueError, TypeError):
                        declared = 0  # The read bound remains authoritative.
                    if declared > MAX_AVATAR_BYTES:
                        raise ValueError("avatar download too large")
                payload = response.read(MAX_AVATAR_BYTES + 1)
                if len(payload) > MAX_AVATAR_BYTES:
                    raise ValueError("avatar download too large")
                return payload
        except HTTPError as exc:
            try:
                if exc.code not in {301, 302, 303, 307, 308} or redirects == MAX_AVATAR_REDIRECTS:
                    raise ValueError("avatar request failed") from None
                location = exc.headers.get("Location")
                if not location:
                    raise ValueError("invalid avatar redirect") from None
                target = urljoin(url, location)
                if not _valid_url(target) or (urlsplit(url).scheme == "https" and urlsplit(target).scheme != "https"):
                    raise ValueError("unsafe avatar redirect") from None
                url = target
            finally:
                exc.close()
    raise ValueError("too many redirects")


def prepare_avatar(payload: bytes, *, source: Literal["network", "cache", "stale-cache"] = "network") -> PreparedAvatar:
    """Validate before pixel decoding, orient frame zero, bound and detach RGBA."""
    if not payload or len(payload) > MAX_AVATAR_BYTES:
        raise ValueError("invalid avatar size")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        # Verification parses the container without decoding pixels.
        with Image.open(BytesIO(payload), formats=_FORMATS) as probe:
            width, height = probe.size
            if width < 1 or height < 1 or width * height > MAX_AVATAR_PIXELS or max(width, height) > MAX_AVATAR_EDGE:
                raise ValueError("avatar pixel budget exceeded")
            probe.verify()
        with Image.open(BytesIO(payload), formats=_FORMATS) as image:
            image.seek(0)  # Animated avatars deliberately use only frame zero.
            original = image.size
            with ImageOps.exif_transpose(image) as oriented:
                dimensions = oriented.size
                rgba = oriented.convert("RGBA")
                rgba.thumbnail((PREPARED_AVATAR_EDGE, PREPARED_AVATAR_EDGE), Image.Resampling.LANCZOS)
                rgba.info.clear()  # No embedded EXIF, GPS, comments or profiles.
    histogram = rgba.getchannel("A").histogram()
    return PreparedAvatar(rgba, original, dimensions, sum(histogram[:255]) > 0,
                          sum(histogram[1:255]) > 0, source)


class AvatarLoader:
    """One frame/command's bounded decoded-image memo and optional disk cache."""
    def __init__(self, policy: AvatarPolicy | None = None):
        policy = policy or AvatarPolicy()
        self.policy = policy
        self.cache = (AvatarCache(policy.directory, policy.ttl_seconds, MAX_AVATAR_BYTES)
                      if policy.enabled and policy.directory is not None else None)
        self._memo: OrderedDict[str, AvatarResult] = OrderedDict()

    def load(self, url: str | None) -> AvatarResult:
        if not url:
            return AvatarResult(reason="missing")
        if not isinstance(url, str) or not _valid_url(url):
            return AvatarResult(reason="unsupported source")
        if url in self._memo:
            self._memo.move_to_end(url)
            return self._memo[url]
        result = self._load(url)
        self._memo[url] = result
        if len(self._memo) > 8:
            self._memo.popitem(last=False)
        return result

    def _load(self, url: str) -> AvatarResult:
        if self.cache and (not self.policy.refresh or self.policy.offline):
            cached = self.cache.get(self.policy.scope, url, allow_expired=self.policy.offline)
            if cached:
                payload, expired = cached
                try:
                    return AvatarResult(prepare_avatar(payload, source="stale-cache" if expired else "cache"))
                except (OSError, ValueError, SyntaxError, EOFError, Image.DecompressionBombError, Image.DecompressionBombWarning):
                    self.cache.discard(self.policy.scope, url)
        if self.policy.offline:
            return AvatarResult(reason="not cached")
        try:
            payload = _download(url)
            asset = prepare_avatar(payload)
        except (OSError, ValueError, SyntaxError, EOFError, HTTPException, Image.DecompressionBombError, Image.DecompressionBombWarning):
            return AvatarResult(reason="unavailable or invalid")
        if self.cache:
            self.cache.put(self.policy.scope, url, payload)
        return AvatarResult(asset)


_CURRENT: ContextVar[AvatarLoader | None] = ContextVar("gitfetch_avatar_loader", default=None)


@contextmanager
def avatar_context(loader: AvatarLoader | None) -> Iterator[None]:
    token = _CURRENT.set(loader if loader is not None else _CURRENT.get())
    try:
        yield
    finally:
        _CURRENT.reset(token)


F = TypeVar("F", bound=Callable[..., Any])


def avatar_render(function: F) -> F:
    """Bind a CLI-injected loader around legacy config-first rendering APIs."""
    @wraps(function)
    def wrapped(config, *args, **kwargs):
        with avatar_context(config.get("_avatar_loader")):
            return function(config, *args, **kwargs)
    return cast(F, wrapped)


def fetch_avatar_image(url: str | None) -> Image.Image | None:
    """Compatibility API; an explicit AvatarLoader context shares assets."""
    result = (_CURRENT.get() or AvatarLoader()).load(url)
    return result.asset.image if result.asset else None
