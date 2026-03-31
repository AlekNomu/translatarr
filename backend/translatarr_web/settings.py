"""
translatarr_web.settings
~~~~~~~~~~~~~~~~~~~~
Application settings backed by the ``settings`` SQLite table.
"""

from __future__ import annotations

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
}

# Descriptions surfaced by the settings API so the frontend can display help text.
WHISPER_MODEL_INFO: dict[str, dict[str, str]] = {
    "tiny":   {"label": "Tiny",   "description": "Fastest, low quality (~1 GB VRAM)"},
    "base":   {"label": "Base",   "description": "Fast, decent quality (~1 GB VRAM)"},
    "small":  {"label": "Small",  "description": "Good speed/quality balance (~2 GB VRAM)"},
    "medium": {"label": "Medium", "description": "Recommended — good quality (~5 GB VRAM)"},
    "large":  {"label": "Large",  "description": "Most accurate, slowest (~10 GB VRAM)"},
}


def seed_defaults(db: sqlite3.Connection) -> None:
    """Insert default settings if they don't already exist."""
    for key, value in DEFAULT_SETTINGS.items():
        db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
    db.commit()


def load_settings(db: sqlite3.Connection) -> dict[str, str]:
    """Return all settings as a plain dict."""
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    return {row["key"]: row["value"] for row in rows}


def load_setting(db: sqlite3.Connection, key: str) -> str:
    """Return a single setting value, falling back to the default."""
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
