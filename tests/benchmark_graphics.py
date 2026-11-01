"""Offline graphics overhead; no protocol is sent to a real terminal."""
from dataclasses import replace
from io import BytesIO
from random import Random
from statistics import median
from timeit import repeat
from unittest import mock

from avatar_fixtures import image_bytes
from modern_fixtures import REFERENCE, fixture
from PIL import Image

from gitfetch.config import preset_config
from gitfetch.images import AvatarLoader, prepare_avatar
from gitfetch.kitty_graphics import chunk_png, encode_avatar
from gitfetch.layout import Viewport
from gitfetch.render import _render_avatar_image
from gitfetch.terminal_capabilities import AvatarPreferences, classify_terminal, select_avatar_backend
from gitfetch.terminal_output import build_terminal_frame

ENV = {"TERM": "xterm-ghostty", "TERM_PROGRAM": "ghostty"}


def measure(label, operation, *, number=100):
    result = median(repeat(operation, number=number, repeat=5)) * 1000 / number
    print(f"{label}: {result:.4f} ms (median, 5 x {number})")


def main():
    caps = classify_terminal(ENV, stdout_tty=True)
    selected = select_avatar_backend(caps, AvatarPreferences(), output_format="ansi", modern=True)
    asset = prepare_avatar(image_bytes("partial"))
    noise = Image.frombytes("RGBA", (512, 512), Random(7).randbytes(512 * 512 * 4))
    noisy_asset = replace(asset, image=noise)
    output = BytesIO()
    noise.save(output, "PNG")
    payload = output.getvalue()
    print(f"Typical synthetic avatar: {asset.effective_size}; high-entropy PNG: {len(payload)} bytes")
    measure("Passive classification + backend selection", lambda: select_avatar_backend(
        classify_terminal(ENV, stdout_tty=True), AvatarPreferences(), output_format="ansi", modern=True), number=10000)
    measure("Typical prepared PNG + protocol chunks", lambda: encode_avatar(asset, number=7, columns=28, rows=14))
    measure("512x512 high-entropy PNG + chunks", lambda: encode_avatar(noisy_asset, number=7, columns=28, rows=14), number=10)
    measure("Chunk generation only, pre-encoded high-entropy PNG", lambda: chunk_png(payload, number=7, columns=28, rows=14))
    measure("Existing half-block truecolor resize + encode", lambda: _render_avatar_image(asset.image, 28, "halfblock", "truecolor", ".#"))
    config = preset_config("minimal")
    config["display"].update(avatar=True, presentation="modern")
    config["_color_force"] = "on"
    config["_avatar_loader"] = mock.Mock(spec=AvatarLoader)
    config["_avatar_loader"].load.return_value.asset = asset
    _, _, doc = fixture()
    frame_args = {"reference_date": REFERENCE, "image_number": 7}
    # Isolate planner/text/frame construction from PNG compression.
    transmission = encode_avatar(asset, number=7, columns=28, rows=14)
    with mock.patch("gitfetch.terminal_output.encode_avatar", return_value=transmission):
        measure("Frame composition, PNG encoding excluded", lambda: build_terminal_frame(config, doc, selected, Viewport(100, 30), **frame_args))
    measure("Complete typical native frame, asset acquisition excluded", lambda: build_terminal_frame(config, doc, selected, Viewport(100, 30), **frame_args))
    measure("No-avatar backend selection", lambda: select_avatar_backend(caps, AvatarPreferences(), output_format="ansi", modern=True, avatar=False), number=10000)
    print("Active probe overhead: not applicable; no active probe exists")


if __name__ == "__main__":
    main()
