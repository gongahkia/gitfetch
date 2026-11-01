"""Bounded, deterministic Kitty PNG transport. No I/O, layout or detection."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO

from gitfetch.images import PreparedAvatar

MAX_NATIVE_EDGE = 512
MAX_PNG_BYTES = 2 * 1024 * 1024
CHUNK_SIZE = 4096
ST = "\x1b\\"


@dataclass(frozen=True)
class KittyTransmission:
    number: int
    columns: int
    rows: int
    chunks: tuple[str, ...]

    @property
    def cleanup(self) -> str:
        # A number allocates a new terminal-owned ID; never overwrite a guessed
        # global image ID. Delete only our newest image number, including data.
        return f"\x1b_Ga=d,d=N,I={self.number},q=2;{ST}"


def _positive(value: int, maximum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ValueError("invalid Kitty geometry or image number")


def encode_avatar(asset: PreparedAvatar, *, number: int, columns: int, rows: int) -> KittyTransmission:
    _positive(number, 0xffffffff)
    _positive(columns, 256)
    _positive(rows, 256)
    if asset.image.mode != "RGBA" or min(asset.effective_size) < 1 or max(asset.effective_size) > 1024:
        raise ValueError("invalid prepared avatar")
    with asset.fit((MAX_NATIVE_EDGE, MAX_NATIVE_EDGE)) as image, BytesIO() as output:
        image.save(output, "PNG")
        payload = output.getvalue()
    if not payload or len(payload) > MAX_PNG_BYTES:
        raise ValueError("Kitty PNG payload exceeds budget")
    return chunk_png(payload, number=number, columns=columns, rows=rows)


def chunk_png(payload: bytes, *, number: int, columns: int, rows: int) -> KittyTransmission:
    _positive(number, 0xffffffff)
    _positive(columns, 256)
    _positive(rows, 256)
    if not payload.startswith(b"\x89PNG\r\n\x1a\n") or len(payload) > MAX_PNG_BYTES:
        raise ValueError("invalid Kitty PNG payload")
    encoded = base64.b64encode(payload).decode("ascii")
    chunks = []
    for start in range(0, len(encoded), CHUNK_SIZE):
        more = int(start + CHUNK_SIZE < len(encoded))
        control = f"a=T,f=100,t=d,I={number},c={columns},r={rows},C=1,q=2," if start == 0 else "q=2,"
        chunks.append(f"\x1b_G{control}m={more};{encoded[start:start + CHUNK_SIZE]}{ST}")
    return KittyTransmission(number, columns, rows, tuple(chunks))
