# tests/test_rate_limiter.py

import pytest
import time
from pgql.security.rate_limiter import TokenBucketRateLimiter


class TestTokenBucketRateLimiter:
    """Test token bucket rate limiter."""
    
    def test_initialization(self):
        """Test rate limiter initialization."""
        limiter = TokenBucketRateLimiter(rate=10, per=60)
        assert limiter.rate == 10
        assert limiter.per == 60
    
    def test_allows_initial_requests(self):
        """Test that initial requests are allowed."""
        limiter = TokenBucketRateLimiter(rate=10, per=60)
        
        # First request should be allowed
        assert limiter.is_allowed()
    
    def test_rate_limiting_enforced(self):
        """Test that rate limiting is enforced."""
        # Very restrictive: 2 requests per 60 seconds
        limiter = TokenBucketRateLimiter(rate=2, per=60)
        
        # First 2 requests should be allowed
        assert limiter.is_allowed()
        assert limiter.is_allowed()
        
        # Third request should be denied
        assert not limiter.is_allowed()
    
    def test_token_refill_over_time(self):
        """Test that tokens refill over time."""
        # 10 requests per second
        limiter = TokenBucketRateLimiter(rate=10, per=1)
        
        # Consume all tokens
        for _ in range(10):
            assert limiter.is_allowed()
        
        # Should be rate limited
        assert not limiter.is_allowed()
        
        # Wait for tokens to refill (0.2 seconds = 2 tokens)
        time.sleep(0.2)
        
        # Should allow 1-2 more requests
        assert limiter.is_allowed()
    
    def test_per_client_rate_limiting(self):
        """Test that rate limiting is per-client."""
        limiter = TokenBucketRateLimiter(rate=2, per=60)
        
        # Client A uses up quota
        assert limiter.is_allowed(client_id="client_a")
        assert limiter.is_allowed(client_id="client_a")
        assert not limiter.is_allowed(client_id="client_a")
        
        # Client B should have separate quota
        assert limiter.is_allowed(client_id="client_b")
        assert limiter.is_allowed(client_id="client_b")
        assert not limiter.is_allowed(client_id="client_b")
    
    def test_reset_client_quota(self):
        """Test resetting a client's quota."""
        limiter = TokenBucketRateLimiter(rate=2, per=60)
        
        # Use up quota
        assert limiter.is_allowed(client_id="test")
        assert limiter.is_allowed(client_id="test")
        assert not limiter.is_allowed(client_id="test")
        
        # Reset quota
        limiter.reset(client_id="test")
        
        # Should be able to make requests again
        assert limiter.is_allowed(client_id="test")
        assert limiter.is_allowed(client_id="test")
    
    def test_default_client_id(self):
        """Test that default client_id is used."""
        limiter = TokenBucketRateLimiter(rate=2, per=60)
        
        # Use default client_id
        assert limiter.is_allowed()
        assert limiter.is_allowed()
        assert not limiter.is_allowed()
    
    def test_burst_capacity(self):
        """Test that burst capacity equals rate."""
        limiter = TokenBucketRateLimiter(rate=5, per=60)
        
        # Should allow exactly 5 requests immediately (burst)
        for i in range(5):
            assert limiter.is_allowed(), f"Request {i+1} should be allowed"
        
        # 6th request should be denied
        assert not limiter.is_allowed()
    
    def test_thread_safety(self):
        """Test basic thread safety (sequential calls)."""
        limiter = TokenBucketRateLimiter(rate=10, per=60)
        
        # Make multiple sequential calls
        results = [limiter.is_allowed() for _ in range(12)]
        
        # First 10 should succeed, last 2 should fail
        assert sum(results) == 10
        assert results[:10] == [True] * 10
        assert results[10:] == [False] * 2


class TestGlobalRateLimiter:
    """Test global rate limiter instance."""
    
    def test_global_instance_exists(self):
        """Test that global rate limiter instance exists."""
        from pgql.security.rate_limiter import rate_limiter
        
        assert rate_limiter is not None
        assert isinstance(rate_limiter, TokenBucketRateLimiter)
    
    def test_global_instance_configuration(self):
        """Test that global instance has correct configuration."""
        from pgql.security.rate_limiter import rate_limiter
        
        # Should be 30 requests per 60 seconds
        assert rate_limiter.rate == 30
        assert rate_limiter.per == 60
