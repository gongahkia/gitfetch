from io import BytesIO
import unittest
from unittest import mock

from PIL import Image

from gitfetch.images import AVATAR_TIMEOUT_SECONDS, MAX_AVATAR_BYTES, fetch_avatar_image


class AvatarImageTests(unittest.TestCase):
    def test_fetch_uses_timeout_and_decodes_in_memory(self) -> None:
        output = BytesIO()
        Image.new("RGB", (2, 3), "red").save(output, "PNG")
        response = mock.MagicMock()
        response.headers = {"Content-Length": str(len(output.getvalue()))}
        response.read.return_value = output.getvalue()
        response.__enter__.return_value = response
        with mock.patch("gitfetch.images.urlopen", return_value=response) as urlopen:
            image = fetch_avatar_image("https://example.test/avatar.png")
        self.assertEqual(image.size, (2, 3))
        self.assertEqual(image.mode, "RGBA")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], AVATAR_TIMEOUT_SECONDS)

    def test_fetch_rejects_oversized_image_before_reading(self) -> None:
        response = mock.MagicMock()
        response.headers = {"Content-Length": str(MAX_AVATAR_BYTES + 1)}
        response.__enter__.return_value = response
        with mock.patch("gitfetch.images.urlopen", return_value=response):
            self.assertIsNone(fetch_avatar_image("https://example.test/avatar.png"))
        response.read.assert_not_called()
