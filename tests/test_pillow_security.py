"""Patched EXIF processing and the intentional Python support boundary."""
import contextlib
import importlib.util
import io
import json
import struct
import subprocess
import sys
import unittest
import zlib
from pathlib import Path
from unittest import mock

import PIL
from PIL import Image

from gitfetch.images import MAX_AVATAR_BYTES, prepare_avatar


class PillowSecurityTests(unittest.TestCase):
    def test_repeated_exif_markers_fail_safely_and_normal_exif_preserves_alpha(self):
        self.assertEqual(int(PIL.__version__.split('.')[0]), 13)
        image = Image.new('RGBA', (32, 16), (30, 60, 90, 128))
        exif = Image.Exif()
        exif[274] = 6
        # Insert raw eXIf bytes: PNG writers can normalize/drop metadata, which
        # would accidentally remove the adversarial input before testing it.
        data = b'Exif\x00\x00' * 750_000 + exif.tobytes()
        chunk = (struct.pack('>I', len(data)) + b'eXIf' + data
                 + struct.pack('>I', zlib.crc32(b'eXIf' + data)))
        with io.BytesIO() as output:
            image.save(output, 'PNG')
            png = output.getvalue()
        payload = png[:33] + chunk + png[33:]  # after the PNG signature + IHDR
        self.assertLess(len(payload), MAX_AVATAR_BYTES)
        code = """
import json, sys, tempfile
from pathlib import Path
from gitfetch.images import AvatarLoader, AvatarPolicy, MAX_AVATAR_BYTES
payload = sys.stdin.buffer.read(MAX_AVATAR_BYTES + 1)
with tempfile.TemporaryDirectory() as directory:
    loader = AvatarLoader(AvatarPolicy(Path(directory), True, 60, offline=True))
    url = 'https://synthetic.invalid/exif.png'
    loader.cache.put(loader.policy.scope, url, payload)
    result = loader.load(url)
    print(json.dumps({'asset': result.asset is not None, 'reason': result.reason}))
"""
        # A generous process deadline contains a future quadratic regression;
        # this is not a sub-millisecond timing assertion or a live network test.
        result = subprocess.run([sys.executable, '-c', code], input=payload,
                                capture_output=True, timeout=10, check=True)
        rejected = json.loads(result.stdout)
        self.assertFalse(rejected['asset'])
        self.assertEqual(rejected['reason'], 'not cached')
        with io.BytesIO() as output:
            image.save(output, 'PNG', exif=exif)
            prepared = prepare_avatar(output.getvalue())
        self.assertEqual(prepared.image.size, (16, 32))
        self.assertEqual(prepared.oriented_size, (16, 32))
        self.assertEqual(prepared.image.mode, 'RGBA')
        self.assertEqual(prepared.image.getpixel((0, 0)), (30, 60, 90, 128))
        self.assertEqual(prepared.image.info, {})

    def test_installer_rejects_python310_before_pip_or_shell_changes(self):
        path = Path(__file__).parents[1] / 'installer' / 'installation.py'
        spec = importlib.util.spec_from_file_location('installer_security_test', path)
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        with (mock.patch.object(installer.sys, 'version_info', (3, 10, 21)),
              mock.patch.object(installer.subprocess, 'run') as run,
              mock.patch.object(installer, '_ensure_user_bin_on_path') as shell,
              contextlib.redirect_stderr(io.StringIO()) as stderr):
            self.assertEqual(installer.main(), 1)
        self.assertIn('Python 3.11+', stderr.getvalue())
        run.assert_not_called()
        shell.assert_not_called()
