# pgql/security/rate_limiter.py

import time
from collections import defaultdict
from threading import Lock
from typing import Dict


class TokenBucketRateLimiter:
    """Token bucket rate limiter for API requests.
    
    This implements a token bucket algorithm that allows a certain number
    of requests per time period, with burst capacity.
    """
    
    def __init__(self, rate: int = 30, per: int = 60):
        """Initialize rate limiter.
        
        Args:
            rate: Number of requests allowed per time period (default: 30)
            per: Time period in seconds (default: 60)
        """
        self.rate = rate
        self.per = per
        self.allowance: Dict[str, float] = defaultdict(lambda: float(rate))
        self.last_check: Dict[str, float] = defaultdict(lambda: time.time())
        self.lock = Lock()
    
    def is_allowed(self, client_id: str = "default") -> bool:
        """Check if a request is allowed.
        
        Args:
            client_id: Identifier for the client (default: "default")
        
        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        with self.lock:
            current = time.time()
            time_passed = current - self.last_check[client_id]
            self.last_check[client_id] = current
            
            # Refill tokens based on time passed
            self.allowance[client_id] += time_passed * (self.rate / self.per)
            if self.allowance[client_id] > self.rate:
                self.allowance[client_id] = float(self.rate)
            
            # Check if we have tokens available
            if self.allowance[client_id] < 1.0:
                return False
            
            # Consume one token
            self.allowance[client_id] -= 1.0
            return True
    
    def reset(self, client_id: str = "default") -> None:
        """Reset rate limit for a specific client.
        
        Args:
            client_id: Identifier for the client to reset
        """
        with self.lock:
            self.allowance[client_id] = float(self.rate)
            self.last_check[client_id] = time.time()


# Global rate limiter instance (30 requests per minute)
rate_limiter = TokenBucketRateLimiter(rate=30, per=60)
