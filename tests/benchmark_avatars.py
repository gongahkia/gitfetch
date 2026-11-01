"""Local avatar costs, excluding real network/provider latency and terminal I/O."""
import tempfile
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from statistics import median
from timeit import repeat
from unittest import mock

from avatar_fixtures import image_bytes
from PIL import Image

from gitfetch.images import AvatarLoader, AvatarPolicy, _download, avatar_render, prepare_avatar
from gitfetch.render import _render_avatar_image

URL = "https://benchmark.invalid/avatar.png"


def measure(label, operation, *, number=20):
    batches = repeat(operation, number=number, repeat=5)
    print(f"{label}: {median(batches) * 1000 / number:.4f} ms (median, 5 x {number})")


def main():
    with Image.open(BytesIO(image_bytes("partial"))) as source:
        image = source.resize((1024, 1024), Image.Resampling.LANCZOS)
        output = BytesIO()
        image.save(output, "PNG")
    payload = output.getvalue()
    asset = prepare_avatar(payload)
    print(f"Local RGBA PNG: 1024x1024, {len(payload)} compressed bytes; encoders at 28 cells")

    def response(*args, **kwargs):
        stream = BytesIO(payload)
        stream.headers = {"Content-Length": str(len(payload))}
        return stream

    with tempfile.TemporaryDirectory() as directory:
        policy = AvatarPolicy(Path(directory), True, 3600, scope="benchmark")
        with mock.patch("gitfetch.images.urlopen", side_effect=response):
            measure("Mocked HTTP read only (no decoding)", lambda: _download(URL))
            measure("Cold fetch + decode + atomic cache write", lambda: AvatarLoader(replace(policy, refresh=True)).load(URL))
        with mock.patch("gitfetch.images.urlopen", side_effect=AssertionError("warm network")):
            measure("Warm disk cache + decode", lambda: AvatarLoader(policy).load(URL))
            loader = AvatarLoader(policy)
            loader.load(URL)
            measure("Frame memo hit (no decoding)", lambda: loader.load(URL), number=10000)
        measure("Validate + decode + prepare only", lambda: prepare_avatar(payload))
        measure("Fit prepared RGBA to 96x96", lambda: asset.fit((96, 96)))
        for style in ("ascii", "halfblock", "braille"):
            for color in ("none", "truecolor"):
                measure(f"{style}/{color} resize + encode", lambda style=style, color=color:
                        _render_avatar_image(asset.image, 28, style, color, "BS#&@$%*!:."))

        @avatar_render
        def no_avatar(config):
            return None
        def asset_overhead():
            no_avatar({"_avatar_loader": AvatarLoader(policy)})
        measure("No-avatar asset setup + scoped binding only", asset_overhead, number=10000)


if __name__ == "__main__":
    main()
