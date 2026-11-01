"""Small synthetic images generated in memory; no credentials or remote assets."""
import struct
import zlib
from io import BytesIO

from PIL import Image, ImageDraw

CASES = ("opaque", "transparent", "partial", "landscape", "portrait", "tiny", "oriented", "animated")


def image_bytes(case="opaque"):
    size = {"landscape": (160, 80), "portrait": (80, 160), "tiny": (1, 1)}.get(case, (64, 64))
    background = (0, 0, 0, 0) if case in {"transparent", "partial"} else (12, 18, 30, 255)
    image = Image.new("RGBA", size, background)
    if case == "tiny":
        image.putpixel((0, 0), (255, 180, 60, 255))
    else:
        draw = ImageDraw.Draw(image)
        w, h = size
        alpha = 128 if case == "partial" else 255
        draw.ellipse((w // 3, h // 8, 2 * w // 3, h // 2), fill=(235, 190, 140, alpha))
        draw.rounded_rectangle((w // 5, h // 2, 4 * w // 5, h - 3), radius=5, fill=(80, 190, 220, alpha))
    output = BytesIO()
    if case == "oriented":
        image = image.resize((80, 40)).convert("RGB")
        exif = Image.Exif()
        exif[274] = 6
        exif[270] = "synthetic orientation fixture"
        image.save(output, "JPEG", exif=exif)
    elif case == "animated":
        image.convert("RGB").save(output, "GIF", save_all=True,
                                  append_images=[Image.new("RGB", size, "red")], duration=100, loop=0)
    else:
        image.save(output, "PNG")
    return output.getvalue()


def oversized_dimensions(width, height):
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\0")) + chunk(b"IEND", b""))
