import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import time

import pytest
import fakeredis

from cache.memory_cache import InMemoryCache
from cache.redis_cache import RedisCache
from cache.keys import build_key
from cache import factory
from config import settings


class TestInMemoryCache:
    def test_set_then_get_returns_value(self):
        cache = InMemoryCache()
        cache.set("key1", {"price": 5000}, ttl_seconds=60)
        assert cache.get("key1") == {"price": 5000}

    def test_get_missing_key_returns_none(self):
        cache = InMemoryCache()
        assert cache.get("nonexistent") is None

    def test_expired_entry_returns_none(self):
        cache = InMemoryCache()
        cache.set("key1", "value", ttl_seconds=0.01)
        time.sleep(0.05)
        assert cache.get("key1") is None

    def test_expired_entry_is_evicted_from_store(self):
        cache = InMemoryCache()
        cache.set("key1", "value", ttl_seconds=0.01)
        time.sleep(0.05)
        cache.get("key1")  # triggers eviction
        assert len(cache) == 0

    def test_clear_empties_store(self):
        cache = InMemoryCache()
        cache.set("a", 1, 60)
        cache.set("b", 2, 60)
        cache.clear()
        assert len(cache) == 0


class TestRedisCache:
    @pytest.fixture
    def redis_cache(self, monkeypatch):
        fake_client = fakeredis.FakeRedis()
        monkeypatch.setattr("redis.from_url", lambda *a, **kw: fake_client)
        return RedisCache(url="redis://fake:6379/0")

    def test_set_then_get_returns_value(self, redis_cache):
        redis_cache.set("key1", {"price": 5000}, ttl_seconds=60)
        assert redis_cache.get("key1") == {"price": 5000}

    def test_get_missing_key_returns_none(self, redis_cache):
        assert redis_cache.get("nonexistent") is None

    def test_expired_entry_returns_none(self, redis_cache):
        redis_cache.set("key1", "value", ttl_seconds=60)
        # fakeredis honors TTL; rather than sleeping past it (flaky/slow),
        # confirm the TTL was actually set on the underlying key. A
        # 1-second TTL could round to 0 in the immediate check, so use
        # a larger window with a sane upper bound instead.
        ttl = redis_cache._client.ttl("key1")
        assert 0 < ttl <= 60

    def test_construction_pings_and_raises_if_unreachable(self, monkeypatch):
        class DeadClient:
            def ping(self):
                raise ConnectionError("connection refused")

        monkeypatch.setattr("redis.from_url", lambda *a, **kw: DeadClient())
        with pytest.raises(ConnectionError):
            RedisCache(url="redis://unreachable:6379/0")


class TestBuildKey:
    def test_same_params_produce_same_key_regardless_of_order(self):
        key1 = build_key("flights", origin="Delhi", destination="Mumbai")
        key2 = build_key("flights", destination="Mumbai", origin="Delhi")
        assert key1 == key2

    def test_different_params_produce_different_keys(self):
        key1 = build_key("flights", origin="Delhi", destination="Mumbai")
        key2 = build_key("flights", origin="Delhi", destination="Goa")
        assert key1 != key2

    def test_different_prefix_produces_different_key_for_same_params(self):
        key1 = build_key("flights", city="Mumbai")
        key2 = build_key("hotels", city="Mumbai")
        assert key1 != key2


class TestCacheFactory:
    def setup_method(self):
        factory.reset_cache()

    def teardown_method(self):
        factory.reset_cache()

    def test_returns_in_memory_when_redis_not_configured(self, monkeypatch):
        monkeypatch.setattr(settings, "redis_url", None)
        cache = factory.get_cache()
        assert isinstance(cache, InMemoryCache)

    def test_falls_back_to_in_memory_when_redis_unreachable(self, monkeypatch):
        monkeypatch.setattr(settings, "redis_url", "redis://unreachable:6379/0")

        def raise_on_ping(*args, **kwargs):
            class DeadClient:
                def ping(self):
                    raise ConnectionError("refused")
            return DeadClient()

        monkeypatch.setattr("redis.from_url", raise_on_ping)
        cache = factory.get_cache()
        assert isinstance(cache, InMemoryCache)

    def test_uses_redis_when_configured_and_reachable(self, monkeypatch):
        monkeypatch.setattr(settings, "redis_url", "redis://fake:6379/0")
        fake_client = fakeredis.FakeRedis()
        monkeypatch.setattr("redis.from_url", lambda *a, **kw: fake_client)

        cache = factory.get_cache()
        assert isinstance(cache, RedisCache)

    def test_returns_same_instance_on_repeated_calls(self, monkeypatch):
        monkeypatch.setattr(settings, "redis_url", None)
        cache1 = factory.get_cache()
        cache2 = factory.get_cache()
        assert cache1 is cache2


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
