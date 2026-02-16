# pgql/dashboard/routes/theme_routes.py
"""Theme customization routes — colors, fonts, branding.

Persists to data/theme.json alongside config.json.
"""

import base64
import os
import json
import re
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger("promptql_dashboard")

router = APIRouter(prefix="/config", tags=["Theme"])

# --- Storage ---

# Same data dir as ConfigManager
if os.path.exists("/app/data"):
    _data_dir = Path("/app/data")
else:
    _data_dir = Path(os.path.expanduser("~/.promptql-mcp"))

_data_dir.mkdir(parents=True, exist_ok=True)
THEME_FILE = _data_dir / "theme.json"

# --- Defaults ---

DEFAULT_THEME = {
    "colors": {
        "accent": "#6366f1",
        "accent_hover": "#5558e6",
        "accent_light": "#eef2ff",
        "bg_primary": "#f5f6f8",
        "bg_secondary": "#ffffff",
        "bg_card": "#ffffff",
        "bg_input": "#f0f2f5",
        "bg_sidebar": "#1e1e2d",
        "text_primary": "#1a1d23",
        "text_secondary": "#5f6b7a",
        "text_muted": "#9ca3af",
        "success": "#10b981",
        "warning": "#f59e0b",
        "error": "#ef4444",
        "info": "#3b82f6",
    },
    "font": "Inter",
    "app_name": "PromptQL",
    "logo_text": "PQ",
    "logo_base64": None,
    "favicon_base64": None,
}

# --- Helpers ---

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{3,8}$")


def _load_theme() -> dict:
    """Load theme from file, falling back to defaults."""
    if THEME_FILE.exists():
        try:
            with open(THEME_FILE, "r") as f:
                saved = json.load(f)
            # Merge with defaults so new keys are always present
            merged = {**DEFAULT_THEME, **saved}
            merged["colors"] = {**DEFAULT_THEME["colors"], **(saved.get("colors") or {})}
            return merged
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to load theme.json: {e}, using defaults")
    return {**DEFAULT_THEME}


def _save_theme(theme: dict):
    """Persist theme to disk."""
    _data_dir.mkdir(parents=True, exist_ok=True)
    with open(THEME_FILE, "w") as f:
        json.dump(theme, f, indent=2)


def _validate_color(value: str) -> bool:
    """Check if value is a valid hex color."""
    return bool(_HEX_RE.match(value))


# --- Request Models ---

class ThemeUpdate(BaseModel):
    colors: Optional[dict] = None
    font: Optional[str] = None
    app_name: Optional[str] = None
    logo_text: Optional[str] = None
    logo_base64: Optional[str] = None
    favicon_base64: Optional[str] = None


# --- Google Fonts ---

AVAILABLE_FONTS = [
    "Inter", "Roboto", "Outfit", "Poppins", "Open Sans",
    "Lato", "Montserrat", "Raleway", "Nunito", "Source Sans 3",
    "DM Sans", "Manrope", "Plus Jakarta Sans", "Work Sans", "Rubik",
]


# --- Endpoints ---

@router.get("/theme")
async def get_theme():
    """Get current theme settings."""
    theme = _load_theme()
    return {
        "theme": theme,
        "defaults": DEFAULT_THEME,
        "available_fonts": AVAILABLE_FONTS,
    }


@router.put("/theme")
async def update_theme(update: ThemeUpdate):
    """Update theme settings (partial update supported)."""
    theme = _load_theme()

    # Update colors
    if update.colors:
        for key, value in update.colors.items():
            if key not in DEFAULT_THEME["colors"]:
                raise HTTPException(400, f"Unknown color key: {key}")
            if not _validate_color(value):
                raise HTTPException(400, f"Invalid color format for {key}: {value}")
            theme["colors"][key] = value

    # Update font
    if update.font is not None:
        if update.font not in AVAILABLE_FONTS:
            raise HTTPException(400, f"Unknown font: {update.font}. Available: {AVAILABLE_FONTS}")
        theme["font"] = update.font

    # Update branding
    if update.app_name is not None:
        name = update.app_name.strip()
        if not name or len(name) > 30:
            raise HTTPException(400, "App name must be 1-30 characters")
        theme["app_name"] = name

    if update.logo_text is not None:
        text = update.logo_text.strip()
        if not text or len(text) > 4:
            raise HTTPException(400, "Logo text must be 1-4 characters")
        theme["logo_text"] = text

    # Update logo image (base64)
    if update.logo_base64 is not None:
        if update.logo_base64 == "":
            theme["logo_base64"] = None
        else:
            # Basic size check (~200KB max after base64)
            if len(update.logo_base64) > 300_000:
                raise HTTPException(400, "Logo image too large (max ~200KB)")
            theme["logo_base64"] = update.logo_base64

    # Update favicon (base64)
    if update.favicon_base64 is not None:
        if update.favicon_base64 == "":
            theme["favicon_base64"] = None
        else:
            if len(update.favicon_base64) > 300_000:
                raise HTTPException(400, "Favicon image too large (max ~200KB)")
            theme["favicon_base64"] = update.favicon_base64

    _save_theme(theme)
    logger.info("Theme updated and saved")
    return {"success": True, "theme": theme}


@router.delete("/theme")
async def reset_theme():
    """Reset theme to defaults."""
    if THEME_FILE.exists():
        THEME_FILE.unlink()
    logger.info("Theme reset to defaults")
    return {"success": True, "theme": DEFAULT_THEME}


# --- Dynamic Favicon ---

# Default SVG favicon
_DEFAULT_FAVICON_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="8" fill="#6366f1"/>
  <text x="16" y="22" font-family="system-ui,sans-serif" font-size="16" font-weight="700" fill="#fff" text-anchor="middle">PQ</text>
</svg>"""


@router.get("/theme/favicon")
async def get_favicon():
    """Serve dynamic favicon — custom upload or default SVG."""
    theme = _load_theme()
    favicon_b64 = theme.get("favicon_base64")

    if favicon_b64:
        # Parse data URI: "data:image/png;base64,iVBOR..."
        if "," in favicon_b64:
            header, data = favicon_b64.split(",", 1)
            # Extract mime type
            mime = "image/png"
            if "image/" in header:
                mime = header.split("image/")[1].split(";")[0]
                mime = f"image/{mime}"
            raw = base64.b64decode(data)
        else:
            mime = "image/png"
            raw = base64.b64decode(favicon_b64)
        return Response(content=raw, media_type=mime,
                        headers={"Cache-Control": "public, max-age=3600"})

    # Default SVG
    return Response(content=_DEFAULT_FAVICON_SVG, media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=3600"})
