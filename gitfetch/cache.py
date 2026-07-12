import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


class CacheStore:
    def __init__(self, directory: Path, enabled: bool, ttl_seconds: int, bypass_read: bool = False) -> None:
        self.directory = directory
        self.enabled = enabled
        self.ttl_seconds = ttl_seconds
        self.bypass_read = bypass_read
        if self.enabled:
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            # Caches may contain private API responses.  Tighten permissions for
            # directories created by older releases as well.
            try:
                self.directory.chmod(0o700)
            except OSError:
                pass

    def _path_for(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.directory / f"{digest}.json"

    def get(self, key: str) -> Any | None:
        if not self.enabled or self.bypass_read:
            return None
        path = self._path_for(key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if payload.get("expires_at", 0) < time.time():
            return None
        return payload.get("value")

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> Any:
        if not self.enabled:
            return value
        ttl = ttl_seconds if ttl_seconds is not None else self.ttl_seconds
        payload = {
            "expires_at": time.time() + max(ttl, 0),
            "value": value,
        }
        path = self._path_for(key)
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.directory,
                prefix=f".{path.name}.",
                delete=False,
            ) as temporary:
                temporary.write(json.dumps(payload, ensure_ascii=True, indent=2))
                temporary_path = temporary.name
            os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, path)
        finally:
            if temporary_path:
                try:
                    os.unlink(temporary_path)
                except FileNotFoundError:
                    pass
        return value
