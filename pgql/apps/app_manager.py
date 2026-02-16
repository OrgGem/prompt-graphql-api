# pgql/apps/app_manager.py
"""App Manager — CRUD operations for multi-app access control."""

import json
import secrets
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import logging
from cryptography.fernet import Fernet

try:
    import fcntl
except ImportError:
    fcntl = None  # Windows/macOS fallback — no file locking

logger = logging.getLogger(__name__)

# Constants
API_KEY_PREFIX = "pgql_"
API_KEY_LENGTH = 24  # 143 bits entropy (vs 95 bits for 16 chars)
ENCRYPTION_KEY_ENV = "PGQL_APPS_ENCRYPTION_KEY"


class AppManager:
    """Manages apps with per-app API keys, table access lists, and roles."""

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.apps_file = config_dir / "apps.json"
        self._cipher = self._init_encryption()
        self._data = self._load()

    # ── Persistence ──────────────────────────────────────────────

    def _init_encryption(self) -> Optional[Fernet]:
        """Initialize encryption cipher from environment variable."""
        key = os.getenv(ENCRYPTION_KEY_ENV)
        if not key:
            logger.warning(
                f"{ENCRYPTION_KEY_ENV} not set. API keys will be stored in plain text. "
                "Generate key: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
            return None
        try:
            return Fernet(key.encode())
        except Exception as e:
            logger.error(f"Invalid encryption key: {e}. Keys will be plain text.")
            return None

    def _encrypt_key(self, api_key: str) -> str:
        """Encrypt API key if cipher is available."""
        if not self._cipher:
            return api_key
        return self._cipher.encrypt(api_key.encode()).decode()

    def _decrypt_key(self, encrypted_key: str) -> str:
        """Decrypt API key if cipher is available."""
        if not self._cipher:
            return encrypted_key
        try:
            return self._cipher.decrypt(encrypted_key.encode()).decode()
        except Exception as e:
            logger.error(f"Failed to decrypt key: {e}")
            return encrypted_key  # Fallback to plain text

    def _load(self) -> dict:
        """Load apps.json from disk."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if self.apps_file.exists():
            try:
                with open(self.apps_file, "r") as f:
                    if fcntl:
                        fcntl.flock(f, fcntl.LOCK_SH)
                    data = json.load(f)
                    if fcntl:
                        fcntl.flock(f, fcntl.LOCK_UN)

                # Decrypt API keys on load
                for app in data.get("apps", {}).values():
                    if "api_key" in app:
                        app["api_key"] = self._decrypt_key(app["api_key"])

                logger.info(f"Loaded {len(data.get('apps', {}))} apps from {self.apps_file}")
                return data
            except Exception as e:
                logger.error(f"Error loading apps.json: {e}")
        return {"apps": {}, "schema_cache": {"tables": [], "last_loaded": None}}

    def _save(self):
        """Save apps.json to disk with file locking and encryption."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)

            # Encrypt API keys before save
            data_to_save = {
                "apps": {},
                "schema_cache": self._data.get("schema_cache", {})
            }

            for app_id, app in self._data.get("apps", {}).items():
                encrypted_app = app.copy()
                if "api_key" in encrypted_app:
                    encrypted_app["api_key"] = self._encrypt_key(encrypted_app["api_key"])
                data_to_save["apps"][app_id] = encrypted_app

            # Atomic write with exclusive lock
            with open(self.apps_file, "w") as f:
                if fcntl:
                    fcntl.flock(f, fcntl.LOCK_EX)
                json.dump(data_to_save, f, indent=2)
                if fcntl:
                    fcntl.flock(f, fcntl.LOCK_UN)

            logger.info(f"Saved {len(self._data.get('apps', {}))} apps to {self.apps_file}")
        except Exception as e:
            logger.error(f"Error saving apps.json: {e}")

    # ── CRUD ─────────────────────────────────────────────────────

    def list_apps(self) -> list[dict]:
        """List all apps (API keys masked)."""
        result = []
        for app_id, app in self._data.get("apps", {}).items():
            masked = {**app, "api_key": self._mask_key(app.get("api_key", ""))}
            result.append(masked)
        return result

    def get_app(self, app_id: str) -> Optional[dict]:
        """Get a single app by ID (API key masked)."""
        app = self._data.get("apps", {}).get(app_id)
        if app:
            return {**app, "api_key": self._mask_key(app.get("api_key", ""))}
        return None

    def get_app_with_key(self, app_id: str) -> Optional[dict]:
        """Get app with UNMASKED API key (for internal auth use only)."""
        app = self._data.get("apps", {}).get(app_id)
        return app.copy() if app else None

    def create_app(
        self,
        app_id: str,
        description: str = "",
        allowed_tables: list[str] | None = None,
        role: str = "read",
    ) -> dict:
        """Create a new app. Returns the app with the UNMASKED API key (shown once)."""
        if not app_id or not app_id.strip():
            raise ValueError("app_id is required")

        # Sanitize app_id: lowercase, alphanumeric + hyphens
        app_id = app_id.strip().lower().replace(" ", "-")

        if app_id in self._data.get("apps", {}):
            raise ValueError(f"App '{app_id}' already exists")

        if role not in ("read", "write"):
            raise ValueError("role must be 'read' or 'write'")
        
        # Validate allowed_tables against cached schema
        if allowed_tables:
            allowed_tables = [t.strip() for t in allowed_tables if t.strip()]
            cached = self.get_cached_tables()
            schema_tables = cached.get("tables", [])
            if schema_tables:
                invalid_tables = [t for t in allowed_tables if t not in schema_tables]
                if invalid_tables:
                    raise ValueError(
                        f"Invalid tables not in Hasura schema: {invalid_tables}. "
                        f"Available tables: {', '.join(schema_tables[:10])}{'...' if len(schema_tables) > 10 else ''}"
                    )

        api_key = self._generate_key()

        app = {
            "app_id": app_id,
            "api_key": api_key,
            "allowed_tables": allowed_tables or [],
            "role": role,
            "description": description,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "active": True,
        }

        self._data.setdefault("apps", {})[app_id] = app
        self._save()
        logger.info(f"Created app '{app_id}' with role='{role}', tables={allowed_tables}")

        # Return with unmasked key (only on creation)
        return app.copy()

    def update_app(self, app_id: str, **updates) -> dict:
        """Update an existing app. Returns the updated app (masked key)."""
        if app_id not in self._data.get("apps", {}):
            raise ValueError(f"App '{app_id}' not found")

        app = self._data["apps"][app_id]

        # Validate allowed_tables if being updated
        if "allowed_tables" in updates:
            allowed_tables = updates["allowed_tables"]
            if allowed_tables:
                allowed_tables = [t.strip() for t in allowed_tables if t.strip()]
                cached = self.get_cached_tables()
                schema_tables = cached.get("tables", [])
                if schema_tables:
                    invalid_tables = [t for t in allowed_tables if t not in schema_tables]
                    if invalid_tables:
                        raise ValueError(
                            f"Invalid tables not in Hasura schema: {invalid_tables}. "
                            f"Available: {', '.join(schema_tables[:10])}{'...' if len(schema_tables) > 10 else ''}"
                        )
                updates["allowed_tables"] = allowed_tables

        # Validate role if being updated
        if "role" in updates and updates["role"] not in ("read", "write"):
            raise ValueError("role must be 'read' or 'write'")

        for key, value in updates.items():
            if key in ("description", "allowed_tables", "role", "active"):
                app[key] = value

        self._save()
        logger.info(f"Updated app '{app_id}' with fields: {list(updates.keys())}")
        return self.get_app(app_id)

    def delete_app(self, app_id: str) -> bool:
        """Delete an app."""
        apps = self._data.get("apps", {})
        if app_id not in apps:
            return False
        del apps[app_id]
        self._save()
        logger.info(f"Deleted app '{app_id}'")
        return True

    def regenerate_key(self, app_id: str) -> str:
        """Regenerate API key for an app. Returns the new UNMASKED key."""
        apps = self._data.get("apps", {})
        if app_id not in apps:
            raise ValueError(f"App '{app_id}' not found")
        new_key = self._generate_key()
        apps[app_id]["api_key"] = new_key
        self._save()
        logger.info(f"Regenerated API key for app '{app_id}'")
        return new_key

    # ── Resolve ──────────────────────────────────────────────────

    def resolve_by_api_key(self, api_key: str) -> Optional[dict]:
        """Find an app by its API key. Returns None if not found or inactive."""
        if not api_key:
            return None
        for app in self._data.get("apps", {}).values():
            if app.get("api_key") == api_key and app.get("active", True):
                return app.copy()
        return None

    # ── Schema Cache ─────────────────────────────────────────────

    def get_cached_tables(self) -> dict:
        """Get cached schema tables and metadata."""
        return self._data.get("schema_cache", {"tables": [], "last_loaded": None})

    def update_schema_cache(self, tables: list[str]) -> None:
        """Update the cached table list."""
        self._data["schema_cache"] = {
            "tables": sorted(tables),
            "last_loaded": datetime.now(timezone.utc).isoformat(),
        }
        self._save()
        logger.info(f"Schema cache updated: {len(tables)} tables")

    # ── Helpers ───────────────────────────────────────────────────

    def _generate_key(self) -> str:
        """Generate a cryptographically secure API key."""
        return f"{API_KEY_PREFIX}{secrets.token_urlsafe(API_KEY_LENGTH)}"

    @staticmethod
    def _mask_key(key: str) -> str:
        """Return a masked version of the API key for display."""
        if not key or len(key) < 12:
            return "****"
        return key[:8] + "..." + key[-4:]
