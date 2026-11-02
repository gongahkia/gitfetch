"""Deterministic security, caching, preparation and image-policy regression tests."""
import copy
import os
import tempfile
import unittest
import warnings
from dataclasses import replace
from http.client import IncompleteRead
from io import BytesIO
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError, URLError

from avatar_fixtures import CASES, image_bytes, oversized_dimensions
from PIL import Image

from gitfetch.avatar_cache import AvatarCache
from gitfetch.cache import CacheStore
from gitfetch.images import (
    AVATAR_TIMEOUT_SECONDS,
    MAX_AVATAR_BYTES,
    MAX_AVATAR_EDGE,
    MAX_AVATAR_PIXELS,
    MAX_AVATAR_REDIRECTS,
    PREPARED_AVATAR_EDGE,
    AvatarLoader,
    AvatarPolicy,
    avatar_context,
    fetch_avatar_image,
    prepare_avatar,
)

URL = "https://avatars.example.test/image.png?signature=secret"


def response(payload=None, headers=None):
    stream = BytesIO(image_bytes() if payload is None else payload)
    stream.headers = {} if headers is None else headers
    return stream


class PreparationTests(unittest.TestCase):
    def test_all_local_image_fixtures_prepare_as_detached_rgba(self):
        for case in CASES:
            with self.subTest(case=case):
                asset = prepare_avatar(image_bytes(case))
                self.assertEqual(asset.image.mode, "RGBA")
                self.assertGreater(asset.image.width, 0)
                self.assertLessEqual(max(asset.effective_size), PREPARED_AVATAR_EDGE)
                self.assertNotIn("exif", asset.image.info)
                self.assertEqual(asset.source, "network")

    def test_original_and_effective_geometry(self):
        for case, dimensions in [("opaque", (64, 64)), ("landscape", (160, 80)), ("portrait", (80, 160)), ("tiny", (1, 1))]:
            asset = prepare_avatar(image_bytes(case))
            self.assertEqual(asset.original_size, dimensions)
            self.assertEqual(asset.oriented_size, dimensions)
            self.assertEqual(asset.effective_size, dimensions)

    def test_exif_orientation_applied_once(self):
        asset = prepare_avatar(image_bytes("oriented"))
        self.assertEqual(asset.original_size, (80, 40))
        self.assertEqual(asset.oriented_size, (40, 80))
        self.assertEqual(asset.effective_size, (40, 80))
        self.assertNotIn(274, asset.image.getexif())

    def test_animation_is_static_first_frame(self):
        data = image_bytes("animated")
        with Image.open(BytesIO(data)) as original:
            expected = original.convert("RGBA").tobytes()
        asset = prepare_avatar(data)
        self.assertEqual(asset.image.tobytes(), expected)
        self.assertFalse(getattr(asset.image, "is_animated", False))

    def test_alpha_metadata_and_pixels_preserved(self):
        opaque = prepare_avatar(image_bytes())
        transparent = prepare_avatar(image_bytes("transparent"))
        partial = prepare_avatar(image_bytes("partial"))
        self.assertFalse(opaque.has_transparency)
        self.assertTrue(transparent.has_transparency)
        self.assertFalse(transparent.has_partial_alpha)
        self.assertTrue(partial.has_partial_alpha)
        self.assertIn(128, partial.image.getchannel("A").get_flattened_data())
        self.assertEqual(transparent.image.getpixel((0, 0))[3], 0)

    def test_large_but_allowed_image_is_prepared_at_bounded_size(self):
        output = BytesIO()
        Image.new("RGB", (2048, 1024), "red").save(output, "PNG")
        asset = prepare_avatar(output.getvalue())
        self.assertEqual(asset.original_size, (2048, 1024))
        self.assertEqual(asset.effective_size, (1024, 512))

    def test_fit_retains_aspect_ratio_and_does_not_mutate(self):
        for case, expected in [("landscape", (32, 16)), ("portrait", (16, 32))]:
            asset = prepare_avatar(image_bytes(case))
            original = asset.image.tobytes()
            fitted = asset.fit((32, 32))
            self.assertEqual(fitted.size, expected)
            fitted.putpixel((0, 0), (0, 0, 0, 0))
            self.assertEqual(asset.image.tobytes(), original)
            self.assertLessEqual(max(asset.fit((100000, 100000)).size), PREPARED_AVATAR_EDGE)

    def test_invalid_truncated_and_unsupported_formats_rejected(self):
        for payload in (b"", b"not an image", image_bytes()[:50], image_bytes()[:-16], b'<svg xmlns="http://www.w3.org/2000/svg"/>'):
            with self.subTest(length=len(payload)), self.assertRaises((OSError, ValueError, SyntaxError)):
                prepare_avatar(payload)

    def test_compressed_limit_checked_before_open(self):
        with (mock.patch("gitfetch.images.Image.open", side_effect=AssertionError("decode not allowed")),
              self.assertRaises(ValueError)):
            prepare_avatar(b"x" * (MAX_AVATAR_BYTES + 1))

    def test_decoded_pixel_and_edge_limits_precede_verification_or_load(self):
        for dimensions in ((MAX_AVATAR_PIXELS, 2), (MAX_AVATAR_EDGE + 1, 1), (2049, 2048)):
            with (self.subTest(dimensions=dimensions),
                  mock.patch.object(Image.Image, "verify", side_effect=AssertionError("too late")),
                  self.assertRaises((ValueError, Image.DecompressionBombError))):
                prepare_avatar(oversized_dimensions(*dimensions))

    def test_pillow_bomb_warning_and_error_are_graceful(self):
        for size in ((11, 10), (21, 10)):
            with (mock.patch("gitfetch.images.Image.MAX_IMAGE_PIXELS", 100),
                  mock.patch("gitfetch.images._download", return_value=oversized_dimensions(*size)),
                  warnings.catch_warnings(record=True) as emitted):
                self.assertIsNone(AvatarLoader().load(URL).asset)
                self.assertFalse(emitted)


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "cache"
        self.policy = AvatarPolicy(self.root, True, 60, scope="test-provider-instance-auth")
        self.payload = image_bytes()

    def loader(self, **overrides):
        return AvatarLoader(replace(self.policy, **overrides))

    def fetch(self, loader=None, payload=None):
        with mock.patch("gitfetch.images.urlopen", return_value=response(self.payload if payload is None else payload)) as http:
            result = (loader or self.loader()).load(URL)
        return result, http

    def test_cold_fetch_populates_binary_cache(self):
        result, http = self.fetch()
        self.assertEqual(result.asset.source, "network")
        self.assertEqual(http.call_count, 1)
        files = list((self.root / "avatars-v1").iterdir())
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].read_bytes(), self.payload)
        self.assertEqual(files[0].suffix, ".avatar")
        self.assertNotIn("secret", files[0].name)
        self.assertFalse(list(self.root.glob("*.json")))

    def test_warm_cache_avoids_network_and_preserves_image(self):
        first, _ = self.fetch()
        with mock.patch("gitfetch.images.urlopen", side_effect=AssertionError("warm fetch")):
            second = self.loader().load(URL)
        self.assertEqual(second.asset.source, "cache")
        self.assertEqual(first.asset.image.tobytes(), second.asset.image.tobytes())

    def test_refresh_bypasses_read_and_updates_entry(self):
        self.fetch()
        result, http = self.fetch(self.loader(refresh=True), image_bytes("transparent"))
        self.assertEqual(result.asset.source, "network")
        self.assertTrue(result.asset.has_transparency)
        http.assert_called_once()
        self.assertTrue(self.loader(offline=True).load(URL).asset.has_transparency)

    def test_expired_cache_is_refetched_online(self):
        self.fetch()
        path = self.loader().cache.path_for(self.policy.scope, URL)
        os.utime(path, (1, 1))
        result, http = self.fetch(payload=image_bytes("portrait"))
        self.assertEqual(result.asset.effective_size, (80, 160))
        http.assert_called_once()

    def test_offline_uses_fresh_and_stale_cached_images_without_network(self):
        self.fetch()
        for stale in (False, True):
            if stale:
                os.utime(self.loader().cache.path_for(self.policy.scope, URL), (1, 1))
            with mock.patch("gitfetch.images.urlopen", side_effect=AssertionError("offline network")):
                result = self.loader(offline=True).load(URL)
            self.assertEqual(result.asset.source, "stale-cache" if stale else "cache")

    def test_offline_missing_never_fetches(self):
        with mock.patch("gitfetch.images.urlopen", side_effect=AssertionError("offline network")):
            result = self.loader(offline=True).load(URL)
        self.assertIsNone(result.asset)
        self.assertEqual(result.reason, "not cached")

    def test_offline_wins_even_if_refresh_is_also_requested(self):
        self.fetch()
        with mock.patch("gitfetch.images.urlopen", side_effect=AssertionError("offline network")):
            self.assertIsNotNone(self.loader(offline=True, refresh=True).load(URL).asset)

    def test_cache_disabled_does_not_touch_disk(self):
        self.fetch(self.loader(enabled=False))
        self.assertFalse(self.root.exists())
        with mock.patch("gitfetch.images.urlopen", side_effect=AssertionError("offline network")):
            self.assertIsNone(self.loader(enabled=False, offline=True).load(URL).asset)
        self.assertFalse(self.root.exists())

    def test_cache_disabled_refetches_in_new_invocation(self):
        for _ in range(2):
            _, http = self.fetch(self.loader(enabled=False))
            http.assert_called_once()

    def test_repeated_load_and_legacy_calls_share_one_fetch_and_decode(self):
        loader = self.loader()
        with (mock.patch("gitfetch.images.urlopen", return_value=response()) as http,
              mock.patch("gitfetch.images.prepare_avatar", wraps=prepare_avatar) as decode,
              avatar_context(loader)):
            first = loader.load(URL).asset
            self.assertIs(fetch_avatar_image(URL), first.image)
            self.assertIs(loader.load(URL).asset, first)
        self.assertEqual((http.call_count, decode.call_count), (1, 1))

    def test_failures_are_memoized_and_safe(self):
        loader = self.loader()
        with mock.patch("gitfetch.images.urlopen", side_effect=URLError(URL)) as http:
            first = loader.load(URL)
            self.assertEqual(loader.load(URL), first)
        self.assertEqual(http.call_count, 1)
        self.assertNotIn(URL, repr(first))
        self.assertNotIn("secret", repr(first))

    def test_corrupt_cache_recovers_online_and_is_removed_offline(self):
        loader = self.loader()
        loader.cache.put(self.policy.scope, URL, b"broken")
        result, http = self.fetch()
        self.assertIsNotNone(result.asset)
        http.assert_called_once()
        loader.cache.put(self.policy.scope, URL, b"broken again")
        with mock.patch("gitfetch.images.urlopen", side_effect=AssertionError("offline network")):
            self.assertIsNone(self.loader(offline=True).load(URL).asset)
        self.assertFalse(loader.cache.path_for(self.policy.scope, URL).exists())

    def test_url_changes_never_return_unrelated_cached_avatar(self):
        self.fetch()
        with mock.patch("gitfetch.images.urlopen", side_effect=AssertionError("offline network")):
            self.assertIsNone(self.loader(offline=True).load(URL + "different").asset)

    def test_cache_and_io_failures_leave_profile_asset_usable(self):
        for target in ("gitfetch.avatar_cache.AvatarCache._secure_directory", "gitfetch.avatar_cache.os.replace"):
            with self.subTest(target=target), mock.patch(target, side_effect=PermissionError("cache unavailable")):
                self.assertIsNotNone(self.fetch()[0].asset)
        self.assertFalse(list(self.root.rglob("*.tmp")))

    def test_permissions_and_atomic_replacement(self):
        self.fetch()
        path = self.loader().cache.path_for(self.policy.scope, URL)
        self.assertEqual(self.root.stat().st_mode & 0o777, 0o700)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        real_replace = os.replace
        def replace_checked(source, destination):
            self.assertEqual(Path(source).stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.read_bytes(), self.payload)
            real_replace(source, destination)
        with mock.patch("gitfetch.avatar_cache.os.replace", side_effect=replace_checked):
            self.fetch(self.loader(refresh=True), image_bytes("partial"))
        self.assertEqual(path.read_bytes(), image_bytes("partial"))

    def test_scope_covers_provider_instance_auth_and_access_mode_without_leaking_secrets(self):
        cache = CacheStore(self.root, True, 60)
        keys = []
        for provider, instance, token, mode in [("gitea", "https://one", "tokenA", "public"),
                                               ("forgejo", "https://one", "tokenA", "public"),
                                               ("gitea", "https://two", "tokenA", "public"),
                                               ("gitea", "https://one", "tokenB", "public"),
                                               ("gitea", "https://one", "tokenA", "viewer"),
                                               ("gitea", "https://one", None, "public")]:
            policy = AvatarPolicy.from_cache(cache, provider=provider, instance=instance, token=token, mode=mode)
            keys.append(AvatarCache(self.root, 60, MAX_AVATAR_BYTES).path_for(policy.scope, URL))
            self.assertNotIn("tokenA", repr(policy))
            self.assertNotIn("https://one", repr(policy))
        self.assertEqual(len(set(keys)), len(keys))

    def test_scopes_are_isolated_offline(self):
        self.fetch()
        with mock.patch("gitfetch.images.urlopen", side_effect=AssertionError("offline network")):
            self.assertIsNone(self.loader(scope="different", offline=True).load(URL).asset)

    def test_symlink_entries_and_directories_are_not_followed(self):
        loader = self.loader()
        loader.cache._secure_directory()
        unrelated = Path(self.temp.name) / "unrelated"
        unrelated.write_bytes(self.payload)
        path = loader.cache.path_for(self.policy.scope, URL)
        path.symlink_to(unrelated)
        self.assertIsNone(self.loader(offline=True).load(URL).asset)
        self.fetch(self.loader(refresh=True), image_bytes("partial"))
        self.assertEqual(unrelated.read_bytes(), self.payload)
        path.unlink()
        loader.cache.directory.rmdir()
        loader.cache.directory.symlink_to(unrelated.parent, target_is_directory=True)
        self.assertIsNone(self.loader(offline=True).load(URL).asset)

    def test_bounded_growth_prunes_only_owned_avatar_files(self):
        loader = self.loader()
        loader.cache._secure_directory()
        unrelated = loader.cache.directory / "do-not-remove.txt"
        unrelated.write_text("keep")
        with mock.patch("gitfetch.avatar_cache.MAX_CACHE_ENTRIES", 2), mock.patch("gitfetch.avatar_cache.MAX_CACHE_BYTES", 5):
            for i in range(5):
                loader.cache.put("scope", str(i), b"xx")
        entries = list(loader.cache.directory.glob("*.avatar"))
        self.assertEqual(len(entries), 2)
        self.assertLessEqual(sum(p.stat().st_size for p in entries), 5)
        self.assertEqual(unrelated.read_text(), "keep")

    def test_memo_is_bounded(self):
        loader = self.loader(offline=True)
        for i in range(20):
            loader.load(URL + str(i))
        self.assertLessEqual(len(loader._memo), 8)

    def test_nested_context_resets_and_does_not_leak_offline_policy(self):
        offline = self.loader(offline=True)
        with mock.patch("gitfetch.images.urlopen", return_value=response()) as http:
            with avatar_context(offline):
                with avatar_context(None):
                    self.assertIsNone(fetch_avatar_image(URL))
                self.assertIsNone(fetch_avatar_image(URL))
            self.assertIsNotNone(fetch_avatar_image(URL))
        http.assert_called_once()


class FetchSecurityTests(unittest.TestCase):
    def test_rejects_unsupported_and_credentialed_urls_without_http(self):
        for url in (None, "", "file:///etc/passwd", "ftp://example.test/x", "data:image/png,aaa", "https://user:token@example.test/x",
                    "https://example.test/\nX", "https://example.test:999999/x", "https://", "https://[", "https://example.test/" + "x" * 8193):
            with self.subTest(url=str(url)[:40]), mock.patch("gitfetch.images.urlopen", side_effect=AssertionError("unsafe URL")):
                self.assertIsNone(AvatarLoader().load(url).asset)

    def test_http_and_self_hosted_instances_remain_supported(self):
        for url in ("http://gitlab.internal:3000/avatar", "https://forgejo.example/avatar", "http://127.0.0.1:3000/avatar"):
            with self.subTest(url=url), mock.patch("gitfetch.images.urlopen", return_value=response()) as http:
                self.assertIsNotNone(AvatarLoader().load(url).asset)
                request = http.call_args.args[0]
                self.assertNotIn("Authorization", request.headers)
                self.assertNotIn("Cookie", request.headers)
                self.assertEqual(http.call_args.kwargs["timeout"], AVATAR_TIMEOUT_SECONDS)

    def test_invalid_content_lengths_use_actual_read_bound(self):
        for length in (None, "", "invalid", "-1", "1.5", "1"):
            stream = response(headers={"Content-Length": length})
            with self.subTest(length=length), mock.patch("gitfetch.images.urlopen", return_value=stream):
                self.assertIsNotNone(AvatarLoader().load(URL).asset)
                self.assertTrue(stream.closed)

    def test_declared_or_actual_oversize_rejected(self):
        for payload, headers in ((b"x", {"Content-Length": str(MAX_AVATAR_BYTES + 1)}),
                                 (b"x" * (MAX_AVATAR_BYTES + 1), {"Content-Length": "1"})):
            stream = response(payload, headers)
            with mock.patch("gitfetch.images.urlopen", return_value=stream):
                self.assertIsNone(AvatarLoader().load(URL).asset)
                self.assertTrue(stream.closed)

    def test_network_failures_invalid_bytes_and_incomplete_reads_are_optional(self):
        for failure in (URLError("missing"), TimeoutError(), OSError(), IncompleteRead(b"x", 100)):
            with self.subTest(failure=type(failure)), mock.patch("gitfetch.images.urlopen", side_effect=failure):
                result = AvatarLoader().load(URL)
                self.assertIsNone(result.asset)
                self.assertEqual(result.reason, "unavailable or invalid")
        for payload in (b"invalid", image_bytes()[:50], oversized_dimensions(3000, 3000)):
            with mock.patch("gitfetch.images.urlopen", return_value=response(payload)):
                self.assertIsNone(AvatarLoader().load(URL).asset)

    def test_redirect_is_explicit_and_carries_no_credentials(self):
        redirect = HTTPError(URL, 302, "redirect", {"Location": "https://cdn.example.test/avatar"}, BytesIO())
        with mock.patch("gitfetch.images.urlopen", side_effect=[redirect, response()]) as http:
            self.assertIsNotNone(AvatarLoader().load(URL).asset)
        self.assertEqual(http.call_count, 2)
        self.assertEqual(http.call_args.args[0].full_url, "https://cdn.example.test/avatar")
        self.assertNotIn("Authorization", http.call_args.args[0].headers)
        self.assertTrue(redirect.fp is None or redirect.fp.closed)

    def test_relative_redirect_is_supported(self):
        redirect = HTTPError(URL, 302, "redirect", {"Location": "/new.png"}, BytesIO())
        with mock.patch("gitfetch.images.urlopen", side_effect=[redirect, response()]) as http:
            self.assertIsNotNone(AvatarLoader().load(URL).asset)
        self.assertEqual(http.call_args.args[0].full_url, "https://avatars.example.test/new.png")

    def test_unsafe_redirects_and_https_downgrade_are_rejected_before_second_request(self):
        for target in ("file:///etc/passwd", "ftp://example.test/x", "https://user:token@example.test/x", "http://example.test/x", ""):
            redirect = HTTPError(URL, 302, "redirect", {"Location": target}, BytesIO())
            with self.subTest(target=target), mock.patch("gitfetch.images.urlopen", side_effect=redirect) as http:
                self.assertIsNone(AvatarLoader().load(URL).asset)
                http.assert_called_once()
                self.assertTrue(redirect.fp is None or redirect.fp.closed)

    def test_redirect_loops_are_bounded(self):
        errors = [HTTPError(URL, 302, "redirect", {"Location": URL}, BytesIO()) for _ in range(MAX_AVATAR_REDIRECTS + 1)]
        with mock.patch("gitfetch.images.urlopen", side_effect=errors) as http:
            self.assertIsNone(AvatarLoader().load(URL).asset)
        self.assertEqual(http.call_count, MAX_AVATAR_REDIRECTS + 1)

    def test_loader_does_not_mutate_source_policy_or_bytes(self):
        policy = AvatarPolicy(offline=True)
        before = copy.deepcopy(policy)
        with avatar_context(AvatarLoader(policy)):
            fetch_avatar_image(URL)
        self.assertEqual(policy, before)
