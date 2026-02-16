# pgql/utils/config_utils.py

import os
from typing import Optional


class TimeoutConfig:
    """Configuration for HTTP timeouts.
    
    All values can be overridden via environment variables.
    """
    
    @staticmethod
    def get_request_timeout() -> float:
        """Get request timeout in seconds (default: 30s)."""
        return float(os.getenv("PROMPTQL_REQUEST_TIMEOUT", "30.0"))
    
    @staticmethod
    def get_connect_timeout() -> float:
        """Get connection timeout in seconds (default: 10s)."""
        return float(os.getenv("PROMPTQL_CONNECT_TIMEOUT", "10.0"))
    
    @staticmethod
    def get_pool_timeout() -> float:
        """Get connection pool timeout in seconds (default: 5s)."""
        return float(os.getenv("PROMPTQL_POOL_TIMEOUT", "5.0"))
    
    @staticmethod
    def get_max_keepalive_connections() -> int:
        """Get max keepalive connections (default: 5)."""
        return int(os.getenv("PROMPTQL_MAX_KEEPALIVE", "5"))
    
    @staticmethod
    def get_max_connections() -> int:
        """Get max total connections (default: 10)."""
        return int(os.getenv("PROMPTQL_MAX_CONNECTIONS", "10"))
    
    @staticmethod
    def get_poll_interval() -> int:
        """Get polling interval in seconds (default: 2s)."""
        return int(os.getenv("PROMPTQL_POLL_INTERVAL", "2"))
    
    @staticmethod
    def get_max_poll_time() -> int:
        """Get maximum polling time in seconds (default: 120s)."""
        return int(os.getenv("PROMPTQL_MAX_POLL_TIME", "120"))
    
    @staticmethod
    def get_cache_ttl() -> int:
        """Get cache TTL in seconds (default: 300s = 5min)."""
        return int(os.getenv("PROMPTQL_CACHE_TTL", "300"))
