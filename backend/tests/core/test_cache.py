"""Tests for airwave.core.cache."""

import time
from unittest.mock import patch

import pytest

from airwave.core.cache import SimpleCache, cache, cached


class TestSimpleCache:
    """Tests for SimpleCache."""

    def test_get_miss_returns_none(self):
        c = SimpleCache(default_ttl=60)
        assert c.get("missing") is None

    def test_set_and_get(self):
        c = SimpleCache(default_ttl=60)
        c.set("k", "v")
        assert c.get("k") == "v"

    def test_get_expired_returns_none_and_removes(self):
        c = SimpleCache(default_ttl=0)  # Expire immediately
        c.set("k", "v")
        time.sleep(0.01)
        assert c.get("k") is None
        assert "k" not in c._cache

    def test_delete(self):
        c = SimpleCache(default_ttl=60)
        c.set("k", "v")
        c.delete("k")
        assert c.get("k") is None
        c.delete("nonexistent")  # No-op

    def test_clear(self):
        c = SimpleCache(default_ttl=60)
        c.set("a", 1)
        c.set("b", 2)
        c.clear()
        assert c.get("a") is None
        assert c.get("b") is None

    def test_cleanup_expired(self):
        c = SimpleCache(default_ttl=0)
        c.set("x", 1)
        time.sleep(0.01)
        n = c.cleanup_expired()
        assert n == 1
        assert len(c._cache) == 0

    def test_cleanup_expired_none(self):
        c = SimpleCache(default_ttl=300)
        c.set("x", 1)
        n = c.cleanup_expired()
        assert n == 0
        assert c.get("x") == 1

    def test_stats(self):
        c = SimpleCache(default_ttl=300)
        c.set("a", 1)
        c.set("b", 2)
        st = c.stats()
        assert st["total_entries"] == 2
        assert st["active_entries"] == 2
        assert st["expired_entries"] == 0

    def test_stats_with_expired(self):
        c = SimpleCache(default_ttl=0)
        c.set("a", 1)
        time.sleep(0.01)
        st = c.stats()
        assert st["total_entries"] == 1
        assert st["expired_entries"] == 1
        assert st["active_entries"] == 0

    def test_set_custom_ttl(self):
        c = SimpleCache(default_ttl=60)
        c.set("k", "v", ttl=1)
        assert c.get("k") == "v"
        time.sleep(1.01)
        assert c.get("k") is None


@pytest.mark.asyncio
async def test_cached_decorator_hit():
    """Cached decorator returns cached value on second call."""
    cache.clear()
    call_count = 0

    @cached(ttl=60, key_prefix="test")
    async def expensive():
        nonlocal call_count
        call_count += 1
        return "result"

    r1 = await expensive()
    r2 = await expensive()
    assert r1 == r2 == "result"
    assert call_count == 1


@pytest.mark.asyncio
async def test_cached_decorator_miss_then_set():
    """Cached decorator calls function and caches result."""
    cache.clear()
    @cached(ttl=60, key_prefix="test2")
    async def fn(x: int):
        return x * 2

    assert await fn(3) == 6
    assert await fn(3) == 6
    assert await fn(5) == 10
