# pgql/utils/cache.py

from cachetools import TTLCache
import time
from functools import wraps
from typing import Dict, Any, Callable, Optional
import logging

logger = logging.getLogger(__name__)


class MetadataCache:
    """TTL cache for metadata with statistics tracking.
    
    This implements a time-to-live cache that automatically expires
    entries after a specified duration. Useful for caching Hasura metadata
    and other semi-static data.
    """
    
    def __init__(self, ttl: int = 300, maxsize: int = 100):
        """Initialize metadata cache.
        
        Args:
            ttl: Time to live in seconds (default: 300 = 5 minutes)
            maxsize: Maximum number of cache entries (default: 100)
        """
        self.cache = TTLCache(maxsize=maxsize, ttl=ttl)
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache.
        
        Args:
            key: Cache key
        
        Returns:
            Cached value or None if not found/expired
        """
        if key in self.cache:
            self.hits += 1
            logger.debug(f"Cache HIT: {key}")
            return self.cache[key]
        self.misses += 1
        logger.debug(f"Cache MISS: {key}")
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        self.cache[key] = value
        logger.debug(f"Cache SET: {key}")
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()
        logger.info("Cache cleared")
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dict with hits, misses, hit_rate, and size
        """
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "size": len(self.cache),
            "maxsize": self.cache.maxsize,
            "ttl": self.cache.ttl
        }


# Global cache instance (5 minute TTL)
metadata_cache = MetadataCache(ttl=300, maxsize=100)


def cached(key_func: Callable) -> Callable:
    """Decorator for caching function results.
    
    Args:
        key_func: Function that generates cache key from function arguments
    
    Returns:
        Decorated function with caching
    
    Example:
        @cached(lambda self, endpoint: f"metadata:{endpoint}")
        def export_metadata(self, endpoint):
            # ... actual implementation
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = key_func(*args, **kwargs)
            result = metadata_cache.get(cache_key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            metadata_cache.set(cache_key, result)
            return result
        return wrapper
    return decorator


def async_cached(key_func: Callable) -> Callable:
    """Decorator for caching async function results.
    
    Args:
        key_func: Function that generates cache key from function arguments
    
    Returns:
        Decorated async function with caching
    
    Example:
        @async_cached(lambda self, endpoint: f"metadata:{endpoint}")
        async def export_metadata(self, endpoint):
            # ... actual implementation
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = key_func(*args, **kwargs)
            result = metadata_cache.get(cache_key)
            if result is not None:
                return result
            result = await func(*args, **kwargs)
            metadata_cache.set(cache_key, result)
            return result
        return wrapper
    return decorator
