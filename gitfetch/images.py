from __future__ import annotations

from io import BytesIO
from typing import Final
from urllib.error import URLError
from urllib.request import Request, urlopen

from PIL import Image


AVATAR_TIMEOUT_SECONDS: Final = 10
MAX_AVATAR_BYTES: Final = 5 * 1024 * 1024


def fetch_avatar_image(url: str | None) -> Image.Image | None:
    """Fetch a bounded avatar image without leaving files in the temp directory."""
    if not url:
        return None
    try:
        request = Request(url, headers={"User-Agent": "gitfetch/2.0.0"})
        with urlopen(request, timeout=AVATAR_TIMEOUT_SECONDS) as response:
            declared_size = response.headers.get("Content-Length")
            if declared_size and int(declared_size) > MAX_AVATAR_BYTES:
                return None
            payload = response.read(MAX_AVATAR_BYTES + 1)
        if len(payload) > MAX_AVATAR_BYTES:
            return None
        with Image.open(BytesIO(payload)) as image:
            return image.convert("RGBA")
    except (OSError, URLError, ValueError):
        return None
