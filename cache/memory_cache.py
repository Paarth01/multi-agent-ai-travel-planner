"""
In-memory TTL cache — the default backend when REDIS_URL isn't set, or
when Redis is configured but unreachable (see cache/factory.py). Not
shared across processes, so this only helps within a single running
backend instance; fine for local dev and demos, not for a multi-worker
production deployment (use Redis for that).
"""
import time
from threading import Lock
from typing import Any


class InMemoryCache:
    def __init__(self):
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.time() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        with self._lock:
            self._store[key] = (time.time() + ttl_seconds, value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)
