"""
Cache backend interface. Both InMemoryCache and RedisCache implement
this shape, so client code (and the factory in cache/factory.py) can
swap between them without caring which is active.
"""
from typing import Any, Protocol


class CacheBackend(Protocol):
    def get(self, key: str) -> Any | None:
        """Returns the cached value, or None on miss/expiry."""
        ...

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        """Stores value under key, expiring after ttl_seconds."""
        ...
