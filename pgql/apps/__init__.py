# pgql/apps/__init__.py
"""App management module — multi-app access control."""

from .app_manager import AppManager
from pgql.config import ConfigManager

# Get the same config directory as ConfigManager
config_dir = ConfigManager().config_dir

# Singleton instance
app_manager = AppManager(config_dir=config_dir)

__all__ = ["app_manager", "AppManager"]
