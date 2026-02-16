# tests/test_config_utils.py

import pytest
import os
from pgql.utils.config_utils import TimeoutConfig


class TestTimeoutConfig:
    """Test timeout configuration utility."""
    
    def test_default_request_timeout(self, monkeypatch):
        """Test default request timeout."""
        monkeypatch.delenv("PROMPTQL_REQUEST_TIMEOUT", raising=False)
        assert TimeoutConfig.get_request_timeout() == 30.0
    
    def test_custom_request_timeout(self, monkeypatch):
        """Test custom request timeout from env var."""
        monkeypatch.setenv("PROMPTQL_REQUEST_TIMEOUT", "60.0")
        assert TimeoutConfig.get_request_timeout() == 60.0
    
    def test_default_connect_timeout(self, monkeypatch):
        """Test default connect timeout."""
        monkeypatch.delenv("PROMPTQL_CONNECT_TIMEOUT", raising=False)
        assert TimeoutConfig.get_connect_timeout() == 10.0
    
    def test_custom_connect_timeout(self, monkeypatch):
        """Test custom connect timeout from env var."""
        monkeypatch.setenv("PROMPTQL_CONNECT_TIMEOUT", "20.0")
        assert TimeoutConfig.get_connect_timeout() == 20.0
    
    def test_default_pool_timeout(self, monkeypatch):
        """Test default pool timeout."""
        monkeypatch.delenv("PROMPTQL_POOL_TIMEOUT", raising=False)
        assert TimeoutConfig.get_pool_timeout() == 5.0
    
    def test_default_max_keepalive(self, monkeypatch):
        """Test default max keepalive connections."""
        monkeypatch.delenv("PROMPTQL_MAX_KEEPALIVE", raising=False)
        assert TimeoutConfig.get_max_keepalive_connections() == 5
    
    def test_custom_max_keepalive(self, monkeypatch):
        """Test custom max keepalive connections."""
        monkeypatch.setenv("PROMPTQL_MAX_KEEPALIVE", "10")
        assert TimeoutConfig.get_max_keepalive_connections() == 10
    
    def test_default_max_connections(self, monkeypatch):
        """Test default max connections."""
        monkeypatch.delenv("PROMPTQL_MAX_CONNECTIONS", raising=False)
        assert TimeoutConfig.get_max_connections() == 10
    
    def test_custom_max_connections(self, monkeypatch):
        """Test custom max connections."""
        monkeypatch.setenv("PROMPTQL_MAX_CONNECTIONS", "20")
        assert TimeoutConfig.get_max_connections() == 20
    
    def test_default_poll_interval(self, monkeypatch):
        """Test default poll interval."""
        monkeypatch.delenv("PROMPTQL_POLL_INTERVAL", raising=False)
        assert TimeoutConfig.get_poll_interval() == 2
    
    def test_custom_poll_interval(self, monkeypatch):
        """Test custom poll interval."""
        monkeypatch.setenv("PROMPTQL_POLL_INTERVAL", "5")
        assert TimeoutConfig.get_poll_interval() == 5
    
    def test_default_max_poll_time(self, monkeypatch):
        """Test default max poll time."""
        monkeypatch.delenv("PROMPTQL_MAX_POLL_TIME", raising=False)
        assert TimeoutConfig.get_max_poll_time() == 120
    
    def test_custom_max_poll_time(self, monkeypatch):
        """Test custom max poll time."""
        monkeypatch.setenv("PROMPTQL_MAX_POLL_TIME", "300")
        assert TimeoutConfig.get_max_poll_time() == 300
    
    def test_default_cache_ttl(self, monkeypatch):
        """Test default cache TTL."""
        monkeypatch.delenv("PROMPTQL_CACHE_TTL", raising=False)
        assert TimeoutConfig.get_cache_ttl() == 300
    
    def test_custom_cache_ttl(self, monkeypatch):
        """Test custom cache TTL."""
        monkeypatch.setenv("PROMPTQL_CACHE_TTL", "600")
        assert TimeoutConfig.get_cache_ttl() == 600
