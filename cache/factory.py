"""
Selects the active cache backend: Redis if REDIS_URL is configured and
reachable, in-memory otherwise. Falls back to in-memory (rather than
raising) if Redis is configured but unreachable — a cache being down
should degrade performance, not take down trip planning.

Returns a process-wide singleton so all clients share one cache
instance (and, for InMemoryCache, one underlying dict) rather than
each client keeping its own private cache that never gets hits from
other clients' identical lookups.
"""
import logging

from cache.base import CacheBackend
from cache.memory_cache import InMemoryCache
from cache.redis_cache import RedisCache
from config import settings

logger = logging.getLogger(__name__)

_cache_instance: CacheBackend | None = None


def get_cache() -> CacheBackend:
    global _cache_instance
    if _cache_instance is not None:
        return _cache_instance

    if settings.redis_url:
        try:
            _cache_instance = RedisCache(settings.redis_url)
            logger.info("Using Redis cache at %s", settings.redis_url)
            return _cache_instance
        except Exception as exc:
            logger.warning("Redis unreachable (%s), falling back to in-memory cache", exc)

    _cache_instance = InMemoryCache()
    return _cache_instance


def reset_cache() -> None:
    """Clears the singleton so the next get_cache() call re-evaluates config. Mainly for tests."""
    global _cache_instance
    _cache_instance = None
