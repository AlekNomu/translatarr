"""
translatarr_web.settings
~~~~~~~~~~~~~~~~~~~~
Application settings backed by the ``settings`` SQLite table.
"""

from __future__ import annotations

import os
import sqlite3

DEFAULT_SETTINGS: dict[str, str] = {
    "target_lang": "fr",
    "whisper_model": "medium",
    "source_language": "",
    "sync_check": "1",
    "workers": "4",
    "movies_path": "/movies",
    "series_path": "/tv",
    "scan_interval_minutes": "360",
    "scan_on_startup": "1",
    "generate_after_scan": "0",
    # Sonarr integration
    "sonarr_enabled":      "0",
    "sonarr_host":         "sonarr",
    "sonarr_port":         "8989",
    "sonarr_http_timeout": "60",
    "sonarr_api_key":      "",
    # Radarr integration
    "radarr_enabled":      "0",
    "radarr_host":         "radarr",
    "radarr_port":         "7878",
    "radarr_http_timeout": "60",
    "radarr_api_key":      "",
    # Jellyfin integration
    "jellyfin_enabled":      "0",
    "jellyfin_host":         "jellyfin",
    "jellyfin_port":         "8096",
    "jellyfin_http_timeout": "60",
    "jellyfin_api_key":      "",
}

# Descriptions surfaced by the settings API so the frontend can display help text.
WHISPER_MODEL_INFO: dict[str, dict[str, str]] = {
    "tiny":   {"label": "Tiny",   "description": "Fastest, low quality (~1 GB VRAM)"},
    "base":   {"label": "Base",   "description": "Fast, decent quality (~1 GB VRAM)"},
    "small":  {"label": "Small",  "description": "Good speed/quality balance (~2 GB VRAM)"},
    "medium": {"label": "Medium", "description": "Recommended — good quality (~5 GB VRAM)"},
    "large":  {"label": "Large",  "description": "Most accurate, slowest (~10 GB VRAM)"},
}


# Environment variables that override database settings (useful for Docker mounts).
_ENV_OVERRIDES: dict[str, str] = {
    "movies_path": "MOVIES_PATH",
    "series_path": "SERIES_PATH",
}


def _apply_env_overrides(settings: dict[str, str]) -> dict[str, str]:
    for key, env_var in _ENV_OVERRIDES.items():
        value = os.environ.get(env_var)
        if value:
            settings[key] = value
    return settings


def seed_defaults(db: sqlite3.Connection) -> None:
    """Insert default settings if they don't already exist."""
    for key, value in DEFAULT_SETTINGS.items():
        db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
    db.commit()


def load_settings(db: sqlite3.Connection) -> dict[str, str]:
    """Return all settings as a plain dict, with env var overrides applied."""
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    return _apply_env_overrides({row["key"]: row["value"] for row in rows})


def load_setting(db: sqlite3.Connection, key: str) -> str:
    """Return a single setting value, with env var override taking precedence."""
    env_var = _ENV_OVERRIDES.get(key)
    if env_var:
        value = os.environ.get(env_var)
        if value:
            return value
    row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row:
        return row["value"]
    return DEFAULT_SETTINGS.get(key, "")


def save_settings(db: sqlite3.Connection, updates: dict[str, str]) -> None:
    """Upsert one or more settings."""
    for key, value in updates.items():
        db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
    db.commit()
