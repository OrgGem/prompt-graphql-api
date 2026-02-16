# pgql/config.py

import os
import json
import logging
import base64
import hashlib
import platform
from pathlib import Path
import dotenv
from typing import Optional
from urllib.parse import urlparse
from cryptography.fernet import Fernet
import keyring

# Configure logging
logger = logging.getLogger("promptql_config")

# Load environment variables from .env file if it exists
dotenv.load_dotenv()

class ConfigManager:
    """Manages configuration for the PromptQL MCP server."""
    
    KEYRING_SERVICE = "promptql-mcp-server"

    # Complete mapping: ENV_VAR -> config_key
    ENV_MAPPINGS = {
        "PROMPTQL_API_KEY": "api_key",
        "PGQL_BASE_URL": "base_url",
        "PROMPTQL_AUTH_TOKEN": "auth_token",
        "PROMPTQL_AUTH_MODE": "auth_mode",
        "PROMPTQL_HASURA_GRAPHQL_ENDPOINT": "hasura_graphql_endpoint",
        "PROMPTQL_HASURA_ADMIN_SECRET": "hasura_admin_secret",
        "DASHBOARD_API_KEY": "dashboard_api_key",
        # LLM Configuration (OpenAI-compatible)
        "LLM_API_KEY": "llm_api_key",
        "LLM_BASE_URL": "llm_base_url",
        "LLM_MODEL": "llm_model",
        "LLM_TEMPERATURE": "llm_temperature",
        "LLM_MAX_TOKENS": "llm_max_tokens",
    }

    # Reverse mapping: config_key -> ENV_VAR (for get() lookups)
    CONFIG_TO_ENV = {v: k for k, v in ENV_MAPPINGS.items()}
    
    def __init__(self):
        """Initialize the configuration manager."""
        # Use /app/data in Docker, ~/.promptql-mcp locally
        if os.path.exists("/app/data"):
            self.config_dir = Path("/app/data")
        else:
            self.config_dir = Path(os.path.expanduser("~/.promptql-mcp"))
        self.config_file = self.config_dir / "config.json"
        self.config = self._load_config()
    
    def _get_encryption_key(self) -> bytes:
        """Generate encryption key from system-specific data."""
        salt = f"{platform.node()}-{os.path.expanduser('~')}"
        key = hashlib.pbkdf2_hmac('sha256', salt.encode(), b'promptql-mcp', 100000)
        return base64.urlsafe_b64encode(key[:32])
    
    def _encrypt(self, data: str) -> str:
        """Encrypt sensitive data."""
        f = Fernet(self._get_encryption_key())
        return f.encrypt(data.encode()).decode()
    
    def _decrypt(self, data: str) -> str:
        """Decrypt sensitive data."""
        try:
            f = Fernet(self._get_encryption_key())
            return f.decrypt(data.encode()).decode()
        except Exception as e:
            logger.debug(f"Decryption failed (may be plaintext): {e}")
            # Return as-is if decryption fails (backward compatibility)
            return data
    
    def _validate_url(self, url: str, require_https: bool = True) -> bool:
        """Validate URL format and schema."""
        try:
            parsed = urlparse(url)
            if require_https and parsed.scheme != 'https':
                logger.warning(f"Non-HTTPS URL detected: {url}")
                if os.getenv("PROMPTQL_STRICT_HTTPS", "true").lower() == "true":
                    raise ValueError("HTTPS required for production")
            return True
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Invalid URL: {url} - {e}")
            return False
    
    def _load_config(self) -> dict:
        """Load configuration: saved file first, then env vars override.
        
        Priority (highest to lowest):
        1. Environment variables (always win)
        2. Saved config file (persists UI changes)
        3. Defaults (empty)
        
        After merging, the result is saved back to disk.
        """
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Step 1: Load saved config from file (if exists)
        config = {}
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    config = json.load(f)
                    logger.info(f"Loaded saved config from {self.config_file}")
            except Exception as e:
                logger.error(f"Error loading config file: {e}")
        
        # Step 2: Overlay env vars (env always takes priority)
        env_updated = False
        for env_key, config_key in self.ENV_MAPPINGS.items():
            env_val = os.environ.get(env_key, "").strip()
            if env_val:
                old_val = config.get(config_key)
                if old_val != env_val:
                    config[config_key] = env_val
                    env_updated = True
                    logger.info(f"Config '{config_key}' set from env var {env_key}")
        
        # Step 3: Save merged config back to disk for persistence
        if env_updated or not self.config_file.exists():
            try:
                with open(self.config_file, "w") as f:
                    json.dump(config, f, indent=2)
                try:
                    os.chmod(self.config_file, 0o600)
                except OSError:
                    pass  # Windows doesn't support chmod
                logger.info(f"Saved merged config to {self.config_file}")
            except Exception as e:
                logger.error(f"Error saving config file: {e}")
        
        return config
    
    def save_config(self) -> None:
        """Save configuration to file."""
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.config, f, indent=2)
            
            try:
                os.chmod(self.config_file, 0o600)
            except OSError:
                pass  # Windows doesn't support chmod
            logger.info(f"Configuration saved to {self.config_file}")
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get config value. Priority: env var > keyring > saved config."""
        sensitive_keys = ['api_key', 'auth_token', 'admin_secret', 'hasura_admin_secret', 'llm_api_key']
        
        # 1. Check env var first (always wins at runtime too)
        env_key = self.CONFIG_TO_ENV.get(key.lower())
        if env_key:
            env_val = os.environ.get(env_key, "").strip()
            if env_val:
                return env_val
        
        # 2. Try keyring for sensitive keys
        if key.lower() in sensitive_keys:
            try:
                value = keyring.get_password(self.KEYRING_SERVICE, key)
                if value:
                    logger.debug(f"Retrieved {key} from system keyring")
                    return value
            except Exception as e:
                logger.debug(f"Keyring not available for {key}: {e}")
        
        # 3. Try saved config file
        value = self.config.get(key.lower(), default)
        if value and key.lower() in sensitive_keys:
            return self._decrypt(value)
        return value
    
    def set(self, key: str, value: str) -> None:
        """Set config value, using keyring for sensitive keys."""
        if not value:
            logger.warning(f"Attempted to set empty value for {key}")
            return
        
        sensitive_keys = ['api_key', 'auth_token', 'admin_secret', 'llm_api_key']
        
        # Validate URLs (skip strict HTTPS for LLM and local endpoints)
        if 'url' in key.lower():
            require_https = 'llm_' not in key.lower() and 'base_url' != key.lower()
            if not self._validate_url(value, require_https=require_https):
                raise ValueError(f"Invalid URL format for {key}")
        
        # Try to use keyring for sensitive keys
        if key.lower() in sensitive_keys:
            try:
                keyring.set_password(self.KEYRING_SERVICE, key, value)
                logger.info(f"Stored {key} in system keyring")
                # Also save encrypted version as backup
                self.config[key.lower()] = self._encrypt(value)
                self.save_config()
                return
            except Exception as e:
                logger.warning(f"Keyring failed for {key}, using encrypted file: {e}")
                # Fallback to encrypted file
                self.config[key.lower()] = self._encrypt(value)
                self.save_config()
                return
        
        # Non-sensitive keys: store as plaintext
        self.config[key.lower()] = value
        self.save_config()
        logger.info(f"Updated configuration for {key}")
    
    def is_configured(self) -> bool:
        """Check if the essential configuration is present.
        
        Required: api_key, base_url
        Optional: auth_token (only needed for DDN/PromptQL Cloud)
        """
        return (bool(self.get("api_key")) and
                bool(self.get("base_url")))

    def get_auth_mode(self) -> str:
        """Get the authentication mode, defaulting to 'public' if not set."""
        return self.get("auth_mode", "public")

    @staticmethod
    def generate_api_key(prefix: str = "pgql", length: int = 32) -> str:
        """Generate a random API key."""
        import secrets
        token = secrets.token_urlsafe(length)
        return f"{prefix}_{token}"