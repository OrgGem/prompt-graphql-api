# tests/test_cache.py

import pytest
import time
from pgql.utils.cache import MetadataCache, metadata_cache, cached, async_cached


class TestMetadataCache:
    """Test metadata cache functionality."""
    
    def test_initialization(self):
        """Test cache initialization."""
        cache = MetadataCache(ttl=300, maxsize=100)
        assert cache.cache.ttl == 300
        assert cache.cache.maxsize == 100
        assert cache.hits == 0
        assert cache.misses == 0
    
    def test_set_and_get(self):
        """Test basic set and get operations."""
        cache = MetadataCache(ttl=300)
        
        cache.set("key1", "value1")
        result = cache.get("key1")
        
        assert result == "value1"
        assert cache.hits == 1
        assert cache.misses == 0
    
    def test_cache_miss(self):
        """Test cache miss."""
        cache = MetadataCache(ttl=300)
        
        result = cache.get("nonexistent")
        
        assert result is None
        assert cache.hits == 0
        assert cache.misses == 1
    
    def test_ttl_expiration(self):
        """Test TTL expiration."""
        cache = MetadataCache(ttl=1, maxsize=10)  # 1 second TTL
        
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        
        # Wait for expiration
        time.sleep(1.1)
        
        result = cache.get("key1")
        assert result is None  # Should be expired
    
    def test_clear(self):
        """Test cache clear."""
        cache = MetadataCache(ttl=300)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        cache.clear()
        
        assert cache.get("key1") is None
        assert cache.get("key2") is None
    
    def test_stats(self):
        """Test cache statistics."""
        cache = MetadataCache(ttl=300, maxsize=100)
        
        cache.set("key1", "value1")
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss
        
        stats = cache.stats()
        
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5
        assert stats["size"] == 1
        assert stats["maxsize"] == 100
        assert stats["ttl"] == 300


class TestCachedDecorator:
    """Test cached decorator."""
    
    def test_cached_decorator(self):
        """Test that cached decorator works."""
        call_count = 0
        
        @cached(lambda x: f"key:{x}")
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2
        
        # First call - cache miss
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1
        
        # Second call - cache hit
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Should not increment
        
        # Different argument - cache miss
        result3 = expensive_function(10)
        assert result3 == 20
        assert call_count == 2


class TestAsyncCachedDecorator:
    """Test async_cached decorator."""
    
    @pytest.mark.asyncio
    async def test_async_cached_decorator(self):
        """Test that async_cached decorator works."""
        call_count = 0
        
        @async_cached(lambda x: f"async_key:{x}")
        async def async_expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 3
        
        # First call - cache miss
        result1 = await async_expensive_function(5)
        assert result1 == 15
        assert call_count == 1
        
        # Second call - cache hit
        result2 = await async_expensive_function(5)
        assert result2 == 15
        assert call_count == 1  # Should not increment
        
        # Different argument - cache miss
        result3 = await async_expensive_function(10)
        assert result3 == 30
        assert call_count == 2


class TestGlobalCache:
    """Test global metadata_cache instance."""
    
    def test_global_cache_exists(self):
        """Test that global cache instance exists."""
        assert metadata_cache is not None
        assert isinstance(metadata_cache, MetadataCache)
    
    def test_global_cache_configuration(self):
        """Test global cache configuration."""
        stats = metadata_cache.stats()
        assert stats["ttl"] == 300  # 5 minutes
        assert stats["maxsize"] == 100
