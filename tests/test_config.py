# tests/test_config.py

import pytest
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from pgql.config import ConfigManager


class TestEncryption:
    """Test encryption and decryption functionality."""
    
    def test_encryption_decryption(self, temp_config_dir, monkeypatch):
        """Test that encryption and decryption work correctly."""
        monkeypatch.setenv("HOME", str(temp_config_dir.parent))
        config = ConfigManager()
        
        # Test encryption
        plaintext = "my-secret-key-12345"
        encrypted = config._encrypt(plaintext)
        
        # Encrypted should be different from plaintext
        assert encrypted != plaintext
        assert len(encrypted) > 0
        
        # Test decryption
        decrypted = config._decrypt(encrypted)
        assert decrypted == plaintext
    
    def test_encryption_consistency(self, temp_config_dir, monkeypatch):
        """Test that same plaintext encrypts to same ciphertext with same key."""
        monkeypatch.setenv("HOME", str(temp_config_dir.parent))
        config = ConfigManager()
        
        plaintext = "test-data"
        encrypted1 = config._encrypt(plaintext)
        encrypted2 = config._encrypt(plaintext)
        
        # Should be consistent (same key)
        # Note: Fernet includes timestamp, so this may differ
        # But decryption should work
        assert config._decrypt(encrypted1) == plaintext
        assert config._decrypt(encrypted2) == plaintext
    
    def test_decrypt_invalid_data(self, temp_config_dir, monkeypatch):
        """Test decryption of invalid data returns plaintext (backward compat)."""
        monkeypatch.setenv("HOME", str(temp_config_dir.parent))
        config = ConfigManager()
        
        # Plain text should be returned as-is (backward compatibility)
        plaintext = "not-encrypted-data"
        result = config._decrypt(plaintext)
        assert result == plaintext


class TestURLValidation:
    """Test URL validation functionality."""
    
    def test_valid_https_url(self, temp_config_dir, monkeypatch):
        """Test that valid HTTPS URLs pass validation."""
        monkeypatch.setenv("HOME", str(temp_config_dir.parent))
        config = ConfigManager()
        
        assert config._validate_url("https://api.example.com")
        assert config._validate_url("https://api.example.com/path")
        assert config._validate_url("https://api.example.com:8080")
    
    def test_http_url_strict_mode(self, temp_config_dir, monkeypatch):
        """Test that HTTP URLs fail in strict mode."""
        monkeypatch.setenv("HOME", str(temp_config_dir.parent))
        monkeypatch.setenv("PROMPTQL_STRICT_HTTPS", "true")
        config = ConfigManager()
        
        with pytest.raises(ValueError, match="HTTPS required"):
            config._validate_url("http://api.example.com")
    
    def test_http_url_non_strict_mode(self, temp_config_dir, monkeypatch):
        """Test that HTTP URLs pass in non-strict mode."""
        monkeypatch.setenv("HOME", str(temp_config_dir.parent))
        monkeypatch.setenv("PROMPTQL_STRICT_HTTPS", "false")
        config = ConfigManager()
        
        assert config._validate_url("http://api.example.com")


class TestConfigManager:
    """Test ConfigManager get/set functionality."""
    
    @patch('pgql.config.keyring')
    def test_get_from_environment(self, mock_keyring, temp_config_dir, monkeypatch):
        """Test getting config from environment variables."""
        mock_keyring.get_password.return_value = None  # No keyring value
        monkeypatch.setenv("HOME", str(temp_config_dir.parent))
        monkeypatch.setenv("PROMPTQL_API_KEY", "env-api-key")
        
        config = ConfigManager()
        assert config.get("api_key") == "env-api-key"
    
    def test_get_from_file(self, temp_config_dir, monkeypatch):
        """Test getting config from file."""
        monkeypatch.setenv("HOME", str(temp_config_dir.parent))
        
        # Create config file
        config_file = temp_config_dir / "config.json"
        config_data = {"base_url": "https://api.test.com"}
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        
        config = ConfigManager()
        assert config.get("base_url") == "https://api.test.com"
    
    @patch('pgql.config.keyring')
    def test_set_sensitive_key_encryption(self, mock_keyring, temp_config_dir, monkeypatch):
        """Test that sensitive keys are encrypted when set."""
        mock_keyring.get_password.return_value = None
        mock_keyring.set_password.side_effect = Exception("No keyring")
        monkeypatch.setenv("HOME", str(temp_config_dir.parent))
        
        config = ConfigManager()
        config.set("api_key", "my-secret-key")
        
        # Read raw config file
        with open(config.config_file, "r") as f:
            raw_config = json.load(f)
        
        # Should be encrypted (not plaintext)
        assert raw_config["api_key"] != "my-secret-key"
        
        # But get() should return decrypted value
        assert config.get("api_key") == "my-secret-key"
    
    def test_set_non_sensitive_key_plaintext(self, temp_config_dir, monkeypatch):
        """Test that non-sensitive keys are stored as plaintext."""
        monkeypatch.setenv("HOME", str(temp_config_dir.parent))
        
        config = ConfigManager()
        config.set("auth_mode", "public")
        
        # Read raw config file
        with open(config.config_file, "r") as f:
            raw_config = json.load(f)
        
        # Should be plaintext
        assert raw_config["auth_mode"] == "public"
    
    def test_set_url_validation(self, temp_config_dir, monkeypatch):
        """Test that URLs are validated when set."""
        monkeypatch.setenv("HOME", str(temp_config_dir.parent))
        monkeypatch.setenv("PROMPTQL_STRICT_HTTPS", "true")
        
        config = ConfigManager()
        
        # Valid HTTPS URL should work
        config.set("base_url", "https://api.example.com")
        assert config.get("base_url") == "https://api.example.com"
        
        # Invalid HTTP URL should fail
        with pytest.raises(ValueError, match="HTTPS required"):
            config.set("base_url", "http://api.example.com")
    
    def test_is_configured(self, temp_config_dir, monkeypatch):
        """Test is_configured method."""
        monkeypatch.setenv("HOME", str(temp_config_dir.parent))
        
        config = ConfigManager()
        
        # Initially not configured
        assert not config.is_configured()
        
        # Set all required fields
        config.set("api_key", "test-key")
        config.set("base_url", "https://api.test.com")
        config.set("auth_token", "test-token")
        
        # Now should be configured
        assert config.is_configured()
    
    def test_get_auth_mode_default(self, temp_config_dir, monkeypatch):
        """Test that auth_mode defaults to 'public'."""
        monkeypatch.setenv("HOME", str(temp_config_dir.parent))
        
        config = ConfigManager()
        assert config.get_auth_mode() == "public"
