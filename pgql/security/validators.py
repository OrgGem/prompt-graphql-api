# pgql/security/validators.py

from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re
import uuid


class ThreadIDValidator(BaseModel):
    """Validator for thread IDs (UUIDs)."""
    thread_id: str = Field(..., min_length=36, max_length=36)
    
    @field_validator('thread_id')
    def validate_uuid(cls, v):
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid UUID format: {v}")


class MessageValidator(BaseModel):
    """Validator for user messages."""
    message: str = Field(..., min_length=1, max_length=10000)
    
    @field_validator('message')
    def sanitize_message(cls, v):
        # Remove null bytes
        v = v.replace('\x00', '')
        # Validate UTF-8
        try:
            v.encode('utf-8')
        except UnicodeError:
            raise ValueError("Message must be valid UTF-8")
        return v


class URLValidator(BaseModel):
    """Validator for URLs."""
    url: str
    
    @field_validator('url')
    def validate_https(cls, v):
        if not v.startswith('https://') and not v.startswith('http://'):
            raise ValueError("URL must use HTTP or HTTPS protocol")
        return v


def validate_thread_id(thread_id: str) -> str:
    """Validate and return thread ID.
    
    Args:
        thread_id: Thread ID to validate (should be UUID format)
    
    Returns:
        Validated thread ID
    
    Raises:
        ValueError: If thread ID is invalid
    """
    return ThreadIDValidator(thread_id=thread_id).thread_id


def validate_message(message: str) -> str:
    """Validate and sanitize message.
    
    Args:
        message: User message to validate
    
    Returns:
        Sanitized message
    
    Raises:
        ValueError: If message is invalid
    """
    return MessageValidator(message=message).message


def validate_url(url: str) -> str:
    """Validate URL format.
    
    Args:
        url: URL to validate
    
    Returns:
        Validated URL
    
    Raises:
        ValueError: If URL is invalid
    """
    return URLValidator(url=url).url
