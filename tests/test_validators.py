# tests/test_validators.py

import pytest
from pydantic import ValidationError
from pgql.security.validators import (
    validate_thread_id,
    validate_message,
    validate_url,
    ThreadIDValidator,
    MessageValidator,
    URLValidator
)


class TestThreadIDValidator:
    """Test thread ID validation."""
    
    def test_valid_uuid(self):
        """Test that valid UUIDs pass validation."""
        valid_uuids = [
            "123e4567-e89b-12d3-a456-426614174000",
            "550e8400-e29b-41d4-a716-446655440000",
            "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
        ]
        
        for uuid in valid_uuids:
            result = validate_thread_id(uuid)
            assert result == uuid
    
    def test_invalid_uuid_format(self):
        """Test that invalid UUID formats fail validation."""
        invalid_uuids = [
            "not-a-uuid",
            "123",
            "123e4567-e89b-12d3-a456",  # Too short
            "123e4567-e89b-12d3-a456-426614174000-extra",  # Too long
            "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",  # Invalid characters
        ]
        
        for uuid in invalid_uuids:
            with pytest.raises(ValueError):
                validate_thread_id(uuid)
    
    def test_empty_thread_id(self):
        """Test that empty thread ID fails validation."""
        with pytest.raises(ValueError):
            validate_thread_id("")


class TestMessageValidator:
    """Test message validation and sanitization."""
    
    def test_valid_message(self):
        """Test that valid messages pass validation."""
        valid_messages = [
            "Hello, world!",
            "What is 2+2?",
            "This is a longer message with multiple sentences. It should work fine.",
            "Message with special chars: @#$%^&*()",
        ]
        
        for msg in valid_messages:
            result = validate_message(msg)
            assert result == msg
    
    def test_message_null_byte_removal(self):
        """Test that null bytes are removed from messages."""
        message_with_null = "Hello\x00World"
        result = validate_message(message_with_null)
        assert result == "HelloWorld"
        assert '\x00' not in result
    
    def test_message_too_short(self):
        """Test that empty messages fail validation."""
        with pytest.raises(ValidationError):
            validate_message("")
    
    def test_message_too_long(self):
        """Test that messages over 10,000 characters fail validation."""
        long_message = "a" * 10001
        with pytest.raises(ValidationError):
            validate_message(long_message)
    
    def test_message_max_length(self):
        """Test that messages at exactly 10,000 characters pass."""
        max_message = "a" * 10000
        result = validate_message(max_message)
        assert len(result) == 10000
    
    def test_message_utf8_validation(self):
        """Test that messages are validated as UTF-8."""
        # Valid UTF-8
        unicode_message = "Hello 你好 مرحبا"
        result = validate_message(unicode_message)
        assert result == unicode_message


class TestURLValidator:
    """Test URL validation."""
    
    def test_valid_https_url(self):
        """Test that valid HTTPS URLs pass validation."""
        valid_urls = [
            "https://api.example.com",
            "https://api.example.com/path",
            "https://api.example.com:8080",
            "https://api.example.com/path?query=value",
        ]
        
        for url in valid_urls:
            result = validate_url(url)
            assert result == url
    
    def test_valid_http_url(self):
        """Test that HTTP URLs pass validation."""
        http_url = "http://localhost:8080"
        result = validate_url(http_url)
        assert result == http_url
    
    def test_invalid_url_no_protocol(self):
        """Test that URLs without protocol fail validation."""
        invalid_urls = [
            "api.example.com",
            "www.example.com",
            "example.com/path",
        ]
        
        for url in invalid_urls:
            with pytest.raises(ValueError, match="must use HTTP or HTTPS"):
                validate_url(url)
    
    def test_invalid_url_wrong_protocol(self):
        """Test that URLs with wrong protocol fail validation."""
        invalid_urls = [
            "ftp://example.com",
            "file:///path/to/file",
            "ws://example.com",
        ]
        
        for url in invalid_urls:
            with pytest.raises(ValueError, match="must use HTTP or HTTPS"):
                validate_url(url)


class TestValidatorHelperFunctions:
    """Test validator helper functions."""
    
    def test_validate_thread_id_returns_string(self):
        """Test that validate_thread_id returns a string."""
        uuid = "123e4567-e89b-12d3-a456-426614174000"
        result = validate_thread_id(uuid)
        assert isinstance(result, str)
    
    def test_validate_message_returns_string(self):
        """Test that validate_message returns a string."""
        message = "Test message"
        result = validate_message(message)
        assert isinstance(result, str)
    
    def test_validate_url_returns_string(self):
        """Test that validate_url returns a string."""
        url = "https://api.example.com"
        result = validate_url(url)
        assert isinstance(result, str)
