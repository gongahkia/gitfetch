import os
import tempfile
import unittest
from pathlib import Path

from gitfetch.cache import CacheStore


class CacheStoreTests(unittest.TestCase):
    def test_expired_entries_can_be_requested_as_stale_fallbacks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = CacheStore(Path(tmpdir), enabled=True, ttl_seconds=0)
            cache.set("response", {"cached": True})
            self.assertIsNone(cache.get("response"))
            self.assertEqual(cache.get("response", allow_expired=True), {"cached": True})

    def test_cache_files_and_directory_are_private(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            directory = Path(tmpdir) / "cache"
            cache = CacheStore(directory, enabled=True, ttl_seconds=60)
            cache.set("private-response", {"secret": "value"})
            path = cache._path_for("private-response")
            self.assertEqual(cache.get("private-response"), {"secret": "value"})
            self.assertEqual(os.stat(directory).st_mode & 0o777, 0o700)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
