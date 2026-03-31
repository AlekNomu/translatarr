"""Unit tests for translatarr_web.settings — settings CRUD."""

from __future__ import annotations

import sqlite3
import pytest

from translatarr_web.settings import (
    DEFAULT_SETTINGS,
    WHISPER_MODEL_INFO,
    load_setting,
    load_settings,
    save_settings,
    seed_defaults,
)


@pytest.fixture()
def mem_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    return conn


def test_seed_inserts_all_defaults(mem_db):
    seed_defaults(mem_db)
    rows = mem_db.execute("SELECT key FROM settings").fetchall()
    keys = {r["key"] for r in rows}
    assert keys == set(DEFAULT_SETTINGS.keys())


def test_seed_is_idempotent(mem_db):
    seed_defaults(mem_db)
    seed_defaults(mem_db)  # must not raise or duplicate
    count = mem_db.execute("SELECT COUNT(*) FROM settings").fetchone()[0]
    assert count == len(DEFAULT_SETTINGS)


def test_load_settings_returns_all(mem_db):
    seed_defaults(mem_db)
    settings = load_settings(mem_db)
    assert settings["target_lang"] == "fr"
    assert settings["whisper_model"] == "medium"


def test_load_setting_fallback(mem_db):
    # Table is empty — should return the hard-coded default
    value = load_setting(mem_db, "target_lang")
    assert value == DEFAULT_SETTINGS["target_lang"]


def test_load_setting_unknown_key(mem_db):
    assert load_setting(mem_db, "nonexistent_key") == ""


def test_save_settings_upsert(mem_db):
    seed_defaults(mem_db)
    save_settings(mem_db, {"target_lang": "es", "workers": "8"})
    assert load_setting(mem_db, "target_lang") == "es"
    assert load_setting(mem_db, "workers") == "8"


def test_env_override_load_settings(mem_db, monkeypatch):
    seed_defaults(mem_db)
    monkeypatch.setenv("MOVIES_PATH", "/data/films")
    monkeypatch.setenv("SERIES_PATH", "/data/series")
    settings = load_settings(mem_db)
    assert settings["movies_path"] == "/data/films"
    assert settings["series_path"] == "/data/series"
    # Unrelated settings must not be affected
    assert settings["target_lang"] == "fr"


def test_env_override_load_setting(mem_db, monkeypatch):
    seed_defaults(mem_db)
    monkeypatch.setenv("MOVIES_PATH", "/custom/movies")
    assert load_setting(mem_db, "movies_path") == "/custom/movies"


def test_env_override_not_set_uses_db(mem_db, monkeypatch):
    seed_defaults(mem_db)
    save_settings(mem_db, {"movies_path": "/my/movies"})
    monkeypatch.delenv("MOVIES_PATH", raising=False)
    assert load_setting(mem_db, "movies_path") == "/my/movies"


def test_whisper_model_info_has_all_models():
    expected = {"tiny", "base", "small", "medium", "large"}
    assert set(WHISPER_MODEL_INFO.keys()) == expected


def test_whisper_model_info_has_description():
    for key, info in WHISPER_MODEL_INFO.items():
        assert "label" in info, f"Missing label for {key}"
        assert "description" in info, f"Missing description for {key}"
        assert "VRAM" in info["description"], f"Missing VRAM info for {key}"
