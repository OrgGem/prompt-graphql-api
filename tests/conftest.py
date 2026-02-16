# tests/conftest.py

import pytest
import os
import tempfile
from pathlib import Path


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Create temporary config directory for testing."""
    config_dir = tmp_path / ".promptql-mcp"
    config_dir.mkdir()
    
    # Set HOME to temp directory
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Windows
    
    return config_dir


@pytest.fixture
def clean_env(monkeypatch):
    """Clean environment variables for testing."""
    # Remove all PROMPTQL_ env vars
    for key in list(os.environ.keys()):
        if key.startswith("PROMPTQL_"):
            monkeypatch.delenv(key, raising=False)
    
    return monkeypatch


@pytest.fixture
def sample_config():
    """Sample configuration data."""
    return {
        "api_key": "test-api-key-123",
        "base_url": "https://api.promptql.hasura.app",
        "auth_token": "test-auth-token-456",
        "auth_mode": "public"
    }
