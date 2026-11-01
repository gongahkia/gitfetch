"""Private, bounded binary avatar storage; independent of API response JSON."""
from __future__ import annotations

import hashlib
import os
import re
import stat
import tempfile
import time
from pathlib import Path

MAX_CACHE_ENTRIES = 128
MAX_CACHE_BYTES = 64 * 1024 * 1024
_ENTRY = re.compile(r"[a-f0-9]{64}\.avatar\Z")


class AvatarCache:
    def __init__(self, directory: Path, ttl_seconds: int, max_entry_bytes: int):
        self.root = directory
        self.directory = directory / "avatars-v1"
        self.ttl_seconds = max(0, ttl_seconds)
        self.max_entry_bytes = max_entry_bytes

    def _secure_directory(self) -> None:
        for directory in (self.root, self.directory):
            if directory.is_symlink():
                raise OSError("unsafe cache directory")
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            info = directory.stat()
            if hasattr(os, "getuid") and info.st_uid != os.getuid():
                raise OSError("cache directory belongs to another user")
            directory.chmod(0o700)

    def path_for(self, scope: str, url: str) -> Path:
        key = hashlib.sha256((scope + "\0" + url).encode("utf-8")).hexdigest()
        return self.directory / f"{key}.avatar"

    def get(self, scope: str, url: str, *, allow_expired: bool = False) -> tuple[bytes, bool] | None:
        try:
            self._secure_directory()
            path = self.path_for(scope, url)
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
            if path.is_symlink():
                return None
            with os.fdopen(os.open(path, flags), "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > self.max_entry_bytes:
                    return None
                if hasattr(os, "getuid") and info.st_uid != os.getuid():
                    return None
                if hasattr(os, "fchmod"):
                    os.fchmod(stream.fileno(), 0o600)
                else:
                    os.chmod(path, 0o600)
                expired = info.st_mtime + self.ttl_seconds < time.time()
                if expired and not allow_expired:
                    return None
                payload = stream.read(self.max_entry_bytes + 1)
                return (payload, expired) if len(payload) <= self.max_entry_bytes else None
        except OSError:
            return None

    def discard(self, scope: str, url: str) -> None:
        try:
            self.path_for(scope, url).unlink(missing_ok=True)
        except OSError:
            pass

    def put(self, scope: str, url: str, payload: bytes) -> None:
        if len(payload) > self.max_entry_bytes:
            return
        temporary: str | None = None
        try:
            self._secure_directory()
            with tempfile.NamedTemporaryFile(dir=self.directory, prefix=".avatar-", suffix=".tmp", delete=False) as stream:
                temporary = stream.name
                os.chmod(temporary, 0o600)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path_for(scope, url))
            self._prune()
        except OSError:
            pass  # Optional cache failures must not prevent profile rendering.
        finally:
            if temporary:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass

    def _prune(self) -> None:
        entries = []
        for path in self.directory.iterdir():
            info = path.lstat()
            if _ENTRY.fullmatch(path.name) and stat.S_ISREG(info.st_mode):
                entries.append((info.st_mtime, path.name, info.st_size, path))
            elif path.name.startswith(".avatar-") and path.suffix == ".tmp" and info.st_mtime < time.time() - 86400:
                path.unlink(missing_ok=True)
        total = sum(entry[2] for entry in entries)
        count = len(entries)
        for _, _, size, path in sorted(entries):
            if count <= MAX_CACHE_ENTRIES and total <= MAX_CACHE_BYTES:
                break
            path.unlink(missing_ok=True)
            count -= 1
            total -= size
