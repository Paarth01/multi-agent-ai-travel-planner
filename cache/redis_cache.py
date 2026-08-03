"""
Redis-backed cache. Values are JSON-serialized (client responses are
plain dicts/lists at the point they're cached — see how clients call
this, always before mapping into Pydantic models). Connection is
verified with a PING at construction time so callers can fail fast and
fall back to InMemoryCache (see cache/factory.py) rather than
discovering Redis is unreachable on the first real request.
"""
import json
from typing import Any

import redis


class RedisCache:
    def __init__(self, url: str, connect_timeout: float = 2.0):
        self._client = redis.from_url(url, socket_connect_timeout=connect_timeout, socket_timeout=connect_timeout)
        self._client.ping()  # raises redis.RedisError if unreachable

    def get(self, key: str) -> Any | None:
        raw = self._client.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._client.set(key, json.dumps(value), ex=ttl_seconds)
