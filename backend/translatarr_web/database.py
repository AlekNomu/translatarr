"""
translatarr_web.database
~~~~~~~~~~~~~~~~~~~~
SQLite database initialisation and per-request connection helper.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import Flask, current_app, g

# ─────────────────────────────────────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────────────────────────────────────

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS media_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    media_type      TEXT NOT NULL CHECK (media_type IN ('movie', 'episode')),
    file_path       TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    year            INTEGER,
    series_name     TEXT,
    season          INTEGER,
    episode         INTEGER,
    has_source_srt  INTEGER DEFAULT 0,
    source_srt_label TEXT,
    has_target_srt  INTEGER DEFAULT 0,
    target_srt_path TEXT,
    file_size       INTEGER,
    duration        REAL,
    added_at        TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_media_type   ON media_items(media_type);
CREATE INDEX IF NOT EXISTS idx_series_name  ON media_items(series_name);

CREATE TABLE IF NOT EXISTS history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    media_id    INTEGER REFERENCES media_items(id) ON DELETE SET NULL,
    file_path   TEXT NOT NULL,
    action      TEXT NOT NULL CHECK (action IN (
        'transcribed', 'translated', 'resynced', 'skipped', 'failed', 'deleted'
    )),
    target_lang TEXT NOT NULL DEFAULT 'fr',
    detail      TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_history_created ON history(created_at DESC);

CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    task_type   TEXT NOT NULL,
    media_id    INTEGER REFERENCES media_items(id) ON DELETE SET NULL,
    status      TEXT DEFAULT 'queued' CHECK (status IN (
        'queued', 'running', 'completed', 'failed', 'cancelled'
    )),
    progress    INTEGER DEFAULT 0,
    detail      TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    started_at  TEXT,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS series_metadata (
    series_name TEXT PRIMARY KEY,
    sonarr_id   INTEGER,
    overview    TEXT,
    poster_url  TEXT,
    fanart_url  TEXT,
    status      TEXT,
    last_aired  TEXT,
    series_path TEXT,
    fetched_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS movie_metadata (
    file_path   TEXT PRIMARY KEY,
    radarr_id   INTEGER,
    overview    TEXT,
    poster_url  TEXT,
    movie_path  TEXT,
    fetched_at  TEXT DEFAULT (datetime('now'))
);
"""

# ─────────────────────────────────────────────────────────────────────────────
# Connection helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    """Return the per-request SQLite connection (stored on Flask ``g``)."""
    if "db" not in g:
        db_path = current_app.config.get("DB_PATH", ":memory:")
        g.db = sqlite3.connect(
            db_path,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


def close_db(_exc: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Initialisation
# ─────────────────────────────────────────────────────────────────────────────

def init_db(db_path: Path) -> None:
    """Create tables if they don't exist."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    conn.close()


def init_app(app: Flask, db_path: Path) -> None:
    """Register the database teardown and store *db_path* for ``get_db``."""
    app.config["DB_PATH"] = str(db_path)
    app.teardown_appcontext(close_db)
